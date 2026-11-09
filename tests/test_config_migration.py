"""Migración de rutas de config.json al arrancar (issue #240).

Trabaja sobre un directorio temporal: nunca toca ~/.klaus-proxy real.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import setup as st  # noqa: E402


@pytest.fixture
def cfg_root(tmp_path, monkeypatch):
    root = tmp_path / "klaus"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(st, "config_dir", lambda: root)
    return root


def _write(root: Path, vault_path: str, mode: int = 0o600) -> Path:
    cfg = {
        "version": "0.12.2",
        "salt": "s" * 32,
        "hosts": ["api.anthropic.com"],
        "capture_dir": str(root / "captures"),
        "vault_path": vault_path,
        "log_level": "info",
        "pseudo_literals": [],
        "pseudo_word_literals": [],
    }
    f = root / "config.json"
    f.write_text(json.dumps(cfg), encoding="utf-8")
    os.chmod(f, mode)
    return f


def test_startup_migrates_stale_vault_path(cfg_root):
    f = _write(cfg_root, str(cfg_root / "captures" / ".vault.json"))
    result = st.init_config_if_missing()
    assert result["vault_path"] == str(cfg_root / "captures" / ".pseudonym_vault.json")
    assert json.loads(f.read_text(encoding="utf-8"))["vault_path"] == str(
        cfg_root / "captures" / ".pseudonym_vault.json"
    )


def test_migration_keeps_600_permissions(cfg_root):
    f = _write(cfg_root, str(cfg_root / "captures" / ".vault.json"))
    st.init_config_if_missing()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_correct_config_is_not_rewritten(cfg_root):
    f = _write(cfg_root, str(cfg_root / "captures" / ".pseudonym_vault.json"))
    before = f.stat().st_mtime_ns
    st.init_config_if_missing()
    assert f.stat().st_mtime_ns == before


def test_first_run_creates_valid_config(cfg_root):
    result = st.init_config_if_missing()
    assert result["vault_path"] == str(cfg_root / "captures" / ".pseudonym_vault.json")
    assert (cfg_root / "config.json").exists()
