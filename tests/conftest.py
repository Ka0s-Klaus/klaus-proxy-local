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
