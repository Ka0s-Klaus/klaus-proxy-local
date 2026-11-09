"""Instrumentación de trazas de ejecuciones con IA (docs/trazabilidad.md §7).

API mínima:

    ctx = start_trace("texto de entrada", channel="api")   # evento input_received (seq 1)
    record_event(ctx, "model_called", {...})               # encadenado al último evento
    end_trace(ctx, status="ok")

Reglas de la especificación que este módulo cumple:

- Un fichero JSONL por traza en ``<dir>/AAAA-MM-DD/<trace_id>.jsonl``, solo en adición.
- Si escribir un evento falla, la ejecución continúa y el fallo se registra en el
  log de la aplicación (§7). Nunca se lanza una excepción por un fallo de escritura.
- Antes de escribir, el ``payload`` pasa por el filtro de redacción (§6). Si el
  filtro falla, se escribe un evento ``error`` con ``recoverable: true`` y no se
  guarda el contenido original.
- Directorio ``0700`` y ficheros ``0600`` (§5).

El directorio se elige con ``trace_dir``, o con la variable de entorno
``KLAUS_TRAZAS_DIR``, o por defecto ``logs/trazas`` relativo al directorio actual
(el mismo que usa ``klaus-trazas``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from Klaus_proxy_local.trace_stats import EVENT_TYPES, SCHEMA_VERSION

log = logging.getLogger("klaus.trazas")

DEFAULT_TRACE_DIR = Path("logs") / "trazas"
ENV_TRACE_DIR = "KLAUS_TRAZAS_DIR"

# Actor por tipo de evento, según los ejemplos de §8.
DEFAULT_ACTOR: dict[str, str] = {
    "input_received": "user",
    "retrieval_performed": "system",
    "prompt_built": "system",
    "model_called": "model",
    "tool_called": "tool",
    "agent_step": "agent",
    "verification_run": "system",
    "human_review": "human_reviewer",
    "output_emitted": "system",
    "error": "system",
}


# ── Redacción (§6) ──────────────────────────────────────────────────────────


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),  # claves de API de Anthropic
    re.compile(r"AKIA[0-9A-Z]{16}"),  # claves de acceso AWS
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),  # tokens de GitHub
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),  # tokens de Slack
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
]
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_DNI_NIE = re.compile(r"\b(?:\d{8}|[XYZ]\d{7})[A-Za-z]\b")
_CARD = re.compile(r"\b(?:\d[ \-]?){13,19}\b")


def _mask(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"[REDACTED:{kind}:{digest}]"


def redact_text(text: str) -> str:
    """Sustituye datos sensibles por un marcador con hash. No guarda el original."""

    def card_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return _mask("tarjeta", m.group(0))
        return m.group(0)

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: _mask("secreto", m.group(0)), text)
    text = _EMAIL.sub(lambda m: _mask("correo", m.group(0)), text)
    text = _DNI_NIE.sub(lambda m: _mask("identificador", m.group(0)), text)
    text = _CARD.sub(card_sub, text)
    return text


def redact_payload(value: Any) -> Any:
    """Aplica ``redact_text`` a todas las cadenas de un payload anidado."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(v) for v in value]
    return value


# ── Contexto y escritura ────────────────────────────────────────────────────


@dataclass
class TraceContext:
    """Estado de una ejecución: ``trace_id``, ``seq`` actual y último ``event_id``."""

    trace_id: str
    path: Path
    seq: int = 0
    last_event_id: str | None = None
    status: str | None = None
    redact: Callable[[Any], Any] = field(default=redact_payload, repr=False)


def _trace_dir(trace_dir: Path | None) -> Path:
    if trace_dir is not None:
        return Path(trace_dir)
    env = os.environ.get(ENV_TRACE_DIR)
    return Path(env) if env else DEFAULT_TRACE_DIR


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _append(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write_event(
    ctx: TraceContext,
    event_type: str,
    payload: dict[str, Any],
    parent_event_id: str | None,
) -> str:
    """Construye, redacta y añade un evento. Devuelve su ``event_id``."""
    ctx.seq += 1
    event_id = str(uuid.uuid4())
    base = {
        "event_id": event_id,
        "trace_id": ctx.trace_id,
        "parent_event_id": parent_event_id,
        "seq": ctx.seq,
        "timestamp": _now(),
        "event_type": event_type,
        "schema_version": SCHEMA_VERSION,
        "actor": DEFAULT_ACTOR.get(event_type, "system"),
    }
    try:
        safe_payload = ctx.redact(payload)
        event = {**base, "payload": safe_payload}
    except Exception as exc:  # el filtro falla: no se guarda el contenido original
        log.error("filtro de redacción falló en traza %s: %s", ctx.trace_id, exc)
        event = {
            **base,
            "event_type": "error",
            "actor": "system",
            "payload": {
                "error_code": "REDACTION_FAILED",
                "error_message": "el filtro de redacción falló; evento sustituido",
                "recoverable": True,
            },
        }

    try:
        _append(ctx.path, json.dumps(event, ensure_ascii=False))
    except OSError as exc:
        # §7: el fallo no interrumpe la ejecución principal
        log.error("no se pudo escribir el evento en %s: %s", ctx.path, exc)
    return event_id


# ── API pública (§7) ────────────────────────────────────────────────────────


def start_trace(
    input_text: str,
    channel: str = "api",
    *,
    trace_dir: Path | None = None,
    redact: Callable[[Any], Any] | None = None,
) -> TraceContext:
    """Abre una traza y registra la entrada (``input_received``, seq 1, raíz).

    Solo se guarda el hash de la entrada, nunca su contenido (§3, principio 4).
    """
    trace_id = str(uuid.uuid4())
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    root = _trace_dir(trace_dir)
    directory = root / day
    try:
        # Raíz y carpeta del día, ambas privadas (§5)
        _ensure_private_dir(root)
        _ensure_private_dir(directory)
    except OSError as exc:
        log.error("no se pudo crear el directorio de trazas %s: %s", directory, exc)
    ctx = TraceContext(
        trace_id=trace_id,
        path=directory / f"{trace_id}.jsonl",
        redact=redact or redact_payload,
    )
    digest = "sha256:" + hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    ctx.last_event_id = _write_event(
        ctx,
        "input_received",
        {"content_hash": digest, "channel": channel},
        parent_event_id=None,
    )
    return ctx


def record_event(
    ctx: TraceContext,
    event_type: str,
    payload: dict[str, Any],
    parent_event_id: str | None = None,
) -> str:
    """Añade un evento a la traza. Devuelve su ``event_id``.

    ``parent_event_id`` por defecto es el último evento de la traza.
    Un ``event_type`` desconocido es un error de programación y sí lanza ValueError.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type desconocido: {event_type!r}")
    parent = parent_event_id if parent_event_id is not None else ctx.last_event_id
    event_id = _write_event(ctx, event_type, payload, parent)
    ctx.last_event_id = event_id
    return event_id


def end_trace(ctx: TraceContext, status: str) -> None:
    """Cierra la traza. El estado queda en el contexto y en el log.

    No añade evento: el enum de tipos de §4.2 es cerrado.
    """
    ctx.status = status
    log.info(
        "traza %s cerrada con estado %s (%d eventos)", ctx.trace_id, status, ctx.seq
    )
