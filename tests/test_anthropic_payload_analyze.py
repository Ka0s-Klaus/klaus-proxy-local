#!/usr/bin/env python3
"""Tests del analizador de payloads /v1/messages."""
from __future__ import annotations

import json

import anthropic_payload_analyze as an

# --- CLI: ayuda y uso --------------------------------------------------------


def test_help_long_returns_zero_and_prints_usage(capsys):
    rc = an.main(["prog", "--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Uso:" in out
    assert "--all" in out


def test_help_short_returns_zero(capsys):
    assert an.main(["prog", "-h"]) == 0
    assert "Uso:" in capsys.readouterr().out


def test_no_args_prints_usage_and_returns_one(capsys):
    rc = an.main(["prog"])
    assert rc == 1
    assert "Uso:" in capsys.readouterr().out


# --- detección de payload ----------------------------------------------------


def test_is_messages_payload_true():
    rec = {"payload": {"model": "claude-opus-4-8", "messages": []}}
    assert an.is_messages_payload(rec) is True


def test_is_messages_payload_false_on_telemetry():
    assert an.is_messages_payload({"payload": {"events": []}}) is False
    assert an.is_messages_payload({"payload": "texto"}) is False
    assert an.is_messages_payload({}) is False


# --- summarize ---------------------------------------------------------------


def test_summarize_basic_fields():
    rec = {
        "host": "llm.tools.cloud.customer1.es",
        "payload": {
            "model": "claude-opus-4-8",
            "max_tokens": 64000,
            "system": [{"type": "text", "text": "hola"}],
            "tools": [{"name": "Read"}, {"name": "Bash"}],
            "messages": [{"role": "user", "content": "hey"}],
        },
    }
    s = an.summarize(rec)
    assert s["host"] == "llm.tools.cloud.customer1.es"
    assert s["model"] == "claude-opus-4-8"
    assert s["num_tools"] == 2
    assert s["tools"] == ["Read", "Bash"]
    assert s["num_messages"] == 1
    assert s["system_chars"] == len("hola")


# --- render_dump -------------------------------------------------------------


def test_render_dump_has_sections():
    rec = {
        "host": "h",
        "captured_at": "2026-06-10T14:30:22",
        "payload": {
            "model": "claude-opus-4-8",
            "max_tokens": 100,
            "system": "sys",
            "tools": [{"name": "Read", "description": "lee ficheros"}],
            "messages": [{"role": "user", "content": "hola"}],
        },
    }
    md = an.render_dump(rec)
    assert "## System prompt" in md
    assert "## Herramientas" in md
    assert "## Mensajes" in md
    assert "Read" in md


# --- main sobre un fichero concreto ------------------------------------------


def test_main_analyzes_a_concrete_file(tmp_path, capsys):
    rec = {
        "host": "llm.tools.cloud.customer1.es",
        "captured_at": "2026-06-10T14:30:22",
        "payload": {
            "model": "claude-opus-4-8",
            "max_tokens": 100,
            "system": [{"type": "text", "text": "sys"}],
            "tools": [{"name": "Read"}],
            "messages": [{"role": "user", "content": "hola"}],
        },
    }
    p = tmp_path / "cap.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    rc = an.main(["prog", str(p)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "llm.tools.cloud.customer1.es" in out
    assert "cap.json" in out


def test_main_dump_writes_decoded_md(tmp_path):
    rec = {
        "host": "h",
        "captured_at": "t",
        "payload": {
            "model": "claude-opus-4-8",
            "max_tokens": 1,
            "system": "s",
            "tools": [],
            "messages": [],
        },
    }
    p = tmp_path / "cap.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    an.main(["prog", "--dump", str(p)])
    assert (tmp_path / "cap.decoded.md").exists()
