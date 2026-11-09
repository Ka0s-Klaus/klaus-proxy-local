---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.12.2

**Fecha:** 2026-11-09 · **Anterior:** v0.12.1

Release **patch**. Corrige las trazas del proxy: `POST /v1/messages/count_tokens` se registraba como llamada al modelo. Es el único cambio de comportamiento; el resto son la versión y la documentación.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

**Reinicia `claude-proxy`.** Hasta que no se reinicia, el proxy en marcha sigue con el código anterior.

`config.json`, la SALT, el vault y las capturas se conservan. Las trazas ya escritas tampoco se modifican (son de solo adición).

## 🐛 Correcciones

### 🧾 Trazas: solo llamadas de inferencia (#234, #235)

El addon de trazas comparaba el path por prefijo (`/v1/messages`), así que también registraba `POST /v1/messages/count_tokens`. Esa ruta cuenta tokens y no es una llamada de inferencia: su respuesta es `{"input_tokens": N}`, sin `model` ni `usage`. Cada una aparecía como `returned_model: no_devuelto`, sin tokens de salida.

Ahora solo se traza `POST /v1/messages` exacto, con o sin query string (`?beta=true`). `count_tokens` y `batches` no generan traza. Las 33 trazas de ese tipo escritas antes de la corrección se conservan, porque el registro es de solo adición; las métricas de rendimiento (#232) las incluyen en el histórico.

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| Tests de `is_messages_call` y del hook con `count_tokens` y `?beta=true` | Añadidos (`tests/test_klaus_trazas_addon.py`) |
| CI de la PR #235 (lint, tests 3.10–3.13, seguridad) | ✅ |
| Compilación de los ficheros tocados | ✅ |
| Prueba real: tras reiniciar, `count_tokens` no genera trazas nuevas | ⏳ pendiente tras reiniciar `claude-proxy` |

## 🔗 Enlaces

- Issue de la release: #236
- Fix: #234 / PR #235
- Métricas de rendimiento: #232 / PR #233
- Anterior: [RELEASE_v0.12.1_NOTES.md](./RELEASE_v0.12.1_NOTES.md)
