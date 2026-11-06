"""Centinela de fugas y recarga en caliente de reglas (#187, ADR-002)."""

import json
from datetime import datetime

import pytest

import anthropic_payload_pseudonymize as ps
from Klaus_proxy_local import sentinel as sn
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

WHEN = datetime(2026, 11, 6, 12, 0, 0)


@pytest.fixture(scope="module")
def scanner():
    return SensitiveDataScanner(enable_business=False)


class FakeSink:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


def make_sentinel(scanner, notifier=None, notify=True, min_confidence="MEDIUM"):
    sink = FakeSink()
    s = sn.Sentinel(
        sink=sink,
        min_confidence=min_confidence,
        notify=notify,
        notifier=notifier or (lambda t, m: True),
        scanner=scanner,
    )
    return s, sink


# --- extracción del texto nuevo ---------------------------------------------


def test_last_message_text_includes_tool_result_and_ignores_older_turns():
    payload = {
        "messages": [
            {"role": "user", "content": "turno antiguo ana@acme-internal.io"},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [{"type": "text", "text": "salida: ver foo.bar"}],
                    }
                ],
            },
        ]
    }
    text = sn.last_message_text(payload)
    assert "salida: ver foo.bar" in text
    assert "acme-internal" not in text


def test_last_message_text_empty_without_messages():
    assert sn.last_message_text({}) == ""
    assert sn.last_message_text({"messages": []}) == ""


def test_session_uses_working_directory_and_day():
    payload = {
        "system": [{"type": "text", "text": "Primary working directory: /p/uno\nmás"}]
    }
    assert sn.session_of(payload, WHEN) == "/p/uno|2026-11-06"
    assert sn.session_of({}, WHEN) == "sin-cwd|2026-11-06"


# --- detección y umbral ------------------------------------------------------


def test_detects_uncovered_value_and_writes_only_identifier(scanner):
    s, sink = make_sentinel(scanner)
    text = "contacto: ana@acme-internal.io"
    out = s.process(text, "/p|2026-11-06", lambda v: False, WHEN)
    assert out and out[0]["category"] == "corporate-domain"
    for rec in sink.records:
        assert rec["id"].startswith("⟨corporate-domain·")
        assert "acme-internal" not in json.dumps(rec, ensure_ascii=False)


def test_covered_value_is_not_an_alert(scanner):
    s, sink = make_sentinel(scanner)
    out = s.process("ana@acme-internal.io", "/p|d", lambda v: True, WHEN)
    assert out == [] and sink.records == []


def test_threshold_filters_low_confidence(scanner):
    # Un issue-key es LOW: con umbral MEDIUM no avisa; con LOW sí
    s_med, sink_med = make_sentinel(scanner, min_confidence="MEDIUM")
    s_low, sink_low = make_sentinel(scanner, min_confidence="LOW")
    text = "ver PRJX-123 y PRJX-124 y PRJX-125"
    s_med.process(text, "/p|d", lambda v: False, WHEN)
    s_low.process(text, "/p|d", lambda v: False, WHEN)
    assert all(r["confidence"] != "LOW" for r in sink_med.records)
    assert any(r["confidence"] == "LOW" for r in sink_low.records)


def test_one_alert_per_value_and_session(scanner):
    s, sink = make_sentinel(scanner)
    text = "ana@acme-internal.io"
    s.process(text, "/p|d", lambda v: False, WHEN)
    s.process(text, "/p|d", lambda v: False, WHEN)
    assert len(sink.records) == 1
    s.process(text, "/otro|d", lambda v: False, WHEN)  # otra sesión: vuelve a avisar
    assert len(sink.records) == 2


# --- notificaciones agrupadas por sesión ------------------------------------


def test_notifications_grouped_per_session_with_cooldown(scanner):
    calls = []
    s, _ = make_sentinel(scanner, notifier=lambda t, m: calls.append(m))
    s.process(
        "ana@acme-internal.io bob@otra-empresa.net", "/p|d", lambda v: False, WHEN
    )
    s.flush_notifications(now=1000.0)
    assert len(calls) == 1 and "2 dato(s)" in calls[0]
    # Dentro del enfriamiento no vuelve a notificar la misma sesión
    s.process("eva@tercera-firma.org", "/p|d", lambda v: False, WHEN)
    s.flush_notifications(now=1010.0)
    assert len(calls) == 1
    s.flush_notifications(now=1000.0 + sn.NOTIFY_COOLDOWN_S + 1)
    assert len(calls) == 2


def test_notify_disabled_sends_nothing(scanner):
    calls = []
    s, sink = make_sentinel(
        scanner, notifier=lambda t, m: calls.append(m), notify=False
    )
    s.process("ana@acme-internal.io", "/p|d", lambda v: False, WHEN)
    s.flush_notifications(now=1000.0)
    assert calls == [] and len(sink.records) == 1


# --- fail-safe ---------------------------------------------------------------


def test_observe_never_blocks_and_counts_drops(scanner, monkeypatch):
    s, _ = make_sentinel(scanner)

    class FullQueue:
        def put_nowait(self, item):
            raise sn.queue.Full

    monkeypatch.setattr(s, "_queue", FullQueue())
    s.observe("uno", "/p|d", lambda v: False)  # no debe bloquear ni lanzar
    assert s.dropped == 1


def test_pseudonymizer_observe_swallows_sentinel_errors():
    """Un fallo del centinela no puede tumbar la petición (fail-safe, ADR-002)."""

    class Boom:
        def observe(self, *args):
            raise RuntimeError("roto a propósito")

    p = ps.AnthropicPseudonymizer(vault=ps.Vault(), rules=ps.Rules())
    p._sentinel_state = "activo"
    p._sentinel = Boom()
    body = json.dumps({"messages": [{"role": "user", "content": "hola"}]})
    p._observe_sentinel(body, ps.Vault(), ps.Rules())  # no debe lanzar


# --- recarga en caliente (A) -------------------------------------------------


@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    """HOME temporal: build_rules y la recarga leen el mismo config.json."""
    home = tmp_path / "home"
    (home / ".klaus-proxy").mkdir(parents=True)
    cfg = home / ".klaus-proxy" / "config.json"
    cfg.write_text(json.dumps({"salt": "x"}), encoding="utf-8")
    v = home / ".klaus-proxy" / "captures" / ".pseudonym_vault.json"
    monkeypatch.setattr(ps.Path, "home", lambda: home)
    monkeypatch.setattr(ps, "config_path", lambda: cfg)
    monkeypatch.setattr(ps, "vault_path", lambda: v)
    return v


def test_rules_reloaded_when_config_changes_without_restart(
    isolated_vault, monkeypatch
):
    """Una regla aprobada con klaus-scan se aplica sin reiniciar (A, #187)."""
    cfg = ps.config_path()
    p = ps.AnthropicPseudonymizer()
    before = p._get_rules()
    assert "canario-zq" not in before.word_literals

    data = json.loads(cfg.read_text())
    data["pseudo_word_literals"] = ["canario-zq"]
    cfg.write_text(json.dumps(data), encoding="utf-8")

    after = p._get_rules()
    assert "canario-zq" in after.word_literals


def test_runtime_learned_tokens_survive_reload(isolated_vault):
    cfg = ps.config_path()
    p = ps.AnthropicPseudonymizer()
    rules = p._get_rules()
    p._runtime_added.add("aprendido-en-caliente")
    rules.add_word_literals(["aprendido-en-caliente"])

    data = json.loads(cfg.read_text())
    data["otra_clave"] = 1
    cfg.write_text(json.dumps(data), encoding="utf-8")

    assert "aprendido-en-caliente" in p._get_rules().word_literals


def test_injected_rules_are_never_reloaded(isolated_vault):
    rules = ps.Rules()
    p = ps.AnthropicPseudonymizer(rules=rules)
    cfg = ps.config_path()
    cfg.write_text(json.dumps({"pseudo_word_literals": ["nuevo-zq"]}), encoding="utf-8")
    assert p._get_rules() is rules
