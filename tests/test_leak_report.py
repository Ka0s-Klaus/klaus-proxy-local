"""klaus-leak-report: fugas y cobertura por proyecto (#146)."""

import importlib.util
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from Klaus_proxy_local import leak_report as lr
from Klaus_proxy_local import scan_repos

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 30, 12, 0, 0)
CLIENT = "Tailspin Toys S.L."


def _repo(path, remote):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote], check=True
    )
    return path


def _capture(base, name, payload, sent_payload, ts):
    for sub, body in (("original", payload), ("sent", sent_payload)):
        d = base / sub
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "captured_at": ts,
            "variant": sub,
            "path": "/v1/messages",
            "payload": body,
            "headers": {},
        }
        (d / name).write_text(json.dumps(rec))


def _payload(cwd, text, remote=None):
    p = {
        "system": [{"type": "text", "text": f"Primary working directory: {cwd}\n"}],
        "messages": [{"role": "user", "content": text}],
    }
    if remote:
        p["system"] = []
        p["safeguards"] = [
            {"git_state": {"visibility": [{"host": "github.com", "remote": remote}]}}
        ]
    return p


@pytest.fixture
def env(tmp_path, monkeypatch, _isolated_config_json):
    home = tmp_path / "home"
    projects = tmp_path / "proyectos"
    uno = _repo(projects / "uno", "dev2@example.com:wingtip/uno-app.git")
    (uno / "contrato.md").write_text(f"Cliente: {CLIENT}\n")
    dos = _repo(projects / "dos", "dev2@example.com:wingtip/dos-api.git")
    (dos / "LICENSE").write_text("Copyright (c) 2025 Fabrikam Partners\n")
    config = {
        "salt": "x",
        "projects_dirs": [str(projects)],
        "pseudo_word_literals": ["wingtip", "uno-app", "dos-api", "Fabrikam"],
        "pseudo_literals": ["Fabrikam Partners"],
    }
    (home / ".klaus-proxy").mkdir(parents=True)
    for cfg in (home / ".klaus-proxy" / "config.json", _isolated_config_json):
        cfg.write_text(json.dumps(config))
    monkeypatch.setenv("HOME", str(home))
    # El usuario del SO va en la ruta de tmp_path: fuera de las reglas del test
    monkeypatch.setattr("getpass.getuser", lambda: "usuario-de-prueba")
    monkeypatch.setattr(lr, "cache_path", lambda: tmp_path / "cache.json")
    caps = tmp_path / "captures"
    # uno: una fuga reciente (el nombre protegido sale tal cual) y una limpia
    _capture(
        caps,
        "20261029_100000_anthropic_payload.json",
        _payload(uno, "habla de wingtip"),
        _payload(uno, "habla de wingtip"),
        "2026-10-29T10:00:00",
    )
    _capture(
        caps,
        "20261029_110000_anthropic_payload.json",
        _payload(uno / "src", "nada"),
        _payload(uno / "src", "nada"),
        "2026-10-29T11:00:00",
    )
    # dos: atribuida por remote, sin cwd
    _capture(
        caps,
        "20261020_090000_anthropic_payload.json",
        _payload("/", "hola", remote="wingtip/dos-api"),
        _payload("/", "hola", remote="org_aaaa/org_bbbb"),
        "2026-10-20T09:00:00",
    )
    return {"projects": projects, "uno": uno, "dos": dos, "caps": caps, "tmp": tmp_path}


def test_attribution_by_cwd_and_remote(env):
    projects = [{"path": str(env["uno"])}, {"path": str(env["dos"])}]
    remotes = {"wingtip/dos-api": str(env["dos"])}
    assert lr.attribute(_payload(env["uno"] / "src", "x"), projects, remotes) == str(
        env["uno"]
    )
    assert lr.attribute(
        _payload("/", "x", "wingtip/dos-api"), projects, remotes
    ) == str(env["dos"])
    assert lr.attribute(_payload("/otra", "x"), projects, remotes) is None
    assert lr.capture_cwd({"system": "Primary working directory: /p/x\nmás"}) == "/p/x"


def test_report_coverage_and_leaks(env):
    report = lr.build_report(env["caps"], now=NOW)
    by = {p["name"]: p for p in report["projects"]}
    uno, dos = by["uno"], by["dos"]
    # uno: la razón social no tiene regla → sin cubrir; fuga reciente → crítico
    assert uno["coverage_pct"] < 100
    assert any(v["category"] == "business-name" for v in uno["uncovered"])
    assert uno["leaks"]["captures_total"] == 2
    assert uno["leaks"]["messages_total"] == 2
    assert uno["leaks"]["captures"] == 1 and uno["leaks"]["recent"] == 1
    assert uno["leaks"]["items"][0]["capture"].startswith("20261029_100000")
    assert ("org", lr.safe_id("wingtip", "org")) in [
        tuple(x) for x in uno["leaks"]["items"][0]["leaks"]
    ]
    assert uno["status"] == "critical"
    # dos: el titular ya está en las reglas; la captura por remote no fuga
    assert dos["coverage_pct"] == 100.0 and dos["status"] == "good"
    assert dos["leaks"]["captures_total"] == 1 and dos["leaks"]["captures"] == 0
    assert report["totals"]["detected"] >= 2


def test_report_never_contains_values(env):
    report = lr.build_report(env["caps"], now=NOW)
    text = json.dumps(report, ensure_ascii=False) + lr.render_html(report)
    for secret in (CLIENT, "Tailspin", "Fabrikam Partners", "wingtip"):
        assert secret not in text, secret
    assert "⟨business-name·" in text


def test_reveal_shows_values_and_skips_cache(env):
    report = lr.build_report(env["caps"], now=NOW, reveal=True)
    assert report["revealed"] is True
    assert CLIENT in json.dumps(report, ensure_ascii=False)
    assert "--reveal" in lr.render_html(report)
    assert not (env["tmp"] / "cache.json").exists()


def test_cache_has_no_values_and_is_reused(env, monkeypatch):
    lr.build_report(env["caps"], now=NOW)
    cache_text = (env["tmp"] / "cache.json").read_text()
    for secret in (CLIENT, "Tailspin", "wingtip"):
        assert secret not in cache_text
    calls = []
    monkeypatch.setattr(lr, "_analyze_capture", lambda *a: calls.append(a) or {})
    monkeypatch.setattr(lr, "scan_project", lambda *a, **k: calls.append(a) or {})
    lr.build_report(env["caps"], now=NOW)
    assert calls == []


def test_cache_invalidated_when_code_changes(env, monkeypatch):
    """Un cambio en el pseudonimizador o el escáner recalcula todo (#150)."""
    lr.build_report(env["caps"], now=NOW)
    monkeypatch.setattr(lr, "code_hash", lambda: "otro-codigo")
    calls = []
    real_scan = lr.scan_project
    monkeypatch.setattr(
        lr, "scan_project", lambda *a, **k: calls.append(a) or real_scan(*a, **k)
    )
    lr.build_report(env["caps"], now=NOW)
    assert len(calls) == 2  # los dos proyectos


def test_code_hash_covers_proxy_and_scanner():
    names = {p.name for p in lr.CODE_FILES}
    assert {"anthropic_payload_pseudonymize.py", "sensitive_data_scanner.py"} <= names
    assert all(p.exists() for p in lr.CODE_FILES)


def test_status_thresholds():
    assert lr._status(None, 0) == "good"
    assert lr._status(96, 0) == "good"
    assert lr._status(90, 0) == "warning"
    assert lr._status(50, 0) == "critical"
    assert lr._status(100, 1) == "critical"


def test_save_and_cli(env, capsys):
    out_dir = env["tmp"] / "informes" / "fugas"
    with pytest.raises(SystemExit) as exc:
        lr.main(["--captures-dir", str(env["caps"]), "--reports-dir", str(out_dir)])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "Cobertura global" in out and "uno" in out
    assert "Tailspin" not in out
    assert (out_dir / lr.REPORT_FILE).exists()
    assert len(list(out_dir.glob(f"{lr.REPORT_PREFIX}*.json"))) == 1  # el fechado
    assert (out_dir / lr.REPORT_JSON).exists()  # y el último
    assert lr.load_latest(out_dir)["projects"]


# --- tarjeta del dashboard -----------------------------------------------------------


@pytest.fixture
def dashboard():
    spec = importlib.util.spec_from_file_location(
        "generate_audit_dashboard_leaks",
        ROOT / "scripts" / "generate_audit_dashboard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dashboard_card(dashboard, env):
    out_dir = env["tmp"] / "informes" / "fugas"
    lr.save_report(lr.build_report(env["caps"], now=NOW), out_dir)
    data = dashboard.audit_leaks(out_dir)
    assert data["link"] == "fugas/leak-report.html"
    names = {p["name"]: p for p in data["projects"]}
    assert names["uno"]["recent"] == 1
    html = dashboard._leaks_html({"leaks": data})
    assert "🕵️ Fugas por proyecto" in html and "🔴" in html and "🟢" in html
    assert "Abrir el informe completo" in html


def test_dashboard_card_without_report(dashboard, tmp_path):
    assert dashboard.audit_leaks(tmp_path) is None
    assert "klaus-leak-report" in dashboard._leaks_html({"leaks": None})
    assert dashboard._leaks_html({}) == ""


def test_projects_dirs_used(env):
    assert scan_repos.projects_dirs(scan_repos.load_config()) == [env["projects"]]
