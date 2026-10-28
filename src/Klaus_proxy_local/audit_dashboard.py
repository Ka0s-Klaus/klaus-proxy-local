"""Entry point para el comando instalado 'klaus-audit-dashboard'.

Delega toda la lógica a scripts/generate_audit_dashboard.py para que el
script sea independiente y ejecutable directamente con:
    python scripts/generate_audit_dashboard.py

El módulo instalado simplemente localiza el script real y lo invoca.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    script = (
        Path(__file__).parent.parent.parent / "scripts" / "generate_audit_dashboard.py"
    )
    if not script.exists():
        # Fallback: si estamos instalados vía pip, ejecutar inline
        _run_inline()
        return

    import runpy

    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


def _run_inline() -> None:
    """Fallback cuando el script no está presente (instalación pip pura)."""
    try:
        # Importación dinámica para evitar dependencia circular
        # Buscar el script en el directorio del paquete o en PATH
        for candidate in [
            Path.home()
            / ".local"
            / "share"
            / "klaus"
            / "scripts"
            / "generate_audit_dashboard.py",
        ]:
            if candidate.exists():
                import runpy

                sys.argv[0] = str(candidate)
                runpy.run_path(str(candidate), run_name="__main__")
                return
        print("❌ No se encontró generate_audit_dashboard.py")
        print("   Clona el repositorio y ejecuta:")
        print("   python scripts/generate_audit_dashboard.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
