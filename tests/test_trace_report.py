"""Tests de los informes legibles de trazas (issue #220)."""

import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import trace_report as tr  # noqa: E402
from Klaus_proxy_local import trace_stats as ts  # noqa: E402

SECRET = "pregunta-muy-privada-de-un-cliente"
TID = "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33"


def _ev(eid, parent, seq, etype, actor, payload):
    return {
        "event_id": eid,
        "trace_id": TID,
        "parent_event_id": parent,
        "seq": seq,
        "timestamp": f"2026-11-09T09:14:0{seq}Z",
        "event_type": etype,
        "schema_version": "0.1",
        "actor": actor,
        "payload": payload,
    }


def _trace(tid=TID, error=False):
    events = [
        _ev(
            "a1",
            None,
            1,
            "input_received",
            "user",
            {"content_hash": "sha256:" + "ab" * 32, "channel": "proxy"},
        ),
        _ev(
            "b2",
            "a1",
            2,
            "model_called",
            "model",
            {
                "requested_model": "modelo-x",
                "returned_model": "modelo-x",
                "provider": "anthropic",
                "output_hash": "sha256:" + "cd" * 32,
                "input_tokens": 10,
                "output_tokens": 5,
            },
        ),
        _ev(
            "c3",
            "b2",
            3,
            "output_emitted",
            "system",
            {"output_hash": "sha256:" + "cd" * 32, "destination": "cliente"},
        ),
    ]
    if error:
        events = [
            events[0],
            _ev(
                "e9",
                "a1",
                2,
                "error",
                "system",
                {
                    "error_code": "BLOCKED_BY_GUARD",
                    "error_message": "x",
                    "recoverable": True,
                },
            ),
        ]
    return events


def _report(tmp_path, events, tid=TID, date="2026-11-09"):
    path = tmp_path / date / f"{tid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return ts.read_trace_file(path)


def test_summary_reports_ok_and_tokens(tmp_path):
    s = tr.summarize_trace(_report(tmp_path, _trace()))
    assert s["status"] == "ok"
    assert s["requested_model"] == "modelo-x"
    assert (s["input_tokens"], s["output_tokens"]) == (10, 5)
    assert s["channel"] == "proxy"


def test_blocked_request_has_blocked_status(tmp_path):
    s = tr.summarize_trace(_report(tmp_path, _trace(error=True)))
    assert s["status"] == "bloqueada"


def test_find_trace_by_prefix_and_ambiguity(tmp_path):
    r1 = _report(tmp_path, _trace(), tid=TID)
    r2 = _report(tmp_path, _trace(), tid="7d2e0000-0000-4000-8000-000000000000")
    found, err = tr.find_trace([r1, r2], "7d2e9b40")
    assert found is r1 and err == ""
    found, err = tr.find_trace([r1, r2], "7d2e")
    assert found is None and "ambiguo" in err
    found, err = tr.find_trace([r1], "ffff")
    assert found is None and "No hay" in err


def test_detail_has_timeline_and_no_content(tmp_path):
    text = tr.render_detail(_report(tmp_path, _trace()))
    assert text.count("\n") > 3
    assert "model_called" in text and "output_emitted" in text
    assert SECRET not in text


def test_markdown_lists_items_to_review_and_hides_content(tmp_path):
    reports = [_report(tmp_path, _trace())]
    md = tr.render_markdown(reports, tmp_path)
    assert "## 🔍 Para revisar" in md
    assert "salidas sin revisión humana" in md
    assert "## 📜 Detalle por traza" in md
    assert SECRET not in md


def test_markdown_clean_when_nothing_to_review(tmp_path):
    md = tr.render_markdown([], tmp_path)
    assert "No hay trazas" in md


def test_write_private_sets_0600(tmp_path):
    target = tmp_path / "x" / "informe.md"
    tr.write_private(target, "hola")
    assert target.read_text(encoding="utf-8") == "hola"
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(target).st_mode) == 0o600


def test_recent_table_respects_limit(tmp_path):
    reports = [
        _report(
            tmp_path,
            _trace(tid=f"7d2e9b4{i}-0000-4000-8000-000000000000"),
            tid=f"7d2e9b4{i}-0000-4000-8000-000000000000",
        )
        for i in range(3)
    ]
    table = tr.render_recent_table(reports, limit=2)
    rows = [line for line in table.splitlines() if "modelo-x" in line]
    assert len(rows) == 2  # solo las dos trazas más recientes
