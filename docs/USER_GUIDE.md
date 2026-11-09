---
tags: [proyecto/klaus-proxy-local, tipo/guia, seguridad/fugas, proxy/centinela]
---

# 📋 Guía de uso — Klaus Proxy Local

> Uso diario: qué se protege, dónde queda la evidencia y cómo comprobarlo. Para instalar y arrancar, ve al [inicio rápido](./QUICK_START.md). Para el detalle técnico y todas las variables, al [runbook](./anthropic-audit-proxy.md).

**Versión:** v0.10.0

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
| `klaus-leak-report [--open] [--reveal] [--drill]` | Informe de fugas por proyecto: qué datos sensibles tiene cada repo, cuáles no cubre el proxy, qué ha salido en las capturas y el % de cobertura ([ver abajo](#-informe-de-fugas-por-proyecto)). |
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

Los valores aprobados se añaden al vault y a `config.json`: a `pseudo_word_literals` si son un único token y a `pseudo_literals` si no. Al terminar, el resumen dice `Approved for vault: N`.

**Reinicia `claude-proxy` después de aprobar.** El proxy lee las reglas al arrancar: hasta que lo reinicies, lo que acabas de aprobar sigue saliendo en claro. Un reinicio anterior a la aprobación no sirve.

**Orden completo:**
1. `klaus-scan ~/proyectos --reveal` en tu terminal. Responde `Y` a `Review N finding(s)?` y aprueba con `A`.
2. Reinicia `claude-proxy`.
3. `klaus-leak-report --open` para medir la cobertura con las reglas nuevas.

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
klaus-leak-report --drill     # simulacro: ¿el detector ve una fuga falsa? (#171)
```

> 🧯 **¿Te puedes fiar de un «0 fugas»?** `--drill` siembra fugas falsas en un directorio temporal y comprueba que el detector las ve y que el proxy las habría sustituido. No toca tus capturas. Ver [Simulacro de fugas](./guides/LEAK_DRILL.md).

- **Caché:** la primera ejecución analiza todas las capturas y tarda varios minutos. Después solo analiza lo nuevo. Un repo se vuelve a revisar si cambian su commit o sus ficheros. Todo se recalcula si cambian tus reglas o el código de Klaus. Las capturas se reasignan si añades o quitas un proyecto de la carpeta de proyectos: las de un proyecto quitado pasan a «sin proyecto atribuible» y sus fugas se siguen contando (#180). La caché está en `~/.klaus-proxy/leak-report-cache.json` y solo guarda identificadores.
- **Tiempos:** en la instalación del autor, la primera ejecución tardó unos 9 minutos. Tras aprobar cientos de reglas de golpe tardó 20, porque hubo que recalcularlo todo. Con la caché al día tarda unos segundos.
- **Qué cuenta para la cobertura:** solo los valores CRITICAL y HIGH. Los dominios de confianza MEDIUM, los nombres de paquete y las claves de incidencia (LOW) aparecen como sin cubrir, pero no bajan el %.
- **Valores:** se muestran como `⟨categoría·hash·longitud⟩`, igual que en `klaus-scan`. `--reveal` los muestra en claro; úsalo solo en tu terminal.
- **Nombres de proyecto:** el informe muestra los nombres de tus proyectos. Es local (`informes/` no se versiona); no lo compartas tal cual.
- **Dashboard de auditoría:** la tarjeta «🕵️ Fugas por proyecto» resume el último informe y enlaza a él.
- **Para cubrir un valor:** `klaus-scan <proyecto> --reveal` en tu terminal, apruébalo y reinicia `claude-proxy`. Lanza el informe después del reinicio, no a la vez que `klaus-scan`, o medirá sin las reglas nuevas.

### Cómo leer las fugas después de aprobar reglas

El informe busca en **todas** las capturas los valores que protegen **tus reglas actuales**. Al aprobar reglas nuevas pasan dos cosas a la vez:

- **La cobertura sube.** En la instalación del autor pasó del 64 % al 100 %, y de 12 proyectos 🔴 a 3.
- **Las capturas con fugas también suben.** En la instalación del autor pasaron de 461 a 1351. No son fugas nuevas: son peticiones **anteriores** a la regla que ya llevaban ese valor, y ahora el informe sabe que es sensible. Lo enviado no se puede deshacer, pero sí archivar como evidencia (ver [runbook](./anthropic-audit-proxy.md)).

Para saber si el proxy protege **ahora**, mira las capturas con fugas posteriores al último reinicio de `claude-proxy`. Su hora va en el nombre del fichero (`AAAAMMDD_HHMMSS_…`). La hora del reinicio está en `~/.klaus-proxy/logs/proxy.log`, en la última línea `🧩 Addons:`. Si no hay ninguna posterior, las reglas funcionan.

**Un proyecto sigue en 🔴 con cobertura del 100 %** si tiene alguna fuga en los últimos 30 días. Deja de estarlo cuando esas capturas superan los 30 días. La retención (#132) las borra a esa edad: si quieres conservar la evidencia, muévelas antes a `~/.klaus-proxy/captures/archive/`.

**Reglas de una sola palabra:** igual que el proxy, el informe solo cuenta una regla de `pseudo_word_literals` como fuga cuando aparece como palabra completa. La regla `fabri` dentro de `tailspinfabri` no se sustituye ni es fuga (#158).

---

## ⚙️ Configuración

`~/.klaus-proxy/config.json` lo crea `install.sh`. Las claves que usa el proxy:

| Clave | Para qué |
| --- | --- |
| `salt` | SALT de los seudónimos. No la cambies: los seudónimos dejarían de coincidir con el vault |
| `hosts` | Hosts de la API que se descifran y pseudonimizan (por defecto `api.anthropic.com`). Un gateway LLM propio tiene que estar aquí o en `ANTHROPIC_BASE_URL` |
| (proyecto) | Un `ANTHROPIC_BASE_URL` que solo aparece en `.claude/settings*.json` de un repo de `projects_dirs` se **bloquea** (403) hasta que lo añadas a `hosts`. Ver [TROUBLESHOOTING](TROUBLESHOOTING.md) |
| `capture_only_hosts` | Hosts que se **auditan sin pseudonimizar**: se descifran y se capturan, pero la petición sale tal cual. Para tráfico que dejaría de funcionar con seudónimos, como los conectores MCP de claude.ai (`mcp-proxy.anthropic.com`). Sus capturas llevan `"capture_only": true` y no cuentan como fugas |
| `intercept_all` | `true` para descifrar todo el HTTPS, no solo la API (por defecto `false`) |
| `pseudo_literals`, `pseudo_word_literals` | Valores a proteger (ver arriba) |
| `pseudo_patterns` | Expresiones regulares; `claude-proxy` añade una para tu carpeta de proyectos |
| `projects_dirs` | Carpetas cuyos repos git protege `claude-proxy` al arrancar (hasta 3 niveles). Por defecto, la carpeta padre del repo desde el que arrancas |
| `pseudo_pattern_ignore` | Valores que los patrones no deben tocar |
| `capture_retention_days` | Días que se conservan las capturas; se borran las más antiguas al arrancar `claude-proxy` (por defecto `30`; `0` = sin límite) |
| `capture_originals` | `false` para no guardar `original/`: sin datos reales en claro, pero sin verificación por pares (por defecto `true`) |
| `audit_injection_reviewed` | Avisos de prompt injection marcados como revisados en el dashboard |
| `sentinel_enabled` | Centinela de fugas: avisa de datos nuevos sin regla tras cada petición (por defecto `true`). Ver [Centinela](#-centinela-de-fugas) |
| `sentinel_min_confidence` | Confianza mínima que avisa: `MEDIUM` (por defecto, todo salvo LOW), `HIGH` o `CRITICAL` |
| `sentinel_notify` | `true` para una notificación del sistema por sesión (solo macOS). Por defecto `true` |
| `sentinel_silenced_categories` | Categorías que el centinela no avisa. Lista vacía por defecto. Se gestiona desde `klaus-alerts` (`c`); se lee en cada análisis, sin reiniciar |

Las variables de entorno (`ANTHROPIC_PSEUDO_*`, `ANTHROPIC_CAPTURE_*`, `KLAUS_INTERCEPT_ALL`, `KLAUS_LOG_DIR`) están en el [runbook](./anthropic-audit-proxy.md#configuración-por-entorno). Se aplican al proceso de `claude-proxy`, así que hay que exportarlas antes de arrancarlo.

---

## 🔔 Centinela de fugas

Un dato **nuevo**, sin regla, sale en claro en la petición en la que aparece, y se reenvía en todas las siguientes de la sesión. El centinela (#187) lo detecta **después del envío** y avisa, para que lo revises cuanto antes.

- **Qué analiza:** el último mensaje de cada petición (turno del usuario y `tool_result`), con los mismos detectores que `klaus-scan`.
- **Qué avisa:** valores que el proxy **no** sustituiría con sus reglas actuales, con confianza igual o superior a `sentinel_min_confidence`.
- **Cómo avisa:** una notificación por sesión (directorio de trabajo + día), con el recuento. Un mismo valor avisa una vez por sesión.
- **Dónde queda el registro:** `~/.klaus-proxy/alerts.jsonl`, una línea JSON por aviso. **Nunca guarda el valor**, solo `⟨categoría·hash·longitud⟩`.
- **Coste:** se ejecuta en segundo plano. Medido en #185: p95 ≈ 2 ms por petición.

> ⚠️ **No es una barrera.** Cuando avisa, el dato ya ha salido en esa petición. Por eso importa tanto la recarga en caliente: cuando apruebas una regla, se aplica en la **siguiente** petición, sin reiniciar `claude-proxy`.

**Límites:** no ve datos sin forma reconocible, como un nombre de proyecto dentro de una frase. Ver [ADR-002](./decisions/ADR-002-centinela-klaus-alerts.md) y #179.

**Para revisar un aviso:** ejecuta `klaus-alerts` en su **propia terminal**. Ver la sección «klaus-alerts» más abajo.

---

## 🖥️ klaus-alerts (revisión de avisos)

`klaus-alerts` muestra en tiempo real los avisos del centinela (#189). Es un comando aparte: si lo cierras o falla, el proxy sigue funcionando igual.

```bash
klaus-alerts
```

**Pantallas**

1. **Sesiones:** los avisos pendientes agrupados por sesión (carpeta de trabajo y día), con el recuento. Enter abre la sesión.
2. **Valores de la sesión:** cada valor aparece con su identificador enmascarado `⟨categoría·hash·longitud⟩`.

**Teclas**

| Tecla | Acción | Qué pasa |
|---|---|---|
| `a` | Aprobar | Pide confirmación. Añade el valor al vault y a `config.json`. Se aplica en la siguiente petición |
| `f` | Falso positivo | Lo añade a `pseudo_pattern_ignore` de `config.json` |
| `s` | Ignorar en la sesión | Oculta los avisos de esa sesión en esta interfaz |
| `v` | Ver contexto | Muestra la línea donde aparece el valor **solo en pantalla**. No se guarda |
| `c` | Silenciar categoría | Pide confirmación. Añade la categoría a `sentinel_silenced_categories` |
| `Esc` / `q` | Volver / salir | |

**Cómo se recupera el valor.** El registro `alerts.jsonl` nunca guarda el valor. Para `a`, `f` y `v`, `klaus-alerts` lo busca en la captura local de la misma sesión y del mismo minuto (±2 min) y lo confirma por el identificador. Si la captura ya no existe (por ejemplo, la retención la ha borrado), la acción no se aplica y lo indica.

**Límites**

- `s` solo oculta en la interfaz. Si el mismo valor vuelve a salir en esa sesión, el centinela **sigue notificando**. Ver [ADR-002](./decisions/ADR-002-centinela-klaus-alerts.md).
- Cada acción deja una línea en `alerts.jsonl` (sin valores), así que el estado se mantiene al reiniciar la interfaz.
- Requiere una terminal interactiva. Funciona en macOS y Linux.

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

## 🧰 Utilidades de instalación

Dos comandos de instalación que puedes ejecutar a mano si algo falla o quieres repetir un paso. `klaus-setup` llama al primero; el segundo es manual (`install.sh` tiene su propia lógica para instalar Python en macOS).

### `klaus-install-wrappers` — scripts `claude-with-proxy`

Copia los wrappers `claude-with-proxy` a la carpeta de comandos del usuario. Según el sistema:

- macOS / Linux: `claude-with-proxy` (bash/zsh) y `claude-with-proxy.fish`.
- Windows: `claude-with-proxy.ps1` y `claude-with-proxy.bat`.

| Sistema | Destino |
|---|---|
| macOS / Linux | `~/.local/bin/` |
| Windows | `%APPDATA%\Scripts` |

- **Quién lo llama:** `klaus-setup` lo ejecuta al configurar la terminal. Es un paso interno.
- **Cuándo usarlo a mano:** si borraste los wrappers o quieres reinstalarlos. Es seguro repetirlo: los wrappers ya presentes se reportan como «Already installed».
- **Salida esperada:** una línea por wrapper, p. ej. `✅ Installed: claude-with-proxy.fish`.

### `klaus-install-python` — comprobar y, si hace falta, instalar Python 3.13

Comprueba la versión de Python y, solo si es inferior a 3.13, intenta instalarla con el gestor del sistema:

| Sistema | Qué ejecuta |
|---|---|
| macOS con Homebrew | `brew update` y `brew install python@3.13` |
| Ubuntu / Debian | `apt install python3.13 python3.13-venv python3.13-dev` (tras `apt update`) |
| Fedora / RHEL | `dnf install python3.13 python3.13-devel` |
| Windows | `choco install python313` (si hay Chocolatey) |

- **Si ya tienes Python 3.13+:** no cambia nada y termina con `✅ Python 3.13 is compatible!`.
- **Si no hay gestor compatible:** muestra las instrucciones para instalarlo a mano y termina con error.
- **Aviso:** en macOS y Linux instala software del sistema. Si no quieres que lo haga, instala Python 3.13 tú antes.

```bash
klaus-install-python   # comprueba la versión; instala Python 3.13 si hace falta
```

---

## 🔗 Ayuda

- Issues: https://github.com/Ka0s-Klaus/klaus-proxy-local/issues
- Seguridad: [SECURITY.md](../SECURITY.md)
