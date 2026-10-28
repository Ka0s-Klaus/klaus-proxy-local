"""Immutable snapshot of the mitmproxy addons (#71).

mitmproxy reloads ``-s`` scripts whenever they change on disk. Loading them
straight from the working clone meant every ``git checkout``/``stash`` or edit
swapped the pseudonymizer protecting live sessions, and a broken file left the
proxy running without it (fail-open). claude-proxy now copies the addons into
a content-addressed, read-only directory and runs mitmdump from there, so the
clone can change freely until the next restart.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# Load order matters: file log first (it must be attached when the others log
# on load), guard last (it checks what the pseudonymizer did).
ADDON_FILES = (
    "klaus_file_log.py",
    "anthropic_payload_pseudonymize.py",
    "anthropic_payload_capture.py",
    "klaus_pseudo_guard.py",
)
VERSION_FILE = "VERSION.json"


def snapshot_root() -> Path:
    return Path.home() / ".klaus-proxy" / "addons"


def source_commit(src_dir: Path) -> str:
    """Short commit of the clone, ``+dirty`` if the addons differ from it."""
    try:
        sha = subprocess.run(
            ["git", "-C", str(src_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(src_dir), "status", "--porcelain", "--", *ADDON_FILES],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
        return f"{sha}+dirty" if dirty else sha
    except Exception:
        return "unknown"


def _content_hash(src_dir: Path) -> str:
    h = hashlib.sha256()
    for name in ADDON_FILES:
        h.update(name.encode())
        h.update(b"\0")
        h.update((src_dir / name).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def snapshot_addons(src_dir: Path, root: Path | None = None) -> tuple[Path, dict]:
    """Copy the addons to ``<root>/<sha12>/`` once and return ``(dir, info)``.

    The directory is content-addressed: the same addons reuse it, any change
    gets a new one, and existing snapshots are never modified (a proxy still
    running from them must not see a reload). Files are made read-only.
    """
    root = root or snapshot_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    sha = _content_hash(src_dir)
    dest = root / sha[:12]
    if not dest.is_dir():
        tmp = root / f".tmp-{sha[:12]}-{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(mode=0o700)
        for name in ADDON_FILES:
            shutil.copyfile(src_dir / name, tmp / name)
            os.chmod(tmp / name, 0o444)
        info = {
            "commit": source_commit(src_dir),
            "sha": sha,
            "source": str(src_dir),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        (tmp / VERSION_FILE).write_text(json.dumps(info, indent=2), encoding="utf-8")
        os.chmod(tmp / VERSION_FILE, 0o444)
        try:
            os.rename(tmp, dest)
        except OSError:
            # Another claude-proxy created it first: same content, use theirs.
            shutil.rmtree(tmp, ignore_errors=True)
    info = json.loads((dest / VERSION_FILE).read_text(encoding="utf-8"))
    return dest, info
