"""Tests del snapshot inmutable de addons y del guardián fail-closed (#71)."""

import json
import stat
import subprocess
from types import SimpleNamespace

import pytest

import klaus_pseudo_guard as guard
from Klaus_proxy_local import addons_snapshot as snap


@pytest.fixture
def src_dir(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    for name in snap.ADDON_FILES:
        (d / name).write_text(f"# {name} v1\n", encoding="utf-8")
    return d


@pytest.fixture
def root(tmp_path):
    return tmp_path / "addons"


def test_snapshot_copies_addons_read_only_with_version(src_dir, root):
    dest, info = snap.snapshot_addons(src_dir, root)
    assert dest.parent == root
    for name in snap.ADDON_FILES:
        assert (dest / name).read_text(encoding="utf-8") == f"# {name} v1\n"
        assert stat.S_IMODE((dest / name).stat().st_mode) == 0o400
    assert info["sha"].startswith(dest.name)
    assert json.loads((dest / snap.VERSION_FILE).read_text()) == info
    assert not [p for p in root.iterdir() if p.name.startswith(".tmp-")]


def test_snapshot_is_content_addressed(src_dir, root):
    first, _ = snap.snapshot_addons(src_dir, root)
    assert snap.snapshot_addons(src_dir, root)[0] == first
    (src_dir / "anthropic_payload_pseudonymize.py").write_text("# v2\n")
    second, _ = snap.snapshot_addons(src_dir, root)
    assert second != first
    # El snapshot anterior no cambia: un proxy que corra desde él no recarga.
    assert (first / "anthropic_payload_pseudonymize.py").read_text() == (
        "# anthropic_payload_pseudonymize.py v1\n"
    )


def test_editing_the_clone_does_not_touch_the_snapshot(src_dir, root):
    dest, _ = snap.snapshot_addons(src_dir, root)
    before = (dest / "anthropic_payload_pseudonymize.py").stat().st_mtime_ns
    (src_dir / "anthropic_payload_pseudonymize.py").write_text("this is ( broken")
    (src_dir / "anthropic_payload_capture.py").unlink()
    assert (dest / "anthropic_payload_pseudonymize.py").stat().st_mtime_ns == before
    assert (dest / "anthropic_payload_capture.py").exists()


def test_snapshot_race_reuses_existing_dir(src_dir, root, monkeypatch):
    dest, _ = snap.snapshot_addons(src_dir, root)
    real_is_dir = snap.Path.is_dir
    # Simula que otro claude-proxy crea el snapshot entre la comprobación y el
    # rename: is_dir() dice que no existe, pero el rename choca con él.
    monkeypatch.setattr(
        snap.Path, "is_dir", lambda self: False if self == dest else real_is_dir(self)
    )
    assert snap.snapshot_addons(src_dir, root)[0] == dest
    assert not [p for p in root.iterdir() if p.name.startswith(".tmp-")]


def test_source_commit_reports_dirty_addons(src_dir):
    git = ["git", "-C", str(src_dir)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
        check=True,
    )
    clean = snap.source_commit(src_dir)
    assert clean and "+dirty" not in clean and clean != "unknown"
    (src_dir / "klaus_pseudo_guard.py").write_text("# cambiado\n")
    assert snap.source_commit(src_dir) == clean + "+dirty"


def test_source_commit_outside_git(tmp_path):
    assert snap.source_commit(tmp_path) == "unknown"


# --- guardián -----------------------------------------------------------------


def _flow(seen=False, response=None):
    return SimpleNamespace(
        metadata={"klaus_pseudo_seen": True} if seen else {},
        response=response,
        request=SimpleNamespace(
            method="POST",
            pretty_host="api.anthropic.com",
            path="/v1/messages",
            pretty_url="https://api.anthropic.com/v1/messages",
        ),
    )


def test_guard_lets_through_requests_seen_by_pseudonymizer():
    flow = _flow(seen=True)
    guard.KlausPseudoGuard().request(flow)
    assert flow.response is None
    assert "anthropic_blocked" not in flow.metadata


def test_guard_blocks_requests_the_pseudonymizer_never_saw():
    flow = _flow(seen=False)
    guard.KlausPseudoGuard().request(flow)
    assert flow.response.status_code == 502
    assert b"BLOQUEADA" in flow.response.content
    assert flow.metadata["anthropic_blocked"] is True


def test_guard_respects_existing_response():
    """El fail-closed del seudonimizador ya respondió: no se toca."""
    existing = object()
    flow = _flow(seen=False, response=existing)
    guard.KlausPseudoGuard().request(flow)
    assert flow.response is existing


def test_guard_reports_snapshot_version(tmp_path):
    (tmp_path / guard.VERSION_FILE).write_text(
        json.dumps({"commit": "abc1234", "sha": "f" * 64})
    )
    assert guard.addons_version(tmp_path) == "abc1234 (snapshot ffffffffffff)"
    assert guard.addons_version(tmp_path / "nada").startswith("sin snapshot")


def test_guard_is_last_in_load_order():
    assert snap.ADDON_FILES[-1] == "klaus_pseudo_guard.py"
    assert snap.ADDON_FILES[0] == "klaus_file_log.py"
    assert any(isinstance(a, guard.KlausPseudoGuard) for a in guard.addons)
