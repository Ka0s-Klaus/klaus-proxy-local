"""Hosts de solo captura: se auditan sin seudonimizar (#125)."""

import argparse
import json
from datetime import datetime
from types import SimpleNamespace

import anthropic_pair_verify as pv
import anthropic_payload_capture as cap
import anthropic_payload_pseudonymize as ps
from Klaus_proxy_local.audit_all_payloads import PayloadAuditor
from Klaus_proxy_local.fix_pseudonymization import PseudonymizationDiagnostic

MCP = "mcp-proxy.anthropic.com"


def _config(path, **data):
    path.write_text(json.dumps(data), encoding="utf-8")


class FakeRequest:
    def __init__(self, host, path, text):
        self.pretty_host = host
        self.path = path
        self.text = text
        self.method = "POST"
        self.pretty_url = f"https://{host}{path}"

    def get_text(self, strict=False):
        return self.text

    def set_text(self, text):
        self.text = text


def test_hosts_from_config(_isolated_config_json):
    _config(_isolated_config_json, capture_only_hosts=[MCP.upper(), " "])
    assert ps.capture_only_hosts() == (MCP,)
    assert ps.is_capture_only_host(MCP)
    assert cap.is_captured_host(MCP)
    assert not cap.is_anthropic_host(MCP)
    assert not cap.is_captured_host("other.example")


def test_broken_config_has_no_capture_only_hosts(_isolated_config_json):
    _isolated_config_json.write_text("{no json")
    assert ps.capture_only_hosts() == ()
    assert cap.capture_only_hosts() == ()


def test_request_leaves_body_untouched_and_redacts_capture(
    _isolated_config_json, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_HOSTS", "api.anthropic.com")
    _config(_isolated_config_json, capture_only_hosts=[MCP])
    secret = "ghp_" + "a" * 36
    body = json.dumps({"q": "busca cliente-x", "token": secret})
    req = FakeRequest(MCP, "/v1/mcp/srv_1", body)
    flow = SimpleNamespace(request=req, metadata={})
    ps.AnthropicPseudonymizer(vault=ps.Vault(), rules=ps.build_rules()).request(flow)
    assert req.text == body  # sale tal cual
    assert flow.metadata["klaus_capture_only"] is True
    original = flow.metadata["anthropic_original_body"]
    assert "cliente-x" in original and secret not in original


def test_llm_path_on_capture_only_host_is_still_pseudonymized(
    _isolated_config_json, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_HOSTS", "api.anthropic.com")
    _config(_isolated_config_json, capture_only_hosts=[MCP])
    req = FakeRequest(MCP, "/v1/messages", json.dumps({"m": "hola"}))
    flow = SimpleNamespace(request=req, metadata={})
    ps.AnthropicPseudonymizer(vault=ps.Vault(), rules=ps.build_rules()).request(flow)
    assert "klaus_capture_only" not in flow.metadata
    assert flow.metadata.get("anthropic_pseudo_ran") is True


def test_record_marks_capture_only():
    rec = cap.build_record(
        method="POST",
        url=f"https://{MCP}/v1/mcp/x",
        host=MCP,
        path="/v1/mcp/x",
        headers={},
        body="{}",
        captured_at=datetime(2026, 10, 29),
        capture_only=True,
    )
    assert rec["capture_only"] is True
    assert (
        cap.build_record(
            method="GET",
            url="u",
            host="h",
            path="/",
            headers={},
            body=None,
            captured_at=datetime(2026, 10, 29),
        )["capture_only"]
        is False
    )


def _write_pair(captures, name, record):
    for variant in ("original", "sent"):
        d = captures / variant
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps({**record, "variant": variant}))


def test_tools_skip_capture_only(tmp_path):
    captures = tmp_path / "captures"
    _write_pair(
        captures,
        "20261029_100000_anthropic_payload.json",
        {"host": MCP, "method": "POST", "capture_only": True, "pseudo_ran": False},
    )
    _write_pair(
        captures,
        "20261029_100001_anthropic_payload.json",
        {"host": "api.anthropic.com", "method": "POST", "pseudo_ran": True},
    )
    args = argparse.Namespace(
        original_dir=str(captures / "original"),
        sent_dir=str(captures / "sent"),
        name=None,
    )
    pairs, _ = pv._resolve_targets(args)
    assert [p[0] for p in pairs] == ["20261029_100001_anthropic_payload.json"]

    auditor = PayloadAuditor(captures)
    assert auditor.load_payloads() == (1, 1)

    diag = PseudonymizationDiagnostic(captures)
    assert diag.load_payloads() == 1
    assert diag.non_pseudonymized == []
