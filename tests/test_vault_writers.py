"""Los escritores del vault usan el único vault válido (issue #242).

Trabaja con HOME temporal: nunca toca ~/.klaus-proxy real.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
VALID_RELATIVE = Path(".klaus-proxy") / "captures" / ".pseudonym_vault.json"


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ANTHROPIC_PSEUDO_VAULT", raising=False)
    return home


def test_vault_save_default_path_is_the_valid_vault(fake_home):
    import anthropic_payload_pseudonymize as ps

    vault = ps.Vault()
    vault._register("valor-de-prueba", "secret_prueba")
    path = vault.save()
    assert path == fake_home / VALID_RELATIVE
    assert path.exists()


def test_load_default_reads_the_valid_vault(fake_home):
    import anthropic_payload_pseudonymize as ps

    vault = ps.Vault()
    vault._register("valor-de-prueba", "secret_prueba")
    vault.save()
    assert ps.Vault.load().real_to_pseudo == {"valor-de-prueba": "secret_prueba"}


def test_env_override_is_the_only_way_to_redirect(fake_home, monkeypatch):
    # Documenta el riesgo: la variable es la única forma de cambiar la ruta.
    import anthropic_payload_pseudonymize as ps

    other = fake_home / "otro.json"
    monkeypatch.setenv("ANTHROPIC_PSEUDO_VAULT", str(other))
    assert ps.vault_path() == other


def test_no_writer_uses_a_literal_vault_json_path():
    """Ningún fichero de código usa el nombre antiguo `.vault.json`."""
    offenders = []
    for base in ("src", "scripts"):
        for path in (ROOT / base).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if ".vault.json" in text.replace(".pseudonym_vault.json", ""):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def _dashboard():
    spec = importlib.util.spec_from_file_location(
        "gad_vault", ROOT / "scripts" / "generate_audit_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _efdef_check(tmp_path, env_line: str | None):
    gad = _dashboard()
    project = tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    (project / "README.md").write_text("# R\n", encoding="utf-8")
    (project / "CLAUDE.md").write_text("", encoding="utf-8")
    cfg = tmp_path / "klaus"
    cfg.mkdir()
    if env_line is not None:
        (cfg / "klaus-env.sh").write_text(env_line + "\n", encoding="utf-8")
    result = gad.audit_efdef(project, cfg)
    return next(c for c in result["checks"] if c["label"] == "ANTHROPIC_PSEUDO_VAULT")


def test_efdef_flags_env_file_redirect(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_PSEUDO_VAULT", raising=False)
    check = _efdef_check(tmp_path, 'export ANTHROPIC_PSEUDO_VAULT="/tmp/x.json"')
    assert check["passed"] is False


def test_efdef_passes_without_redirect(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_PSEUDO_VAULT", raising=False)
    check = _efdef_check(tmp_path, 'export HTTPS_PROXY="http://127.0.0.1:8899"')
    assert check["passed"] is True
