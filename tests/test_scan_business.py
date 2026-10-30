"""klaus-scan: nombres de negocio y salida segura (#140)."""

import json
import subprocess

import pytest

from Klaus_proxy_local import business_names as bn
from Klaus_proxy_local import scan
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

CLIENT = "Cliente Ficticio S.L."


def _values(line):
    return {(v, c) for v, c, _conf, _r in bn.detect_line(line)}


# --- detect_line ------------------------------------------------------------------


@pytest.mark.parametrize(
    "line,value",
    [
        (f"Contrato con {CLIENT} para 2026", CLIENT),
        ("Proveedor: Northwind Traders GmbH.", "Northwind Traders GmbH"),
        ("by Contoso Inc. and others", "Contoso Inc."),
        ("Fabrikam Holdings Ltd, London", "Fabrikam Holdings Ltd"),
    ],
)
def test_legal_names(line, value):
    assert (value, "business-name") in _values(line)


def test_legal_name_needs_suffix_word():
    assert not [c for _v, c in _values("class MyCorp: pass") if c == "business-name"]
    assert not _values("import AG from 'x'")


@pytest.mark.parametrize(
    "line,holder",
    [
        ("# Copyright (c) 2024 Tailspin Toys", "Tailspin Toys"),
        ("© 2021-2026 Wingtip Partners. All rights reserved.", "Wingtip Partners"),
        ("Copyright 2023, Adventure Works <legal@x>", "Adventure Works"),
    ],
)
def test_copyright_holder(line, holder):
    assert (holder, "business-name") in _values(line)


def test_copyright_generic_holders_ignored():
    assert not _values("Copyright (c) 2020 The Project Contributors")
    assert not _values("Copyright notice and permission")  # sin año


def test_email_and_url_domains():
    v = _values("ventas@fabrikam-legal.es https://intranet.fabrikam-legal.es/x")
    assert v == {("fabrikam-legal.es", "corporate-domain")}
    # example.* son marcadores de posición
    assert not _values("https://api.cliente-ficticio.example.es/v1")


def test_public_domains_ignored():
    line = (
        "git@github.com:x/y https://pypi.org/p user@gmail.com "
        "https://docs.example.com https://x.test config.json"
    )
    assert not _values(line)


def test_saas_tenant_and_cctld():
    assert bn.domain_value("wingtip.atlassian.net") == "wingtip.atlassian.net"
    assert bn.domain_value("api.eu.tailspin.co.uk") == "tailspin.co.uk"
    assert bn.domain_value("127.0.0.1") is None


def test_cloud_ids():
    v = _values('project_id = "tailspin-prod-42"')
    assert ("tailspin-prod-42", "cloud-project") in v
    v = _values("arn:aws:iam::210987654321:role/x")
    assert ("210987654321", "cloud-project") in v
    assert not [c for _v, c in _values('project_id: "my-project-id"')]
    assert not [c for _v, c in _values("--project your-project")]


def test_issue_keys_need_three():
    hits = [
        bn.RawHit(v, c, conf, "f", 1, r)
        for line in ("PRJ-1 y ISO-9001", "ver PRJ-22", "PRJ-333 cierra", "OTRO-1")
        for v, c, conf, r in bn.detect_line(line)
    ]
    kept, counts, _ = bn.aggregate(hits, lambda v: False)
    keys = {h.value for h in kept if h.category == "issue-key"}
    assert keys == {"PRJ"}
    assert counts[("PRJ", "issue-key")] == 3


# --- manifiestos -----------------------------------------------------------------


def test_manifests(tmp_path):
    pkg = json.dumps({"name": "@tailspin/web", "author": "Ana Ruiz <a@x.es>"})
    assert bn.detect_manifest(tmp_path / "package.json", pkg) == [
        ("tailspin", "Scope de npm"),
        ("Ana Ruiz", "Autor en package.json"),
    ]
    comp = json.dumps({"name": "wingtip/api", "authors": [{"name": "Luis Gil"}]})
    assert [v for v, _ in bn.detect_manifest(tmp_path / "composer.json", comp)] == [
        "wingtip",
        "Luis Gil",
    ]
    gomod = "module github.com/fabrikam/payments\n\ngo 1.22\n"
    assert bn.detect_manifest(tmp_path / "go.mod", gomod) == [("fabrikam", "Módulo Go")]
    pom = (
        "<project><parent><groupId>org.springframework.boot</groupId></parent>"
        "<groupId>com.contoso.billing</groupId></project>"
    )
    assert bn.detect_manifest(tmp_path / "pom.xml", pom) == [
        ("contoso", "groupId de Maven")
    ]
    pyproject = '[project]\nauthors = [{ name = "Eva Sanz", email = "e@x.es" }]\n'
    assert bn.detect_manifest(tmp_path / "pyproject.toml", pyproject) == [
        ("Eva Sanz", "Autor en pyproject")
    ]
    assert bn.detect_manifest(tmp_path / "package.json", "{roto") == []


# --- escáner completo -------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proyecto-tailspin"
    (root / "docs" / "tailspin-toys").mkdir(parents=True)
    (root / "LICENSE").write_text("Copyright (c) 2025 Tailspin Toys\n")
    (root / "docs" / "tailspin-toys" / "contrato.md").write_text(
        f"Firmado con {CLIENT}.\nSoporte: ana@fabrikam-legal.es\n"
        "Ver PRJ-1, PRJ-2 y PRJ-3.\n"
    )
    (root / "package.json").write_text(json.dumps({"name": "@wingtip/app"}))
    (root / "config.py").write_text('API = "sk-ant-' + "a" * 30 + '"\n')
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    env = {
        "GIT_AUTHOR_NAME": "Dev",
        "GIT_AUTHOR_EMAIL": "dev@northwind-corp.es",
        "GIT_COMMITTER_NAME": "Dev",
        "GIT_COMMITTER_EMAIL": "dev@northwind-corp.es",
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", "x"],
        check=True,
        env=env,
    )
    return root


def _scan(root):
    return SensitiveDataScanner(enable_business=True).scan_directory(root)


def test_scanner_aggregates_business(project, _isolated_config_json):
    _isolated_config_json.write_text(
        json.dumps({"salt": "x", "pseudo_word_literals": ["wingtip"]})
    )
    res = _scan(project)
    by = {(f.value, f.category): f for f in res.findings}
    assert by[("Tailspin Toys", "business-name")].confidence.name == "HIGH"
    assert (CLIENT, "business-name") in by
    assert ("fabrikam-legal.es", "corporate-domain") in by
    assert ("northwind-corp.es", "corporate-domain") in by
    assert by[("PRJ", "issue-key")].occurrences == 3
    assert ("wingtip", "package-name") not in by  # ya protegido
    assert res.already_protected == 1
    assert any(f.category != "issue-key" and "sk-ant" in f.value for f in res.findings)


def test_business_disabled_by_default_in_class(project):
    res = SensitiveDataScanner().scan_directory(project)
    assert not [f for f in res.findings if f.category in bn.BUSINESS_CATEGORIES]


# --- salida segura -----------------------------------------------------------------

SECRETS = (CLIENT, "Tailspin", "fabrikam", "northwind", "wingtip", "sk-ant", "PRJ")


def _run(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        scan.main(argv)
    assert exc.value.code == 0
    out = capsys.readouterr()
    return out.out, out.err


def test_default_output_reveals_nothing(project, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    out, _err = _run([str(project), "--min-confidence", "LOW"], capsys)
    assert "Findings to Review" in out
    assert "review skipped" in out  # sin TTY no se pregunta (EOFError)
    body = out.split("Scanning:", 1)[1].split("\n", 1)[1]
    for s in SECRETS:
        assert s.lower() not in body.lower(), s
    assert "⟨business-name·" in body
    assert "⟨dir·" in body  # docs/tailspin-toys enmascarado


def test_json_reveals_nothing(project, capsys):
    out, _err = _run([str(project), "--json", "--min-confidence", "LOW"], capsys)
    data = json.loads(out)
    assert data["revealed"] is False and data["findings"]
    text = json.dumps(data, ensure_ascii=False)
    for s in SECRETS:
        assert s.lower() not in text.lower(), s
    assert all("value" not in f and "context" not in f for f in data["findings"])


def test_counts_only(project, capsys):
    out, _err = _run([str(project), "--counts", "--min-confidence", "LOW"], capsys)
    assert "business-name" in out and "corporate-domain" in out
    for s in SECRETS:
        assert s.lower() not in out.lower(), s


def test_reveal_shows_values(project, capsys):
    out, _err = _run([str(project), "--json", "--reveal"], capsys)
    data = json.loads(out)
    assert data["revealed"] is True
    assert CLIENT in {f.get("value") for f in data["findings"]}


def test_safe_id_is_stable_and_opaque(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_SALT", "s1")
    a = scan.safe_id(CLIENT, "business-name")
    assert a == scan.safe_id(CLIENT, "business-name")
    assert a.endswith(f"·{len(CLIENT)}c⟩") and "Cliente" not in a
    monkeypatch.setenv("ANTHROPIC_PSEUDO_SALT", "s2")
    assert scan.safe_id(CLIENT, "business-name") != a


def test_business_prefix():
    assert scan._get_prefix_for_category("corporate-domain") == "org"


# --- aprobar sin ANTHROPIC_PSEUDO_SALT en el entorno (#156) -------------------------


def test_approve_without_env_salt(monkeypatch, _isolated_config_json, tmp_path):
    import anthropic_payload_pseudonymize as ps
    from Klaus_proxy_local.sensitive_data_scanner import (
        Confidence,
        SensitiveDataFinding,
        VaultIntegration,
    )

    monkeypatch.delenv("ANTHROPIC_PSEUDO_SALT", raising=False)
    monkeypatch.setenv("ANTHROPIC_PSEUDO_VAULT", str(tmp_path / "vault.json"))
    monkeypatch.setattr(ps, "vault_path", lambda: tmp_path / "vault.json")
    _isolated_config_json.write_text('{"salt": "salt-de-config"}')
    finding = SensitiveDataFinding(
        CLIENT, "business-name", "business", Confidence.HIGH, tmp_path, 1, "", ""
    )
    pseudo = VaultIntegration().add_finding_to_vault(finding, "org")
    cfg = json.loads(_isolated_config_json.read_text())
    assert CLIENT in cfg["pseudo_literals"]
    # El mismo seudónimo que daría claude-proxy con la SALT de config.json
    monkeypatch.setenv("ANTHROPIC_PSEUDO_SALT", "salt-de-config")
    assert pseudo == ps.Vault().map(CLIENT, "org")


def test_rule_added_even_if_vault_fails(monkeypatch, _isolated_config_json, tmp_path):
    from Klaus_proxy_local.sensitive_data_scanner import (
        Confidence,
        SensitiveDataFinding,
        VaultIntegration,
    )

    vi = VaultIntegration()

    def broken_vault():
        raise RuntimeError("vault roto")

    monkeypatch.setattr(vi, "get_vault", broken_vault)
    finding = SensitiveDataFinding(
        "wingtip-legal.es",
        "corporate-domain",
        "business",
        Confidence.HIGH,
        tmp_path,
        1,
        "",
        "",
    )
    with pytest.raises(RuntimeError):
        vi.add_finding_to_vault(finding, "org")
    cfg = json.loads(_isolated_config_json.read_text())
    assert "wingtip-legal.es" in cfg["pseudo_word_literals"]
