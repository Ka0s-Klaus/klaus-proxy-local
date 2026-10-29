"""History of audit reports for the audit dashboard (#77).

Every run of ``generate_audit_dashboard.py`` stores its result in ``informes/``
instead of overwriting a single HTML:

- ``audit-YYYYMMDD-HHMMSS.json``: raw report (schema, date, the 5 plans);
- ``audit-YYYYMMDD-HHMMSS.html``: dashboard of that report, with the changes
  against its predecessor computed when it was generated;
- ``index.js``: list of reports, rewritten on every run. Each HTML loads it with
  ``<script src>``, which works over ``file://``, so old reports also list the
  newer ones;
- ``audit-dashboard.html``: copy of the latest report, stable entry point.

Pure functions (no audits, no I/O apart from the reports dir) so they can be
tested without captures or pytest.
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PREFIX = "audit-"
INDEX_FILE = "index.js"
DASHBOARD_FILE = "audit-dashboard.html"
PLANS = (
    ("security", "🔐 Seguridad"),
    ("pseudonymization", "📊 Pseudonimización"),
    ("performance", "⚡ Actividad"),
    ("tests", "🧪 Tests"),
    ("efdef", "📋 EFDEF"),
)
_STATUS_RANK = {"good": 0, "no_data": 1, "warning": 2, "critical": 3}
_STATUS_LABEL = {
    "good": "✅ OK",
    "warning": "⚠️ Revisar",
    "critical": "🔴 Crítico",
    "no_data": "⬜ Sin datos",
}

# Series and per-request details: they change on every run and say nothing
# about the state of the system, so they are left out of the comparison.
_SKIP_FIELDS = {
    "daily_dates",
    "daily_pct",
    "daily_totals",
    "daily_counts",
    "recent",
    "output_summary",
    "injection_hits",
    "path_distribution",
    "status_distribution",
    "checks",
    "host_distribution",
    "model_distribution",
}

# Direction that means improvement. Fields not listed are shown neutral.
_HIGHER_IS_BETTER = {
    "secrets_redacted_pct",
    "pct",
    "pct_modified",
    "recent_pct",
    "pass_rate",
}
_LOWER_IS_BETTER = {
    "unexpected_count",
    "injection_count",
    "pseudo_no",
    "failed",
    "errors",
}
_FIELD_LABEL = {
    "total": "Peticiones auditadas",
    "secrets_redacted": "Con secretos redactados",
    "secrets_redacted_pct": "% secretos redactados",
    "blocked": "Peticiones bloqueadas",
    "unexpected_count": "Peticiones a hosts inesperados",
    "injection_count": "Patrones de prompt injection",
    "total_llm": "Peticiones LLM",
    "pseudo_yes": "Pseudonimizador ejecutado",
    "pseudo_modified": "Con datos sustituidos",
    "pseudo_no": "Sin pseudonimizar",
    "pct": "% pseudonimizadas",
    "pct_modified": "% con datos sustituidos",
    "recent_pct": "% pseudonimizadas (recientes)",
    "recent_total": "Peticiones recientes",
    "vault_entries": "Entradas del vault",
    "literals_count": "Literales",
    "word_literals_count": "Word-literals",
    "total_all": "Capturas totales",
    "total_last30": "Capturas (30 días)",
    "active_days": "Días activos",
    "avg_per_active_day": "Media por día activo",
    "test_count": "Tests",
    "passed": "Superados",
    "failed": "Fallidos",
    "errors": "Errores",
    "pass_rate": "% superados",
}


# ── Report files ────────────────────────────────────────────────────────────


def build_report(
    plans: dict[str, dict],
    total_captures: int,
    date_range: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now()
    return {
        "schema": SCHEMA_VERSION,
        "id": PREFIX + generated_at.strftime("%Y%m%d-%H%M%S"),
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "total_captures": total_captures,
        "date_range": date_range,
        "plans": plans,
    }


def save_report(report: dict[str, Any], reports_dir: Path) -> Path:
    """Write the report JSON (0600) without ever overwriting an existing one.

    Two runs in the same second get ``-2``, ``-3``… and ``report["id"]`` is
    updated to match.
    """
    reports_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    base = report["id"]
    n = 1
    while True:
        rid = base if n == 1 else f"{base}-{n}"
        path = reports_dir / f"{rid}.json"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            n += 1
            continue
        report["id"] = rid
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
        return path


def list_reports(reports_dir: Path) -> list[dict[str, Any]]:
    """Saved reports, newest first. Unreadable files are skipped."""
    reports = []
    for path in reports_dir.glob(f"{PREFIX}*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("plans"), dict):
            data.setdefault("id", path.stem)
            reports.append(data)
    return sorted(
        reports, key=lambda r: (r.get("generated_at", ""), r["id"]), reverse=True
    )


def predecessor(reports: list[dict[str, Any]], report_id: str) -> dict | None:
    """Report generated right before ``report_id`` (``reports`` newest first)."""
    ids = [r["id"] for r in reports]
    if report_id not in ids:
        return None
    i = ids.index(report_id)
    return reports[i + 1] if i + 1 < len(reports) else None


def write_index(reports: list[dict[str, Any]], reports_dir: Path) -> Path:
    """``index.js`` with the list the selector shows (newest first)."""
    entries = [
        {
            "id": r["id"],
            "generated_at": r.get("generated_at", ""),
            "total_captures": r.get("total_captures", 0),
            "statuses": {
                key: (r["plans"].get(key) or {}).get("status", "no_data")
                for key, _label in PLANS
            },
        }
        for r in reports
    ]
    path = reports_dir / INDEX_FILE
    tmp = reports_dir / f".{INDEX_FILE}.{os.getpid()}.tmp"
    tmp.write_text(
        "window.KLAUS_REPORTS = "
        + json.dumps(entries, ensure_ascii=False, indent=1)
        + ";\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def write_private(path: Path, text: str) -> None:
    """Atomic write with 0600 permissions."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


# ── Comparison ──────────────────────────────────────────────────────────────


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def diff_reports(new: dict[str, Any], old: dict[str, Any] | None) -> list[dict]:
    """Changes from ``old`` to ``new``: one dict per change.

    ``kind`` is ``status``, ``number``, ``added``, ``removed`` or ``check``;
    ``trend`` is ``better``, ``worse`` or ``neutral``.
    """
    if old is None:
        return []
    changes: list[dict] = []

    def add(plan, field, kind, before, after, trend="neutral"):
        changes.append(
            {
                "plan": plan,
                "field": field,
                "kind": kind,
                "before": before,
                "after": after,
                "trend": trend,
            }
        )

    n_new, n_old = new.get("total_captures", 0), old.get("total_captures", 0)
    if n_new != n_old:
        add("general", "total_captures", "number", n_old, n_new)

    for key, _label in PLANS:
        a = old["plans"].get(key) or {}
        b = new["plans"].get(key) or {}
        sa, sb = a.get("status", "no_data"), b.get("status", "no_data")
        if sa != sb:
            worse = _STATUS_RANK.get(sb, 1) > _STATUS_RANK.get(sa, 1)
            add(key, "status", "status", sa, sb, "worse" if worse else "better")

        for field in sorted(set(a) | set(b)):
            if field == "status" or field in _SKIP_FIELDS:
                continue
            va, vb = a.get(field), b.get(field)
            if va == vb:
                continue
            na, nb = _number(va), _number(vb)
            if na is not None and nb is not None:
                trend = "neutral"
                if field in _HIGHER_IS_BETTER:
                    trend = "better" if nb > na else "worse"
                elif field in _LOWER_IS_BETTER:
                    trend = "better" if nb < na else "worse"
                add(key, field, "number", va, vb, trend)
            elif isinstance(va, list) or isinstance(vb, list):
                before = {str(x) for x in va or []}
                after = {str(x) for x in vb or []}
                bad = field in {"unexpected_hosts"}
                for item in sorted(after - before):
                    add(key, field, "added", None, item, "worse" if bad else "neutral")
                for item in sorted(before - after):
                    add(
                        key,
                        field,
                        "removed",
                        item,
                        None,
                        "better" if bad else "neutral",
                    )

        if key == "efdef":
            checks_a = {c.get("label"): c for c in a.get("checks") or []}
            checks_b = {c.get("label"): c for c in b.get("checks") or []}
            for label in sorted(set(checks_a) | set(checks_b), key=str):
                pa = (checks_a.get(label) or {}).get("passed")
                pb = (checks_b.get(label) or {}).get("passed")
                if pa != pb:
                    trend = "better" if pb else "worse"
                    add(key, label, "check", pa, pb, trend)
    return changes


# ── HTML fragments ──────────────────────────────────────────────────────────


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", " ")
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return str(value)


def _when(report: dict[str, Any]) -> str:
    try:
        return datetime.fromisoformat(report["generated_at"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (KeyError, ValueError):
        return report.get("id", "?")


def render_changes_html(changes: list[dict], previous: dict | None) -> str:
    """Panel 'Cambios respecto al informe anterior'."""
    if previous is None:
        body = '<p class="changes-empty">Es el primer informe: no hay uno anterior con el que comparar.</p>'
        title = "🔁 Cambios respecto al informe anterior"
    else:
        title = f'🔁 Cambios respecto al informe anterior <span class="changes-prev">({html.escape(_when(previous))})</span>'
        if not changes:
            body = '<p class="changes-empty">Sin cambios en estados, métricas ni checks.</p>'
        else:
            labels = dict(PLANS) | {"general": "General"}
            rows = []
            for c in changes:
                plan = html.escape(labels.get(c["plan"], c["plan"]))
                field = c["field"]
                if c["kind"] == "status":
                    what = "Estado"
                    detail = f"{_STATUS_LABEL.get(c['before'], c['before'])} → {_STATUS_LABEL.get(c['after'], c['after'])}"
                elif c["kind"] == "number":
                    what = _FIELD_LABEL.get(
                        field,
                        "Capturas totales" if field == "total_captures" else field,
                    )
                    delta = c["after"] - c["before"]
                    sign = "+" if delta > 0 else ""
                    detail = f"{_fmt(c['before'])} → {_fmt(c['after'])} <span class=\"delta\">({sign}{_fmt(delta)})</span>"
                elif c["kind"] == "check":
                    what = f"Check «{field}»"
                    detail = (
                        "✅ pasa"
                        if c["after"]
                        else ("❌ falla" if c["after"] is False else "— eliminado")
                    )
                elif c["kind"] == "added":
                    what = "Hosts inesperados" if field == "unexpected_hosts" else field
                    detail = f"+ {html.escape(str(c['after']))}"
                else:
                    what = "Hosts inesperados" if field == "unexpected_hosts" else field
                    detail = f"− {html.escape(str(c['before']))}"
                icon = {"better": "▲", "worse": "▼"}.get(c["trend"], "•")
                rows.append(
                    f'<tr class="chg-{c["trend"]}"><td class="chg-icon">{icon}</td>'
                    f"<td>{plan}</td><td>{html.escape(str(what))}</td><td>{detail}</td></tr>"
                )
            worse = sum(c["trend"] == "worse" for c in changes)
            better = sum(c["trend"] == "better" for c in changes)
            summary = f'<p class="changes-summary">{len(changes)} cambios · <span class="chg-better">▲ {better} a mejor</span> · <span class="chg-worse">▼ {worse} a peor</span></p>'
            body = (
                summary + '<table class="changes-table">' + "".join(rows) + "</table>"
            )
    return f'<section class="changes" id="changes"><h2>{title}</h2>{body}</section>'


def render_history_html(report: dict[str, Any], base: str = "") -> str:
    """Selector of reports. Filled from ``index.js``; falls back to the current one."""
    rid = html.escape(report["id"])
    when = html.escape(_when(report))
    return (
        f'<div class="history" data-current="{rid}" data-base="{html.escape(base)}">'
        f'<label for="report-select">📂 Informe:</label>'
        f'<select id="report-select"><option value="{rid}" selected>{when}</option></select>'
        f'<a class="history-latest" id="history-latest" href="{html.escape(base)}{DASHBOARD_FILE}" hidden>Ir al último ↗</a>'
        f'<span class="history-note" id="history-note"></span>'
        f"</div>"
        f'<script src="{html.escape(base)}{INDEX_FILE}"></script>'
    )


HISTORY_CSS = """
  .history { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:8px; font-size:.8rem; color:var(--text-secondary); }
  .history select { font:inherit; padding:4px 8px; border:1px solid var(--border); border-radius:6px; background:var(--surface-card); color:var(--text-primary); max-width:100%; }
  .history-latest { color:#2a78d6; text-decoration:none; font-weight:600; }
  .history-note { color:#fab219; font-weight:600; }
  .changes { margin:16px 24px 0; padding:14px 16px; border:1px solid var(--border); border-radius:10px; background:var(--surface-card); }
  .changes h2 { font-size:.95rem; margin:0 0 8px; }
  .changes-prev { font-weight:400; color:var(--text-muted); font-size:.8rem; }
  .changes-empty, .changes-summary { font-size:.8rem; color:var(--text-secondary); margin:0 0 6px; }
  .changes-table { width:100%; border-collapse:collapse; font-size:.8rem; }
  .changes-table td { padding:4px 6px; border-top:1px solid var(--border); vertical-align:top; overflow-wrap:anywhere; }
  .chg-icon { width:1.2em; }
  .chg-better .chg-icon, .chg-better { color:#0ca30c; }
  .chg-worse .chg-icon, .chg-worse { color:#d03b3b; }
  .chg-better td:not(.chg-icon), .chg-worse td:not(.chg-icon) { color:var(--text-primary); }
  .delta { color:var(--text-muted); }
  @media (max-width: 600px) { .changes { margin:12px 16px 0; } }
"""

HISTORY_JS = """
(function () {
  var box = document.querySelector('.history');
  if (!box) return;
  var list = window.KLAUS_REPORTS || [];
  var current = box.dataset.current, base = box.dataset.base || '';
  var sel = document.getElementById('report-select');
  var rank = {critical: '🔴', warning: '⚠️', no_data: '⬜', good: '✅'};
  if (list.length) {
    sel.innerHTML = '';
    list.forEach(function (r, i) {
      var worst = Object.values(r.statuses).sort(function (a, b) {
        return ['good','no_data','warning','critical'].indexOf(b) - ['good','no_data','warning','critical'].indexOf(a);
      })[0];
      var o = document.createElement('option');
      o.value = r.id;
      o.textContent = r.generated_at.replace('T', ' ') + (i === 0 ? '  (último)' : '') + '  ' + (rank[worst] || '');
      if (r.id === current) o.selected = true;
      sel.appendChild(o);
    });
    if (list[0].id !== current) {
      document.getElementById('history-latest').hidden = false;
      document.getElementById('history-note').textContent = 'Estás viendo un informe anterior';
    }
  }
  sel.addEventListener('change', function () {
    var idx = list.length ? list.findIndex(function (r) { return r.id === sel.value; }) : -1;
    location.href = base + (idx === 0 ? 'audit-dashboard.html' : sel.value + '.html');
  });
})();
"""
