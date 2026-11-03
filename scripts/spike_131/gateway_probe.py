"""Addon de medición del spike de la versión servidor (#172, fase 0 de #131).

Se carga en ``mitmdump --mode reverse:https://api.anthropic.com`` DESPUÉS del
seudonimizador y ANTES del guardián. Por cada petición escribe una línea JSON en
``$SPIKE_OUT`` con lo mínimo para responder a R1/R2/R3:

- nombres de cabecera, el esquema de ``Authorization`` y si la petición declara
  el beta de OAuth (R1). **Nunca** guarda valores de credenciales ni cuerpos;
- si llega ``X-Klaus-Token`` con el valor esperado, y se quita antes de
  reenviar (R2). Con ``SPIKE_ENFORCE=1`` responde 403 si falta o no coincide,
  como haría el gateway real
  (403, no 401: ver el informe del spike);
- si el home o el usuario del sistema salen en claro tras seudonimizar;
- estado HTTP y tiempos (R3).

Uso: ver ``run_spike.py``.
"""

from __future__ import annotations

import getpass
import json
import os
import time
from pathlib import Path
from typing import Any

TOKEN_HEADER = "X-Klaus-Token"


class GatewayProbe:
    def __init__(self) -> None:
        self.out = Path(os.environ.get("SPIKE_OUT", "spike-probe.jsonl"))
        self.expected = os.environ.get("SPIKE_TOKEN", "")
        self.enforce = os.environ.get("SPIKE_ENFORCE", "1") == "1"
        self.home = str(Path.home())
        self.user = getpass.getuser()

    def request(self, flow: Any) -> None:
        req = flow.request
        names = sorted({k.lower() for k in req.headers.keys()})
        auth = req.headers.get("authorization", "")
        beta = req.headers.get("anthropic-beta", "")
        token = req.headers.get(TOKEN_HEADER)
        if token is None:
            token_state = "falta"
        elif self.expected and token == self.expected:
            token_state = "ok"
        else:
            token_state = "no-coincide"
        if TOKEN_HEADER in req.headers:
            del req.headers[TOKEN_HEADER]
        body = req.get_text(strict=False) or ""
        flow.metadata["spike"] = {
            "t": time.time(),
            "method": req.method,
            "path": req.path.split("?")[0],
            "header_names": names,
            "auth_scheme": auth.split(" ", 1)[0] if auth else None,
            "has_x_api_key": "x-api-key" in names,
            "oauth_beta": "oauth" in beta.lower(),
            "klaus_token": token_state,
            "klaus_token_forwarded": TOKEN_HEADER in req.headers,
            "home_in_clear": self.home in body,
            "user_in_clear": len(self.user) >= 4 and self.user in body,
            "body_bytes": len(body.encode()),
        }
        if self.enforce and token_state != "ok" and flow.response is None:
            from mitmproxy import http

            # 403 y no 401: con 401 Claude Code cree que su credencial de
            # Anthropic no vale y reintenta en bucle en vez de fallar (#172)
            flow.response = http.Response.make(
                403, b"klaus-gateway: X-Klaus-Token ausente o incorrecto\n"
            )
            flow.metadata["spike"]["rejected_by_gateway"] = True

    def response(self, flow: Any) -> None:
        rec = flow.metadata.get("spike")
        if rec is None:
            return
        res = flow.response
        req = flow.request
        rec["status"] = res.status_code
        rec["content_type"] = res.headers.get("content-type", "").split(";")[0]
        if req.timestamp_end and res.timestamp_start:
            rec["upstream_first_byte_ms"] = round(
                (res.timestamp_start - req.timestamp_end) * 1000
            )
        if req.timestamp_start and res.timestamp_end:
            rec["total_ms"] = round((res.timestamp_end - req.timestamp_start) * 1000)
        with self.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


addons = [GatewayProbe()]
