"""Tests del módulo de instrumentación de trazas (docs/trazabilidad.md §6, §7, §10)."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import trace_stats as ts  # noqa: E402
from Klaus_proxy_local import trazas as tz  # noqa: E402

ROOT = Path(__file__).parent.parent


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _demo(trace_dir: Path) -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    import ejemplo_trazas

    return ejemplo_trazas.run_demo(trace_dir)


# ── Flujo completo ──────────────────────────────────────────────────────────


def test_full_flow_produces_valid_trace(tmp_path):
    trace_id = _demo(tmp_path)
    files = list(tmp_path.glob("*/*.jsonl"))
    assert len(files) == 1
    events = _events(files[0])
    assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6]
    assert events[0]["parent_event_id"] is None
    assert all(e["trace_id"] == trace_id for e in events)
    report = ts.read_trace_file(files[0])
    assert report.issues == []


def test_stats_show_real_data_after_demo(tmp_path):
    _demo(tmp_path)
    reports = ts.scan_traces(tmp_path)
    stats = ts.compute_stats(reports)
    assert stats["traces_valid"] == 1
    assert stats["events_total"] == 6
    assert stats["model_version_drift"] == 1
    assert stats["verifications"] == {"cita_a_fuente": {"warn": 1}}
    assert stats["human_reviews"] == {"modified": 1}
    assert stats["outputs_emitted"] == 1
    assert stats["outputs_without_review"] == 0


def test_input_is_stored_as_hash_only(tmp_path):
    secret_input = "pregunta confidencial sobre el cliente Acme"
    ctx = tz.start_trace(secret_input, trace_dir=tmp_path)
    text = ctx.path.read_text(encoding="utf-8")
    assert "confidencial" not in text
    assert "sha256:" in text


def test_parent_defaults_to_last_event(tmp_path):
    ctx = tz.start_trace("x", trace_dir=tmp_path)
    first = ctx.last_event_id
    second = tz.record_event(
        ctx,
        "prompt_built",
        {"prompt_version": "1", "template_id": "t", "content_hash": "sha256:a"},
    )
    events = _events(ctx.path)
    assert events[1]["parent_event_id"] == first
    assert ctx.last_event_id == second


def test_unknown_event_type_raises(tmp_path):
    ctx = tz.start_trace("x", trace_dir=tmp_path)
    with pytest.raises(ValueError):
        tz.record_event(ctx, "inventado", {})


def test_end_trace_records_status(tmp_path):
    ctx = tz.start_trace("x", trace_dir=tmp_path)
    tz.end_trace(ctx, status="ok")
    assert ctx.status == "ok"


# ── Escritura y permisos (§5, §7) ───────────────────────────────────────────


def test_write_failure_does_not_raise(tmp_path, monkeypatch):
    ctx = tz.start_trace("x", trace_dir=tmp_path)

    def boom(path, line):
        raise OSError("disco lleno")

    monkeypatch.setattr(tz, "_append", boom)
    # No debe lanzar: la ejecución principal continúa (§7)
    event_id = tz.record_event(
        ctx,
        "prompt_built",
        {"prompt_version": "1", "template_id": "t", "content_hash": "sha256:a"},
    )
    assert event_id


@pytest.mark.skipif(os.name != "posix", reason="permisos POSIX")
def test_permissions_are_private(tmp_path):
    ctx = tz.start_trace("x", trace_dir=tmp_path / "t")
    dir_mode = stat.S_IMODE(os.stat(ctx.path.parent).st_mode)
    file_mode = stat.S_IMODE(os.stat(ctx.path).st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600


def test_env_var_selects_directory(tmp_path, monkeypatch):
    monkeypatch.setenv(tz.ENV_TRACE_DIR, str(tmp_path / "desde-env"))
    ctx = tz.start_trace("x")
    assert str(ctx.path).startswith(str(tmp_path / "desde-env"))


# ── Redacción (§6) ──────────────────────────────────────────────────────────


def test_redacts_email():
    out = tz.redact_text("escribe a juan.perez@cliente.es por favor")
    assert "juan.perez@cliente.es" not in out
    assert "[REDACTED:correo:" in out


def test_redacts_luhn_valid_card_but_not_random_digits():
    card = "4111 1111 1111 1111"  # tarjeta de prueba que pasa Luhn
    assert "4111" not in tz.redact_text(f"pago {card}")
    assert tz.redact_text("pedido 1234 5678 9012 3456") == "pedido 1234 5678 9012 3456"


def test_redacts_dni_and_nie():
    assert "12345678Z" not in tz.redact_text("DNI 12345678Z")
    assert "X1234567L" not in tz.redact_text("NIE X1234567L")


def test_redacts_known_secrets():
    key = "sk-ant-api03-abcdefghijklmnop"
    out = tz.redact_text(f"usa {key} ahora")
    assert key not in out
    assert "password=hunter2" not in tz.redact_text("password=hunter2")


def test_redaction_applies_to_payload_values(tmp_path):
    ctx = tz.start_trace("x", trace_dir=tmp_path)
    tz.record_event(
        ctx,
        "human_review",
        {"reviewer_id": "juan.perez@cliente.es", "decision": "approved"},
    )
    text = ctx.path.read_text(encoding="utf-8")
    assert "juan.perez@cliente.es" not in text


def test_filter_failure_writes_error_event_without_original(tmp_path):
    def broken(_payload):
        raise RuntimeError("regla rota")

    ctx = tz.start_trace("x", trace_dir=tmp_path, redact=broken)
    # start_trace ya usó el filtro roto: el input_received se sustituye por error
    events = _events(ctx.path)
    assert events[0]["event_type"] == "error"
    assert events[0]["payload"]["error_code"] == "REDACTION_FAILED"
    assert events[0]["payload"]["recoverable"] is True
    assert "regla rota" not in ctx.path.read_text(encoding="utf-8")


# ── Esquema JSON (§10.1) ────────────────────────────────────────────────────


def test_schema_enums_match_code():
    schema = json.loads(
        (ROOT / "schemas" / "evento.schema.json").read_text(encoding="utf-8")
    )
    props = schema["properties"]
    assert set(props["event_type"]["enum"]) == set(ts.EVENT_TYPES)
    assert set(props["actor"]["enum"]) == set(ts.ACTORS)
    assert set(tz.DEFAULT_ACTOR) == set(ts.EVENT_TYPES)


def test_schema_is_valid_json_with_conditions_for_each_type():
    schema = json.loads(
        (ROOT / "schemas" / "evento.schema.json").read_text(encoding="utf-8")
    )
    typed = {
        rule["if"]["properties"]["event_type"]["const"] for rule in schema["allOf"]
    }
    assert typed == set(ts.EVENT_TYPES)
