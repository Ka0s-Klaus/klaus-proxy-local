#!/usr/bin/env python3
"""Verificador de una captura de payload Anthropic (auditoría en un solo comando).

Comprueba, sobre la ÚLTIMA captura de inferencia (``/v1/messages`` hacia el
proveedor) que dejó ``anthropic_payload_capture.py``, que lo que salió del equipo
cumple las tres garantías de la auditoría:

  1. 🎯 **Destino** — la inferencia fue al gateway del proveedor esperado
     (``llm.tools.cloud.customer1.es``), no directa a Anthropic.
  2. 🔑 **Secretos redactados** — las cabeceras sensibles (Authorization/x-api-key/…)
     viajaron como «REDACTED» y no hay ningún token ``sk-…``/``Bearer …`` visible.
  3. 🕵️ **Sin fugas en claro** — ningún valor real del vault de seudonimización
     (rutas, usuario, identidad git, org/repo, emails, IPs) aparece en el cuerpo.
     Además informa (WARN) si NO se detecta ningún seudónimo, señal de que el
     seudonimizador podría no haber actuado.

Diseño: la lógica pura (selección de captura, comprobaciones, enmascarado) está
separada del CLI para poder testearla sin disco real. NUNCA imprime el valor real
de un secreto: los hallazgos se muestran con el seudónimo (seguro) y el valor real
enmascarado.

Uso rápido:
    python3 src/anthropic_capture_verify.py

Ver docs/anthropic-audit-proxy.md §"Verificación en un comando: anthropic-capture-verify".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Configuración ------------------------------------------------------------

DEFAULT_ANTHROPIC_DIR = REPO_ROOT / "captures"
# La verificación se hace sobre lo que REALMENTE salió del equipo → subdir sent/.
# El subdir original/ contiene datos reales A PROPÓSITO (para comparar), así que
# verificarlo dispararía (correctamente) el fallo de fuga: nunca es el objetivo.
DEFAULT_CAPTURE_DIR = DEFAULT_ANTHROPIC_DIR / "sent"
DEFAULT_VAULT = DEFAULT_ANTHROPIC_DIR / ".pseudonym_vault.json"
DEFAULT_PROVIDER_HOST = "llm.tools.cloud.customer1.es"

# Ruta de inferencia real (lo demás —telemetría, catálogo MCP— no lleva prompt).
INFERENCE_PATH_MARKER = "/v1/messages"

# Cabeceras que DEBEN viajar redactadas si están presentes.
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "anthropic-organization-id",
    "cookie",
    "set-cookie",
}
REDACTION_MARKERS = ("«REDACTED»", "«REDACTED:")

# Tokens que jamás deberían aparecer en claro en las cabeceras.
_TOKEN_RES = (
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{6,}", re.IGNORECASE),
)

# Valores del vault de baja sensibilidad: si aparecen, es WARN (no FAIL). Son
# genéricos (loopback, DNS públicos) y su presencia no compromete privacidad.
LOW_SENSITIVITY_LEAKS = frozenset({"127.0.0.1", "0.0.0.0", "8.8.8.8", "::1"})

# Longitud mínima de un valor real para buscarlo (evita falsos positivos por
# substrings triviales).
_MIN_LEAK_LEN = 4


# --- Resultado de una comprobación -------------------------------------------


@dataclass
class Result:
    """Resultado de una comprobación individual."""

    name: str
    level: str  # "pass" | "warn" | "fail"
    detail: str

    @property
    def icon(self) -> str:
        return {"pass": "✅", "warn": "⚠️ ", "fail": "❌"}.get(self.level, "•")


# --- Utilidades puras ---------------------------------------------------------


def discover_captures(directory: Path) -> list[Path]:
    """Devuelve las capturas ``*_anthropic_payload*.json`` ordenadas por nombre.

    El nombre empieza por ``YYYYMMDD_HHMMSS`` así que el orden lexicográfico es
    también cronológico.
    """
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*_anthropic_payload*.json"))


def load_capture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_vault(path: Path) -> dict[str, str]:
    """Carga el vault real→seudónimo; devuelve {} si no existe."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def host_variants(provider_host: str, vault: dict[str, str] | None) -> set[str]:
    """Formas aceptables del host del proveedor: la real y su versión
    seudonimizada. El registro `sent/` guarda el host ya seudonimizado (para no
    filtrar el subdominio corporativo), así que hay que aceptar ambas."""
    variants = {provider_host.lower()}
    if vault:
        h = provider_host
        for real in sorted(vault, key=len, reverse=True):
            if real and real in h:
                h = h.replace(real, vault[real])
        variants.add(h.lower())
    return variants


def is_inference(
    record: dict[str, Any], provider_host: str, vault: dict[str, str] | None = None
) -> bool:
    """True si la captura es la inferencia real hacia el proveedor esperado
    (acepta el host real o su seudónimo)."""
    host = (record.get("host") or "").lower()
    path = record.get("path") or ""
    return host in host_variants(provider_host, vault) and INFERENCE_PATH_MARKER in path


def select_capture(
    paths: Iterable[Path],
    *,
    provider_host: str,
    prefer_inference: bool = True,
    vault: dict[str, str] | None = None,
) -> Path | None:
    """Elige la captura a verificar: la última inferencia; si no hay, la última.

    Devuelve ``None`` si no hay capturas.
    """
    paths = list(paths)
    if not paths:
        return None
    if prefer_inference:
        inference = [
            p for p in paths if is_inference(load_capture(p), provider_host, vault)
        ]
        if inference:
            return inference[-1]
    return paths[-1]


def _serialize(obj: Any) -> str:
    """Serializa a texto para búsqueda de substrings."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False)


def mask(value: str) -> str:
    """Enmascara un valor real para poder reportarlo sin re-exponerlo."""
    if len(value) <= 4:
        return "•" * len(value)
    return f"{value[:2]}{'•' * (len(value) - 3)}{value[-1:]}"


# --- Comprobaciones -----------------------------------------------------------


def check_destination(
    record: dict[str, Any], expected_host: str, vault: dict[str, str] | None = None
) -> Result:
    host = (record.get("host") or "").lower()
    path = record.get("path") or ""
    if host not in host_variants(expected_host, vault):
        return Result(
            "Destino",
            "fail",
            f"host de la captura = {host or '(vacío)'}; esperado {expected_host} (o su seudónimo).",
        )
    marker = "inferencia" if INFERENCE_PATH_MARKER in path else "no-inferencia"
    return Result("Destino", "pass", f"{host}{path}  ({marker})")


def check_secrets_redacted(record: dict[str, Any]) -> Result:
    headers = record.get("headers") or {}
    problems: list[str] = []

    if record.get("secrets_redacted") is not True:
        problems.append("el campo secrets_redacted no es true")

    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            val = str(value)
            if not any(val.startswith(m) for m in REDACTION_MARKERS):
                problems.append(f"cabecera '{key}' no redactada")

    serialized_headers = _serialize(headers)
    for rx in _TOKEN_RES:
        if rx.search(serialized_headers):
            problems.append(f"token en claro en cabeceras (patrón {rx.pattern})")

    if problems:
        return Result("Secretos redactados", "fail", "; ".join(problems))
    return Result(
        "Secretos redactados",
        "pass",
        "cabeceras sensibles = «REDACTED»; sin tokens en claro.",
    )


def find_plaintext_leaks(
    record: dict[str, Any], vault: dict[str, str]
) -> list[tuple[str, str]]:
    """Devuelve [(valor_real, seudónimo)] del vault presentes en cuerpo/cabeceras."""
    haystack = (
        _serialize(record.get("payload")) + "\n" + _serialize(record.get("headers"))
    )
    leaks: list[tuple[str, str]] = []
    for real, pseudo in vault.items():
        if len(real) < _MIN_LEAK_LEN:
            continue
        if real in haystack:
            leaks.append((real, pseudo))
    return leaks


def check_no_plaintext_leaks(record: dict[str, Any], vault: dict[str, str]) -> Result:
    if not vault:
        return Result(
            "Sin fugas en claro",
            "warn",
            "no hay vault de seudonimización; no se puede comprobar fuga de valores reales.",
        )
    leaks = find_plaintext_leaks(record, vault)
    if not leaks:
        return Result(
            "Sin fugas en claro",
            "pass",
            f"ninguno de los {len(vault)} valores reales del vault aparece en el cuerpo.",
        )
    high = [(r, p) for r, p in leaks if r not in LOW_SENSITIVITY_LEAKS]
    low = [(r, p) for r, p in leaks if r in LOW_SENSITIVITY_LEAKS]
    lines = []
    for real, pseudo in high + low:
        sev = "baja" if real in LOW_SENSITIVITY_LEAKS else "ALTA"
        lines.append(f"[{sev}] {mask(real)} (debería ser {pseudo})")
    level = "fail" if high else "warn"
    return Result("Sin fugas en claro", level, "FUGAS: " + "; ".join(lines))


def check_pseudonymization(record: dict[str, Any], vault: dict[str, str]) -> Result:
    """WARN (no fail) si no se ve ningún seudónimo: puede ser un prompt trivial,
    pero también que el seudonimizador no actuara."""
    if not vault:
        return Result("Seudonimización activa", "warn", "sin vault; no verificable.")
    haystack = _serialize(record.get("payload"))
    present = [p for p in set(vault.values()) if p and p in haystack]
    if present:
        return Result(
            "Seudonimización activa",
            "pass",
            f"{len(present)} seudónimo(s) presentes en el cuerpo (reescritura confirmada).",
        )
    return Result(
        "Seudonimización activa",
        "warn",
        "no se detecta ningún seudónimo en el cuerpo. Normal si el prompt no "
        "contenía datos sensibles; revísalo si esperabas rutas/usuario.",
    )


def verify(
    record: dict[str, Any], vault: dict[str, str], *, expected_host: str
) -> list[Result]:
    return [
        check_destination(record, expected_host, vault),
        check_secrets_redacted(record),
        check_no_plaintext_leaks(record, vault),
        check_pseudonymization(record, vault),
    ]


def overall_ok(results: Iterable[Result]) -> bool:
    """True si ninguna comprobación falló (los WARN no tumban el veredicto)."""
    return not any(r.level == "fail" for r in results)


# --- Presentación / CLI -------------------------------------------------------


def format_report(path: Path, record: dict[str, Any], results: list[Result]) -> str:
    lines = [
        "🔍 Verificación de captura Anthropic",
        f"   fichero : {path.name}",
        f"   momento : {record.get('captured_at', '?')}",
        f"   método  : {record.get('method', '?')}  {record.get('path', '')}",
        "",
    ]
    for r in results:
        lines.append(f"{r.icon} {r.name}: {r.detail}")
    lines.append("")
    verdict = "✅ TODO CORRECTO" if overall_ok(results) else "❌ REVISAR — hay fallos"
    lines.append(verdict)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="anthropic-capture-verify",
        description="Verifica en un comando la última captura de payload Anthropic.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Captura concreta a verificar (por defecto: la última inferencia).",
    )
    parser.add_argument(
        "--dir", default=str(DEFAULT_CAPTURE_DIR), help="Directorio de capturas."
    )
    parser.add_argument(
        "--vault", default=str(DEFAULT_VAULT), help="Ruta del vault de seudonimización."
    )
    parser.add_argument(
        "--provider-host",
        default=DEFAULT_PROVIDER_HOST,
        help="Host esperado del proveedor.",
    )
    parser.add_argument(
        "--any",
        action="store_true",
        help="Verifica la última captura aunque no sea inferencia.",
    )
    args = parser.parse_args(argv[1:])

    vault = load_vault(Path(args.vault))

    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"❌ No existe la captura: {path}", file=sys.stderr)
            return 2
    else:
        captures = discover_captures(Path(args.dir))
        # Fallback: las capturas previas al split original/sent viven planas en
        # captures/. Útil justo tras el despliegue, antes de la 1ª captura
        # nueva. Solo aplica si se usa el directorio por defecto (no --dir).
        if not captures and Path(args.dir) == DEFAULT_CAPTURE_DIR:
            hist = discover_captures(DEFAULT_ANTHROPIC_DIR)
            if hist:
                print(
                    f"ℹ️  Sin capturas en {args.dir}; uso histórico "
                    f"{DEFAULT_ANTHROPIC_DIR}.",
                    file=sys.stderr,
                )
                captures = hist
        path = select_capture(
            captures,
            provider_host=args.provider_host,
            prefer_inference=not args.any,
            vault=vault,
        )
        if path is None:
            print(
                f"❌ No hay capturas en {args.dir}. ¿Arrancaste `claude-proxy` y lanzaste `claude` por él?",
                file=sys.stderr,
            )
            return 2

    record = load_capture(path)
    results = verify(record, vault, expected_host=args.provider_host)
    print(format_report(path, record, results))
    return 0 if overall_ok(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
