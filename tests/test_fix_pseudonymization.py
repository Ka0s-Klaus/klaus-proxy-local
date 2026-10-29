"""Tests for host matching in fix_pseudonymization recommendations (#45)."""

from Klaus_proxy_local.fix_pseudonymization import PseudonymizationDiagnostic

CONFIG_OK = {"exists": True, "enabled": True, "salt_set": True, "rules_count": 1}
WARNING = "Internal/Third-party services NOT pseudonymized"


def _recommendations(hosts):
    diag = PseudonymizationDiagnostic()
    analysis = {"by_host": {host: 1 for host in hosts}}
    return diag._get_recommendations(CONFIG_OK, analysis, total=len(hosts))


class TestHostMatching:
    def test_anthropic_api_host_matches(self):
        assert WARNING in _recommendations(["api.anthropic.com"])

    def test_corporate_gateway_matches(self):
        assert WARNING in _recommendations(["llm.tools.cloud.customer1.es"])

    def test_gateway_matches_in_any_position(self):
        assert WARNING in _recommendations(
            ["logs.example.com", "llm.tools.cloud.customer1.es"]
        )

    def test_lookalike_hosts_do_not_match(self):
        out = _recommendations(
            ["api.anthropic.com.attacker.io", "evil-llm.tools.example.com"]
        )
        assert WARNING not in out

    def test_no_hosts(self):
        assert WARNING not in _recommendations([])


def test_show_config_never_prints_salt(tmp_path):
    """--show-config puede acabar en el contexto de un agente (#106)."""
    import json

    salt = "0123456789abcdef" * 2
    diag = PseudonymizationDiagnostic(captures_dir=tmp_path / "captures")
    diag.config_file = tmp_path / "config.json"
    diag.config_file.write_text(json.dumps({"salt": salt, "hosts": ["h"]}))
    out = diag.show_config_file()
    assert salt not in out and salt[:8] not in out
    assert "«oculta, 32 caracteres»" in out and '"hosts"' in out
    # No modifica el fichero
    assert json.loads(diag.config_file.read_text())["salt"] == salt


def test_check_config_reads_real_keys(tmp_path, monkeypatch):
    """Claves que usa el proxy, no las inventadas de antes (#110)."""
    import json

    monkeypatch.delenv("ANTHROPIC_PSEUDO_ENABLE", raising=False)
    diag = PseudonymizationDiagnostic(captures_dir=tmp_path / "captures")
    diag.config_file = tmp_path / "config.json"
    diag.config_file.write_text(
        json.dumps(
            {
                "salt": "x" * 32,
                "hosts": ["api.anthropic.com"],
                "pseudo_word_literals": ["cliente-x", "acme"],
                "pseudo_patterns": [{"pattern": "p", "replacement_prefix": "dir"}],
            }
        )
    )
    cfg = diag.check_config()
    assert (cfg["enabled"], cfg["salt_set"], cfg["rules_count"]) == (True, True, 3)
    recs = diag._get_recommendations(cfg, {"by_host": {}}, total=0)
    assert "❌" not in recs and "No custom rules" not in recs
    assert "python -m" not in recs and "'patterns'" not in recs


def test_recommendations_flag_disabled_and_missing_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_ENABLE", "0")
    diag = PseudonymizationDiagnostic(captures_dir=tmp_path / "captures")
    diag.config_file = tmp_path / "missing.json"
    recs = diag._get_recommendations(diag.check_config(), {"by_host": {}}, total=0)
    assert "config.json or its SALT is missing" in recs
    assert "ANTHROPIC_PSEUDO_ENABLE=0" in recs
    assert "./install.sh" in recs


def test_load_payloads_uses_pseudo_ran(tmp_path):
    """Procesada sin cambios no es «no pseudonimizada»; GET no tiene cuerpo (#110)."""
    import json

    sent = tmp_path / "captures" / "sent"
    sent.mkdir(parents=True)
    rows = {
        "a.json": {"method": "POST", "pseudonymized": True, "pseudo_ran": True},
        "b.json": {"method": "POST", "pseudonymized": False, "pseudo_ran": True},
        "c.json": {"method": "GET", "pseudonymized": False, "pseudo_ran": False},
        "d.json": {"method": "POST", "pseudonymized": False, "pseudo_ran": False},
    }
    for name, row in rows.items():
        (sent / name).write_text(json.dumps(row))
    diag = PseudonymizationDiagnostic(captures_dir=tmp_path / "captures")
    assert diag.load_payloads() == 4
    assert [p["file"] for p in diag.non_pseudonymized] == ["d.json"]
    assert len(diag.pseudonymized) == 2 and len(diag.no_body) == 1
