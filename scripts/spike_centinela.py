#!/usr/bin/env python3
"""Spike #185: coste y ruido de un centinela de fugas (#184).

Para cada petición de los últimos N días, analiza SOLO el texto nuevo (el último
mensaje: turno del usuario y tool_result) con los detectores de klaus-scan y
mide:

- Tiempo de detección por petición (p50 / p95).
- Avisos: valores detectados que el proxy NO cubriría con sus reglas actuales.
  Un mismo valor cuenta una vez por «sesión» (mismo directorio de trabajo y día).

Solo lectura: no escribe en captures/, en el vault ni en config.json.

Sin ``--reveal`` no imprime ningún valor, solo identificadores
``⟨categoría·hash·longitud⟩``. ``--reveal`` muestra una muestra aleatoria con
contexto para la revisión manual de falsos positivos. Ejecútalo SOLO en tu
terminal, nunca desde Claude Code: lo que se imprime en una sesión llega al
modelo.

Uso:
    python3 scripts/spike_centinela.py                 # métricas, sin valores
    python3 scripts/spike_centinela.py --days 7 --reveal --sample 30   # tu terminal
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import anthropic_pair_verify as pv  # noqa: E402
from Klaus_proxy_local import capture_retention, scan_repos  # noqa: E402
from Klaus_proxy_local import leak_report as lr  # noqa: E402
from Klaus_proxy_local.business_names import detect_line  # noqa: E402
from Klaus_proxy_local.scan import safe_id  # noqa: E402
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner  # noqa: E402

CONTEXT = 30
# Orden de confianza. Decisión #185: el centinela avisa de todo salvo LOW
RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def detect(text: str, scanner: SensitiveDataScanner) -> list[tuple[str, str, str, str]]:
    """``(valor, categoría, confianza, contexto)`` con los detectores de klaus-scan."""
    hits: list[tuple[str, str, str, str]] = []
    for f in scanner.pattern_detector.detect(text, Path("."), 0):
        hits.append((f.value, f.category, "CRITICAL", f.context))
    for line in text.splitlines():
        for value, category, conf, _reason in detect_line(line):
            hits.append((value, category, conf, line))
    return hits


def requests(captures_dir: Path, since: datetime):
    """Peticiones de conversación de la ventana: (nombre, sesión, último mensaje)."""
    for opath in sorted((captures_dir / "original").glob("*.json")):
        try:
            rec = pv.load_capture(opath)
        except (OSError, ValueError):
            continue
        if not str(rec.get("path") or "").startswith("/v1/messages"):
            continue
        try:
            when = datetime.fromisoformat(str(rec.get("captured_at", ""))[:19])
        except ValueError:
            continue
        if when < since:
            continue
        payload = rec.get("payload") or {}
        msgs = payload.get("messages") or []
        if not msgs:
            continue
        session = (lr.capture_cwd(payload) or "sin-cwd", when.date().isoformat())
        last = {"payload": {"messages": [msgs[-1]]}}
        yield opath.name, session, pv.message_text(last)


def pct(data: list[float], q: int) -> float:
    if len(data) < 2:
        return data[0] if data else 0.0
    return statistics.quantiles(data, n=100)[q - 1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--captures-dir", help="por defecto, el de claude-proxy")
    ap.add_argument(
        "--reveal", action="store_true", help="muestra valores (solo terminal)"
    )
    ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--min-confidence", default="MEDIUM", choices=list(RANK))
    ap.add_argument("--seed", type=int, default=185)
    args = ap.parse_args(argv)

    config = scan_repos.load_config()
    captures = (
        Path(args.captures_dir).expanduser()
        if args.captures_dir
        else capture_retention.captures_dir(config)
    )
    since = datetime.now() - timedelta(days=args.days)

    coverage = lr.Coverage(captures)
    scanner = SensitiveDataScanner(enable_business=False)

    floor = RANK[args.min_confidence]
    detect_ms: list[float] = []
    all_uncovered = 0  # sin filtro de confianza, para comparar
    covers_ms: list[float] = []
    n_requests = 0
    n_with_hits = 0
    uncovered_total = 0
    per_session: dict[tuple, set[str]] = defaultdict(set)
    by_category: Counter = Counter()
    by_id: Counter = Counter()
    samples: list[dict] = []
    rng = random.Random(args.seed)

    for name, session, text in requests(captures, since):
        n_requests += 1
        t0 = time.perf_counter_ns()
        hits = detect(text, scanner) if text else []
        t1 = time.perf_counter_ns()
        detect_ms.append((t1 - t0) / 1e6)

        t2 = time.perf_counter_ns()
        uncovered = [h for h in hits if not coverage.covers(h[0])]
        all_uncovered += len(uncovered)
        uncovered = [h for h in uncovered if RANK[h[2]] >= floor]
        covers_ms.append((time.perf_counter_ns() - t2) / 1e6)

        if hits:
            n_with_hits += 1
        for value, category, _conf, context in uncovered:
            sid = safe_id(value, category)
            uncovered_total += 1
            by_category[category] += 1
            by_id[sid] += 1
            per_session[session].add(sid)
            samples.append(
                {
                    "id": sid,
                    "category": category,
                    "context": context,
                    "capture": name,
                    "value": value,
                }
            )

    total_ms = [a + b for a, b in zip(detect_ms, covers_ms)]
    avisos_por_sesion = [len(v) for v in per_session.values()]

    print("── Spike #185: centinela de fugas ──")
    print(f"Ventana: últimos {args.days} días · capturas: {captures}")
    print(f"Peticiones analizadas: {n_requests}")
    print(f"Con algún valor detectado: {n_with_hits}")
    print(f"Valores sin cubrir, todas las confianzas: {all_uncovered}")
    print(f"Valores sin cubrir, desde {args.min_confidence}: {uncovered_total}")
    print()
    print("⏱  Tiempo por petición (ms)")
    print(f"   detección   p50={pct(detect_ms, 50):.2f}  p95={pct(detect_ms, 95):.2f}")
    print(f"   cobertura   p50={pct(covers_ms, 50):.2f}  p95={pct(covers_ms, 95):.2f}")
    print(f"   total       p50={pct(total_ms, 50):.2f}  p95={pct(total_ms, 95):.2f}")
    print()
    print("🔔 Avisos por sesión (valores distintos, sesión = cwd + día)")
    if avisos_por_sesion:
        print(f"   sesiones con aviso: {len(avisos_por_sesion)}")
        print(
            f"   mediana={statistics.median(avisos_por_sesion):.1f}  máx={max(avisos_por_sesion)}"
        )
    else:
        print("   ninguna")
    print()
    print("📂 Avisos por categoría")
    for cat, n in by_category.most_common():
        print(f"   {cat:<20} {n}")
    print()
    print(
        "🔁 Valores más repetidos (id, nº de peticiones) — un valor que sale en muchos proyectos suele ser ruido"
    )
    for sid, n in by_id.most_common(15):
        print(f"   {sid}  {n}")

    if args.reveal:
        rng.shuffle(samples)
        print()
        print(
            f"🧪 Muestra para revisar a mano ({min(args.sample, len(samples))} de {len(samples)})"
        )
        print("   Marca cada una: V = dato sensible real · F = falso positivo")
        for s in samples[: args.sample]:
            ctx = s["context"]
            i = ctx.find(s["value"])
            lo = max(0, i - CONTEXT)
            snippet = ctx[lo : i + len(s["value"]) + CONTEXT].replace("\n", " ")
            print(f"   [{s['id']}] {snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
