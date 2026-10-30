# Klaus Proxy Local — Tu control de privacidad

## ¿Trabajas con Claude Code en entornos corporativos o sensibles?

Klaus Proxy Local es la herramienta que te falta. Mientras usas Claude Code (o cualquier cliente de la API de Anthropic), este proxy se interpone en el camino y **te da control total** sobre qué datos salen de tu máquina.

### El problema

Cada vez que envías una pregunta a Claude, el contenido completo de tu request viaja hacia `api.anthropic.com`. Eso incluye:
- Rutas de archivos del proyecto (`~/proyectos/cliente-secreto/...`)
- Identificadores sensibles (emails corporativos, git user, org interna)
- Fragmentos de código con credenciales olvidadas
- Contexto del directorio (`pwd`, structure trees)

En entornos corporativos, compliance o con datos sensibles, eso es un **incumplimiento** de política.

### La solución: Klaus Proxy Local

Klaus Proxy Local corre **localmente en tu máquina** (puerto 8899) y hace tres cosas críticas:

1. **Captura**. Registra exactamente qué sale de tu equipo (para auditoría)
2. **Pseudonimiza en vuelo**. Antes de que viaje, reemplaza datos sensibles por seudónimos reversibles y redacta los secretos reconocibles:
   - `ana@empresa.example` → `email_16b8b260`
   - `~/proyectos/cliente-secreto` → `~/proyectos/dir_0f284a1e`
   - `ghp_…` (token de GitHub) → `«REDACTED:github-token»` (irreversible)
3. **Revierte en respuesta**. Cuando Claude responde, los seudónimos se convierten de vuelta a valores reales, así tus tool calls y el contexto siguen siendo operativos.

Todo funciona con **fail-closed**: si el pseudonimizador no ha procesado una petición, o no ha podido reescribirla, la petición **no sale** del equipo.

### Características clave

- ✅ **Determinista**: el mismo email siempre → el mismo seudónimo (gracias a SALT y hashing)
- ✅ **Reversible**: bidireccional real ↔ pseudónimo (vault persistente)
- ✅ **Transparent**: Claude sigue viéndose igual; los tool calls funcionan sin cambios
- ✅ **Detección de secretos en tu disco**: `klaus-scan` busca credenciales en un proyecto por patrones, contexto y entropía, y las añade a las reglas del proxy
- ✅ **Auditable**: evidencia de captura original vs. enviada
- ✅ **Sin errores de certificado en el resto de herramientas**: solo se descifra el tráfico de la API; pip, git o brew pasan en túnel con su certificado real y quedan registrados
- ✅ **Sin configuración inicial**: `install.sh` genera certificados, SALT y configuración; al arrancar dentro de un repo protege su org/repo y la carpeta de proyectos
- ✅ **Probado**: 746 tests en CI (Python 3.10–3.13), verificador de fugas por pares y audit dashboard

### Casos de uso

- **Equipos corporativos** que necesitan compliance sobre qué datos salen (GDPR, CCPA, normas internas)
- **Consultorías** trabajando con código de clientes multiples
- **Equipos sensibles** (finanzas, salud, legal) donde no puedes dejar rastro en APIs externas
- **Desarrolladores** que quieren auditarse a sí mismos antes de usar Claude a mayor escala
- **Investigadores** de privacidad / seguridad

### Comienza en 3 minutos

```bash
# 1. Instala (desde el repositorio; no está en PyPI)
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local && ./install.sh

# 2. Arranca el proxy (Terminal 1)
claude-proxy

# 3. Usa Claude a través del proxy (Terminal 2)
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude "tu pregunta aquí"

# 4. Audita lo que ha salido
klaus-audit-dashboard --open
```

Atajos: `claude-with-proxy` hace el `source` y el `export` por ti; `klaus-setup` hace que cada terminal nueva arranque el proxy y exporte `HTTPS_PROXY`. Solo se descifra el tráfico de la API: el resto del HTTPS va en túnel, registrado y sin errores de certificado.

¿Listo para auditar todo lo que envía tu equipo?
