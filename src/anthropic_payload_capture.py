#!/usr/bin/env python3
"""Addon de mitmproxy para auditar el payload enviado a la API de Anthropic.

Objetivo (privacidad / compliance): capturar el cuerpo EXACTO de cada request
que Claude Code (u otro cliente) envía a ``api.anthropic.com``, de forma que un
DPO pueda documentar qué información sale hacia la API.

Uso:
    mitmdump -s src/anthropic_payload_capture.py

Y enrutando el cliente a través del proxy (ver docs/anthropic-audit-proxy.md):
    HTTPS_PROXY=http://127.0.0.1:8080 \
    NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem \
    claude -p "hola"

Cada request a Anthropic se vuelca en ``captures/`` con el formato
``YYYYMMDD_HHMMSS_anthropic_payload.json``. Los secretos (API key, Authorization)
se redactan por defecto para que la evidencia sea segura de versionar.

El módulo separa la lógica pura (redacción, construcción del registro, nombre de
fichero) de los hooks de mitmproxy, de modo que sea unit-testable sin arrancar el
proxy.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# --- Configuración -----------------------------------------------------------

# Hosts a auditar. Por defecto se incluye tanto la API pública de Anthropic como
# el gateway LLM corporativo de customer 1, ya que la inferencia real (/v1/messages)
# se enruta a través de este último. Ampliable vía ANTHROPIC_CAPTURE_HOSTS
# (lista separada por comas).
_DEFAULT_HOSTS = (
    "api.anthropic.com",
    "llm.tools.cloud.customer1.es",
)


def _configured_hosts() -> tuple[str, ...]:
    override = os.environ.get("ANTHROPIC_CAPTURE_HOSTS")
    if override:
        return tuple(h.strip().lower() for h in override.split(",") if h.strip())
    return _DEFAULT_HOSTS


ANTHROPIC_HOSTS = _DEFAULT_HOSTS

# Cabeceras cuyo valor se enmascara en la evidencia.
SENSITIVE_HEADERS = {
    "x-api-key",
    "authorization",
    "anthropic-organization-id",
    "cookie",
    "set-cookie",
}

REDACTION = "«REDACTED»"

# Directorio de salida: captures/ relativo a la raíz del proyecto (tooling).
# Permite override por env var para tests / rutas alternativas.
_DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "captures"


def output_dir() -> Path:
    """Directorio base donde se escriben las evidencias."""
    override = os.environ.get("ANTHROPIC_CAPTURE_DIR")
    return Path(override) if override else _DEFAULT_OUTPUT


# Subdirectorios espejo: `sent/` (lo que salió del equipo, ya seudonimizado) y
# `original/` (los mismos datos ANTES de seudonimizar, con los secretos Tier-1
# redactados). Mismo nombre de fichero en ambos → comparación con `diff` directa.
SENT_SUBDIR = "sent"
ORIGINAL_SUBDIR = "original"


def sent_dir() -> Path:
    """Subdirectorio de payloads tal y como salieron (seudonimizados)."""
    return output_dir() / SENT_SUBDIR


def original_dir() -> Path:
    """Subdirectorio de payloads originales (datos reales, secretos redactados)."""
    return output_dir() / ORIGINAL_SUBDIR


def is_anthropic_host(host: str) -> bool:
    """True si el host está en la lista de hosts auditados (Anthropic o gateway)."""
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in _configured_hosts())


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Devuelve una copia de las cabeceras con los secretos enmascarados."""
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            redacted[key] = REDACTION
        else:
            redacted[key] = value
    return redacted


def apply_forward(text: str | None, mapping: dict[str, str]) -> str | None:
    """Reemplaza valores reales por sus seudónimos ya conocidos (longest-first),
    SIN acuñar ninguno nuevo. Espejo de la reversión del seudonimizador; se usa
    para seudonimizar url/host/cabeceras del registro `sent` con los MISMOS
    seudónimos que ya aplicó al cuerpo, para que la evidencia sea coherente.
    """
    if not text or not mapping:
        return text
    for real in sorted(mapping, key=len, reverse=True):
        if real and real in text:
            text = text.replace(real, mapping[real])
    return text


def parse_body(raw: bytes | str | None) -> Any:
    """Intenta decodificar el cuerpo como JSON; si no, lo devuelve como texto.

    Acepta ``bytes`` (cuerpo crudo de la request) o ``str`` (el cuerpo
    ``original`` ya decodificado que el seudonimizador deja en ``flow.metadata``).
    """
    if not raw:
        return None
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
    else:
        text = raw
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def build_record(
    *,
    method: str,
    url: str,
    host: str,
    path: str,
    headers: dict[str, str],
    body: bytes | str | None,
    captured_at: datetime,
    redact: bool = True,
    variant: str = "sent",
    pseudonymized: bool = False,
    counterpart: str | None = None,
) -> dict[str, Any]:
    """Construye el registro de auditoría de una request.

    ``variant``: ``"sent"`` (cuerpo seudonimizado que salió del equipo) u
    ``"original"`` (los mismos datos antes de seudonimizar, con los secretos
    Tier-1 redactados). ``pseudonymized`` indica si la seudonimización reescribió
    el cuerpo. ``counterpart`` es el nombre del fichero pareja en el subdir
    hermano, para localizar el par a comparar.
    """
    hdrs = redact_headers(headers) if redact else dict(headers)
    return {
        "captured_at": captured_at.isoformat(),
        "variant": variant,
        "pseudonymized": pseudonymized,
        "counterpart": counterpart,
        "method": method,
        "url": url,
        "host": host,
        "path": path,
        "secrets_redacted": redact,
        "headers": hdrs,
        "payload": parse_body(body),
    }


def evidence_filename(captured_at: datetime) -> str:
    """Nombre de fichero de evidencia con timestamp: YYYYMMDD_HHMMSS_anthropic_payload.json."""
    return captured_at.strftime("%Y%m%d_%H%M%S") + "_anthropic_payload.json"


def write_record(
    record: dict[str, Any], captured_at: datetime, directory: Path | None = None
) -> Path:
    """Escribe el registro en disco y devuelve la ruta del fichero."""
    directory = directory or output_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / evidence_filename(captured_at)
    # Evita colisiones si dos requests caen en el mismo segundo.
    counter = 1
    while path.exists():
        path = directory / (
            captured_at.strftime("%Y%m%d_%H%M%S") + f"_anthropic_payload_{counter}.json"
        )
        counter += 1
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def evidence_paths(
    captured_at: datetime, sent_directory: Path, original_directory: Path
) -> tuple[Path, Path, str]:
    """Nombre de fichero COMPARTIDO por el par sent/original, único en AMBOS dirs.

    Devuelve ``(ruta_sent, ruta_original, nombre)``. El mismo nombre en los dos
    subdirectorios permite comparar el par con un ``diff`` directo. El contador
    ``_N`` se incrementa mientras el nombre exista en cualquiera de los dos dirs,
    de modo que el par nunca se desalinea.
    """
    base = captured_at.strftime("%Y%m%d_%H%M%S")
    name = base + "_anthropic_payload.json"
    counter = 1
    while (sent_directory / name).exists() or (original_directory / name).exists():
        name = f"{base}_anthropic_payload_{counter}.json"
        counter += 1
    return sent_directory / name, original_directory / name, name


# --- Hooks de mitmproxy -------------------------------------------------------
# Se importan de forma perezosa: el módulo debe poder importarse en tests sin
# tener mitmproxy instalado.


class AnthropicPayloadCapture:
    """Addon de mitmproxy: vuelca cada request a Anthropic como evidencia."""

    def __init__(self, redact: bool | None = None) -> None:
        # Redacción activada salvo que se pida explícitamente lo contrario.
        if redact is None:
            redact = os.environ.get("ANTHROPIC_CAPTURE_REDACT", "1") != "0"
        self.redact = redact

    def request(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        req = flow.request
        if not is_anthropic_host(req.pretty_host):
            return
        now = datetime.now()

        # El seudonimizador (addon previo) deja en flow.metadata el cuerpo
        # `original` (datos reales, secretos Tier-1 ya redactados) y si hubo
        # reescritura. Si no corrió (deshabilitado, o GET sin cuerpo), el
        # original coincide con lo enviado y pseudonymized=False.
        meta = getattr(flow, "metadata", {}) or {}
        original_body = meta.get("anthropic_original_body")
        pseudonymized = bool(meta.get("anthropic_pseudonymized"))
        if original_body is None:
            original_body = req.raw_content
            pseudonymized = False

        s_dir = sent_dir()
        o_dir = original_dir()
        s_dir.mkdir(parents=True, exist_ok=True)
        o_dir.mkdir(parents=True, exist_ok=True)
        sent_path, original_path, name = evidence_paths(now, s_dir, o_dir)

        # Mapa real→seudónimo poblado por el cuerpo (para url/host/cabeceras).
        fwd = meta.get("anthropic_vault_forward") or {}
        base = dict(
            method=req.method,
            captured_at=now,
            redact=self.redact,
            pseudonymized=pseudonymized,
            counterpart=name,
        )
        # `sent`: destino y cabeceras seudonimizados con el vault del cuerpo, para
        # que no se filtre el host del gateway ni otros valores nuestros.
        sent_headers = {k: apply_forward(v, fwd) for k, v in dict(req.headers).items()}
        sent_record = build_record(
            url=apply_forward(req.pretty_url, fwd),
            host=apply_forward(req.pretty_host, fwd),
            path=apply_forward(req.path, fwd),
            headers=sent_headers,
            body=req.raw_content,
            variant="sent",
            **base,
        )
        # `original`: destino y cabeceras REALES (el cuerpo ya trae datos reales).
        original_record = build_record(
            url=req.pretty_url,
            host=req.pretty_host,
            path=req.path,
            headers=dict(req.headers),
            body=original_body,
            variant="original",
            **base,
        )

        sent_path.write_text(
            json.dumps(sent_record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        original_path.write_text(
            json.dumps(original_record, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        try:
            from mitmproxy import ctx

            ctx.log.info(
                f"[anthropic-capture] {req.method} {req.path} → "
                f"sent/{name} + original/{name} (pseudonymized={pseudonymized})"
            )
        except Exception:
            print(f"[anthropic-capture] {req.method} {req.path} -> {name}")


# mitmproxy busca una variable de módulo ``addons``.
addons = [AnthropicPayloadCapture()]
