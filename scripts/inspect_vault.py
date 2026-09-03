#!/usr/bin/env python3
"""
Herramienta para inspeccionar anonimizaciones (vault) de Klaus Proxy Local

Uso:
    python scripts/inspect_vault.py [opciones]

Ejemplos:
    # Ver todas las anonimizaciones
    python scripts/inspect_vault.py --all

    # Buscar una anonimización específica
    python scripts/inspect_vault.py --search "user@example.com"

    # Ver solo mapeo real → pseudo
    python scripts/inspect_vault.py --forward

    # Ver solo mapeo pseudo → real
    python scripts/inspect_vault.py --reverse

    # Listar capturas originales
    python scripts/inspect_vault.py --captures original
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any


def get_vault_path() -> Path:
    """Obtiene la ruta del vault."""
    home = Path.home()
    vault_path = home / ".klaus-proxy" / ".." / "captures" / ".pseudonym_vault.json"
    return vault_path.resolve()


def get_captures_path(direction: str = "original") -> Path:
    """Obtiene la ruta de las capturas."""
    home = Path.home()
    captures_path = home / ".klaus-proxy" / ".." / "captures" / direction
    return captures_path.resolve()


def load_vault() -> Dict[str, Any]:
    """Carga el vault."""
    vault_path = get_vault_path()

    if not vault_path.exists():
        print(f"❌ Vault no encontrado en: {vault_path}")
        print("   Asegúrate de haber ejecutado claude-proxy antes")
        return {}

    with open(vault_path, 'r') as f:
        return json.load(f)


def show_all_mappings(vault: Dict[str, Any]):
    """Muestra todos los mapeos."""
    print("\n📋 TODAS LAS ANONIMIZACIONES")
    print("════════════════════════════════════════════════════════════════\n")

    if not vault:
        print("❌ Vault vacío")
        return

    real_to_pseudo = vault.get('real_to_pseudo', {})

    print(f"Total de mapeos: {len(real_to_pseudo)}\n")

    for i, (real, pseudo) in enumerate(real_to_pseudo.items(), 1):
        print(f"{i}. Valor real:")
        print(f"   └─ {real}")
        print(f"   Pseudonimizado:")
        print(f"   └─ {pseudo}\n")


def show_forward_mapping(vault: Dict[str, Any]):
    """Muestra mapeo real → pseudo."""
    print("\n📋 MAPEO REAL → PSEUDONIMIZADO")
    print("════════════════════════════════════════════════════════════════\n")

    real_to_pseudo = vault.get('real_to_pseudo', {})

    if not real_to_pseudo:
        print("❌ No hay mapeos")
        return

    print(json.dumps(real_to_pseudo, indent=2, ensure_ascii=False))


def show_reverse_mapping(vault: Dict[str, Any]):
    """Muestra mapeo pseudo → real."""
    print("\n📋 MAPEO PSEUDONIMIZADO → REAL")
    print("════════════════════════════════════════════════════════════════\n")

    pseudo_to_real = vault.get('pseudo_to_real', {})

    if not pseudo_to_real:
        print("❌ No hay mapeos")
        return

    print(json.dumps(pseudo_to_real, indent=2, ensure_ascii=False))


def search_mapping(vault: Dict[str, Any], term: str):
    """Busca una anonimización específica."""
    print(f"\n🔍 BUSCANDO: '{term}'")
    print("════════════════════════════════════════════════════════════════\n")

    real_to_pseudo = vault.get('real_to_pseudo', {})
    pseudo_to_real = vault.get('pseudo_to_real', {})

    found = False

    # Buscar en reales
    for real, pseudo in real_to_pseudo.items():
        if term.lower() in real.lower():
            print(f"✓ Encontrado (como valor REAL):")
            print(f"  Real: {real}")
            print(f"  Pseudo: {pseudo}\n")
            found = True

    # Buscar en pseudonimizados
    for pseudo, real in pseudo_to_real.items():
        if term.lower() in pseudo.lower():
            print(f"✓ Encontrado (como valor PSEUDO):")
            print(f"  Pseudo: {pseudo}")
            print(f"  Real: {real}\n")
            found = True

    if not found:
        print(f"❌ No se encontró '{term}' en el vault")


def list_captures(direction: str = "original"):
    """Lista archivos de capturas."""
    captures_path = get_captures_path(direction)

    print(f"\n📁 CAPTURAS {direction.upper()}")
    print("════════════════════════════════════════════════════════════════\n")

    if not captures_path.exists():
        print(f"❌ Directorio no encontrado: {captures_path}")
        return

    files = list(captures_path.glob("*.json"))

    if not files:
        print("❌ No hay archivos de captura")
        return

    print(f"Total: {len(files)} archivos\n")

    for i, file in enumerate(sorted(files), 1):
        size = file.stat().st_size
        size_kb = size / 1024
        print(f"{i}. {file.name} ({size_kb:.1f} KB)")


def show_stats(vault: Dict[str, Any]):
    """Muestra estadísticas del vault."""
    print("\n📊 ESTADÍSTICAS DEL VAULT")
    print("════════════════════════════════════════════════════════════════\n")

    real_to_pseudo = vault.get('real_to_pseudo', {})

    total = len(real_to_pseudo)

    # Categorizar por tipo
    categories = {}
    for real in real_to_pseudo.keys():
        if real.startswith('/'):
            cat = 'Rutas'
        elif '@' in real:
            cat = 'Emails'
        elif real.startswith('sk-'):
            cat = 'API Keys'
        else:
            cat = 'Otros'

        categories[cat] = categories.get(cat, 0) + 1

    print(f"Total de anonimizaciones: {total}\n")
    print("Por categoría:")
    for cat, count in sorted(categories.items()):
        pct = (count / total * 100) if total > 0 else 0
        print(f"  • {cat}: {count} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Inspecciona anonimizaciones (vault) de Klaus Proxy Local"
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Mostrar todas las anonimizaciones'
    )
    parser.add_argument(
        '--forward',
        action='store_true',
        help='Mostrar mapeo real → pseudo'
    )
    parser.add_argument(
        '--reverse',
        action='store_true',
        help='Mostrar mapeo pseudo → real'
    )
    parser.add_argument(
        '--search',
        type=str,
        help='Buscar una anonimización específica'
    )
    parser.add_argument(
        '--captures',
        choices=['original', 'sent'],
        help='Listar archivos de capturas'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Mostrar estadísticas del vault'
    )

    args = parser.parse_args()

    vault = load_vault()

    if not vault:
        return

    if args.all:
        show_all_mappings(vault)
    elif args.forward:
        show_forward_mapping(vault)
    elif args.reverse:
        show_reverse_mapping(vault)
    elif args.search:
        search_mapping(vault, args.search)
    elif args.captures:
        list_captures(args.captures)
    elif args.stats:
        show_stats(vault)
    else:
        # Por defecto, mostrar estadísticas
        show_stats(vault)
        print()
        print("💡 Usa --help para ver más opciones")


if __name__ == '__main__':
    main()
