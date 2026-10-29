# 📋 Guía de uso — Klaus Proxy Local

> Uso diario: qué se protege, dónde queda la evidencia y cómo comprobarlo. Para instalar y arrancar, ve al [inicio rápido](./QUICK_START.md). Para el detalle técnico y todas las variables, al [runbook](./anthropic-audit-proxy.md).

**Versión:** v0.6.0

---

## 🔐 Qué se protege

Cada petición de Claude Code a `api.anthropic.com` pasa por estos pasos antes de salir:

| Qué | Cómo | Ejemplo |
| --- | --- | --- |
| **Secretos reconocibles** (claves privadas, claves de AWS y Google, tokens de GitHub y Slack, JWT; `password=…` solo con `ANTHROPIC_PSEUDO_SECRET_KV=1`) | Se **redactan** de forma irreversible | `ghp_…` → `«REDACTED:github-token»` |
| **Rutas** del repo y del home | Seudónimo de ruta | `~/proyectos/mi-repo` → `/proj_1a2b3c4d` |
| **Usuario** de cualquier `/Users/<u>` o `/home/<u>` | Seudónimo | `ana` → `user_5e6f7a8b` |
| **Carpetas de proyectos**, también fuera de una ruta | Seudónimo | `cliente-x` → `dir_9c0d1e2f` |
| **Org/repo** de los remotes de git | Seudónimo con frontera de palabra | `acme/mi-repo` → `org_…/org_…` |
| **Emails e IPv4** | Seudónimo | `email_d8da9a55` → `email_…` |
| **Tus valores** (`pseudo_literals`, `pseudo_word_literals`, `pseudo_patterns`) | Seudónimo | un cliente, un código de proyecto… |

En la respuesta, los seudónimos se **restauran** a los valores reales, así que Claude Code lee y escribe tus rutas de verdad. Los secretos redactados no se restauran.

El org/repo se registra al arrancar `claude-proxy` dentro de un repo y, en los modos de permisos `auto` y `plan`, también desde cada petición. Las reglas completas están en el [runbook](./anthropic-audit-proxy.md).

---

## ➕ Proteger un valor concreto

Para algo que el proxy no reconoce solo (el nombre de un cliente, un código interno), añádelo a `~/.klaus-proxy/config.json`:

```json
{
  "pseudo_word_literals": ["cliente-x", "PRJ-2041"],
  "pseudo_literals": ["Cliente Uno S.A."]
}
```

- `pseudo_word_literals`: solo casan como palabra completa; para tokens cortos.
- `pseudo_literals`: casan en cualquier parte del texto; para valores largos o con espacios.

Después, **reinicia `claude-proxy`**. También puedes usar `python3 scripts/add_to_vault.py <carpeta>`, que busca secretos en una carpeta y los añade a estas listas ([guía](./ADD_TO_VAULT_AUTOMATIC.md)).

> ⚠️ Añadir un valor **solo al vault** no lo protege: el vault guarda el seudónimo de lo que ya casa con una regla.

---

## 📍 Dónde queda la evidencia

```
~/.klaus-proxy/captures/
├── original/<fecha>_anthropic_payload.json   ← la petición con tus datos reales
├── sent/<fecha>_anthropic_payload.json       ← lo que salió de tu máquina
└── .pseudonym_vault.json                     ← tabla real → seudónimo
```

- Cada petición genera un par `original` + `sent` con el mismo nombre.
- **El vault guarda los valores reales en claro** (`{"valor real": "seudónimo"}`), con permisos `0600`. No lo compartas.
- Los seudónimos se calculan con la SALT de `config.json`: sin ella no se pueden deducir los valores, pero el vault sí los contiene.
- Nada de esto se versiona ni se sincroniza. Para borrar la evidencia: `rm -rf ~/.klaus-proxy/captures/original ~/.klaus-proxy/captures/sent`.

---

## 🔍 Comprobar qué ha salido

| Herramienta | Para qué |
| --- | --- |
| `python3 src/anthropic_pair_verify.py` | Compara cada `original` con su `sent` y marca cualquier valor real que haya salido. Es la comprobación de referencia. |
| `klaus-audit-dashboard --open` | Dashboard HTML con 5 planes (seguridad, pseudonimización, actividad, tests, EFDEF) e histórico ([guía](./reports/web/README.md)). |
| `klaus-audit-payloads` | Estadísticas de pseudonimización por payload ([guía](./AUDIT_ALL_PAYLOADS.md)). |
| `klaus-fix-pseudonymization --show-payloads` | Lista las peticiones que no se pseudonimizaron ([guía](./FIX_PSEUDONYMIZATION.md)). |
| `python3 scripts/inspect_vault.py --stats` | Qué hay en el vault ([guía](./INSPECT_ANONYMIZATIONS.md)). |

Los scripts con `python3 …` se ejecutan desde el clon del repositorio.

---

## 🔎 Buscar secretos en un proyecto

`klaus-scan` revisa **una carpeta de tu disco** (no el tráfico) en busca de claves, credenciales y datos sensibles:

```bash
klaus-scan ~/proyectos/mi-repo --min-confidence HIGH
klaus-scan ~/proyectos/mi-repo --approve-all   # añade los CRITICAL a las reglas del proxy
```

Los valores aprobados se añaden al vault y a `config.json`; reinicia `claude-proxy` para que se apliquen.

---

## ⚙️ Configuración

`~/.klaus-proxy/config.json` lo crea `install.sh`. Las claves que usa el proxy:

| Clave | Para qué |
| --- | --- |
| `salt` | SALT de los seudónimos. No la cambies: los seudónimos dejarían de coincidir con el vault |
| `hosts` | Hosts de la API que se descifran y pseudonimizan (por defecto `api.anthropic.com`). Un gateway LLM propio tiene que estar aquí o en `ANTHROPIC_BASE_URL` |
| `intercept_all` | `true` para descifrar todo el HTTPS, no solo la API (por defecto `false`) |
| `pseudo_literals`, `pseudo_word_literals` | Valores a proteger (ver arriba) |
| `pseudo_patterns` | Expresiones regulares; `claude-proxy` añade una para tu carpeta de proyectos |
| `pseudo_pattern_ignore` | Valores que los patrones no deben tocar |
| `audit_injection_reviewed` | Avisos de prompt injection marcados como revisados en el dashboard |

Las variables de entorno (`ANTHROPIC_PSEUDO_*`, `ANTHROPIC_CAPTURE_*`, `KLAUS_INTERCEPT_ALL`, `KLAUS_LOG_DIR`) están en el [runbook](./anthropic-audit-proxy.md#configuración-por-entorno). Se aplican al proceso de `claude-proxy`, así que hay que exportarlas antes de arrancarlo.

---

## ❓ Preguntas frecuentes

**¿Puedo desactivar la pseudonimización un momento?** Arrancando `claude-proxy` con `ANTHROPIC_PSEUDO_ENABLE=0`: las peticiones **salen sin pseudonimizar** (se siguen capturando). No lo hagas sin necesidad; para usar Claude Code sin proxy basta otra terminal sin `HTTPS_PROXY` (con `klaus-setup`, `klaus-off` en esa terminal).

**¿Puedo cambiar el puerto?** No: el proxy escucha siempre en `127.0.0.1:8899`.

**¿Qué clientes funcionan?** Claude Code (CLI), que es con el que se prueba. Cualquier cliente que respete `HTTPS_PROXY` y confíe en la CA del proxy pasaría por él, pero no está probado.

**¿Y el resto de herramientas de la terminal?** Con `klaus-setup`, todo el HTTPS de la terminal (pip, git, brew, gh…) pasa por el proxy. Solo se descifran los hosts de la API; el resto va en túnel con su certificado real, así que no hay errores de certificado. Cada conexión queda en `proxy.log` como `TÚNEL host:puerto` (host y hora, no contenido). Para verlas:

```bash
grep TÚNEL ~/.klaus-proxy/logs/proxy.log | tail
```

**¿Funciona en Windows?** No está soportado: el instalador y el arranque son para macOS y Linux.

**¿Qué hago si algo falla?** Mira el [troubleshooting](./TROUBLESHOOTING.md) y el log, en `~/.klaus-proxy/logs/proxy.log`.

---

## 🔗 Ayuda

- Issues: https://github.com/Ka0s-Klaus/klaus-proxy-local/issues
- Seguridad: [SECURITY.md](../SECURITY.md)
