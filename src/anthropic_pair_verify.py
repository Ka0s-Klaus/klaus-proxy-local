#!/usr/bin/env python3
"""Validador diferencial ``original`` ↔ ``sent`` del proxy de auditoría.

Empareja cada captura ``captures/original/<n>`` (datos reales, secretos Tier-1 ya
redactados) con su gemela ``captures/sent/<n>`` (lo que REALMENTE salió del equipo,
seudonimizado) y comprueba que **ningún dato sensible del original sobrevive
verbatim en el sent**.

Por qué existe (y por qué complementa a ``anthropic_capture_verify.py``):
    El verificador de una sola captura busca fugas comparando el cuerpo con el
    **vault** (valores reales → seudónimo). Tiene un punto ciego: si un
    identificador NUNCA se seudonimizó (p.ej. porque no estaba en
    ``ANTHROPIC_PSEUDO_WORD_LITERALS``) tampoco entró al vault, así que no hay
    valor que buscar y la fuga pasa en silencio. Este validador NO depende del
    vault: deriva "lo sensible" del propio ``original`` + el entorno + los mismos
    patrones del seudonimizador, y verifica que no reaparezca en ``sent``.

Capas de detección:
    - **HARD → FAIL**: emails, IPv4 (no loopback/DNS público), prefijos de ruta
      home/proj, usuario/identidad git, word-literals + tokens de remote, y
      valores del vault presentes en el original que reaparecen en el sent.
    - **SECRET → FAIL**: un secreto Tier-1 (PEM/AWS/GitHub/JWT/…) en claro en el
      sent (en el original ya viaja como «REDACTED:…»; si aparece sin redactar en
      lo que salió, es fuga).

El veredicto (exit code) lo deciden SOLO las capas HARD/SECRET: son precisas y
accionables. Aparte, el modo de descubrimiento ``--survivors`` emite una tabla
global de *slugs con guion* (``org-repo``) que sobreviven de original a sent en el
CONTENIDO de los mensajes y no son vocabulario conocido — candidatos a añadir a
``ANTHROPIC_PSEUDO_WORD_LITERALS`` (pre-flight P4). Es un apoyo heurístico de
revisión, NO un veredicto: nunca afecta al exit code.

Diseño: la lógica pura (emparejado, detección, diff) está separada del CLI para
testearla sin disco real. Los valores reales confirmados como sensibles se
reportan SIEMPRE enmascarados (``mask``), nunca en claro.

Uso rápido:
    python3 src/anthropic_pair_verify.py               # barrido de todos los pares
    python3 src/anthropic_pair_verify.py <nombre.json> # un par concreto
    python3 src/anthropic_pair_verify.py --survivors   # tabla de slugs a revisar

Ver docs/anthropic-audit-proxy.md §"Validación diferencial por pares".
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic_capture_verify import (
    _MIN_LEAK_LEN,
    LOW_SENSITIVITY_LEAKS,
    Result,
    _serialize,
    load_capture,
    load_vault,
    mask,
)
from anthropic_payload_pseudonymize import (
    _EMAIL_RE,
    _IPV4_RE,
    _SECRET_RES,
    Rules,
    build_rules,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Configuración ------------------------------------------------------------

DEFAULT_ANTHROPIC_DIR = REPO_ROOT / "captures"
DEFAULT_ORIGINAL_DIR = DEFAULT_ANTHROPIC_DIR / "original"
DEFAULT_SENT_DIR = DEFAULT_ANTHROPIC_DIR / "sent"
DEFAULT_VAULT = DEFAULT_ANTHROPIC_DIR / ".pseudonym_vault.json"

_CAPTURE_GLOB = "*_anthropic_payload*.json"

# Slug con guion (``org-repo``, ``kyndryl-global-delivery``, ``Ka0s-Klaus``): forma
# de alto valor para identificadores privados y rara en el andamiaje de la API
# (los esquemas de tools usan snake_case/camelCase, no slugs con guion).
_SLUG_RE = re.compile(r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b")

# Seudónimos acuñados por el vault: ``prefix_<hash8>`` (con posibles ``z`` de
# resolución de colisión). Aparecen en el sent A PROPÓSITO, no son fugas.
_PSEUDO_TOKEN_RE = re.compile(r"^[A-Za-z]+_[0-9a-f]{8}z*$")

# Slugs de forma reconocible que NUNCA son datos del proyecto: UUIDs, fechas ISO,
# rangos numéricos (``10-20``) y flags/betas de la propia API (``claude-…``,
# ``anthropic-…``, cabeceras ``x-…``). Se excluyen del descubrimiento.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_DATEISH_RE = re.compile(r"^\d{4}-\d{2}")
_NUMERIC_SLUG_RE = re.compile(r"^\d+(?:-\d+)+$")
_SURVIVOR_SKIP_PREFIX = ("claude-", "anthropic-", "x-", "sk-ant-")

# Slugs comunes del lenguaje/andamiaje que NO son identificadores privados.
_SURVIVOR_ALLOW = frozenset(
    {
        "read-only",
        "well-known",
        "up-to-date",
        "end-to-end",
        "opt-in",
        "opt-out",
        "fine-grained",
        "co-authored",
        "multi-select",
        "single-select",
        "case-sensitive",
        "case-insensitive",
        "line-buffered",
        "real-time",
        "cross-host",
        "non-trivial",
        "sub-agent",
        "tool-use",
        "tool-result",
        "world-readable",
        "self-hosted",
        "so-called",
        "step-by-step",
        "multi-step",
        "trade-offs",
        "general-purpose",
        "system-reminder",
        "task-notification",
        "built-in",
        "one-off",
        "one-line",
        "one-liner",
        "fan-out",
        "re-run",
        "re-runs",
        "dry-run",
        "round-trip",
        "hot-reload",
        "fail-closed",
        "data-at-rest",
        "long-running",
        "mid-session",
        "multi-repo",
        "multi-agent",
        "server-hosted",
    }
)


# --- Emparejado ---------------------------------------------------------------


def discover_pairs(
    original_dir: Path, sent_dir: Path
) -> tuple[list[tuple[str, Path, Path]], list[tuple[str, str]]]:
    """Empareja capturas por nombre de fichero (compartido por el par).

    Devuelve ``(pairs, orphans)`` donde ``pairs = [(nombre, ruta_original,
    ruta_sent)]`` y ``orphans = [(nombre, falta)]`` con ``falta`` ∈
    {``"original"``, ``"sent"``}. El orden es lexicográfico = cronológico.
    """
    orig = (
        {p.name: p for p in original_dir.glob(_CAPTURE_GLOB)}
        if original_dir.is_dir()
        else {}
    )
    sent = (
        {p.name: p for p in sent_dir.glob(_CAPTURE_GLOB)} if sent_dir.is_dir() else {}
    )
    pairs: list[tuple[str, Path, Path]] = []
    orphans: list[tuple[str, str]] = []
    for name in sorted(set(orig) | set(sent)):
        if name in orig and name in sent:
            pairs.append((name, orig[name], sent[name]))
        elif name in orig:
            orphans.append((name, "sent"))
        else:
            orphans.append((name, "original"))
    return pairs, orphans


# --- Detección de valores sensibles en el original ----------------------------


@dataclass(frozen=True)
class Span:
    """Un valor real que NO debería reaparecer verbatim en el sent."""

    value: str
    category: str  # "email" | "ipv4" | "path" | "identity" | "org" | "vault"


def _record_text(record: dict[str, Any]) -> str:
    """Serializa cuerpo + cabeceras de un registro para búsqueda de substrings."""
    return _serialize(record.get("payload")) + "\n" + _serialize(record.get("headers"))


def sensitive_spans(
    record: dict[str, Any], vault: dict[str, str], rules: Rules
) -> list[Span]:
    """Extrae del ``original`` los valores reales que deben desaparecer en el sent.

    Deriva la sensibilidad de tres fuentes independientes del vault: regex
    (email/IPv4), reglas del seudonimizador (rutas home/proj, identidad/usuario,
    org/repo) y —adicionalmente— los valores del propio vault. Dedup por valor.
    """
    text = _record_text(record)
    seen: set[str] = set()
    spans: list[Span] = []

    def add(value: str, category: str) -> None:
        value = (value or "").strip()
        if len(value) < _MIN_LEAK_LEN or value in seen:
            return
        if value not in text:
            return
        seen.add(value)
        spans.append(Span(value, category))

    # 1) Regex de forma reconocible.
    for m in _EMAIL_RE.findall(text):
        add(m, "email")
    for m in _IPV4_RE.findall(text):
        if m not in LOW_SENSITIVITY_LEAKS:
            add(m, "ipv4")

    # 2) Reglas del seudonimizador (autodetectadas del entorno).
    for prefix, _label in rules.path_prefixes:
        add(prefix, "path")
    for lit in rules.literals:
        add(lit, "identity")
    for word in rules.word_literals:
        add(word, "org")

    # 3) Valores reales del vault presentes en el original.
    for real in vault:
        add(real, "vault")

    return spans


def diff_leaks(spans: list[Span], sent_record: dict[str, Any]) -> list[Span]:
    """Spans sensibles del original que reaparecen VERBATIM en el sent (= fuga)."""
    haystack = _record_text(sent_record)
    return [s for s in spans if s.value in haystack]


def secrets_in_sent(sent_record: dict[str, Any]) -> list[str]:
    """Etiquetas de secretos Tier-1 que viajan EN CLARO (sin redactar) en el sent."""
    haystack = _serialize(sent_record.get("payload"))
    found: list[str] = []
    for regex, label in _SECRET_RES:
        if regex.search(haystack) and label not in found:
            found.append(label)
    return found


def _scaffold_allow(record: dict[str, Any]) -> set[str]:
    """Tokens de andamiaje de la API (nombres de tools, modelo): nunca son datos
    del usuario, así que se excluyen de la heurística de supervivientes."""
    allow: set[str] = set()
    payload = record.get("payload")
    if isinstance(payload, dict):
        for tool in payload.get("tools", []) or []:
            if isinstance(tool, dict) and isinstance(tool.get("name"), str):
                allow.add(tool["name"])
        if isinstance(payload.get("model"), str):
            allow.add(payload["model"])
    return allow


def _iter_content_text(content: Any):
    """Texto plano de un content block (str o lista de bloques anidados)."""
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    yield block["text"]
                if "content" in block:
                    yield from _iter_content_text(block["content"])
                if isinstance(block.get("input"), dict):
                    yield _serialize(block["input"])


def message_text(record: dict[str, Any]) -> str:
    """Solo el CONTENIDO de los mensajes (turnos de usuario, tool_use/tool_result).

    Es donde vive el dato del proyecto auditado. Excluye a propósito ``system``,
    ``tools`` y cabeceras: son andamiaje de Anthropic/Claude Code y su vocabulario
    (slugs tipo ``fan-out``, ``system-reminder``) ahoga cualquier señal real.
    """
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return ""
    parts: list[str] = []
    for msg in payload.get("messages", []) or []:
        parts.extend(_iter_content_text(msg.get("content")))
    return "\n".join(parts)


def survivor_tokens(
    original_record: dict[str, Any],
    sent_record: dict[str, Any],
    vault: dict[str, str] | None = None,
) -> list[str]:
    """Slugs con guion presentes en el CONTENIDO de original Y de sent, filtrando
    vocabulario/andamiaje conocido, UUIDs, fechas, rangos y flags de la API.

    Apoyo de descubrimiento (NO veredicto): caza identificadores privados que
    ninguna capa dura detectó — típicamente org/repo/cliente de OTRO proyecto no
    cubiertos por ``ANTHROPIC_PSEUDO_WORD_LITERALS``. Puede tener falsos
    positivos: es señal para alimentar los word-literals (pre-flight P4).
    """
    allow_low = {a.lower() for a in _SURVIVOR_ALLOW}
    allow_low |= {a.lower() for a in _scaffold_allow(original_record)}
    allow_low |= {a.lower() for a in _scaffold_allow(sent_record)}
    pseudo_values = set(vault.values()) if vault else set()

    original_text = message_text(original_record)
    sent_text = message_text(sent_record)

    survivors: set[str] = set()
    for tok in _SLUG_RE.findall(original_text):
        if len(tok) < _MIN_LEAK_LEN:
            continue
        low = tok.lower()
        if low in allow_low:
            continue
        if tok in pseudo_values or _PSEUDO_TOKEN_RE.match(tok):
            continue
        if _UUID_RE.match(tok) or _DATEISH_RE.match(tok) or _NUMERIC_SLUG_RE.match(tok):
            continue
        if any(low.startswith(p) for p in _SURVIVOR_SKIP_PREFIX):
            continue
        if tok in sent_text:
            survivors.add(tok)
    return sorted(survivors)


def collect_survivors(
    pairs: list[tuple[str, Path, Path]], vault: dict[str, str]
) -> dict[str, int]:
    """Recuento global {slug: nº de pares en que sobrevive} sobre todos los pares."""
    counts: dict[str, int] = {}
    for _name, opath, spath in pairs:
        original = load_capture(opath)
        sent = load_capture(spath)
        for tok in survivor_tokens(original, sent, vault):
            counts[tok] = counts.get(tok, 0) + 1
    return counts


# --- Verificación de un par ---------------------------------------------------


def verify_pair(
    original_record: dict[str, Any],
    sent_record: dict[str, Any],
    vault: dict[str, str],
    rules: Rules,
) -> list[Result]:
    """Ejecuta las comprobaciones diferenciales sobre un par y devuelve Results."""
    results: list[Result] = []

    # 1) Coherencia del par.
    ov = original_record.get("variant")
    sv = sent_record.get("variant")
    if ov == "original" and sv == "sent":
        results.append(Result("Emparejamiento", "pass", "variantes original/sent OK."))
    else:
        results.append(
            Result(
                "Emparejamiento",
                "warn",
                f"variantes inesperadas (original={ov!r}, sent={sv!r}).",
            )
        )

    # 2) Fugas HARD (valores sensibles del original que reaparecen en el sent).
    spans = sensitive_spans(original_record, vault, rules)
    leaks = diff_leaks(spans, sent_record)
    if leaks:
        by_cat: dict[str, list[str]] = {}
        for s in leaks:
            by_cat.setdefault(s.category, []).append(mask(s.value))
        detail = "; ".join(
            f"[{cat}] {', '.join(vals)}" for cat, vals in sorted(by_cat.items())
        )
        results.append(Result("Fugas en claro", "fail", "FUGAS: " + detail))
    else:
        results.append(
            Result(
                "Fugas en claro",
                "pass",
                f"ninguno de los {len(spans)} valores sensibles del original "
                "reaparece en el sent.",
            )
        )

    # 3) Secretos Tier-1 sin redactar en el sent.
    secs = secrets_in_sent(sent_record)
    if secs:
        results.append(
            Result(
                "Secretos redactados",
                "fail",
                f"secreto(s) en claro en el sent: {', '.join(secs)}.",
            )
        )
    else:
        results.append(
            Result("Secretos redactados", "pass", "sin secretos Tier-1 en el sent.")
        )

    return results


def pair_failed(results: list[Result]) -> bool:
    return any(r.level == "fail" for r in results)


def pair_warned(results: list[Result]) -> bool:
    return any(r.level == "warn" for r in results)


# --- Presentación / CLI -------------------------------------------------------


def format_pair(name: str, results: list[Result]) -> str:
    lines = [f"📦 {name}"]
    for r in results:
        lines.append(f"   {r.icon} {r.name}: {r.detail}")
    return "\n".join(lines)


def _resolve_targets(
    args: argparse.Namespace,
) -> tuple[list[tuple[str, Path, Path]], list[tuple[str, str]]]:
    original_dir = Path(args.original_dir)
    sent_dir = Path(args.sent_dir)
    pairs, orphans = discover_pairs(original_dir, sent_dir)
    if args.name:
        pairs = [p for p in pairs if p[0] == args.name]
    return pairs, orphans


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="anthropic-pair-verify",
        description=(
            "Valida por pares original↔sent que ningún dato sensible sobrevive en "
            "lo que salió del equipo (independiente del vault)."
        ),
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Nombre de un par concreto (por defecto: todos los pares).",
    )
    parser.add_argument(
        "--original-dir",
        default=str(DEFAULT_ORIGINAL_DIR),
        help="Directorio de capturas originales.",
    )
    parser.add_argument(
        "--sent-dir",
        default=str(DEFAULT_SENT_DIR),
        help="Directorio de capturas enviadas.",
    )
    parser.add_argument(
        "--vault", default=str(DEFAULT_VAULT), help="Ruta del vault de seudonimización."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Imprime también los pares sin hallazgos.",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="El exit code también falla si hay WARN (modo auditoría estricta).",
    )
    parser.add_argument(
        "--survivors",
        action="store_true",
        help=(
            "Modo descubrimiento: emite la tabla de slugs candidatos a añadir a "
            "ANTHROPIC_PSEUDO_WORD_LITERALS (informativo; no afecta al exit code)."
        ),
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="En --survivors, umbral mínimo de pares para listar un slug.",
    )
    args = parser.parse_args(argv[1:])

    vault = load_vault(Path(args.vault))
    rules = build_rules()
    pairs, orphans = _resolve_targets(args)

    if not pairs:
        target = f" '{args.name}'" if args.name else ""
        print(
            f"❌ No hay pares que verificar{target} en {args.original_dir} ↔ "
            f"{args.sent_dir}.",
            file=sys.stderr,
        )
        return 2

    if args.survivors:
        counts = collect_survivors(pairs, vault)
        listed = sorted(
            ((v, k) for k, v in counts.items() if v >= args.min_count),
            reverse=True,
        )
        print(
            f"🔎 Slugs supervivientes candidatos ({len(listed)} de {len(counts)} "
            f"distintos, en {len(pairs)} par(es)):"
        )
        for count, slug in listed:
            print(f"   {count:>5}  {slug}")
        print(
            "\nℹ️  Revisa cuáles son sensibles y añádelos a "
            "ANTHROPIC_PSEUDO_WORD_LITERALS (pre-flight P4). Informativo: no falla."
        )
        return 0

    n_fail = n_warn = 0
    for name, opath, spath in pairs:
        results = verify_pair(load_capture(opath), load_capture(spath), vault, rules)
        failed = pair_failed(results)
        warned = pair_warned(results)
        n_fail += 1 if failed else 0
        n_warn += 1 if warned else 0
        if failed or warned or args.verbose:
            print(format_pair(name, results))

    print("")
    print(
        f"🔍 Validación diferencial: {len(pairs)} par(es)  ·  "
        f"❌ {n_fail} con fugas  ·  ⚠️  {n_warn} con avisos"
    )
    if orphans and not args.name:
        print(f"⚠️  {len(orphans)} captura(s) huérfana(s) (par incompleto).")

    if n_fail:
        print("❌ REVISAR — hay fugas en claro.")
    elif n_warn and args.fail_on_warn:
        print("⚠️  REVISAR — avisos con --fail-on-warn.")
    else:
        print("✅ Sin fugas en claro.")

    if n_fail or (n_warn and args.fail_on_warn):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
