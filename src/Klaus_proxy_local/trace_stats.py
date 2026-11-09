"""klaus-trazas: estadísticas e integridad de las trazas de ejecuciones con IA.

Implementa la lectura y validación de la especificación ``docs/trazabilidad.md``
(v0.1): ficheros JSONL en ``logs/trazas/AAAA-MM-DD/<trace_id>.jsonl``, un evento
por línea. Es un comando de solo lectura: no escribe, no modifica ni borra
trazas (principio de solo adición, §3 y §5 de la especificación).

Qué muestra (derivado de §3, §4.2, §4.3 y §9 de la especificación):

- Trazas totales, por fecha, válidas y con incidencias de integridad.
- Eventos por ``event_type``.
- Llamadas al modelo en las que ``returned_model`` difiere de ``requested_model``.
- Verificaciones ``pass`` / ``warn`` / ``fail`` por ``check_name``.
- Revisiones humanas ``approved`` / ``rejected`` / ``modified``.
- Errores por ``error_code``, recuperables frente a no recuperables.
- Salidas emitidas sin revisión humana en la misma traza.

Nunca imprime valores de ``payload``: solo identificadores, contadores y tipos.

Interpretación de la especificación: §8 omite ``top_p`` y ``max_tokens`` en
``model_called``, así que solo se exigen como obligatorios los campos que la
traza de ejemplo incluye (ver ``REQUIRED_PAYLOAD``).
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TRACE_DIR = Path.home() / ".klaus-proxy" / "logs" / "trazas"
SCHEMA_VERSION = "0.1"

EVENT_TYPES = frozenset(
    {
        "input_received",
        "retrieval_performed",
        "prompt_built",
        "model_called",
        "tool_called",
        "agent_step",
        "verification_run",
        "human_review",
        "output_emitted",
        "error",
    }
)
ACTORS = frozenset({"user", "system", "model", "tool", "agent", "human_reviewer"})
CHECK_RESULTS = ("pass", "warn", "fail")
UNKNOWN_MODEL = "no_devuelto"  # valor de trazas cuando la API no devuelve modelo
MAX_ISSUES_SHOWN = 3  # incidencias guardadas por traza en el informe
MAX_TRACES_SHOWN = 10  # trazas con incidencias listadas en texto
REVIEW_DECISIONS = ("approved", "rejected", "modified")

COMMON_FIELDS = (
    "event_id",
    "trace_id",
    "parent_event_id",
    "seq",
    "timestamp",
    "event_type",
    "schema_version",
    "actor",
    "payload",
)

# Campos obligatorios de ``payload`` por tipo (§4.2).
REQUIRED_PAYLOAD: dict[str, tuple[str, ...]] = {
    "input_received": ("content_hash", "channel"),
    "retrieval_performed": ("query", "sources", "index_name"),
    "prompt_built": ("prompt_version", "template_id", "content_hash"),
    "model_called": ("requested_model", "returned_model", "provider", "output_hash"),
    "tool_called": ("tool_name", "tool_version", "input_hash", "output_hash", "status"),
    "agent_step": ("step_name", "plan_ref", "outcome"),
    "verification_run": ("check_name", "check_version", "result"),
    "human_review": ("reviewer_id", "decision"),
    "output_emitted": ("output_hash", "destination"),
    "error": ("error_code", "error_message", "recoverable"),
}


@dataclass
class TraceReport:
    """Resultado de leer y validar un fichero de traza."""

    path: Path
    date: str
    trace_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


# ── Validación de eventos (§4.1, §4.2) ──────────────────────────────────────


def validate_event(event: Any) -> list[str]:
    """Comprueba campos comunes y específicos de un evento. Devuelve incidencias."""
    if not isinstance(event, dict):
        return ["el evento no es un objeto JSON"]
    issues = []
    for name in COMMON_FIELDS:
        if name not in event:
            issues.append(f"falta el campo común '{name}'")
    if issues:
        return issues

    event_type = event["event_type"]
    if event_type not in EVENT_TYPES:
        issues.append(f"event_type desconocido: {event_type!r}")
    if event["actor"] not in ACTORS:
        issues.append(f"actor desconocido: {event['actor']!r}")
    if not isinstance(event["seq"], int) or isinstance(event["seq"], bool):
        issues.append("seq no es un entero")
    if not isinstance(event["payload"], dict):
        issues.append("payload no es un objeto")
        return issues

    for name in REQUIRED_PAYLOAD.get(event_type, ()):
        if name not in event["payload"]:
            issues.append(f"{event_type}: falta payload.{name}")

    if event_type == "verification_run":
        result = event["payload"].get("result")
        if result is not None and result not in CHECK_RESULTS:
            issues.append("verification_run: result fuera de pass/fail/warn")
    if event_type == "human_review":
        decision = event["payload"].get("decision")
        if decision is not None and decision not in REVIEW_DECISIONS:
            issues.append("human_review: decision fuera de approved/rejected/modified")
    return issues


# ── Reglas de integridad de una traza (§4.3) ────────────────────────────────


def validate_trace(events: list[dict[str, Any]]) -> list[str]:
    """Aplica las reglas de §4.3 a los eventos de una misma traza."""
    if not events:
        return ["la traza no tiene eventos"]
    issues = []

    trace_ids = {e.get("trace_id") for e in events}
    if len(trace_ids) > 1:
        issues.append("hay eventos de más de un trace_id en el mismo fichero")

    roots = [e for e in events if e.get("parent_event_id") is None]
    if len(roots) != 1:
        issues.append(
            f"la traza tiene {len(roots)} eventos raíz (debe tener exactamente 1)"
        )

    seqs = sorted(e.get("seq") for e in events if isinstance(e.get("seq"), int))
    if seqs != list(range(1, len(events) + 1)):
        issues.append("seq no es consecutivo desde 1 (hay huecos o duplicados)")

    event_ids = {e.get("event_id") for e in events}
    for e in events:
        parent = e.get("parent_event_id")
        if parent is not None and parent not in event_ids:
            issues.append(f"parent_event_id {parent} no existe en la traza")

    ordered = sorted(
        (e for e in events if isinstance(e.get("seq"), int)), key=lambda e: e["seq"]
    )
    seen_model = False
    for e in ordered:
        if e.get("event_type") == "model_called":
            seen_model = True
        if e.get("event_type") == "output_emitted" and not seen_model:
            issues.append("output_emitted sin model_called previo en la traza")
            break

    has_output = any(e.get("event_type") == "output_emitted" for e in events)
    for e in events:
        if (
            e.get("event_type") == "human_review"
            and e.get("payload", {}).get("decision") == "approved"
            and not has_output
        ):
            issues.append("human_review approved huérfano: no hay output_emitted")
            break
    return issues


# ── Lectura de ficheros ─────────────────────────────────────────────────────


def read_trace_file(path: Path) -> TraceReport:
    """Lee un JSONL de traza y reúne eventos e incidencias (sin imprimir payloads)."""
    report = TraceReport(path=path, date=path.parent.name, trace_id=path.stem)
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        report.issues.append(f"no se puede leer: {type(exc).__name__}")
        return report

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            report.issues.append(f"línea {number}: JSON no válido")
            continue
        for issue in validate_event(event):
            report.issues.append(f"línea {number}: {issue}")
        if isinstance(event, dict):
            events.append(event)

    report.events = events
    if events:
        # Las reglas de §4.3 se aplican también con errores de campo: pueden
        # dar avisos derivados, pero ayudan a localizar el problema.
        report.issues.extend(validate_trace(events))
    elif not report.issues:
        report.issues.append("la traza no tiene eventos")
    return report


def scan_traces(trace_dir: Path, date: str | None = None) -> list[TraceReport]:
    """Recorre ``trace_dir/AAAA-MM-DD/*.jsonl``. Filtra por fecha si se indica."""
    if not trace_dir.is_dir():
        return []
    reports = []
    for day_dir in sorted(p for p in trace_dir.iterdir() if p.is_dir()):
        if date is not None and day_dir.name != date:
            continue
        for path in sorted(day_dir.glob("*.jsonl")):
            reports.append(read_trace_file(path))
    return reports


def permissions_warning(trace_dir: Path) -> str | None:
    """§5: solo el rol administrador puede leer las trazas. Avisa si es legible por otros."""
    if not trace_dir.exists():
        return None
    mode = stat.S_IMODE(os.stat(trace_dir).st_mode)
    if mode & 0o077:
        return (
            f"⚠️  {trace_dir} es accesible por otros usuarios "
            f"({oct(mode)}). La especificación exige acceso solo al administrador."
        )
    return None


# ── Estadísticas ────────────────────────────────────────────────────────────


def compute_stats(reports: list[TraceReport]) -> dict[str, Any]:
    """Agrega las estadísticas a partir de los informes de cada traza."""
    by_date: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    checks: dict[str, Counter[str]] = defaultdict(Counter)
    decisions: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    errors_recoverable: Counter[str] = Counter()
    model_pairs: Counter[str] = Counter()
    model_calls = 0
    model_drift = 0
    model_unknown = 0
    outputs = 0
    outputs_unreviewed = 0
    valid = 0
    invalid_traces: list[dict[str, Any]] = []

    for report in reports:
        by_date[report.date] += 1
        if report.issues:
            invalid_traces.append(
                {
                    "trace_id": report.trace_id,
                    "date": report.date,
                    "issues": report.issues[:MAX_ISSUES_SHOWN],
                    "issue_count": len(report.issues),
                }
            )
        else:
            valid += 1

        has_review = False
        for e in report.events:
            etype = e.get("event_type")
            payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
            event_types[str(etype)] += 1

            if etype == "model_called":
                model_calls += 1
                requested = payload.get("requested_model")
                returned = payload.get("returned_model")
                if returned in (None, "", UNKNOWN_MODEL):
                    # La API no devolvió modelo: no es una versión distinta
                    model_unknown += 1
                elif requested != returned:
                    model_drift += 1
                    model_pairs[f"{requested} → {returned}"] += 1
            elif etype == "verification_run":
                checks[str(payload.get("check_name"))][str(payload.get("result"))] += 1
            elif etype == "human_review":
                has_review = True
                decisions[str(payload.get("decision"))] += 1
            elif etype == "error":
                code = str(payload.get("error_code"))
                errors[code] += 1
                if payload.get("recoverable") is True:
                    errors_recoverable[code] += 1
            elif etype == "output_emitted":
                outputs += 1
        if (
            any(e.get("event_type") == "output_emitted" for e in report.events)
            and not has_review
        ):
            outputs_unreviewed += sum(
                1 for e in report.events if e.get("event_type") == "output_emitted"
            )

    return {
        "traces_total": len(reports),
        "traces_valid": valid,
        "traces_with_issues": len(reports) - valid,
        "invalid_traces": invalid_traces,
        "traces_by_date": dict(sorted(by_date.items())),
        "events_total": sum(event_types.values()),
        "events_by_type": dict(event_types.most_common()),
        "model_calls": model_calls,
        "model_version_drift": model_drift,
        "model_version_unknown": model_unknown,
        "model_version_pairs": dict(model_pairs.most_common()),
        "verifications": {k: dict(v) for k, v in sorted(checks.items())},
        "human_reviews": dict(decisions),
        "errors_by_code": dict(errors.most_common()),
        "errors_recoverable": dict(errors_recoverable),
        "outputs_emitted": outputs,
        "outputs_without_review": outputs_unreviewed,
    }


# ── Presentación ────────────────────────────────────────────────────────────


def render_text(stats: dict[str, Any], warning: str | None = None) -> str:
    """Informe de texto para terminal."""
    out: list[str] = []
    add = out.append
    add("🧾 klaus-trazas — estadísticas de trazabilidad (especificación v0.1)")
    add("=" * 64)
    if warning:
        add(warning)
    add("")

    add("📁 Trazas")
    add(f"   Total:            {stats['traces_total']}")
    add(f"   Válidas:          {stats['traces_valid']}")
    add(f"   Con incidencias:  {stats['traces_with_issues']}")
    for bad in stats["invalid_traces"][:MAX_TRACES_SHOWN]:
        add(f"      ✖ {bad['date']}/{bad['trace_id']}")
        for issue in bad["issues"]:
            add(f"          - {issue}")
        if bad["issue_count"] > len(bad["issues"]):
            add(
                f"          … {bad['issue_count'] - len(bad['issues'])} incidencias más (usa --json)"
            )
    if len(stats["invalid_traces"]) > MAX_TRACES_SHOWN:
        add(
            f"      … y {len(stats['invalid_traces']) - MAX_TRACES_SHOWN} trazas más (usa --json)"
        )
    for day, count in stats["traces_by_date"].items():
        add(f"   {day}: {count}")
    add("")

    add(f"🧩 Eventos: {stats['events_total']}")
    for etype, count in stats["events_by_type"].items():
        add(f"   {etype:<22}{count}")
    add("")

    add("🤖 Modelo")
    add(f"   Llamadas:                    {stats['model_calls']}")
    add(f"   Versión devuelta ≠ pedida:   {stats['model_version_drift']}")
    add(f"   Versión no devuelta por la API: {stats.get('model_version_unknown', 0)}")
    for pair, count in stats["model_version_pairs"].items():
        add(f"      {pair}  ×{count}")
    add("")

    add("✅ Verificaciones")
    if not stats["verifications"]:
        add("   (ninguna)")
    for check, results in stats["verifications"].items():
        detail = "  ".join(f"{r}={results.get(r, 0)}" for r in CHECK_RESULTS)
        add(f"   {check:<24}{detail}")
    add("")

    add("👤 Revisión humana")
    if not stats["human_reviews"]:
        add("   (ninguna)")
    for decision in REVIEW_DECISIONS:
        if decision in stats["human_reviews"]:
            add(f"   {decision:<12}{stats['human_reviews'][decision]}")
    add("")

    add("⚠️  Errores")
    if not stats["errors_by_code"]:
        add("   (ninguno)")
    for code, count in stats["errors_by_code"].items():
        recov = stats["errors_recoverable"].get(code, 0)
        add(f"   {code:<24}{count}  (recuperables: {recov})")
    add("")

    add("📤 Salidas")
    add(f"   Emitidas:                    {stats['outputs_emitted']}")
    add(f"   Sin revisión humana previa:  {stats['outputs_without_review']}")
    return "\n".join(out) + "\n"


# ── CLI ─────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klaus-trazas",
        description=(
            "Estadísticas e integridad de las trazas de ejecuciones con IA "
            "(solo lectura). Ver docs/trazabilidad.md."
        ),
        epilog=(
            "Ejemplos:\n"
            "  klaus-trazas                       # todas las trazas (~/.klaus-proxy/logs/trazas)\n"
            "  klaus-trazas --date 2026-11-06    # solo un día\n"
            "  klaus-trazas --json               # salida JSON\n"
            "  klaus-trazas --strict             # código de salida 1 si hay incidencias"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_TRACE_DIR,
        help="directorio de trazas (por defecto: ~/.klaus-proxy/logs/trazas)",
    )
    parser.add_argument("--date", help="filtrar por fecha AAAA-MM-DD")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    parser.add_argument(
        "--traza",
        metavar="ID",
        help="detalle de una traza: id completo o prefijo único",
    )
    parser.add_argument(
        "--informe",
        nargs="?",
        const="",
        metavar="RUTA",
        help=(
            "exporta un informe Markdown para revisión humana "
            "(por defecto: ~/.klaus-proxy/logs/informes/trazas-<fecha>.md)"
        ),
    )
    parser.add_argument(
        "--ultimas",
        type=int,
        default=10,
        metavar="N",
        help="trazas recientes en la tabla del informe de terminal (0 = ninguna)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="devolver código 1 si alguna traza tiene incidencias",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from Klaus_proxy_local import trace_report as tr  # import tardío: evita ciclo

    args = build_parser().parse_args(argv)
    reports = scan_traces(args.dir, args.date)
    stats = compute_stats(reports)
    warning = permissions_warning(args.dir)

    if args.traza:
        found, error = tr.find_trace(reports, args.traza)
        if found is None:
            print(error, file=sys.stderr)
            return 1
        print(tr.render_detail(found), end="")
        return 1 if args.strict and found.issues else 0

    if args.informe is not None:
        path = (
            Path(args.informe).expanduser()
            if args.informe
            else tr.default_report_path()
        )
        tr.write_private(path, tr.render_markdown(reports, args.dir))
        print(f"Informe escrito en {path} (permisos 0600)")
        return 1 if args.strict and stats["traces_with_issues"] else 0

    if args.json:
        payload = dict(stats)
        if warning:
            payload["warning"] = warning
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not args.dir.is_dir():
            print(f"No existe el directorio de trazas: {args.dir}", file=sys.stderr)
            print("Usa --dir para indicar otro.", file=sys.stderr)
            return 1 if args.strict else 0
        print(render_text(stats, warning), end="")
        if args.ultimas > 0:
            print("🗂️  Trazas recientes")
            print(tr.render_recent_table(reports, args.ultimas), end="")
            print()

    if args.strict and stats["traces_with_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
