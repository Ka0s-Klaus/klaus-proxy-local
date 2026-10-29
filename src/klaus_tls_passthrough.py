#!/usr/bin/env python3
"""Addon de mitmproxy: solo descifra el tráfico hacia la API del LLM (#105).

Con el hook de ``klaus-setup`` todo el HTTPS de la terminal (pip, git, brew,
gh…) pasa por el proxy. Si mitmproxy lo descifrara todo, cada herramienta que
no confíe en su CA daría errores de certificado. Este addon decide en el
ClientHello:

- Hosts auditados: ``api.anthropic.com``, ``hosts`` y ``capture_only_hosts``
  de ``config.json`` y el host de ``ANTHROPIC_BASE_URL``. Se descifran para
  seudonimizarlos (salvo los de solo captura, #125) y capturarlos. Solo se
  descifra lo que se audita: nada sale descifrado sin pasar por la captura.
- Resto: túnel TLS sin descifrar. El cliente ve el certificado real del
  servidor (sin errores) y queda una línea ``TÚNEL host:puerto`` en el log.

Si este addon no carga, mitmproxy lo descifra todo: falla hacia el lado
seguro (más errores de certificado, nunca tráfico de la API sin seudonimizar).
``KLAUS_INTERCEPT_ALL=1`` o ``"intercept_all": true`` en ``config.json``
restauran el descifrado de todo el tráfico.

Uso:
    mitmdump -s src/klaus_tls_passthrough.py ...
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Siempre descifrado, aunque config.json defina otros hosts
ALWAYS_INTERCEPT = ("api.anthropic.com",)

logger = logging.getLogger("klaus.flow")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def config_path() -> Path:
    return Path.home() / ".klaus-proxy" / "config.json"


def claude_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def intercept_all() -> bool:
    """True si hay que descifrar todo (comportamiento anterior a #105)."""
    if _env_flag("KLAUS_INTERCEPT_ALL"):
        return True
    return _read_json(config_path()).get("intercept_all") is True


def _base_url_hosts() -> list[str]:
    """Host de ``ANTHROPIC_BASE_URL`` (entorno o settings.json de Claude Code)."""
    urls = [os.environ.get("ANTHROPIC_BASE_URL", "")]
    env = _read_json(claude_settings_path()).get("env")
    if isinstance(env, dict):
        urls.append(str(env.get("ANTHROPIC_BASE_URL", "")))
    return [urlparse(u).hostname or "" for u in urls if u]


def intercept_hosts() -> tuple[str, ...]:
    """Hosts (y sus subdominios) que se descifran.

    Mismas fuentes que el seudonimizador y la captura (``ANTHROPIC_PSEUDO_HOSTS``
    / ``ANTHROPIC_CAPTURE_HOSTS``, ``hosts`` y ``capture_only_hosts`` de
    config.json), más ``api.anthropic.com`` y el gateway de ``ANTHROPIC_BASE_URL``.
    """
    hosts = list(ALWAYS_INTERCEPT)
    for var in ("ANTHROPIC_PSEUDO_HOSTS", "ANTHROPIC_CAPTURE_HOSTS"):
        hosts += os.environ.get(var, "").split(",")
    cfg = _read_json(config_path())
    for key in ("hosts", "capture_only_hosts"):
        cfg_hosts = cfg.get(key, [])
        if isinstance(cfg_hosts, list):
            hosts += [str(h) for h in cfg_hosts]
    hosts += _base_url_hosts()
    return tuple(dict.fromkeys(h.strip().lower() for h in hosts if h.strip()))


def should_intercept(host: str, hosts: tuple[str, ...]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in hosts)


class KlausTlsPassthrough:
    """Deja en túnel el TLS que no va a la API del LLM."""

    def __init__(self) -> None:
        self.all = False
        self.hosts: tuple[str, ...] = ALWAYS_INTERCEPT

    def load(self, loader: Any) -> None:
        self.all = intercept_all()
        self.hosts = intercept_hosts()
        if self.all:
            logger.info("🔓 Descifrando todo el tráfico (intercept_all)")
        else:
            logger.info(
                f"🔓 Se descifra solo: {', '.join(self.hosts)}; el resto, en túnel"
            )

    def tls_clienthello(self, data: Any) -> None:
        if self.all:
            return
        client, server = data.context.client, data.context.server
        host = client.sni or (server.address[0] if server.address else "")
        if should_intercept(host, self.hosts):
            return
        data.ignore_connection = True
        port = server.address[1] if server.address else "?"
        logger.info(f"TÚNEL {host}:{port} (sin descifrar)")


addons = [KlausTlsPassthrough()]
