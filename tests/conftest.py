"""Configuración de pytest para la suite del proxy de auditoría.

Añade ``src/`` al ``sys.path`` para que los tests importen los addons
(``import anthropic_payload_capture`` …) sin instalar el paquete.

Auto-genera ANTHROPIC_PSEUDO_SALT para que los tests corran sin configuración manual.
"""

import os
import secrets
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# Auto-generate ANTHROPIC_PSEUDO_SALT for tests if not already set
if "ANTHROPIC_PSEUDO_SALT" not in os.environ:
    os.environ["ANTHROPIC_PSEUDO_SALT"] = secrets.token_hex(16)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_config_json(tmp_path_factory, monkeypatch):
    """Ningún test escribe en el ~/.klaus-proxy/config.json real (#99).

    Las herramientas que protegen valores añaden reglas a config.json; aquí se
    redirige a uno temporal. Un test puede volver a parchear ``config_path``.
    """
    import anthropic_payload_capture as cap
    import anthropic_payload_pseudonymize as ps

    cfg = tmp_path_factory.mktemp("isolated-config") / "config.json"
    cfg.write_text('{"salt": "x"}', encoding="utf-8")
    monkeypatch.setattr(ps, "config_path", lambda: cfg)
    monkeypatch.setattr(cap, "config_path", lambda: cfg)
    return cfg
