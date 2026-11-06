"""klaus-alerts: revisión en tiempo real de los avisos del centinela (#189, ADR-002).

Comando aparte, en su propia terminal. Solo LEE ``~/.klaus-proxy/alerts.jsonl``
(lo escribe el proxy, #187); lo único que escribe son acciones (una línea JSON
con ``"action"``) y los cambios de reglas en ``config.json`` y el vault, por las
mismas rutas que ``klaus-scan``. Si esta interfaz se cierra o falla, el proxy
sigue igual.

Teclas (sesión → valores → acción):

- ``a`` aprobar: vault y ``config.json``. Pide confirmación.
- ``f`` falso positivo: ``pseudo_pattern_ignore``.
- ``s`` ignorar en esta sesión (solo oculta en la interfaz; ver ADR-002).
- ``v`` ver el contexto, en claro solo en esta pantalla. No se guarda.
- ``c`` silenciar la categoría entera. Pide confirmación.

El valor nunca está en ``alerts.jsonl``. Para ``a`` y ``v`` se recupera de la
captura local más cercana en el tiempo y de la misma sesión, comprobando el
identificador ``⟨categoría·hash·longitud⟩``; el valor vive solo en memoria.
"""

from __future__ import annotations

import curses
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from Klaus_proxy_local.scan import safe_id
from Klaus_proxy_local.sentinel import (
    AlertSink,
    alerts_path,
    detect,
    last_message_text,
    session_of,
)

POLL_MS = 500  # el fichero se relee cada medio segundo (criterio: < 1 s)
CAPTURE_WINDOW_S = 120  # captura candidata: ±2 minutos del aviso
ACTION_RESOLVES = {"approve", "false_positive"}  # ocultan el aviso concreto


def captures_originals_dir() -> Path:
    return Path.home() / ".klaus-proxy" / "captures" / "original"


# --- Lectura incremental de alerts.jsonl -----------------------------------


class AlertFeed:
    """Lee solo las líneas nuevas. Reinicia si el fichero se rota o se trunca."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._offset = 0
        self._inode: int | None = None

    def poll(self) -> list[dict]:
        try:
            st = self.path.stat()
        except OSError:
            return []
        if self._inode is not None and (
            st.st_ino != self._inode or st.st_size < self._offset
        ):
            self._offset = 0
        self._inode = st.st_ino
        if st.st_size <= self._offset:
            return []
        with self.path.open("rb") as fh:
            fh.seek(self._offset)
            data = fh.read()
        end = data.rfind(b"\n")
        if end < 0:  # línea a medias: se espera a la siguiente lectura
            return []
        self._offset += end + 1
        records = []
        for line in data[: end + 1].splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                records.append(rec)
        return records


# --- Estado derivado del fichero ---------------------------------------------


@dataclass
class SessionView:
    key: str
    label: str
    alerts: list[dict] = field(default_factory=list)

    @property
    def last_ts(self) -> str:
        return max((a.get("ts", "") for a in self.alerts), default="")


@dataclass
class State:
    alerts: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)

    def feed(self, records: list[dict]) -> None:
        for rec in records:
            (self.actions if "action" in rec else self.alerts).append(rec)

    def _resolved(self) -> set[tuple[str, str]]:
        return {
            (a["session"], a["id"])
            for a in self.actions
            if a.get("action") in ACTION_RESOLVES
        }

    def _ignored_sessions(self) -> set[str]:
        return {
            a["session"] for a in self.actions if a.get("action") == "ignore_session"
        }

    def _silenced(self) -> set[str]:
        return {
            a["category"] for a in self.actions if a.get("action") == "silence_category"
        }

    def sessions(self) -> list[SessionView]:
        """Avisos pendientes agrupados por sesión; más reciente primero.

        Un valor aparece una sola vez por sesión (el primer aviso). Se ocultan
        los ya tratados, las sesiones ignoradas y las categorías silenciadas.
        """
        resolved, ignored, silenced = (
            self._resolved(),
            self._ignored_sessions(),
            self._silenced(),
        )
        groups: dict[str, SessionView] = {}
        seen: set[tuple[str, str]] = set()
        for a in self.alerts:
            key = (a.get("session", ""), a.get("id", ""))
            if key in seen or key in resolved:
                continue
            if key[0] in ignored or a.get("category") in silenced:
                continue
            seen.add(key)
            session = key[0]
            label = session.split("|", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            view = groups.setdefault(
                session, SessionView(key=session, label=label or "sesión")
            )
            view.alerts.append(a)
        return sorted(groups.values(), key=lambda s: s.last_ts, reverse=True)


# --- Acciones ------------------------------------------------------------------


def record_action(sink: AlertSink, action: str, alert: dict) -> None:
    """Deja rastro en ``alerts.jsonl``. Sin valores."""
    sink.write(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "session": alert.get("session", ""),
            "id": alert.get("id", ""),
            "category": alert.get("category", ""),
        }
    )


def _candidate_captures(originals: Path, when: datetime) -> list[Path]:
    out: list[tuple[float, Path]] = []
    if not originals.is_dir():
        return []
    for p in originals.glob("*.json"):
        try:
            t = datetime.strptime(p.name[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        delta = abs((t - when).total_seconds())
        if delta <= CAPTURE_WINDOW_S:
            out.append((delta, p))
    return [p for _, p in sorted(out, key=lambda x: x[0])]


def recover_value(
    alert: dict, scanner: Any, originals: Path | None = None
) -> tuple[str, str] | None:
    """(valor, contexto) recuperados de la captura local, o None.

    El valor no está en el aviso: se busca en la captura de la misma sesión y
    minuto, y se confirma comparando el identificador enmascarado.
    """
    try:
        when = datetime.fromisoformat(alert["ts"])
    except (KeyError, ValueError, TypeError):
        return None
    for path in _candidate_captures(originals or captures_originals_dir(), when):
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        payload = original.get("payload")
        if session_of(payload, when) != alert.get("session"):
            continue
        for f in detect(last_message_text(payload), scanner):
            if safe_id(f.value, f.category) == alert.get("id"):
                return f.value, f.context
    return None


def approve(value: str, category: str) -> str:
    """Añade el valor al vault y a ``config.json``. Devuelve el seudónimo."""
    from Klaus_proxy_local.scan import _get_prefix_for_category
    from Klaus_proxy_local.sensitive_data_scanner import (
        Confidence,
        SensitiveDataFinding,
        VaultIntegration,
    )

    finding = SensitiveDataFinding(
        value=value,
        category=category,
        detection_method="klaus-alerts",
        confidence=Confidence.MEDIUM,
        file_path=Path("."),
        line_number=0,
        context="",
        reason="aprobado en klaus-alerts (#189)",
    )
    return VaultIntegration().add_finding_to_vault(
        finding, _get_prefix_for_category(category)
    )


def mark_false_positive(value: str) -> None:
    from anthropic_payload_pseudonymize import add_to_config_list

    add_to_config_list("pseudo_pattern_ignore", [value])


def silence_category(category: str) -> None:
    from anthropic_payload_pseudonymize import add_to_config_list

    add_to_config_list("sentinel_silenced_categories", [category])


# --- Pintado (funciones puras, comprobables sin terminal) ----------------------


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(width - 1, 0)] + "…"


def render_sessions(sessions: list[SessionView], width: int) -> list[str]:
    if not sessions:
        return ["  Sin avisos pendientes. Esperando nuevos…"]
    lines = []
    for s in sessions:
        n = len(s.alerts)
        when = s.last_ts[11:16] if len(s.last_ts) >= 16 else "--:--"
        day = s.last_ts[:10]
        noun = "valor" if n == 1 else "valores"
        lines.append(
            _fit(f"  {s.label:<24} {day}  {n:>3} {noun}   último {when}", width)
        )
    return lines


def render_session(session: SessionView, width: int) -> list[str]:
    lines = []
    for a in session.alerts:
        ts = a.get("ts", "")[11:16] or "--:--"
        lines.append(
            _fit(
                f"  {a.get('category', '?'):<20} {a.get('id', '?'):<40} "
                f"{a.get('confidence', '?'):<7} {ts}",
                width,
            )
        )
    return lines


# --- Interfaz curses -------------------------------------------------------------

HELP_SESSIONS = "↑↓ mover · Enter abrir · q salir"
HELP_SESSION = (
    "a aprobar · f falso positivo · s ignorar sesión · v ver contexto · "
    "c silenciar categoría · Esc volver"
)


class _App:
    def __init__(self, screen, feed: AlertFeed, scanner: Any) -> None:
        self.scr = screen
        self.feed = feed
        self.scanner = scanner
        self.state = State()
        self.sink = AlertSink(feed.path)
        self.cursor = 0
        self.open: SessionView | None = None
        self.item = 0
        self.msg = ""
        self.context_view: str | None = None

    def _draw(self) -> None:
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        sessions = self.state.sessions()
        if self.open is not None:
            # refresca la sesión abierta con lo último leído
            self.open = next((s for s in sessions if s.key == self.open.key), None)
        if self.open is None:
            header = f" klaus-alerts · {len(sessions)} sesión(es) con avisos"
            body = render_sessions(sessions, w)
            self.cursor = min(self.cursor, max(len(sessions) - 1, 0))
            body = [
                ("▶" if i == self.cursor else " ") + line[1:] if line else line
                for i, line in enumerate(body)
            ]
            help_line = HELP_SESSIONS
        else:
            header = f" {self.open.label} · {self.open.last_ts[:10]}"
            body = render_session(self.open, w)
            self.item = min(self.item, max(len(body) - 1, 0))
            body = [
                ("▶" if i == self.item else " ") + line[1:]
                for i, line in enumerate(body)
            ]
            help_line = HELP_SESSION
        self._put(0, header, w, curses.A_BOLD)
        for i, line in enumerate(body[: max(h - 4, 0)]):
            self._put(2 + i, line, w)
        if self.context_view:
            self._put(h - 3, self.context_view, w)
        self._put(h - 2, self.msg, w)
        self._put(h - 1, help_line, w, curses.A_DIM)
        self.scr.refresh()

    def _put(self, y: int, text: str, w: int, attr: int = 0) -> None:
        try:
            self.scr.addnstr(y, 0, text, max(w - 1, 0), attr)
        except curses.error:
            pass

    def _confirm(self, question: str) -> bool:
        """Espera la respuesta sin el sondeo de 0,5 s (getkey falla con timeout)."""
        self.msg = f"{question} [s/N]"
        self._draw()
        self.scr.timeout(-1)
        try:
            key = self.scr.getch()
        finally:
            self.scr.timeout(POLL_MS)
        return key in (ord("s"), ord("S"), ord("y"), ord("Y"))

    def _current_alert(self) -> dict | None:
        if self.open is None or not self.open.alerts:
            return None
        return self.open.alerts[self.item]

    def _act(self, key: str) -> None:
        alert = self._current_alert()
        if key == "s" and alert:
            record_action(self.sink, "ignore_session", alert)
            self.msg = "Sesión ignorada en esta vista."
            self.item = 0
            return
        if alert is None:
            return
        if key == "a":
            got = recover_value(alert, self.scanner)
            if got is None:
                self.msg = "Valor no localizado en las capturas: no aprobado."
                return
            value, _ = got
            if not self._confirm(f"¿Aprobar {alert['id']}?"):
                self.msg = "Cancelado."
                return
            pseudo = approve(value, alert["category"])
            record_action(self.sink, "approve", alert)
            self.msg = (
                f"Aprobado {alert['id']} → {pseudo}. Aplica en la siguiente petición."
            )
        elif key == "f":
            got = recover_value(alert, self.scanner)
            if got is None:
                self.msg = "Valor no localizado en las capturas: no marcado."
                return
            mark_false_positive(got[0])
            record_action(self.sink, "false_positive", alert)
            self.msg = f"Marcado como falso positivo: {alert['id']}."
        elif key == "c":
            if not self._confirm(f"¿Silenciar la categoría {alert['category']}?"):
                self.msg = "Cancelado."
                return
            silence_category(alert["category"])
            record_action(self.sink, "silence_category", alert)
            self.msg = f"Categoría {alert['category']} silenciada."
        elif key == "v":
            got = recover_value(alert, self.scanner)
            if got is None:
                self.msg = "Valor no localizado en las capturas."
                return
            # En claro solo en pantalla: nada se escribe en disco.
            self.context_view = f"contexto: {got[1]}"

    def loop(self) -> None:
        self.scr.timeout(POLL_MS)
        self.state.feed(self.feed.poll())
        while True:
            self.state.feed(self.feed.poll())
            self._draw()
            key = self.scr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                return
            if self.open is None:
                sessions = self.state.sessions()
                if key == curses.KEY_UP:
                    self.cursor = max(self.cursor - 1, 0)
                elif key == curses.KEY_DOWN:
                    self.cursor = min(self.cursor + 1, max(len(sessions) - 1, 0))
                elif key in (curses.KEY_ENTER, 10, 13) and sessions:
                    self.open = sessions[self.cursor]
                    self.item = 0
                    self.msg = ""
            else:
                ch = chr(key) if 0 <= key < 256 else ""
                if key in (27, curses.KEY_BACKSPACE, 127):  # Esc / retroceso
                    self.open = None
                    self.context_view = None
                    self.msg = ""
                elif key == curses.KEY_UP:
                    self.item = max(self.item - 1, 0)
                elif key == curses.KEY_DOWN:
                    self.item = min(self.item + 1, max(len(self.open.alerts) - 1, 0))
                elif ch in "afscv" and ch:
                    if ch != "v":
                        self.context_view = None
                    self._act(ch)


def main(argv: list[str] | None = None) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "klaus-alerts necesita una terminal interactiva. "
            "Ejecútalo en su propia terminal.",
            file=sys.stderr,
        )
        return 2
    from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

    feed = AlertFeed(alerts_path())
    scanner = SensitiveDataScanner(enable_business=False)

    def run(screen) -> None:
        _App(screen, feed, scanner).loop()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
