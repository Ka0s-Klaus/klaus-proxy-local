"""Retención de capturas y opción de no guardar los originales (#132)."""

import importlib.util
import json
import stat
from datetime import datetime
from pathlib import Path

import pytest

import anthropic_pair_verify as pv
import anthropic_payload_capture as cap
from Klaus_proxy_local import capture_retention as cr
from Klaus_proxy_local.launcher import ProxyLauncher

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 30, 12, 0, 0)
OLD = "20261029_100000_anthropic_payload.json"  # 32 días antes de NOW
RECENT = "20261125_100000_anthropic_payload.json"
# Para lo que usa la fecha real: siempre más antiguo que cualquier retención
ANCIENT = "20200101_100000_anthropic_payload.json"


def _pair(base, name, size=10):
    for sub in ("original", "sent"):
        d = base / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps({"x": "y" * size}))


@pytest.fixture
def captures(tmp_path):
    base = tmp_path / "captures"
    _pair(base, OLD)
    _pair(base, RECENT)
    (base / "original" / "notas.json").write_text("{}")  # sin fecha
    (base / "archive").mkdir()
    (base / "archive" / OLD).write_text("{}")
    (base / ".pseudonym_vault.json").write_text("{}")
    return base


def test_prune_removes_old_pairs_only(captures):
    res = cr.prune_captures(captures, 30, now=NOW)
    assert res["removed_pairs"] == 1
    assert res["freed_bytes"] > 0
    assert res["oldest_kept"] == "2026-11-25T10:00:00"
    for sub in ("original", "sent"):
        assert not (captures / sub / OLD).exists()
        assert (captures / sub / RECENT).exists()
    # Lo que no es un par con fecha, el archivo y el vault no se tocan
    assert (captures / "original" / "notas.json").exists()
    assert (captures / "archive" / OLD).exists()
    assert (captures / ".pseudonym_vault.json").exists()
    state = captures / cr.STATE_FILE
    assert json.loads(state.read_text())["removed_pairs"] == 1
    assert stat.S_IMODE(state.stat().st_mode) == 0o600


def test_dry_run_deletes_nothing(captures):
    res = cr.prune_captures(captures, 30, now=NOW, dry_run=True)
    assert res["removed_pairs"] == 1
    assert (captures / "sent" / OLD).exists()
    assert not (captures / cr.STATE_FILE).exists()
    assert "se borrarían 1 pares" in cr.describe(res, dry_run=True)


def test_zero_days_is_unlimited(captures):
    res = cr.prune_captures(captures, 0, now=NOW)
    assert res["removed_pairs"] == 0
    assert (captures / "sent" / OLD).exists()
    assert "sin límite" in cr.describe(res)


@pytest.mark.parametrize(
    "value,expected",
    [(None, 30), (7, 7), (0, 0), (-1, 30), ("10", 30), (True, 30)],
)
def test_retention_days(value, expected):
    config = {} if value is None else {"capture_retention_days": value}
    assert cr.retention_days(config) == expected


def test_captures_dir_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_CAPTURE_DIR", str(tmp_path / "env"))
    assert cr.captures_dir({"capture_dir": "/x"}) == tmp_path / "env"
    monkeypatch.delenv("ANTHROPIC_CAPTURE_DIR")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cr.captures_dir({"capture_dir": "~/c"}) == tmp_path / "c"
    assert cr.captures_dir({}) == tmp_path / ".klaus-proxy" / "captures"


def test_launcher_applies_retention(tmp_path, monkeypatch, capsys):
    base = tmp_path / "captures"
    _pair(base, ANCIENT)
    monkeypatch.setenv("ANTHROPIC_CAPTURE_DIR", str(base))
    launcher = ProxyLauncher()
    launcher.config = {"capture_retention_days": 30}
    launcher.apply_capture_retention()
    assert "30 días · borrados 1 pares" in capsys.readouterr().out
    assert not (base / "sent" / ANCIENT).exists()


def test_launcher_retention_failure_does_not_stop(monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(cr, "prune_captures", boom)
    launcher = ProxyLauncher()
    launcher.config = {}
    launcher.apply_capture_retention()
    assert "no aplicada: disco lleno" in capsys.readouterr().out


def test_cli_dry_run(tmp_path, monkeypatch, capsys):
    base = tmp_path / "captures"
    _pair(base, ANCIENT)
    monkeypatch.setenv("ANTHROPIC_CAPTURE_DIR", str(base))
    monkeypatch.setattr(cr, "load_config", lambda: {})
    with pytest.raises(SystemExit) as exc:
        cr.main(["--dry-run", "--days", "1"])
    assert exc.value.code == 0
    assert "1 días · se borrarían 1 pares" in capsys.readouterr().out
    assert (base / "sent" / ANCIENT).exists()


# --- capture_originals --------------------------------------------------------


def test_capture_originals_flag(_isolated_config_json):
    assert cap.capture_originals() is True
    _isolated_config_json.write_text('{"capture_originals": false}')
    assert cap.capture_originals() is False
    _isolated_config_json.write_text("{roto")
    assert cap.capture_originals() is True


# --- dashboard ----------------------------------------------------------------


@pytest.fixture
def dashboard():
    spec = importlib.util.spec_from_file_location(
        "generate_audit_dashboard_retention",
        ROOT / "scripts" / "generate_audit_dashboard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dashboard_uses_sent_without_original(dashboard, tmp_path):
    base = tmp_path / "captures"
    (base / "original").mkdir(parents=True)
    (base / "sent").mkdir()
    rec = {"host": "api.anthropic.com", "captured_at": "2026-11-25T10:00:00"}
    (base / "sent" / RECENT).write_text(json.dumps(rec))
    original, sent = dashboard._captures(base)
    assert len(sent) == 1
    assert original[0]["_sent_only"] is True
    assert original[0]["_file"] == RECENT


def test_dashboard_retention_notice(dashboard, tmp_path):
    base = tmp_path / "captures"
    base.mkdir()
    cr.write_state(
        base,
        {"last_run": "2026-11-30T12:00:00", "removed_pairs": 12, "freed_bytes": 2048},
    )
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text('{"capture_originals": false}')
    caps = [{"captured_at": "2026-11-25T10:00:00.123", "_sent_only": True}]
    r = dashboard.audit_retention(base, cfg_dir, caps)
    assert r["days"] == 30 and r["oldest"] == "2026-11-25T10:00:00"
    html = dashboard._retention_html({"retention": r})
    assert "30 días" in html
    assert "12 pares" in html and "2.0 KB" in html
    assert "capture_originals: false" in html
    assert dashboard._retention_html({}) == ""
    unlimited = dashboard._retention_html({"retention": {**r, "days": 0}})
    assert "Sin límite" in unlimited


# --- verificador por pares ----------------------------------------------------


def test_pair_verify_explains_missing_originals(tmp_path, capsys):
    base = tmp_path / "captures"
    (base / "original").mkdir(parents=True)
    (base / "sent").mkdir()
    (base / "sent" / RECENT).write_text("{}")
    code = pv.main(
        [
            "anthropic-pair-verify",
            "--original-dir",
            str(base / "original"),
            "--sent-dir",
            str(base / "sent"),
        ]
    )
    assert code == 2
    assert "capture_originals: false" in capsys.readouterr().err
