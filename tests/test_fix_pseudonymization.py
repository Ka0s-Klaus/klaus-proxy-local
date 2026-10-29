"""Tests for host matching in fix_pseudonymization recommendations (#45)."""

from Klaus_proxy_local.fix_pseudonymization import PseudonymizationDiagnostic

CONFIG_OK = {"pseudonymization_enabled": True, "salt_set": True, "patterns_count": 1}
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
