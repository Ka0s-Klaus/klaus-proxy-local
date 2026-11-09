"""Informes legibles de las trazas para revisión humana (issue #220).

Todo lo que se muestra sale de campos no sensibles: ids, hashes truncados,
modelos, tokens, códigos de error, tiempos e incidencias. Nunca se imprime
el contenido de ``payload`` que pueda contener datos del usuario.

- ``render_recent_table``: tabla de trazas recientes para la terminal.
- ``render_detail``: línea de tiempo de una traza.
- ``render_markdown``: informe exportable, con sección «Para revisar».
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Klaus_proxy_local.trace_stats import (
    EXCHANGE_TYPES,
    MAX_ISSUES_SHOWN,
    TraceReport,
    _is_count,
    compute_stats,
    render_performance_lines,
)

UNKNOWN_MODEL = "no_devuelto"
HASH_SHOWN = 12  # caracteres hexadecimales de un hash en los informes
RECENT_DEFAULT = 10


def _short_hash(value: Any) -> str:
    text = str(value or "")
    if text.startswith("sha256:"):
        return "sha256:" + text[len("sha256:") :][:HASH_SHOWN]
    return text[:HASH_SHOWN] if text else "—"


def _cell(value: Any) -> str:
    """Valor seguro para una celda de tabla Markdown."""
    text = "—" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _ms_text(value: Any) -> str | None:
    return None if value is None else f"{value} ms"


def _ms_cell(dist: Any, key: str) -> str | None:
    value = (dist or {}).get(key) if isinstance(dist, dict) else None
    return _ms_text(value)


def _pct_cell(value: Any) -> str | None:
    return None if value is None else f"{value}%"


def _time(timestamp: Any) -> str:
    return (
        str(timestamp)[11:19]
        if isinstance(timestamp, str) and len(timestamp) >= 19
        else "—"
    )


def summarize_trace(report: TraceReport) -> dict[str, Any]:
    """Resumen de una traza para tablas: sin contenido, solo metadatos."""
    events = sorted(
        (e for e in report.events if isinstance(e.get("seq"), int)),
        key=lambda e: e["seq"],
    )
    summary: dict[str, Any] = {
        "trace_id": report.trace_id,
        "date": report.date,
        "time": _time(events[0].get("timestamp")) if events else "—",
        "channel": "—",
        "requested_model": None,
        "returned_model": None,
        "input_tokens": None,
        "output_tokens": None,
        "outputs": 0,
        "errors": [],
        "reviews": 0,
        "issues": report.issues,
        "status": "sin eventos",
    }
    for e in events:
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        etype = e.get("event_type")
        if etype == "input_received":
            summary["channel"] = payload.get("channel", "—")
        elif etype == "model_called" and summary["requested_model"] is None:
            summary["requested_model"] = payload.get("requested_model")
            summary["returned_model"] = payload.get("returned_model")
            summary["input_tokens"] = payload.get("input_tokens")
            summary["output_tokens"] = payload.get("output_tokens")
        elif etype == "output_emitted":
            summary["outputs"] += 1
        elif etype == "error":
            summary["errors"].append(
                {
                    "code": payload.get("error_code"),
                    "recoverable": payload.get("recoverable"),
                }
            )
        elif etype == "human_review":
            summary["reviews"] += 1

    # Rendimiento (§4.4): la primera llamada a la API de la traza que lo registre
    summary["duration_ms"] = None
    summary["connection_reused"] = None
    for e in events:
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        if e.get("event_type") in EXCHANGE_TYPES and _is_count(
            payload.get("duration_ms")
        ):
            summary["duration_ms"] = payload["duration_ms"]
            reused = payload.get("connection_reused")
            summary["connection_reused"] = reused if isinstance(reused, bool) else None
            break

    if summary["errors"]:
        codes = {err["code"] for err in summary["errors"]}
        summary["status"] = "bloqueada" if "BLOCKED_BY_GUARD" in codes else "error"
    elif summary["outputs"]:
        summary["status"] = "ok"
    elif events:
        summary["status"] = "sin salida"
    return summary


def find_trace(
    reports: list[TraceReport], prefix: str
) -> tuple[TraceReport | None, str]:
    """Busca por id completo o prefijo único. Devuelve (informe, mensaje de error)."""
    matches = [r for r in reports if r.trace_id.startswith(prefix)]
    if not matches:
        return None, f"No hay ninguna traza que empiece por «{prefix}»."
    if len(matches) > 1:
        ids = ", ".join(m.trace_id[:12] for m in matches[:5])
        return None, f"El prefijo «{prefix}» es ambiguo: {ids}…"
    return matches[0], ""


def _perf_suffix(payload: dict[str, Any]) -> str:
    """Métricas de rendimiento de un evento (§4.4), solo si existen."""
    if not _is_count(payload.get("duration_ms")):
        return ""
    reused = payload.get("connection_reused")
    conn = (
        "—" if not isinstance(reused, bool) else ("reutilizada" if reused else "nueva")
    )
    http = payload.get("http_status", "—")
    return f" latencia={payload['duration_ms']} ms ttfb={payload.get('ttfb_ms', '—')} ms http={http} conexión={conn}"


def _event_summary(event: dict[str, Any]) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    etype = event.get("event_type")
    if etype == "input_received":
        return f"canal={payload.get('channel', '—')} hash={_short_hash(payload.get('content_hash'))}"
    if etype == "model_called":
        tokens = (
            f"{payload.get('input_tokens', '—')}/{payload.get('output_tokens', '—')}"
        )
        return (
            f"pedido={payload.get('requested_model', '—')} "
            f"devuelto={payload.get('returned_model', '—')} "
            f"tokens(in/out)={tokens} respuesta={_short_hash(payload.get('output_hash'))}"
            f"{_perf_suffix(payload)}"
        )
    if etype == "output_emitted":
        return f"destino={payload.get('destination', '—')} hash={_short_hash(payload.get('output_hash'))}"
    if etype == "error":
        return (
            f"código={payload.get('error_code', '—')} "
            f"recuperable={payload.get('recoverable', '—')}"
            f"{_perf_suffix(payload)}"
        )
    if etype == "verification_run":
        return f"{payload.get('check_name', '—')}={payload.get('result', '—')}"
    if etype == "human_review":
        return f"revisor={payload.get('reviewer_id', '—')} decisión={payload.get('decision', '—')}"
    return ""


def render_recent_table(reports: list[TraceReport], limit: int = RECENT_DEFAULT) -> str:
    """Tabla de las últimas trazas, en texto plano para la terminal."""
    if not reports:
        return "   (no hay trazas)\n"
    ordered = sorted(reports, key=lambda r: (r.date, r.trace_id))[-limit:]
    rows = [summarize_trace(r) for r in ordered]
    header = f"   {'fecha':<10} {'hora':<8} {'traza':<10} {'modelo pedido':<22} {'devuelto':<26} {'tokens in/out':<14} {'estado':<9} incid."
    lines = [header, "   " + "-" * (len(header) - 3)]
    for r in rows:
        tokens = f"{r['input_tokens'] or '—'}/{r['output_tokens'] or '—'}"
        lines.append(
            f"   {r['date']:<10} {r['time']:<8} {r['trace_id'][:8]:<10} "
            f"{str(r['requested_model'] or '—'):<22} {str(r['returned_model'] or '—'):<26} "
            f"{tokens:<14} {r['status']:<9} {len(r['issues'])}"
        )
    return "\n".join(lines) + "\n"


def render_detail(report: TraceReport) -> str:
    """Línea de tiempo de una traza, para leerla en la terminal."""
    summary = summarize_trace(report)
    out = [
        f"🔎 Traza {report.trace_id}",
        f"   Fecha {report.date} · estado {summary['status']} · canal {summary['channel']}",
        "",
    ]
    for e in sorted(
        (x for x in report.events if isinstance(x.get("seq"), int)),
        key=lambda x: x["seq"],
    ):
        parent = e.get("parent_event_id")
        out.append(
            f"   {e['seq']:>2}  {_time(e.get('timestamp'))}  {str(e.get('event_type')):<20}"
            f" {str(e.get('actor')):<15} {_event_summary(e)}"
            + (f"  ← {str(parent)[:8]}" if parent else "")
        )
    if report.issues:
        out.append("")
        out.append("   ⚠️  Incidencias:")
        out.extend(f"      - {issue}" for issue in report.issues)
    return "\n".join(out) + "\n"


def review_items(reports: list[TraceReport]) -> list[str]:
    """Lo que un revisor debe mirar, en frases cortas."""
    stats = compute_stats(reports)
    items: list[str] = []
    if stats["traces_with_issues"]:
        items.append(
            f"🛑 {stats['traces_with_issues']} trazas con incidencias de integridad: "
            "revisar su detalle antes de dar por buena la auditoría."
        )
    if stats["outputs_without_review"]:
        items.append(
            f"📤 {stats['outputs_without_review']} salidas sin revisión humana. "
            "El proxy no registra revisiones: cada salida necesita revisión fuera del sistema."
        )
    for code, count in stats["errors_by_code"].items():
        items.append(f"⚠️ {count} errores `{code}`.")
    for pair, count in stats["model_version_pairs"].items():
        items.append(f"🔄 {count} llamadas con versión distinta a la pedida: {pair}.")
    if stats["model_version_unknown"]:
        items.append(
            f"❔ {stats['model_version_unknown']} llamadas en las que la API no devolvió modelo."
        )
    return items


def render_markdown(
    reports: list[TraceReport], trace_dir: Path, now: datetime | None = None
) -> str:
    """Informe Markdown completo, pensado para revisarse con calma."""
    stats = compute_stats(reports)
    generated = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    dates = sorted({r.date for r in reports})
    period = f"{dates[0]} → {dates[-1]}" if dates else "sin trazas"
    out: list[str] = [
        "# 🧾 Informe de trazas de IA",
        "",
        f"- **Generado:** {generated}",
        f"- **Directorio:** `{trace_dir}`",
        f"- **Periodo:** {period}",
        "- **Especificación:** `docs/trazabilidad.md` (v0.1)",
        "",
        "## 📊 Resumen",
        "",
        "| Indicador | Valor |",
        "|---|---|",
        f"| Trazas | {stats['traces_total']} |",
        f"| Válidas | {stats['traces_valid']} |",
        f"| Con incidencias | {stats['traces_with_issues']} |",
        f"| Llamadas al modelo | {stats['model_calls']} |",
        f"| Versión devuelta ≠ pedida | {stats['model_version_drift']} |",
        f"| Versión no devuelta | {stats['model_version_unknown']} |",
        f"| Salidas emitidas | {stats['outputs_emitted']} |",
        f"| Salidas sin revisión humana | {stats['outputs_without_review']} |",
        f"| Errores | {sum(stats['errors_by_code'].values())} |",
        f"| Latencia p95 | {_cell(_ms_cell(stats['performance'].get('duration_ms'), 'p95'))} |",
        f"| Cobertura de rendimiento | {_cell(_pct_cell(stats['performance'].get('coverage_pct')))} |",
        "",
        "## 🔍 Para revisar",
        "",
    ]
    items = review_items(reports)
    (
        out.extend(f"- {item}" for item in items)
        if items
        else out.append("- ✅ Nada pendiente de revisar.")
    )

    out += ["", "## ⏱️ Rendimiento y conexión", ""]
    out.extend(
        f"- {line.strip()}"
        for line in render_performance_lines(stats["performance"]).splitlines()
    )
    out.append("")
    out.append(
        "_Cobertura = llamadas con `duration_ms` / llamadas a la API. "
        "Las trazas anteriores a la métrica cuentan como «sin dato»._"
    )

    out += ["", "## 🗂️ Trazas", ""]
    if not reports:
        out.append("_No hay trazas en el periodo._")
    else:
        out += [
            "| Fecha | Hora | Traza | Canal | Modelo pedido | Modelo devuelto | Tokens in/out | Latencia | Estado | Incidencias |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in sorted(reports, key=lambda r: (r.date, r.trace_id)):
            s = summarize_trace(r)
            out.append(
                f"| {_cell(s['date'])} | {_cell(s['time'])} | `{s['trace_id'][:8]}` | "
                f"{_cell(s['channel'])} | {_cell(s['requested_model'])} | "
                f"{_cell(s['returned_model'])} | "
                f"{_cell(s['input_tokens'])}/{_cell(s['output_tokens'])} | "
                f"{_cell(_ms_text(s['duration_ms']))} | "
                f"{_cell(s['status'])} | {len(s['issues'])} |"
            )

        out += ["", "## 📜 Detalle por traza", ""]
        for r in sorted(reports, key=lambda r: (r.date, r.trace_id)):
            s = summarize_trace(r)
            out += [
                f"### `{r.trace_id}`",
                "",
                f"{r.date} {s['time']} UTC · estado **{s['status']}**",
                "",
            ]
            out += ["| # | Hora | Tipo | Actor | Resumen |", "|---|---|---|---|---|"]
            for e in sorted(
                (x for x in r.events if isinstance(x.get("seq"), int)),
                key=lambda x: x["seq"],
            ):
                out.append(
                    f"| {e['seq']} | {_cell(_time(e.get('timestamp')))} | "
                    f"{_cell(e.get('event_type'))} | {_cell(e.get('actor'))} | "
                    f"{_cell(_event_summary(e))} |"
                )
            if r.issues:
                out += ["", "**Incidencias:**", ""]
                out.extend(f"- {_cell(issue)}" for issue in r.issues)
            out.append("")

    out += [
        "---",
        "",
        "_Informe generado por `klaus-trazas`. Solo contiene metadatos y hashes: "
        "el contenido de las conversaciones no está en las trazas._",
        "",
    ]
    return "\n".join(out)


def write_private(path: Path, content: str) -> None:
    """Escribe el informe con permisos 0600 (§5: solo el administrador)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.chmod(path, 0o600)


def default_report_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path.home() / ".klaus-proxy" / "logs" / "informes" / f"trazas-{stamp}.md"


# ── Plan de auditoría para el dashboard (issue #226) ───────────────────────

MAX_DETAIL_TRACES = 200  # trazas con línea de tiempo en el dashboard
RECENT_TRACES = 10  # filas en la tabla de recientes


def _timeline(report: TraceReport) -> list[dict[str, Any]]:
    """Línea de tiempo de una traza: solo metadatos y resúmenes sin contenido."""
    rows = []
    for e in sorted(
        (x for x in report.events if isinstance(x.get("seq"), int)),
        key=lambda x: x["seq"],
    ):
        rows.append(
            {
                "seq": e["seq"],
                "time": _time(e.get("timestamp")),
                "type": str(e.get("event_type")),
                "actor": str(e.get("actor")),
                "summary": _event_summary(e),
            }
        )
    return rows


def audit_traces(trace_dir: Path) -> dict[str, Any]:
    """Plan ``traces`` del dashboard: estado, cifras, puntos a revisar y detalle."""
    from Klaus_proxy_local.trace_stats import scan_traces

    reports = scan_traces(trace_dir)
    if not reports:
        return {
            "status": "no_data",
            "trace_dir": str(trace_dir),
            "total": 0,
            "valid": 0,
            "with_issues": 0,
            "model_calls": 0,
            "model_unknown": 0,
            "model_drift": 0,
            "outputs": 0,
            "outputs_without_review": 0,
            "errors": 0,
            "performance": {},
            "review_items": [],
            "recent": [],
            "details": [],
        }

    stats = compute_stats(reports)
    items = review_items(reports)
    if stats["traces_with_issues"]:
        status = "critical"
    elif stats["outputs_without_review"] or stats["model_version_unknown"]:
        status = "warning"
    else:
        status = "good"

    ordered = sorted(reports, key=lambda r: (r.date, r.trace_id), reverse=True)
    recent = [summarize_trace(r) for r in ordered[:RECENT_TRACES]]
    details = []
    for r in ordered[:MAX_DETAIL_TRACES]:
        s = summarize_trace(r)
        details.append(
            {
                "trace_id": r.trace_id,
                "date": r.date,
                "time": s["time"],
                "status": s["status"],
                "channel": s["channel"],
                "requested_model": s["requested_model"],
                "returned_model": s["returned_model"],
                "input_tokens": s["input_tokens"],
                "output_tokens": s["output_tokens"],
                "duration_ms": s["duration_ms"],
                "connection_reused": s["connection_reused"],
                "issues": r.issues[:MAX_ISSUES_SHOWN],
                "issue_count": len(r.issues),
                "timeline": _timeline(r),
            }
        )

    return {
        "status": status,
        "trace_dir": str(trace_dir),
        "total": stats["traces_total"],
        "valid": stats["traces_valid"],
        "with_issues": stats["traces_with_issues"],
        "model_calls": stats["model_calls"],
        "model_unknown": stats["model_version_unknown"],
        "model_drift": stats["model_version_drift"],
        "outputs": stats["outputs_emitted"],
        "outputs_without_review": stats["outputs_without_review"],
        "errors": sum(stats["errors_by_code"].values()),
        "performance": stats["performance"],
        "review_items": items,
        "recent": [
            {
                "trace_id": s["trace_id"],
                "date": s["date"],
                "time": s["time"],
                "requested_model": s["requested_model"],
                "returned_model": s["returned_model"],
                "input_tokens": s["input_tokens"],
                "output_tokens": s["output_tokens"],
                "duration_ms": s["duration_ms"],
                "status": s["status"],
                "issues": len(s["issues"]),
            }
            for s in recent
        ],
        "details": details,
    }
