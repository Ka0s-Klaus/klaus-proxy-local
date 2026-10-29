#!/usr/bin/env python3
"""generate_audit_dashboard.py — Klaus Proxy Local Audit Dashboard Generator #34

Lee las capturas de ~/.klaus-proxy/captures/, ejecuta 5 planes de auditoría
y guarda el informe en informes/ (#77): audit-<fecha>.json + .html, index.js
y audit-dashboard.html (el último). Cada HTML tiene un selector de informes y
los cambios respecto al anterior; se abre directamente con file://.

Uso:
    python3 scripts/generate_audit_dashboard.py [--captures-dir PATH] [--reports-dir PATH]
    python3 scripts/generate_audit_dashboard.py --open
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from Klaus_proxy_local import audit_reports  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _captures(captures_dir: Path) -> tuple[list[dict], list[dict]]:
    original, sent = [], []
    for f in sorted((captures_dir / "original").glob("*.json")):
        d = _load_json(f)
        if d:
            d["_file"] = f.name
            original.append(d)
    for f in sorted((captures_dir / "sent").glob("*.json")):
        d = _load_json(f)
        if d:
            sent.append(d)
    return original, sent


def _ts_to_date(ts_str: str | None) -> str | None:
    return ts_str[:10] if ts_str else None


# ──────────────────────────────────────────────────────────────────────────────
# Audit Plan 1 — Seguridad
# ──────────────────────────────────────────────────────────────────────────────


def _load_expected_hosts() -> set[str]:
    """Lee los hosts esperados desde config.json. Fallback: solo api.anthropic.com."""
    try:
        cfg_path = Path.home() / ".klaus-proxy" / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            hosts = [h.strip().lower() for h in cfg.get("hosts", []) if h.strip()]
            if hosts:
                return set(hosts)
    except Exception:
        pass
    return {"api.anthropic.com"}


EXPECTED_HOSTS = _load_expected_hosts()

# Con \s+ entre palabras: además de admitir varios espacios o saltos de
# línea, el código fuente no contiene las frases literales y leerlo no
# dispara el detector (#86).
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"act\s+as\s+(?:a\s+)?(?:different|new|another)",
    r"jail\s*break",
    r"DAN\s+mode",
    r"forget\s+(?:your\s+)?(?:instructions|rules)",
    r"you\s+are\s+now",
    r"disregard\s+(?:your\s+)?(?:previous|system)",
    r"override\s+(?:your\s+)?(?:instructions|rules)",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_INJECTION_CONTEXT = 80  # caracteres de contexto a cada lado de la coincidencia


_SOURCE_KEYS = ("file_path", "url", "command", "path", "pattern", "query")


def _tool_source(tool_input: object) -> str:
    """De dónde salió el resultado de una herramienta: fichero, URL, comando…"""
    if not isinstance(tool_input, dict):
        return ""
    for key in _SOURCE_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            value = " ".join(value.split())
            if len(value) <= 120:
                return value
            # En una ruta lo que identifica la fuente es el final (el fichero);
            # en un comando o una URL, el principio.
            if key in ("file_path", "path"):
                return "…" + value[-119:]
            return value[:119] + "…"
    return ""


def _user_texts(payload: dict, path: str):
    """Textos de los mensajes de rol "user" con su origen (#86).

    Solo el rol "user", para evitar falsos positivos del system prompt (que
    describe estos ataques). Los resultados de
    herramientas sí se analizan: es por donde entra un injection real
    (ficheros, webs), y se etiquetan con el nombre de la herramienta.
    """
    messages = [m for m in payload.get("messages", []) if isinstance(m, dict)]
    tools = {
        b.get("id"): (b.get("name", "?"), _tool_source(b.get("input")))
        for m in messages
        if isinstance(m.get("content"), list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_use"
    }
    text_origin = (
        "contenido enviado a count_tokens"
        if "count_tokens" in path
        else "mensaje del usuario"
    )
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            yield text_origin, "", content
            continue
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                yield text_origin, "", b.get("text", "")
            elif b.get("type") == "tool_result":
                inner = b.get("content")
                if isinstance(inner, list):
                    inner = "\n".join(
                        x.get("text", "") for x in inner if isinstance(x, dict)
                    )
                tool, source = tools.get(b.get("tool_use_id"), ("herramienta", ""))
                yield f"resultado de {tool}", source, str(inner or "")


def _injection_matches(cap: dict) -> dict[str, dict]:
    """Coincidencias de una captura: una por bloque de texto distinto (#86).

    La clave es el hash del bloque, así que un fichero o una salida de
    herramienta reenviados en el historial se reconocen como el mismo.
    """
    payload = cap.get("payload")
    if not isinstance(payload, dict):
        return {}
    path = cap.get("path", "")
    found: dict[str, dict] = {}
    for origin, source, text in _user_texts(payload, path):
        matches = list(_INJECTION_RE.finditer(text))
        if not matches:
            continue
        key = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        if key in found:
            continue
        first = matches[0]
        start = max(0, first.start() - _INJECTION_CONTEXT)
        end = first.end() + _INJECTION_CONTEXT
        found[key] = {
            "id": key[:12],
            "captured_at": cap.get("captured_at", "?")[:19],
            "file": cap.get("_file", ""),
            "path": path.split("?")[0],
            "origin": origin,
            "source": source,
            "patterns": sorted({m.group(0).lower() for m in matches}),
            "match": first.group(0),
            "before": ("…" if start else "")
            + " ".join(text[start : first.start()].split()),
            "after": " ".join(text[first.end() : end].split())
            + ("…" if end < len(text) else ""),
            "requests": 1,
        }
    return found


def load_reviewed_injections(config_dir: Path) -> dict[str, str]:
    """Avisos de injection marcados como revisados: {id: nota} (#86)."""
    cfg = _load_json(config_dir / "config.json")
    reviewed = cfg.get("audit_injection_reviewed") if isinstance(cfg, dict) else None
    if not isinstance(reviewed, dict):
        return {}
    return {str(k): str(v or "") for k, v in reviewed.items()}


def mark_injections_reviewed(config_dir: Path, ids: list[str], note: str) -> None:
    """Añade ids a audit_injection_reviewed en config.json (escritura atómica)."""
    cfg_path = config_dir / "config.json"
    cfg = _load_json(cfg_path) if cfg_path.exists() else {}
    if not isinstance(cfg, dict):
        raise SystemExit(f"❌ {cfg_path} no es un objeto JSON válido")
    reviewed = cfg.get("audit_injection_reviewed")
    if not isinstance(reviewed, dict):
        reviewed = {}
    for hit_id in ids:
        reviewed[hit_id.strip().lower()] = note
    cfg["audit_injection_reviewed"] = reviewed
    config_dir.mkdir(parents=True, exist_ok=True)
    audit_reports.write_private(
        cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
    )


def audit_security(
    original: list[dict],
    _sent: list[dict],
    reviewed: dict[str, str] | None = None,
) -> dict:
    total = len(original)
    if total == 0:
        return {"status": "no_data", "total": 0, "host_distribution": []}

    unexpected_hosts: list[str] = []
    injection_hits: dict[str, dict] = {}
    secrets_redacted = 0
    blocked = 0

    for cap in original:
        host = cap.get("host", "")
        if host and host not in EXPECTED_HOSTS:
            unexpected_hosts.append(host)
        if cap.get("secrets_redacted"):
            secrets_redacted += 1
        if cap.get("blocked"):
            blocked += 1
        # Las sesiones reenvían el historial: un mismo bloque cuenta una vez,
        # con el número de peticiones en las que aparece (#86).
        for key, hit in _injection_matches(cap).items():
            if key in injection_hits:
                injection_hits[key]["requests"] += 1
            else:
                injection_hits[key] = hit

    # Los marcados como revisados no cuentan para el estado (#86).
    reviewed = reviewed or {}
    reviewed_hits = []
    for key in [k for k in injection_hits if k[:12] in reviewed]:
        hit = injection_hits.pop(key)
        hit["note"] = reviewed[key[:12]]
        reviewed_hits.append(hit)

    unexpected_unique = list(dict.fromkeys(unexpected_hosts))
    unexpected_count = len(unexpected_hosts)

    if unexpected_count == 0 and len(injection_hits) == 0:
        status = "good"
    elif unexpected_count > 0:
        status = "critical"
    else:
        status = "warning"

    host_dist: dict[str, int] = {}
    for cap in original:
        h = cap.get("host", "unknown")
        host_dist[h] = host_dist.get(h, 0) + 1

    return {
        "status": status,
        "total": total,
        "secrets_redacted": secrets_redacted,
        "secrets_redacted_pct": round(100 * secrets_redacted / total, 1),
        "blocked": blocked,
        "unexpected_hosts": unexpected_unique,
        "unexpected_count": unexpected_count,
        "injection_hits": list(injection_hits.values())[:20],
        "injection_count": len(injection_hits),
        "injection_reviewed": reviewed_hits[:20],
        "injection_reviewed_count": len(reviewed_hits),
        "host_distribution": sorted(host_dist.items(), key=lambda x: -x[1]),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Audit Plan 2 — Pseudonimización
# ──────────────────────────────────────────────────────────────────────────────


def audit_pseudonymization(original: list[dict], config_dir: Path) -> dict:
    llm_caps = [c for c in original if c.get("path", "").startswith("/v1/messages")]
    total_llm = len(llm_caps)

    if total_llm == 0:
        return {
            "status": "no_data",
            "total_llm": 0,
            "pseudo_yes": 0,
            "pseudo_no": 0,
            "pct": 0,
            "daily_dates": [],
            "daily_pct": [],
            "daily_totals": [],
            "vault_entries": 0,
            "literals_count": 0,
            "word_literals_count": 0,
            "model_distribution": [],
        }

    # #38: pseudo_ran=True → el pseudonimizador procesó la request (métrica real de cobertura)
    # pseudonymized=True → encontró datos sensibles y los reemplazó
    # Capturas antiguas (pre-#38) no tienen pseudo_ran. Heurístico de compatibilidad:
    #   - Si el host es api.anthropic.com (siempre configurado) → pseudo_ran=True aunque pseudonymized=False
    #     (el pseudonimizador corrió pero el mensaje era limpio, p.ej. "generate title")
    #   - Para otros hosts sin pseudo_ran ni pseudonymized → definitivamente no corrió
    _always_covered = {"api.anthropic.com"}

    def _pseudo_ran_compat(cap: dict) -> bool:
        if cap.get("pseudo_ran"):
            return True
        if cap.get("pseudonymized"):
            return True
        host = (cap.get("host") or "").lower()
        return host in _always_covered

    ran_yes = sum(1 for c in llm_caps if _pseudo_ran_compat(c))
    modified_yes = sum(1 for c in llm_caps if c.get("pseudonymized"))
    pct_ran = round(100 * ran_yes / total_llm, 1)
    pct_modified = round(100 * modified_yes / total_llm, 1)

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=90)).isoformat()[:10]
    daily: dict[str, dict[str, int]] = {}
    for cap in llm_caps:
        d = _ts_to_date(cap.get("captured_at"))
        if not d or d < cutoff:
            continue
        rec = daily.setdefault(d, {"ran": 0, "modified": 0, "total": 0})
        rec["total"] += 1
        if _pseudo_ran_compat(cap):
            rec["ran"] += 1
        if cap.get("pseudonymized"):
            rec["modified"] += 1

    daily_dates = sorted(daily.keys())
    daily_pct = [
        round(100 * daily[d]["ran"] / daily[d]["total"], 1) if daily[d]["total"] else 0
        for d in daily_dates
    ]
    daily_totals = [daily[d]["total"] for d in daily_dates]

    vault_path = config_dir / "captures" / ".pseudonym_vault.json"
    vault_entries = 0
    if vault_path.exists():
        v = _load_json(vault_path)
        if isinstance(v, dict):
            vault_entries = len(v)

    cfg = _load_json(config_dir / "config.json") or {}
    literals_count = len(cfg.get("pseudo_literals", []))
    word_literals_count = len(cfg.get("pseudo_word_literals", []))

    model_dist: dict[str, int] = {}
    for cap in llm_caps:
        m = (
            (cap.get("payload") or {}).get("model")
            if isinstance(cap.get("payload"), dict)
            else None
        )
        model_dist[m or "unknown"] = model_dist.get(m or "unknown", 0) + 1

    # El semáforo se basa en los últimos 30 días para no penalizar deuda histórica
    # (el problema masivo fue el 2026-07-31, corregido por fix/36 en 2026-10-28).
    # Los datos all-time se muestran para transparencia.
    cutoff_30 = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()[:10]
    recent_total = sum(daily[d]["total"] for d in daily_dates if d >= cutoff_30)
    recent_ran = sum(daily[d]["ran"] for d in daily_dates if d >= cutoff_30)
    recent_pct = round(100 * recent_ran / recent_total, 1) if recent_total else pct_ran
    if recent_total == 0:
        # Sin capturas recientes: estado basado en configuración actual (all-time fallback)
        status = (
            "good" if pct_ran >= 99 else ("warning" if pct_ran >= 90 else "critical")
        )
    else:
        status = (
            "good"
            if recent_pct >= 99
            else ("warning" if recent_pct >= 90 else "critical")
        )

    return {
        "status": status,
        "total_llm": total_llm,
        "pseudo_yes": ran_yes,
        "pseudo_modified": modified_yes,
        "pseudo_no": total_llm - ran_yes,
        "pct": pct_ran,
        "pct_modified": pct_modified,
        "recent_pct": recent_pct,
        "recent_total": recent_total,
        "daily_dates": daily_dates,
        "daily_pct": daily_pct,
        "daily_totals": daily_totals,
        "vault_entries": vault_entries,
        "literals_count": literals_count,
        "word_literals_count": word_literals_count,
        "model_distribution": sorted(model_dist.items(), key=lambda x: -x[1]),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Audit Plan 3 — Actividad
# ──────────────────────────────────────────────────────────────────────────────


def audit_performance(original: list[dict]) -> dict:
    if not original:
        return {
            "status": "no_data",
            "total_all": 0,
            "total_last30": 0,
            "active_days": 0,
            "avg_per_active_day": 0,
            "daily_dates": [],
            "daily_counts": [],
            "path_distribution": [],
            "status_distribution": [],
            "recent": [],
        }

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()[:10]
    daily: dict[str, int] = {}
    for cap in original:
        d = _ts_to_date(cap.get("captured_at"))
        if d and d >= cutoff:
            daily[d] = daily.get(d, 0) + 1

    daily_dates = sorted(daily.keys())
    daily_counts = [daily[d] for d in daily_dates]

    path_dist: dict[str, int] = {}
    for cap in original:
        p = cap.get("path", "unknown")
        if p.startswith("/mcp-registry"):
            p = "/mcp-registry/..."
        elif p.startswith("/api/web/domain_info"):
            p = "/api/web/domain_info"
        elif p.startswith("/api/eval"):
            p = "/api/eval/..."
        path_dist[p] = path_dist.get(p, 0) + 1

    status_dist: dict[str, int] = {}
    for cap in original:
        sc = cap.get("status_code")
        key = str(sc) if sc else "no_status"
        status_dist[key] = status_dist.get(key, 0) + 1

    active_days = len(daily_dates)
    total_last30 = sum(daily_counts)
    avg = round(total_last30 / active_days, 1) if active_days else 0

    recent = sorted(original, key=lambda c: c.get("captured_at") or "", reverse=True)[
        :5
    ]

    return {
        "status": "good" if active_days > 0 else "warning",
        "total_all": len(original),
        "total_last30": total_last30,
        "active_days": active_days,
        "avg_per_active_day": avg,
        "daily_dates": daily_dates,
        "daily_counts": daily_counts,
        "path_distribution": sorted(path_dist.items(), key=lambda x: -x[1])[:10],
        "status_distribution": sorted(status_dist.items(), key=lambda x: -x[1]),
        "recent": [
            {
                "ts": c.get("captured_at", "")[:19],
                "path": c.get("path", ""),
                "host": c.get("host", ""),
            }
            for c in recent
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Audit Plan 4 — Tests
# ──────────────────────────────────────────────────────────────────────────────


_PYTEST_MISSING = (
    "pytest no está instalado en este entorno. Instálalo en el venv de Klaus "
    "(~/.local/share/klaus/venv/bin/pip install pytest) o instala uv."
)


def _has_pytest(python: str) -> bool:
    try:
        return (
            subprocess.run(
                [python, "-c", "import pytest"], capture_output=True, timeout=30
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def _pytest_command(project_root: Path) -> list[str] | None:
    """Comando para ejecutar pytest (#82).

    El venv instalado por install.sh no trae pytest (es un extra de
    desarrollo), así que se prueba por orden: el intérprete actual, el .venv
    del repo y, como último recurso, un entorno efímero de uv.
    """
    for python in (sys.executable, str(project_root / ".venv" / "bin" / "python")):
        if Path(python).exists() and _has_pytest(python):
            return [python, "-m", "pytest"]
    uv = shutil.which("uv")
    if uv:
        uv_env = ["--no-project", "--with", "pytest", "--with", "mitmproxy"]
        return [uv, "run", *uv_env, "python", "-m", "pytest"]
    return None


def audit_tests(project_root: Path) -> dict:
    test_count = passed = failed = errors = 0
    output_lines: list[str] = []
    status = "no_data"

    cmd = _pytest_command(project_root)
    if cmd is None:
        output_lines = [_PYTEST_MISSING]
    else:
        try:
            run_res = subprocess.run(
                cmd + ["--no-header", "--tb=no"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            summary_lines = (run_res.stdout + run_res.stderr).splitlines()
            output_lines = [ln for ln in summary_lines if ln.strip()][-15:]
            for line in summary_lines[-5:]:
                m_pass = re.search(r"(\d+) passed", line)
                m_fail = re.search(r"(\d+) failed", line)
                m_err = re.search(r"(\d+) error", line)
                if m_pass:
                    passed = int(m_pass.group(1))
                if m_fail:
                    failed = int(m_fail.group(1))
                if m_err:
                    errors = int(m_err.group(1))
            test_count = passed + failed + errors
            if test_count == 0:
                status = "no_data"
            elif failed == 0 and errors == 0:
                status = "good"
            elif failed + errors < max(test_count * 0.1, 1):
                status = "warning"
            else:
                status = "critical"
        except subprocess.TimeoutExpired:
            output_lines = ["Timeout ejecutando pytest (>300s)"]
        except Exception as e:
            output_lines = [f"Error: {e}"]

    return {
        "status": status,
        "test_count": test_count,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": round(100 * passed / test_count, 1) if test_count else 0,
        "output_summary": output_lines,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Audit Plan 5 — EFDEF Compliance
# ──────────────────────────────────────────────────────────────────────────────


def audit_efdef(project_root: Path, config_dir: Path) -> dict:
    checks: list[dict] = []

    def chk(label: str, description: str, passed: bool, detail: str = "") -> None:
        checks.append(
            {
                "label": label,
                "description": description,
                "passed": passed,
                "detail": detail,
            }
        )

    cfg_file = config_dir / "config.json"
    cfg = _load_json(cfg_file) or {}
    chk("config.json", "Archivo de configuración existe", cfg_file.exists())

    vault_file = config_dir / "captures" / ".pseudonym_vault.json"
    v = _load_json(vault_file) if vault_file.exists() else None
    chk(
        "Vault existe",
        "Vault de pseudonimización creado y accesible",
        vault_file.exists(),
        f"{len(v)} entradas" if isinstance(v, dict) else "",
    )

    salt = cfg.get("salt", "")
    chk(
        "Salt configurado",
        "ANTHROPIC_PSEUDO_SALT generado (>=16 chars)",
        bool(salt and len(salt) >= 16),
        f"salt de {len(salt)} chars" if salt else "ausente",
    )

    chk(
        "pseudo_literals key",
        "config.json contiene pseudo_literals para persistencia",
        "pseudo_literals" in cfg,
    )
    chk(
        "pseudo_word_literals key",
        "config.json contiene pseudo_word_literals",
        "pseudo_word_literals" in cfg,
    )

    cert = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
    chk("Certificado CA", "Certificado mitmproxy generado y disponible", cert.exists())

    env_file = config_dir / "klaus-env.sh"
    chk(
        "Klaus env file",
        "~/.klaus-proxy/klaus-env.sh con vars SSL/TLS",
        env_file.exists(),
    )

    for subdir in ["architecture", "guides", "reports", "decisions"]:
        p = project_root / "docs" / subdir
        chk(
            f"docs/{subdir}/",
            f"Carpeta docs/{subdir}/ existe (EFDEF Sección 23)",
            p.is_dir(),
        )

    readme = project_root / "README.md"
    readme_has_docs = "📚 Documentación" in (
        readme.read_text(encoding="utf-8") if readme.exists() else ""
    )
    chk(
        "README docs section",
        "README.md tiene sección Documentación como mapa del proyecto",
        readme_has_docs,
    )

    claude_md = project_root / "CLAUDE.md"
    has_workflow = False
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        has_workflow = (
            "Issue" in content and "Rama" in content and "Pull Request" in content
        )
    chk(
        "Workflow CLAUDE.md",
        "CLAUDE.md documenta flujo Issue→Rama→PR (Sección 22)",
        has_workflow,
    )

    passed_count = sum(1 for c in checks if c["passed"])
    total_count = len(checks)
    pct = round(100 * passed_count / total_count, 1) if total_count else 0
    status = "good" if pct >= 90 else ("warning" if pct >= 70 else "critical")

    return {
        "status": status,
        "checks": checks,
        "passed": passed_count,
        "total": total_count,
        "pct": pct,
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTML Generation — uses #MARKER# tokens to avoid conflict with CSS {}
# ──────────────────────────────────────────────────────────────────────────────


def _status_color(status: str) -> str:
    return {
        "good": "#0ca30c",
        "warning": "#fab219",
        "critical": "#d03b3b",
        "no_data": "#898781",
    }.get(status, "#898781")


def _status_emoji(status: str) -> str:
    return {"good": "✅", "warning": "⚠️", "critical": "🔴", "no_data": "⬜"}.get(
        status, "⬜"
    )


def _status_label(status: str) -> str:
    return {
        "good": "OK",
        "warning": "Revisar",
        "critical": "Crítico",
        "no_data": "Sin datos",
    }.get(status, "?")


def _pct_color(pct: float, good_threshold: float = 90) -> str:
    return (
        "#0ca30c" if pct >= good_threshold else ("#fab219" if pct >= 70 else "#d03b3b")
    )


def _build_html(replacements: dict[str, str], template: str) -> str:
    html = template
    for key, value in replacements.items():
        html = html.replace(f"#{key}#", str(value))
    return html


HTML_TEMPLATE = """\
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klaus Proxy — Audit Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  :root {
    --surface-page: #f9f9f7;
    --surface-card: #fcfcfb;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #898781;
    --border: #e1e0d9;
    --baseline: #c3c2b7;
    --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a;
    --s4: #eda100; --s5: #e87ba4; --s6: #008300;
    --good: #0ca30c; --warning: #fab219;
    --serious: #ec835a; --critical: #d03b3b;
    --radius: 8px; --gap: 16px;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --surface-page: #0d0d0d; --surface-card: #1a1a19;
      --text-primary: #f0efec; --text-secondary: #c3c2b7;
      --text-muted: #898781; --border: #2c2c2a; --baseline: #383835;
      --s1: #3987e5; --s2: #d95926; --s3: #199e70;
      --s4: #c98500; --s5: #d55181; --s6: #008300;
    }
  }
  :root[data-theme="dark"] {
    --surface-page: #0d0d0d; --surface-card: #1a1a19;
    --text-primary: #f0efec; --text-secondary: #c3c2b7;
    --text-muted: #898781; --border: #2c2c2a; --baseline: #383835;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70;
    --s4: #c98500; --s5: #d55181; --s6: #008300;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--surface-page); color: var(--text-primary); min-height: 100vh;
  }
  .header {
    background: var(--surface-card); border-bottom: 1px solid var(--border);
    padding: 20px var(--gap) 16px;
  }
  .header-top {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
  }
  .header h1 { font-size: 1.25rem; font-weight: 700; }
  .header .meta { font-size: 0.78rem; color: var(--text-muted); }
  .theme-btn {
    background: none; border: 1px solid var(--border); border-radius: 6px;
    padding: 4px 10px; cursor: pointer; color: var(--text-secondary); font-size: 0.82rem;
  }
  .summary-cards { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
  .summary-card {
    background: var(--surface-page); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 10px 14px; min-width: 130px;
    cursor: pointer; transition: border-color .15s;
    display: flex; flex-direction: column; gap: 2px;
  }
  .summary-card:hover, .summary-card.active { border-color: var(--s1); background: var(--surface-card); }
  .summary-card .card-title { font-size: 0.72rem; color: var(--text-muted); }
  .summary-card .card-status { font-size: 1rem; font-weight: 600; display: flex; align-items: center; gap: 6px; }
  .status-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; display: inline-block; }
  .tabs {
    display: flex; overflow-x: auto; padding: 0 var(--gap);
    background: var(--surface-card); border-bottom: 1px solid var(--border);
  }
  .tab-btn {
    background: none; border: none; border-bottom: 2px solid transparent;
    padding: 10px 14px; cursor: pointer; font-size: 0.85rem;
    color: var(--text-secondary); white-space: nowrap; transition: color .12s, border-color .12s;
  }
  .tab-btn:hover { color: var(--text-primary); }
  .tab-btn.active { color: var(--s1); border-bottom-color: var(--s1); font-weight: 600; }
  .main { padding: var(--gap); max-width: 1100px; margin: 0 auto; }
  .panel { display: none; }
  .panel.active { display: block; }
  .section-header { margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }
  .section-header h2 { font-size: 1.05rem; font-weight: 700; }
  .status-badge { font-size: 0.72rem; padding: 2px 8px; border-radius: 20px; color: #fff; font-weight: 600; }
  .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--gap); }
  .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--gap); }
  .card {
    background: var(--surface-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: var(--gap);
  }
  .card h3 {
    font-size: 0.82rem; color: var(--text-muted); margin-bottom: 8px;
    font-weight: 500; text-transform: uppercase; letter-spacing: .04em;
  }
  .stat-tile {
    background: var(--surface-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 14px var(--gap);
  }
  .stat-tile .stat-label { font-size: 0.75rem; color: var(--text-muted); }
  .stat-tile .stat-value { font-size: 1.8rem; font-weight: 700; line-height: 1.15; }
  .stat-tile .stat-sub { font-size: 0.78rem; color: var(--text-secondary); }
  .chart-wrap { position: relative; height: 220px; }
  .chart-wrap-tall { position: relative; height: 280px; }
  .data-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .data-table th {
    text-align: left; padding: 6px 8px; color: var(--text-muted);
    border-bottom: 1px solid var(--border); font-weight: 500;
  }
  .data-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr:hover td { background: var(--surface-page); }
  .checklist { list-style: none; display: flex; flex-direction: column; gap: 8px; }
  .check-item {
    display: flex; align-items: flex-start; gap: 10px; padding: 8px;
    border-radius: 6px; background: var(--surface-page); border: 1px solid var(--border);
  }
  .check-icon { font-size: 1rem; flex-shrink: 0; margin-top: 1px; }
  .check-label { font-size: 0.85rem; font-weight: 600; }
  .check-desc { font-size: 0.75rem; color: var(--text-muted); }
  .check-detail { font-size: 0.72rem; color: var(--text-secondary); margin-top: 1px; }
  .progress-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 4px; transition: width .4s; }
  .mt8  { margin-top:  8px; }
  .mt12 { margin-top: 12px; }
  .mt16 { margin-top: 16px; }
  .mb8  { margin-bottom:  8px; }
  .mb12 { margin-bottom: 12px; }
  code {
    font-family: "Menlo","Consolas",monospace; font-size: .8em;
    background: var(--border); padding: 1px 4px; border-radius: 3px;
  }
  @media (max-width: 600px) {
    .header h1 { font-size: 1rem; }
    .summary-card { min-width: 100px; }
    .tab-btn { padding: 10px 10px; }
  }
#HISTORY_CSS#
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <h1>🔌 Klaus Proxy &mdash; Audit Dashboard</h1>
      <div class="meta">Generado: #GENERATED_AT# &middot; Capturas totales: #TOTAL_CAPTURES# &middot; Periodo: #DATE_RANGE#</div>
      #HISTORY_HTML#
    </div>
    <button class="theme-btn" onclick="toggleTheme()">🌙 Modo oscuro</button>
  </div>
  <div class="summary-cards" id="summary-cards">
    #SUMMARY_CARDS_HTML#
  </div>
</div>
#CHANGES_HTML#

<nav class="tabs" id="tabs">
  <button class="tab-btn active" data-tab="security">🔐 Seguridad</button>
  <button class="tab-btn" data-tab="pseudo">📊 Pseudonimización</button>
  <button class="tab-btn" data-tab="perf">⚡ Actividad</button>
  <button class="tab-btn" data-tab="tests">🧪 Tests</button>
  <button class="tab-btn" data-tab="efdef">📋 EFDEF</button>
</nav>

<main class="main">

<!-- ── Seguridad ── -->
<div id="panel-security" class="panel active">
  <div class="section-header">
    <h2>🔐 Auditoría de Seguridad</h2>
    <span class="status-badge" style="background:#SEC_COLOR#">#SEC_EMOJI# #SEC_LABEL#</span>
  </div>
  <div class="grid-3 mb12">
    <div class="stat-tile">
      <div class="stat-label">Capturas totales</div>
      <div class="stat-value">#SEC_TOTAL#</div>
      <div class="stat-sub">todos los endpoints</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Secretos redactados</div>
      <div class="stat-value">#SEC_REDACTED_PCT#%</div>
      <div class="stat-sub">#SEC_REDACTED# de #SEC_TOTAL#</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Hosts inesperados</div>
      <div class="stat-value" style="color:#SEC_HOSTS_COLOR#">#SEC_UNEXPECTED#</div>
      <div class="stat-sub">se espera solo api.anthropic.com</div>
    </div>
  </div>
  <div class="grid-2">
    <div class="card">
      <h3>Distribución de hosts</h3>
      <div class="chart-wrap"><canvas id="chart-hosts"></canvas></div>
    </div>
    <div class="card">
      <h3>Hosts capturados</h3>
      <table class="data-table mt8">
        <thead><tr><th>Host</th><th>Capturas</th><th>Estado</th></tr></thead>
        <tbody id="hosts-table-body"></tbody>
      </table>
      #INJECTION_HTML#
    </div>
  </div>
</div>

<!-- ── Pseudonimización ── -->
<div id="panel-pseudo" class="panel">
  <div class="section-header">
    <h2>📊 Calidad de Pseudonimización</h2>
    <span class="status-badge" style="background:#PSEUDO_COLOR#">#PSEUDO_EMOJI# #PSEUDO_LABEL#</span>
  </div>
  <div class="card mb12" style="background:var(--surface-card);border:1.5px solid var(--border)">
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <div>
        <div style="font-size:.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em">Últimos 90 días</div>
        <div style="font-size:2.2rem;font-weight:700;color:#RECENT_PSEUDO_COLOR#">#RECENT_PSEUDO_PCT#%</div>
        <div style="font-size:.8rem;color:var(--text-muted)">#RECENT_PSEUDO_TOTAL# peticiones · objetivo ≥99%</div>
      </div>
      <div style="flex:1;min-width:200px;font-size:.85rem;color:var(--text-secondary)">
        El semáforo se basa en los últimos 90 días. Las capturas históricas previas al fix/36 (2026-10-28)
        aparecen en las métricas all-time pero no afectan al estado actual del sistema.
      </div>
    </div>
  </div>
  <div class="grid-3 mb12">
    <div class="stat-tile">
      <div class="stat-label">Cobertura total (all-time)</div>
      <div class="stat-value" style="color:#PSEUDO_PCT_COLOR#">#PSEUDO_PCT#%</div>
      <div class="stat-sub">#PSEUDO_YES# de #PSEUDO_TOTAL# procesadas</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Con datos sensibles reemplazados</div>
      <div class="stat-value">#PSEUDO_MODIFIED_PCT#%</div>
      <div class="stat-sub">#PSEUDO_MODIFIED# de #PSEUDO_TOTAL# modificadas</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Sin cobertura</div>
      <div class="stat-value" style="color:#PSEUDO_NO_COLOR#">#PSEUDO_NO#</div>
      <div class="stat-sub">peticiones no procesadas por el pseudonimizador</div>
    </div>
  </div>
  <div class="grid-2 mb12">
    <div class="stat-tile">
      <div class="stat-label">Entradas en el vault</div>
      <div class="stat-value">#VAULT_ENTRIES#</div>
      <div class="stat-sub">pares real &rarr; pseudónimo</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Literales protegidas</div>
      <div class="stat-value">#LITERALS_TOTAL#</div>
      <div class="stat-sub">#WORD_LITERALS_COUNT# word + #LITERALS_COUNT# literales</div>
    </div>
  </div>
  <div class="grid-2">
    <div class="card">
      <h3>% Pseudonimización diaria (últimos 90 días)</h3>
      <div class="chart-wrap"><canvas id="chart-pseudo-daily"></canvas></div>
    </div>
    <div class="card">
      <h3>Modelos LLM utilizados</h3>
      <div class="chart-wrap"><canvas id="chart-models"></canvas></div>
    </div>
  </div>
  <div class="card mt12">
    <h3>Peticiones LLM diarias (últimos 90 días)</h3>
    <div class="chart-wrap-tall"><canvas id="chart-pseudo-volume"></canvas></div>
  </div>
</div>

<!-- ── Actividad ── -->
<div id="panel-perf" class="panel">
  <div class="section-header">
    <h2>⚡ Actividad del Proxy</h2>
    <span class="status-badge" style="background:#PERF_COLOR#">#PERF_EMOJI# #PERF_LABEL#</span>
  </div>
  <div class="grid-3 mb12">
    <div class="stat-tile">
      <div class="stat-label">Capturas últimos 30 días</div>
      <div class="stat-value">#PERF_LAST30#</div>
      <div class="stat-sub">#PERF_ACTIVE_DAYS# días activos</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Promedio por día activo</div>
      <div class="stat-value">#PERF_AVG#</div>
      <div class="stat-sub">capturas / día</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Total histórico</div>
      <div class="stat-value">#PERF_TOTAL#</div>
      <div class="stat-sub">desde el primer día</div>
    </div>
  </div>
  <div class="card mb12">
    <h3>Actividad diaria (últimos 30 días)</h3>
    <div class="chart-wrap"><canvas id="chart-activity"></canvas></div>
  </div>
  <div class="grid-2">
    <div class="card">
      <h3>Top endpoints capturados</h3>
      <table class="data-table mt8">
        <thead><tr><th>Path</th><th>Capturas</th></tr></thead>
        <tbody id="paths-table-body"></tbody>
      </table>
    </div>
    <div class="card">
      <h3>Capturas recientes</h3>
      <table class="data-table mt8">
        <thead><tr><th>Timestamp</th><th>Host</th><th>Path</th></tr></thead>
        <tbody id="recent-table-body"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── Tests ── -->
<div id="panel-tests" class="panel">
  <div class="section-header">
    <h2>🧪 Cobertura de Tests</h2>
    <span class="status-badge" style="background:#TESTS_COLOR#">#TESTS_EMOJI# #TESTS_LABEL#</span>
  </div>
  <div class="grid-3 mb12">
    <div class="stat-tile">
      <div class="stat-label">Tests totales</div>
      <div class="stat-value">#TESTS_TOTAL#</div>
      <div class="stat-sub">colectados por pytest</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Tests pasando</div>
      <div class="stat-value" style="color:var(--good)">#TESTS_PASSED#</div>
      <div class="stat-sub">#TESTS_PASS_RATE#% pass rate</div>
    </div>
    <div class="stat-tile">
      <div class="stat-label">Tests fallando</div>
      <div class="stat-value" style="color:var(--critical)">#TESTS_FAILED#</div>
      <div class="stat-sub">#TESTS_ERRORS# errores</div>
    </div>
  </div>
  <div class="card mb12">
    <h3>Pass rate</h3>
    <div class="progress-bar mt8" style="height:12px">
      <div class="progress-fill" style="width:#TESTS_PASS_RATE#%;background:#TESTS_COLOR#"></div>
    </div>
    <div style="font-size:.78rem;color:var(--text-secondary);margin-top:4px">
      #TESTS_PASS_RATE#% &mdash; #TESTS_PASSED# passed / #TESTS_FAILED# failed / #TESTS_ERRORS# errors
    </div>
  </div>
  <div class="card">
    <h3>Salida de pytest</h3>
    <pre id="pytest-output" style="font-size:.78rem;color:var(--text-secondary);background:var(--surface-page);border-radius:6px;padding:12px;margin-top:8px;overflow-x:auto;white-space:pre-wrap"></pre>
  </div>
</div>

<!-- ── EFDEF ── -->
<div id="panel-efdef" class="panel">
  <div class="section-header">
    <h2>📋 Compliance EFDEF</h2>
    <span class="status-badge" style="background:#EFDEF_COLOR#">#EFDEF_EMOJI# #EFDEF_LABEL#</span>
  </div>
  <div class="grid-3 mb12">
    <div class="stat-tile">
      <div class="stat-label">Checks superados</div>
      <div class="stat-value">#EFDEF_PASSED# / #EFDEF_TOTAL#</div>
      <div class="stat-sub">#EFDEF_PCT#% cumplimiento</div>
    </div>
    <div class="stat-tile" style="grid-column:span 2">
      <div class="stat-label">Progreso general</div>
      <div class="progress-bar mt8" style="height:10px">
        <div class="progress-fill" style="width:#EFDEF_PCT#%;background:#EFDEF_COLOR#"></div>
      </div>
      <div style="font-size:.78rem;color:var(--text-secondary);margin-top:4px">
        #EFDEF_PCT#% &mdash; #EFDEF_PASSED# superados de #EFDEF_TOTAL#
      </div>
    </div>
  </div>
  <div class="card">
    <h3>Checklist de compliance</h3>
    <ul class="checklist mt8" id="efdef-checklist"></ul>
  </div>
</div>

</main>

<script>
const DATA = #AUDIT_DATA_JSON#;

function toggleTheme() {
  const r = document.documentElement;
  r.setAttribute('data-theme', r.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  buildCharts();
}

// Tab navigation
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + tab).classList.add('active');
  });
});
document.querySelectorAll('.summary-card').forEach(card => {
  card.addEventListener('click', () => {
    const tab = card.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.summary-card').forEach(c => c.classList.remove('active'));
    document.getElementById('panel-' + tab).classList.add('active');
    card.classList.add('active');
  });
});

// Hosts table
(function() {
  const tbody = document.getElementById('hosts-table-body');
  if (!tbody) return;
  const expected = new Set(['api.anthropic.com']);
  DATA.security.host_distribution.forEach(function(item) {
    const host = item[0], count = item[1];
    const ok = expected.has(host);
    const tr = document.createElement('tr');
    tr.innerHTML = '<td><code>' + host + '</code></td><td>' + count.toLocaleString() + '</td><td>' + (ok ? '✅ Esperado' : '⚠️ Inesperado') + '</td>';
    tbody.appendChild(tr);
  });
})();

// Paths table
(function() {
  const tbody = document.getElementById('paths-table-body');
  if (!tbody) return;
  DATA.performance.path_distribution.forEach(function(item) {
    const path = item[0], count = item[1];
    const tr = document.createElement('tr');
    tr.innerHTML = '<td><code>' + path + '</code></td><td>' + count.toLocaleString() + '</td>';
    tbody.appendChild(tr);
  });
})();

// Recent captures table
(function() {
  const tbody = document.getElementById('recent-table-body');
  if (!tbody) return;
  DATA.performance.recent.forEach(function(r) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td style="white-space:nowrap">' + r.ts + '</td><td><code>' + r.host + '</code></td><td style="font-size:.75rem;color:var(--text-muted)">' + r.path + '</td>';
    tbody.appendChild(tr);
  });
})();

// pytest output
(function() {
  const el = document.getElementById('pytest-output');
  if (!el) return;
  el.textContent = DATA.tests.output_summary.join('\\n') || '(sin salida)';
})();

// EFDEF checklist
(function() {
  const ul = document.getElementById('efdef-checklist');
  if (!ul) return;
  DATA.efdef.checks.forEach(function(c) {
    const li = document.createElement('li');
    li.className = 'check-item';
    li.innerHTML = '<span class="check-icon">' + (c.passed ? '✅' : '❌') + '</span>' +
      '<div><div class="check-label">' + c.label + '</div>' +
      '<div class="check-desc">' + c.description + '</div>' +
      (c.detail ? '<div class="check-detail">' + c.detail + '</div>' : '') + '</div>';
    ul.appendChild(li);
  });
})();

// Charts
const CHARTS = {};
function isDark() {
  const t = document.documentElement.getAttribute('data-theme');
  if (t === 'dark') return true;
  if (t === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function buildCharts() {
  const dark = isDark();
  const textColor = dark ? '#c3c2b7' : '#52514e';
  const gridColor = dark ? '#2c2c2a' : '#e1e0d9';
  const baseColor = dark ? '#383835' : '#c3c2b7';
  const surfaceColor = dark ? '#1a1a19' : '#fcfcfb';
  const catColors = dark
    ? ['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767']
    : ['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#e34948'];

  Chart.defaults.color = textColor;
  Chart.defaults.borderColor = gridColor;

  function mk(id, config) {
    if (CHARTS[id]) { CHARTS[id].destroy(); }
    const el = document.getElementById(id);
    if (!el) return;
    CHARTS[id] = new Chart(el, config);
  }

  const axisOpts = {
    x: { grid: { color: gridColor }, border: { color: baseColor }, ticks: { maxTicksLimit: 8 } },
    y: { grid: { color: gridColor }, border: { color: baseColor }, beginAtZero: true }
  };

  // Hosts donut
  mk('chart-hosts', {
    type: 'doughnut',
    data: {
      labels: DATA.security.host_distribution.map(function(i) { return i[0]; }),
      datasets: [{ data: DATA.security.host_distribution.map(function(i) { return i[1]; }),
        backgroundColor: catColors, borderWidth: 2, borderColor: surfaceColor }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: function(ctx) { return ' ' + ctx.label + ': ' + ctx.parsed.toLocaleString(); } } }
      }
    }
  });

  // Daily pseudo %
  mk('chart-pseudo-daily', {
    type: 'line',
    data: {
      labels: DATA.pseudonymization.daily_dates,
      datasets: [{ label: '% pseudo', data: DATA.pseudonymization.daily_pct,
        borderColor: catColors[0], backgroundColor: catColors[0] + '26',
        fill: true, tension: 0.3, pointRadius: 3, pointHoverRadius: 5, borderWidth: 2 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false,
        callbacks: { label: function(ctx) { return ' ' + ctx.parsed.y + '%'; } } } },
      scales: { x: axisOpts.x, y: { ...axisOpts.y, min: 0, max: 100, ticks: { callback: function(v) { return v + '%'; } } } }
    }
  });

  // LLM volume bar
  mk('chart-pseudo-volume', {
    type: 'bar',
    data: {
      labels: DATA.pseudonymization.daily_dates,
      datasets: [{ label: 'Peticiones LLM', data: DATA.pseudonymization.daily_totals,
        backgroundColor: catColors[0] + 'b3', borderRadius: 3, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: axisOpts
    }
  });

  // Models bar horizontal
  mk('chart-models', {
    type: 'bar',
    data: {
      labels: DATA.pseudonymization.model_distribution.map(function(i) { return i[0].replace('claude-',''); }),
      datasets: [{ data: DATA.pseudonymization.model_distribution.map(function(i) { return i[1]; }),
        backgroundColor: catColors, borderRadius: 4, borderSkipped: false }]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: axisOpts.x,
        y: { grid: { display: false }, border: { color: baseColor }, ticks: { font: { size: 10 } } }
      }
    }
  });

  // Activity bar
  mk('chart-activity', {
    type: 'bar',
    data: {
      labels: DATA.performance.daily_dates,
      datasets: [{ label: 'Capturas', data: DATA.performance.daily_counts,
        backgroundColor: catColors[2] + 'bf', borderRadius: 3, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: axisOpts
    }
  });
}

buildCharts();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', buildCharts);
</script>
<script>#HISTORY_JS#</script>
</body>
</html>
"""


_INJECTION_STEPS_HTML = """\
<div style='margin-top:8px;padding:8px 10px;border-left:3px solid #fab219;\
background:var(--surface-page);border-radius:4px;color:var(--text-secondary)'>
<b style='color:var(--text-primary)'>Qué hacer con cada aviso</b>
<ol style='margin:4px 0 0;padding-left:18px'>
<li><b>Mira el origen y el fragmento.</b> Si es código, documentación o una
conversación <i>sobre</i> prompt injection, es un falso positivo.</li>
<li><b>Falso positivo:</b> márcalo como revisado y dejará de contar. Copia el
comando que aparece en el aviso:
<code>klaus-audit-dashboard --mark-reviewed &lt;id&gt; --note "motivo"</code>.
Admite varios ids a la vez.</li>
<li><b>Sospechoso</b> (un fichero, web o salida de comando que da órdenes a
Claude):
<ul style='padding-left:16px'>
<li>No sigas trabajando en esa sesión de Claude Code.</li>
<li>Localiza la fuente: el <i>Origen</i> del aviso o, si no aparece, la
captura indicada en <code>~/.klaus-proxy/captures/original/</code>.</li>
<li>Revisa lo que hizo Claude después de leerla en esa sesión
(<code>git status</code>, <code>git diff</code>, comandos ejecutados) y deshaz lo
que no hayas pedido.</li>
<li>Elimina o aísla la fuente (fichero, dependencia, URL). Si pudo exponer
credenciales, rótalas.</li>
<li>Cuando esté resuelto, márcalo como revisado con una nota.</li>
</ul></li>
</ol></div>"""


def _injection_hit_html(hit: dict | str) -> str:
    """Una coincidencia de injection con su contexto (#86)."""
    esc = html.escape
    if isinstance(hit, str):  # informes anteriores a #86: solo la hora
        return f"<li>{esc(hit)}</li>"
    patterns = ", ".join(hit.get("patterns") or [hit.get("match", "")])
    requests = hit.get("requests", 1)
    seen = f" · en {requests} peticiones" if requests > 1 else ""
    source = (
        f"<div style='font-size:.72rem'>Origen: <code>{esc(hit['source'])}</code></div>"
        if hit.get("source")
        else ""
    )
    hit_id = hit.get("id", "")
    command = (
        f" · <code style='user-select:all'>klaus-audit-dashboard --mark-reviewed "
        f"{esc(hit_id)}</code>"
        if hit_id
        else ""
    )
    return (
        f"<li style='margin-bottom:6px'>"
        f"<code>{esc(hit.get('captured_at', ''))}</code> · "
        f"<b style='color:var(--text-primary)'>{esc(patterns)}</b> · "
        f"{esc(hit.get('origin', ''))} · <code>{esc(hit.get('path', ''))}</code>{seen}"
        f"{source}"
        f"<div style='font-family:monospace;white-space:pre-wrap;word-break:break-word;"
        f"background:var(--surface-page);border-radius:4px;padding:4px 6px;margin-top:2px'>"
        f"{esc(hit.get('before', ''))}"
        f"<mark>{esc(hit.get('match', ''))}</mark>"
        f"{esc(hit.get('after', ''))}</div>"
        f"<div style='font-size:.72rem'>Captura: <code>{esc(hit.get('file', ''))}</code>"
        f"{command}</div>"
        f"</li>"
    )


def _injection_reviewed_html(security: dict) -> str:
    """Avisos marcados como revisados, plegados (#86)."""
    esc = html.escape
    count = security.get("injection_reviewed_count", 0)
    if not count:
        return ""
    items = "".join(
        f"<li><code>{esc(h.get('id', ''))}</code> · {esc(h.get('captured_at', ''))} · "
        f"{esc(h.get('origin', ''))}"
        + (f" · <code>{esc(h['source'])}</code>" if h.get("source") else "")
        + (f" — <i>{esc(h['note'])}</i>" if h.get("note") else "")
        + "</li>"
        for h in security.get("injection_reviewed", [])
    )
    return (
        f"<details class='mt12' style='font-size:.78rem;color:var(--text-muted)'>"
        f"<summary>✔️ {count} avisos de injection marcados como revisados "
        f"(no cuentan para el estado)</summary>"
        f"<ul style='margin-top:4px;padding-left:16px'>{items}</ul>"
        f"<div>Se guardan en <code>audit_injection_reviewed</code> de "
        f"<code>~/.klaus-proxy/config.json</code>; borra una entrada para que "
        f"vuelva a contar.</div></details>"
    )


def render_html(
    security: dict,
    pseudo: dict,
    perf: dict,
    tests: dict,
    efdef: dict,
    total_captures: int,
    date_range: str,
    *,
    generated_at: str | None = None,
    history_html: str = "",
    changes_html: str = "",
) -> str:
    plans = [
        ("security", security, "🔐 Seguridad"),
        ("pseudo", pseudo, "📊 Pseudonimización"),
        ("perf", perf, "⚡ Actividad"),
        ("tests", tests, "🧪 Tests"),
        ("efdef", efdef, "📋 EFDEF"),
    ]

    cards_html = ""
    for tab_id, plan, label in plans:
        st = plan.get("status", "no_data")
        col = _status_color(st)
        lbl = _status_label(st)
        em = _status_emoji(st)
        cards_html += (
            f'<div class="summary-card" data-tab="{tab_id}">'
            f'<div class="card-title">{label}</div>'
            f'<div class="card-status">'
            f'<span class="status-dot" style="background:{col}"></span>'
            f"{em} {lbl}</div></div>"
        )

    injection_count = security.get("injection_count", 0)
    injection_hits = security.get("injection_hits", [])
    if injection_count == 0:
        injection_html = '<div class="mt12" style="font-size:.8rem;color:#0ca30c">✅ Sin patrones de prompt injection pendientes de revisar.</div>'
    else:
        lines = "".join(_injection_hit_html(h) for h in injection_hits[:10])
        more = (
            f"<li style='color:var(--text-muted)'>…y {injection_count - 10} más</li>"
            if injection_count > 10
            else ""
        )
        injection_html = (
            f'<div class="mt12" style="font-size:.8rem;color:#fab219">'
            f"⚠️ {injection_count} textos con patrones de injection pendientes de revisar."
            f'<ul style="margin-top:4px;padding-left:16px;color:var(--text-muted)">{lines}{more}</ul>'
            f"{_INJECTION_STEPS_HTML}</div>"
        )
    injection_html += _injection_reviewed_html(security)

    audit_data = {
        "security": security,
        "pseudonymization": pseudo,
        "performance": perf,
        "tests": tests,
        "efdef": efdef,
    }

    literals_total = pseudo.get("literals_count", 0) + pseudo.get(
        "word_literals_count", 0
    )

    replacements = {
        "GENERATED_AT": generated_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "HISTORY_HTML": history_html,
        "CHANGES_HTML": changes_html,
        "HISTORY_CSS": audit_reports.HISTORY_CSS,
        "HISTORY_JS": audit_reports.HISTORY_JS,
        "TOTAL_CAPTURES": f"{total_captures:,}",
        "DATE_RANGE": date_range,
        "SUMMARY_CARDS_HTML": cards_html,
        # "<" escapado: los fragmentos de injection (#86) pueden contener
        # "</script>" y cerrarían el bloque donde se incrusta el JSON.
        "AUDIT_DATA_JSON": json.dumps(
            audit_data, ensure_ascii=False, default=str
        ).replace("<", "\\u003c"),
        # Security
        "SEC_COLOR": _status_color(security.get("status", "no_data")),
        "SEC_EMOJI": _status_emoji(security.get("status", "no_data")),
        "SEC_LABEL": _status_label(security.get("status", "no_data")),
        "SEC_TOTAL": f"{security.get('total', 0):,}",
        "SEC_REDACTED": f"{security.get('secrets_redacted', 0):,}",
        "SEC_REDACTED_PCT": str(security.get("secrets_redacted_pct", 0)),
        "SEC_UNEXPECTED": str(security.get("unexpected_count", 0)),
        "SEC_HOSTS_COLOR": (
            "#d03b3b" if security.get("unexpected_count", 0) > 0 else "#0ca30c"
        ),
        "INJECTION_HTML": injection_html,
        # Pseudonymization
        "PSEUDO_COLOR": _status_color(pseudo.get("status", "no_data")),
        "PSEUDO_EMOJI": _status_emoji(pseudo.get("status", "no_data")),
        "PSEUDO_LABEL": _status_label(pseudo.get("status", "no_data")),
        "PSEUDO_PCT": str(pseudo.get("pct", 0)),
        "PSEUDO_PCT_COLOR": _pct_color(pseudo.get("pct", 0), good_threshold=99),
        "RECENT_PSEUDO_PCT": str(pseudo.get("recent_pct", pseudo.get("pct", 0))),
        "RECENT_PSEUDO_COLOR": _pct_color(
            pseudo.get("recent_pct", pseudo.get("pct", 0)), good_threshold=99
        ),
        "RECENT_PSEUDO_TOTAL": f"{pseudo.get('recent_total', 0):,}",
        "PSEUDO_YES": f"{pseudo.get('pseudo_yes', 0):,}",
        "PSEUDO_MODIFIED": f"{pseudo.get('pseudo_modified', 0):,}",
        "PSEUDO_MODIFIED_PCT": str(pseudo.get("pct_modified", 0)),
        "PSEUDO_NO": f"{pseudo.get('pseudo_no', 0):,}",
        "PSEUDO_NO_COLOR": "#d03b3b" if pseudo.get("pseudo_no", 0) > 0 else "#0ca30c",
        "PSEUDO_TOTAL": f"{pseudo.get('total_llm', 0):,}",
        "VAULT_ENTRIES": f"{pseudo.get('vault_entries', 0):,}",
        "LITERALS_COUNT": str(pseudo.get("literals_count", 0)),
        "WORD_LITERALS_COUNT": str(pseudo.get("word_literals_count", 0)),
        "LITERALS_TOTAL": str(literals_total),
        # Performance
        "PERF_COLOR": _status_color(perf.get("status", "no_data")),
        "PERF_EMOJI": _status_emoji(perf.get("status", "no_data")),
        "PERF_LABEL": _status_label(perf.get("status", "no_data")),
        "PERF_LAST30": f"{perf.get('total_last30', 0):,}",
        "PERF_ACTIVE_DAYS": str(perf.get("active_days", 0)),
        "PERF_AVG": str(perf.get("avg_per_active_day", 0)),
        "PERF_TOTAL": f"{perf.get('total_all', 0):,}",
        # Tests
        "TESTS_COLOR": _status_color(tests.get("status", "no_data")),
        "TESTS_EMOJI": _status_emoji(tests.get("status", "no_data")),
        "TESTS_LABEL": _status_label(tests.get("status", "no_data")),
        "TESTS_TOTAL": str(tests.get("test_count", 0)),
        "TESTS_PASSED": str(tests.get("passed", 0)),
        "TESTS_FAILED": str(tests.get("failed", 0)),
        "TESTS_ERRORS": str(tests.get("errors", 0)),
        "TESTS_PASS_RATE": str(tests.get("pass_rate", 0)),
        # EFDEF
        "EFDEF_COLOR": _status_color(efdef.get("status", "no_data")),
        "EFDEF_EMOJI": _status_emoji(efdef.get("status", "no_data")),
        "EFDEF_LABEL": _status_label(efdef.get("status", "no_data")),
        "EFDEF_PASSED": str(efdef.get("passed", 0)),
        "EFDEF_TOTAL": str(efdef.get("total", 0)),
        "EFDEF_PCT": str(efdef.get("pct", 0)),
    }

    return _build_html(replacements, HTML_TEMPLATE)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Klaus Proxy — Genera dashboard HTML de auditoría"
    )
    parser.add_argument(
        "--captures-dir",
        default=str(Path.home() / ".klaus-proxy" / "captures"),
        help="Directorio de capturas (default: ~/.klaus-proxy/captures)",
    )
    parser.add_argument(
        "--config-dir",
        default=str(Path.home() / ".klaus-proxy"),
        help="Directorio de configuración (default: ~/.klaus-proxy)",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(Path(__file__).parent.parent / "informes"),
        help="Directorio del histórico de informes (default: informes/ del repo)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Copia adicional del último dashboard (el principal va a "
        "<reports-dir>/audit-dashboard.html)",
    )
    parser.add_argument(
        "--open", action="store_true", help="Abre el dashboard en el navegador"
    )
    parser.add_argument(
        "--mark-reviewed",
        nargs="+",
        metavar="ID",
        help="Marca avisos de prompt injection como revisados (dejan de contar) "
        "y genera el informe",
    )
    parser.add_argument(
        "--note", default="", help="Nota que se guarda con --mark-reviewed"
    )
    args = parser.parse_args(argv)

    if args.mark_reviewed:
        mark_injections_reviewed(Path(args.config_dir), args.mark_reviewed, args.note)
        print(
            f"✅ {len(args.mark_reviewed)} aviso(s) de injection marcados como revisados"
        )

    captures_dir = Path(args.captures_dir)
    config_dir = Path(args.config_dir)
    reports_dir = Path(args.reports_dir)
    output_path = reports_dir / audit_reports.DASHBOARD_FILE
    project_root = Path(__file__).parent.parent

    print("🔍 Leyendo capturas...")
    if not captures_dir.exists():
        print(f"❌ Directorio de capturas no encontrado: {captures_dir}")
        sys.exit(1)

    original, sent = _captures(captures_dir)
    total = len(original)
    print(f"   ✅ {total:,} capturas originales | {len(sent):,} enviadas")

    dates = sorted(
        c.get("captured_at", "")[:10] for c in original if c.get("captured_at")
    )
    date_range = f"{dates[0]} → {dates[-1]}" if dates else "sin datos"

    print("🔐 Auditoría de seguridad...")
    security = audit_security(original, sent, load_reviewed_injections(config_dir))

    print("📊 Auditoría de pseudonimización...")
    pseudo = audit_pseudonymization(original, config_dir)

    print("⚡ Auditoría de actividad...")
    perf = audit_performance(original)

    print("🧪 Auditoría de tests...")
    tests = audit_tests(project_root)

    print("📋 Auditoría EFDEF...")
    efdef = audit_efdef(project_root, config_dir)

    print("💾 Guardando informe...")
    report = audit_reports.build_report(
        {
            "security": security,
            "pseudonymization": pseudo,
            "performance": perf,
            "tests": tests,
            "efdef": efdef,
        },
        total,
        date_range,
    )
    report_json = audit_reports.save_report(report, reports_dir)
    reports = audit_reports.list_reports(reports_dir)
    previous = audit_reports.predecessor(reports, report["id"])
    # Se compara la versión ya guardada: mismo formato JSON que el anterior
    # (en memoria hay tuplas que en el JSON son listas).
    saved = next(r for r in reports if r["id"] == report["id"])
    changes = audit_reports.diff_reports(saved, previous)
    audit_reports.write_index(reports, reports_dir)

    print("🎨 Generando dashboard HTML...")

    def _render(base: str) -> str:
        return render_html(
            security,
            pseudo,
            perf,
            tests,
            efdef,
            total,
            date_range,
            generated_at=report["generated_at"].replace("T", " "),
            history_html=audit_reports.render_history_html(report, base),
            changes_html=audit_reports.render_changes_html(changes, previous),
        )

    html = _render("")
    report_html = reports_dir / f"{report['id']}.html"
    audit_reports.write_private(report_html, html)
    audit_reports.write_private(output_path, html)
    if args.output:
        extra = Path(args.output)
        extra.parent.mkdir(parents=True, exist_ok=True)
        base = os.path.relpath(reports_dir.resolve(), extra.parent.resolve()) + "/"
        audit_reports.write_private(extra, _render(base))
        print(f"   Copia adicional: {extra}")
    size_kb = output_path.stat().st_size / 1024
    print(f"✅ Informe guardado: {report_json.name} (+ {report_html.name})")
    print(f"✅ Dashboard: {output_path}  ({size_kb:.1f} KB)")
    print(f"   Histórico: {len(reports)} informe(s) en {reports_dir}")
    if previous is None:
        print("   Cambios: primer informe, nada con lo que comparar")
    else:
        worse = sum(c["trend"] == "worse" for c in changes)
        print(f"   Cambios respecto al anterior: {len(changes)} ({worse} a peor)")

    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│ Resumen de auditoría                                    │")
    print("├─────────────────────────────────────────────────────────┤")
    STATUS_ICON = {"good": "✅", "warning": "⚠️ ", "critical": "🔴", "no_data": "⬜"}
    STATUS_LBL = {
        "good": "OK      ",
        "warning": "Revisar ",
        "critical": "Crítico ",
        "no_data": "Sin datos",
    }
    for plan, emoji, label in [
        (security, "🔐", "Seguridad      "),
        (pseudo, "📊", "Pseudonimizac. "),
        (perf, "⚡", "Actividad      "),
        (tests, "🧪", "Tests          "),
        (efdef, "📋", "EFDEF          "),
    ]:
        st = plan.get("status", "no_data")
        print(
            f"│  {emoji} {label}  {STATUS_ICON.get(st,'⬜')} {STATUS_LBL.get(st,'?')}                        │"
        )
    print("└─────────────────────────────────────────────────────────┘")
    print()
    print("🌐 Abrir en navegador:")
    print(f"   file://{output_path.resolve()}")

    if args.open:
        import webbrowser

        webbrowser.open(f"file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
