# Klaus Proxy Local — Tu control de privacidad

## ¿Trabajas con Claude Code en entornos corporativos o sensibles?

Klaus Proxy Local es la herramienta que te falta. Mientras usas Claude Code (o cualquier cliente de la API de Anthropic), este proxy se interpone en el camino y **te da control total** sobre qué datos salen de tu máquina.

### El problema

Cada vez que envías una pregunta a Claude, el contenido completo de tu request viaja hacia `api.anthropic.com`. Eso incluye:
- Rutas de archivos del proyecto (`/Users/empresa/proyectos/cliente-secreto/...`)
- Identificadores sensibles (emails corporativos, git user, org interna)
- Fragmentos de código con credenciales olvidadas
- Contexto del directorio (`pwd`, structure trees)

En entornos corporativos, compliance o con datos sensibles, eso es un **incumplimiento** de política.

### La solución: Klaus Proxy Local

Klaus Proxy Local corre **localmente en tu máquina** (puerto 8899) y hace tres cosas críticas:

1. **Captura**. Registra exactamente qué sale de tu equipo (para auditoría)
2. **Pseudonimiza en vuelo**. Antes de que viaje, reemplaza datos sensibles por seudónimos reversibles:
   - `asantacana@kyndryl.com` → `email_16b8b260`
   - `/Users/asantacana/proyectos/` → `_u_0f284a1e`
   - `https://github.com/...?token=ghp_xyz` → `url_9c2f5a7d`
3. **Revierte en respuesta**. Cuando Claude responde, los seudónimos se convierten de vuelta a valores reales, así tus tool calls y el contexto siguen siendo operativos.

Todo funciona con **fail-closed**: si algo falla, la request **no sale** del equipo.

### Características clave

- ✅ **Determinista**: el mismo email siempre → el mismo seudónimo (gracias a SALT y hashing)
- ✅ **Reversible**: bidireccional real ↔ pseudónimo (vault persistente)
- ✅ **Transparent**: Claude sigue viéndose igual; los tool calls funcionan sin cambios
- ✅ **Multi-tier detection**: 3 niveles de detección de datos sensibles (patrones, contexto, heurística)
- ✅ **Auditable**: evidencia de captura original vs. enviada
- ✅ **Zero-config**: genera certificados, SALT y configuración automáticamente en primer arranque
- ✅ **Production-ready**: 465 tests pasando, auditoría completa, CI/CD limpio

### Casos de uso

- **Equipos corporativos** que necesitan compliance sobre qué datos salen (GDPR, CCPA, normas internas)
- **Consultorías** trabajando con código de clientes multiples
- **Equipos sensibles** (finanzas, salud, legal) donde no puedes dejar rastro en APIs externas
- **Desarrolladores** que quieren auditarse a sí mismos antes de usar Claude a mayor escala
- **Investigadores** de privacidad / seguridad

### Comienza en 3 minutos

```bash
# 1. Instala
pip install Klaus-proxy-local==0.3.0

# 2. Arranca el proxy (Terminal 1)
claude-proxy

# 3. Usa Claude a través del proxy (Terminal 2)
export HTTPS_PROXY=http://127.0.0.1:8899
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem
claude "tu pregunta aquí"

# 4. Audita capturas automáticamente (Terminal 3)
python full_audit_with_fixes.py --auto
```

¿Listo para auditar todo lo que envía tu equipo?
