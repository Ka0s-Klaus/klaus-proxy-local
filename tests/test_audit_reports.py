"""Tests del histórico de informes de auditoría (#77)."""

import importlib.util
import json
import stat
from datetime import datetime
from pathlib import Path

import pytest

from Klaus_proxy_local import audit_reports as ar

ROOT = Path(__file__).resolve().parent.parent


def _plans(**over):
    plans = {
        "security": {
            "status": "good",
            "total": 10,
            "unexpected_hosts": [],
            "unexpected_count": 0,
        },
        "pseudonymization": {"status": "good", "pct": 99.5, "pseudo_no": 0},
        "performance": {"status": "good", "total_all": 10, "daily_counts": [1, 2]},
        "tests": {"status": "good", "passed": 100, "failed": 0, "pass_rate": 100.0},
        "efdef": {
            "status": "good",
            "checks": [
                {"label": "config.json", "passed": True},
                {"label": "vault", "passed": True},
            ],
        },
    }
    for key, value in over.items():
        plans[key] = {**plans[key], **value}
    return plans


def _report(when, total=10, **over):
    return ar.build_report(_plans(**over), total, "2026-10-28 → 2026-10-29", when)


def test_save_report_never_overwrites_and_is_private(tmp_path):
    when = datetime(2026, 10, 29, 9, 0, 0)
    first = ar.save_report(_report(when), tmp_path / "informes")
    second_report = _report(when)
    second = ar.save_report(second_report, tmp_path / "informes")
    assert first.name == "audit-20261029-090000.json"
    assert second.name == "audit-20261029-090000-2.json"
    assert second_report["id"] == "audit-20261029-090000-2"
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "informes").stat().st_mode) == 0o700


def test_list_reports_newest_first_and_skips_broken(tmp_path):
    for h in (8, 10, 9):
        ar.save_report(_report(datetime(2026, 10, 29, h)), tmp_path)
    (tmp_path / "audit-roto.json").write_text("{no es json")
    ids = [r["id"] for r in ar.list_reports(tmp_path)]
    assert ids == [
        "audit-20261029-100000",
        "audit-20261029-090000",
        "audit-20261029-080000",
    ]
    reports = ar.list_reports(tmp_path)
    assert ar.predecessor(reports, ids[0])["id"] == ids[1]
    assert ar.predecessor(reports, ids[-1]) is None


def test_write_index_lists_statuses(tmp_path):
    ar.save_report(_report(datetime(2026, 10, 29, 8)), tmp_path)
    ar.save_report(
        _report(datetime(2026, 10, 29, 9), tests={"status": "critical"}), tmp_path
    )
    path = ar.write_index(ar.list_reports(tmp_path), tmp_path)
    text = path.read_text()
    assert text.startswith("window.KLAUS_REPORTS = ")
    entries = json.loads(text[len("window.KLAUS_REPORTS = ") : -2])
    assert [e["statuses"]["tests"] for e in entries] == ["critical", "good"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_diff_first_report_is_empty():
    assert ar.diff_reports(_report(datetime(2026, 10, 29)), None) == []


def test_diff_detects_status_numbers_hosts_and_checks():
    old = _report(datetime(2026, 10, 29, 8))
    new = _report(
        datetime(2026, 10, 29, 9),
        total=12,
        security={
            "status": "warning",
            "unexpected_hosts": ["evil.example"],
            "unexpected_count": 2,
        },
        tests={"passed": 98, "failed": 2, "pass_rate": 98.0},
        efdef={
            "checks": [
                {"label": "config.json", "passed": True},
                {"label": "vault", "passed": False},
            ]
        },
        performance={"daily_counts": [5, 6]},  # serie: no cuenta
    )
    changes = {(c["plan"], c["field"], c["kind"]): c for c in ar.diff_reports(new, old)}
    assert changes[("security", "status", "status")]["trend"] == "worse"
    assert changes[("security", "unexpected_hosts", "added")]["after"] == "evil.example"
    assert changes[("tests", "failed", "number")]["trend"] == "worse"
    assert changes[("tests", "pass_rate", "number")]["trend"] == "worse"
    assert changes[("tests", "passed", "number")]["trend"] == "neutral"
    assert changes[("efdef", "vault", "check")]["trend"] == "worse"
    assert changes[("general", "total_captures", "number")]["after"] == 12
    assert not any(c[1] == "daily_counts" for c in changes)


def test_diff_improvement_is_better():
    old = _report(
        datetime(2026, 10, 29, 8),
        security={"status": "critical"},
        pseudonymization={"pct": 90.0},
    )
    new = _report(datetime(2026, 10, 29, 9))
    trends = {c["field"]: c["trend"] for c in ar.diff_reports(new, old)}
    assert trends == {"status": "better", "pct": "better"}


def test_diff_ignores_tuple_vs_list_after_json_roundtrip(tmp_path):
    old = _report(datetime(2026, 10, 29, 8), security={"host_distribution": [("a", 1)]})
    ar.save_report(old, tmp_path)
    reloaded = ar.list_reports(tmp_path)[0]
    assert ar.diff_reports(reloaded, old) == []


def test_render_changes_html_escapes_and_summarizes():
    old = _report(datetime(2026, 10, 29, 8))
    new = _report(
        datetime(2026, 10, 29, 9), security={"unexpected_hosts": ["<script>x"]}
    )
    html = ar.render_changes_html(ar.diff_reports(new, old), old)
    assert "&lt;script&gt;x" in html and "<script>x" not in html
    assert "1 cambios" in html
    assert "primer informe" in ar.render_changes_html([], None)
    assert "Sin cambios" in ar.render_changes_html([], old)


def test_render_history_html_uses_base():
    r = _report(datetime(2026, 10, 29, 9))
    html = ar.render_history_html(r, "../informes/")
    assert 'src="../informes/index.js"' in html
    assert 'data-current="audit-20261029-090000"' in html


# --- generador completo, con los planes simulados ----------------------------


@pytest.fixture
def generator(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "generate_audit_dashboard_test",
        ROOT / "scripts" / "generate_audit_dashboard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    state = {
        "tests": {
            "status": "good",
            "test_count": 5,
            "passed": 5,
            "failed": 0,
            "errors": 0,
            "pass_rate": 100.0,
        }
    }
    monkeypatch.setattr(
        mod, "audit_security", lambda o, s: {"status": "good", "total": len(o)}
    )
    monkeypatch.setattr(
        mod, "audit_pseudonymization", lambda o, c: {"status": "good", "pct": 100.0}
    )
    monkeypatch.setattr(
        mod, "audit_performance", lambda o: {"status": "good", "total_all": len(o)}
    )
    monkeypatch.setattr(mod, "audit_tests", lambda root: state["tests"])
    monkeypatch.setattr(
        mod,
        "audit_efdef",
        lambda root, cfg: {
            "status": "good",
            "checks": [],
            "passed": 0,
            "total": 0,
            "pct": 0,
        },
    )
    return mod, state


def test_generator_keeps_history_and_shows_changes(generator, tmp_path):
    mod, state = generator
    captures = tmp_path / "captures"
    (captures / "original").mkdir(parents=True)
    (captures / "sent").mkdir()
    reports = tmp_path / "informes"
    args = [
        "--captures-dir",
        str(captures),
        "--config-dir",
        str(tmp_path),
        "--reports-dir",
        str(reports),
    ]

    mod.main(args)
    state["tests"] = {
        **state["tests"],
        "status": "critical",
        "failed": 3,
        "passed": 2,
        "pass_rate": 40.0,
    }
    import time

    time.sleep(1.1)
    mod.main(args + ["--output", str(tmp_path / "copia" / "dash.html")])

    jsons = sorted(reports.glob("audit-2*.json"))
    htmls = sorted(reports.glob("audit-2*.html"))
    assert len(jsons) == 2 and len(htmls) == 2
    dashboard = (reports / "audit-dashboard.html").read_text()
    assert dashboard == htmls[-1].read_text()
    assert "▼" in dashboard and "Fallidos" in dashboard
    assert "primer informe" in htmls[0].read_text()
    assert "#HISTORY_HTML#" not in dashboard and 'src="index.js"' in dashboard
    copy = (tmp_path / "copia" / "dash.html").read_text()
    assert 'src="../informes/index.js"' in copy
    index = (reports / "index.js").read_text()
    assert index.count('"id"') == 2
