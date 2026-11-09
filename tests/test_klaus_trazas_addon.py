"""Tests del addon que genera trazas desde el proxy (docs/trazabilidad.md)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import klaus_trazas_addon as ka  # noqa: E402
from Klaus_proxy_local import trace_stats as ts  # noqa: E402
from Klaus_proxy_local.addons_snapshot import ADDON_FILES  # noqa: E402

SRC = Path(__file__).parent.parent / "src"
SECRET_TEXT = "mi pregunta confidencial sobre el cliente Acme"


def _request(**extra) -> bytes:
    body = {
        "model": "modelo-ejemplo-x",
        "max_tokens": 256,
        "temperature": 0.2,
        "messages": [
            {"role": "user", "content": "primera pregunta"},
            {"role": "assistant", "content": "respuesta"},
            {"role": "user", "content": SECRET_TEXT},
        ],
    }
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def _json_response(model="modelo-ejemplo-x-2026-09") -> bytes:
    return json.dumps(
        {
            "id": "msg_1",
            "model": model,
            "content": [{"type": "text", "text": "respuesta del modelo"}],
            "usage": {"input_tokens": 812, "output_tokens": 146},
        }
    ).encode("utf-8")


def _sse_response(model="modelo-ejemplo-x-2026-09") -> bytes:
    return (
        "event: message_start\n"
        f'data: {{"type":"message_start","message":{{"model":"{model}",'
        '"usage":{"input_tokens":812,"output_tokens":1}}}\n\n'
        "event: content_block_delta\n"
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hola"}}\n\n'
        "event: message_delta\n"
        'data: {"type":"message_delta","usage":{"output_tokens":146}}\n\n'
    ).encode("utf-8")


def _trace_file(trace_dir: Path) -> Path:
    files = list(trace_dir.glob("*/*.jsonl"))
    assert len(files) == 1
    return files[0]


# ── Funciones puras ─────────────────────────────────────────────────────────


def test_last_user_text_uses_last_user_message():
    body = json.loads(_request())
    assert ka.last_user_text(body) == SECRET_TEXT


def test_last_user_text_handles_block_lists():
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hola"},
                    {"type": "image", "source": {}},
                    {"type": "text", "text": "mundo"},
                ],
            }
        ]
    }
    assert ka.last_user_text(body) == "hola\nmundo"


def test_returned_model_json_and_sse():
    assert ka.returned_model(_json_response()) == "modelo-ejemplo-x-2026-09"
    assert ka.returned_model(_sse_response()) == "modelo-ejemplo-x-2026-09"
    assert ka.returned_model(b"no es nada") is None


def test_usage_tokens_json_and_sse():
    assert ka.usage_tokens(_json_response()) == (812, 146)
    # En SSE el de salida llega al final (message_delta)
    assert ka.usage_tokens(_sse_response()) == (812, 146)


def test_request_params_keeps_sampling_fields_only_when_present():
    params = ka.request_params({"model": "m", "temperature": 0.2})
    assert params == {"requested_model": "m", "temperature": 0.2}


# ── Registro de una llamada ─────────────────────────────────────────────────


def test_successful_call_writes_valid_trace_without_text(tmp_path):
    trace_id = ka.record_exchange(
        _request(), 200, _json_response(), blocked=False, trace_dir=tmp_path
    )
    assert trace_id
    path = _trace_file(tmp_path)
    report = ts.read_trace_file(path)
    assert report.issues == []
    types = [e["event_type"] for e in report.events]
    assert types == ["input_received", "model_called", "output_emitted"]
    assert SECRET_TEXT not in path.read_text(encoding="utf-8")
    assert "respuesta del modelo" not in path.read_text(encoding="utf-8")


def test_successful_call_records_real_returned_model(tmp_path):
    ka.record_exchange(
        _request(), 200, _json_response(), blocked=False, trace_dir=tmp_path
    )
    stats = ts.compute_stats(ts.scan_traces(tmp_path))
    assert stats["model_calls"] == 1
    assert stats["model_version_drift"] == 1
    assert stats["outputs_emitted"] == 1
    # Sin revisión humana en el proxy: toda salida cuenta como no revisada
    assert stats["outputs_without_review"] == 1


def test_streaming_response_is_recorded(tmp_path):
    ka.record_exchange(
        _request(), 200, _sse_response(), blocked=False, trace_dir=tmp_path
    )
    events = ts.read_trace_file(_trace_file(tmp_path)).events
    model = next(e for e in events if e["event_type"] == "model_called")
    assert model["payload"]["returned_model"] == "modelo-ejemplo-x-2026-09"
    assert model["payload"]["output_tokens"] == 146


def test_api_error_records_error_event(tmp_path):
    ka.record_exchange(
        _request(), 529, b'{"type":"error"}', blocked=False, trace_dir=tmp_path
    )
    report = ts.read_trace_file(_trace_file(tmp_path))
    assert report.issues == []
    err = report.events[-1]
    assert err["event_type"] == "error"
    assert err["payload"]["error_code"] == "HTTP_529"
    assert err["payload"]["recoverable"] is True


def test_non_recoverable_error_is_marked(tmp_path):
    ka.record_exchange(_request(), 400, b"{}", blocked=False, trace_dir=tmp_path)
    err = ts.read_trace_file(_trace_file(tmp_path)).events[-1]
    assert err["payload"]["recoverable"] is False


def test_blocked_request_records_guard_error(tmp_path):
    ka.record_exchange(_request(), 403, b"", blocked=True, trace_dir=tmp_path)
    report = ts.read_trace_file(_trace_file(tmp_path))
    assert report.issues == []
    assert report.events[-1]["payload"]["error_code"] == "BLOCKED_BY_GUARD"


def test_missing_response_records_error(tmp_path):
    ka.record_exchange(_request(), None, b"", blocked=False, trace_dir=tmp_path)
    err = ts.read_trace_file(_trace_file(tmp_path)).events[-1]
    assert err["payload"]["error_code"] == "NO_RESPONSE"


def test_non_message_body_writes_nothing(tmp_path):
    result = ka.record_exchange(
        b'{"sin": "modelo"}', 200, b"{}", blocked=False, trace_dir=tmp_path
    )
    assert result is None
    assert list(tmp_path.glob("*/*.jsonl")) == []


def test_invalid_json_writes_nothing(tmp_path):
    assert (
        ka.record_exchange(b"no json", 200, b"{}", blocked=False, trace_dir=tmp_path)
        is None
    )
    assert list(tmp_path.glob("*/*.jsonl")) == []


def test_addon_failure_does_not_raise(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(ka.trazas, "start_trace", boom)
    assert (
        ka.record_exchange(
            _request(), 200, _json_response(), blocked=False, trace_dir=tmp_path
        )
        is None
    )


# ── Integración con el empaquetado ──────────────────────────────────────────


def test_addon_is_registered_before_guard():
    assert "klaus_trazas_addon.py" in ADDON_FILES
    assert ADDON_FILES.index("klaus_trazas_addon.py") < ADDON_FILES.index(
        "klaus_pseudo_guard.py"
    )
    assert (SRC / "klaus_trazas_addon.py").exists()


def test_hook_reads_decoded_body_not_compressed_bytes(tmp_path, monkeypatch):
    """Regresión: con gzip, raw_content son bytes comprimidos; hay que leer .content."""
    import gzip
    from types import SimpleNamespace

    monkeypatch.setenv("KLAUS_TRAZAS_DIR", str(tmp_path))
    plain = _json_response()
    flow = SimpleNamespace(
        request=SimpleNamespace(
            method="POST",
            path="/v1/messages",
            content=_request(),
            raw_content=_request(),
        ),
        response=SimpleNamespace(
            status_code=200, content=plain, raw_content=gzip.compress(plain)
        ),
        metadata={},
    )
    ka.KlausTrazasAddon().response(flow)
    events = ts.read_trace_file(_trace_file(tmp_path)).events
    model = next(e for e in events if e["event_type"] == "model_called")
    assert model["payload"]["returned_model"] == "modelo-ejemplo-x-2026-09"
    assert model["payload"]["input_tokens"] == 812
