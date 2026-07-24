"""Configuración de pytest para la suite del proxy de auditoría.

Añade ``src/`` al ``sys.path`` para que los tests importen los addons
(``import anthropic_payload_capture`` …) sin instalar el paquete.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
