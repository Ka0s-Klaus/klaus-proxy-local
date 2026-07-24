#!/usr/bin/env python3
"""Limpieza y hardening de los artefactos en reposo que Claude Code persiste.

Contexto (privacidad / compliance): cuando un ``tool_result`` es grande, Claude
Code vuelca su contenido COMPLETO a disco, en claro, en dos ubicaciones:

    ~/.claude/projects/<proj>/<session>/tool-results/<id>.txt
    /private/tmp/claude-<uid>/<proj>/<session>/tasks/<id>.output

La auditoría de red (seudonimizador mitmproxy) demostró que hacia el gateway el
contenido sale SIEMPRE seudonimizado (0 fugas). El vector de exposición real es
por tanto **local data-at-rest**: esos ficheros quedan world-readable
(``-rw-r--r--``), en claro, y sobreviven al cierre de la sesión. Ver
``docs/MANIFIESTO_ficheros_embebidos.md`` §"Ficheros externalizados".

Este script mitiga ese riesgo con dos operaciones independientes:

    --harden   Restringe permisos: ficheros → 0600, directorios de artefactos
               (``tool-results`` / ``tasks``) → 0700. Solo owner.
    --clean    Borra artefactos regulares con antigüedad (mtime) mayor que
               ``--older-than-days`` (por defecto 7).

Seguridad de diseño:

- **Dry-run por defecto.** Nada se modifica ni se borra sin ``--apply``.
  El borrado es difícilmente reversible, así que se exige opt-in explícito.
- **Contención de rutas.** Solo se tocan entradas cuyo directorio padre sea
  ``tool-results`` o ``tasks`` bajo las raíces conocidas. Nunca fuera de ahí.
- **Symlinks protegidos.** Algunos ``*.output`` son symlinks a transcripts de
  subagentes (``subagents/agent-*.jsonl``). NUNCA se hace ``chmod`` a través de
  un symlink ni se sigue para borrar el destino. El propio enlace solo se borra
  si se pide ``--include-symlinks`` (por defecto NO).

Uso:
    # Inventario (no toca nada):
    python3 src/anthropic_artifacts_cleanup.py

    # Ver qué haría (dry-run) — hardening + limpieza de >14 días:
    python3 src/anthropic_artifacts_cleanup.py --harden --clean --older-than-days 14

    # Ejecutar de verdad:
    python3 src/anthropic_artifacts_cleanup.py --harden --clean --apply

El módulo separa la lógica pura (descubrimiento, clasificación, planificación)
de la ejecución y del CLI, de modo que sea unit-testable sin tocar disco real.
"""
from __future__ import annotations

import argparse
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# --- Configuración -----------------------------------------------------------

# Directorios cuyo contenido son artefactos de tool_result en reposo. La
# contención de rutas se ancla en estos nombres de directorio padre.
ARTIFACT_DIRNAMES = ("tool-results", "tasks")

# Permisos objetivo del hardening.
FILE_MODE = 0o600  # -rw-------  solo owner
DIR_MODE = 0o700  # drwx------  solo owner

DEFAULT_OLDER_THAN_DAYS = 7


def default_home() -> Path:
    return Path(os.path.expanduser("~"))


def default_tmp_base(uid: int | None = None) -> Path:
    """Base de artefactos temporales de Claude Code: ``/private/tmp/claude-<uid>``.

    En macOS ``/tmp`` es un symlink a ``/private/tmp``; se usa la forma canónica.
    """
    if uid is None:
        uid = os.getuid()
    return Path(f"/private/tmp/claude-{uid}")


# --- Modelo de artefacto -----------------------------------------------------

_KIND_FILE = "file"
_KIND_SYMLINK = "symlink"
_KIND_DIR = "dir"
_KIND_OTHER = "other"


@dataclass(frozen=True)
class Artifact:
    """Una entrada de disco candidata, ya clasificada (sin re-tocar disco)."""

    path: Path
    kind: str  # file | symlink | dir | other
    size: int
    mtime: float
    mode: int  # os.stat st_mode & 0o777 (para symlink: el del propio enlace)

    @classmethod
    def from_path(cls, path: Path) -> "Artifact":
        st = path.lstat()  # lstat: no sigue symlinks
        if stat.S_ISLNK(st.st_mode):
            kind = _KIND_SYMLINK
        elif stat.S_ISDIR(st.st_mode):
            kind = _KIND_DIR
        elif stat.S_ISREG(st.st_mode):
            kind = _KIND_FILE
        else:
            kind = _KIND_OTHER
        return cls(
            path=path,
            kind=kind,
            size=st.st_size,
            mtime=st.st_mtime,
            mode=stat.S_IMODE(st.st_mode),
        )


@dataclass(frozen=True)
class Action:
    """Una acción planificada sobre un artefacto."""

    op: str  # "chmod" | "delete"
    path: Path
    detail: str


# --- Contención de rutas -----------------------------------------------------


def is_artifact_entry(path: Path) -> bool:
    """True si ``path`` está DENTRO de un directorio de artefactos conocido.

    Defensa en profundidad: aunque el descubrimiento ya limita el barrido, toda
    acción se revalida contra esta condición antes de tocar el fichero.
    """
    return path.parent.name in ARTIFACT_DIRNAMES


def is_artifact_dir(path: Path) -> bool:
    """True si ``path`` es uno de los directorios de artefactos en sí."""
    return path.name in ARTIFACT_DIRNAMES


# --- Descubrimiento ----------------------------------------------------------


def discover_artifact_dirs(home: Path, tmp_base: Path) -> list[Path]:
    """Localiza todos los directorios de artefactos bajo las raíces conocidas."""
    dirs: list[Path] = []
    projects = home / ".claude" / "projects"
    if projects.is_dir():
        dirs.extend(sorted(projects.glob("*/*/tool-results")))
    if tmp_base.is_dir():
        dirs.extend(sorted(tmp_base.glob("*/*/tasks")))
    return [d for d in dirs if d.is_dir()]


def scan(home: Path, tmp_base: Path) -> list[Artifact]:
    """Devuelve el inventario de artefactos (los directorios y su contenido)."""
    artifacts: list[Artifact] = []
    for d in discover_artifact_dirs(home, tmp_base):
        artifacts.append(Artifact.from_path(d))
        for child in sorted(d.iterdir()):
            artifacts.append(Artifact.from_path(child))
    return artifacts


# --- Planificación (lógica pura, testable) -----------------------------------


def plan_harden(artifacts: Iterable[Artifact]) -> list[Action]:
    """Planifica los ``chmod`` necesarios para dejar todo en modo solo-owner.

    - Ficheros regulares dentro de un dir de artefactos → 0600.
    - Directorios de artefactos → 0700.
    - Symlinks: se OMITEN (no se hace chmod a través del enlace).
    - Solo se planifica si el modo actual difiere del objetivo (idempotente).
    """
    actions: list[Action] = []
    for a in artifacts:
        if a.kind == _KIND_DIR and is_artifact_dir(a.path):
            if a.mode != DIR_MODE:
                actions.append(
                    Action(
                        "chmod", a.path, f"{_fmt_mode(a.mode)} → {_fmt_mode(DIR_MODE)}"
                    )
                )
        elif a.kind == _KIND_FILE and is_artifact_entry(a.path):
            if a.mode != FILE_MODE:
                actions.append(
                    Action(
                        "chmod", a.path, f"{_fmt_mode(a.mode)} → {_fmt_mode(FILE_MODE)}"
                    )
                )
        # symlink / other → nunca se toca el modo
    return actions


def plan_clean(
    artifacts: Iterable[Artifact],
    *,
    older_than_days: float,
    now: float,
    include_symlinks: bool = False,
) -> list[Action]:
    """Planifica el borrado de artefactos regulares (y opcionalmente symlinks)
    cuya antigüedad (``now - mtime``) supere ``older_than_days``.

    Nunca borra directorios. Nunca sigue symlinks (solo elimina el enlace, y
    solo si ``include_symlinks``).
    """
    cutoff = older_than_days * 86400.0
    actions: list[Action] = []
    for a in artifacts:
        if not is_artifact_entry(a.path):
            continue
        if a.kind == _KIND_FILE:
            pass
        elif a.kind == _KIND_SYMLINK and include_symlinks:
            pass
        else:
            continue
        age_days = (now - a.mtime) / 86400.0
        if (now - a.mtime) >= cutoff:
            tag = "symlink" if a.kind == _KIND_SYMLINK else f"{a.size}B"
            actions.append(Action("delete", a.path, f"{tag}, {age_days:.1f}d"))
    return actions


# --- Ejecución ---------------------------------------------------------------


def apply_actions(actions: Iterable[Action], *, dry_run: bool) -> list[str]:
    """Ejecuta (o simula) las acciones. Revalida la contención de ruta.

    Devuelve las líneas de log de lo realizado/simulado.
    """
    log: list[str] = []
    for act in actions:
        # Defensa en profundidad: jamás actuar fuera de un dir de artefactos.
        safe = is_artifact_entry(act.path) or (
            act.op == "chmod" and is_artifact_dir(act.path)
        )
        if not safe:
            log.append(f"SKIP (fuera de ámbito) {act.path}")
            continue

        prefix = "[dry-run] " if dry_run else ""
        if act.op == "chmod":
            mode = DIR_MODE if is_artifact_dir(act.path) else FILE_MODE
            if not dry_run:
                os.chmod(act.path, mode)
            log.append(f"{prefix}chmod {_fmt_mode(mode)} {act.path}  ({act.detail})")
        elif act.op == "delete":
            if not dry_run:
                # unlink no sigue symlinks: borra el enlace, nunca el destino.
                act.path.unlink()
            log.append(f"{prefix}rm {act.path}  ({act.detail})")
    return log


# --- Utilidades --------------------------------------------------------------


def _fmt_mode(mode: int) -> str:
    return format(mode, "04o")


def summarize(artifacts: list[Artifact]) -> dict[str, int]:
    files = [a for a in artifacts if a.kind == _KIND_FILE and is_artifact_entry(a.path)]
    symlinks = [a for a in artifacts if a.kind == _KIND_SYMLINK]
    dirs = [a for a in artifacts if a.kind == _KIND_DIR and is_artifact_dir(a.path)]
    world_readable = [f for f in files if f.mode & 0o077]
    return {
        "dirs": len(dirs),
        "files": len(files),
        "symlinks": len(symlinks),
        "world_or_group_readable_files": len(world_readable),
        "total_bytes": sum(f.size for f in files),
    }


# --- CLI ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anthropic_artifacts_cleanup.py",
        description="Hardening y limpieza de artefactos en reposo de Claude Code.",
    )
    p.add_argument(
        "--harden",
        action="store_true",
        help="Restringe permisos a solo-owner (ficheros 0600, dirs 0700).",
    )
    p.add_argument(
        "--clean",
        action="store_true",
        help="Borra artefactos regulares más antiguos que --older-than-days.",
    )
    p.add_argument(
        "--older-than-days",
        type=float,
        default=DEFAULT_OLDER_THAN_DAYS,
        help=f"Umbral de antigüedad para --clean (default {DEFAULT_OLDER_THAN_DAYS}).",
    )
    p.add_argument(
        "--include-symlinks",
        action="store_true",
        help="Incluye symlinks (transcripts de subagentes) en --clean. "
        "Solo borra el enlace, nunca el destino.",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta los cambios. Sin este flag todo es dry-run.",
    )
    p.add_argument(
        "--home", type=Path, default=None, help="Override de $HOME (para pruebas)."
    )
    p.add_argument(
        "--tmp-base",
        type=Path,
        default=None,
        help="Override de /private/tmp/claude-<uid> (para pruebas).",
    )
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    home = args.home or default_home()
    tmp_base = args.tmp_base or default_tmp_base()

    artifacts = scan(home, tmp_base)
    s = summarize(artifacts)

    print("🗂️  Inventario de artefactos en reposo de Claude Code")
    print(f"   raíces: {home}/.claude/projects/*/*/tool-results")
    print(f"           {tmp_base}/*/*/tasks")
    print(
        f"   dirs={s['dirs']} ficheros={s['files']} symlinks={s['symlinks']} "
        f"({s['total_bytes']} bytes en claro)"
    )
    print(
        f"   ⚠️  ficheros legibles por grupo/otros: "
        f"{s['world_or_group_readable_files']}"
    )

    if not args.harden and not args.clean:
        print("\nℹ️  Solo inventario. Usa --harden y/o --clean (y --apply para actuar).")
        return 0

    actions: list[Action] = []
    if args.harden:
        actions += plan_harden(artifacts)
    if args.clean:
        actions += plan_clean(
            artifacts,
            older_than_days=args.older_than_days,
            now=time.time(),
            include_symlinks=args.include_symlinks,
        )

    if not actions:
        print(
            "\n✅ Nada que hacer: permisos ya restringidos y sin artefactos vencidos."
        )
        return 0

    mode_label = "APLICANDO" if args.apply else "DRY-RUN (usa --apply para ejecutar)"
    print(f"\n🔧 {len(actions)} acción(es) — {mode_label}:")
    for line in apply_actions(actions, dry_run=not args.apply):
        print(f"   {line}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
