# 🔍 Auditoría de payload enviado a Anthropic

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

- **¿Qué hago?** Capturo el cuerpo exacto de cada petición HTTPS que Claude Code emite hacia la API de Anthropic (y hacia el gateway LLM corporativo), para poder auditar —desde una óptica de privacidad y compliance— qué información sale del equipo.
- **¿Cómo lo hago?** Interceptando el tráfico TLS con un proxy `mitmproxy` local + un addon Python ([`src/anthropic_payload_capture.py`](../src/anthropic_payload_capture.py)) que vuelca cada request a fichero JSON, **redactando los secretos** (API key / `Authorization`).
- **¿Para qué lo hago?** Para documentar la frontera de datos real: qué se envía, a qué host, y qué contiene (system prompt, herramientas, contenido de ficheros del repo, telemetría).

---

## 📦 Ubicación y layout

```text
klaus-proxy-local/                 # el clon (instalación editable: no lo muevas)
├── src/                      # addons de mitmproxy + paquete Klaus_proxy_local (CLIs)
├── scripts/                  # dashboard, prune_vault, add_to_vault, inspect_vault…
├── tests/                    # suite pytest
├── docs/                     # documentación (docs/archive/: histórica)
└── informes/                 # informes locales del dashboard (gitignored)

~/.klaus-proxy/               # estado local (nunca versionado)
├── config.json               # SALT, hosts y reglas (pseudo_*)
├── addons/<hash>/            # snapshot inmutable de los addons en ejecución
├── captures/{original,sent}/ + .pseudonym_vault.json
├── logs/proxy.log
└── klaus-env.sh, ca-bundle.pem
```

- Se versionan el código, los tests y la documentación; **nunca** `~/.klaus-proxy/` ni `informes/`: contienen prompts, ficheros reales y el vault real ↔ seudónimo.
- La **raíz del proyecto auditado** (palanca de rutas, org/repo) sale del directorio desde el que se arranca `claude-proxy` (o de `ANTHROPIC_PSEUDO_PROJECT_ROOT`). Así se audita cualquier repo sin acoplarse a él.

---

## 🧭 Hallazgo principal: hay DOS destinos, no uno

> ℹ️ **Contexto:** este hallazgo es del entorno donde nació la herramienta (julio de 2026), con `ANTHROPIC_BASE_URL` apuntando a un gateway corporativo. **Por defecto el proxy audita y pseudonimiza `api.anthropic.com`** (clave `hosts` de `config.json`). Si usas un gateway, añádelo a `hosts` (o ponlo en `ANTHROPIC_BASE_URL`). Desde v0.6.0 solo se descifran esos hosts, `anthropic.com` y `claude.ai`; el resto va en túnel (#116). Un host desconocido con ruta de LLM solo se pseudonimiza, con un aviso en el log, si se descifra: con `"intercept_all": true`.

La inferencia **no** viaja directamente a `api.anthropic.com`. Claude Code (v2.1.216) reparte el tráfico así:

| Destino | Endpoint | Qué contiene | Sensibilidad |
| --- | --- | --- | --- |
| **`llm.tools.cloud.customer1.es`** (gateway corporativo, GCP `203.0.113.10`) | `POST /v1/messages?beta=true` | **La inferencia real**: system prompt, definición de las 25 tools, historial de mensajes, y **todo el contenido de ficheros que se lean/editen**. `model=claude-opus-4-8`, `max_tokens=64000`. | 🔴 Alta |
| `api.anthropic.com` | `POST /api/event_logging/v2/batch` | Telemetría de uso (eventos del CLI). ~226 KB. Rutas y contenido **hasheados**; comandos y prompts reducidos a **longitud/tipo**. El análisis detallado se retiró de `docs/` en `b825f9d`. | 🟢 Baja |
| `api.anthropic.com` | `GET /mcp-registry/v0/servers` | Lookup del catálogo de servidores MCP (sin datos del usuario). | 🟢 Baja |

> **Implicación de compliance:** los prompts y el contenido del repositorio salen hacia el **gateway de customer 1**, que actúa como intermediario y reenvía a Anthropic (API estilo Anthropic, cabecera `anthropic-version: 2023-06-01`). La telemetría, en cambio, va **directa** a Anthropic. Cualquier DPA/evaluación de privacidad debe cubrir ambos flujos por separado.

> 📡 **Telemetría — veredicto (2026-07-24):** analizada en detalle en el informe de telemetría (retirado de `docs/` en `b825f9d`). Sensibilidad **baja** (rutas/contenido hasheados; prompts/comandos reducidos a metadatos). Único dato identificativo: `device_id` + fingerprint de `env`. Decisión: **documentar y no bloquear**.

```mermaid
flowchart LR
    CC[Claude Code CLI<br/>claude-cli/2.1.216]
    subgraph MO[customer 1 Cloud · GCP]
      GW[llm.tools.cloud.customer1.es<br/>POST /v1/messages]
    end
    subgraph ANT[api.anthropic.com]
      TEL[/api/event_logging/v2/batch<br/>telemetría/]
      MCP[/mcp-registry/v0/servers<br/>catálogo MCP/]
    end
    CC -->|🔴 prompts + system + ficheros| GW
    GW -.reenvía.-> Anthropic[(Modelo Anthropic)]
    CC -->|🟠 telemetría de uso| TEL
    CC -->|🟢 lookup catálogo| MCP
```

---

## 🛠️ Runbook — cómo reproducir la captura

### Requisitos
- `mitmproxy` (instalado vía Homebrew: `brew install mitmproxy`).
- CA de mitmproxy generada en `~/.mitmproxy/mitmproxy-ca-cert.pem` (se crea en el primer arranque).

### Pasos

1. **Arrancar el proxy con el addon:**
   ```bash
   mitmdump -s src/anthropic_payload_capture.py --listen-host 127.0.0.1 -p 8899
   ```

2. **Enrutar Claude Code a través del proxy** (en OTRA terminal). Node no usa el keychain del sistema, de ahí `NODE_EXTRA_CA_CERTS`:
   ```bash
   HTTPS_PROXY=http://127.0.0.1:8899 \
   HTTP_PROXY=http://127.0.0.1:8899 \
   NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem \
   claude -p "tu prompt de prueba"
   ```
   > ⚠️ La sesión de Claude Code que solicita la auditoría **no puede autocapturarse** (su request ya está en vuelo). Usa siempre un proceso `claude` nuevo por el proxy.

3. **Revisar la evidencia**: cada request deja un par de ficheros con el mismo
   nombre en dos subdirectorios espejo de `captures/`:
   - `sent/` — el cuerpo **seudonimizado** que realmente salió del equipo.
   - `original/` — los **mismos datos antes** de seudonimizar (con los secretos
     Tier-1 igualmente redactados). Comparación directa: `diff original/X sent/X`.

### 🚀 Arranque

El proxy corre **en primer plano** en una terminal dedicada (logs de cada petición en vivo) y `claude` se enruta por él desde otra:

```text
claude  →  mitmdump 127.0.0.1:8899 (seudonimiza + captura + guardián)  →  api.anthropic.com
```

| Paso | Efecto |
| --- | --- |
| Terminal 1: `claude-proxy` (desde dentro de un repo) | Arranca `mitmdump` en `127.0.0.1:8899` con 5 addons desde un **snapshot inmutable** en `~/.klaus-proxy/addons/<hash>/` (#71): log en disco → passthrough TLS (solo se descifra la API) → seudonimizador → captura → guardián fail-closed. El directorio de arranque solo sirve para registrar su org/repo y la carpeta de proyectos en `config.json` (#61, #42). **Los cambios en `src/` y en `config.json` se aplican al reiniciarlo.** Ctrl+C lo detiene. |
| Terminal 2: `source ~/.klaus-proxy/klaus-env.sh` | Confianza en la CA del proxy (`NODE_EXTRA_CA_CERTS` para Claude Code; bundle de CAs para git/curl/Python). |
| Terminal 2: `export HTTPS_PROXY=http://127.0.0.1:8899` y `claude` | Enruta Claude Code por el proxy. Solo afecta a esa terminal. |

```mermaid
flowchart LR
    subgraph t1[terminal 1]
      P[claude-proxy<br/>mitmdump · 5 addons<br/>logs en vivo]
    end
    subgraph t2[terminal 2]
      C[claude] -->|HTTPS_PROXY + klaus-env.sh| P
    end
    P --> A[api.anthropic.com]
```

**Credenciales:** el proxy no las toca ni las guarda. Las cabeceras de autenticación se redactan en las capturas.

> ⚠️ **Fail-closed:** si el pseudonimizador no está cargado, el guardián responde 502 y la petición no sale. Si `claude-proxy` no está en marcha, Claude Code no puede conectar con `HTTPS_PROXY` apuntando a él. `claude-with-proxy` se niega a lanzar `claude` si el proxy no escucha. `klaus-setup` hace que cada terminal nueva arranque el proxy y exporte `HTTPS_PROXY` (#105).

> ℹ️ La sesión de Claude Code que pide la auditoría **no puede autocapturarse** (su petición ya está en vuelo). Audita siempre un proceso `claude` **nuevo** lanzado por el proxy.

> 🔁 **Sin recarga en caliente:** mitmproxy recarga los scripts `-s` cuando cambian en disco; por eso `claude-proxy` los ejecuta desde una copia inmutable. Un `git checkout` no cambia ni rompe el proxy en marcha; para aplicar cambios, reinícialo.

### 🛡️ Alternativa opcional — LaunchAgent (no mantenida)

> ⚠️ Sección conservada como referencia: no se prueba con las versiones actuales y supone funciones de shell propias para enrutar `claude`, que el proyecto no incluye.

> ⚠️ **No es el modelo activo.** Se revirtió al modelo manual de arriba para ver los
> logs en vivo. El plist está en
> `~/Library/LaunchAgents/com.customer1.anthropic-audit-proxy.plist.disabled` y las
> funciones `claude-audit` / `claude-audit-stop` / `claude-audit-restart` **se
> eliminaron**. Esta sección se conserva solo como procedimiento **reversible** de
> reactivación.

Con LaunchAgent el proxy se gestionaría como servicio de macOS (`launchd`) con
`RunAtLoad` + `KeepAlive` (arranca al iniciar sesión y se reinicia si cae),
`WorkingDirectory` = repo **AUDITADO** (de ahí sale `project_root()` para la
palanca de rutas y la identidad git; las capturas y el vault cuelgan del tooling,
no del cwd) y log en `~/.claude/mitmproxy-audit.log`.

**Reactivar** (ejecuta desde la raíz de `klaus-proxy-local`, a partir de la
plantilla versionada
[`com.customer1.anthropic-audit-proxy.plist.template`](./com.customer1.anthropic-audit-proxy.plist.template)):

```bash
# {{TOOL}} = raíz de klaus-proxy-local (este repo); {{AUDIT_REPO}} = proyecto a auditar.
AUDIT_REPO="${AUDIT_REPO:-$HOME/proyectos/customer1-ecosistema1}"   # ajústalo al repo que auditas
sed -e "s#{{MITMDUMP}}#$(which mitmdump)#g" \
    -e "s#{{TOOL}}#$PWD#g" \
    -e "s#{{AUDIT_REPO}}#$AUDIT_REPO#g" \
    -e "s#{{HOME}}#$HOME#g" \
    docs/com.customer1.anthropic-audit-proxy.plist.template \
    > ~/Library/LaunchAgents/com.customer1.anthropic-audit-proxy.plist

# Carga y arranca el servicio (uid del usuario = `id -u`):
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.customer1.anthropic-audit-proxy.plist
launchctl enable   gui/$(id -u)/com.customer1.anthropic-audit-proxy

# Verifica:
launchctl print gui/$(id -u)/com.customer1.anthropic-audit-proxy | grep -E "state|pid"
lsof -nP -iTCP:8899 -sTCP:LISTEN
```

Con el LaunchAgent en marcha, la función `claude()` de `~/.zshrc` (la misma del
modelo manual: **solo enruta**, fail-closed) encontraría el proxy ya escuchando en
`:8899` y saldría por él sin más. Para volver a deshabilitarlo:

```bash
launchctl bootout gui/$(id -u)/com.customer1.anthropic-audit-proxy
mv ~/Library/LaunchAgents/com.customer1.anthropic-audit-proxy.plist{,.disabled}
```

> ℹ️ También con LaunchAgent, la sesión que pide la auditoría **no puede
> autocapturarse**: audita un proceso `claude` **nuevo**.

### 🧪 Secuencia de primera prueba (de principio a fin)

En **dos terminales** que ya tengan exportadas tus credenciales del proveedor
(`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` — las funciones **no** las gestionan):

```bash
# Terminal 1 — arranca el proxy en primer plano (déjala abierta, logs en vivo):
claude-proxy

# Terminal 2 — lanza claude enrutado por el proxy:
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude -p "responde solo con la palabra: pong"

# Terminal 2 — verifica en un comando lo que salió del equipo:
python3 src/anthropic_capture_verify.py
```

Esperado: `✅ TODO CORRECTO` con destino `api.anthropic.com`, cabeceras redactadas y sin fugas.

> ⚠️ La sesión de Claude Code que pide la auditoría **no puede autocapturarse**:
> lanza siempre un proceso `claude` **nuevo** por el proxy, que sí es auditable.

### ✅ Verificación en un comando: `anthropic-capture-verify`

Después de una prueba, en lugar de abrir el `.json` a mano, un único comando
comprueba la **última captura de inferencia** (`/v1/messages` → proveedor) y
emite veredicto. Opera sobre `sent/` (lo que **realmente salió**); verificar
`original/` daría FAIL de fuga a propósito, porque ahí los datos reales están
por diseño:

```bash
python3 src/anthropic_capture_verify.py
```

Verifica las **tres garantías** de la auditoría y avisa si la seudonimización no actuó:

| Comprobación | Qué exige | Nivel si falla |
| --- | --- | --- |
| 🎯 **Destino** | La inferencia fue a `llm.tools.cloud.customer1.es` (no directa a Anthropic) | ❌ FAIL |
| 🔑 **Secretos redactados** | Cabeceras `Authorization`/`x-api-key`/… = `«REDACTED»` y **cero** tokens `sk-…`/`Bearer …` en claro | ❌ FAIL |
| 🕵️ **Sin fugas en claro** | Ningún **valor real** del vault (rutas, usuario, identidad git, org/repo, emails, IPs) aparece en el cuerpo | ❌ FAIL (⚠️ WARN si el valor es de baja sensibilidad: loopback/DNS público) |
| 🕵️ **Seudonimización activa** | Se detecta ≥1 seudónimo en el cuerpo (prueba de que reescribió) | ⚠️ WARN (normal si el prompt no tenía datos sensibles) |

- **Selección automática:** elige la última captura que sea inferencia real al
  proveedor. La telemetría a `api.anthropic.com` (que es la más reciente a menudo)
  se ignora salvo que pases `--any`.
- **No re-expone secretos:** si detecta una fuga, muestra el **seudónimo** esperado
  y el valor real **enmascarado** (`/U•••••••••••b`), nunca el valor completo.
- **Código de salida:** `0` todo correcto · `1` hay fallos · `2` no hay capturas
  (útil para encadenar en cron/CI).

| Flag | Efecto | Default |
| --- | --- | --- |
| `[fichero]` | Verifica una captura concreta en vez de la última inferencia | — |
| `--dir PATH` | Directorio de capturas | `captures/sent/` (con fallback al histórico plano) |
| `--vault PATH` | Ruta del vault de seudonimización | `captures/.pseudonym_vault.json` |
| `--provider-host H` | Host esperado del proveedor | `llm.tools.cloud.customer1.es` |
| `--any` | Verifica la última captura aunque sea telemetría/no-inferencia | off |

> ⚠️ **Necesitas capturas primero.** Si no existe ninguna, el comando devuelve `2`
> con el aviso *"¿Arrancaste `claude-proxy` y lanzaste `claude` por él?"*. Para
> generarlas hay que tener el proxy en marcha (`claude-proxy`, ver arriba) y lanzar
> `claude` por él; el proxy manual equivale a:
> ```bash
> mitmdump -s src/anthropic_payload_pseudonymize.py \
>          -s src/anthropic_payload_capture.py --listen-host 127.0.0.1 -p 8899
> ```

> 🧪 Tests en [`tests/test_anthropic_capture_verify.py`](../tests/test_anthropic_capture_verify.py) (30):
> selección de inferencia vs telemetría, destino, redacción de cabeceras/token,
> detección de fugas (alta/baja sensibilidad), enmascarado sin re-exposición,
> seudonimización presente/ausente y códigos de salida del CLI.
> Ejecuta: `pytest tests/test_anthropic_capture_verify.py`.

### 🔬 Validación diferencial por pares: `anthropic-pair-verify`

El verificador de arriba compara una captura contra el **vault**. Tiene un punto
ciego: si un identificador **nunca se seudonimizó** (p.ej. faltaba en
`ANTHROPIC_PSEUDO_WORD_LITERALS`), tampoco entró al vault, así que **no hay valor
que buscar** y la fuga pasa en silencio — es el fallo que produjo las fugas de
alta sensibilidad del barrido histórico.

`anthropic_pair_verify.py` cierra ese hueco **sin depender del vault**: empareja
cada `original/<n>` con su `sent/<n>` (mismo nombre) y comprueba que **ningún dato
sensible del original sobrevive verbatim en el sent**, derivando "lo sensible" del
propio original + el entorno + los mismos patrones del seudonimizador.

```bash
python3 src/anthropic_pair_verify.py               # barrido de todos los pares
python3 src/anthropic_pair_verify.py <nombre.json> # un par concreto
python3 src/anthropic_pair_verify.py --survivors   # tabla de slugs a revisar
```

**Capas que deciden el veredicto (exit code):**

| Comprobación | Qué exige | Nivel si falla |
| --- | --- | --- |
| 🔗 **Emparejamiento** | Variantes `original`/`sent` coherentes | ⚠️ WARN |
| 🕵️ **Fugas en claro (HARD)** | Ningún valor sensible del original reaparece en el sent: emails, IPv4 (no loopback), rutas home/proj, usuario/identidad git, word-literals + org/repo del remote, y valores del vault | ❌ FAIL |
| 🔑 **Secretos redactados** | Ningún secreto Tier-1 (PEM/AWS/GitHub/JWT/…) viaja **en claro** en el sent (deben ir `«REDACTED:…»`) | ❌ FAIL |

- **Código de salida:** `0` sin fugas · `1` alguna fuga HARD (o WARN con
  `--fail-on-warn`) · `2` no hay pares. Gateable en CI (formaliza el caso **T7**
  del plan de pruebas de control).
- **No re-expone valores:** las fugas HARD se reportan **enmascaradas** (`mask`),
  agrupadas por categoría; nunca el valor completo.

**Modo descubrimiento `--survivors` (informativo, NO veredicto):** emite una tabla
global de *slugs con guion* (`org-repo`) que sobreviven de original a sent en el
**contenido de los mensajes** y no son vocabulario conocido (excluye UUIDs, fechas,
flags `claude-*`/`anthropic-*`, cabeceras y andamiaje de la API). Es el apoyo para
descubrir qué identificadores añadir a `ANTHROPIC_PSEUDO_WORD_LITERALS`
(pre-flight **P4**). Nunca afecta al exit code. Afina el umbral con `--min-count N`.

| Flag | Efecto | Default |
| --- | --- | --- |
| `[nombre]` | Verifica un par concreto en vez de todos | — |
| `--original-dir` / `--sent-dir` | Directorios del par | `captures/original/` · `captures/sent/` |
| `--vault PATH` | Ruta del vault | `captures/.pseudonym_vault.json` |
| `--verbose` | Imprime también los pares sin hallazgos | off |
| `--fail-on-warn` | El exit code también falla con WARN (auditoría estricta) | off |
| `--survivors` | Modo descubrimiento (tabla de slugs candidatos) | off |
| `--min-count N` | En `--survivors`, umbral mínimo de pares por slug | `1` |

> 🧪 Tests en [`tests/test_anthropic_pair_verify.py`](../tests/test_anthropic_pair_verify.py) (26):
> emparejado y huérfanos, cada categoría HARD/SECRET con y sin fuga, `_MIN_LEAK_LEN`,
> `message_text` (excluye system/tools/cabeceras), `collect_survivors`, códigos de
> salida y la regresión del hallazgo (slug de otro proyecto no seudonimizado).
> Ejecuta: `pytest tests/test_anthropic_pair_verify.py`.

> 🧭 **Cuándo usar cuál:** `anthropic-capture-verify` para un chequeo rápido de la
> última inferencia (destino + secretos + fugas de vault); `anthropic-pair-verify`
> para el **barrido de control** independiente del vault sobre todo el histórico de
> pares. Se complementan.

### Configuración por variables de entorno

| Variable | Efecto | Default |
| --- | --- | --- |
| `ANTHROPIC_CAPTURE_HOSTS` | Lista de hosts a capturar (coma-separada); sustituye a `hosts` de `config.json`. Sin ella, se capturan los mismos hosts que se seudonimizan (#119) | `hosts` de `config.json` (`api.anthropic.com`) |
| `ANTHROPIC_CAPTURE_REDACT` | `0` para capturar secretos tal cual (⚠️ no versionar) | `1` (redacta) |
| `ANTHROPIC_CAPTURE_DIR` | Directorio **base** de salida (los pares caen en sus subdirs `sent/` y `original/`) | `captures/` |

---

## 🕵️ Seudonimización bidireccional (opcional)

Además de **observar**, el proxy puede **reescribir en vuelo** los datos sensibles del cuerpo por seudónimos estables, y **revertirlos en la respuesta** para que las tool calls sigan operando sobre valores reales. Addon: [`src/anthropic_payload_pseudonymize.py`](../src/anthropic_payload_pseudonymize.py).

> 🔗 **El seudonimizador y la captura cooperan por `flow.metadata`.** El seudonimizador (que corre ANTES) deja en el flujo el cuerpo `original` (datos reales, secretos Tier-1 ya redactados) además de reescribir la request. La captura (DESPUÉS) graba el par: `sent/` desde la request ya reescrita, `original/` desde el cuerpo del `metadata`. Si el seudonimizador está deshabilitado, `original` == `sent` y `pseudonymized=false`.

> 🔧 **Transformación estructural (no regex sobre JSON crudo):** el cuerpo se parsea como JSON y solo se seudonimizan los **valores string**, re-serializando después. Así el encoder re-escapa comillas y backslashes y es **imposible romper el JSON** (una sustitución sobre el JSON ya serializado podía comerse el `\` de un `\"` → `400 Invalid JSON`; corregido). Si el cuerpo no es JSON, cae a texto plano.

```mermaid
flowchart LR
    CLI[Claude Code] -->|real| P1[pseudonymize.request<br/>forward]
    P1 -->|seudónimo| GW[gateway / Anthropic]
    GW -->|seudónimo| P2[pseudonymize.response<br/>restore]
    P2 -->|real| CLI
```

- **Qué seudonimiza (por defecto, autodetectado):** raíz del repo y `$HOME` (**palanca de rutas**), usuario del SO e identidad git (`user.name`/`user.email`), org y nombre de repo del `remote origin`, y por regex emails e IPv4 (con octetos 0–255; las versiones tipo `cc_version=2.1.312.625` no cuentan, #57).
- **Org/repo de cualquier proyecto:** además del repo desde el que arranca `claude-proxy` (#61), el seudonimizador **aprende** el org/repo de los remotes que Claude Code envía en cada petición y los guarda en `pseudo_word_literals` (#63). Solo en los modos de permisos `auto` y `plan` (ver README). Los nombres con puntos se reconocen (#65).
- **`pseudo_patterns` (#42):** regex de `config.json` que se aplican antes que el resto de reglas, sobre el texto real. Si hay grupos, solo se seudonimiza el grupo 1. `claude-proxy` registra la carpeta que contiene el repo (p. ej. `~/proyectos`), con lo que los nombres de todos los proyectos quedan ocultos en las rutas aunque no tengan remote o vayan truncados. Hay un patrón integrado para el usuario de cualquier `/Users/<u>` o `/home/<u>`. Los patrones **ignoran los valores que no pueden ser un dato** (#92): sin letras ni números (`…`, `|`), de un solo carácter, marcadores de plantilla (`{user}`, `<u>`, `«X»`, `$USER`, `%USERNAME%`) y, como usuario, nombres genéricos (`Shared`, `Guest`, `root`, `user`, `username`, `usuario`, `nobody`). Así no entran al vault ni el verificador los toma por fugas. Para excluir valores concretos (por ejemplo, usuarios de ejemplo de unos tests), añádelos a `pseudo_pattern_ignore` en `config.json`. Los **nombres de carpeta de proyectos** que ya están en el vault (`dir_…`) se sustituyen también **fuera de una ruta**, como palabra completa y con el mismo seudónimo (#93): un `<carpeta>.md`, la raíz de un árbol en un README o una ruta codificada con guiones (`-Users-u-proyectos-<carpeta>-…`). Solo los de 5 caracteres o más que no sean genéricos (`scripts`, `tests`, `tools`…) ni estén en `pseudo_pattern_ignore`. Distingue mayúsculas: `EFDEF` no es `efdef`.
- **Secretos (Tier 1) — redacción IRREVERSIBLE:** si un `Read`/`Bash` arrastra una credencial, el **cuerpo** no está redactado como las cabeceras. Estos patrones la sustituyen por un placeholder fijo `«REDACTED:label»` que **no entra al vault** (no se revierte — el modelo casi nunca necesita el valor real, y así el vault no acumula secretos):

  | Patrón | Detecta |
  | --- | --- |
  | `private-key` | Bloques `-----BEGIN … PRIVATE KEY-----` |
  | `aws-access-key` | `AKIA…` (16) |
  | `github-token` | `ghp_/gho_/ghu_/ghs_/ghr_…` |
  | `google-api-key` | `AIza…` (35) |
  | `slack-token` | `xox[baprs]-…` |
  | `jwt` | `eyJ….….…` |
  | `secret-kv` ⚙️ | `secret/token/password/api_key… = valor` (redacta solo el valor). **Opt-in** (`ANTHROPIC_PSEUDO_SECRET_KV=1`): sobre código mis-dispara, así que solo para auditar un `.env`/secretos concreto. Lleva lookahead de delimitador para no confundir `os.getenv("X")` con una credencial. |

- **Literales con frontera de palabra (Tier 2) — reversibles:** términos cortos/ambiguos (códigos de cliente `orgcode1`/`orgcode2`, IDs de proyecto cloud como `orgcode3`, dominios corporativos) que **no** pueden ir por substring porque corromperían palabras (`orgcode2` dentro de `HTTPS`). Se sustituyen solo con frontera alfanumérica y **sí** se revierten. Org/repo del remote se autodetectan; el resto se añade por `ANTHROPIC_PSEUDO_WORD_LITERALS`.
- **Palanca de rutas:** una ruta como `/home/localuser/proyectos/customer1-ecosistema1/dashboard/app.py` sale como `/proj_xxxxxxxx/dashboard/app.py` — se oculta home + usuario + nombre de proyecto pero se **conserva la estructura relativa y la extensión**, y al volver se reconstruye la ruta absoluta real. Incluso una ruta que el modelo **invente** bajo el seudónimo (`/proj_xxxx/docs/nuevo.md`) se traduce a la ruta real antes de que el CLI la ejecute.
- **Vault:** mapa bidireccional `real↔seudónimo` (hash con sal, estable y no reversible sin el vault). Se persiste en `captures/.pseudonym_vault.json`. ⚠️ **Es el fichero más sensible de la auditoría — contiene los valores reales.** Vive en el directorio gitignored; nunca se versiona.

### Ejecución (seudonimizador ANTES de la captura)

El orden importa: el seudonimizador debe reescribir **antes** de que la captura grabe, para que la evidencia refleje lo que *realmente* sale del equipo.

```bash
# Lo que lanza claude-proxy (desde el snapshot ~/.klaus-proxy/addons/<hash>/):
mitmdump -s klaus_file_log.py \
         -s klaus_tls_passthrough.py \
         -s anthropic_payload_pseudonymize.py \
         -s anthropic_payload_capture.py \
         -s klaus_pseudo_guard.py --listen-host 127.0.0.1 -p 8899
```

El log va primero para registrar la carga de los demás; el passthrough TLS después, para decidir qué conexiones se descifran (solo los hosts de la API; el resto va en túnel, #116); el guardián, el último, para comprobar que el seudonimizador procesó cada petición.

### Configuración por entorno

| Variable | Efecto | Default |
| --- | --- | --- |
| `ANTHROPIC_PSEUDO_ENABLE` | Interruptor general | `1` |
| `ANTHROPIC_PSEUDO_PATHS` | Palanca de rutas de ficheros | `1` |
| `ANTHROPIC_PSEUDO_REGEX` | Detección email / IPv4 | `1` |
| `ANTHROPIC_PSEUDO_SECRETS` | Detectores precisos de secretos (PEM/AWS/GitHub/...) | `1` |
| `ANTHROPIC_PSEUDO_SECRET_KV` | Matcher genérico `clave=valor` (ruidoso sobre código) | `0` |
| `ANTHROPIC_PSEUDO_LITERALS` | Literales extra por substring (coma-separados) | — |
| `ANTHROPIC_PSEUDO_WORD_LITERALS` | Literales con frontera de palabra: `orgcode1,orgcode2,orgcode3,customer1.es` | — |
| `ANTHROPIC_PSEUDO_PATHS_EXTRA` | Prefijos de ruta extra `"/ruta=label,..."` | — |
| `ANTHROPIC_PSEUDO_USER_DIRS` | Patrón integrado de usuarios en `/Users/<u>` y `/home/<u>` (#42) | `1` |
| `ANTHROPIC_PSEUDO_DIR_WORDS` | Nombres de carpeta de proyectos del vault también fuera de una ruta (#93) | `1` |
| `ANTHROPIC_PSEUDO_SALT` | Sal del hash de seudónimos. **Obligatoria**: `claude-proxy` la exporta desde `config.json` | (de `config.json`) |
| `ANTHROPIC_PSEUDO_VAULT` | Ruta del vault | `captures/.pseudonym_vault.json` |
| `KLAUS_INTERCEPT_ALL` | Descifrar todo el HTTPS, no solo los hosts de la API (equivale a `"intercept_all": true` en `config.json`) (#116) | `0` |
| `KLAUS_LOG_DIR` | Directorio del log en disco (`proxy.log`, rotado 5 MB × 5) (#55) | `~/.klaus-proxy/logs/` |

Además de las variables, `~/.klaus-proxy/config.json` admite `hosts` (hosts de la API que se descifran y pseudonimizan), `intercept_all`, `pseudo_literals`, `pseudo_word_literals`, `pseudo_patterns` y `pseudo_pattern_ignore`, que persisten entre reinicios.

**Limpiar el vault (#92).** Los valores que entraron al vault antes de que los patrones los ignorasen se quitan con:

```bash
python3 scripts/prune_vault.py --dry-run   # qué se quitaría
python3 scripts/prune_vault.py             # quitar, con copia de seguridad
```

Ejecútalo con **`claude-proxy` parado**: el proxy guarda su copia en memoria del vault cada vez que añade un seudónimo y volvería a escribir las entradas quitadas. El script se niega a continuar si el puerto 8899 está escuchando, salvo con `--force`. Solo toca entradas de patrones activos (`user_`, `dir_`…).

> ⚠️ **Limitación conocida (streaming):** la respuesta se procesa **completa** (mitmproxy bufferiza por defecto), lo que es correcto para las tool calls pero retrasa el render token a token. Las respuestas SSE se restauran **por bloque** (#67): se concatenan los `content_block_delta` de cada bloque (texto, argumentos de `tool_use` y thinking) antes de revertir, porque un seudónimo puede llegar partido entre dos deltas.

> Tests en [`tests/test_anthropic_payload_pseudonymize.py`](../tests/test_anthropic_payload_pseudonymize.py): round-trip forward/restore, longest-match-first, palanca de rutas, regex, idempotencia, persistencia del vault, redacción irreversible de secretos, word-literals con frontera (no corrompen `HTTPS`/`COMMIT`), transformación estructural JSON (regresión del `400`) y `secret-kv` sin morder `os.getenv(...)`.

---

## 🎨 Logs coloreados

Los dos addons colorean sus líneas de log **por semántica**, para escanear en vivo de un vistazo qué está pasando:

| Color | Nivel | Cuándo | Ejemplo |
| --- | --- | --- | --- |
| 🟢 Verde | `ok` | Se ejecutó una acción de auditoría real: el cuerpo se **reescribió** (dato sensible neutralizado) o la respuesta se **revirtió** | `[anthropic-pseudo] request POST /v1/messages seudónimos=53`<br>`[anthropic-capture] POST /v1/messages → sent/… (pseudonymized=True)` |
| ⚪ Neutro | — | La request salió pero **no había nada que seudonimizar** (p. ej. telemetría `event_logging`). No es un problema — ver telemetría | `[anthropic-capture] POST /api/event_logging/v2/batch → sent/… (pseudonymized=False)` |
| 🟡 Amarillo | `warn` | Degradación que **no es fuga**: no se pudo persistir el vault (la request ya salió seudonimizada) o no se pudo revertir la response (el CLI puede ver seudónimos) | `[anthropic-pseudo] WARN no pude persistir el vault: … (la request va seudonimizada)`<br>`[anthropic-pseudo] WARN no pude leer la response de /… — no se revierte` |
| 🔴 Rojo | `error` | Fallo serio: request **bloqueada en fail-closed** (no se pudo seudonimizar → no salió) o fallo al **escribir la evidencia** en disco | `[anthropic-pseudo] BLOQUEADA (fail-closed) POST /v1/messages: …`<br>`[anthropic-capture] ERROR escribiendo evidencia 20260724_130145_… : …` |

> 💡 El neutro (sin color) para `pseudonymized=False` es **deliberado**: la telemetría domina el tráfico y nunca contiene rutas/identidad, así que colorearla llamaría la atención sin motivo. El amarillo se reserva a degradaciones sin fuga; lo que sí pone en riesgo un dato se **bloquea** (rojo), no se avisa.

### Cuándo se colorea

El coloreado se activa **solo si la salida es una terminal** (`sys.stdout.isatty()`), de modo que si rediriges el log a un fichero o lo pasas por un pipe (`claude-proxy | tee audit.log`) **no se cuelan secuencias ANSI** en la evidencia. Además:

| Variable | Efecto |
| --- | --- |
| `NO_COLOR` (presente, cualquier valor) | Desactiva el color (convención [no-color.org](https://no-color.org)) |
| `ANTHROPIC_LOG_COLOR=1` | **Fuerza** color aunque no sea TTY (útil para `less -R`) |
| `ANTHROPIC_LOG_COLOR=0` | Desactiva color aunque sea TTY |

El helper `colorize()` / `color_enabled()` es una función pura (misma implementación autocontenida en ambos addons), con tests en `test_anthropic_payload_capture.py` y `test_anthropic_payload_pseudonymize.py`.

### 🚧 Fail-closed: si no se puede seudonimizar, no sale

El seudonimizador está diseñado para **fallar cerrado**: si cualquier paso de la seudonimización de una request a un host objetivo lanza una excepción (no se puede leer/decodificar el cuerpo, reescribirlo, etc.), la request se **aborta localmente** y **no se envía a Anthropic**.

- Técnicamente: `request()` envuelve todo el trabajo en un `try`; ante excepción, `_fail_closed()` fija `flow.response` a un **502** con un mensaje explicativo (mitmproxy responde **sin contactar con el servidor**). Si ni eso se puede, `flow.kill()`.
- **Por qué:** sin esta red, una excepción en un hook de mitmproxy se **loguea pero el flujo continúa con el cuerpo original** — es decir, saldría **sin seudonimizar** (fail-**open**). El fail-closed convierte ese borde silencioso en un bloqueo ruidoso (línea 🔴 roja).
- **Evidencia:** la request bloqueada se marca con `blocked: true` en el par `sent`/`original`. El cuerpo de `sent/` es un **marcador** (`«BLOCKED: …»`), no el cuerpo real — porque no salió nada. El cuerpo real (con secretos redactados) queda en `original/` para diagnóstico.
- **Alcance:** solo aplica a la **request** (hacia Anthropic). En la **response** (hacia el CLI) NO se bloquea: no poder revertir seudónimos no es una fuga, así que se avisa en 🟡 amarillo y se deja pasar (bloquearla solo rompería la sesión).

- **Guardián (#71):** `klaus_pseudo_guard.py` se carga el último y bloquea con **502** cualquier petición que el seudonimizador no haya marcado como procesada, por ejemplo si su addon no llegó a cargar. En el log aparece `[klaus-guard] BLOQUEADA …`. Cubre el caso en que mitmproxy se queda sin el addon, que el `try` de `request()` no puede ver.

> En la práctica este bloqueo casi nunca se dispara: `get_text`/`pseudonymize_body` no lanzan sobre el JSON bien formado que envía Claude Code. Es una **red de seguridad**, no un camino habitual.

---

## 🔒 Tratamiento de secretos

Por defecto se **redactan** (`«REDACTED»`) las cabeceras `x-api-key`, `Authorization`, `anthropic-organization-id`, `cookie`. Esto hace que los ficheros de evidencia sean seguros de versionar. El campo `secrets_redacted: true` del JSON deja constancia de que la redacción se aplicó.

## 🗂️ Nomenclatura y estructura de ficheros

Cada request genera un **par** de evidencias con **idéntico nombre** en dos
subdirectorios espejo, de modo que se compare al instante qué se *iba* a enviar
frente a lo que se envió:

```
captures/
├── original/   YYYYMMDD_HHMMSS_anthropic_payload.json   # datos reales (secretos Tier-1 redactados)
└── sent/       YYYYMMDD_HHMMSS_anthropic_payload.json   # cuerpo seudonimizado — lo que salió
```

(Con sufijo `_N` ante colisiones dentro del mismo segundo; el contador se
sincroniza sobre ambos subdirectorios para que el par nunca se desalinee.)

Cada registro lleva `variant` (`original`|`sent`), `pseudonymized` (bool) y
`counterpart` (el nombre del fichero pareja). Comparación:

```bash
diff captures/original/20260722_090605_anthropic_payload.json \
     captures/sent/20260722_090605_anthropic_payload.json
```

> ⚠️ **`original/` es tan sensible como el vault**: contiene rutas, identidad,
> prompts y contenido de ficheros en claro. Vive en el directorio gitignored y
> **jamás** se versiona. Las credenciales Tier-1 (claves privadas, tokens
> AWS/GitHub/JWT) sí se redactan también aquí: nunca caen a disco.

> 🕵️ **`sent/` seudonimiza también `url`/`host`/`path` y valores de cabecera**
> (no solo el cuerpo), reutilizando el vault ya poblado por el cuerpo — sin
> acuñar seudónimos nuevos. Así el subdominio del gateway corporativo no se
> filtra en la evidencia. En `original/` esos campos van reales. El verificador
> acepta el host del proveedor tanto real como seudonimizado.

> ℹ️ Las capturas **anteriores** a este split viven planas en `captures/`
> (sin par `original/`). El verificador cae a ellas si `sent/` aún está vacío.

## 🧰 Scripts del tooling

Cinco scripts **versionados** en `src/`, cada uno con su test espejo en
`tests/` (lo que se versiona es el código; los datos de `captures/` no):

| Script | Rol | Doc |
| --- | --- | --- |
| [`klaus_tls_passthrough.py`](../src/klaus_tls_passthrough.py) | Addon de **passthrough TLS**: solo descifra los hosts de la API; el resto va en túnel y se registra (#116). | [Arquitectura](./ARCHITECTURE_DEEP_DIVE.md) |
| [`anthropic_payload_capture.py`](../src/anthropic_payload_capture.py) | Addon de **captura**: graba el par `original/`+`sent/` de cada request. | este documento |
| [`anthropic_payload_pseudonymize.py`](../src/anthropic_payload_pseudonymize.py) | Addon de **seudonimización** bidireccional (forward/restore). | §"Seudonimización bidireccional" |
| [`anthropic_capture_verify.py`](../src/anthropic_capture_verify.py) | **Verificador** de una captura (destino, secretos, fugas). | §"Verificación en un comando" |
| [`anthropic_pair_verify.py`](../src/anthropic_pair_verify.py) | **Validador diferencial** por pares `original`↔`sent` (fugas independientes del vault + descubrimiento de slugs). | §"Validación diferencial por pares" |
| [`anthropic_payload_analyze.py`](../src/anthropic_payload_analyze.py) | **Analizador**: vuelca todo lo que sale al modelo (system, tools, historial, ficheros embebidos). | `MANIFIESTO_ficheros_embebidos.md` (retirado) |
| [`anthropic_artifacts_cleanup.py`](../src/anthropic_artifacts_cleanup.py) | **Limpieza + hardening** del riesgo *data-at-rest* (artefactos en claro que Claude Code deja en disco). | `MANUAL_limpieza_hardening.md` (retirado) |

## 🧪 Tests

Espejo en `tests/`. La configuración de pytest vive en `pyproject.toml` (`[tool.pytest.ini_options]`); las dependencias de test se instalan con `pip install -e ".[dev]"` (ver [entorno de desarrollo](./setup.md)). Ejecuta toda la suite con `pytest`.

- Cada addon y cada CLI tiene su fichero de tests (`test_anthropic_payload_pseudonymize.py`, `test_anthropic_pair_verify.py`, `test_anthropic_payload_capture.py`, `test_addons_snapshot.py`, `test_audit_reports.py`…).
- `tests/conftest.py` genera una SALT de prueba y redirige `config.json` a un fichero temporal: ningún test escribe en el `~/.klaus-proxy/` real.
- CI ejecuta la suite completa en Python 3.10, 3.11, 3.12 y 3.13, y el lint con `black==25.11.0` y `ruff<1` (fijados en `pyproject.toml`).
