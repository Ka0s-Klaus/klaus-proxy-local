---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.11.0

**Fecha:** 2026-11-09 · **Anterior:** v0.10.0

Release **minor**: introduce `klaus-trazas`, el lector de trazas de ejecuciones con IA según la especificación [trazabilidad.md](./trazabilidad.md), y la instrumentación para generarlas. Incluye además tres correcciones de arranque e instalación y la revisión de la documentación.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
klaus-trazas --help          # comprueba que el comando está en el PATH
```

Reinicia `claude-proxy` para cargar el código nuevo del proxy. `config.json`, la SALT, el vault y las capturas se conservan.

## ✨ Novedades

### 🧾 `klaus-trazas`: estadísticas e integridad de trazas (#206, #207)

Lee `logs/trazas/AAAA-MM-DD/*.jsonl` (solo lectura) y muestra:

- Trazas válidas e incidencias de integridad (reglas de §4.3 de la especificación).
- Eventos por tipo, llamadas al modelo con versión devuelta distinta de la pedida.
- Verificaciones `pass` / `warn` / `fail`, revisiones humanas y errores.
- Salidas emitidas sin revisión humana previa.

Opciones: `--dir`, `--date AAAA-MM-DD`, `--json`, `--strict`. Nunca imprime valores de `payload`.

### 🧩 Instrumentación de trazas (#210, #211)

- `start_trace`, `record_event` y `end_trace` en `Klaus_proxy_local.trazas`.
- Escritura JSONL solo en adición. Directorio `0700`, ficheros `0600`.
- Un fallo de escritura no interrumpe la ejecución: se registra en el log.
- Filtro de redacción: correos, DNI/NIE, tarjetas validadas con Luhn y secretos con patrones conocidos. Si el filtro falla, se escribe un evento `error` y no el contenido original.
- Esquema JSON en [`schemas/evento.schema.json`](../schemas/evento.schema.json).
- Ejemplo sin modelos en `scripts/ejemplo_trazas.py`.

**Alcance:** el proxy todavía no escribe trazas. La instrumentación está lista para usarse desde un flujo con modelos; la integración en el proxy queda para otra versión.

## 🐛 Correcciones

- **`claude-proxy` libera el puerto 8899** (#202, #203). Si un `mitmdump` previo ocupa el puerto, lo detiene y relanza el proxy, mostrando cada paso. Si lo ocupa otro programa, aborta sin tocarlo.
- **Enlaces de comandos en `install.sh`** (#208, #209). `klaus-trazas`, `klaus-alerts`, `klaus-startup-scan`, `klaus-install-python` y `klaus-install-wrappers` no quedaban enlazados en `~/.local/bin`.

## 📚 Documentación

- Revisión completa de la documentación frente al código (#204, #205): comandos, rutas, enlaces y utilidades de instalación.

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| `pytest` (Python 3.13, venv temporal) | 929 passed, 3 skipped |
| `ruff check .` | ✅ |
| `black --check .` | ✅ |
| CI de la PR de preparación | Pendiente de comprobar antes del merge |

## ⚠️ Notas

- La suite registra 3 tests saltados (`skipped`); no son fallos.
