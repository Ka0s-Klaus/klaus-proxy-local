#!/usr/bin/env python3
"""Tests del validador diferencial original↔sent."""
from __future__ import annotations

import json

import anthropic_pair_verify as pv
from anthropic_payload_pseudonymize import Rules

# --- helpers ------------------------------------------------------------------


def _record(payload, *, variant="original", headers=None):
    return {
        "captured_at": "2026-07-24T10:00:00",
        "variant": variant,
        "counterpart": "20260724_100000_anthropic_payload.json",
        "method": "POST",
        "host": "llm.tools.cloud.customer1.es",
        "path": "/v1/messages",
        "secrets_redacted": True,
        "headers": headers or {},
        "payload": payload,
    }


def _msg_payload(text):
    return {
        "model": "claude-opus-4-8",
        "max_tokens": 100,
        "system": [{"type": "text", "text": text}],
        "tools": [{"name": "Read"}, {"name": "Bash"}],
        "messages": [{"role": "user", "content": text}],
    }


def _write_pair(tmp_path, name, original_payload, sent_payload):
    o_dir = tmp_path / "original"
    s_dir = tmp_path / "sent"
    o_dir.mkdir(exist_ok=True)
    s_dir.mkdir(exist_ok=True)
    (o_dir / name).write_text(
        json.dumps(_record(original_payload, variant="original")), encoding="utf-8"
    )
    (s_dir / name).write_text(
        json.dumps(_record(sent_payload, variant="sent")), encoding="utf-8"
    )


# --- discover_pairs -----------------------------------------------------------


def test_discover_pairs_matches_by_name(tmp_path):
    _write_pair(
        tmp_path,
        "20260724_100000_anthropic_payload.json",
        _msg_payload("hola"),
        _msg_payload("hola"),
    )
    pairs, orphans = pv.discover_pairs(tmp_path / "original", tmp_path / "sent")
    assert len(pairs) == 1
    assert not orphans
    assert pairs[0][0] == "20260724_100000_anthropic_payload.json"


def test_discover_pairs_reports_orphans(tmp_path):
    (tmp_path / "original").mkdir()
    (tmp_path / "sent").mkdir()
    (tmp_path / "original" / "20260724_100000_anthropic_payload.json").write_text(
        json.dumps(_record(_msg_payload("x"))), encoding="utf-8"
    )
    pairs, orphans = pv.discover_pairs(tmp_path / "original", tmp_path / "sent")
    assert not pairs
    assert orphans == [("20260724_100000_anthropic_payload.json", "sent")]


# --- sensitive_spans ----------------------------------------------------------


def test_sensitive_spans_from_rules_and_regex():
    rules = Rules(
        path_prefixes=[("/Users/alice/proj", "proj")],
        literals=["alice"],
        word_literals=["acme-corp"],
    )
    rec = _record(
        _msg_payload("dev en /Users/alice/proj por alice (acme-corp) mail a@b.com")
    )
    spans = pv.sensitive_spans(rec, {}, rules)
    cats = {s.category for s in spans}
    assert "path" in cats
    assert "identity" in cats
    assert "org" in cats
    assert "email" in cats


def test_sensitive_spans_respects_min_len_and_presence():
    rules = Rules(literals=["ab", "presente"])  # "ab" < _MIN_LEAK_LEN
    rec = _record(_msg_payload("texto con presente dentro"))
    values = {s.value for s in pv.sensitive_spans(rec, {}, rules)}
    assert "presente" in values
    assert "ab" not in values  # descartado por longitud
    # literal no presente en el texto no genera span
    assert all(s.value != "ausente" for s in pv.sensitive_spans(rec, {}, rules))


def test_sensitive_spans_ipv4_excludes_loopback():
    rules = Rules()
    rec = _record(_msg_payload("host 10.20.30.40 y loopback 127.0.0.1"))
    values = {s.value for s in pv.sensitive_spans(rec, {}, rules)}
    assert "10.20.30.40" in values
    assert "127.0.0.1" not in values


def test_sensitive_spans_includes_vault_values():
    rules = Rules()
    rec = _record(_msg_payload("aparece secreto-largo aqui"))
    spans = pv.sensitive_spans(rec, {"secreto-largo": "id_deadbeef"}, rules)
    assert any(s.category == "vault" and s.value == "secreto-largo" for s in spans)


# --- diff_leaks ---------------------------------------------------------------


def test_diff_leaks_detects_surviving_value():
    spans = [pv.Span("alice", "identity")]
    sent = _record(_msg_payload("sigue apareciendo alice"), variant="sent")
    assert pv.diff_leaks(spans, sent) == spans


def test_diff_leaks_clean_when_pseudonymized():
    spans = [pv.Span("alice", "identity")]
    sent = _record(_msg_payload("sustituido por id_1234"), variant="sent")
    assert pv.diff_leaks(spans, sent) == []


# --- secrets_in_sent ----------------------------------------------------------


def test_secrets_in_sent_flags_raw_secret():
    aws = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    sent = _record(_msg_payload(f"clave {aws} en claro"), variant="sent")
    assert "aws-access-key" in pv.secrets_in_sent(sent)


def test_secrets_in_sent_clean_when_redacted():
    sent = _record(_msg_payload("clave «REDACTED:aws-access-key» ok"), variant="sent")
    assert pv.secrets_in_sent(sent) == []


# --- survivor_tokens ----------------------------------------------------------


def test_survivor_tokens_flags_unpseudonymized_slug():
    original = _record(_msg_payload("repo masorange-b2b del cliente"))
    sent = _record(_msg_payload("repo masorange-b2b del cliente"), variant="sent")
    assert "masorange-b2b" in pv.survivor_tokens(original, sent)


def test_survivor_tokens_ignores_allowlisted_and_removed():
    original = _record(_msg_payload("modo read-only y token secreto-slug-x"))
    # slug de la allowlist no cuenta; el otro fue seudonimizado (ausente en sent)
    sent = _record(_msg_payload("modo read-only y token org_abcd1234"), variant="sent")
    survivors = pv.survivor_tokens(original, sent)
    assert "read-only" not in survivors
    assert "secreto-slug-x" not in survivors


def test_survivor_tokens_excludes_pseudonyms():
    original = _record(_msg_payload("valor org_abcd1234 presente"))
    sent = _record(_msg_payload("valor org_abcd1234 presente"), variant="sent")
    assert pv.survivor_tokens(original, sent, {"real": "org_abcd1234"}) == []


# --- verify_pair --------------------------------------------------------------


def test_verify_pair_all_clean():
    rules = Rules(literals=["alice"])
    original = _record(_msg_payload("dev alice trabaja"))
    sent = _record(_msg_payload("dev id_1111 trabaja"), variant="sent")
    results = pv.verify_pair(original, sent, {}, rules)
    assert not pv.pair_failed(results)
    assert not pv.pair_warned(results)


def test_verify_pair_hard_leak_fails():
    rules = Rules(literals=["alice"])
    original = _record(_msg_payload("dev alice trabaja"))
    sent = _record(_msg_payload("dev alice trabaja"), variant="sent")
    results = pv.verify_pair(original, sent, {}, rules)
    assert pv.pair_failed(results)


def test_verify_pair_secret_in_sent_fails():
    jwt = "eyJ" + "abcdefghij" + ".ABCDEFGHIJ" + ".klmnopqrst"
    original = _record(_msg_payload("ok"))
    sent = _record(_msg_payload(f"token {jwt} fuera"), variant="sent")
    results = pv.verify_pair(original, sent, {}, Rules())
    assert pv.pair_failed(results)


def test_verify_pair_survivor_slug_is_not_a_verdict():
    # Un slug superviviente NO tumba ni avisa en el veredicto: es descubrimiento
    # aparte (--survivors), no una comprobación por par.
    original = _record(_msg_payload("cliente kyndryl-global-delivery"))
    sent = _record(_msg_payload("cliente kyndryl-global-delivery"), variant="sent")
    results = pv.verify_pair(original, sent, {}, Rules())
    assert not pv.pair_failed(results)
    assert not pv.pair_warned(results)


def test_verify_pair_flags_mismatched_variants():
    results = pv.verify_pair(
        _record(_msg_payload("x"), variant="sent"),
        _record(_msg_payload("x"), variant="original"),
        {},
        Rules(),
    )
    assert pv.pair_warned(results)


# --- main / CLI ---------------------------------------------------------------


def test_main_clean_pair_returns_zero(tmp_path, capsys):
    _write_pair(
        tmp_path,
        "20260724_100000_anthropic_payload.json",
        _msg_payload("hola mundo"),
        _msg_payload("hola mundo"),
    )
    rc = pv.main(
        [
            "prog",
            "--original-dir",
            str(tmp_path / "original"),
            "--sent-dir",
            str(tmp_path / "sent"),
        ]
    )
    assert rc == 0
    assert "Sin fugas" in capsys.readouterr().out


def test_main_leaking_pair_returns_one(tmp_path, capsys):
    _write_pair(
        tmp_path,
        "20260724_100000_anthropic_payload.json",
        _msg_payload("ip 10.20.30.40 fija"),
        _msg_payload("ip 10.20.30.40 fija"),
    )
    rc = pv.main(
        [
            "prog",
            "--original-dir",
            str(tmp_path / "original"),
            "--sent-dir",
            str(tmp_path / "sent"),
        ]
    )
    assert rc == 1
    assert "REVISAR" in capsys.readouterr().out


def test_main_fail_on_warn(tmp_path):
    # WARN se produce por incoherencia de variantes del par. --fail-on-warn lo
    # convierte en fallo; por defecto no tumba.
    name = "20260724_100000_anthropic_payload.json"
    o_dir = tmp_path / "original"
    s_dir = tmp_path / "sent"
    o_dir.mkdir()
    s_dir.mkdir()
    # variante cruzada a propósito → verify_pair avisa.
    (o_dir / name).write_text(
        json.dumps(_record(_msg_payload("x"), variant="sent")), encoding="utf-8"
    )
    (s_dir / name).write_text(
        json.dumps(_record(_msg_payload("x"), variant="original")), encoding="utf-8"
    )
    common = ["prog", "--original-dir", str(o_dir), "--sent-dir", str(s_dir)]
    assert pv.main(common) == 0  # WARN no tumba por defecto
    assert pv.main(common + ["--fail-on-warn"]) == 1


# --- message_text / survivors mode -------------------------------------------


def test_message_text_excludes_system_and_headers():
    rec = _record(_msg_payload("acme-uno en mensaje"))
    rec["payload"]["system"] = [{"type": "text", "text": "boiler-plate en system"}]
    rec["headers"] = {"X-Slug-Header": "no-deberia-verse"}
    text = pv.message_text(rec)
    assert "acme-uno" in text
    assert "boiler-plate" not in text
    assert "no-deberia-verse" not in text


def test_collect_survivors_counts_across_pairs(tmp_path):
    for stamp in ("100000", "100001"):
        _write_pair(
            tmp_path,
            f"20260724_{stamp}_anthropic_payload.json",
            _msg_payload("repo widget-alpha-lib"),
            _msg_payload("repo widget-alpha-lib"),
        )
    pairs, _ = pv.discover_pairs(tmp_path / "original", tmp_path / "sent")
    counts = pv.collect_survivors(pairs, {})
    assert counts.get("widget-alpha-lib") == 2


def test_main_survivors_mode_lists_and_returns_zero(tmp_path, capsys):
    _write_pair(
        tmp_path,
        "20260724_100000_anthropic_payload.json",
        _msg_payload("cliente beta-corp-internal"),
        _msg_payload("cliente beta-corp-internal"),
    )
    rc = pv.main(
        [
            "prog",
            "--survivors",
            "--original-dir",
            str(tmp_path / "original"),
            "--sent-dir",
            str(tmp_path / "sent"),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0  # informativo: nunca falla
    assert "beta-corp-internal" in out
    assert "supervivientes" in out


def test_main_no_pairs_returns_two(tmp_path):
    (tmp_path / "original").mkdir()
    (tmp_path / "sent").mkdir()
    rc = pv.main(
        [
            "prog",
            "--original-dir",
            str(tmp_path / "original"),
            "--sent-dir",
            str(tmp_path / "sent"),
        ]
    )
    assert rc == 2


def test_main_single_name_selects_one(tmp_path, capsys):
    for stamp in ("100000", "100001"):
        _write_pair(
            tmp_path,
            f"20260724_{stamp}_anthropic_payload.json",
            _msg_payload("limpio"),
            _msg_payload("limpio"),
        )
    rc = pv.main(
        [
            "prog",
            "20260724_100001_anthropic_payload.json",
            "--original-dir",
            str(tmp_path / "original"),
            "--sent-dir",
            str(tmp_path / "sent"),
        ]
    )
    assert rc == 0
    assert "1 par(es)" in capsys.readouterr().out
