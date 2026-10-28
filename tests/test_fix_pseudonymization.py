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
