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


def test_tool_result_turn_gets_its_own_input_hash():
    """Regresión: un turno tool_result no debe colapsar en el hash de la cadena vacía."""
    empty_hash = ka._sha256("")
    body_a = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "denegado A",
                    }
                ],
            }
        ]
    }
    body_b = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t2", "content": "ok B"}
                ],
            }
        ]
    }
    text_a, text_b = ka.last_user_text(body_a), ka.last_user_text(body_b)
    assert ka._sha256(text_a) != empty_hash
    assert ka._sha256(text_a) != ka._sha256(text_b)
    # La representación no contiene el texto como cadena suelta de la traza
    assert "denegado A" in text_a  # se hashea, nunca se guarda en la traza


# ── Métricas de rendimiento y conexión (docs/trazabilidad.md §4.4) ──────────


def test_performance_fields_from_timestamps():
    fields = ka.performance_fields(
        request_start=100.0,
        response_start=100.412,
        response_end=101.830,
        tcp_setup=99.5,  # conexión abierta antes de la petición: reutilizada
        strategy="lazy",
    )
    assert fields == {
        "duration_ms": 1830,
        "ttfb_ms": 412,
        "connection_reused": True,
        "connection_strategy": "lazy",
    }


def test_new_connection_is_not_reused():
    fields = ka.performance_fields(100.0, 100.2, 100.5, tcp_setup=100.01, strategy=None)
    assert fields["connection_reused"] is False
    assert "connection_strategy" not in fields


def test_unknown_timestamps_are_omitted_not_zeroed():
    # Sin instante de apertura no se sabe si la conexión se reutilizó: se omite.
    fields = ka.performance_fields(100.0, None, 100.5, tcp_setup=None, strategy=None)
    assert fields == {"duration_ms": 500}
    assert "connection_reused" not in fields
    assert "ttfb_ms" not in fields


def test_negative_durations_are_clamped_to_zero():
    fields = ka.performance_fields(100.0, 99.0, 99.0, tcp_setup=None, strategy=None)
    assert fields["duration_ms"] == 0
    assert fields["ttfb_ms"] == 0


def test_timing_of_tolerates_objects_without_mitmproxy_fields():
    from types import SimpleNamespace

    # Sin mitmproxy instalado ni campos de tiempo: no lanza y no inventa datos.
    assert ka.timing_of(SimpleNamespace()) == {}
    flow = SimpleNamespace(
        request=SimpleNamespace(timestamp_start=10.0),
        response=SimpleNamespace(timestamp_start=10.2, timestamp_end=10.9, status_code=200),
        server_conn=SimpleNamespace(timestamp_tcp_setup=9.0),
    )
    fields = ka.timing_of(flow)
    assert fields["duration_ms"] == 900
    assert fields["ttfb_ms"] == 200
    assert fields["connection_reused"] is True
    assert fields["http_status"] == 200


def test_successful_call_records_performance_fields(tmp_path):
    timing = {"duration_ms": 1830, "ttfb_ms": 412, "http_status": 200, "connection_reused": True}
    ka.record_exchange(
        _request(), 200, _json_response(), blocked=False, trace_dir=tmp_path, timing=timing
    )
    path = _trace_file(tmp_path)
    report = ts.read_trace_file(path)
    assert report.issues == []
    model = next(e for e in report.events if e["event_type"] == "model_called")
    assert model["payload"]["duration_ms"] == 1830
    assert model["payload"]["connection_reused"] is True
    assert SECRET_TEXT not in path.read_text(encoding="utf-8")


def test_error_event_records_performance_fields(tmp_path):
    timing = {"duration_ms": 95, "http_status": 529}
    ka.record_exchange(
        _request(), 529, b'{"type":"error"}', blocked=False, trace_dir=tmp_path, timing=timing
    )
    report = ts.read_trace_file(_trace_file(tmp_path))
    err = report.events[-1]
    assert err["payload"]["duration_ms"] == 95
    assert err["payload"]["http_status"] == 529
    assert err["payload"]["error_code"] == "HTTP_529"


def test_blocked_call_has_no_performance_fields(tmp_path):
    ka.record_exchange(
        _request(), None, b"", blocked=True, trace_dir=tmp_path, timing={"duration_ms": 5}
    )
    err = ts.read_trace_file(_trace_file(tmp_path)).events[-1]
    assert err["payload"]["error_code"] == "BLOCKED_BY_GUARD"
    assert "duration_ms" not in err["payload"]


def test_calls_without_timing_still_write_valid_traces(tmp_path):
    # Compatibilidad: sin timing, la traza es igual que antes (campos opcionales).
    ka.record_exchange(_request(), 200, _json_response(), blocked=False, trace_dir=tmp_path)
    report = ts.read_trace_file(_trace_file(tmp_path))
    assert report.issues == []
    model = next(e for e in report.events if e["event_type"] == "model_called")
    assert "duration_ms" not in model["payload"]
