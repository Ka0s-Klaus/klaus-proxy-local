# Especificación: Trazabilidad de ejecuciones de sistemas con IA

> Versión 0.1 · Estado: borrador · Idioma: español
> Documento pensado para usarse como contexto en Claude Code (copiar en la raíz del repositorio como `docs/trazabilidad.md` y referenciarlo desde `CLAUDE.md`).

---

## 1. Objetivo

Registrar cada ejecución de un flujo que involucre modelos de lenguaje, recuperación de datos, herramientas externas o agentes, de forma que sea posible reconstruir **qué entró, qué se usó, qué se generó, qué se comprobó y quién aprobó la salida**.

La trazabilidad sirve para **auditar**, no para **reproducir exactamente** una salida: los modelos pueden ser no deterministas y los proveedores pueden cambiar versiones.

## 2. Alcance

**Incluye**
- Entradas del usuario o del sistema.
- Fuentes recuperadas (RAG) y su versión.
- Prompt y configuración del sistema.
- Modelo, versión devuelta por la API y parámetros de muestreo.
- Llamadas a herramientas (entradas y salidas).
- Pasos de agentes y su orden.
- Comprobaciones de verificación y su resultado.
- Intervención humana (aprobación, rechazo, modificación).
- **Métricas de rendimiento y conexión** de cada llamada al modelo: duración, tiempo hasta la primera respuesta, código HTTP, reutilización de la conexión y estrategia de conexión (ver §4.4). Son métricas de primera clase: el informe de auditoría las muestra.

**No incluye (por ahora)**
- Métricas de coste económico (€ por petición o mensual); se tratan en una especificación aparte.
- Almacenamiento a largo plazo de datos de negocio.
- Explicabilidad interna del modelo (pesos, atención).

## 3. Principios

1. **Un identificador de traza por ejecución.** Todos los registros de una misma ejecución comparten `trace_id`.
2. **Registros inmutables y solo de adición.** Nunca se edita un registro; las correcciones se registran como eventos nuevos.
3. **Versión real, no solo solicitada.** Se guarda la versión de modelo que devolvió la API.
4. **Datos sensibles fuera por defecto.** Se guarda una referencia o un hash del contenido sensible, no el contenido, salvo que la política lo autorice.
5. **Orden reconstruible.** Cada evento tiene `seq` (número dentro de la traza) y `timestamp` en UTC.

## 4. Modelo de datos

Cada evento es un objeto JSON. Los campos comunes son obligatorios en todos los eventos.

### 4.1 Campos comunes

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `event_id` | string (UUID v4) | sí | Identificador único del evento. |
| `trace_id` | string (UUID v4) | sí | Identificador de la ejecución completa. |
| `parent_event_id` | string o null | sí | Evento que causó este. `null` para el evento raíz. |
| `seq` | integer | sí | Orden dentro de la traza, empezando en 1. |
| `timestamp` | string (ISO 8601, UTC) | sí | Momento del evento. |
| `event_type` | string (enum, ver 4.2) | sí | Tipo de evento. |
| `schema_version` | string | sí | Versión de este esquema, p. ej. `"0.1"`. |
| `actor` | string | sí | `user`, `system`, `model`, `tool`, `agent` o `human_reviewer`. |
| `payload` | object | sí | Contenido específico del tipo de evento. |

### 4.2 Tipos de evento

| `event_type` | Qué registra | Campos específicos de `payload` |
|---|---|---|
| `input_received` | Entrada original | `content_hash`, `content_ref` (opcional), `channel` |
| `retrieval_performed` | Recuperación de fuentes | `query`, `sources: [{source_id, version, content_hash}]`, `index_name` |
| `prompt_built` | Prompt final enviado | `prompt_version`, `template_id`, `content_hash` |
| `model_called` | Llamada al modelo | `requested_model`, `returned_model`, `provider`, `temperature`, `top_p`, `max_tokens`, `input_tokens`, `output_tokens`, `output_hash`; opcionales de rendimiento (§4.4) |
| `tool_called` | Llamada a herramienta | `tool_name`, `tool_version`, `input_hash`, `output_hash`, `status` |
| `agent_step` | Paso de un agente | `step_name`, `plan_ref`, `outcome` |
| `verification_run` | Comprobación aplicada | `check_name`, `check_version`, `result` (`pass`, `fail`, `warn`), `details_ref` |
| `human_review` | Intervención humana | `reviewer_id`, `decision` (`approved`, `rejected`, `modified`), `comment_ref` |
| `output_emitted` | Salida entregada al usuario o a otro sistema | `output_hash`, `destination` |
| `error` | Fallo en cualquier paso | `error_code`, `error_message`, `recoverable`; opcionales de rendimiento (§4.4) |

### 4.3 Reglas de integridad

- Todo `trace_id` debe tener **exactamente un** evento con `parent_event_id: null`.
- `seq` debe ser **consecutivo** dentro de cada traza, sin huecos.
- Todo `parent_event_id` debe referir a un `event_id` existente dentro de la misma traza.
- Un `output_emitted` no puede existir sin un `model_called` previo en la misma traza.
- Si existe un `human_review` con `decision: approved`, debe seguir a una `output_emitted` o precederla según el flujo, nunca quedar huérfano.

### 4.4 Métricas de rendimiento y conexión 📈

Se registran en los eventos `model_called` (llamada completada) y `error` (llamada que falló tras enviarse a la API). Son **campos opcionales**: una traza anterior a su introducción sigue siendo válida y se cuenta como «sin dato», nunca como 0.

| Campo | Tipo | Descripción |
|---|---|---|
| `duration_ms` | integer ≥ 0 | Tiempo total desde que se envía la petición hasta que termina la respuesta (en ms). |
| `ttfb_ms` | integer ≥ 0 | Tiempo hasta la primera respuesta de la API (cabeceras), en ms. |
| `http_status` | integer | Código HTTP devuelto por la API. Ausente si no hubo respuesta. |
| `connection_reused` | boolean | `true` si la petición usó una conexión upstream ya abierta; `false` si abrió una nueva. |
| `connection_strategy` | string | Estrategia de conexión upstream activa (p. ej. `lazy`, valor de `connection_strategy` de mitmproxy). |

**Reglas:**

- Un campo que no se puede medir **se omite** (o vale `null`); nunca se rellena con `0` ni con `false`. En el informe cuenta como «sin dato».
- Todos los valores de tiempo son **milisegundos enteros**, medidos en el proxy (no se confía en el reloj del cliente).
- Los campos de rendimiento **nunca** incluyen cabeceras, claves, cuerpos ni contenido: solo números, booleanos y cadenas de configuración.
- `duration_ms` y `ttfb_ms` son aproximaciones de la capa de proxy: incluyen el tiempo de red hasta la API, no el tiempo de procesamiento interno del cliente.
- El informe de auditoría calcula percentiles (p50, p95, p99) solo sobre las trazas que tienen `duration_ms`, e indica qué porcentaje de trazas tiene datos de rendimiento (cobertura).

**Ejemplo de `payload` de `model_called` con métricas:**

```json
{
  "requested_model": "claude-haiku-5-5",
  "returned_model": "claude-haiku-5-5",
  "provider": "anthropic",
  "max_tokens": 1024,
  "input_tokens": 812,
  "output_tokens": 146,
  "output_hash": "sha256:c07e…",
  "duration_ms": 1830,
  "ttfb_ms": 412,
  "http_status": 200,
  "connection_reused": true,
  "connection_strategy": "lazy"
}
```

## 5. Almacenamiento

- Formato: **JSON Lines** (un evento por línea), un fichero por traza o un fichero diario por servicio.
- Solo escritura en adición. Ningún proceso modifica ni borra líneas existentes.
- Ruta sugerida: `logs/trazas/AAAA-MM-DD/<trace_id>.jsonl`.
- Contenido sensible: se almacena en un directorio separado (`logs/contenido/`) referenciado por `content_ref`, con plazo de retención propio.
- Ubicación: **solo ficheros locales**, sin servicios externos de observabilidad en esta versión.
- Acceso: **solo el rol administrador** puede leer los ficheros de traza y el contenido referenciado. Los permisos del sistema de ficheros deben restringir lectura y escritura a ese rol; el resto de usuarios y servicios no tienen acceso de lectura. El proceso que escribe la traza solo necesita permiso de escritura en adición.
- Retención por defecto: **90 días**, configurable por entorno.

## 6. Anonimización y datos sensibles

- Nunca guardar en `payload` secretos, tokens, contraseñas o claves de API.
- Los datos personales se sustituyen por un hash o una referencia.
- Antes de escribir, aplicar un filtro de redacción que detecte patrones habituales (correos, números de identificación, tarjetas). Un fallo del filtro no debe bloquear la ejecución, pero sí generar un evento `error` con `recoverable: true`.

## 7. Interfaz de instrumentación

La instrumentación debe ser **un módulo reutilizable**, no código repetido en cada flujo.

Funciones mínimas que debe exponer:

```
start_trace(input) -> trace_context
record_event(trace_context, event_type, payload, parent_event_id=None) -> event_id
end_trace(trace_context, status) -> None
```

- `trace_context` contiene `trace_id`, `seq` actual y el último `event_id`.
- Si `record_event` falla al escribir, la ejecución principal debe continuar y el fallo se registra en el log de la aplicación.

## 8. Ejemplo de traza completa

Ejecución ficticia de un asistente que responde una consulta con recuperación y revisión humana.

```json
[
  {
    "event_id": "a1f0c3e2-7b1d-4c8a-9e21-0f3b2d5c6a10",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": null,
    "seq": 1,
    "timestamp": "2026-11-06T09:14:02Z",
    "event_type": "input_received",
    "schema_version": "0.1",
    "actor": "user",
    "payload": { "content_hash": "sha256:3f9a…", "channel": "api" }
  },
  {
    "event_id": "b2e1d4f3-8c2e-4d9b-a032-1g4c3e6d7b21",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": "a1f0c3e2-7b1d-4c8a-9e21-0f3b2d5c6a10",
    "seq": 2,
    "timestamp": "2026-11-06T09:14:03Z",
    "event_type": "retrieval_performed",
    "schema_version": "0.1",
    "actor": "system",
    "payload": {
      "query": "política de retención de logs",
      "index_name": "docs-internos",
      "sources": [
        { "source_id": "doc-112", "version": "v3.2", "content_hash": "sha256:91ab…" }
      ]
    }
  },
  {
    "event_id": "c3f2e5a4-9d3f-4e0c-b143-2h5d4f7e8c32",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": "b2e1d4f3-8c2e-4d9b-a032-1g4c3e6d7b21",
    "seq": 3,
    "timestamp": "2026-11-06T09:14:04Z",
    "event_type": "model_called",
    "schema_version": "0.1",
    "actor": "model",
    "payload": {
      "requested_model": "modelo-ejemplo-x",
      "returned_model": "modelo-ejemplo-x-2026-09",
      "provider": "proveedor-ejemplo",
      "temperature": 0.2,
      "input_tokens": 812,
      "output_tokens": 146,
      "output_hash": "sha256:c07e…"
    }
  },
  {
    "event_id": "d4a3f6b5-0e4a-4f1d-8254-3i6e5g8f9d43",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": "c3f2e5a4-9d3f-4e0c-b143-2h5d4f7e8c32",
    "seq": 4,
    "timestamp": "2026-11-06T09:14:05Z",
    "event_type": "verification_run",
    "schema_version": "0.1",
    "actor": "system",
    "payload": { "check_name": "cita_a_fuente", "check_version": "1.0", "result": "warn", "details_ref": "logs/contenido/d4a3f6b5.json" }
  },
  {
    "event_id": "e5b4a7c6-1f5b-4a2e-9365-4j7f6h9g0e54",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": "d4a3f6b5-0e4a-4f1d-8254-3i6e5g8f9d43",
    "seq": 5,
    "timestamp": "2026-11-06T09:16:40Z",
    "event_type": "human_review",
    "schema_version": "0.1",
    "actor": "human_reviewer",
    "payload": { "reviewer_id": "rev-07", "decision": "modified", "comment_ref": "logs/contenido/e5b4a7c6.txt" }
  },
  {
    "event_id": "f6c5b8d7-2a6c-4b3f-a476-5k8g7i0h1f65",
    "trace_id": "7d2e9b40-3c11-4f7a-8b6e-5a1c0d9f2e33",
    "parent_event_id": "e5b4a7c6-1f5b-4a2e-9365-4j7f6h9g0e54",
    "seq": 6,
    "timestamp": "2026-11-06T09:16:41Z",
    "event_type": "output_emitted",
    "schema_version": "0.1",
    "actor": "system",
    "payload": { "output_hash": "sha256:5d1b…", "destination": "usuario-final" }
  }
]
```

Lectura de la traza: desde la salida entregada (`seq 6`) se llega a la revisión humana (`seq 5`), a la verificación que dio `warn` (`seq 4`), al modelo y versión real (`seq 3`), a la fuente concreta y su versión (`seq 2`) y a la entrada (`seq 1`).

## 9. Criterios de aceptación

- [ ] Toda ejecución genera una traza con un único evento raíz.
- [ ] Ningún registro se modifica después de escribirse (verificable con hash de línea o comprobación de solo adición).
- [ ] Dada una `output_emitted`, es posible recorrer hasta la entrada con `parent_event_id` sin ambigüedad.
- [ ] La `returned_model` se guarda siempre que la API la devuelva.
- [ ] Ningún secreto aparece en los ficheros de traza (prueba automatizada con patrones conocidos).
- [ ] Un fallo al escribir la traza no interrumpe la respuesta al usuario.
- [ ] Existe un validador que comprueba las reglas de la sección 4.3 sobre un fichero de traza.
- [ ] Solo el rol administrador puede leer trazas y contenido referenciado (verificable con los permisos del sistema de ficheros).
- [ ] Las llamadas al modelo registran `duration_ms`, `http_status` y `connection_reused` (§4.4) cuando el proxy puede medirlos, y el informe de auditoría muestra p50/p95/p99 y la cobertura de estos datos.

## 10. Tareas sugeridas para Claude Code

1. Implementar el esquema como JSON Schema en `schemas/evento.schema.json`.
2. Implementar el módulo de instrumentación (`start_trace`, `record_event`, `end_trace`) con escritura JSONL.
3. Implementar el validador de integridad (sección 4.3) como CLI: `validar-traza <fichero.jsonl>`.
4. Implementar el filtro de redacción (sección 6) con pruebas unitarias.
5. Escribir pruebas con la traza de ejemplo de la sección 8 y con casos de fallo (huecos en `seq`, `parent_event_id` inexistente, `output_emitted` sin `model_called`).
6. Añadir un ejemplo de integración en un flujo real del repositorio.

## 11. Preguntas abiertas

**Decisiones tomadas:**

- Almacenamiento: ficheros locales en la primera versión, sin plataforma de observabilidad externa.
- Acceso: solo el rol administrador puede leer trazas y contenido referenciado.

**Pendientes:**

- ¿Hace falta cifrado en reposo para `logs/contenido/`? Depende de la clasificación de los datos que se procesen.
- ¿Se alinearán los nombres de campos con alguna convención estándar de telemetría? Conviene verificar el estado actual antes de decidirlo.

---

## Instrucciones para Claude Code

Añadir a `CLAUDE.md`:

```markdown
## Trazabilidad
- La especificación vive en `docs/trazabilidad.md`. Léela antes de tocar cualquier flujo con modelos, herramientas o agentes.
- Toda ejecución nueva debe instrumentarse con el módulo de trazabilidad; no registrar eventos a mano.
- Nunca escribir secretos ni datos personales en el payload de una traza.
- Los registros son de solo adición: no editar ni borrar líneas de ficheros de traza.
```
