#!/usr/bin/env python3
"""Ejemplo de integración del módulo de trazas (docs/trazabilidad.md §10.6).

AVISO: simula un flujo de asistente con recuperación y revisión humana.
No llama a ningún modelo ni a ninguna API: los valores son ficticios.

Uso (desde la raíz del repo, con el paquete instalado o con PYTHONPATH=src):

    python3 scripts/ejemplo_trazas.py --dir /tmp/trazas-demo
    klaus-trazas --dir /tmp/trazas-demo
"""

import argparse
from pathlib import Path

from Klaus_proxy_local.trazas import end_trace, record_event, start_trace


def run_demo(trace_dir: Path) -> str:
    """Ejecuta un flujo simulado y devuelve el trace_id generado."""
    ctx = start_trace(
        "¿Cuál es la política de retención de logs?", channel="api", trace_dir=trace_dir
    )
    record_event(
        ctx,
        "retrieval_performed",
        {
            "query": "política de retención de logs",
            "index_name": "docs-internos",
            "sources": [
                {
                    "source_id": "doc-112",
                    "version": "v3.2",
                    "content_hash": "sha256:91ab",
                }
            ],
        },
    )
    record_event(
        ctx,
        "model_called",
        {
            "requested_model": "modelo-ejemplo-x",
            "returned_model": "modelo-ejemplo-x-2026-09",
            "provider": "proveedor-ejemplo",
            "temperature": 0.2,
            "input_tokens": 812,
            "output_tokens": 146,
            "output_hash": "sha256:c07e",
        },
    )
    record_event(
        ctx,
        "verification_run",
        {
            "check_name": "cita_a_fuente",
            "check_version": "1.0",
            "result": "warn",
        },
    )
    review = record_event(
        ctx,
        "human_review",
        {
            "reviewer_id": "rev-07",
            "decision": "modified",
        },
    )
    record_event(
        ctx,
        "output_emitted",
        {
            "output_hash": "sha256:5d1b",
            "destination": "usuario-final",
        },
        parent_event_id=review,
    )
    end_trace(ctx, status="ok")
    return ctx.trace_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera una traza de ejemplo (sin modelos)."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="directorio de trazas (por defecto: logs/trazas)",
    )
    args = parser.parse_args()
    trace_id = run_demo(args.dir or Path("logs") / "trazas")
    print(f"Traza de ejemplo generada: {trace_id}")


if __name__ == "__main__":
    main()
