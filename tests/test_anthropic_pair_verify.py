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


# --- falsos positivos de contexto (#59) ---------------------------------------


def _ip(*parts: int) -> str:
    """Construye una cadena con forma de IPv4 sin escribirla literal."""
    return ".".join(str(p) for p in parts)


def _verify(original_text, sent_text, vault=None, rules=None):
    rules = rules or Rules()
    spans = pv.sensitive_spans(_record(_msg_payload(original_text)), vault or {}, rules)
    return pv.diff_leaks(spans, _record(_msg_payload(sent_text), variant="sent"))


def test_ip_kept_in_non_ip_context_is_not_a_leak():
    """La IP se seudonimizó; la misma cifra dentro de una versión queda intacta."""
    ip = _ip(1, 2, 3, 4)
    original = f"host {ip} y release {ip}.5 y cc_version={ip}"
    sent = f"host ip_deadbeef y release {ip}.5 y cc_version={ip}"
    assert _verify(original, sent) == []


def test_ip_still_in_ip_context_is_a_leak():
    ip = _ip(10, 20, 30, 40)
    leaks = _verify(f"host {ip}", f"host {ip}")
    assert [(s.value, s.category) for s in leaks] == [(ip, "ipv4")]


def test_escaped_newline_before_decorator_is_not_an_email():
    """En JSON serializado ``\\n@pytest.fixture`` parecería ``n@pytest.fixture``."""
    code = "import pytest\n@pytest.fixture\ndef f(): pass"
    rec = _record(_msg_payload(code))
    assert not [
        s for s in pv.sensitive_spans(rec, {}, Rules()) if s.category == "email"
    ]


def test_real_email_still_detected_and_leaks():
    email = "dev" + "@" + "corp.example"
    leaks = _verify(f"mail {email}\nfin", f"mail {email}\nfin")
    assert [(s.value, s.category) for s in leaks] == [(email, "email")]


def test_regex_layers_run_on_headers_too():
    ip = _ip(10, 1, 2, 3)
    rec = _record(_msg_payload("nada"), headers={"X-Forwarded-For": ip})
    assert ip in {s.value for s in pv.sensitive_spans(rec, {}, Rules())}


def test_stale_ip_vault_entry_is_not_a_leak():
    """Entrada antigua del vault que el regex actual ya no considera IP (#57)."""
    version = _ip(2, 1, 312, 625)
    text = f"cc_version={version}"
    assert _verify(text, text, vault={version: "ip_a1f04bd1"}) == []


def test_non_regex_vault_entry_still_checked_by_substring():
    text = "ruta secreto-largo aqui"
    leaks = _verify(text, text, vault={"secreto-largo": "proj_deadbeef"})
    assert [(s.value, s.category) for s in leaks] == [("secreto-largo", "vault")]


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


# --- rendimiento sin cambiar resultados (#73) ----------------------------------


def _reference_matches(record, regex):
    """Implementación de #59, sin prefiltro ni caché: la referencia."""
    leaves = []

    def walk(obj):
        if isinstance(obj, str):
            leaves.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk([record.get("payload"), record.get("headers")])
    return {m for leaf in leaves for m in regex.findall(leaf)}


def _history_records(n=6):
    """Peticiones de una sesión que reenvían el historial (hojas duplicadas)."""
    history = []
    records = []
    ip = ".".join(["10", "1", "2", "3"])
    for i in range(n):
        history.append({"role": "user", "content": f"turno {i} sin datos"})
        history.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": f"ruta {i}: dev{i}" + "@" + "corp.example",
                    },
                    {"type": "tool_use", "input": {"cmd": f"ping {ip}", "n": i}},
                    {
                        "type": "text",
                        "text": f"versión 1.2.3.4.{i} y cc_version=2.1.{i}.4",
                    },
                ],
            }
        )
        records.append(
            _record(
                {"messages": list(history), "system": [{"text": "a.b c@d"}]},
                headers={"X-Forwarded-For": ip, "Accept": "*/*"},
            )
        )
    return records


def test_layer_matches_equals_reference_on_repeated_history():
    from anthropic_payload_pseudonymize import _EMAIL_RE, _IPV4_RE

    pv._leaf_layer_matches.cache_clear()
    for rec in _history_records():
        got = pv.layer_matches(rec)
        assert got["email"] == _reference_matches(rec, _EMAIL_RE)
        assert got["ipv4"] == _reference_matches(rec, _IPV4_RE)
        assert pv.regex_matches(rec, _EMAIL_RE) == got["email"]
    # El historial repetido se resuelve desde la caché.
    assert pv._leaf_layer_matches.cache_info().hits > 0


def test_regex_matches_with_other_regex_still_works():
    import re

    rec = _record(_msg_payload("token-AB12 y token-CD34"))
    assert pv.regex_matches(rec, re.compile(r"token-\w+")) == {
        "token-AB12",
        "token-CD34",
    }


def test_string_leaves_visits_every_string():
    obj = {"a": ["x", {"b": "y", "c": [1, None, "z"]}], "d": "w"}
    assert sorted(pv._string_leaves(obj)) == ["w", "x", "y", "z"]


def test_verify_pair_results_unchanged_with_shared_serialization():
    """verify_pair reutiliza el payload serializado: mismas fugas y secretos."""
    rules = Rules(literals=["alice"])
    orig = _record(_msg_payload("alice en " + ".".join(["10", "9", "8", "7"])))
    sent = _record(_msg_payload("alice sigue"), variant="sent")
    spans = pv.sensitive_spans(orig, {}, rules)
    assert pv.diff_leaks(spans, sent) == pv.diff_leaks(
        spans, sent, pv._record_text(sent)
    )
    assert pv.secrets_in_sent(sent) == pv.secrets_in_sent(
        sent, pv._serialize(sent["payload"])
    )
    status = {r.name: r.level for r in pv.verify_pair(orig, sent, {}, rules)}
    assert status["Fugas en claro"] == "fail"


# --- capa pseudo_patterns (#42) ------------------------------------------------


def _pattern_rules():
    import anthropic_payload_pseudonymize as ps

    patterns, _ = ps.compile_patterns([ps.projects_root_pattern("/Users/u/proyectos")])
    return Rules(patterns=patterns)


def test_pattern_value_leaked_in_path_context_is_detected():
    rules = _pattern_rules()
    text = "cd /Users/u/proyectos/cliente-x/src"
    leaks = _verify(text, text, rules=rules)
    assert [(s.value, s.category) for s in leaks] == [("cliente-x", "pattern")]


def test_pattern_value_outside_path_context_is_not_a_leak():
    """El nombre sigue en otro contexto (no ruta): el seudonimizador no lo toca."""
    rules = _pattern_rules()
    original = "cd /Users/u/proyectos/cliente-x/src; el informe de cliente-x"
    sent = "cd /Users/u/proyectos/dir_deadbeef/src; el informe de cliente-x"
    assert _verify(original, sent, rules=rules) == []


def test_pattern_vault_entries_are_left_to_pattern_layer():
    rules = _pattern_rules()
    text = "carpeta docs-web aparte"
    assert _verify(text, text, vault={"docs-web": "dir_12345678"}, rules=rules) == []


def test_ignored_pattern_values_are_not_leaks():
    """Marcadores y pseudo_pattern_ignore: el seudonimizador no los toca (#92)."""
    import anthropic_payload_pseudonymize as ps

    rules = Rules(patterns=[(ps._USER_DIR_RE, "user")], pattern_ignore=["run" + "ner"])
    text = "cd /home/" + "run" + "ner/work; ls /Users/{name}/x"
    assert _verify(text, text, rules=rules) == []
    leaked = "cd /home/ana.lopez/work"
    assert [s.value for s in _verify(leaked, leaked, rules=rules)] == ["ana.lopez"]


# --- #93: nombres de carpeta como palabra -------------------------------------


def _dir_word_rules():
    rules = _pattern_rules()
    rules.dir_words = True
    return rules


def test_dir_name_left_outside_path_is_a_leak_with_dir_words():
    rules = _dir_word_rules()
    original = "cd /Users/u/proyectos/cliente-x/src; el informe de cliente-x"
    sent = "cd /Users/u/proyectos/dir_deadbeef/src; el informe de cliente-x"
    leaks = _verify(original, sent, rules=rules)
    assert [(s.value, s.category) for s in leaks] == [("cliente-x", "dir")]


def test_vault_dir_name_without_path_in_record_is_checked():
    rules = _dir_word_rules()
    vault = {"cliente-x": "dir_12345678"}
    text = "```\ncliente-x/\n├── README.md\n```"
    assert [s.value for s in _verify(text, text, vault=vault, rules=rules)] == [
        "cliente-x"
    ]
    sent = "```\ndir_12345678/\n├── README.md\n```"
    assert _verify(text, sent, vault=vault, rules=rules) == []


def test_generic_dir_names_are_not_word_leaks():
    rules = _dir_word_rules()
    vault = {"scripts": "dir_12345678", "docs": "dir_87654321"}
    text = "ver scripts y docs"
    assert _verify(text, text, vault=vault, rules=rules) == []
