# 📋 Guía de uso — Klaus Proxy Local

> Uso diario: qué se protege, dónde queda la evidencia y cómo comprobarlo. Para instalar y arrancar, ve al [inicio rápido](./QUICK_START.md). Para el detalle técnico y todas las variables, al [runbook](./anthropic-audit-proxy.md).

**Versión:** v0.7.0

---

## 🔐 Qué se protege

Cada petición de Claude Code a `api.anthropic.com` pasa por estos pasos antes de salir:

| Qué | Cómo | Ejemplo |
| --- | --- | --- |
| **Secretos reconocibles** (claves privadas; claves de AWS, Google, Anthropic, OpenAI y Stripe; tokens de GitHub, Slack y Bearer; JWT; `refresh_token` y `aws_session_token`; la contraseña de una cadena de conexión o URL; `password=…` solo con `ANTHROPIC_PSEUDO_SECRET_KV=1`) | Se **redactan** de forma irreversible. En una conexión o URL solo la contraseña: `postgres://app:«REDACTED:url-password»@db/ventas` | `ghp_…` → `«REDACTED:github-token»` |
| **Rutas** del repo y del home | Seudónimo de ruta | `~/proyectos/mi-repo` → `/proj_1a2b3c4d` |
| **Usuario** de cualquier `/Users/<u>` o `/home/<u>` | Seudónimo | `ana` → `user_5e6f7a8b` |
| **Carpetas de proyectos**, también fuera de una ruta | Seudónimo | `cliente-x` → `dir_9c0d1e2f` |
| **Org/repo** de los remotes de git | Seudónimo con frontera de palabra | `acme/mi-repo` → `org_…/org_…` |
| **Emails e IPv4** | Seudónimo | `email_d8da9a55` → `email_…` |
| **Tus valores** (`pseudo_literals`, `pseudo_word_literals`, `pseudo_patterns`) | Seudónimo | un cliente, un código de proyecto… |

**Tu login no se toca:** el proxy solo reescribe el cuerpo de la petición. Las cabeceras `Authorization` y `x-api-key` salen intactas, y los cuerpos de los endpoints de autenticación (`/v1/oauth/…`, `/api/oauth/token`, `/api/oauth/claude_cli/…`, `/api/auth/…`), que llevan credenciales que Anthropic tiene que recibir, pasan sin tocar (#148).

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
- Las de `capture_only_hosts` llevan `"capture_only": true`: salieron **sin pseudonimizar** (los dos lados tienen los datos reales y los secretos redactados) y las herramientas de verificación no las cuentan como fugas.
- **El vault guarda los valores reales en claro** (`{"valor real": "seudónimo"}`), con permisos `0600`. No lo compartas.
- Los seudónimos se calculan con la SALT de `config.json`: sin ella no se pueden deducir los valores, pero el vault sí los contiene.
- **Retención: 30 días por defecto** (#132). Al arrancar `claude-proxy` se borran los pares `original` + `sent` más antiguos que `capture_retention_days` de `config.json` (`0` = sin límite). No se tocan el vault ni `captures/archive/`: lo que quieras conservar, muévelo allí. Para ver qué se borraría sin borrar: `klaus-prune-captures --dry-run`. El dashboard de auditoría muestra la retención activa, la captura más antigua y el último borrado.
- **Sin originales:** con `capture_originals: false` solo se guarda `sent/`. Así no quedan datos reales en claro en disco (salvo el vault) y ocupa la mitad, pero **no se puede verificar por pares** (`anthropic_pair_verify.py`).
- Nada de esto se versiona ni se sincroniza. Para borrar toda la evidencia: `rm -rf ~/.klaus-proxy/captures/original ~/.klaus-proxy/captures/sent`.

---

## 🔍 Comprobar qué ha salido

| Herramienta | Para qué |
| --- | --- |
| `python3 src/anthropic_pair_verify.py` | Compara cada `original` con su `sent` y marca cualquier valor real que haya salido. Es la comprobación de referencia. |
| `klaus-audit-dashboard --open` | Dashboard HTML con 5 planes (seguridad, pseudonimización, actividad, tests, EFDEF) e histórico ([guía](./reports/web/README.md)). |
| `klaus-audit-payloads` | Estadísticas de pseudonimización por payload ([guía](./AUDIT_ALL_PAYLOADS.md)). |
| `klaus-fix-pseudonymization --show-payloads` | Lista las peticiones que no se pseudonimizaron ([guía](./FIX_PSEUDONYMIZATION.md)). |
| `python3 scripts/inspect_vault.py --stats` | Qué hay en el vault ([guía](./INSPECT_ANONYMIZATIONS.md)). |
| `klaus-leak-report [--open] [--reveal]` | Informe de fugas por proyecto: qué datos sensibles tiene cada repo, cuáles no cubre el proxy, qué ha salido en las capturas y el % de cobertura ([ver abajo](#-informe-de-fugas-por-proyecto)). |
| `klaus-scan-repos [--dry-run]` | Protege el org/repo de todos los repos de la carpeta de proyectos; úsalo tras clonar uno y reinicia `claude-proxy`. Solo muestra recuentos. |
| `klaus-prune-captures [--dry-run] [--days N]` | Aplica la retención de capturas sin reiniciar el proxy; `--dry-run` muestra qué se borraría. |

Los scripts con `python3 …` se ejecutan desde el clon del repositorio.

---

## 🔎 Buscar secretos y nombres de negocio en un proyecto

`klaus-scan` revisa **una carpeta de tu disco**, no el tráfico. Busca claves, credenciales y **nombres de negocio**: los valores que el proxy solo pseudonimiza si tienen una regla (#140).

```bash
klaus-scan ~/proyectos/mi-repo                       # umbral HIGH por defecto
klaus-scan ~/proyectos/mi-repo --min-confidence MEDIUM
klaus-scan ~/proyectos/mi-repo --counts              # solo recuentos por categoría
klaus-scan ~/proyectos/mi-repo --approve-all         # añade lo detectado a las reglas del proxy
```

**Nombres de negocio que detecta** (`--no-business` para desactivarlo):

| Categoría | Qué busca | Confianza |
| --- | --- | --- |
| `business-name` | Razón social con forma jurídica (`Cliente X S.L.`, `… GmbH`, `… Inc.`) y titular de copyright | HIGH |
| `corporate-domain` | Dominios de email no públicos, también los de los autores en `git log` | HIGH |
| `corporate-domain` | Dominios de URL no públicos y el *tenant* de un SaaS (`cliente-x.atlassian.net`) | MEDIUM |
| `cloud-project` | ID de proyecto GCP, cuenta AWS, suscripción Azure | HIGH |
| `package-name` | Scope de npm, vendor de composer, `groupId` de Maven, módulo Go y autores de los manifiestos | MEDIUM |
| `issue-key` | Clave de proyecto de los IDs de incidencia (`PRJ-123`), a partir de 3 apariciones | LOW |

Cada valor se lista **una vez**, con sus apariciones y la primera ubicación. Lo que ya está en `pseudo_word_literals` o `pseudo_literals` no se lista: solo se cuenta. Los dominios públicos (GitHub, PyPI, Gmail…) y los marcadores de posición (`example.*`, `your-project`) se ignoran.

**La salida no revela los valores.** Cada hallazgo se muestra como `⟨categoría·a1b2c3d4·13c⟩`: un hash con tu SALT más la longitud. El mismo valor da siempre el mismo identificador, así que puedes cruzar hallazgos sin ver ningún carácter. No se muestra contexto, las rutas son relativas a la carpeta escaneada y se enmascara cualquier carpeta que comparta una palabra con un valor detectado. `--json` sigue las mismas reglas. Así puedes pedirle a Claude Code que lo ejecute.

- **`--reveal`** muestra valores y contexto en claro. Úsalo solo en tu terminal: lo que se imprime en una sesión de Claude Code llega al modelo.
- **Sin terminal interactiva** (por ejemplo, lanzado por Claude Code) no se pregunta nada: termina con el resumen. Para aprobar, usa `--approve-all` o lánzalo tú.

Los valores aprobados se añaden al vault y a `config.json`: a `pseudo_word_literals` si son un único token y a `pseudo_literals` si no. Reinicia `claude-proxy` para que se apliquen.

---

## 🕵️ Informe de fugas por proyecto

`klaus-leak-report` revisa cada repo git de la carpeta de proyectos (`projects_dirs`) y responde a cuatro preguntas (#146):

| Pregunta | Cómo lo calcula |
| --- | --- |
| **¿Qué datos sensibles tiene?** | Lo que detecta `klaus-scan`: secretos y nombres de negocio |
| **¿Puede sufrir una fuga?** | Pasa cada valor por el pseudonimizador con tus reglas actuales. Si sale igual, ninguna regla lo cubre |
| **¿La ha sufrido?** | Asigna cada captura a su proyecto según el directorio de trabajo que envía Claude Code (o los remotes de git) y busca valores reales en `sent/`, como el verificador por pares. Indica la fecha y el fichero de cada captura con fugas |
| **Cobertura** | % de valores CRITICAL y HIGH que el proxy sustituye o redacta. 🟢 ≥ 95 % · 🟡 ≥ 80 % · 🔴 menos, o alguna fuga en los últimos 30 días |

```bash
klaus-leak-report --open      # genera informes/fugas/leak-report.html y lo abre
klaus-leak-report --no-cache  # recalcula todo
```

- **Caché:** la primera ejecución analiza todas las capturas y tarda varios minutos. Después solo analiza lo nuevo. Un repo se vuelve a revisar si cambian su commit o sus ficheros, y todo se recalcula si cambian tus reglas. La caché está en `~/.klaus-proxy/leak-report-cache.json` y solo guarda identificadores.
- **Valores:** se muestran como `⟨categoría·hash·longitud⟩`, igual que en `klaus-scan`. `--reveal` los muestra en claro; úsalo solo en tu terminal.
- **Nombres de proyecto:** el informe muestra los nombres de tus proyectos. Es local (`informes/` no se versiona); no lo compartas tal cual.
- **Dashboard de auditoría:** la tarjeta «🕵️ Fugas por proyecto» resume el último informe y enlaza a él.
- **Para cubrir un valor:** `klaus-scan <proyecto> --reveal` en tu terminal, apruébalo y reinicia `claude-proxy`.

---

## ⚙️ Configuración

`~/.klaus-proxy/config.json` lo crea `install.sh`. Las claves que usa el proxy:

| Clave | Para qué |
| --- | --- |
| `salt` | SALT de los seudónimos. No la cambies: los seudónimos dejarían de coincidir con el vault |
| `hosts` | Hosts de la API que se descifran y pseudonimizan (por defecto `api.anthropic.com`). Un gateway LLM propio tiene que estar aquí o en `ANTHROPIC_BASE_URL` |
| `capture_only_hosts` | Hosts que se **auditan sin pseudonimizar**: se descifran y se capturan, pero la petición sale tal cual. Para tráfico que dejaría de funcionar con seudónimos, como los conectores MCP de claude.ai (`mcp-proxy.anthropic.com`). Sus capturas llevan `"capture_only": true` y no cuentan como fugas |
| `intercept_all` | `true` para descifrar todo el HTTPS, no solo la API (por defecto `false`) |
| `pseudo_literals`, `pseudo_word_literals` | Valores a proteger (ver arriba) |
| `pseudo_patterns` | Expresiones regulares; `claude-proxy` añade una para tu carpeta de proyectos |
| `projects_dirs` | Carpetas cuyos repos git protege `claude-proxy` al arrancar (hasta 3 niveles). Por defecto, la carpeta padre del repo desde el que arrancas |
| `pseudo_pattern_ignore` | Valores que los patrones no deben tocar |
| `capture_retention_days` | Días que se conservan las capturas; se borran las más antiguas al arrancar `claude-proxy` (por defecto `30`; `0` = sin límite) |
| `capture_originals` | `false` para no guardar `original/`: sin datos reales en claro, pero sin verificación por pares (por defecto `true`) |
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
