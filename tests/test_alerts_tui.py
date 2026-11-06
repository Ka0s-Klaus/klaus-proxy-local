"""klaus-alerts: lectura de avisos, estado, acciones y recuperación del valor (#189)."""

import json
from datetime import datetime

import pytest

from Klaus_proxy_local import alerts_tui as at
from Klaus_proxy_local import sentinel as sn
from Klaus_proxy_local.scan import safe_id
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

WHEN = datetime(2026, 11, 6, 12, 0, 0)
VALUE = "ana@acme-internal.io"  # detectado como corporate-domain (ver test_sentinel)
SESSION = "/p|2026-11-06"


@pytest.fixture(scope="module")
def scanner():
    return SensitiveDataScanner(enable_business=False)


def _alert(
    session=SESSION,
    sid="⟨corporate-domain·a1b2c3d4·11c⟩",
    ts="2026-11-06T12:00:00",
    cat="corporate-domain",
):
    return {
        "ts": ts,
        "session": session,
        "category": cat,
        "id": sid,
        "confidence": "MEDIUM",
    }


def _write_lines(path, records):
    with path.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# --- AlertFeed ---------------------------------------------------------------


def test_feed_reads_only_new_complete_lines(tmp_path):
    path = tmp_path / "alerts.jsonl"
    _write_lines(path, [_alert(sid="⟨x·1·1c⟩")])
    feed = at.AlertFeed(path)
    assert len(feed.poll()) == 1
    assert feed.poll() == []  # nada nuevo
    _write_lines(path, [_alert(sid="⟨x·2·1c⟩")])
    assert [r["id"] for r in feed.poll()] == ["⟨x·2·1c⟩"]


def test_feed_waits_for_partial_line_and_skips_garbage(tmp_path):
    path = tmp_path / "alerts.jsonl"
    path.write_text('{"id": "⟨x·1·1c⟩"', encoding="utf-8")  # línea a medias
    feed = at.AlertFeed(path)
    assert feed.poll() == []
    with path.open("a", encoding="utf-8") as fh:
        fh.write("}\nno es json\n")
    assert [r["id"] for r in feed.poll()] == ["⟨x·1·1c⟩"]


def test_feed_restarts_after_truncation(tmp_path):
    path = tmp_path / "alerts.jsonl"
    _write_lines(path, [_alert(sid="⟨a·1·1c⟩"), _alert(sid="⟨a·2·1c⟩")])
    feed = at.AlertFeed(path)
    assert len(feed.poll()) == 2
    path.write_text("", encoding="utf-8")
    _write_lines(path, [_alert(sid="⟨b·1·1c⟩")])
    assert [r["id"] for r in feed.poll()] == ["⟨b·1·1c⟩"]


def test_feed_missing_file_is_empty(tmp_path):
    assert at.AlertFeed(tmp_path / "no.jsonl").poll() == []


# --- Estado: agrupación y ocultación ------------------------------------------


def test_state_groups_by_session_and_dedupes_values():
    st = at.State()
    st.feed(
        [
            _alert(sid="⟨a·1·1c⟩", ts="2026-11-06T10:00:00"),
            _alert(
                sid="⟨a·1·1c⟩", ts="2026-11-06T10:05:00"
            ),  # mismo valor, misma sesión
            _alert(sid="⟨a·2·1c⟩", ts="2026-11-06T10:06:00"),
            _alert(session="/q|2026-11-06", sid="⟨a·3·1c⟩", ts="2026-11-06T11:00:00"),
        ]
    )
    sessions = st.sessions()
    assert [s.label for s in sessions] == ["q", "p"]  # la más reciente primero
    assert len(sessions[1].alerts) == 2


def test_resolved_and_ignored_items_are_hidden():
    st = at.State()
    st.feed(
        [
            _alert(sid="⟨a·1·1c⟩"),
            _alert(sid="⟨a·2·1c⟩"),
            _alert(session="/q|2026-11-06", sid="⟨a·3·1c⟩"),
            {
                "action": "approve",
                "session": SESSION,
                "id": "⟨a·1·1c⟩",
                "category": "corporate-domain",
            },
            {
                "action": "ignore_session",
                "session": "/q|2026-11-06",
                "id": "",
                "category": "",
            },
        ]
    )
    sessions = st.sessions()
    assert [s.key for s in sessions] == [SESSION]
    assert [a["id"] for a in sessions[0].alerts] == ["⟨a·2·1c⟩"]


def test_silenced_category_is_hidden():
    st = at.State()
    st.feed(
        [
            _alert(sid="⟨a·1·1c⟩", cat="corporate-domain"),
            _alert(sid="⟨b·1·1c⟩", cat="api-key"),
            {
                "action": "silence_category",
                "session": "",
                "id": "",
                "category": "corporate-domain",
            },
        ]
    )
    ids = [a["id"] for s in st.sessions() for a in s.alerts]
    assert ids == ["⟨b·1·1c⟩"]


# --- Acciones: rastro sin valores ---------------------------------------------


def test_record_action_writes_identifier_only(tmp_path):
    sink = sn.AlertSink(tmp_path / "alerts.jsonl")
    at.record_action(sink, "approve", _alert())
    line = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    rec = json.loads(line)
    assert rec["action"] == "approve"
    assert rec["id"].startswith("⟨corporate-domain·")
    assert VALUE not in line


# --- Recuperación del valor desde la captura -----------------------------------


def _detected(scanner):
    """Valor que el detector saca de VALUE (lo que el centinela identificaría)."""
    found = [
        f
        for f in sn.detect(f"contacto: {VALUE}", scanner)
        if f.category == "corporate-domain"
    ]
    assert found, "el detector debe encontrar el valor de prueba"
    return found[0].value


def _capture(dirpath, name, text):
    dirpath.mkdir(parents=True, exist_ok=True)
    payload = {
        "system": "Primary working directory: /p\n",
        "messages": [{"role": "user", "content": text}],
    }
    (dirpath / name).write_text(
        json.dumps(
            {
                "path": "/v1/messages",
                "captured_at": "2026-11-06T12:00:00",
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )


def test_recover_value_matches_identifier_in_capture(tmp_path, scanner):
    originals = tmp_path / "original"
    _capture(originals, "20261106_120000_anthropic_payload.json", f"contacto: {VALUE}")
    value = _detected(scanner)
    alert = _alert(sid=safe_id(value, "corporate-domain"))
    got = at.recover_value(alert, scanner, originals)
    assert got is not None
    assert got[0] == value


def test_recover_value_ignores_other_sessions_and_far_captures(tmp_path, scanner):
    originals = tmp_path / "original"
    _capture(originals, "20261106_120000_anthropic_payload.json", f"contacto: {VALUE}")
    sid = safe_id(_detected(scanner), "corporate-domain")
    other = _alert(session="/otro|2026-11-06", sid=sid)
    far = _alert(sid=sid, ts="2026-11-06T15:00:00")
    assert at.recover_value(other, scanner, originals) is None
    assert at.recover_value(far, scanner, originals) is None


def test_recover_value_none_without_captures(tmp_path, scanner):
    assert at.recover_value(_alert(), scanner, tmp_path / "vacio") is None


# --- Configuración: falso positivo y silenciar --------------------------------


def test_config_helpers_write_lists_without_duplicates(tmp_path):
    import anthropic_payload_pseudonymize as ps

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"pseudo_pattern_ignore": ["x"]}), encoding="utf-8")
    ps.add_to_config_list("pseudo_pattern_ignore", [VALUE, VALUE], cfg)
    ps.add_to_config_list("sentinel_silenced_categories", ["corporate-domain"], cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["pseudo_pattern_ignore"] == ["x", VALUE]
    assert data["sentinel_silenced_categories"] == ["corporate-domain"]


# --- Centinela: categorías silenciadas ----------------------------------------


def test_sentinel_skips_silenced_categories(scanner):
    sink = type(
        "S", (), {"records": [], "write": lambda self, r: self.records.append(r)}
    )()
    s = sn.Sentinel(
        sink=sink,
        notify=False,
        scanner=scanner,
        silenced=lambda: ["corporate-domain"],
    )
    try:
        out = s.process(f"contacto: {VALUE}", SESSION, lambda v: False, WHEN)
    finally:
        s.stop()
    assert out == []


# --- Pintado: nunca muestra el valor -------------------------------------------


def test_render_never_shows_value_only_identifiers():
    st = at.State()
    st.feed([_alert()])
    sessions = st.sessions()
    text = "\n".join(
        at.render_sessions(sessions, 100) + at.render_session(sessions[0], 100)
    )
    assert "⟨corporate-domain·a1b2c3d4·11c⟩" in text
    assert VALUE not in text


def test_render_empty_state_message():
    assert "Sin avisos" in at.render_sessions([], 80)[0]


def test_main_refuses_without_terminal(monkeypatch, capsys):
    monkeypatch.setattr(at.sys.stdin, "isatty", lambda: False, raising=False)
    assert at.main([]) == 2
    assert "terminal interactiva" in capsys.readouterr().err
