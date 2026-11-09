"""Aviso de versión al arrancar el proxy (issue #246).

Consulta la última release pública del repositorio. Nunca bloquea el arranque:
cualquier fallo se convierte en un estado ``unknown`` y el proxy continúa.

La petición solo lleva un User-Agent genérico. No envía datos del usuario,
cabeceras de identidad ni cookies.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

REPO = "Ka0s-Klaus/klaus-proxy-local"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT_S = 2.0
SKIP_ENV = "KLAUS_SKIP_UPDATE_CHECK"
USER_AGENT = "klaus-proxy-update-check"

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

FetchFn = Callable[[str, float], Optional[str]]


@dataclass(frozen=True)
class UpdateStatus:
    state: str  # "up_to_date" | "outdated" | "unknown" | "skipped"
    current: str
    latest: Optional[str] = None
    url: Optional[str] = None


def parse_version(text: str) -> Optional[tuple[int, int, int]]:
    """``v0.12.3`` o ``0.12.3`` → (0, 12, 3). ``None`` si no es una versión X.Y.Z."""
    match = _VERSION.match((text or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _fetch_latest(url: str, timeout: float) -> Optional[str]:
    """Devuelve el JSON de la última release como texto, o ``None`` si falla."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:  # red caída, timeout, 404, JSON… nunca interrumpe el arranque
        return None


def check_for_update(
    current: str,
    fetch: FetchFn = _fetch_latest,
    timeout: float = TIMEOUT_S,
    env: Optional[dict] = None,
) -> UpdateStatus:
    """Compara la versión instalada con la última release publicada. No lanza excepciones."""
    environ = os.environ if env is None else env
    if environ.get(SKIP_ENV, "").strip() in ("1", "true", "yes"):
        return UpdateStatus("skipped", current)

    try:
        raw = fetch(LATEST_URL, timeout)
        if not raw:
            return UpdateStatus("unknown", current)
        data = json.loads(raw)
        tag = data.get("tag_name") if isinstance(data, dict) else None
        url = data.get("html_url") if isinstance(data, dict) else None
        latest = parse_version(tag) if isinstance(tag, str) else None
        mine = parse_version(current)
        if latest is None or mine is None:
            return UpdateStatus("unknown", current)
        if mine < latest:
            return UpdateStatus(
                "outdated",
                current,
                latest=tag.lstrip("v"),
                url=url if isinstance(url, str) else None,
            )
        return UpdateStatus("up_to_date", current, latest=tag.lstrip("v"))
    except Exception:
        return UpdateStatus("unknown", current)


def describe(status: UpdateStatus) -> str:
    """Línea de texto para el arranque. Vacía si no hay nada que decir."""
    if status.state == "outdated":
        return (
            f"⚠️  Hay una versión más reciente del proxy: v{status.latest} "
            f"(tienes v{status.current}).\n"
            f"   Actualiza con: git pull && ./install.sh  ·  {status.url or ''}\n"
            "   El proxy arranca igual."
        )
    if status.state == "unknown":
        return "ⓘ  No se pudo comprobar si hay una versión más reciente. El proxy arranca igual."
    return ""
