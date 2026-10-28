#!/usr/bin/env python3
"""Addon guardián: fail-closed si el seudonimizador no ha visto la request (#71).

mitmproxy recarga los scripts ``-s`` cuando cambian en disco. Al recargar
quita el addon anterior y, si el nuevo no carga (error de sintaxis, fichero
borrado por un ``checkout``…), sigue funcionando SIN él: las requests salen
sin seudonimizar. Este addon se carga el ÚLTIMO y bloquea cualquier request
que ``AnthropicPseudonymizer.request`` no haya marcado con
``klaus_pseudo_seen``.

Es autocontenido a propósito: no importa el seudonimizador, que es justo lo
que puede estar roto.

Uso:
    mitmdump -s src/anthropic_payload_pseudonymize.py ... -s src/klaus_pseudo_guard.py
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

SEEN_KEY = "klaus_pseudo_seen"
VERSION_FILE = "VERSION.json"

logger = logging.getLogger("klaus.guard")


def blocked_body(method: str, url: str) -> bytes:
    return (
        "klaus-proxy: request BLOQUEADA (fail-closed).\n"
        "El seudonimizador no está cargado, así que nada sale hacia la API.\n"
        "Reinicia claude-proxy y revisa ~/.klaus-proxy/logs/proxy.log.\n"
        f"Request: {method} {url}\n"
    ).encode("utf-8")


def addons_version(directory: Path) -> str:
    """Commit de los addons según el VERSION.json del snapshot, si lo hay."""
    try:
        info = json.loads((directory / VERSION_FILE).read_text(encoding="utf-8"))
        return f"{info.get('commit', '?')} (snapshot {info.get('sha', '?')[:12]})"
    except (OSError, ValueError):
        return f"sin snapshot: {directory}"


class KlausPseudoGuard:
    """Bloquea las requests que el seudonimizador no ha procesado."""

    def load(self, loader: Any) -> None:
        logger.info(f"🧩 Addons: {addons_version(Path(__file__).resolve().parent)}")

    def request(self, flow: Any) -> None:
        if flow.metadata.get(SEEN_KEY) or flow.response is not None:
            return
        req = flow.request
        flow.metadata["anthropic_blocked"] = True
        logger.error(
            f"[klaus-guard] BLOQUEADA {req.method} {req.pretty_host}{req.path}: "
            f"el seudonimizador no está cargado"
        )
        try:
            from mitmproxy import http

            flow.response = http.Response.make(
                502,
                blocked_body(req.method, req.pretty_url),
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        except Exception:  # pragma: no cover - sin mitmproxy no hay flujo real
            flow.kill()


addons = [KlausPseudoGuard()]
