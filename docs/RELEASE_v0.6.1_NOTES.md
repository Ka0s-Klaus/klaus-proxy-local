# Klaus Proxy Local v0.6.1

**Fecha:** 2026-10-29 · **Anterior:** v0.6.0

Release de auditoría. **El proxy solo descifra lo que audita,** y con `capture_only_hosts` se puede auditar un host sin pseudonimizarlo, como los conectores MCP de claude.ai. El dashboard muestra además qué tráfico pasó por el proxy sin pseudonimizar. Incluye tres correcciones detectadas al auditar la telemetría de Claude Code.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

1. **Reinicia `claude-proxy`** desde dentro de un repo. Al arrancar, el log muestra `🔓 Se descifra solo: …` con los hosts que se auditan.
2. **Si arrancabas con `ANTHROPIC_CAPTURE_HOSTS`, ya no hace falta.** La captura lee `hosts` de `config.json` (#119). La variable, si está exportada, tiene prioridad sobre `config.json`: `unset ANTHROPIC_CAPTURE_HOSTS`.
3. **Opcional, auditar los conectores MCP de claude.ai:** añade a `~/.klaus-proxy/config.json`

   ```json
   "capture_only_hosts": ["mcp-proxy.anthropic.com"]
   ```

   y reinicia `claude-proxy`.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🔍 Auditar sin pseudonimizar: `capture_only_hosts` (#125)

Algunos destinos no pueden recibir seudónimos sin dejar de funcionar. Los conectores MCP de claude.ai, por ejemplo, buscarían «org_1a2b…» en lugar de «cliente-x», o guardarían un documento con seudónimos. Los hosts de `capture_only_hosts`:

- **se descifran y se capturan,** pero la petición sale tal cual;
- **se guardan en disco** con los secretos Tier-1 redactados en `original/` y en `sent/`, y con `"capture_only": true`;
- **no cuentan** como fugas en `anthropic-pair-verify` ni como «no pseudonimizadas» en `klaus-audit-payloads` y `klaus-fix-pseudonymization`. El dashboard los da por esperados.

Si un host está también en `hosts`, se pseudonimiza. Una ruta de LLM (`/v1/messages`) se pseudonimiza siempre.

## 🔓 Solo se descifra lo que se audita (#125)

En v0.6.0, `klaus_tls_passthrough` descifraba todos los subdominios de `anthropic.com` y `claude.ai`. Tres de ellos salían descifrados **sin pseudonimizar ni capturar**:

| Host | Qué es | Ahora |
| --- | --- | --- |
| `mcp-proxy.anthropic.com` | Llamadas a los conectores MCP de claude.ai | Túnel, o capturado con `capture_only_hosts` |
| `downloads.claude.ai` | Comprobación de versión de Claude Code | Túnel |
| `platform.claude.com` | Renovación del token OAuth | Túnel: el proxy ya no ve el token |

Ahora se descifran `api.anthropic.com`, `hosts`, `capture_only_hosts` y el host de `ANTHROPIC_BASE_URL`, y nada más. Ningún tráfico descifrado sale sin quedar capturado.

## 📊 Dashboard (#123)

- **Sección nueva «Hosts no capturados»** en el plan de Seguridad. Lee `proxy.log` y sus rotaciones, y lista por host:
  - las conexiones **en túnel**, de las que solo se conoce el host y la hora;
  - las **descifradas que salieron sin pseudonimizar**, que desde esta versión solo aparecen en el histórico;
  - la última vez de cada modo.
- **La tabla «Hosts capturados» era incoherente.** Marcaba como «Inesperado» todo host distinto de `api.anthropic.com`, aunque estuviera en `hosts`, mientras el estado del plan lo daba por bueno. Ahora usan el mismo criterio.

## 🐛 Correcciones

- **La captura ignoraba `hosts` de `config.json`** (#119). Un gateway o un host añadido para auditarlo se pseudonimizaba, pero no dejaba pares `original/` + `sent/`. Ahora la captura usa las mismas fuentes que el pseudonimizador.
- **Un `config.json` ilegible desactivaba en silencio tus reglas** (#121). Si el JSON se rompía, el pseudonimizador descartaba `pseudo_literals`, `pseudo_word_literals` y `pseudo_patterns` sin dejar rastro. Ahora lo avisa en el log (`config.json ilegible`). Cierra las alertas de CodeQL #62 y #63.

## 🔬 Verificación

- **`capture_only_hosts` con un `mitmdump` real,** usando httpbin.org como host de solo captura:
  - el servidor recibe el cuerpo intacto;
  - la captura lleva `capture_only: true` y el token de prueba como `«REDACTED:github-token»`.
- **Túnel:** `downloads.claude.ai` y `platform.claude.com` responden sin la CA del proxy y quedan como `TÚNEL` en el log.
- **En la instalación del autor:** una llamada real al conector Claude Docs funciona y queda capturada con `capture_only: true`, con `Authorization` redactada. La telemetría de Datadog se sigue capturando y pseudonimizando.

## 🧪 Calidad

- 718 tests passed, 3 skipped (+19 desde v0.6.0). CI en Python 3.10, 3.11, 3.12 y 3.13. Sin alertas abiertas de CodeQL.

## 📝 Limitaciones conocidas

- La sección «Hosts no capturados» solo cubre el periodo que conserva `proxy.log` (5 MB × 5 ficheros rotados).
- El aprendizaje de org/repo por petición sigue funcionando solo en los modos de permisos `auto` y `plan` (#68).

**Changelog completo:** [`v0.6.0...v0.6.1`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.6.0...v0.6.1) · [CHANGELOG](../CHANGELOG.md)
