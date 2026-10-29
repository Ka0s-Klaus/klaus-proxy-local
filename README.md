# 🔌 Klaus Proxy Local

> **Proxy local de auditoría, pseudonimización y detección automática de fugas** — intercepta,
> audita y pseudonimiza el tráfico que Claude Code envía a la API de Anthropic (y al
> gateway LLM corporativo), con análisis multi-modo y corrección automática de fugas.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Version](https://img.shields.io/badge/version-0.5.2-green)](./docs/RELEASE_v0.5.2_NOTES.md)
[![Tests](https://img.shields.io/badge/tests-669%20passed-brightgreen)](./.github/workflows/ci.yml)
[![Status](https://img.shields.io/badge/status-Production%20Ready-success)](./docs/RELEASE_v0.5.2_NOTES.md)
[![mitmproxy](https://img.shields.io/badge/mitmproxy-addon-orange)](https://mitmproxy.org)
[![K*](https://img.shields.io/badge/K%2A-AI%20Workspace-purple)](https://github.com/Ka0s-Klaus)

---

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

### ¿Qué hago?
`Klaus Proxy Local` es un **proxy local de auditoría** que se sitúa delante de Claude
Code (u otro cliente de la API de Anthropic) e intercepta cada petición HTTPS hacia
`api.anthropic.com` y hacia el gateway LLM corporativo. Sobre ese tráfico:

- **Audita** el cuerpo exacto que sale del equipo (system prompt, definición de
  herramientas, historial y **contenido de ficheros del repo**), redactando los
  secretos de las cabeceras.
- **Seudonimiza en vuelo** los datos sensibles del cuerpo (rutas, usuario, identidad
  git, org/repo, emails, IPs) por seudónimos estables y **los revierte en la respuesta**
  para que las tool calls sigan operando sobre valores reales.
- **Verifica** que lo que salió cumple las garantías (destino correcto, secretos
  redactados, cero fugas en claro) y **limpia** los artefactos *data-at-rest* que
  Claude Code deja en disco.

### ¿Cómo lo hago?
- Un proxy `mitmproxy` local (`claude-proxy` → `mitmdump --listen-host 127.0.0.1 -p 8899`, solo loopback)
  con cuatro addons Python de [`src/`](./src), cargados desde un snapshot inmutable:
  `klaus_file_log.py` (log en disco), `anthropic_payload_pseudonymize.py` (reescribe/revierte),
  `anthropic_payload_capture.py` (graba la evidencia) y `klaus_pseudo_guard.py` (bloquea lo
  que no se haya pseudonimizado).
- Claude Code se enruta por el proxy vía `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS`, de
  forma **fail-closed** (si el proxy no escucha, `claude` aborta y no deja salir
  tráfico sin auditar).
- La evidencia cae en `~/.klaus-proxy/captures/` como pares espejo `original/` (datos
  reales) vs `sent/` (lo que realmente salió, seudonimizado).

### ¿Y para qué lo hago?
- **Privacidad / compliance**: documentar y controlar la frontera de datos real hacia
  la API — qué se envía, a qué host y qué contiene.
- **Prevención de fugas**: seudonimizar identidades, rutas y códigos internos antes de
  que salgan del equipo.
- **Trazabilidad**: evidencia auditable y verificable de cada inferencia.

> 🛣️ **Roadmap:** sobre esta base de interceptación se pueden añadir capacidades de
> proxy/gateway (caché semántico, rate limiting, métricas, multi-proveedor). Hoy el
> foco es la auditoría y la seudonimización.

---

## 🚀 Inicio rápido (v0.5.2)

> ℹ️ El paquete **no está publicado en PyPI**: se instala desde el repositorio con
> `install.sh` (macOS y Linux, Python ≥ 3.10; en macOS instala Python 3.13 vía Homebrew si falta; en Debian/Ubuntu hace falta `python3-venv`).

```bash
# Instalar: crea un venv en ~/.local/share/klaus/venv, instala mitmproxy, genera
# config + SALT + certificado CA y enlaza los comandos en ~/.local/bin
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
./install.sh --check   # opcional: solo verifica prerequisitos
./install.sh

# Terminal 1: arrancar el proxy (solo escucha en 127.0.0.1:8899)
claude-proxy
# ✅ Captures guardadas en ~/.klaus-proxy/captures/ (no repo)
# ✅ Logs con COLORES (verde = OK, rojo = error)
# ✅ Ctrl+C responde al instante

# Terminal 2: usar Claude Code (SSL/TLS configurado automáticamente)
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude "tu pregunta"

# Terminal 3: auditar payloads (CLI)
klaus-audit-payloads

# Terminal 3 alternativo: dashboard visual en el navegador
# (guarda cada informe en informes/; selector de anteriores + cambios)
klaus-audit-dashboard --open
```

**Auditoría avanzada:**
```bash
# Ver payloads específicos que no están pseudonimizados
klaus-fix-pseudonymization --show-payloads

# Exportar audit a CSV
klaus-audit-payloads --export=csv
```

**Alternativamente, configuración automática al arrancar el shell:**
```bash
# Setup de una vez (auto-startup en nuevos terminales)
klaus-setup
# Selecciona 'y' para auto-startup, luego: exec $SHELL
```

> ⚠️ La instalación es *editable*: el venv apunta al clon del repositorio. **No borres
> ni muevas esa carpeta.** Para actualizar: `git pull && ./install.sh`.

✨ **Eso es todo.** Todo es automático: configuración, certificados, SALT, auditoría, corrección de fugas, **y ahora con captura en usuario-local + colores + Ctrl+C rápido**.

---

## 🔐 SSL/TLS Certificate Trust (v0.3.0+)

Klaus Proxy now **automatically configures** SSL/TLS certificate trust for all your tools. No more "Client TLS handshake failed" errors.

### How It Works

When you start `claude-proxy`, it automatically generates `~/.klaus-proxy/klaus-env.sh` containing:

```bash
export GIT_SSL_CAINFO="$HOME/.klaus-proxy/ca-bundle.pem"
export CURL_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export SSL_CERT_FILE="$HOME/.klaus-proxy/ca-bundle.pem"
export REQUESTS_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export NODE_EXTRA_CA_CERTS="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
```

This tells your tools (git, curl, Python, Node.js) to trust the proxy's certificate automatically.

`ca-bundle.pem` = system CAs + the proxy CA, regenerated on every `claude-proxy` start.
The first four variables **replace** the trust store, so pointing them at the proxy CA
alone would break HTTPS that doesn't go through the proxy. `NODE_EXTRA_CA_CERTS` only
**adds** to Node's store, so it uses the proxy CA directly.

### Setup Options

#### Option 1: Auto-Startup (Recommended)

```bash
# Interactive setup (one-time)
klaus-setup

# Follow prompts:
# • Shell detected: zsh (or your shell)
# • Enable auto-startup? [y/N]: y
# • Reload shell
exec $SHELL
```

Now every time you open a terminal:
- ✅ Proxy starts automatically
- ✅ SSL/TLS variables are loaded
- ✅ Git/curl/all HTTPS tools trust the proxy

#### Option 2: Manual (Quick Test)

```bash
# Terminal 1: Start proxy
claude-proxy

# Terminal 2: Load SSL/TLS variables
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

# Now use git, curl, or Claude Code
git clone https://github.com/your-repo
curl https://api.github.com
claude "your question"
```

#### Option 3: Persistent in Shell Config

Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Load Klaus Proxy SSL/TLS configuration
[ -f ~/.klaus-proxy/klaus-env.sh ] && source ~/.klaus-proxy/klaus-env.sh

# Set proxy for HTTPS connections
export HTTPS_PROXY=http://127.0.0.1:8899
```

Then reload:
```bash
exec $SHELL
```

### Usage Examples

**Git Clone (HTTPS)**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

git clone https://github.com/anthropics/anthropic-cli.git
# ✅ Works without certificate errors
```

**Git Push with Proxy**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

git push origin main
# ✅ All HTTPS git operations work
```

**Curl (HTTPS)**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

curl https://api.github.com
# ✅ Proxy's certificate is trusted automatically
```

**Python Requests**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

python -c "import requests; print(requests.get('https://api.github.com').status_code)"
# ✅ REQUESTS_CA_BUNDLE is set automatically
```

**Node.js Tools**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

# NODE_EXTRA_CA_CERTS is exported by klaus-env.sh
npm install
# ✅ Works through proxy
```

### What Gets Configured

| Tool | Variable | Configured | Status |
|------|----------|-----------|--------|
| **git** | `GIT_SSL_CAINFO` | ✅ Auto | Works |
| **curl** | `CURL_CA_BUNDLE` | ✅ Auto | Works |
| **OpenSSL** | `SSL_CERT_FILE` | ✅ Auto | Works |
| **Python** | `REQUESTS_CA_BUNDLE` | ✅ Auto | Works |
| **Node.js / Claude Code** | `NODE_EXTRA_CA_CERTS` | ✅ Auto | Works |

### Disable Auto-Startup (If Needed)

If you enabled auto-startup but want to disable it:

1. Remove the Klaus Proxy hook from your shell config:
   - Edit `~/.zshrc` (or `~/.bashrc`)
   - Find the section: `🔐 Klaus Proxy Local — Auto-startup`
   - Delete those lines
   - Save and reload: `exec $SHELL`

2. Or keep the hook but manually start/stop the proxy:
   ```bash
   # Start manually when needed
   claude-proxy
   ```

### Troubleshooting

**"Still getting TLS handshake errors?"**

1. Ensure environment variables are loaded:
   ```bash
   source ~/.klaus-proxy/klaus-env.sh
   env | grep SSL
   # Should show: GIT_SSL_CAINFO, CURL_CA_BUNDLE, SSL_CERT_FILE (→ ~/.klaus-proxy/ca-bundle.pem)
   ```

2. Verify certificate exists:
   ```bash
   file ~/.mitmproxy/mitmproxy-ca-cert.pem
   # Should be: PEM certificate
   ```

3. Check proxy is running:
   ```bash
   pgrep -f mitmdump
   # Should show a PID
   ```

4. Test with verbose output:
   ```bash
   GIT_TRACE=1 git ls-remote https://github.com/anthropics/anthropic-cli.git
   # Should succeed without SSL errors
   ```

---

## ✨ What's New in v0.3.2

### 🐛 Critical Bugs Fixed

| Issue | Before | After |
|-------|--------|-------|
| **Captures location** | `/repo/captures/` ❌ | `~/.klaus-proxy/captures/` ✅ |
| **Log colors** | Disabled (no colors) ❌ | Full ANSI support ✅ |
| **Ctrl+C response** | 5 second hang ❌ | Instant (<100ms) ✅ |

### 🔧 Changes

1. **Captures Migration**
   - All scripts now use `~/.klaus-proxy/captures/` by default
   - Auto-migrates existing `config.json` on startup
   - 13 files updated (capture, analyze, verify, audit scripts)

2. **ANSI Colors Restored**
   - Removed `subprocess.PIPE` that forced mitmproxy to disable colors
   - mitmproxy now inherits parent TTY → detects terminal → enables colors natively
   - Logs show with full color support (green requests, red errors)

3. **Instant Ctrl+C**
   - Removed log reader thread holding file descriptor
   - Process exits in <100ms (was 5 seconds)
   - No hanging on shutdown

### 📖 Documentation

- **[RELEASE_v0.3.2_NOTES.md](./docs/RELEASE_v0.3.2_NOTES.md)** — Complete bugfix details + testing results

### ✅ Backward Compatibility

- ✅ Fully compatible with v0.3.1 and earlier
- ✅ Auto-migrates old `config.json` paths
- ✅ No breaking changes to API or scripts

[📖 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md)

---

## ✨ What's New in v0.3.1

### 🆕 New Commands

| Command | Purpose | Usage |
|---------|---------|-------|
| **`klaus-audit-payloads`** | Audit all captured payloads | `klaus-audit-payloads` |
| **`klaus-fix-pseudonymization`** | Diagnose pseudonymization issues | `klaus-fix-pseudonymization --show-payloads` |

### 🆕 New Features

1. **Automatic Payload Auditing**
   - Executive summary with security assessment
   - Pseudonymization effectiveness metrics
   - Secret redaction verification
   - Breakdown by HTTP method, host, status code
   - CSV export for compliance
   - Security rating: EXCELLENT / GOOD / NEEDS REVIEW

2. **Pseudonymization Diagnostics**
   - Identifies why payloads aren't pseudonymized
   - Shows non-pseudonymized payloads with details
   - Reviews configuration (patterns, SALT, enabled flag)
   - Provides actionable remediation steps
   - Distinguishes safe-to-skip hosts (monitoring) vs. critical (APIs)

3. **SSL/TLS Auto-Configuration**
   - Auto-generates `~/.klaus-proxy/klaus-env.sh`
   - Exports GIT_SSL_CAINFO, CURL_CA_BUNDLE, SSL_CERT_FILE
   - Shell hook auto-loads variables on startup
   - Fixes "Client TLS handshake failed" errors
   - Works with git, curl, Python, Node.js

### 📖 New Documentation

- **[AUDIT_ALL_PAYLOADS.md](./docs/AUDIT_ALL_PAYLOADS.md)** — Complete audit guide (400+ lines)
- **[FIX_PSEUDONYMIZATION.md](./docs/FIX_PSEUDONYMIZATION.md)** — Remediation guide (500+ lines)
- SSL/TLS setup in README with examples for git, curl, Python, Node.js

### 🔧 Improvements

- Capture directory auto-detection (project root or home directory)
- Beautiful unicode-boxed output with status indicators
- Comprehensive error handling and recommendations
- Decision matrix for quick host classification

---

## 📦 Releases

### v0.5.2 — Carpetas de proyectos protegidas fuera de las rutas y vault limpio ✅
- 🗂️ Los nombres de carpeta de proyectos se protegen también fuera de una ruta: `<carpeta>.md`, árboles de directorios y rutas con guiones (#93)
- 🧹 Los patrones ignoran marcadores, puntuación y nombres genéricos; `pseudo_pattern_ignore` y `scripts/prune_vault.py` para limpiar el vault (#92)
- ✅ **666 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.5.2_NOTES.md)

### v0.5.1 — Avisos de prompt injection detallados y accionables ✅
- 🔐 Cada aviso del audit dashboard muestra origen, fuente, fragmento, captura e id; un texto reenviado cuenta una vez (#86)
- 🧭 Indicaciones a seguir y `klaus-audit-dashboard --mark-reviewed` para los falsos positivos (#88)
- 🐛 El repo ya no dispara su propio detector; rutas largas y `</script>` corregidos (#86, #88)
- ✅ **634 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.5.1_NOTES.md)

### v0.5.0 — Protección de cualquier proyecto, guardián fail-closed e histórico del dashboard ✅
- 🛡️ **Org/repo y carpetas de proyectos protegidos** sin configurar nada: aprendidos de cada petición, `pseudo_patterns` y usuarios en rutas (#42, #61, #63, #65)
- 🚧 **Guardián fail-closed + snapshot inmutable de addons**: un `checkout` ya no cambia ni rompe el pseudonimizador en marcha (#71)
- 🔁 **Seudónimos partidos en streaming** restaurados por bloque (#67)
- 📝 **Logs en disco** (`~/.klaus-proxy/logs/proxy.log`) (#55)
- 📂 **Histórico del audit dashboard** con selector y cambios respecto al anterior (#77)
- ⚡ `anthropic-pair-verify` 7× más rápido y sin falsos positivos (#59, #73)
- ✅ **625 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.5.0_NOTES.md)

### v0.4.0 — Instalación completa, dashboard de auditoría y proxy solo en localhost ✅
- 📦 Instalador `install.sh` con venv global (#33)
- 📊 Dashboard HTML de auditoría (#35)
- 🔒 El proxy solo escucha en `127.0.0.1` (#47)

[📖 Release Notes](./docs/RELEASE_v0.4.0_NOTES.md)

### v0.3.2 — Critical Bugfixes ✅
- ✅ **Captures directory migration** — All files now stored in `~/.klaus-proxy/captures/` (not repo)
- ✅ **ANSI colors restored** — Full color support in mitmproxy logs (green requests, red errors)
- ✅ **Instant Ctrl+C** — Response time <100ms (was 5 seconds)
- ✅ **Auto-config migration** — Existing `config.json` auto-updated on startup
- ✅ **13 scripts updated** — All capture, analyze, verify, audit tools use user-local paths
- ✅ **Fully backward compatible** — No breaking changes

[📖 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md) | [📋 What's New](#-whats-new-in-v032)

### v0.3.1 — Comprehensive Audit & Diagnostics System ✅
- 🔍 **Automatic payload audit** (`klaus-audit-payloads`) with summary, detailed, CSV export
- 🔧 **Pseudonymization diagnostics** (`klaus-fix-pseudonymization`) to identify & fix issues
- 🔐 **SSL/TLS auto-configuration** (GIT_SSL_CAINFO, CURL_CA_BUNDLE auto-exported)
- 📊 **Security assessment** with actionable recommendations
- 📚 **Comprehensive documentation** (audit + remediation guides)
- ✅ **465/465 tests passing** + new features tested
- 🚀 **Zero-config SSL/TLS** for Git, curl, Python, Node.js

[📖 Release Notes](./docs/RELEASE_v0.3.1_NOTES.md)

### v0.3.0 — Complete Audit & Auto-Fix System ✅
- ✅ **465/465 tests passing** (fixed 23 failing)
- 🔍 **Multi-mode audit system** (stats, find-leaks, patterns, review)
- 📊 **Automated report generation** (timestamped, indexed)
- 🔧 **Automatic leak detection & fixing** (deterministic hashing)
- 🚀 **Complete workflow** (generate → detect → fix → verify)
- 📚 **6 comprehensive guides** (50+ pages)
- 🔐 **Auto-SALT generation** + zero-config setup

[📖 Release Notes](./docs/RELEASE_v0.3.0_NOTES.md)

### v0.2.0 — Sensitive Data Scanner ✅
- 🔍 Multi-tier secret detection (3 tiers independent)
- 📋 20 built-in patterns + custom pattern support
- ⚡ Interactive CLI review workflow
- 🔗 Vault integration with v0.1.0
- 🧪 65+ tests (100% passing)

Release notes no conservadas en `docs/`.

### v0.1.0 — Initial Release ✅
- 🔐 HTTPS proxy + pseudonymization
- 🚀 Zero-configuration setup
- 🛡️ Security hardening (3 critical fixes)
- 🔒 Bidirectional vault mapping

Release notes no conservadas en `docs/`.

**[🔗 Todas las releases](https://github.com/Ka0s-Klaus/klaus-proxy-local/releases)** · [CHANGELOG](./CHANGELOG.md)

---

## 📚 Documentación

> 🗺️ **Este README es el mapa.** Todas las referencias del proyecto parten de aquí. Si buscas algo y no está en esta tabla, probablemente aún no existe — crea una issue.

| Sección | Descripción | Enlace |
|---|---|---|
| 🏗️ **Arquitectura** | Diseño interno, componentes y flujos | [docs/architecture/](./docs/architecture/README.md) |
| 📖 **Guías** | Quick start, runbooks, troubleshooting | [docs/guides/](./docs/guides/README.md) |
| 📊 **Informes** | Audit dashboard, informes locales y notas de releases | [docs/reports/](./docs/reports/README.md) |
| 🗄️ **Archivo** | Documentos de versiones anteriores (no reflejan el estado actual) | [docs/archive/](./docs/archive/README.md) |
| 🧭 **Decisiones (ADRs)** | Decisiones técnicas y sus alternativas descartadas | [docs/decisions/](./docs/decisions/README.md) |

### ⚡ Accesos directos más usados

| Documento | Descripción |
|---|---|
| [⚡ Quick Start](./docs/QUICK_START.md) | Instalación y primer uso en 2 min |
| [🔎 Audit Quick Start](./docs/AUDIT_QUICK_START.md) | Primera auditoría en 5 min |
| [🌐 Audit Dashboard](./docs/reports/web/README.md) | Dashboard HTML interactivo de auditoría |
| [🛠️ Troubleshooting](./docs/TROUBLESHOOTING.md) | Solución de problemas comunes |
| [🔌 Runbook técnico](./docs/anthropic-audit-proxy.md) | Referencia completa del proxy |
| [🚀 Release v0.5.2](./docs/RELEASE_v0.5.2_NOTES.md) | Notas de la última release |

---

## 🔬 Desarrollo (desde el repositorio)

```bash
# Clonar
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Setup de desarrollo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Correr tests
pytest -v

# Linting
ruff check .
black --check .

# Ejecutar el proxy (manual, sin instalación)
ANTHROPIC_PSEUDO_SALT=your-salt mitmdump \
  -s src/anthropic_payload_pseudonymize.py \
  -s src/anthropic_payload_capture.py --listen-host 127.0.0.1 -p 8899
```

---

## ⚙️ Configuración (variables de entorno)

### Proxy & Auditoría

| Variable | Efecto | Por defecto |
| --- | --- | --- |
| `ANTHROPIC_CAPTURE_HOSTS` | Hosts a auditar (coma-separada) | `api.anthropic.com,llm.tools.cloud.customer1.es` |
| `ANTHROPIC_CAPTURE_DIR` | Directorio base de capturas | `captures/` |
| `ANTHROPIC_PSEUDO_ENABLE` | Interruptor de la seudonimización | `1` |
| `ANTHROPIC_PSEUDO_WORD_LITERALS` | Literales con frontera de palabra (org/proj IDs) | — |
| `ANTHROPIC_PSEUDO_PROJECT_ROOT` | Raíz del proyecto **auditado** (palanca de rutas + git) | `cwd` del proceso |
| `ANTHROPIC_PSEUDO_VAULT` | Ruta del vault de seudonimización | `captures/.pseudonym_vault.json` |
| `KLAUS_LOG_DIR` | Directorio del log del proxy (`proxy.log`) | `~/.klaus-proxy/logs/` |
| `ANTHROPIC_PSEUDO_USER_DIRS` | Patrón integrado de usuarios en `/Users/<u>` y `/home/<u>` | `1` |

### Protección de org/repo

El org y el nombre del repo se pseudonimizan como *word-literals*. Cada vez que `claude-proxy` arranca **dentro de un repo git**, añade el org/repo de su `origin` a `pseudo_word_literals` en `~/.klaus-proxy/config.json`. Desde ese momento quedan protegidos aunque el proxy se arranque desde otro directorio.

- El dashboard de arranque muestra la lista protegida (`🛡️  Protected org/repo`) y avisa en amarillo si está vacía.
- Además, el proxy **aprende el org/repo de cada petición**: Claude Code envía los remotes de git del proyecto en el que trabaja, y el pseudonimizador los protege antes de reescribir esa misma petición y los guarda en `pseudo_word_literals`. En el log aparece `🛡️ org/repo nuevo protegido: …`.
- Los nombres genéricos (`docs`, `api`, `test`, `app`…) no se aprenden, porque se pseudonimizaría esa palabra en todo el texto. Se avisa una vez en el log; si son privados, añádelos a mano.
- ⚠️ Ese campo es interno de Claude Code y **depende del modo de permisos** (verificado con Claude Code 2.1.312):

  | Modo | ¿Envía los remotes? | ¿Se aprende el org/repo? |
  | --- | --- | --- |
  | `auto` | Sí | Sí |
  | `plan` | Sí, desde la 2ª petición | Sí, desde la 2ª petición |
  | `manual`, `acceptEdits`, `dontAsk` | No | No |

  En `plan`, y en `auto` mientras Claude Code aún no ha leído el estado de git, la **primera** petición de un repo nuevo sale antes de aprenderlo.

- **Para proteger un repo en cualquier modo**, haz que esté en `pseudo_word_literals` antes de trabajar en él. Puedes arrancar `claude-proxy` una vez dentro del repo, abrir una sesión en `auto` o `plan` o añadir sus tokens a mano. El dashboard de arranque muestra la lista.

### Patrones (`pseudo_patterns`)

Para datos con forma reconocible que no son un literal fijo. Se aplican **antes** que el resto de reglas, sobre el texto real, y son reversibles: el mismo valor siempre da el mismo seudónimo.

```json
"pseudo_patterns": [
  {"pattern": "/Users/u/proyectos/([^/\\s]+)", "replacement_prefix": "dir"},
  {"pattern": "CLIENTE-\\d{4}", "replacement_prefix": "cli"}
]
```

- Si el regex tiene grupos, **solo se pseudonimiza el grupo 1**: `/Users/u/proyectos/acme/src` → `…/proyectos/dir_1a2b3c4d/src`. Sin grupos, la coincidencia entera.
- `replacement_prefix`: solo minúsculas (`[a-z]+`); por defecto `pat`. Una entrada inválida se ignora.
- **Automático:** al arrancar dentro de un repo, `claude-proxy` añade un patrón para la carpeta que lo contiene (p. ej. `~/proyectos`). Así los nombres de **todos** los proyectos de esa carpeta se protegen en las rutas, aunque no tengan remote o aparezcan truncados. No se añade si esa carpeta es el home.
- **Integrado:** el nombre de usuario de cualquier ruta `/Users/<u>/…` o `/home/<u>/…`, aunque sea de otra máquina (p. ej. un `@import` en un `CLAUDE.md`). Se desactiva con `ANTHROPIC_PSEUDO_USER_DIRS=0`.
- **Fuera de una ruta** (#93): un nombre de carpeta que ya está en el vault se sustituye también suelto, como palabra completa y con el mismo seudónimo (`<carpeta>.md`, la raíz de un árbol, rutas codificadas con guiones `-Users-u-proyectos-<dir>-…`). Solo con 5 caracteres o más y si no es genérico (`scripts`, `tests`…). Se desactiva con `ANTHROPIC_PSEUDO_DIR_WORDS=0`.
- **Valores ignorados** (#92): marcadores (`…`, `{user}`, `$USER`…), puntuación, un solo carácter y nombres genéricos de usuario (`Shared`, `root`…) no se pseudonimizan. `pseudo_pattern_ignore` en `config.json` excluye valores concretos, y `scripts/prune_vault.py` los quita del vault (con el proxy parado).
- `anthropic-pair-verify` comprueba cada patrón por contexto (capa `[pattern]`).

### Addons: snapshot inmutable y guardián

mitmproxy recarga los scripts `-s` cada vez que cambian en disco. Para que un `git checkout`, un `stash` o una edición en el clon no cambien ni rompan el pseudonimizador de un proxy en marcha:

- `claude-proxy` copia los addons a `~/.klaus-proxy/addons/<hash>/` (de solo lectura, con `VERSION.json`) y lanza `mitmdump` desde esa copia. **Los cambios en el clon solo se aplican al reiniciar `claude-proxy`.** Al arrancar se muestra `🧩 Addons: <commit> (snapshot …)`, que también queda en el log.
- El addon `klaus_pseudo_guard.py` se carga el último y **bloquea con un 502 cualquier petición que el pseudonimizador no haya procesado**, por ejemplo si no llegó a cargar. En el log aparece `[klaus-guard] BLOQUEADA …`.
- Los snapshots no se borran solos (pesan unos pocos KB). Puedes borrar los antiguos con el proxy parado.

### Logs del proxy

Además de verse en la terminal, todo lo que registra el proxy se guarda en `~/.klaus-proxy/logs/proxy.log`. Lo escribe el addon `src/klaus_file_log.py`, que `claude-proxy` carga automáticamente:

- Arranque, avisos y errores de mitmproxy y de los addons de seudonimización y captura.
- Una línea por petición: `POST api.anthropic.com/v1/messages → 200 1234B 850ms`.
- Rotación a 5 MB × 5 ficheros (`proxy.log.1` … `proxy.log.5`), sin colores ANSI y con permisos `0600`.

```bash
tail -f ~/.klaus-proxy/logs/proxy.log
```

### SSL/TLS (Auto-Exportadas)

| Variable | Efecto | Status |
| --- | --- | --- |
| `GIT_SSL_CAINFO` | CAs del sistema + CA del proxy para `git` | ✅ Auto-generada |
| `CURL_CA_BUNDLE` | CAs del sistema + CA del proxy para `curl` | ✅ Auto-generada |
| `SSL_CERT_FILE` | CAs del sistema + CA del proxy para OpenSSL | ✅ Auto-generada |
| `REQUESTS_CA_BUNDLE` | CAs del sistema + CA del proxy para Python | ✅ Auto-generada |
| `NODE_EXTRA_CA_CERTS` | Certificado CA para Node.js | ✅ Auto-generada |
| `HTTPS_PROXY` | Dirección del proxy (usuario) | Manual: `http://127.0.0.1:8899` |

> ℹ️ Las variables SSL/TLS se generan automáticamente en `~/.klaus-proxy/klaus-env.sh` cuando inicia `claude-proxy`. Usa `source ~/.klaus-proxy/klaus-env.sh` para cargarlas.

> 📖 Tabla completa de flags en [`docs/anthropic-audit-proxy.md`](./docs/anthropic-audit-proxy.md).

---

## 🗂️ Estructura

```text
klaus-proxy-local/
├── src/         # addons de mitmproxy + CLIs (capture, pseudonymize, guard, file log, verify, pair-verify…)
├── scripts/     # generador del audit dashboard, wrappers de shell
├── tests/       # suite pytest — pytest -q
├── docs/        # runbook, guías, informes y ADRs
└── informes/    # 🔒 DATOS SENSIBLES (gitignored): histórico del audit dashboard e informes Markdown

~/.klaus-proxy/  # fuera del repo
├── config.json  # salt, hosts, pseudo_literals, pseudo_word_literals, pseudo_patterns (0600)
├── captures/    # 🔒 original/, sent/, .pseudonym_vault.json
├── logs/        # proxy.log (rotado)
└── addons/      # snapshots inmutables de los addons que ejecuta mitmdump
```

> ⚠️ **Las capturas, el vault e `informes/` nunca se versionan.** Contienen prompts,
> contenido real de ficheros y el mapa real↔seudónimo. Viven en `~/.klaus-proxy/` o
> están en `.gitignore`, y jamás deben subir a este repositorio público.

---

Ver sección anterior: [📚 Documentación](#-documentación)

---

## 🧪 Tests

```bash
pytest -q          # 666 passed, 3 skipped (v0.5.2)
                   # Includes: capture, pseudonymize, guard, verify, audit, dashboard, vault
```

### Test Coverage
- ✅ **666 tests passing** en Python 3.10–3.13 (CI)
- ✅ Security tests for vault + pseudonymization
- ✅ Integration tests for audit workflows
- ✅ Unit tests for all components
- ✅ CI/CD validation ready

---

## 🤝 Contribuir

¿Quieres contribuir? Lee la [guía de contribución](./CONTRIBUTING.md) y el [código de conducta](./CODE_OF_CONDUCT.md).

---

## 🔒 Seguridad

Si encuentras una vulnerabilidad de seguridad, sigue el proceso descrito en [SECURITY.md](./SECURITY.md). **No abras una issue pública.** Nunca subas el contenido de `captures/` ni el vault: son datos sensibles reales.

---

## 📄 Licencia

MIT © [Ka0s-Klaus](https://github.com/Ka0s-Klaus)
