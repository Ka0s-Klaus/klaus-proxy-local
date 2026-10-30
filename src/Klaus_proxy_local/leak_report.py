#!/usr/bin/env python3
"""Informe de fugas y cobertura por proyecto (#146).

Para cada repo git de la carpeta de proyectos responde a cuatro preguntas:

1. **Qué datos sensibles tiene:** ``klaus-scan`` con nombres de negocio (#140).
2. **Si puede sufrir una fuga:** cada valor se pasa por el pseudonimizador con
   las reglas actuales y una copia en memoria del vault; si sale igual, ninguna
   regla lo cubre.
3. **Si la ha sufrido:** cada captura se atribuye a un proyecto por su
   directorio de trabajo (o los remotes de ``safeguards``) y se le aplica la
   detección del verificador por pares.
4. **Cobertura:** valores CRITICAL/HIGH cubiertos sobre el total.

Los valores se muestran como ``⟨categoría·hash·longitud⟩`` (``--reveal`` los
muestra en claro). La caché guarda solo identificadores, nunca valores.

Uso:
    klaus-leak-report                 # informe en informes/fugas/
    klaus-leak-report --open          # y abrirlo en el navegador
    klaus-leak-report --reveal        # valores en claro (solo en tu terminal)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import webbrowser
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from Klaus_proxy_local import scan_repos
from Klaus_proxy_local.audit_reports import write_private
from Klaus_proxy_local.scan import safe_id, safe_path
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner
from Klaus_proxy_local.setup import _pseudonymizer

CACHE_VERSION = 1
REPORT_FILE = "leak-report.html"
REPORT_JSON = "leak-report.json"
REPORT_PREFIX = "leak-report-"
RECENT_DAYS = 30
COVERAGE_LEVELS = ("CRITICAL", "HIGH")  # lo que entra en el %
GOOD_PCT = 95.0
WARN_PCT = 80.0
MAX_LEAK_ITEMS = 100

_CWD_RE = re.compile(r"Primary working directory: ([^\n\"]+)")


def cache_path() -> Path:
    return Path.home() / ".klaus-proxy" / "leak-report-cache.json"


def default_reports_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "informes" / "fugas"


# --- Reglas del proxy ----------------------------------------------------------


class Coverage:
    """Comprueba si el proxy sustituiría un valor, sin tocar el vault real."""

    def __init__(self, captures_dir: Path) -> None:
        ps = _pseudonymizer()
        self.ps = ps
        config = scan_repos.load_config()
        if config.get("salt"):
            os.environ.setdefault("ANTHROPIC_PSEUDO_SALT", str(config["salt"]))
        self.rules = ps.build_rules()
        self.vault_dict = _load_vault(captures_dir)
        self.vault = ps.Vault()
        for real, pseudo in self.vault_dict.items():
            self.vault._register(real, pseudo)
        self.rules_hash = hashlib.sha256(
            json.dumps(
                [
                    sorted(self.rules.literals),
                    sorted(self.rules.word_literals),
                    sorted(p.pattern for p, _ in self.rules.patterns),
                    sorted(self.rules.pattern_ignore),
                    len(self.vault_dict),
                ]
            ).encode()
        ).hexdigest()[:16]

    def covers(self, value: str) -> bool:
        return self.ps.pseudonymize_text(value, self.vault, self.rules) != value


def _load_vault(captures_dir: Path) -> dict[str, str]:
    try:
        data = json.loads(
            (captures_dir / ".pseudonym_vault.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# --- Caché ---------------------------------------------------------------------


def load_cache() -> dict:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": CACHE_VERSION, "repos": {}, "captures": {}}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {"version": CACHE_VERSION, "repos": {}, "captures": {}}
    data.setdefault("repos", {})
    data.setdefault("captures", {})
    return data


def save_cache(cache: dict) -> None:
    try:
        cache_path().parent.mkdir(parents=True, exist_ok=True)
        write_private(cache_path(), json.dumps(cache))
    except OSError:
        # Sin caché la próxima ejecución tarda más, pero el informe es correcto
        return


def _repo_key(repo: Path, rules_hash: str) -> str:
    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    state = git("rev-parse", "HEAD") + git("status", "--porcelain")
    return hashlib.sha256(f"{state}\0{rules_hash}".encode()).hexdigest()[:16]


# --- Datos sensibles de un proyecto -------------------------------------------


def scan_project(repo: Path, coverage: Coverage, reveal: bool = False) -> dict:
    """Valores detectados en ``repo``, agrupados y con su cobertura."""
    result = SensitiveDataScanner(enable_business=True).scan_directory(repo)
    values = [f.value for f in result.findings]
    grouped: dict[tuple[str, str], dict] = {}
    for f in result.findings:
        key = (f.value, f.category)
        item = grouped.get(key)
        if item is None:
            item = grouped[key] = {
                "id": safe_id(f.value, f.category),
                "category": f.category,
                "confidence": f.confidence.name,
                "occurrences": 0,
                "file": safe_path(f.file_path, repo, values),
                "line": f.line_number,
                "covered": coverage.covers(f.value),
            }
            if reveal:
                item["value"] = f.value
                item["file"] = str(f.file_path)
        item["occurrences"] += f.occurrences
    return {
        "values": list(grouped.values()),
        "already_protected": result.already_protected,
    }


# --- Capturas ------------------------------------------------------------------


def capture_cwd(payload: Any) -> str | None:
    """Directorio de trabajo que Claude Code pone en el system prompt."""
    system = payload.get("system") if isinstance(payload, dict) else None
    blocks = system if isinstance(system, list) else [system]
    for block in blocks:
        text = block.get("text") if isinstance(block, dict) else block
        if isinstance(text, str):
            m = _CWD_RE.search(text)
            if m:
                return m.group(1).strip()
    return None


def attribute(
    payload: Any, projects: list[dict], remotes: dict[str, str]
) -> str | None:
    """Ruta del proyecto de una captura: por cwd o, si no, por remotes."""
    cwd = capture_cwd(payload)
    if cwd:
        best = None
        for p in projects:
            root = p["path"]
            if (cwd == root or cwd.startswith(root + "/")) and (
                best is None or len(root) > len(best)
            ):
                best = root
        if best:
            return best
    ps = _pseudonymizer()
    if isinstance(payload, dict):
        for remote in ps._iter_remotes(payload.get("safeguards")):
            key = "/".join(ps._parse_remote_tokens(remote))
            if key in remotes:
                return remotes[key]
    return None


def scan_captures(
    captures_dir: Path,
    projects: list[dict],
    remotes: dict[str, str],
    coverage: Coverage,
    cache: dict,
    reveal: bool = False,
) -> dict[str, dict]:
    """Por captura: proyecto, fecha y fugas (categoría + identificador)."""
    import anthropic_pair_verify as pv

    out: dict[str, dict] = {}
    cached = cache["captures"]
    for opath in sorted((captures_dir / "original").glob("*.json")):
        spath = captures_dir / "sent" / opath.name
        if not spath.exists():
            continue
        key = f"{opath.stat().st_size}:{spath.stat().st_size}:{coverage.rules_hash}"
        entry = cached.get(opath.name)
        if entry is None or entry.get("key") != key or reveal:
            entry = _analyze_capture(
                opath, spath, projects, remotes, coverage, pv, reveal
            )
            entry["key"] = key
            if not reveal:
                cached[opath.name] = entry
        out[opath.name] = entry
    return out


def _analyze_capture(opath, spath, projects, remotes, coverage, pv, reveal) -> dict:
    try:
        original = pv.load_capture(opath)
        sent = pv.load_capture(spath)
    except (OSError, ValueError):
        return {"project": None, "ts": None, "leaks": [], "skipped": "ilegible"}
    ts = str(original.get("captured_at", ""))[:19] or None
    project = attribute(original.get("payload"), projects, remotes)
    if sent.get("capture_only"):
        return {"project": project, "ts": ts, "leaks": [], "skipped": "capture_only"}
    spans = pv.sensitive_spans(original, coverage.vault_dict, coverage.rules)
    leaks = pv.diff_leaks(spans, sent)
    items = []
    for s in leaks:
        item = {"category": s.category, "id": safe_id(s.value, s.category)}
        if reveal:
            item["value"] = s.value
        items.append(item)
    return {"project": project, "ts": ts, "leaks": items}


# --- Informe -------------------------------------------------------------------


def _status(pct: float | None, recent_leaks: int) -> str:
    if recent_leaks:
        return "critical"
    if pct is None or pct >= GOOD_PCT:
        return "good"
    return "warning" if pct >= WARN_PCT else "critical"


def build_report(
    captures_dir: Path,
    *,
    reveal: bool = False,
    use_cache: bool = True,
    now: datetime | None = None,
    progress=None,
) -> dict:
    now = now or datetime.now()
    say = progress or (lambda msg: None)
    config = scan_repos.load_config()
    dirs = scan_repos.projects_dirs(config)
    details = scan_repos.repo_details(dirs)
    projects = [
        {
            "name": str(d["path"].relative_to(d["root"])),
            "path": str(d["path"]),
            "remotes": d["remotes"],
        }
        for d in details
    ]
    remotes = {r: p["path"] for p in projects for r in p["remotes"]}
    coverage = Coverage(captures_dir)
    cache = (
        load_cache()
        if use_cache
        else {"version": CACHE_VERSION, "repos": {}, "captures": {}}
    )

    for i, p in enumerate(projects, 1):
        say(f"[{i}/{len(projects)}] Analizando proyecto {p['name']}")
        repo = Path(p["path"])
        key = _repo_key(repo, coverage.rules_hash)
        entry = cache["repos"].get(p["path"])
        if reveal or entry is None or entry.get("key") != key:
            entry = {"key": key, **scan_project(repo, coverage, reveal)}
            if not reveal:
                cache["repos"][p["path"]] = entry
        p["scan"] = entry

    say("Analizando capturas…")
    captures = scan_captures(captures_dir, projects, remotes, coverage, cache, reveal)
    if use_cache and not reveal:
        save_cache(cache)

    recent_cut = (now - timedelta(days=RECENT_DAYS)).isoformat(timespec="seconds")
    by_project: dict[str | None, list] = {}
    for name, c in captures.items():
        by_project.setdefault(c.get("project"), []).append((name, c))

    report_projects = []
    for p in projects:
        report_projects.append(
            _project_summary(p, by_project.get(p["path"], []), recent_cut)
        )
    unattributed = _leak_summary(by_project.get(None, []), recent_cut)

    totals = Counter()
    for rp in report_projects:
        totals["detected"] += rp["detected"]
        totals["covered"] += rp["covered"]
        totals["leak_captures"] += rp["leaks"]["captures"]
    pct = (
        round(100 * totals["covered"] / totals["detected"], 1)
        if totals["detected"]
        else None
    )
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "revealed": reveal,
        "projects_dirs": [str(d) for d in dirs],
        "captures_analyzed": len(captures),
        "rules_hash": coverage.rules_hash,
        "totals": {**totals, "coverage_pct": pct},
        "projects": report_projects,
        "unattributed": unattributed,
    }


def _leak_summary(items: list[tuple[str, dict]], recent_cut: str) -> dict:
    with_leaks = [(n, c) for n, c in items if c.get("leaks")]
    with_leaks.sort(key=lambda x: x[0], reverse=True)
    cats = Counter(item["category"] for _n, c in with_leaks for item in c["leaks"])
    return {
        "captures_total": len(items),
        "captures": len(with_leaks),
        "recent": sum(1 for _n, c in with_leaks if (c.get("ts") or "") >= recent_cut),
        "last": with_leaks[0][1].get("ts") if with_leaks else None,
        "by_category": dict(cats),
        "items": [
            {
                "capture": n,
                "ts": c.get("ts"),
                "leaks": sorted({(i["category"], i["id"]) for i in c["leaks"]}),
            }
            for n, c in with_leaks[:MAX_LEAK_ITEMS]
        ],
    }


def _project_summary(p: dict, captures: list, recent_cut: str) -> dict:
    values = p["scan"]["values"]
    scored = [v for v in values if v["confidence"] in COVERAGE_LEVELS]
    protected = p["scan"].get("already_protected", 0)
    covered = sum(1 for v in scored if v["covered"]) + protected
    detected = len(scored) + protected
    pct = round(100 * covered / detected, 1) if detected else None
    leaks = _leak_summary(captures, recent_cut)
    by_category: dict[str, dict] = {}
    for v in values:
        c = by_category.setdefault(v["category"], {"covered": 0, "uncovered": 0})
        c["covered" if v["covered"] else "uncovered"] += 1
    uncovered = sorted(
        (v for v in values if not v["covered"]),
        key=lambda v: (
            ["CRITICAL", "HIGH", "MEDIUM", "LOW"].index(v["confidence"]),
            -v["occurrences"],
        ),
    )
    return {
        "name": p["name"],
        "detected": detected,
        "covered": covered,
        "already_protected": protected,
        "coverage_pct": pct,
        "status": _status(pct, leaks["recent"]),
        "candidates": sum(1 for v in values if not v["covered"] and v not in scored),
        "by_category": by_category,
        "uncovered": uncovered,
        "leaks": leaks,
    }


# --- HTML ----------------------------------------------------------------------

_STATUS_STYLE = {
    "good": ("🟢", "var(--good)", "Cubierto"),
    "warning": ("🟡", "var(--warn)", "Revisar"),
    "critical": ("🔴", "var(--bad)", "Crítico"),
}


def _pct(p: float | None) -> str:
    return "—" if p is None else f"{p:.1f} %"


def render_html(report: dict) -> str:
    esc = html.escape
    rows = []
    sections = []
    for i, p in enumerate(report["projects"]):
        icon, color, label = _STATUS_STYLE[p["status"]]
        leaks = p["leaks"]
        rows.append(
            f"<tr><td><a href='#p{i}'>{esc(p['name'])}</a></td>"
            f"<td><div class='bar'><span style='width:{p['coverage_pct'] or 0}%;"
            f"background:{color}'></span></div></td>"
            f"<td class='num' style='color:{color}'><b>{_pct(p['coverage_pct'])}</b></td>"
            f"<td class='num'>{p['detected'] - p['covered']}</td>"
            f"<td class='num'>{p['candidates']}</td>"
            f"<td class='num'>{leaks['captures']}"
            f"{' · ' + str(leaks['recent']) + ' recientes' if leaks['recent'] else ''}</td>"
            f"<td>{icon} {label}</td></tr>"
        )
        sections.append(_project_html(i, p))
    totals = report["totals"]
    un = report["unattributed"]
    revealed = (
        "<p class='warn'>⚠️ Informe generado con <code>--reveal</code>: contiene "
        "valores en claro. No lo compartas.</p>"
        if report.get("revealed")
        else ""
    )
    unattributed = (
        f"<p>Capturas sin proyecto atribuible: {un['captures_total']:,}, "
        f"{un['captures']:,} con fugas"
        f"{' (última ' + esc(un['last']) + ')' if un['last'] else ''}.</p>"
    )
    return _TEMPLATE.format(
        generated=esc(report["generated_at"]),
        dirs=", ".join(f"<code>{esc(d)}</code>" for d in report["projects_dirs"]),
        captures=f"{report['captures_analyzed']:,}",
        total_pct=_pct(totals.get("coverage_pct")),
        projects=len(report["projects"]),
        leak_captures=f"{totals.get('leak_captures', 0):,}",
        revealed=revealed,
        rows="".join(rows),
        sections="".join(sections),
        unattributed=unattributed,
        recent=RECENT_DAYS,
        good=GOOD_PCT,
        warn=WARN_PCT,
    )


def _project_html(i: int, p: dict) -> str:
    esc = html.escape
    icon, color, label = _STATUS_STYLE[p["status"]]
    cats = "".join(
        f"<tr><td><code>{esc(c)}</code></td><td class='num'>{v['covered']}</td>"
        f"<td class='num'>{v['uncovered']}</td></tr>"
        for c, v in sorted(p["by_category"].items())
    )
    unc = "".join(
        f"<tr><td><code>{esc(v.get('value') or v['id'])}</code></td>"
        f"<td>{esc(v['category'])}</td><td>{esc(v['confidence'])}</td>"
        f"<td class='num'>{v['occurrences']}</td>"
        f"<td><code>{esc(v['file'])}:{v['line']}</code></td></tr>"
        for v in p["uncovered"][:200]
    )
    leaks = p["leaks"]
    leak_rows = "".join(
        f"<tr><td><code>{esc(item['capture'])}</code></td><td>{esc(item['ts'] or '—')}</td>"
        f"<td>{esc(', '.join(sorted({c for c, _ in item['leaks']})))}</td>"
        f"<td><small>{esc(' '.join(sorted({x for _, x in item['leaks']}))[:300])}</small></td></tr>"
        for item in leaks["items"]
    )
    return f"""
<section class='card' id='p{i}'>
  <h2>{icon} {esc(p['name'])} <span style='color:{color}'>{_pct(p['coverage_pct'])}</span></h2>
  <p class='muted'>{label} · {p['detected']} valores CRITICAL/HIGH,
  {p['covered']} cubiertos ({p['already_protected']} ya en reglas) ·
  {p['candidates']} candidatos MEDIUM/LOW sin cubrir</p>
  <h3>¿Qué tiene?</h3>
  <table><thead><tr><th>Categoría</th><th>Cubiertos</th><th>Sin cubrir</th></tr></thead>
  <tbody>{cats or "<tr><td colspan='3'>Nada detectado</td></tr>"}</tbody></table>
  <h3>¿Puede sufrir una fuga? Valores sin cubrir</h3>
  {"<table><thead><tr><th>Valor</th><th>Categoría</th><th>Confianza</th><th>Apariciones</th><th>Primera ubicación</th></tr></thead><tbody>" + unc + "</tbody></table>" if unc else "<p>✅ Todo lo detectado está cubierto.</p>"}
  <h3>¿La ha sufrido?</h3>
  <p>{leaks['captures_total']:,} capturas del proyecto · <b>{leaks['captures']:,} con fugas</b>
  ({leaks['recent']:,} en los últimos {RECENT_DAYS} días){' · última ' + esc(leaks['last']) if leaks['last'] else ''}</p>
  {"<table><thead><tr><th>Captura</th><th>Fecha</th><th>Tipo</th><th>Valores</th></tr></thead><tbody>" + leak_rows + "</tbody></table>" if leak_rows else ""}
</section>"""


_TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fugas por proyecto</title>
<style>
:root {{ --bg:#f7f7f8; --card:#fff; --text:#1d1d1f; --muted:#6b6b70; --line:#e3e3e6;
  --good:#1a8f3c; --warn:#b97a00; --bad:#c62828; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --card:#1e1e21;
  --text:#ececf0; --muted:#9a9aa2; --line:#2e2e33; --good:#4cc46f; --warn:#e3a833;
  --bad:#ef5350; }} }}
body {{ background:var(--bg); color:var(--text); margin:0; padding:16px;
  font:14px/1.5 -apple-system,system-ui,sans-serif; }}
main {{ max-width:1100px; margin:auto; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:16px; margin:12px 0; overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }}
td.num {{ text-align:right; white-space:nowrap; }}
.muted {{ color:var(--muted); font-size:.85rem; }}
.warn {{ color:var(--bad); font-weight:600; }}
.bar {{ background:var(--line); border-radius:4px; height:10px; min-width:80px; }}
.bar span {{ display:block; height:100%; border-radius:4px; }}
a {{ color:inherit; }}
</style></head><body><main>
<h1>🕵️ Fugas por proyecto</h1>
<p class="muted">Generado {generated} · {dirs} · {captures} capturas analizadas</p>
{revealed}
<section class="card">
<h2>Cobertura global: {total_pct}</h2>
<p class="muted">{projects} proyectos · {leak_captures} capturas con fugas atribuidas.
Cobertura = valores CRITICAL/HIGH que el proxy sustituye o redacta, sobre el total.
🟢 ≥ {good:.0f} % · 🟡 ≥ {warn:.0f} % · 🔴 menos, o alguna fuga en los últimos {recent} días.
Los valores se muestran como <code>⟨categoría·hash·longitud⟩</code>.
⚠️ El informe muestra los nombres de tus proyectos: no lo compartas tal cual.</p>
<table><thead><tr><th>Proyecto</th><th></th><th>Cobertura</th><th>Sin cubrir</th>
<th>Candidatos</th><th>Capturas con fugas</th><th>Estado</th></tr></thead>
<tbody>{rows}</tbody></table>
{unattributed}
<p class="muted">Para cubrir un valor: <code>klaus-scan &lt;proyecto&gt; --reveal</code>
en tu terminal y apruébalo, y reinicia <code>claude-proxy</code>.</p>
</section>
{sections}
</main></body></html>
"""


def save_report(report: dict, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["generated_at"].replace(":", "").replace("-", "")
    page = render_html(report)
    data = json.dumps(report, indent=2, ensure_ascii=False)
    write_private(reports_dir / f"{REPORT_PREFIX}{stamp}.html", page)
    write_private(reports_dir / f"{REPORT_PREFIX}{stamp}.json", data)
    write_private(reports_dir / REPORT_FILE, page)
    write_private(reports_dir / REPORT_JSON, data)
    return reports_dir / REPORT_FILE


def load_latest(reports_dir: Path) -> dict | None:
    """Último informe, para la tarjeta del dashboard de auditoría."""
    try:
        data = json.loads((reports_dir / REPORT_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "projects" in data else None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="klaus-leak-report",
        description=(
            "Informe de fugas por proyecto: qué datos sensibles tiene cada repo, "
            "cuáles no cubre el proxy, qué ha salido en las capturas y el % de "
            "cobertura."
        ),
    )
    parser.add_argument(
        "--captures-dir",
        default=None,
        help="Directorio de capturas (por defecto el de claude-proxy)",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(default_reports_dir()),
        help="Dónde guardar el informe (por defecto informes/fugas/)",
    )
    parser.add_argument(
        "--reveal",
        action="store_true",
        help="Valores en claro en el informe (solo en tu terminal; sin caché)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Recalcula todo")
    parser.add_argument("--open", action="store_true", help="Abre el informe")
    args = parser.parse_args(argv)

    from Klaus_proxy_local import capture_retention

    captures_dir = (
        Path(args.captures_dir).expanduser()
        if args.captures_dir
        else capture_retention.captures_dir(scan_repos.load_config())
    )
    report = build_report(
        captures_dir,
        reveal=args.reveal,
        use_cache=not args.no_cache,
        progress=lambda msg: print(msg, file=sys.stderr, flush=True),
    )
    path = save_report(report, Path(args.reports_dir).expanduser())
    totals = report["totals"]
    print(f"🕵️  Cobertura global: {_pct(totals.get('coverage_pct'))}")
    for p in report["projects"]:
        icon = _STATUS_STYLE[p["status"]][0]
        print(
            f"  {icon} {_pct(p['coverage_pct']):>8}  sin cubrir "
            f"{p['detected'] - p['covered']:>4}  capturas con fugas "
            f"{p['leaks']['captures']:>4}  {p['name']}"
        )
    print(f"📄 {path}")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    sys.exit(0)


if __name__ == "__main__":
    main()
