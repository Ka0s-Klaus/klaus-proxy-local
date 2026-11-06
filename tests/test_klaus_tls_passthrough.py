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
        assert tp.intercept_hosts() == ("api.anthropic.com",)

    def test_config_hosts_and_env(self, home, monkeypatch):
        write_json(home / ".klaus-proxy" / "config.json", {"hosts": ["GW.Example"]})
        monkeypatch.setenv("ANTHROPIC_PSEUDO_HOSTS", "llm.example, ")
        hosts = tp.intercept_hosts()
        assert "gw.example" in hosts
        assert "llm.example" in hosts
        assert "" not in hosts

    def test_capture_only_hosts_are_decrypted(self, home):
        # #125: lo que se captura sin seudonimizar también hay que descifrarlo
        write_json(
            home / ".klaus-proxy" / "config.json",
            {"capture_only_hosts": ["mcp-proxy.anthropic.com"]},
        )
        assert "mcp-proxy.anthropic.com" in tp.intercept_hosts()

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
        assert tp.intercept_hosts() == ("api.anthropic.com",)


@pytest.mark.parametrize(
    "host,expected",
    [
        ("api.anthropic.com", True),
        ("edge.api.anthropic.com", True),
        ("anthropic.com", False),
        ("mcp-proxy.anthropic.com", False),
        ("downloads.claude.ai", False),
        ("API.Anthropic.com.", True),
        ("evilapi.anthropic.com", False),
        ("claude.ai", False),
        ("api.anthropic.com.evil.example", False),
        ("pypi.org", False),
        ("", False),
    ],
)
def test_should_intercept(host, expected):
    assert tp.should_intercept(host, ("api.anthropic.com",)) is expected


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


def make_project(root, name, settings=None, filename="settings.json"):
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    if settings is not None:
        write_json(repo / ".claude" / filename, settings)
    return repo


_REAL_PROJECT_REPOS = tp._project_repos


@pytest.fixture(autouse=True)
def no_real_projects(monkeypatch):
    """Por defecto no se escanea ningún proyecto (nunca el disco real)."""
    monkeypatch.setattr(tp, "_project_repos", lambda: [])


@pytest.fixture
def projects(home, monkeypatch):
    """Carpeta de proyectos temporal registrada en config.json."""
    from Klaus_proxy_local import scan_repos

    cfg = home / ".klaus-proxy" / "config.json"
    monkeypatch.setattr(scan_repos, "config_file", lambda: cfg)
    monkeypatch.setattr(tp, "_project_repos", _REAL_PROJECT_REPOS)
    root = home / "projects"
    write_json(cfg, {"projects_dirs": [str(root)]})
    return root


class TestProjectBaseUrl:
    def test_reads_settings_and_settings_local(self, tmp_path):
        a = make_project(
            tmp_path,
            "a",
            {"env": {"ANTHROPIC_BASE_URL": "https://gw-a.example:8443/v1"}},
        )
        b = make_project(
            tmp_path,
            "b",
            {"env": {"ANTHROPIC_BASE_URL": "https://GW-B.example"}},
            filename="settings.local.json",
        )
        assert tp.project_base_url_hosts([a, b]) == {"gw-a.example", "gw-b.example"}

    def test_ignores_broken_or_irrelevant_settings(self, tmp_path):
        bad = make_project(tmp_path, "bad")
        (bad / ".claude").mkdir()
        (bad / ".claude" / "settings.json").write_text("{no json", encoding="utf-8")
        other = make_project(tmp_path, "other", {"env": {"FOO": "1"}})
        assert tp.project_base_url_hosts([bad, other]) == frozenset()

    def test_blocked_unless_approved(self):
        approved = ("api.anthropic.com", "gw-ok.example")
        found = frozenset({"gw-ok.example", "gw-x.example", "api.anthropic.com"})
        assert tp.blocked_hosts(found, approved) == {"gw-x.example"}


class TestProjectGatewayBlocking:
    def test_project_host_without_approval_is_not_tunnelled(self, projects):
        make_project(
            projects, "app", {"env": {"ANTHROPIC_BASE_URL": "https://gw-x.example"}}
        )
        a = tp.KlausTlsPassthrough()
        a.load(None)
        assert a.blocked == {"gw-x.example"}
        data = clienthello("gw-x.example")
        a.tls_clienthello(data)
        # Se intercepta (no túnel) para que request() responda 403 sin reenviar
        assert data.ignore_connection is False

    def test_approved_project_host_works_as_audited(self, projects):
        make_project(
            projects, "app", {"env": {"ANTHROPIC_BASE_URL": "https://gw-ok.example"}}
        )
        write_json(
            projects.parent / ".klaus-proxy" / "config.json",
            {"projects_dirs": [str(projects)], "hosts": ["gw-ok.example"]},
        )
        a = tp.KlausTlsPassthrough()
        a.load(None)
        assert a.blocked == frozenset()
        data = clienthello("gw-ok.example")
        a.tls_clienthello(data)
        assert data.ignore_connection is False

    def test_request_gets_403_for_blocked_host(self, projects):
        pytest.importorskip("mitmproxy")
        make_project(
            projects, "app", {"env": {"ANTHROPIC_BASE_URL": "https://gw-x.example"}}
        )
        a = tp.KlausTlsPassthrough()
        a.load(None)
        flow = SimpleNamespace(
            request=SimpleNamespace(pretty_host="gw-x.example"), response=None
        )
        a.request(flow)
        assert flow.response is not None
        assert flow.response.status_code == 403

    def test_request_to_other_host_is_untouched(self, projects):
        pytest.importorskip("mitmproxy")
        a = tp.KlausTlsPassthrough()
        a.load(None)
        flow = SimpleNamespace(
            request=SimpleNamespace(pretty_host="pypi.org"), response=None
        )
        a.request(flow)
        assert flow.response is None

    def test_refresh_picks_up_new_project(self, projects):
        a = tp.KlausTlsPassthrough()
        a.load(None)
        assert a.blocked == frozenset()
        make_project(
            projects, "late", {"env": {"ANTHROPIC_BASE_URL": "https://gw-late.example"}}
        )
        a._refresh_projects()
        assert a.blocked == {"gw-late.example"}

    def test_warns_once_per_host(self, projects, caplog):
        make_project(
            projects, "app", {"env": {"ANTHROPIC_BASE_URL": "https://gw-x.example"}}
        )
        a = tp.KlausTlsPassthrough()
        with caplog.at_level(logging.WARNING, logger="klaus.flow"):
            a.load(None)
            a._refresh_projects()
        assert caplog.text.count("gw-x.example") == 1
