---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.12.1

**Fecha:** 2026-11-09 · **Anterior:** v0.12.0

Release **patch**. Corrige el proxy que dejaba de conectar con `server closed connection` tras un rato sin actividad. Es el único cambio de comportamiento; el resto son la versión y la documentación.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

**Reinicia `claude-proxy`.** Hasta que no se reinicia, el proxy en marcha sigue con el código anterior.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🐛 Correcciones

### 🔌 Conexión del proxy tras inactividad (#228, #229)

mitmproxy 12 abre por defecto la conexión con Anthropic (`connection_strategy=eager`) en cuanto Claude Code hace CONNECT, y la deja esperando la primera petición. Si pasa un rato sin actividad, el servidor cierra esa conexión; la `POST /v1/messages` siguiente se encontraba un socket muerto y fallaba con `server closed connection`. Desde el 9/11 a las 14:01 todas las llamadas fallaban así.

Ahora el lanzador pasa `--set connection_strategy=lazy`: mitmproxy abre la conexión upstream con la propia petición.

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| Test que fija `connection_strategy=lazy` en el comando de mitmdump | Añadido (`tests/test_fase1_launcher.py`) |
| Compilación de los ficheros tocados | ✅ |
| `pytest` completo | ⏳ pendiente de ejecución por el responsable del release |
| Prueba real: `/v1/messages` tras más de 30 s de inactividad devuelve 200 | ⏳ pendiente tras reiniciar `claude-proxy` |

## 🔗 Enlaces

- Issue de la release: #230
- Fix: #228 / PR #229
- Anterior: [RELEASE_v0.12.0_NOTES.md](./RELEASE_v0.12.0_NOTES.md)
