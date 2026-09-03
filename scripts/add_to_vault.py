#!/usr/bin/env python3
"""
Automatiza la adición de datos sensibles al vault desde una carpeta.

Uso:
    python scripts/add_to_vault.py /path/to/project              # Auto-scan + auto-add CRITICAL
    python scripts/add_to_vault.py /path/to/project --high       # Incluir también HIGH
    python scripts/add_to_vault.py /path/to/project --all        # Incluir CRITICAL + HIGH + MEDIUM
    python scripts/add_to_vault.py /path/to/project --review     # Escanear pero pedir confirmación
    python scripts/add_to_vault.py /path/to/project --json       # Salida en JSON
    python scripts/add_to_vault.py /path/to/project --dry-run    # Ver qué se añadiría
"""

import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

# Importar desde el paquete
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from Klaus_proxy_local.sensitive_data_scanner import (
    Confidence,
    SensitiveDataScanner,
    VaultIntegration,
)


def parse_args(argv: Optional[list[str]] = None) -> dict:
    """Parse command-line arguments."""
    parser = ArgumentParser(
        prog="add-to-vault",
        description="Automatiza la adición de datos sensibles al vault desde una carpeta",
    )

    parser.add_argument(
        "path",
        type=str,
        help="Ruta de la carpeta del proyecto a escanear",
    )

    parser.add_argument(
        "--high",
        action="store_true",
        help="Incluir confianza HIGH además de CRITICAL",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Incluir CRITICAL + HIGH + MEDIUM (todas las confianzas)",
    )

    parser.add_argument(
        "--review",
        action="store_true",
        help="Pedir confirmación antes de añadir al vault",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se añadiría sin hacer cambios",
    )

    parser.add_argument(
        "--contextual",
        action="store_true",
        help="Habilitar detección contextual (variable names, tipos)",
    )

    parser.add_argument(
        "--heuristic",
        action="store_true",
        help="Habilitar detección heurística (análisis de entropía)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en JSON",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar detalles de cada hallazgo",
    )

    return vars(parser.parse_args(argv))


def get_min_confidence(args: dict) -> Confidence:
    """Determinar confianza mínima basada en argumentos."""
    if args.get("all"):
        return Confidence.MEDIUM
    elif args.get("high"):
        return Confidence.HIGH
    else:
        return Confidence.CRITICAL


def print_header() -> None:
    """Imprimir encabezado."""
    print("\n" + "═" * 70)
    print("🔐 Klaus Add to Vault — Automatiza adición de secretos")
    print("═" * 70 + "\n")


def print_progress(current: int, total: int) -> None:
    """Mostrar barra de progreso."""
    if total > 0:
        pct = (current * 100) // total
        bar_len = 40
        filled = (current * bar_len) // total
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r[{bar}] {pct}% ({current}/{total} archivos)", end="", flush=True)


def format_finding(finding, vault_integration: VaultIntegration) -> str:
    """Formatear un finding para mostrar."""
    # Verificar si ya está en vault
    existing = vault_integration.check_already_in_vault(finding.value)
    status = f"✓ ya en vault" if existing else "✦ nuevo"

    icon = {
        Confidence.CRITICAL: "🔴",
        Confidence.HIGH: "🟠",
        Confidence.MEDIUM: "🟡",
        Confidence.LOW: "🔵",
    }.get(finding.confidence, "⚪")

    return (
        f"\n  {icon} [{status}] {finding.confidence.name} — {finding.category}"
        f"\n     Archivo: {finding.file_path}:{finding.line_number}"
        f"\n     Tipo: {finding.detection_method}"
        f"\n     Razón: {finding.reason}"
    )


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    if not args.get("json"):
        print_header()

    # Validar ruta
    path = Path(args["path"]).resolve()
    if not path.exists():
        error_msg = f"❌ Error: Ruta no encontrada: {path}"
        if args.get("json"):
            print(json.dumps({"error": error_msg}))
        else:
            print(error_msg)
        return 1

    if not path.is_dir():
        error_msg = f"❌ Error: No es un directorio: {path}"
        if args.get("json"):
            print(json.dumps({"error": error_msg}))
        else:
            print(error_msg)
        return 1

    if not args.get("json"):
        print(f"📁 Escaneando: {path}")

    # Crear escáner
    scanner = SensitiveDataScanner(
        enable_contextual=args.get("contextual", False),
        enable_heuristic=args.get("heuristic", False),
    )

    # Escanear
    result = scanner.scan_directory(path, print_progress if not args.get("json") else None)
    if not args.get("json"):
        print()  # Nueva línea después de barra de progreso

    # Determinar confianza mínima
    min_confidence = get_min_confidence(args)

    # Filtrar por confianza
    above_threshold = [f for f in result.findings if f.confidence <= min_confidence]

    # Resumen
    if not args.get("json"):
        print("\n" + "─" * 70)
        print("📊 Resultados del escaneo")
        print("─" * 70)
        print(f"Archivos escaneados: {result.total_files_scanned}")
        print(f"Hallazgos encontrados: {len(result.findings)}")
        print(f"Por encima del umbral ({min_confidence.name}): {len(above_threshold)}")

    # Si no hay hallazgos, salir
    if not above_threshold:
        if not args.get("json"):
            print("\n✨ No hay hallazgos para procesar")
        else:
            print(
                json.dumps(
                    {
                        "success": True,
                        "files_scanned": result.total_files_scanned,
                        "findings_total": len(result.findings),
                        "findings_processed": 0,
                        "findings_added": 0,
                    }
                )
            )
        return 0

    # Inicializar vault
    try:
        vault_integration = VaultIntegration()
    except Exception as e:
        error_msg = f"❌ Error al inicializar vault: {e}"
        if args.get("json"):
            print(json.dumps({"error": error_msg}))
        else:
            print(error_msg)
        return 1

    # Mostrar hallazgos si verbose
    if args.get("verbose") and not args.get("json"):
        print("\n" + "─" * 70)
        print("📋 Hallazgos detectados")
        print("─" * 70)
        for finding in above_threshold:
            print(format_finding(finding, vault_integration))

    # Si dry-run, salir aquí
    if args.get("dry_run"):
        if not args.get("json"):
            print("\n" + "─" * 70)
            print("🔍 Modo DRY-RUN: No se hizo ningún cambio")
            print(f"Se habrían añadido {len(above_threshold)} hallazgos al vault")
            print("─" * 70)
        else:
            print(
                json.dumps(
                    {
                        "success": True,
                        "dry_run": True,
                        "files_scanned": result.total_files_scanned,
                        "findings_would_add": len(above_threshold),
                        "findings": [f.to_dict() for f in above_threshold],
                    }
                )
            )
        return 0

    # Revisar si se pide
    if args.get("review"):
        print("\n" + "─" * 70)
        print(f"🔎 Revisar {len(above_threshold)} hallazgo(s)")
        print("─" * 70)
        for finding in above_threshold:
            print(format_finding(finding, vault_integration))
        print()
        response = input("¿Añadir todos al vault? [s/N]: ").strip().upper()
        if response != "S":
            if not args.get("json"):
                print("⊘ Cancelado por el usuario")
            else:
                print(json.dumps({"success": False, "cancelled": True}))
            return 0

    # Añadir al vault
    if not args.get("json"):
        print("\n" + "─" * 70)
        print("✨ Añadiendo hallazgos al vault...")
        print("─" * 70)

    added_count = 0
    added_findings = []
    errors = []

    for idx, finding in enumerate(above_threshold, 1):
        try:
            # Verificar si ya está en vault
            existing = vault_integration.check_already_in_vault(finding.value)
            if existing:
                if not args.get("json"):
                    print(f"  {idx}. ⓘ Ya en vault: {existing}")
                continue

            # Determinar prefijo según categoría
            prefix = _get_prefix_for_category(finding.category)
            pseudo = vault_integration.add_finding_to_vault(finding, prefix)

            added_count += 1
            added_findings.append(
                {
                    "file": str(finding.file_path),
                    "line": finding.line_number,
                    "category": finding.category,
                    "confidence": finding.confidence.name,
                    "pseudo": pseudo,
                }
            )

            if not args.get("json"):
                print(f"  {idx}. ✓ Añadido: {pseudo}")

        except Exception as e:
            error_msg = f"Error al procesar hallazgo {idx}: {e}"
            errors.append(error_msg)
            if not args.get("json"):
                print(f"  {idx}. ❌ {error_msg}")

    # Resultado final
    if not args.get("json"):
        print("\n" + "═" * 70)
        print("✅ Proceso completado")
        print("═" * 70)
        print(f"Archivos escaneados: {result.total_files_scanned}")
        print(f"Hallazgos encontrados: {len(result.findings)}")
        print(f"Hallazgos procesados: {len(above_threshold)}")
        print(f"Añadidos al vault: {added_count}")
        if errors:
            print(f"Errores: {len(errors)}")
    else:
        print(
            json.dumps(
                {
                    "success": len(errors) == 0,
                    "files_scanned": result.total_files_scanned,
                    "findings_total": len(result.findings),
                    "findings_processed": len(above_threshold),
                    "findings_added": added_count,
                    "errors": errors if errors else None,
                    "added": added_findings,
                }
            )
        )

    return 0 if not errors else 1


def _get_prefix_for_category(category: str) -> str:
    """Determinar prefijo del vault según categoría."""
    if "api-key" in category or "token" in category:
        return "api-key"
    elif "password" in category or "secret" in category:
        return "secret"
    elif "connection" in category or "db" in category:
        return "db-connection"
    elif "key" in category:
        return "key"
    elif "host" in category or "ip" in category:
        return "infra"
    else:
        return "data"


if __name__ == "__main__":
    sys.exit(main())
