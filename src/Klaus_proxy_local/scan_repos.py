#!/usr/bin/env python3
"""Protege el org/repo de todos los repos de la carpeta de proyectos (#134).

``claude-proxy`` solo leía el remote del repo desde el que arranca (#61) y el
pseudonimizador aprende el resto por petición, solo en los modos ``auto`` y
``plan`` (#68). Un repo recién clonado que se lista o se revisa desde otro repo
salía en claro. Esta exploración recorre ``projects_dirs`` (hasta 3 niveles),
lee todos los remotes de cada repo git y añade sus tokens a
``pseudo_word_literals``; la identidad git propia de un repo (``user.email`` /
``user.name`` locales) va a ``pseudo_literals``.

La salida solo da recuentos: puede acabar en el contexto del modelo.

Uso:
    klaus-scan-repos --dry-run      # qué se protegería
    klaus-scan-repos                # añadirlo a config.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from Klaus_proxy_local.setup import _pseudonymizer, config_file

MAX_DEPTH = 3
# Directorios que nunca contienen repos propios y pueden ser enormes
_SKIP_DIRS = {"node_modules", "venv", "__pycache__", "site-packages"}
# Sufijo de projects_root_pattern(): de él se recupera la carpeta de proyectos
_ROOT_PATTERN_SUFFIX = r"/([^/\s\"'`\\:;,()\[\]<>]+)"


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (out.stdout or "").strip()


def load_config(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or config_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _pattern_roots(config: dict) -> list[Path]:
    """Carpetas de proyectos ya registradas por ``claude-proxy`` (#42)."""
    roots = []
    for entry in config.get("pseudo_patterns") or []:
        if not isinstance(entry, dict) or entry.get("replacement_prefix") != "dir":
            continue
        pattern = str(entry.get("pattern", ""))
        if pattern.endswith(_ROOT_PATTERN_SUFFIX):
            escaped = pattern[: -len(_ROOT_PATTERN_SUFFIX)]
            roots.append(Path(re.sub(r"\\(.)", r"\1", escaped)))
    return roots


def projects_dirs(config: dict, cwd: Path | None = None) -> list[Path]:
    """``projects_dirs`` de config.json; si no hay, las carpetas de proyectos
    registradas y la del repo actual. Nunca el home ni ``/``: se exploraría
    todo el disco."""
    configured = config.get("projects_dirs")
    if isinstance(configured, list) and configured:
        candidates = [Path(str(d)).expanduser() for d in configured if d]
    else:
        candidates = _pattern_roots(config)
        top = _git(cwd or Path.cwd(), "rev-parse", "--show-toplevel")
        if top:
            candidates.append(Path(top).parent)
    dirs: list[Path] = []
    for d in candidates:
        if d in (Path.home(), Path(d.anchor)) or d in dirs or not d.is_dir():
            continue
        dirs.append(d)
    return dirs


def find_repos(root: Path, depth: int = MAX_DEPTH) -> list[Path]:
    """Repos git bajo ``root`` hasta ``depth`` niveles; no entra en un repo."""
    repos: list[Path] = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return repos
    for child in children:
        if child.name.startswith(".") or child.name in _SKIP_DIRS:
            continue
        try:
            if not child.is_dir() or child.is_symlink():
                continue
            if (child / ".git").exists():
                repos.append(child)
                continue
        except OSError:
            continue
        if depth > 1:
            repos.extend(find_repos(child, depth - 1))
    return repos


def _global_identity() -> set[str]:
    values = set()
    for key in ("user.name", "user.email"):
        try:
            out = subprocess.run(
                ["git", "config", "--global", "--get", key],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if out.stdout.strip():
            values.add(out.stdout.strip())
    return values


def repo_details(dirs: list[Path]) -> list[dict]:
    """Un dict por repo: carpeta, remotes (``org/repo``), tokens e identidad
    git local distinta de la global. Lo usa también el dashboard (#136)."""
    ps = _pseudonymizer()
    global_ident = _global_identity()
    details: list[dict] = []
    seen: set[Path] = set()
    for d in dirs:
        for repo in find_repos(d):
            if repo in seen:
                continue
            seen.add(repo)
            remotes: list[str] = []
            tokens: list[str] = []
            out = _git(repo, "config", "--get-regexp", r"^remote\..*\.url$")
            for line in out.splitlines():
                url = line.partition(" ")[2]
                toks = ps._parse_remote_tokens(url)
                if toks and "/".join(toks) not in remotes:
                    remotes.append("/".join(toks))
                tokens.extend(t for t in toks if t not in tokens)
            identities = []
            for key in ("user.name", "user.email"):
                value = _git(repo, "config", "--local", "--get", key)
                if value and value not in global_ident:
                    identities.append(value)
            details.append(
                {
                    "path": repo,
                    "root": d,
                    "remotes": remotes,
                    "tokens": tokens,
                    "identities": identities,
                }
            )
    return details


def scan(dirs: list[Path]) -> dict:
    """Recorre ``dirs`` y devuelve repos, tokens de org/repo e identidades."""
    ps = _pseudonymizer()
    details = repo_details(dirs)
    tokens: list[str] = []
    generic: list[str] = []
    identities: list[str] = []
    for repo in details:
        for tok in repo["tokens"]:
            bucket = generic if ps.is_generic_repo_token(tok) else tokens
            if tok not in bucket:
                bucket.append(tok)
        identities.extend(v for v in repo["identities"] if v not in identities)
    return {
        "repos": len(details),
        "tokens": tokens,
        "generic": generic,
        "identities": identities,
    }


def protect(result: dict, path: Path | None = None, dry_run: bool = False) -> dict:
    """Añade a config.json lo que falte. Devuelve cuántos son nuevos."""
    ps = _pseudonymizer()
    path = path or config_file()
    config = load_config(path)
    words = set(config.get("pseudo_word_literals") or [])
    literals = set(config.get("pseudo_literals") or [])
    new_tokens = [t for t in result["tokens"] if t not in words]
    new_idents = [v for v in result["identities"] if v not in literals]
    if not dry_run:
        new_tokens, _ = ps.add_word_literals_to_config(new_tokens, path)
        new_idents, _ = ps._add_to_config_list("pseudo_literals", new_idents, path)
    return {"tokens": len(new_tokens), "identities": len(new_idents)}


def describe(result: dict, added: dict, dry_run: bool = False) -> str:
    """Una línea para la terminal: solo recuentos, nunca nombres."""
    verb = "se añadirían" if dry_run else "nuevos"
    line = (
        f"🛡️  org/repo de {result['repos']} repos protegidos "
        f"({len(result['tokens'])} tokens, {added['tokens']} {verb})"
    )
    if result["identities"]:
        line += (
            f" · {len(result['identities'])} identidades git locales "
            f"({added['identities']} {verb})"
        )
    return line


def generic_warning(result: dict) -> str:
    """Los genéricos (``docs``, ``api``…) no se añaden: pseudonimizarían esa
    palabra en todo el texto (#63). Son palabras comunes, se pueden mostrar."""
    if not result["generic"]:
        return ""
    return (
        f"⚠️  org/repo genérico no protegido: {', '.join(result['generic'])} "
        "(añádelo a pseudo_word_literals si es privado)"
    )


def scan_and_protect(cwd: Path | None = None, dry_run: bool = False) -> list[str]:
    """Explora y protege; devuelve las líneas a mostrar."""
    config = load_config()
    dirs = projects_dirs(config, cwd)
    if not dirs:
        return [
            "🛡️  Sin carpeta de proyectos que explorar "
            "(arranca desde un repo o define projects_dirs en config.json)"
        ]
    result = scan(dirs)
    added = protect(result, dry_run=dry_run)
    lines = [describe(result, added, dry_run=dry_run)]
    warning = generic_warning(result)
    if warning:
        lines.append(warning)
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="klaus-scan-repos",
        description=(
            "Protege el org/repo de todos los repos git de la carpeta de "
            "proyectos (projects_dirs en config.json). Reinicia claude-proxy "
            "para aplicarlo."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra cuántos se añadirían, sin escribir config.json",
    )
    args = parser.parse_args(argv)
    for line in scan_and_protect(dry_run=args.dry_run):
        print(line)
    if not args.dry_run:
        print("   Reinicia claude-proxy para aplicarlo.")
    sys.exit(0)


if __name__ == "__main__":
    main()
