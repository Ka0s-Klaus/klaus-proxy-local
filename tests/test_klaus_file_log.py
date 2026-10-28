"""Tests del addon de log en disco (#55)."""

import logging
import logging.handlers
import stat

import pytest

import klaus_file_log as kfl


@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    monkeypatch.setenv("KLAUS_LOG_DIR", str(d))
    return d


@pytest.fixture
def addon(tmp_log_dir):
    # mitmproxy pone el logger raíz en DEBUG al arrancar (tools/main.py)
    root = logging.getLogger()
    old_level = root.level
    root.setLevel(logging.DEBUG)
    a = kfl.KlausFileLog()
    a.load(None)
    yield a
    a.done()
    root.setLevel(old_level)


def test_log_dir_defaults_to_klaus_home(monkeypatch, tmp_path):
    monkeypatch.delenv("KLAUS_LOG_DIR", raising=False)
    monkeypatch.setattr(kfl.Path, "home", lambda: tmp_path)
    assert kfl.log_file() == tmp_path / ".klaus-proxy" / "logs" / "proxy.log"


def test_log_dir_honours_env(tmp_log_dir):
    assert kfl.log_file() == tmp_log_dir / "proxy.log"


def test_load_creates_private_dir_and_file(addon, tmp_log_dir):
    path = tmp_log_dir / "proxy.log"
    assert path.exists()
    assert stat.S_IMODE(tmp_log_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_records_from_any_logger_reach_file(addon, tmp_log_dir):
    logging.getLogger("mitmproxy.proxy").info("hola desde mitmproxy")
    addon.handler.flush()
    assert "hola desde mitmproxy" in (tmp_log_dir / "proxy.log").read_text()


def test_ansi_codes_are_stripped(addon, tmp_log_dir):
    logging.getLogger("addon").info("\033[32m✅ seudonimizado\033[0m")
    addon.handler.flush()
    text = (tmp_log_dir / "proxy.log").read_text()
    assert "✅ seudonimizado" in text
    assert "\033" not in text


def test_build_handler_is_rotating(tmp_path):
    h = kfl.build_handler(tmp_path / "logs" / "proxy.log")
    try:
        assert isinstance(h, logging.handlers.RotatingFileHandler)
        assert h.maxBytes == kfl.MAX_BYTES
        assert h.backupCount == kfl.BACKUP_COUNT
    finally:
        h.close()


def test_done_detaches_handler(tmp_log_dir):
    a = kfl.KlausFileLog()
    a.load(None)
    handler = a.handler
    a.done()
    assert handler not in logging.getLogger().handlers
    assert a.handler is None


def test_load_survives_unwritable_dir(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("KLAUS_LOG_DIR", str(blocker / "logs"))
    a = kfl.KlausFileLog()
    a.load(None)  # no debe lanzar
    assert a.handler is None


def test_format_flow_drops_query_string():
    line = kfl.format_flow(
        "POST", "api.anthropic.com", "/v1/messages?beta=true&key=x", 200, 1234, 0.5
    )
    assert line == "POST api.anthropic.com/v1/messages → 200 1234B 500ms"


def test_format_flow_without_response():
    line = kfl.format_flow("GET", "example.com", "/", None, None, None)
    assert line == "GET example.com/ → - - -"


def test_module_exposes_addon():
    assert any(isinstance(a, kfl.KlausFileLog) for a in kfl.addons)
