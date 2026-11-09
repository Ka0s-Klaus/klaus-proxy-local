"""Plan ``traces`` del informe de auditoría y su renderizado (issue #226)."""

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import trace_report as tr  # noqa: E402

ROOT = Path(__file__).parent.parent
TID = "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33"
SECRET = "pregunta-confidencial-de-un-cliente"


def _write(trace_dir: Path, events, tid=TID, date="2026-11-09"):
    path = trace_dir / date / f"{tid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _ok_events(tid=TID, returned="modelo-x"):
    def ev(eid, parent, seq, etype, actor, payload):
        return {
            "event_id": eid,
            "trace_id": tid,
            "parent_event_id": parent,
            "seq": seq,
            "timestamp": f"2026-11-09T09:14:0{seq}Z",
            "event_type": etype,
            "schema_version": "0.1",
            "actor": actor,
            "payload": payload,
        }

    return [
        ev(
            "a1",
            None,
            1,
            "input_received",
            "user",
            {"content_hash": "sha256:" + "ab" * 32, "channel": "proxy"},
        ),
        ev(
            "b2",
            "a1",
            2,
            "model_called",
            "model",
            {
                "requested_model": "modelo-x",
                "returned_model": returned,
                "provider": "anthropic",
                "output_hash": "sha256:" + "cd" * 32,
                "input_tokens": 3,
                "output_tokens": 4,
            },
        ),
        ev(
            "c3",
            "b2",
            3,
            "output_emitted",
            "system",
            {"output_hash": "sha256:" + "cd" * 32, "destination": "cliente"},
        ),
    ]


def test_no_traces_gives_no_data(tmp_path):
    plan = tr.audit_traces(tmp_path / "vacio")
    assert plan["status"] == "no_data"
    assert plan["total"] == 0 and plan["details"] == []


def test_unreviewed_outputs_give_warning(tmp_path):
    _write(tmp_path, _ok_events())
    plan = tr.audit_traces(tmp_path)
    assert plan["status"] == "warning"  # el proxy no tiene revisión humana
    assert plan["outputs_without_review"] == 1
    assert any("revisión humana" in item for item in plan["review_items"])


def test_integrity_issue_gives_critical(tmp_path):
    events = _ok_events()
    events[2]["seq"] = 9  # hueco en seq
    _write(tmp_path, events)
    plan = tr.audit_traces(tmp_path)
    assert plan["status"] == "critical"
    assert plan["with_issues"] == 1
    assert plan["details"][0]["issue_count"] >= 1


def test_unknown_model_counts_separately(tmp_path):
    _write(tmp_path, _ok_events(returned="no_devuelto"))
    plan = tr.audit_traces(tmp_path)
    assert plan["model_unknown"] == 1 and plan["model_drift"] == 0


def test_details_contain_timeline_and_no_content(tmp_path):
    events = _ok_events()
    events[0]["payload"]["content_hash"] = "sha256:" + "ab" * 32
    _write(tmp_path, events)
    plan = tr.audit_traces(tmp_path)
    detail = plan["details"][0]
    assert [e["type"] for e in detail["timeline"]] == [
        "input_received",
        "model_called",
        "output_emitted",
    ]
    assert SECRET not in json.dumps(plan)


def _dashboard():
    spec = importlib.util.spec_from_file_location(
        "gad", ROOT / "scripts" / "generate_audit_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_escapes_html_in_details(tmp_path):
    gad = _dashboard()
    plan = {
        "details": [
            {
                "trace_id": TID,
                "date": "2026-11-09",
                "time": "09:00:00",
                "status": "ok",
                "issues": ["<script>x</script>"],
                "issue_count": 1,
                "timeline": [
                    {
                        "seq": 1,
                        "time": "09:00:00",
                        "type": "input_received",
                        "actor": "user",
                        "summary": "canal=<b>proxy</b>",
                    }
                ],
            }
        ],
    }
    out = gad._traces_details_html(plan)
    assert "<script>x</script>" not in out
    assert "&lt;script&gt;" in out
    assert "&lt;b&gt;proxy&lt;/b&gt;" in out
    assert "<details" in out


def test_dashboard_renders_traces_panel_without_placeholders(tmp_path):
    gad = _dashboard()
    _write(tmp_path, _ok_events())
    plan = tr.audit_traces(tmp_path)
    empty = {"status": "no_data"}
    page = gad.render_html(
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        0,
        "sin datos",
        traces=plan,
    )
    assert 'id="panel-traces"' in page
    assert "#TRACES_" not in page
    assert "Trazas recientes" in page
    # Sin trazas también debe generar una página válida
    page2 = gad.render_html(
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        {"status": "good"},
        0,
        "sin datos",
        traces=empty,
    )
    assert "#TRACES_" not in page2
