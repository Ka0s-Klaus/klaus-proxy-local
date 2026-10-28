#!/usr/bin/env python3
"""Addon de mitmproxy que guarda los logs del proxy en disco (#55).

``mitmdump`` hereda la terminal de ``claude-proxy`` y no deja rastro en disco:
al cerrar la terminal se pierden los errores TLS, los avisos del pseudonimizador
y el registro de peticiones. Este addon escribe, en paralelo a la terminal:

- Todos los registros de ``logging`` de mitmproxy y de los addons (``ctx.log``).
- Una línea por flujo (método, host+ruta, status, bytes, duración) y los errores
  de conexión. Las líneas de flujo de ``mitmdump`` van directas a stdout y no
  pasan por ``logging``, así que se reconstruyen aquí.

Uso:
    mitmdump -s src/klaus_file_log.py ...

Fichero: ``~/.klaus-proxy/logs/proxy.log`` (``KLAUS_LOG_DIR`` para cambiar el
directorio), rotado a 5 MB × 5 ficheros. Sin secuencias ANSI ni cuerpos ni
query strings: solo metadatos.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Any

LOG_FILENAME = "proxy.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def log_dir() -> Path:
    """Directorio de logs: ``KLAUS_LOG_DIR`` o ``~/.klaus-proxy/logs``."""
    env = os.environ.get("KLAUS_LOG_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".klaus-proxy" / "logs"


def log_file() -> Path:
    return log_dir() / LOG_FILENAME


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class PlainFormatter(logging.Formatter):
    """Formatter que elimina los colores ANSI que añaden los addons."""

    def format(self, record: logging.LogRecord) -> str:
        return strip_ansi(super().format(record))


def build_handler(path: Path) -> logging.Handler:
    """Crea el handler rotativo, con directorio 0700 y fichero 0600.

    Los logs incluyen hosts y rutas de las peticiones: no deben ser legibles
    por otros usuarios del equipo.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    os.chmod(path, 0o600)
    handler.setFormatter(PlainFormatter(_FORMAT))
    handler.setLevel(logging.INFO)
    return handler


def format_flow(
    method: str,
    host: str,
    path: str,
    status: int | None,
    size: int | None,
    duration: float | None,
) -> str:
    """Línea de resumen de un flujo, sin query string."""
    route = path.split("?", 1)[0]
    status_s = str(status) if status is not None else "-"
    size_s = f"{size}B" if size is not None else "-"
    dur_s = f"{duration * 1000:.0f}ms" if duration is not None else "-"
    return f"{method} {host}{route} → {status_s} {size_s} {dur_s}"


class KlausFileLog:
    """Addon de mitmproxy: duplica los logs del proxy en un fichero rotativo."""

    def __init__(self) -> None:
        self.handler: logging.Handler | None = None
        self.flow_logger = logging.getLogger("klaus.flow")

    def load(self, loader: Any) -> None:
        path = log_file()
        try:
            self.handler = build_handler(path)
        except OSError as e:
            logging.getLogger("klaus.filelog").warning(
                f"No se pudo abrir el log en disco ({path}): {e}"
            )
            return
        logging.getLogger().addHandler(self.handler)
        logging.getLogger("klaus.filelog").info(f"📝 Log en disco: {path}")

    def done(self) -> None:
        if self.handler:
            logging.getLogger("klaus.filelog").info("Proxy detenido")
            logging.getLogger().removeHandler(self.handler)
            self.handler.close()
            self.handler = None

    def response(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        req, resp = flow.request, flow.response
        duration = None
        if resp.timestamp_end and req.timestamp_start:
            duration = resp.timestamp_end - req.timestamp_start
        self.flow_logger.info(
            format_flow(
                req.method,
                req.pretty_host,
                req.path,
                resp.status_code,
                len(resp.raw_content or b""),
                duration,
            )
        )

    def error(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        req = flow.request
        self.flow_logger.error(
            f"{format_flow(req.method, req.pretty_host, req.path, None, None, None)}"
            f" ✖ {flow.error.msg}"
        )


addons = [KlausFileLog()]
