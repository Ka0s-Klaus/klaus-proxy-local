"""Centinela de fugas: avisa de datos nuevos sin regla tras cada petición (#187).

Analiza el ÚLTIMO mensaje de cada petición (turno del usuario y ``tool_result``)
con los detectores de klaus-scan y avisa de los valores que el proxy no
sustituiría con sus reglas actuales. Decisiones en ADR-002 (#188):

- Umbral por defecto MEDIUM (todo salvo LOW), configurable.
- Un aviso por valor y sesión (sesión = directorio de trabajo + día).
- Análisis en un hilo de fondo: no añade latencia a la petición.
- Los avisos se agrupan: una notificación por sesión y tanda.
- Nunca se escribe el valor en claro: ``alerts.jsonl`` solo guarda el
  identificador ``⟨categoría·hash·longitud⟩``.

Fail-safe: si el centinela falla, se registra y el proxy sigue igual. No es
una barrera: el dato ya ha salido cuando avisa.
"""

from __future__ import annotations

import json
import platform
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from Klaus_proxy_local.business_names import detect_line
from Klaus_proxy_local.scan import safe_id
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
DEFAULT_MIN_CONFIDENCE = "MEDIUM"
NOTIFY_COOLDOWN_S = 30.0
POLL_S = 1.0
_CWD_RE = re.compile(r"Primary working directory: ([^\\\n\"]+)")


def alerts_path() -> Path:
    return Path.home() / ".klaus-proxy" / "alerts.jsonl"


@dataclass(frozen=True)
class Finding:
    value: str
    category: str
    confidence: str
    context: str


def session_of(payload: Any, when: datetime | None = None) -> str:
    """``cwd|día`` de una petición. Sin directorio de trabajo: ``sin-cwd``."""
    cwd = "sin-cwd"
    system = payload.get("system") if isinstance(payload, dict) else None
    m = _CWD_RE.search(json.dumps(system, ensure_ascii=False))
    if m:
        cwd = m.group(1).strip()
    day = (when or datetime.now()).date().isoformat()
    return f"{cwd}|{day}"


def _text_blocks(content: Any) -> Iterable[str]:
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    yield block["text"]
                if "content" in block:
                    yield from _text_blocks(block["content"])


def last_message_text(payload: Any) -> str:
    """Texto del último mensaje de una petición ya parseada."""
    msgs = payload.get("messages") if isinstance(payload, dict) else None
    if not msgs or not isinstance(msgs[-1], dict):
        return ""
    return "\n".join(_text_blocks(msgs[-1].get("content")))


def detect(text: str, scanner: SensitiveDataScanner) -> list[Finding]:
    """Hallazgos de un texto con los detectores de klaus-scan, sin umbral."""
    found: list[Finding] = []
    if not text:
        return found
    for f in scanner.pattern_detector.detect(text, Path("."), 0):
        found.append(Finding(f.value, f.category, "CRITICAL", f.context))
    for line in text.splitlines():
        for value, category, conf, _reason in detect_line(line):
            found.append(Finding(value, category, conf, line))
    return found


class AlertSink:
    """Escribe avisos en ``alerts.jsonl``: una línea JSON por aviso, sin valores."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            self.path.chmod(0o600)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify_macos(title: str, message: str) -> bool:
    """Notificación del sistema. Solo macOS; en otros sistemas no hace nada."""
    if platform.system() != "Darwin":
        return False
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, check=False)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class Sentinel:
    """Hilo de fondo que analiza peticiones y avisa.

    ``observe`` recibe el texto del último mensaje, la sesión y una función
    ``covers(valor) -> bool`` que dice si el proxy ya sustituiría ese valor.
    """

    def __init__(
        self,
        *,
        sink: AlertSink,
        min_confidence: str = DEFAULT_MIN_CONFIDENCE,
        notify: bool = True,
        notifier: Callable[[str, str], Any] | None = None,
        scanner: SensitiveDataScanner | None = None,
        silenced: Callable[[], Iterable[str]] | None = None,
    ) -> None:
        if min_confidence not in RANK:
            min_confidence = DEFAULT_MIN_CONFIDENCE
        self._sink = sink
        self._floor = RANK[min_confidence]
        self._notify = notify
        self._silenced = silenced or (lambda: ())
        self._notifier = notifier or notify_macos
        self._scanner = scanner or SensitiveDataScanner(enable_business=False)
        self._queue: queue.Queue = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._seen: set[tuple[str, str]] = set()
        self._pending: dict[str, int] = {}
        self._last_notified: dict[str, float] = {}
        self.dropped = 0
        self.errors = 0
        self._thread = threading.Thread(
            target=self._run, name="klaus-sentinel", daemon=True
        )
        self._thread.start()

    def observe(self, text: str, session: str, covers: Callable[[str], bool]) -> None:
        """Encola una petición. No bloquea: si la cola está llena, descarta."""
        try:
            self._queue.put_nowait((text, session, covers, datetime.now()))
        except queue.Full:
            self.dropped += 1

    def process(
        self,
        text: str,
        session: str,
        covers: Callable[[str], bool],
        when: datetime,
    ) -> list[dict]:
        """Analiza un texto de forma síncrona y devuelve los avisos nuevos."""
        out: list[dict] = []
        try:
            silenced = set(self._silenced())
        except Exception:  # noqa: BLE001 - una config ilegible no silencia nada
            silenced = set()
        for f in detect(text, self._scanner):
            if RANK.get(f.confidence, 0) < self._floor:
                continue
            if f.category in silenced:
                continue
            if covers(f.value):
                continue
            sid = safe_id(f.value, f.category)
            key = (session, sid)
            if key in self._seen:
                continue
            self._seen.add(key)
            record = {
                "ts": when.isoformat(timespec="seconds"),
                "session": session,
                "category": f.category,
                "id": sid,
                "confidence": f.confidence,
            }
            self._sink.write(record)
            self._pending[session] = self._pending.get(session, 0) + 1
            out.append(record)
        return out

    def flush_notifications(self, now: float | None = None) -> None:
        """Una notificación por sesión con pendientes, respetando el enfriamiento."""
        if not self._notify:
            self._pending.clear()
            return
        now = now if now is not None else time.monotonic()
        for session in list(self._pending):
            if (
                now - self._last_notified.get(session, float("-inf"))
                < NOTIFY_COOLDOWN_S
            ):
                continue
            count = self._pending.pop(session)
            label = session.split("|", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            msg = (
                f"{count} dato(s) nuevo(s) sin regla en «{label or 'sesión'}». "
                "Revísalos con klaus-alerts."
            )
            self._notifier("klaus: fuga potencial", msg)
            self._last_notified[session] = now

    def stop(self, timeout: float = 5.0) -> None:
        """Para el hilo de fondo (usado por el simulacro y los tests)."""
        self._stop.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=POLL_S)
            except queue.Empty:
                self.flush_notifications()
                continue
            try:
                text, session, covers, when = item
                self.process(text, session, covers, when)
            except Exception:  # noqa: BLE001 - el centinela nunca tumba nada
                self.errors += 1
            self.flush_notifications()
