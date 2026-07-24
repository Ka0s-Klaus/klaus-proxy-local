#!/usr/bin/env python3
"""Tests para el addon de captura de payload de Anthropic."""
from __future__ import annotations

import json
from datetime import datetime

import pytest

import anthropic_payload_capture as cap

# --- is_anthropic_host -------------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("api.anthropic.com", True),
        ("API.ANTHROPIC.COM", True),
        ("edge.api.anthropic.com", True),
        ("llm.tools.cloud.customer1.es", True),
        ("api.openai.com", False),
        ("anthropic.com.evil.example", False),
        ("", False),
    ],
)
def test_is_anthropic_host(host, expected):
    assert cap.is_anthropic_host(host) is expected


def test_configured_hosts_env_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_CAPTURE_HOSTS", "foo.example, bar.example")
    assert cap.is_anthropic_host("foo.example") is True
    assert cap.is_anthropic_host("bar.example") is True
    # Con override, el default deja de aplicar.
    assert cap.is_anthropic_host("api.anthropic.com") is False


# --- redact_headers ----------------------------------------------------------


def test_redact_headers_masks_secrets():
    headers = {
        # Valor sintético ensamblado en runtime (no es una API key real).
        "x-api-key": "sk-" + "ant-" + "supersecret",
        "Authorization": "Bearer abc",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    out = cap.redact_headers(headers)
    assert out["x-api-key"] == cap.REDACTION
    assert out["Authorization"] == cap.REDACTION
    # No secretos: intactos.
    assert out["anthropic-version"] == "2023-06-01"
    assert out["content-type"] == "application/json"


def test_redact_headers_does_not_mutate_input():
    headers = {"x-api-key": "secret"}
    cap.redact_headers(headers)
    assert headers["x-api-key"] == "secret"


# --- parse_body --------------------------------------------------------------


def test_parse_body_json():
    raw = json.dumps({"model": "claude-opus-4-8", "max_tokens": 100}).encode()
    assert cap.parse_body(raw) == {"model": "claude-opus-4-8", "max_tokens": 100}


def test_parse_body_non_json_text():
    assert cap.parse_body(b"not json") == "not json"


def test_parse_body_empty():
    assert cap.parse_body(b"") is None
    assert cap.parse_body(None) is None


# --- build_record ------------------------------------------------------------


def test_build_record_redacts_by_default():
    now = datetime(2026, 6, 10, 14, 30, 22)
    record = cap.build_record(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        host="api.anthropic.com",
        path="/v1/messages",
        headers={"x-api-key": "secret", "anthropic-version": "2023-06-01"},
        body=json.dumps({"model": "claude-opus-4-8"}).encode(),
        captured_at=now,
        redact=True,
    )
    assert record["secrets_redacted"] is True
    assert record["headers"]["x-api-key"] == cap.REDACTION
    assert record["payload"] == {"model": "claude-opus-4-8"}
    assert record["method"] == "POST"
    assert record["captured_at"] == "2026-06-10T14:30:22"


def test_build_record_without_redaction_keeps_secret():
    now = datetime(2026, 6, 10, 14, 30, 22)
    record = cap.build_record(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        host="api.anthropic.com",
        path="/v1/messages",
        headers={"x-api-key": "secret"},
        body=None,
        captured_at=now,
        redact=False,
    )
    assert record["secrets_redacted"] is False
    assert record["headers"]["x-api-key"] == "secret"


# --- evidence_filename -------------------------------------------------------


def test_evidence_filename_format():
    now = datetime(2026, 6, 10, 14, 30, 22)
    assert cap.evidence_filename(now) == "20260610_143022_anthropic_payload.json"


# --- write_record ------------------------------------------------------------


def test_write_record_creates_file(tmp_path):
    now = datetime(2026, 6, 10, 14, 30, 22)
    record = {"hello": "world"}
    path = cap.write_record(record, now, directory=tmp_path)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"hello": "world"}
    assert path.name == "20260610_143022_anthropic_payload.json"


def test_write_record_avoids_collision(tmp_path):
    now = datetime(2026, 6, 10, 14, 30, 22)
    p1 = cap.write_record({"n": 1}, now, directory=tmp_path)
    p2 = cap.write_record({"n": 2}, now, directory=tmp_path)
    assert p1 != p2
    assert p1.exists() and p2.exists()


def test_output_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_CAPTURE_DIR", str(tmp_path))
    assert cap.output_dir() == tmp_path


# --- split original/sent -----------------------------------------------------


def test_parse_body_accepts_str():
    assert cap.parse_body('{"a": 1}') == {"a": 1}
    assert cap.parse_body("plain text") == "plain text"
    assert cap.parse_body("") is None


def test_sent_and_original_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_CAPTURE_DIR", str(tmp_path))
    assert cap.sent_dir() == tmp_path / "sent"
    assert cap.original_dir() == tmp_path / "original"


def test_build_record_variant_fields():
    now = datetime(2026, 6, 10, 14, 30, 22)
    rec = cap.build_record(
        method="POST",
        url="u",
        host="h",
        path="/v1/messages",
        headers={},
        body=b"{}",
        captured_at=now,
        variant="original",
        pseudonymized=True,
        counterpart="X.json",
    )
    assert rec["variant"] == "original"
    assert rec["pseudonymized"] is True
    assert rec["counterpart"] == "X.json"


def test_build_record_defaults_to_sent_variant():
    now = datetime(2026, 6, 10, 14, 30, 22)
    rec = cap.build_record(
        method="POST",
        url="u",
        host="h",
        path="/x",
        headers={},
        body=None,
        captured_at=now,
    )
    assert rec["variant"] == "sent"
    assert rec["pseudonymized"] is False


def test_evidence_paths_shared_name(tmp_path):
    sent = tmp_path / "sent"
    orig = tmp_path / "original"
    sent.mkdir()
    orig.mkdir()
    now = datetime(2026, 6, 10, 14, 30, 22)
    sp, op, name = cap.evidence_paths(now, sent, orig)
    assert sp.name == op.name == name
    assert sp.parent == sent and op.parent == orig
    assert name == "20260610_143022_anthropic_payload.json"


def test_evidence_paths_collision_keeps_pair_aligned(tmp_path):
    sent = tmp_path / "sent"
    orig = tmp_path / "original"
    sent.mkdir()
    orig.mkdir()
    now = datetime(2026, 6, 10, 14, 30, 22)
    sp, op, name = cap.evidence_paths(now, sent, orig)
    sp.write_text("{}")  # ocupa el nombre SOLO en sent/
    sp2, op2, name2 = cap.evidence_paths(now, sent, orig)
    assert name2 != name  # se ha incrementado por la colisión en sent/
    assert sp2.name == op2.name == name2  # el par sigue alineado en ambos dirs


# --- apply_forward: seudonimiza url/host/cabeceras sin acuñar -----------------


def test_apply_forward_replaces_known_reals_longest_first():
    mapping = {"llm.tools.cloud.acme": "llm.tools.cloud.org_x", "acme": "org_y"}
    out = cap.apply_forward("https://llm.tools.cloud.acme/v1", mapping)
    # longest-first: usa el mapeo del host completo, no el corto "acme".
    assert out == "https://llm.tools.cloud.org_x/v1"


def test_apply_forward_no_mint_and_noop():
    assert cap.apply_forward("nada que mapear", {}) == "nada que mapear"
    assert cap.apply_forward(None, {"a": "b"}) is None
    # valor ausente del mapa → intacto (no inventa seudónimos).
    assert (
        cap.apply_forward("texto sin secretos", {"otro": "x"}) == "texto sin secretos"
    )
