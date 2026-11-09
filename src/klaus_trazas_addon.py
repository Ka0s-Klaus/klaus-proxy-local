"""Addon de mitmproxy: registra una traza por cada llamada a /v1/messages.

Cumple docs/trazabilidad.md (v0.1). Por cada POST /v1/messages que llega
a la respuesta se escribe una traza con:

- ``input_received``: hash del último mensaje de usuario (nunca el texto).
- ``model_called``: modelo pedido, modelo devuelto por la API, tokens y hash
  de la respuesta. Solo si la API respondió con éxito.
- ``output_emitted``: hash de la respuesta entregada al cliente.
- ``error``: si la API devolvió un error o el guard bloqueó la petición.

Métricas de rendimiento y conexión (docs/trazabilidad.md §4.4) en ``model_called``
y ``error``: ``duration_ms``, ``ttfb_ms``, ``http_status``, ``connection_reused``
y ``connection_strategy``, tomadas de los tiempos del flujo de mitmproxy.

El proxy no tiene verificaciones ni revisión humana, así que esos tipos no se
generan: ``klaus-trazas`` lo muestra tal cual (todas las salidas sin revisión).

Un fallo de este addon se registra en el log y nunca afecta a la petición.
El addon usa el módulo ``Klaus_proxy_local.trazas`` del paquete, que es el
único que escribe trazas (redacción y permisos incluidos).
"""

from __future__ import annotations

import json
import re
from typing import Any

try:  # el paquete debe estar instalado en el venv del proxy
    import hashlib as _hashlib

    from Klaus_proxy_local import trazas

    _IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depende del entorno
    trazas = None  # type: ignore[assignment]
    _hashlib = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc

PROVIDER = "anthropic"
DESTINATION = "cliente"
MESSAGES_PATH = "/v1/messages"
# Errores que suelen ser transitorios: el cliente puede reintentar.
RECOVERABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504, 529})

_RE_MODEL = re.compile(r'"model"\s*:\s*"([^"]+)"')
_RE_INPUT_TOKENS = re.compile(r'"input_tokens"\s*:\s*(\d+)')
_RE_OUTPUT_TOKENS = re.compile(r'"output_tokens"\s*:\s*(\d+)')


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "sha256:" + _hashlib.sha256(data).hexdigest()


def _text_of(content: Any) -> str:
    """Representación de un ``content`` de mensaje para calcular su hash.

    Cadena: el texto. Lista de bloques: el texto de los bloques ``text`` si los hay.
    Si no los hay (p. ej. Claude Code envía ``tool_result``), se usa la forma
    canónica del contenido: así cada entrada tiene su propio hash y no todas
    colapsan en el hash de la cadena vacía.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        texts = [p for p in parts if isinstance(p, str)]
        if texts:
            return "\n".join(texts)
        return json.dumps(content, sort_keys=True, ensure_ascii=False)
    return (
        json.dumps(content, sort_keys=True, ensure_ascii=False)
        if content is not None
        else ""
    )


def last_user_text(body: dict[str, Any]) -> str:
    """Texto del último mensaje de usuario de una petición /v1/messages."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return _text_of(message.get("content"))
    return ""


def request_params(body: dict[str, Any]) -> dict[str, Any]:
    """Parámetros de muestreo de la petición que la especificación pide (§4.2)."""
    params: dict[str, Any] = {"requested_model": body.get("model")}
    for key in ("temperature", "top_p", "max_tokens"):
        if key in body:
            params[key] = body[key]
    return params


def returned_model(raw: bytes) -> str | None:
    """Modelo que devolvió la API: JSON normal o primer ``message_start`` en SSE."""
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("model"), str):
            return data["model"]
    except json.JSONDecodeError:
        pass
    match = _RE_MODEL.search(text)
    return match.group(1) if match else None


def usage_tokens(raw: bytes) -> tuple[int | None, int | None]:
    """Tokens de entrada y salida. En SSE, el de salida llega al final."""
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        return usage.get("input_tokens"), usage.get("output_tokens")
    except (json.JSONDecodeError, AttributeError):
        pass
    input_match = _RE_INPUT_TOKENS.search(text)
    output_matches = _RE_OUTPUT_TOKENS.findall(text)
    input_tokens = int(input_match.group(1)) if input_match else None
    output_tokens = int(output_matches[-1]) if output_matches else None
    return input_tokens, output_tokens


def _log(msg: str) -> None:
    try:
        from mitmproxy import ctx

        ctx.log.error(msg)
    except Exception:
        print(msg)


def _ms(start: float | None, end: float | None) -> int | None:
    """Milisegundos entre dos instantes (segundos epoch). ``None`` si no se conocen."""
    if start is None or end is None:
        return None
    return max(0, round((end - start) * 1000))


def performance_fields(
    request_start: float | None,
    response_start: float | None,
    response_end: float | None,
    tcp_setup: float | None,
    strategy: str | None,
) -> dict[str, Any]:
    """Métricas de rendimiento y conexión (§4.4), solo con los datos conocidos.

    ``connection_reused`` es ``True`` si la conexión upstream se abrió antes de
    que llegara esta petición. Si no se conoce el instante de apertura, el campo
    se omite: en el informe cuenta como «sin dato», nunca como ``False``.
    Los campos desconocidos se omiten; no se inventan valores.
    """
    fields: dict[str, Any] = {}
    duration = _ms(request_start, response_end)
    if duration is not None:
        fields["duration_ms"] = duration
    ttfb = _ms(request_start, response_start)
    if ttfb is not None:
        fields["ttfb_ms"] = ttfb
    if request_start is not None and tcp_setup is not None:
        fields["connection_reused"] = tcp_setup < request_start
    if strategy:
        fields["connection_strategy"] = strategy
    return fields


def timing_of(flow: Any) -> dict[str, Any]:
    """Métricas de un ``HTTPFlow`` de mitmproxy. Tolerante a versiones distintas."""
    req = getattr(flow, "request", None)
    resp = getattr(flow, "response", None)
    server = getattr(flow, "server_conn", None)
    strategy = None
    try:
        from mitmproxy import ctx

        strategy = getattr(ctx.options, "connection_strategy", None)
    except Exception:
        strategy = None
    fields = performance_fields(
        request_start=getattr(req, "timestamp_start", None),
        response_start=getattr(resp, "timestamp_start", None),
        response_end=getattr(resp, "timestamp_end", None),
        tcp_setup=getattr(server, "timestamp_tcp_setup", None),
        strategy=strategy if isinstance(strategy, str) else None,
    )
    code = getattr(resp, "status_code", None)
    if isinstance(code, int):
        fields["http_status"] = code
    return fields


def record_exchange(
    request_body: bytes,
    status: int | None,
    response_body: bytes,
    blocked: bool,
    trace_dir: Any = None,
    timing: dict[str, Any] | None = None,
) -> str | None:
    """Escribe la traza de una llamada. Devuelve el ``trace_id`` o ``None``.

    ``timing`` son las métricas de rendimiento (ver ``performance_fields``); se
    añaden a ``model_called`` o ``error`` cuando la API llegó a responder.
    Nunca lanza excepciones: cualquier fallo se registra en el log del proxy.
    Función independiente de mitmproxy: se prueba sin proxy.
    """
    try:
        return _record_exchange(
            request_body, status, response_body, blocked, trace_dir, timing or {}
        )
    except Exception as exc:
        _log(f"[klaus-trazas] no se pudo registrar la llamada: {exc}")
        return None


def _with_timing(payload: dict[str, Any], timing: dict[str, Any]) -> dict[str, Any]:
    """Payload con las métricas de rendimiento añadidas (sin modificar el original)."""
    return {**payload, **timing}


def _record_exchange(
    request_body: bytes,
    status: int | None,
    response_body: bytes,
    blocked: bool,
    trace_dir: Any,
    timing: dict[str, Any],
) -> str | None:
    try:
        body = json.loads(request_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict) or "model" not in body:
        return None

    ctx = trazas.start_trace(last_user_text(body), channel="proxy", trace_dir=trace_dir)
    try:
        if blocked:
            trazas.record_event(
                ctx,
                "error",
                {
                    "error_code": "BLOCKED_BY_GUARD",
                    "error_message": "petición bloqueada por el guard: pendiente de aprobación",
                    "recoverable": True,
                },
            )
            trazas.end_trace(ctx, status="blocked")
            return ctx.trace_id

        if status is None:
            trazas.record_event(
                ctx,
                "error",
                _with_timing(
                    {
                        "error_code": "NO_RESPONSE",
                        "error_message": "la API no devolvió respuesta",
                        "recoverable": False,
                    },
                    timing,
                ),
            )
            trazas.end_trace(ctx, status="error")
            return ctx.trace_id

        if status >= 400:
            trazas.record_event(
                ctx,
                "error",
                _with_timing(
                    {
                        "error_code": f"HTTP_{status}",
                        "error_message": f"la API respondió con HTTP {status}",
                        "recoverable": status in RECOVERABLE_STATUS,
                    },
                    timing,
                ),
            )
            trazas.end_trace(ctx, status="error")
            return ctx.trace_id

        input_tokens, output_tokens = usage_tokens(response_body)
        model_payload = request_params(body)
        model_payload.update(
            {
                "returned_model": returned_model(response_body) or "no_devuelto",
                "provider": PROVIDER,
                "output_hash": _sha256(response_body),
            }
        )
        if input_tokens is not None:
            model_payload["input_tokens"] = input_tokens
        if output_tokens is not None:
            model_payload["output_tokens"] = output_tokens
        model_payload = _with_timing(model_payload, timing)
        model_id = trazas.record_event(ctx, "model_called", model_payload)
        trazas.record_event(
            ctx,
            "output_emitted",
            {
                "output_hash": _sha256(response_body),
                "destination": DESTINATION,
            },
            parent_event_id=model_id,
        )
        trazas.end_trace(ctx, status="ok")
        return ctx.trace_id
    except Exception as exc:
        # Ya hay un input_received escrito: la traza queda con error explícito
        _log(f"[klaus-trazas] error registrando la traza {ctx.trace_id}: {exc}")
        return ctx.trace_id


class KlausTrazasAddon:
    """Addon de mitmproxy: una traza por cada POST /v1/messages."""

    def response(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        if trazas is None:
            _log(f"[klaus-trazas] módulo no disponible: {_IMPORT_ERROR}")
            return
        req = flow.request
        if req.method != "POST" or not req.path.startswith(MESSAGES_PATH):
            return
        try:
            meta = getattr(flow, "metadata", {}) or {}
            resp = flow.response
            record_exchange(
                request_body=req.content or b"",
                status=resp.status_code if resp is not None else None,
                # .content = cuerpo decodificado (gzip/br). raw_content son bytes comprimidos.
                response_body=(resp.content or b"") if resp is not None else b"",
                blocked=bool(meta.get("anthropic_blocked")),
                timing=timing_of(flow),
            )
        except Exception as exc:
            _log(f"[klaus-trazas] fallo inesperado: {exc}")


# mitmproxy busca una variable de módulo ``addons``.
addons = [KlausTrazasAddon()]
