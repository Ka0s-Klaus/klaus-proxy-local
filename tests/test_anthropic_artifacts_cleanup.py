#!/usr/bin/env python3
"""Tests del limpiador/hardening de artefactos en reposo de Claude Code."""
from __future__ import annotations

import os
import stat
import time

import pytest

import anthropic_artifacts_cleanup as ac

# --- Fixtures: estructura de disco falsa --------------------------------------


@pytest.fixture()
def fake_tree(tmp_path):
    """Reproduce la topología real de artefactos en un árbol temporal.

    Devuelve (home, tmp_base) y crea:
      home/.claude/projects/<proj>/<sess>/tool-results/big.txt   (0644)
      tmp_base/<proj>/<sess>/tasks/out.output                    (0644)
      tmp_base/<proj>/<sess>/tasks/link.output -> external.jsonl  (symlink)
    """
    home = tmp_path / "home"
    tmp_base = tmp_path / "tmp" / "claude-501"

    tr = home / ".claude" / "projects" / "proj-a" / "sess-1" / "tool-results"
    tr.mkdir(parents=True)
    big = tr / "big.txt"
    big.write_text("contenido en claro con usuario localuser\n" * 10)
    os.chmod(big, 0o644)
    os.chmod(tr, 0o755)

    tasks = tmp_base / "proj-a" / "sess-1" / "tasks"
    tasks.mkdir(parents=True)
    out = tasks / "out.output"
    out.write_text("otra salida\n")
    os.chmod(out, 0o644)
    os.chmod(tasks, 0o755)

    # Symlink a un transcript de subagente FUERA del árbol de tareas.
    external = tmp_path / "external.jsonl"
    external.write_text("transcript sensible del subagente")
    link = tasks / "link.output"
    link.symlink_to(external)

    return (
        home,
        tmp_base,
        {
            "big": big,
            "out": out,
            "link": link,
            "external": external,
            "tr": tr,
            "tasks": tasks,
        },
    )


# --- Descubrimiento / clasificación ------------------------------------------


def test_discover_finds_both_roots(fake_tree):
    home, tmp_base, f = fake_tree
    dirs = ac.discover_artifact_dirs(home, tmp_base)
    assert f["tr"] in dirs
    assert f["tasks"] in dirs


def test_scan_classifies_kinds(fake_tree):
    home, tmp_base, f = fake_tree
    arts = {a.path: a for a in ac.scan(home, tmp_base)}
    assert arts[f["big"]].kind == "file"
    assert arts[f["out"]].kind == "file"
    assert arts[f["link"]].kind == "symlink"
    assert arts[f["tr"]].kind == "dir"


def test_is_artifact_entry_containment(fake_tree):
    _, _, f = fake_tree
    assert ac.is_artifact_entry(f["big"])  # padre = tool-results
    assert ac.is_artifact_entry(f["out"])  # padre = tasks
    assert not ac.is_artifact_entry(f["external"])  # fuera de ámbito


# --- Hardening ----------------------------------------------------------------


def test_plan_harden_targets_files_and_dirs(fake_tree):
    home, tmp_base, f = fake_tree
    actions = ac.plan_harden(ac.scan(home, tmp_base))
    paths = {a.path for a in actions}
    assert f["big"] in paths and f["out"] in paths
    assert f["tr"] in paths and f["tasks"] in paths


def test_plan_harden_skips_symlinks(fake_tree):
    home, tmp_base, f = fake_tree
    actions = ac.plan_harden(ac.scan(home, tmp_base))
    assert f["link"] not in {a.path for a in actions}


def test_harden_apply_sets_owner_only_perms(fake_tree):
    home, tmp_base, f = fake_tree
    actions = ac.plan_harden(ac.scan(home, tmp_base))
    ac.apply_actions(actions, dry_run=False)
    assert stat.S_IMODE(f["big"].stat().st_mode) == ac.FILE_MODE
    assert stat.S_IMODE(f["out"].stat().st_mode) == ac.FILE_MODE
    assert stat.S_IMODE(f["tr"].stat().st_mode) == ac.DIR_MODE
    assert stat.S_IMODE(f["tasks"].stat().st_mode) == ac.DIR_MODE


def test_harden_dry_run_does_not_change_perms(fake_tree):
    home, tmp_base, f = fake_tree
    before = stat.S_IMODE(f["big"].stat().st_mode)
    ac.apply_actions(ac.plan_harden(ac.scan(home, tmp_base)), dry_run=True)
    assert stat.S_IMODE(f["big"].stat().st_mode) == before


def test_harden_is_idempotent(fake_tree):
    home, tmp_base, _ = fake_tree
    ac.apply_actions(ac.plan_harden(ac.scan(home, tmp_base)), dry_run=False)
    # Segunda pasada: ya todo en modo objetivo → nada que planificar.
    assert ac.plan_harden(ac.scan(home, tmp_base)) == []


def test_harden_never_touches_symlink_target(fake_tree):
    home, tmp_base, f = fake_tree
    before = stat.S_IMODE(f["external"].stat().st_mode)
    ac.apply_actions(ac.plan_harden(ac.scan(home, tmp_base)), dry_run=False)
    assert stat.S_IMODE(f["external"].stat().st_mode) == before


# --- Limpieza -----------------------------------------------------------------


def test_plan_clean_respects_age_threshold(fake_tree):
    home, tmp_base, f = fake_tree
    arts = ac.scan(home, tmp_base)
    now = time.time()
    # Nada tiene 30 días → plan vacío.
    assert ac.plan_clean(arts, older_than_days=30, now=now) == []
    # Con "now" 10 días en el futuro, los ficheros regulares vencen.
    future = now + 10 * 86400
    planned = {a.path for a in ac.plan_clean(arts, older_than_days=7, now=future)}
    assert f["big"] in planned and f["out"] in planned


def test_plan_clean_excludes_symlinks_by_default(fake_tree):
    home, tmp_base, f = fake_tree
    future = time.time() + 100 * 86400
    planned = {
        a.path
        for a in ac.plan_clean(ac.scan(home, tmp_base), older_than_days=1, now=future)
    }
    assert f["link"] not in planned


def test_plan_clean_includes_symlinks_when_opted_in(fake_tree):
    home, tmp_base, f = fake_tree
    future = time.time() + 100 * 86400
    planned = {
        a.path
        for a in ac.plan_clean(
            ac.scan(home, tmp_base),
            older_than_days=1,
            now=future,
            include_symlinks=True,
        )
    }
    assert f["link"] in planned


def test_clean_apply_deletes_file_but_not_symlink_target(fake_tree):
    home, tmp_base, f = fake_tree
    future = time.time() + 100 * 86400
    actions = ac.plan_clean(
        ac.scan(home, tmp_base), older_than_days=1, now=future, include_symlinks=True
    )
    ac.apply_actions(actions, dry_run=False)
    assert not f["big"].exists()
    assert not f["out"].exists()
    assert not f["link"].exists()  # el enlace se borró...
    assert f["external"].exists()  # ...pero el destino NO


def test_clean_dry_run_deletes_nothing(fake_tree):
    home, tmp_base, f = fake_tree
    future = time.time() + 100 * 86400
    actions = ac.plan_clean(ac.scan(home, tmp_base), older_than_days=1, now=future)
    ac.apply_actions(actions, dry_run=True)
    assert f["big"].exists() and f["out"].exists()


def test_plan_clean_never_deletes_dirs(fake_tree):
    home, tmp_base, f = fake_tree
    future = time.time() + 100 * 86400
    planned = ac.plan_clean(ac.scan(home, tmp_base), older_than_days=1, now=future)
    assert f["tr"] not in {a.path for a in planned}
    assert f["tasks"] not in {a.path for a in planned}


# --- Contención de ruta (defensa en profundidad) ------------------------------


def test_apply_skips_out_of_scope_paths(tmp_path):
    rogue = tmp_path / "no-es-artefacto.txt"
    rogue.write_text("no tocar")
    action = ac.Action("delete", rogue, "malicioso")
    log = ac.apply_actions([action], dry_run=False)
    assert rogue.exists()  # no se borró
    assert any("SKIP" in line for line in log)


# --- Resumen / utilidades -----------------------------------------------------


def test_summarize_counts(fake_tree):
    home, tmp_base, _ = fake_tree
    s = ac.summarize(ac.scan(home, tmp_base))
    assert s["files"] == 2
    assert s["symlinks"] == 1
    assert s["dirs"] == 2
    assert s["world_or_group_readable_files"] == 2  # ambos 0644


def test_fmt_mode():
    assert ac._fmt_mode(0o600) == "0600"
    assert ac._fmt_mode(0o755) == "0755"


def test_default_tmp_base_uses_uid():
    assert ac.default_tmp_base(501) == __import__("pathlib").Path(
        "/private/tmp/claude-501"
    )


# --- CLI ----------------------------------------------------------------------


def test_main_inventory_only_returns_zero(fake_tree, capsys):
    home, tmp_base, _ = fake_tree
    rc = ac.main(["prog", "--home", str(home), "--tmp-base", str(tmp_base)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Inventario" in out
    assert "Solo inventario" in out


def test_main_harden_dry_run_does_not_apply(fake_tree, capsys):
    home, tmp_base, f = fake_tree
    before = stat.S_IMODE(f["big"].stat().st_mode)
    rc = ac.main(["prog", "--harden", "--home", str(home), "--tmp-base", str(tmp_base)])
    assert rc == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert stat.S_IMODE(f["big"].stat().st_mode) == before  # intacto


def test_main_harden_apply_changes_perms(fake_tree, capsys):
    home, tmp_base, f = fake_tree
    rc = ac.main(
        [
            "prog",
            "--harden",
            "--apply",
            "--home",
            str(home),
            "--tmp-base",
            str(tmp_base),
        ]
    )
    assert rc == 0
    assert "APLICANDO" in capsys.readouterr().out
    assert stat.S_IMODE(f["big"].stat().st_mode) == ac.FILE_MODE
