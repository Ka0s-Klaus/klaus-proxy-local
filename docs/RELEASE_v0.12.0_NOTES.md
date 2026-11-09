---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.12.0

**Fecha:** 2026-11-09 · **Anterior:** v0.11.0

Release **minor**. El proxy ya registra una traza por cada llamada al API, y `klaus-trazas` pasa de contadores a un informe que se puede revisar. Incluye además una corrección de las respuestas comprimidas y otra de la suite de tests.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

**Reinicia `claude-proxy`.** Hasta que no se reinicia, el proxy en marcha sigue con el código anterior. Las trazas empiezan a escribirse en el arranque siguiente.

`config.json`, la SALT, el vault y las capturas se conservan.

## ✨ Novedades

### 🧾 Trazas de cada llamada al API (#214, #215)

Cada `POST /v1/messages` que pasa por el proxy genera una traza en `~/.klaus-proxy/logs/trazas/AAAA-MM-DD/`, según la [especificación de trazabilidad](./trazabilidad.md):

- Hash del último mensaje de usuario. **Nunca el texto.**
- Modelo pedido y modelo devuelto por la API, tokens y hash de la respuesta.
- Si la API falla o el guardián bloquea la petición, un evento `error`.

El proxy no hace verificaciones ni revisión humana, así que `klaus-trazas` marca todas las salidas como «sin revisión humana previa».

### 🔍 `klaus-trazas`: detalle e informe (#220, #221)

- `klaus-trazas`: estadísticas y tabla de las últimas 10 trazas (`--ultimas N`).
- `klaus-trazas --traza ID`: línea de tiempo de una traza. Acepta un prefijo único del id.
- `klaus-trazas --informe [RUTA]`: informe Markdown con resumen, sección **Para revisar**, tabla de trazas y detalle. Permisos `0600`. Por defecto va a `~/.klaus-proxy/logs/informes/`.

Ningún informe contiene texto de conversación.

## 🐛 Correcciones

- **Respuestas comprimidas** (#216, #217). Claude Code pide gzip y el addon leía los bytes comprimidos. El modelo devuelto y los tokens se perdían. Un modelo no devuelto ya no cuenta como cambio de versión (`Versión no devuelta por la API`).
- **Turnos `tool_result`** (#220, #221). Las entradas de este tipo tenían el mismo hash, el de la cadena vacía. Ahora cada una tiene el suyo.
- **La suite detenía el proxy real** (#218, #219). Un test llamaba a `run()` sin aislar el puerto 8899. `conftest.py` lo aísla para toda la suite.

## 📚 Documentación

- Guía de usuario, solución de problemas, arquitectura y runbook: trazas, informe, reemplazo del proxy al arrancar otro, y cadena de addons (#222, #223).

## ⚠️ Antes de actualizar

- **Las trazas anteriores a #216** tienen modelo `no_devuelto`. Son de solo adición y no se reescriben.
- **Arrancar `claude-proxy` en otra terminal detiene el proxy que ya está en marcha.** Es el comportamiento esperado: el nuevo lanzador sustituye al anterior. Para comprobar qué está activo: `lsof -nP -t -iTCP:8899 -sTCP:LISTEN`.

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| `pytest` (Python 3.13, venv temporal) | 956 passed, 3 skipped |
| `ruff check .` | ✅ |
| `black --check .` | ✅ |
| Prueba real con `claude` a través del proxy | ✅ trazas válidas, sin texto del usuario en los ficheros |
