# 📡 Telemetría de Claude Code → Anthropic (`event_logging`)

> Hallazgo de auditoría · 2026-07-24 · fuente: capturas del proxy en `captures/sent/`

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

### ¿Qué hago?

Documento **qué datos envía Claude Code al endpoint de telemetría** `POST /api/event_logging/v2/batch` de `api.anthropic.com`, y dejo por escrito el veredicto de sensibilidad y la decisión tomada. Surge de una pregunta concreta: las capturas de ese endpoint salen con `pseudonymized=False`, y había que confirmar que eso **no** significa que se filtren datos en claro.

### ¿Cómo lo hago?

Analizando el corpus real de evidencias `captures/sent/` (1432 ficheros del endpoint, 15 934 eventos): catálogo de `event_name`, claves de `event_data` y `env`, y **decodificando** el campo `additional_metadata` (viene en base64) de los eventos que podrían llevar contenido real (comandos, ficheros, prompts).

### ¿Y para qué lo hago?

Para que un DPO tenga evidencia trazable de qué sale hacia Anthropic por el canal de telemetría —distinto del canal de inferencia `/v1/messages`— y pueda justificar por qué **no** se bloquea ni se seudonimiza.

---

## 🧭 `pseudonymized=False` no es "sin seudonimizar"

El flag lo fija el seudonimizador como un **diff**: `pseudonymized = bool(new != original)`. Es `False` cuando el cuerpo totalmente seudonimizado sale **byte a byte igual** que el original, es decir: **no había nada que reescribir** en ese cuerpo (ni rutas, ni usuario, ni emails, ni IPs, ni tokens de org). El seudonimizador **sí corrió**. No es un envío en claro.

Reparto del flag en el corpus auditado:

| Endpoint | `true` | `false` |
| --- | --- | --- |
| `/v1/messages` (inferencia real: prompts, ficheros, identidad) | 309 | 3 |
| `/api/event_logging/v2/batch` (telemetría) | 0 | 1072 |
| `count_tokens` / `mcp-registry` / `eval` | 13 | 16 |

La inferencia real va seudonimizada en **309 de 312** casos (los 3 `false` se verificaron: no contenían usuario/home/org). La telemetría es `false` porque no lleva datos que casen con las reglas.

---

## 🔬 Qué manda la telemetría (evidencia decodificada)

Anthropic diseñó estos eventos para **no exponer contenido**: rutas y contenido van **hasheados**; comandos y prompts se reducen a **longitud y tipo**.

| Evento | Qué manda | Qué NO manda |
| --- | --- | --- |
| `tengu_bash_tool_command_executed` | `command_type:"other"`, `stdout_length`, `exit_code`, `executor_shell:"zsh"` | **el comando en sí** |
| `tengu_file_operation` | `filePathHash`, `contentHash` (SHA) | **la ruta y el contenido** (hasheados) |
| `tengu_input_prompt` | `prompt_length:28`, `prompt_source:"typed"` | **el texto del prompt** |
| `tengu_input_command` | `input:"compact"` (nombre de comando built-in) | — |
| `tengu_dir_search` | `subdir:"commands"`, contadores | rutas |
| `tengu_edit_string_lengths` | `oldStringBytes`, `newStringBytes` | el texto editado |

### Único dato genuinamente identificativo

- **`device_id`** (estable entre sesiones): identificador **de la máquina**. Es lo más trazable del lote.
- **`env`**: `platform`, `terminal` (`iTerm.app`), `shell` (`zsh`), `arch`, `node_version`, `version` — fingerprint de entorno genérico.
- `session_id` / `parent_session_id`: UUIDs aleatorios por sesión, meros correladores.

Nada de esto es PII en el sentido de "identifica a una persona física"; es pseudoanónimo a nivel de dispositivo.

---

## ⚖️ Veredicto y decisión

- **Sensibilidad: baja.** La telemetría no lleva prompts, rutas ni contenido en claro — están hasheados o reducidos a metadatos.
- **Seudonimizar no aplica:** el seudonimizador casa rutas/usuario/emails/IPs, y aquí no hay ninguno en claro; no tendría nada que reescribir (sería un no-op).
- **Decisión (2026-07-24): documentar y no bloquear.** Se deja constancia de que salen `device_id` y el fingerprint de `env`. No se activa bloqueo del endpoint ni redacción adicional.
- **Palanca disponible si cambia la política:** bloquear `POST /api/event_logging/v2/batch` en el proxy (responder `200 {}` sin reenviar) es la vía limpia y bajo nuestro control. No implementada por decisión explícita.

---

## 🔗 Relacionado

- [🔍 Auditoría de payload enviado a Anthropic](anthropic-audit-proxy.md) — canal de inferencia y runbook de captura.
- [🔒 Seguridad](security.md) — tratamiento del vault y de las capturas.
