"""Tests de klaus-trazas: validación §4.3, estadísticas y CLI.

La traza de referencia es el ejemplo de la sección 8 de docs/trazabilidad.md.
"""

import copy
import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import trace_stats as ts  # noqa: E402

TRACE_ID = "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33"
E1 = "a1f0c3e2-7b1d-4c8a-9e21-0f3b2d5c6a10"
E2 = "b2e1d4f3-8c2e-4d9b-a032-1g4c3e6d7b21"
E3 = "c3f2e5a4-9d3f-4e0c-b143-2h5d4f7e8c32"
E4 = "d4a3f6b5-0e4a-4f1d-8254-3i6e5g8f9d43"
E5 = "e5b4a7c6-1f5b-4a2e-9365-4j7f6h9g0e54"
E6 = "f6c5b8d7-2a6c-4b3f-a476-5k8g7i0h1f65"


def _event(event_id, parent, seq, event_type, actor, payload):
    return {
        "event_id": event_id,
        "trace_id": TRACE_ID,
        "parent_event_id": parent,
        "seq": seq,
        "timestamp": f"2026-11-06T09:14:0{seq}Z",
        "event_type": event_type,
        "schema_version": "0.1",
        "actor": actor,
        "payload": payload,
    }


def example_trace():
    """Traza de la sección 8 de la especificación."""
    return [
        _event(
            E1,
            None,
            1,
            "input_received",
            "user",
            {"content_hash": "sha256:3f9a", "channel": "api"},
        ),
        _event(
            E2,
            E1,
            2,
            "retrieval_performed",
            "system",
            {
                "query": "política de retención de logs",
                "index_name": "docs-internos",
                "sources": [
                    {
                        "source_id": "doc-112",
                        "version": "v3.2",
                        "content_hash": "sha256:91ab",
                    }
                ],
            },
        ),
        _event(
            E3,
            E2,
            3,
            "model_called",
            "model",
            {
                "requested_model": "modelo-ejemplo-x",
                "returned_model": "modelo-ejemplo-x-2026-09",
                "provider": "proveedor-ejemplo",
                "temperature": 0.2,
                "input_tokens": 812,
                "output_tokens": 146,
                "output_hash": "sha256:c07e",
            },
        ),
        _event(
            E4,
            E3,
            4,
            "verification_run",
            "system",
            {
                "check_name": "cita_a_fuente",
                "check_version": "1.0",
                "result": "warn",
                "details_ref": "logs/contenido/d4a3f6b5.json",
            },
        ),
        _event(
            E5,
            E4,
            5,
            "human_review",
            "human_reviewer",
            {
                "reviewer_id": "rev-07",
                "decision": "modified",
                "comment_ref": "logs/contenido/e5b4a7c6.txt",
            },
        ),
        _event(
            E6,
            E5,
            6,
            "output_emitted",
            "system",
            {"output_hash": "sha256:5d1b", "destination": "usuario-final"},
        ),
    ]


def write_trace(path: Path, events) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) if not isinstance(e, str) else e for e in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── Validación de eventos ───────────────────────────────────────────────────


def test_example_trace_has_no_event_issues():
    for event in example_trace():
        assert ts.validate_event(event) == []


def test_example_trace_passes_integrity_rules():
    assert ts.validate_trace(example_trace()) == []


def test_missing_common_field_is_reported():
    event = example_trace()[0]
    del event["actor"]
    assert any("actor" in issue for issue in ts.validate_event(event))


def test_unknown_event_type_is_reported():
    event = example_trace()[0]
    event["event_type"] = "inventado"
    assert any("event_type desconocido" in i for i in ts.validate_event(event))


def test_missing_specific_payload_field_is_reported():
    event = example_trace()[2]  # model_called
    del event["payload"]["returned_model"]
    assert any("returned_model" in i for i in ts.validate_event(event))


def test_invalid_verification_result_is_reported():
    event = example_trace()[3]
    event["payload"]["result"] = "maybe"
    assert any("result fuera de" in i for i in ts.validate_event(event))


# ── Reglas de integridad (§4.3) y casos de fallo de §10.5 ──────────────────


def test_two_roots_is_reported():
    events = example_trace()
    events[1]["parent_event_id"] = None
    assert any("eventos raíz" in i for i in ts.validate_trace(events))


def test_seq_gap_is_reported():
    events = example_trace()
    events[3]["seq"] = 5  # hueco: no hay seq 4
    assert any("seq no es consecutivo" in i for i in ts.validate_trace(events))


def test_missing_parent_is_reported():
    events = example_trace()
    events[2]["parent_event_id"] = "no-existe"
    assert any("no existe en la traza" in i for i in ts.validate_trace(events))


def test_output_without_model_is_reported():
    # Se cambia el paso del modelo por una herramienta: la salida queda sin model_called.
    events = example_trace()
    events[2]["event_type"] = "tool_called"
    events[2]["payload"] = {
        "tool_name": "t",
        "tool_version": "1",
        "input_hash": "h",
        "output_hash": "h",
        "status": "ok",
    }
    assert any("sin model_called previo" in i for i in ts.validate_trace(events))


def test_orphan_approved_review_is_reported():
    events = [e for e in example_trace() if e["event_type"] != "output_emitted"]
    events[-1]["payload"]["decision"] = "approved"
    assert any("huérfano" in i for i in ts.validate_trace(events))


# ── Lectura de ficheros ─────────────────────────────────────────────────────


def test_read_valid_file_has_no_issues(tmp_path):
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    report = ts.read_trace_file(path)
    assert report.issues == []
    assert report.date == "2026-11-06"
    assert len(report.events) == 6


def test_invalid_json_line_does_not_crash(tmp_path):
    lines = [json.dumps(example_trace()[0]), "{no es json"]
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", lines)
    report = ts.read_trace_file(path)
    assert any("JSON no válido" in i for i in report.issues)


def test_scan_filters_by_date(tmp_path):
    write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    write_trace(tmp_path / "2026-11-07" / f"{TRACE_ID}.jsonl", example_trace())
    assert len(ts.scan_traces(tmp_path)) == 2
    assert len(ts.scan_traces(tmp_path, date="2026-11-07")) == 1


def test_scan_missing_dir_returns_empty(tmp_path):
    assert ts.scan_traces(tmp_path / "no-existe") == []


# ── Estadísticas ────────────────────────────────────────────────────────────


def test_stats_on_example_trace(tmp_path):
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    stats = ts.compute_stats([ts.read_trace_file(path)])
    assert stats["traces_total"] == 1
    assert stats["traces_valid"] == 1
    assert stats["events_total"] == 6
    assert stats["model_calls"] == 1
    assert stats["model_version_drift"] == 1  # 2026-09 devuelto ≠ pedido
    assert stats["verifications"] == {"cita_a_fuente": {"warn": 1}}
    assert stats["human_reviews"] == {"modified": 1}
    assert stats["outputs_emitted"] == 1
    assert stats["outputs_without_review"] == 0


def test_stats_count_unreviewed_output_and_recoverable_errors(tmp_path):
    events = example_trace()
    events = [e for e in events if e["event_type"] != "human_review"]
    events[-1]["seq"] = 5
    events.append(
        _event(
            "g7d6c9e8-0000-4000-8000-000000000001",
            E6,
            6,
            "error",
            "system",
            {"error_code": "E_TIMEOUT", "error_message": "x", "recoverable": True},
        )
    )
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", events)
    stats = ts.compute_stats([ts.read_trace_file(path)])
    assert stats["outputs_without_review"] == 1
    assert stats["errors_by_code"] == {"E_TIMEOUT": 1}
    assert stats["errors_recoverable"] == {"E_TIMEOUT": 1}


def test_text_report_never_prints_payload_values(tmp_path):
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    text = ts.render_text(ts.compute_stats([ts.read_trace_file(path)]))
    assert "sha256:" not in text
    assert "política de retención" not in text
    assert "rev-07" not in text
    assert "usuario-final" not in text


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_cli_json_output(tmp_path, capsys):
    write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    assert ts.main(["--dir", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["traces_total"] == 1
    assert data["events_total"] == 6


def test_cli_strict_returns_1_on_issues(tmp_path):
    broken = copy.deepcopy(example_trace())
    broken[3]["seq"] = 9
    write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", broken)
    assert ts.main(["--dir", str(tmp_path), "--strict"]) == 1
    assert ts.main(["--dir", str(tmp_path)]) == 0


def test_cli_missing_dir(tmp_path, capsys):
    missing = tmp_path / "no-existe"
    assert ts.main(["--dir", str(missing)]) == 0
    assert "No existe el directorio" in capsys.readouterr().err
    assert ts.main(["--dir", str(missing), "--strict"]) == 1


def test_cli_text_report(tmp_path, capsys):
    write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", example_trace())
    assert ts.main(["--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "klaus-trazas" in out
    assert "Total:            1" in out


@pytest.mark.skipif(os.name != "posix", reason="permisos POSIX")
def test_permissions_warning_when_readable_by_others(tmp_path):
    os.chmod(tmp_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
    assert ts.permissions_warning(tmp_path) is not None
    os.chmod(tmp_path, stat.S_IRWXU)
    assert ts.permissions_warning(tmp_path) is None


def test_invalid_trace_lists_reasons_in_stats(tmp_path):
    broken = copy.deepcopy(example_trace())
    broken[3]["seq"] = 9
    path = write_trace(tmp_path / "2026-11-06" / f"{TRACE_ID}.jsonl", broken)
    stats = ts.compute_stats([ts.read_trace_file(path)])
    assert stats["traces_with_issues"] == 1
    bad = stats["invalid_traces"][0]
    assert bad["trace_id"] == TRACE_ID
    assert any("seq no es consecutivo" in i for i in bad["issues"])


def test_issue_message_does_not_echo_payload_value():
    event = example_trace()[3]
    event["payload"]["result"] = "secreto-123"
    issues = ts.validate_event(event)
    assert issues and all("secreto-123" not in i for i in issues)
