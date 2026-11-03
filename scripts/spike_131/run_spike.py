#!/usr/bin/env python3
"""Spike de la fase 0 de la versión servidor (#172, para #131).

Levanta un gateway de prueba (``mitmdump --mode reverse:https://api.anthropic.com``)
en ``127.0.0.1`` con el seudonimizador, el addon de medición y el guardián, y
lanza Claude Code contra él con la credencial que tenga configurada (login de
claude.ai o API key). Mide:

- R1: ¿la API acepta la credencial reenviada por el gateway?
- R2: ¿``ANTHROPIC_CUSTOM_HEADERS`` llega en todas las peticiones? Incluye una
  ejecución con token incorrecto, que el gateway debe rechazar.
- R3: tiempo de ``claude -p`` por el gateway frente al camino actual
  (``HTTPS_PROXY`` del proxy local, si está definido).

Todo se escribe en un directorio temporal (vault incluido, vía
``ANTHROPIC_PSEUDO_VAULT``). No guarda cuerpos ni credenciales.

Uso:
    python3 scripts/spike_131/run_spike.py [--runs 3] [--keep]

Variables: ``MITMDUMP`` (ruta a mitmdump), ``CLAUDE_BIN`` (ruta a claude).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PROBE = Path(__file__).resolve().parent / "gateway_probe.py"
PROMPT = "Responde exactamente con la palabra: ok"
PORT = 18899


def _mitmdump() -> str:
    for cand in (
        os.environ.get("MITMDUMP"),
        str(Path.home() / ".local/share/klaus/venv/bin/mitmdump"),
        shutil.which("mitmdump"),
    ):
        if cand and Path(cand).exists():
            return cand
    sys.exit("No encuentro mitmdump: define MITMDUMP")


def _wait_port(port: int, timeout: float = 20.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    sys.exit(f"El gateway no abrió el puerto {port}")


def _claude(cwd: Path, env: dict[str, str], timeout: int = 180) -> dict:
    claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [claude, "-p", PROMPT],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "exit": "timeout",
            "wall_ms": round((time.perf_counter() - t0) * 1000),
            "answer_ok": False,
            "stderr_head": "",
            "stdout_head": "",
        }
    return {
        "exit": proc.returncode,
        "wall_ms": round((time.perf_counter() - t0) * 1000),
        "answer_ok": "ok" in proc.stdout.strip().lower()[:20],
        # Solo el principio del error, para diagnosticar; nunca la salida entera
        "stderr_head": proc.stderr.strip()[:200],
        "stdout_head": proc.stdout.strip()[:80],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--keep", action="store_true", help="No borrar el directorio")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="klaus-spike-"))
    cwd = work / "cwd"
    cwd.mkdir()
    token = secrets.token_hex(16)
    probe_out = work / "probe.jsonl"
    gw_env = {
        **os.environ,
        "ANTHROPIC_PSEUDO_VAULT": str(work / "vault.json"),
        "SPIKE_OUT": str(probe_out),
        "SPIKE_TOKEN": token,
        "SPIKE_ENFORCE": "1",
    }
    log = (work / "gateway.log").open("w")
    gateway = subprocess.Popen(
        [
            _mitmdump(),
            "--mode",
            "reverse:https://api.anthropic.com",
            "--listen-host",
            "127.0.0.1",
            "-p",
            str(PORT),
            "--set",
            "flow_detail=0",
            "-s",
            str(SRC / "anthropic_payload_pseudonymize.py"),
            "-s",
            str(PROBE),
            "-s",
            str(SRC / "klaus_pseudo_guard.py"),
        ],
        env=gw_env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    results: dict = {"runs": args.runs, "via_gateway": [], "baseline": []}
    try:
        _wait_port(PORT)
        base_url = f"http://127.0.0.1:{PORT}"
        client = {
            **os.environ,
            "ANTHROPIC_BASE_URL": base_url,
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
        for _ in range(args.runs):
            env = {**client, "ANTHROPIC_CUSTOM_HEADERS": f"X-Klaus-Token: {token}"}
            results["via_gateway"].append(_claude(cwd, env))
        bad = {**client, "ANTHROPIC_CUSTOM_HEADERS": "X-Klaus-Token: incorrecto"}
        results["wrong_token"] = _claude(cwd, bad, timeout=90)
        if os.environ.get("HTTPS_PROXY"):
            for _ in range(args.runs):
                results["baseline"].append(_claude(cwd, dict(os.environ)))
    finally:
        gateway.terminate()
        try:
            gateway.wait(10)
        except subprocess.TimeoutExpired:
            gateway.kill()
        log.close()

    probes = []
    if probe_out.exists():
        probes = [json.loads(line) for line in probe_out.read_text().splitlines()]
    results["probes"] = probes

    def median(rows: list[dict]) -> int | None:
        ok = [r["wall_ms"] for r in rows if r["exit"] == 0]
        return round(statistics.median(ok)) if ok else None

    results["summary"] = {
        "gateway_ok": sum(
            r["exit"] == 0 and r["answer_ok"] for r in results["via_gateway"]
        ),
        "gateway_median_ms": median(results["via_gateway"]),
        "baseline_median_ms": median(results["baseline"]),
        "wrong_token_rejected": results["wrong_token"]["exit"] != 0,
        "requests": len(probes),
        "statuses": sorted({p.get("status") for p in probes}, key=str),
        "token_states": sorted({p["klaus_token"] for p in probes}),
        "token_forwarded_upstream": any(p["klaus_token_forwarded"] for p in probes),
        "auth_schemes": sorted({str(p["auth_scheme"]) for p in probes}),
        "oauth_beta": any(p["oauth_beta"] for p in probes),
        "x_api_key": any(p["has_x_api_key"] for p in probes),
        "home_in_clear": any(p["home_in_clear"] for p in probes),
        "user_in_clear": any(p["user_in_clear"] for p in probes),
        "paths": sorted({f"{p['method']} {p['path']}" for p in probes}),
    }
    out = work / "results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(json.dumps(results["summary"], indent=2, ensure_ascii=False))
    print(f"📄 {out}")
    if not args.keep:
        # El vault temporal tiene valores reales: no se deja en disco
        (work / "vault.json").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
