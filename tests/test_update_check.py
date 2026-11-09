"""Aviso de versión al arrancar (issue #246). Sin red: la petición es inyectada."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import launcher  # noqa: E402
from Klaus_proxy_local import update_check as uc  # noqa: E402


def _release(tag: str, url: str = "https://github.com/org/repo/releases/tag/x") -> str:
    return json.dumps({"tag_name": tag, "html_url": url})


def test_parse_version_accepts_v_prefix_and_rejects_garbage():
    assert uc.parse_version("v0.12.3") == (0, 12, 3)
    assert uc.parse_version("0.9.0") == (0, 9, 0)
    assert uc.parse_version("latest") is None
    assert uc.parse_version("") is None
    assert uc.parse_version("0.12") is None


def test_older_version_is_outdated_with_url():
    status = uc.check_for_update(
        "0.12.2", fetch=lambda u, t: _release("v0.12.3"), env={}
    )
    assert status.state == "outdated"
    assert status.latest == "0.12.3"
    assert status.url and "releases" in status.url


def test_same_version_is_up_to_date():
    status = uc.check_for_update(
        "0.12.3", fetch=lambda u, t: _release("v0.12.3"), env={}
    )
    assert status.state == "up_to_date"


def test_newer_local_build_is_not_outdated():
    status = uc.check_for_update(
        "0.13.0", fetch=lambda u, t: _release("v0.12.3"), env={}
    )
    assert status.state == "up_to_date"


def test_numeric_comparison_not_string():
    # 0.9.0 < 0.10.0 aunque "0.9.0" > "0.10.0" como texto
    status = uc.check_for_update(
        "0.9.0", fetch=lambda u, t: _release("v0.10.0"), env={}
    )
    assert status.state == "outdated"


def test_network_failure_is_unknown_and_never_raises():
    def boom(url, timeout):
        raise OSError("sin red")

    assert uc.check_for_update("0.12.3", fetch=boom, env={}).state == "unknown"


def test_empty_or_bad_json_is_unknown():
    assert (
        uc.check_for_update("0.12.3", fetch=lambda u, t: None, env={}).state
        == "unknown"
    )
    assert (
        uc.check_for_update("0.12.3", fetch=lambda u, t: "{no json", env={}).state
        == "unknown"
    )
    assert (
        uc.check_for_update("0.12.3", fetch=lambda u, t: "[]", env={}).state
        == "unknown"
    )


def test_opt_out_skips_the_request():
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        return _release("v9.9.9")

    status = uc.check_for_update("0.12.3", fetch=fetch, env={uc.SKIP_ENV: "1"})
    assert status.state == "skipped"
    assert calls == []


def test_request_uses_timeout_and_generic_user_agent(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _release("v0.12.3").encode()

    def fake_urlopen(request, timeout):
        seen["timeout"] = timeout
        seen["ua"] = request.get_header("User-agent")
        seen["headers"] = dict(request.header_items())
        return Resp()

    monkeypatch.setattr(uc.urllib.request, "urlopen", fake_urlopen)
    assert uc._fetch_latest(uc.LATEST_URL, 2.0)
    assert seen["timeout"] <= 3
    assert seen["ua"] == uc.USER_AGENT
    # Ninguna cabecera de identidad
    lowered = {k.lower() for k in seen["headers"]}
    assert not lowered & {"cookie", "authorization", "from"}


def test_outdated_message_says_proxy_still_starts():
    status = uc.UpdateStatus("outdated", "0.12.2", latest="0.12.3", url="https://x")
    text = uc.describe(status)
    assert "v0.12.3" in text and "arranca igual" in text


def test_up_to_date_prints_nothing():
    assert uc.describe(uc.UpdateStatus("up_to_date", "0.12.3", latest="0.12.3")) == ""


def test_launcher_continues_when_check_crashes(monkeypatch, capsys):
    def explode(*a, **k):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(uc, "check_for_update", explode)
    lz = launcher.ProxyLauncher.__new__(launcher.ProxyLauncher)
    lz.check_for_updates()  # no debe lanzar
    assert capsys.readouterr().out == ""


def test_launcher_prints_warning_when_outdated(monkeypatch, capsys):
    monkeypatch.setattr(
        uc,
        "check_for_update",
        lambda current, **k: uc.UpdateStatus("outdated", current, "9.9.9", "https://x"),
    )
    lz = launcher.ProxyLauncher.__new__(launcher.ProxyLauncher)
    lz.check_for_updates()
    assert "9.9.9" in capsys.readouterr().out
