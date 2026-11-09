"""Tests de la sección EFDEF del dashboard de auditoría (issue #238).

Se trabaja sobre árboles temporales: no se lee el ~/.klaus-proxy real.
"""

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
VALID = Path("captures") / ".pseudonym_vault.json"


def _dashboard():
    spec = importlib.util.spec_from_file_location(
        "gad_efdef", ROOT / "scripts" / "generate_audit_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLAUDE_OK = """# Proyecto

## Repositorio & GitHub
- **Organización:** https://github.com/org
- **Repositorio:** https://github.com/org/repo
- **Usuario GitHub:** usuario
- **GitHub Project (Kanban):** Proyecto #25 de la organización org

## Flujo de trabajo obligatorio
1. **Issue** — crear.
2. **Rama** — crear.
3. **Desarrollo** — commits.
4. **Documentación en la issue** — actualizar.
5. **Pull Request** — abrir.

## Trazabilidad
- nada
"""


def _project(
    root: Path, claude: str = CLAUDE_OK, readme: str = "# R\n\n## 📚 Documentación\n"
) -> Path:
    project = root / "project"
    for sub in ("architecture", "guides", "reports", "decisions"):
        (project / "docs" / sub).mkdir(parents=True)
    (project / "docs" / "trazabilidad.md").write_text("# spec\n", encoding="utf-8")
    (project / "docs" / "guide.md").write_text("# g\n", encoding="utf-8")
    (project / "CLAUDE.md").write_text(claude, encoding="utf-8")
    (project / "README.md").write_text(readme, encoding="utf-8")
    return project


def _config(root: Path, vault_path: str | None = None, mode: int = 0o600) -> Path:
    cfg_dir = root / "klaus"
    (cfg_dir / "captures").mkdir(parents=True)
    (cfg_dir / "logs" / "trazas").mkdir(parents=True)
    (cfg_dir / "klaus-env.sh").write_text("", encoding="utf-8")
    vault = cfg_dir / VALID
    vault.write_text(json.dumps({"a": "b"}), encoding="utf-8")
    cfg = {
        "salt": "x" * 32,
        "pseudo_literals": [],
        "pseudo_word_literals": [],
        "vault_path": str(vault) if vault_path is None else vault_path,
    }
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")
    os.chmod(cfg_file, mode)
    os.chmod(cfg_dir / "logs" / "trazas", 0o700)
    return cfg_dir


def _check(result, label):
    return next(c for c in result["checks"] if c["label"] == label)


def test_all_good_passes_vault_and_permissions(tmp_path):
    gad = _dashboard()
    project = _project(tmp_path)
    cfg = _config(tmp_path)
    result = gad.audit_efdef(project, cfg)
    assert _check(result, "Vault existe")["passed"]
    assert _check(result, "vault_path en config")["passed"]
    assert _check(result, "config.json privado")["passed"]
    assert _check(result, "Trazas privadas")["passed"]
    assert _check(result, "Especificación de trazas")["passed"]


def test_config_pointing_to_wrong_vault_fails(tmp_path):
    gad = _dashboard()
    project = _project(tmp_path)
    cfg = _config(
        tmp_path, vault_path=str(tmp_path / "klaus" / "captures" / ".vault.json")
    )
    result = gad.audit_efdef(project, cfg)
    check = _check(result, "vault_path en config")
    assert check["passed"] is False
    assert ".vault.json" in check["detail"]
    # El vault válido existe: el fallo es de la configuración, no del fichero.
    assert _check(result, "Vault existe")["passed"]


def test_world_readable_config_fails(tmp_path):
    gad = _dashboard()
    result = gad.audit_efdef(_project(tmp_path), _config(tmp_path, mode=0o644))
    assert _check(result, "config.json privado")["passed"] is False


def test_open_trace_dir_fails(tmp_path):
    gad = _dashboard()
    cfg = _config(tmp_path)
    os.chmod(cfg / "logs" / "trazas", 0o755)
    result = gad.audit_efdef(_project(tmp_path), cfg)
    assert _check(result, "Trazas privadas")["passed"] is False


def test_missing_repo_fields_in_claude_md_fail(tmp_path):
    gad = _dashboard()
    claude = CLAUDE_OK.replace(
        "- **GitHub Project (Kanban):** Proyecto #25 de la organización org\n", ""
    )
    result = gad.audit_efdef(_project(tmp_path, claude=claude), _config(tmp_path))
    check = _check(result, "CLAUDE.md: datos del repositorio")
    assert check["passed"] is False
    assert "GitHub Project" in check["detail"]


def test_workflow_words_outside_section_do_not_count(tmp_path):
    gad = _dashboard()
    # Las palabras aparecen en otro sitio, pero el flujo obligatorio no existe.
    claude = (
        CLAUDE_OK.split("## Flujo de trabajo obligatorio")[0]
        + "Issue Rama Pull Request\n"
    )
    result = gad.audit_efdef(_project(tmp_path, claude=claude), _config(tmp_path))
    assert _check(result, "CLAUDE.md: flujo obligatorio")["passed"] is False


def test_broken_readme_link_fails(tmp_path):
    gad = _dashboard()
    readme = "# R\n\n## 📚 Documentación\n- [ok](docs/guide.md)\n- [roto](docs/no-existe.md)\n- [web](https://example.com)\n- [ancla](#seccion)\n"
    result = gad.audit_efdef(_project(tmp_path, readme=readme), _config(tmp_path))
    check = _check(result, "Enlaces del README")
    assert check["passed"] is False
    assert "docs/no-existe.md" in check["detail"]


def test_readme_with_valid_links_passes(tmp_path):
    gad = _dashboard()
    readme = "# R\n\n## 📚 Documentación\n- [ok](docs/guide.md#apartado)\n- [web](https://example.com)\n"
    result = gad.audit_efdef(_project(tmp_path, readme=readme), _config(tmp_path))
    assert _check(result, "Enlaces del README")["passed"]


def test_missing_trazabilidad_spec_fails(tmp_path):
    gad = _dashboard()
    project = _project(tmp_path)
    (project / "docs" / "trazabilidad.md").unlink()
    result = gad.audit_efdef(project, _config(tmp_path))
    assert _check(result, "Especificación de trazas")["passed"] is False
