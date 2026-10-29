#!/usr/bin/env python3
"""Retención de capturas (#132).

Las capturas ``original/`` + ``sent/`` crecen sin límite (cada petición lleva la
conversación entera) y ``original/`` guarda datos reales en claro. Los pares más
antiguos que ``capture_retention_days`` (``config.json``, por defecto 30; ``0`` =
sin límite) se borran al arrancar ``claude-proxy`` o con ``klaus-prune-captures``.

Solo se tocan ``original/`` y ``sent/``: el vault y cualquier otro subdirectorio
(``archive/``…) se conservan. El resultado del último borrado queda en
``captures/.retention.json`` para que lo muestre el dashboard de auditoría.

Uso:
    klaus-prune-captures --dry-run      # qué se borraría
    klaus-prune-captures                # borrar según config.json
    klaus-prune-captures --days 7       # otra retención, solo esta vez
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_RETENTION_DAYS = 30
STATE_FILE = ".retention.json"
SUBDIRS = ("original", "sent")

# Nombre de las evidencias: YYYYMMDD_HHMMSS_anthropic_payload[...].json
_NAME_RE = re.compile(r"^(\d{8})_(\d{6})_")


def config_path() -> Path:
    return Path.home() / ".klaus-proxy" / "config.json"


def load_config(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Sin config.json legible se aplican los valores por defecto
        return {}
    return data if isinstance(data, dict) else {}


def captures_dir(config: dict) -> Path:
    """Mismo orden que ``claude-proxy``: entorno, ``capture_dir``, por defecto."""
    env = os.environ.get("ANTHROPIC_CAPTURE_DIR")
    if env:
        return Path(env).expanduser()
    if config.get("capture_dir"):
        return Path(str(config["capture_dir"])).expanduser()
    return Path.home() / ".klaus-proxy" / "captures"


def retention_days(config: dict) -> int:
    """Días de retención; ``0`` = sin límite. Un valor inválido usa el defecto."""
    value = config.get("capture_retention_days", DEFAULT_RETENTION_DAYS)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return DEFAULT_RETENTION_DAYS
    return value


def capture_time(name: str) -> datetime | None:
    m = _NAME_RE.match(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def prune_captures(
    base: Path, days: int, *, now: datetime | None = None, dry_run: bool = False
) -> dict:
    """Borra los pares más antiguos que ``days`` y devuelve el resumen.

    Un par es el mismo nombre en ``original/`` y ``sent/``; se borran los dos.
    Los ficheros cuyo nombre no lleva fecha no se tocan nunca.
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=days) if days else None
    removed: set[str] = set()
    freed = 0
    oldest: datetime | None = None
    for sub in SUBDIRS:
        d = base / sub
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            ts = capture_time(f.name)
            if ts is None:
                continue
            if cutoff and ts < cutoff:
                removed.add(f.name)
                freed += f.stat().st_size
                if not dry_run:
                    f.unlink()
            elif oldest is None or ts < oldest:
                oldest = ts
    summary = {
        "last_run": now.isoformat(timespec="seconds"),
        "retention_days": days,
        "removed_pairs": len(removed),
        "freed_bytes": freed,
        "oldest_kept": oldest.isoformat(timespec="seconds") if oldest else None,
    }
    if not dry_run:
        write_state(base, summary)
    return summary


def write_state(base: Path, summary: dict) -> None:
    path = base / STATE_FILE
    try:
        base.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        # El estado solo alimenta el aviso del dashboard; el borrado ya se hizo
        return


def read_state(base: Path) -> dict:
    try:
        data = json.loads((base / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def describe(summary: dict, dry_run: bool = False) -> str:
    """Una línea para la terminal y el log."""
    days = summary["retention_days"]
    if not days:
        return "🧹 Retención de capturas: sin límite (capture_retention_days = 0)"
    verb = "se borrarían" if dry_run else "borrados"
    return (
        f"🧹 Retención de capturas: {days} días · {verb} "
        f"{summary['removed_pairs']} pares ({human_size(summary['freed_bytes'])})"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="klaus-prune-captures",
        description=(
            "Borra las capturas original/ + sent/ más antiguas que "
            "capture_retention_days (config.json; por defecto 30, 0 = sin límite)."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Muestra qué se borraría, sin borrar"
    )
    parser.add_argument(
        "--days", type=int, help="Retención para esta ejecución (0 = sin límite)"
    )
    args = parser.parse_args(argv)
    if args.days is not None and args.days < 0:
        parser.error("--days no puede ser negativo")

    config = load_config()
    days = args.days if args.days is not None else retention_days(config)
    base = captures_dir(config)
    summary = prune_captures(base, days, dry_run=args.dry_run)
    print(describe(summary, dry_run=args.dry_run))
    if summary["oldest_kept"]:
        print(f"   Captura más antigua conservada: {summary['oldest_kept']}")
    print(f"   Directorio: {base}")
    sys.exit(0)


if __name__ == "__main__":
    main()
