#!/usr/bin/env python3
"""
Quita del vault los valores que los pseudo_patterns ya no seudonimizan (#92).

Marcadores y puntuación (``…``, ``|``, ``{user}``), valores de un carácter,
nombres genéricos de usuario y los de ``pseudo_pattern_ignore`` de config.json
que entraron al vault antes de la regla que los ignora.

Ejecutar con claude-proxy PARADO: el proxy guarda su copia en memoria del
vault y volvería a escribir las entradas quitadas.

Uso:
    python3 scripts/prune_vault.py --dry-run   # Ver qué se quitaría
    python3 scripts/prune_vault.py             # Quitar (con copia de seguridad)
"""

import os
import shutil
import socket
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from anthropic_payload_pseudonymize import (  # noqa: E402
    Vault,
    build_rules,
    prune_vault,
    vault_path,
)

PROXY_ADDR = (".".join(("127", "0", "0", "1")), 8899)


def proxy_running() -> bool:
    try:
        with socket.create_connection(PROXY_ADDR, timeout=0.5):
            return True
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(
        prog="prune-vault",
        description="Quita del vault los valores que los pseudo_patterns ignoran (#92)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo lista")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continuar aunque claude-proxy esté escuchando",
    )
    args = parser.parse_args(argv)

    path = vault_path()
    if not path.exists():
        print(f"❌ No existe el vault: {path}")
        return 1
    vault = Vault.load(path)
    removed = prune_vault(vault, build_rules())
    if not removed:
        print("✅ Nada que quitar.")
        return 0

    print(f"{len(removed)} entrada(s) que los patrones ya no seudonimizan:")
    for value in removed:
        print(f"  {value!r}")
    if args.dry_run:
        return 0
    if proxy_running() and not args.force:
        print(
            "❌ claude-proxy está escuchando en el puerto 8899: volvería a escribir "
            "estas entradas. Páralo y vuelve a ejecutar (o usa --force)."
        )
        return 2

    backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)
    vault.save(path)
    print(f"✅ Quitadas {len(removed)}. Copia de seguridad: {backup.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
