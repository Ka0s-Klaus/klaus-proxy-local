"""Protección al arrancar del org/repo de la carpeta de proyectos (#134)."""

import json
import subprocess

import pytest

import anthropic_payload_pseudonymize as ps
from Klaus_proxy_local import scan_repos as sr
from Klaus_proxy_local.launcher import ProxyLauncher


def _repo(path, *remotes, email=None):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for name, url in remotes:
        subprocess.run(["git", "-C", str(path), "remote", "add", name, url], check=True)
    if email:
        subprocess.run(
            ["git", "-C", str(path), "config", "user.email", email], check=True
        )
    return path


@pytest.fixture
def projects(tmp_path):
    root = tmp_path / "proyectos"
    _repo(root / "uno", ("origin", "dev2@example.com:cliente-x/repo-nuevo.git"))
    # Segundo remote y identidad propia del repo
    _repo(
        root / "cliente-x" / "dos",
        ("origin", "https://github.com/cliente-x/otro-repo.git"),
        ("upstream", "https://gitlab.example/proveedor-y/base-comun.git"),
        email="persona@cliente-x.example",
    )
    _repo(root / "a" / "b" / "tres", ("origin", "dev2@example.com:acme/docs.git"))
    # Más allá de 3 niveles, en node_modules o en un directorio oculto: fuera
    _repo(
        root / "a" / "b" / "c" / "cuatro",
        ("origin", "dev2@example.com:acme/lejano.git"),
    )
    _repo(root / "node_modules" / "dep", ("origin", "dev2@example.com:acme/dep-x.git"))
    _repo(root / ".oculto" / "r", ("origin", "dev2@example.com:acme/oculto-x.git"))
    (root / "no-es-repo").mkdir()
    return root


def test_find_repos_depth_and_skips(projects):
    names = sorted(r.name for r in sr.find_repos(projects))
    assert names == ["dos", "tres", "uno"]


def test_scan_collects_all_remotes_and_local_identity(projects):
    res = sr.scan([projects])
    assert res["repos"] == 3
    for tok in ("cliente-x", "repo-nuevo", "otro-repo", "proveedor-y", "base-comun"):
        assert tok in res["tokens"]
    assert "acme" in res["tokens"]
    assert res["generic"] == ["docs"]
    assert res["identities"] == ["persona@cliente-x.example"]


def test_protect_writes_config(projects, _isolated_config_json):
    res = sr.scan([projects])
    added = sr.protect(res)
    cfg = json.loads(_isolated_config_json.read_text())
    assert "repo-nuevo" in cfg["pseudo_word_literals"]
    assert "docs" not in cfg["pseudo_word_literals"]
    assert cfg["pseudo_literals"] == ["persona@cliente-x.example"]
    assert added == {"tokens": len(res["tokens"]), "identities": 1}
    # Una segunda pasada no añade nada
    assert sr.protect(res) == {"tokens": 0, "identities": 0}


def test_dry_run_does_not_write(projects, _isolated_config_json):
    before = _isolated_config_json.read_text()
    added = sr.protect(sr.scan([projects]), dry_run=True)
    assert added["tokens"] > 0
    assert _isolated_config_json.read_text() == before


def test_output_has_counts_not_names(projects, _isolated_config_json):
    _isolated_config_json.write_text(
        json.dumps({"salt": "x", "projects_dirs": [str(projects)]})
    )
    lines = sr.scan_and_protect(dry_run=True)
    text = "\n".join(lines)
    assert "org/repo de 3 repos protegidos" in text
    assert "se añadirían" in text
    for name in ("cliente-x", "repo-nuevo", "persona@"):
        assert name not in text
    # Los genéricos sí se nombran: son palabras comunes que no se protegen
    assert "genérico no protegido: docs" in text


def test_projects_dirs_sources(tmp_path, monkeypatch):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    # projects_dirs manda; se ignoran el home y lo que no existe
    cfg = {"projects_dirs": [str(a), str(tmp_path), str(tmp_path / "no")]}
    assert sr.projects_dirs(cfg) == [a]
    # Sin projects_dirs: las carpetas registradas por claude-proxy (#42)
    cfg = {"pseudo_patterns": [ps.projects_root_pattern(str(b)), {"x": 1}, "roto"]}
    assert sr.projects_dirs(cfg, cwd=tmp_path) == [b]
    # ... y la carpeta padre del repo actual
    _repo(a / "actual")
    assert sr.projects_dirs({}, cwd=a / "actual") == [a]


def test_main_dry_run(projects, _isolated_config_json, capsys):
    _isolated_config_json.write_text(
        json.dumps({"salt": "x", "projects_dirs": [str(projects)]})
    )
    with pytest.raises(SystemExit) as exc:
        sr.main(["--dry-run"])
    assert exc.value.code == 0
    assert "3 repos" in capsys.readouterr().out
    assert "pseudo_word_literals" not in json.loads(_isolated_config_json.read_text())


def test_launcher_protects_repos(projects, _isolated_config_json, capsys):
    _isolated_config_json.write_text(
        json.dumps({"salt": "x", "projects_dirs": [str(projects)]})
    )
    launcher = ProxyLauncher()
    launcher.protect_project_repos()
    assert "3 repos protegidos" in capsys.readouterr().out
    assert "repo-nuevo" in launcher.protected_tokens


def test_launcher_scan_failure_does_not_stop(monkeypatch, capsys):
    def boom(*a, **k):
        raise PermissionError("sin permiso")

    monkeypatch.setattr(sr, "scan_and_protect", boom)
    ProxyLauncher().protect_project_repos()
    assert "Exploración de repos no aplicada" in capsys.readouterr().out
