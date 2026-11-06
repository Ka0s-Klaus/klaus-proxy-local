#!/usr/bin/env python3
"""Escaneo de inicio de sesión: protege todos los repos antes de arrancar claude-proxy.

Recorre todos los repos git de ``projects_dirs`` (config.json), ejecuta el
escáner de datos sensibles (MEDIUM+) en cada uno y añade al vault los hallazgos
nuevos que aún no estén protegidos. Totalmente automático, sin interacción.

La salida muestra progreso en tiempo real: una línea por repo que se actualiza
conforme avanzan los archivos y queda fija con el resultado al terminar.

Uso:
    klaus-startup-scan              # escanea y añade al vault
    klaus-startup-scan --dry-run    # muestra qué se añadiría sin cambios
    claude-proxy                    # ejecuta este escaneo automáticamente al arrancar
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from Klaus_proxy_local.scan import _get_prefix_for_category
from Klaus_proxy_local.scan_repos import find_repos, load_config, projects_dirs
from Klaus_proxy_local.sensitive_data_scanner import (
    Confidence,
    SensitiveDataScanner,
    VaultIntegration,
)

# Umbral fijo: MEDIUM cubre MEDIUM + HIGH + CRITICAL
_MIN_CONFIDENCE = Confidence.MEDIUM
_BAR_WIDTH = 18
_LABEL_WIDTH = 22


def _bar(current: int, total: int) -> str:
    if total == 0:
        return "░" * _BAR_WIDTH
    filled = min(_BAR_WIDTH, (current * _BAR_WIDTH) // total)
    return "█" * filled + "░" * (_BAR_WIDTH - filled)


def _repo_label(repo: Path, max_len: int = _LABEL_WIDTH) -> str:
    """Nombre corto del repo (último componente de ruta), recortado si hace falta."""
    name = repo.name
    if len(name) > max_len:
        return name[: max_len - 1] + "…"
    return name


def _clear_line() -> None:
    print("\r" + " " * 80 + "\r", end="", flush=True)


def scan_all(dry_run: bool = False) -> dict:
    """Escanea todos los repos de projects_dirs y añade hallazgos nuevos al vault.

    Args:
        dry_run: Si True, calcula qué se añadiría pero no escribe nada.

    Returns:
        Diccionario con claves: repos, files, new, already_in_vault, errors,
        elapsed, skipped (bool), message (str|None).
    """
    config = load_config()
    dirs = projects_dirs(config)

    if not dirs:
        return _skip(
            "Sin carpeta de proyectos que explorar "
            "(arranca desde un repo o define projects_dirs en config.json)"
        )

    # Descubrir repos
    repos: list[Path] = []
    for d in dirs:
        repos.extend(find_repos(d))

    if not repos:
        return _skip("No se encontraron repos git en projects_dirs")

    # Inicializar vault
    try:
        vault = VaultIntegration()
    except Exception as e:
        return _skip(f"Vault no disponible: {e}")

    scanner = SensitiveDataScanner(
        enable_contextual=True,   # nombres de variable + tipos de archivo
        enable_heuristic=False,   # demasiado ruido para auto-aprobar
        enable_business=True,     # nombres de cliente, dominios, cloud IDs
    )

    total_repos = len(repos)
    total_files = 0
    total_new = 0
    total_already = 0
    total_errors = 0
    idx_width = len(str(total_repos))

    t0 = time.time()

    for idx, repo in enumerate(repos, 1):
        label = _repo_label(repo)
        line_prefix = f"[{idx:{idx_width}}/{total_repos}] {label:<{_LABEL_WIDTH}}"

        # Callback de progreso: actualiza la línea en el sitio
        def _progress(current: int, total: int, _p: str = line_prefix) -> None:
            bar = _bar(current, total)
            pct = (current * 100 // total) if total else 0
            print(f"\r{_p} [{bar}] {pct:>3}%", end="", flush=True)

        try:
            result = scanner.scan_directory(repo, _progress)
            files = result.total_files_scanned
            total_files += files

            above = [f for f in result.findings if f.confidence <= _MIN_CONFIDENCE]

            repo_new = 0
            repo_already = 0
            repo_errors = 0

            for finding in above:
                existing = vault.check_already_in_vault(finding.value)
                if existing:
                    repo_already += 1
                    continue
                if dry_run:
                    repo_new += 1
                    continue
                try:
                    prefix = _get_prefix_for_category(finding.category)
                    vault.add_finding_to_vault(finding, prefix)
                    repo_new += 1
                except Exception:
                    repo_errors += 1

            total_new += repo_new
            total_already += repo_already
            total_errors += repo_errors

            # Línea final fija para este repo
            bar_done = "█" * _BAR_WIDTH
            status_parts: list[str] = []
            if repo_new:
                verb = "añadiría" if dry_run else "nuevos"
                status_parts.append(f"{repo_new} {verb}")
            if repo_already:
                status_parts.append(f"{repo_already} en vault")
            if repo_errors:
                status_parts.append(f"{repo_errors} ❌")
            if not status_parts:
                status_parts.append("sin hallazgos")

            status = " | ".join(status_parts)
            print(f"\r{line_prefix} [{bar_done}] 100% ({files} arch) → {status}")

        except Exception as e:
            _clear_line()
            print(f"{line_prefix} ❌ {type(e).__name__}: {e}")
            total_errors += 1

    return {
        "repos": total_repos,
        "files": total_files,
        "new": total_new,
        "already_in_vault": total_already,
        "errors": total_errors,
        "elapsed": time.time() - t0,
        "skipped": False,
        "message": None,
    }


def _skip(message: str) -> dict:
    return {
        "repos": 0,
        "files": 0,
        "new": 0,
        "already_in_vault": 0,
        "errors": 0,
        "elapsed": 0.0,
        "skipped": True,
        "message": message,
    }


def print_header() -> None:
    from Klaus_proxy_local import __version__

    print()
    print("─" * 60)
    print(f"🛡️  Klaus — Escaneo de inicio de sesión  v{__version__}")
    print("─" * 60)


def print_summary(result: dict, dry_run: bool = False) -> None:
    print()
    print("─" * 60)
    if dry_run:
        print("🔍 DRY-RUN — no se escribió nada")
    elif result["new"]:
        print("✅ Escaneo completado — vault actualizado")
    else:
        print("✅ Escaneo completado")
    print("─" * 60)
    print(f"  Repos escaneados:      {result['repos']}")
    print(f"  Archivos revisados:    {result['files']}")
    if result["new"]:
        verb = "se añadirían" if dry_run else "nuevas entradas"
        print(f"  Vault ({verb}): {result['new']}")
    if result["already_in_vault"]:
        print(f"  Ya protegidos:         {result['already_in_vault']}")
    if result["errors"]:
        print(f"  Errores:               {result['errors']}")
    print(f"  Tiempo:                {result['elapsed']:.1f}s")
    if result["new"] and not dry_run:
        print()
        print("  ⚠️  Reinicia claude-proxy para aplicar las reglas nuevas.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="klaus-startup-scan",
        description=(
            "Escanea todos los repos de projects_dirs (MEDIUM+) y añade al vault "
            "los hallazgos que aún no estén protegidos. Totalmente automático."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué se añadiría al vault sin escribir nada",
    )
    args = parser.parse_args(argv)

    print_header()

    result = scan_all(dry_run=args.dry_run)

    if result["skipped"]:
        print(f"\nⓘ {result['message']}")
        sys.exit(0)

    print_summary(result, dry_run=args.dry_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
