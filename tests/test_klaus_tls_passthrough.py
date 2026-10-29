"""Tests del addon que deja en túnel el TLS que no va a la API (#105)."""

import json
import logging
from types import SimpleNamespace

import pytest

import klaus_tls_passthrough as tp


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(tp.Path, "home", lambda: tmp_path)
    for var in (
        "ANTHROPIC_PSEUDO_HOSTS",
        "ANTHROPIC_CAPTURE_HOSTS",
        "ANTHROPIC_BASE_URL",
        "KLAUS_INTERCEPT_ALL",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def clienthello(sni, address=("example.org", 443)):
    ctx = SimpleNamespace(
        client=SimpleNamespace(sni=sni), server=SimpleNamespace(address=address)
    )
    return SimpleNamespace(context=ctx, ignore_connection=False)


class TestInterceptHosts:
    def test_defaults(self, home):
        assert tp.intercept_hosts() == ("anthropic.com", "claude.ai")

    def test_config_hosts_and_env(self, home, monkeypatch):
        write_json(home / ".klaus-proxy" / "config.json", {"hosts": ["GW.Example"]})
        monkeypatch.setenv("ANTHROPIC_PSEUDO_HOSTS", "llm.example, ")
        hosts = tp.intercept_hosts()
        assert "gw.example" in hosts
        assert "llm.example" in hosts
        assert "" not in hosts

    def test_base_url_from_env_and_claude_settings(self, home, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gw1.example:8443/v1")
        write_json(
            home / ".claude" / "settings.json",
            {"env": {"ANTHROPIC_BASE_URL": "https://gw2.example"}},
        )
        hosts = tp.intercept_hosts()
        assert "gw1.example" in hosts
        assert "gw2.example" in hosts

    def test_broken_config_keeps_defaults(self, home):
        (home / ".klaus-proxy").mkdir()
        (home / ".klaus-proxy" / "config.json").write_text("{no json")
        assert tp.intercept_hosts() == ("anthropic.com", "claude.ai")


@pytest.mark.parametrize(
    "host,expected",
    [
        ("api.anthropic.com", True),
        ("anthropic.com", True),
        ("API.Anthropic.com.", True),
        ("claude.ai", True),
        ("evilanthropic.com", False),
        ("pypi.org", False),
        ("", False),
    ],
)
def test_should_intercept(host, expected):
    assert tp.should_intercept(host, ("anthropic.com", "claude.ai")) is expected


class TestInterceptAll:
    def test_env(self, home, monkeypatch):
        monkeypatch.setenv("KLAUS_INTERCEPT_ALL", "1")
        assert tp.intercept_all() is True

    def test_config(self, home):
        write_json(home / ".klaus-proxy" / "config.json", {"intercept_all": True})
        assert tp.intercept_all() is True

    def test_default_off(self, home):
        assert tp.intercept_all() is False


class TestClientHello:
    def test_api_host_is_decrypted(self, home):
        a = tp.KlausTlsPassthrough()
        a.load(None)
        data = clienthello("api.anthropic.com")
        a.tls_clienthello(data)
        assert data.ignore_connection is False

    def test_other_host_is_tunnelled_and_logged(self, home, caplog):
        a = tp.KlausTlsPassthrough()
        a.load(None)
        data = clienthello("pypi.org", ("pypi.org", 443))
        with caplog.at_level(logging.INFO, logger="klaus.flow"):
            a.tls_clienthello(data)
        assert data.ignore_connection is True
        assert "TÚNEL pypi.org:443" in caplog.text

    def test_no_sni_uses_server_address(self, home):
        a = tp.KlausTlsPassthrough()
        a.load(None)
        data = clienthello(None, ("api.anthropic.com", 443))
        a.tls_clienthello(data)
        assert data.ignore_connection is False

    def test_intercept_all_decrypts_everything(self, home, monkeypatch):
        monkeypatch.setenv("KLAUS_INTERCEPT_ALL", "1")
        a = tp.KlausTlsPassthrough()
        a.load(None)
        data = clienthello("pypi.org")
        a.tls_clienthello(data)
        assert data.ignore_connection is False
