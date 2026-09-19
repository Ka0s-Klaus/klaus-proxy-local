# 🔌 Klaus Proxy Local

> **Proxy local de auditoría, pseudonimización y detección automática de fugas** — intercepta,
> audita y pseudonimiza el tráfico que Claude Code envía a la API de Anthropic (y al
> gateway LLM corporativo), con análisis multi-modo y corrección automática de fugas.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://python.org)
[![Version](https://img.shields.io/badge/version-0.3.1-green)](./docs/RELEASE_v0.3.1_NOTES.md)
[![Tests](https://img.shields.io/badge/tests-465%2F465-brightgreen)](./docs/FIX_SUMMARY.md)
[![Status](https://img.shields.io/badge/status-Production%20Ready-success)](./docs/RELEASE_v0.3.1_NOTES.md)
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
- Un proxy `mitmproxy` local (`mitmdump -p 8899`) con dos addons Python en
  [`src/`](./src): `anthropic_payload_pseudonymize.py` (reescribe/revierte) y
  `anthropic_payload_capture.py` (graba la evidencia).
- Claude Code se enruta por el proxy vía `HTTPS_PROXY` + `NODE_EXTRA_CA_CERTS`, de
  forma **fail-closed** (si el proxy no escucha, `claude` aborta y no deja salir
  tráfico sin auditar).
- La evidencia cae en [`captures/`](./captures) como pares espejo `original/` (datos
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

## 🚀 Inicio rápido (v0.3.1)

```bash
# Instalar
pip install Klaus-proxy-local==0.3.1

# Terminal 1: arrancar el proxy (auto-genera config + certs + SALT + variables SSL/TLS)
claude-proxy

# Terminal 2: usar Claude Code (SSL/TLS configurado automáticamente)
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude "tu pregunta"

# Terminal 3: auditar payloads (NUEVO en v0.3.1)
klaus-audit-payloads
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

✨ **Eso es todo.** Todo es automático: configuración, certificados, SALT, auditoría y corrección de fugas.

---

## 🔐 SSL/TLS Certificate Trust (v0.3.0+)

Klaus Proxy now **automatically configures** SSL/TLS certificate trust for all your tools. No more "Client TLS handshake failed" errors.

### How It Works

When you start `claude-proxy`, it automatically generates `~/.klaus-proxy/klaus-env.sh` containing:

```bash
export GIT_SSL_CAINFO="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
export CURL_CA_BUNDLE="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
export SSL_CERT_FILE="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
export REQUESTS_CA_BUNDLE="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
```

This tells your tools (git, curl, Python, Node.js) to trust the proxy's certificate automatically.

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

# NODE_EXTRA_CA_CERTS is set automatically by proxy launcher
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
| **Node.js** | `NODE_EXTRA_CA_CERTS` | ✅ By proxy | Works |

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
   # Should show: GIT_SSL_CAINFO, CURL_CA_BUNDLE, SSL_CERT_FILE
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

### v0.3.1 — Comprehensive Audit & Diagnostics System ✅
- 🔍 **Automatic payload audit** (`klaus-audit-payloads`) with summary, detailed, CSV export
- 🔧 **Pseudonymization diagnostics** (`klaus-fix-pseudonymization`) to identify & fix issues
- 🔐 **SSL/TLS auto-configuration** (GIT_SSL_CAINFO, CURL_CA_BUNDLE auto-exported)
- 📊 **Security assessment** with actionable recommendations
- 📚 **Comprehensive documentation** (audit + remediation guides)
- ✅ **465/465 tests passing** + new features tested
- 🚀 **Zero-config SSL/TLS** for Git, curl, Python, Node.js

[📖 Release Notes](./docs/RELEASE_v0.3.1_NOTES.md) | [📋 What's New](#-whats-new-in-v031)

### v0.3.0 — Complete Audit & Auto-Fix System ✅
- ✅ **465/465 tests passing** (fixed 23 failing)
- 🔍 **Multi-mode audit system** (stats, find-leaks, patterns, review)
- 📊 **Automated report generation** (timestamped, indexed)
- 🔧 **Automatic leak detection & fixing** (deterministic hashing)
- 🚀 **Complete workflow** (generate → detect → fix → verify)
- 📚 **6 comprehensive guides** (50+ pages)
- 🔐 **Auto-SALT generation** + zero-config setup

[📖 Release Notes](./docs/RELEASE_v0.3.0_NOTES.md) | [📋 Full Details](./docs/FIX_SUMMARY.md)

### v0.2.0 — Sensitive Data Scanner ✅
- 🔍 Multi-tier secret detection (3 tiers independent)
- 📋 20 built-in patterns + custom pattern support
- ⚡ Interactive CLI review workflow
- 🔗 Vault integration with v0.1.0
- 🧪 65+ tests (100% passing)

[📖 Release Notes](./docs/RELEASE_v0.2.0.md)

### v0.1.0 — Initial Release ✅
- 🔐 HTTPS proxy + pseudonymization
- 🚀 Zero-configuration setup
- 🛡️ Security hardening (3 critical fixes)
- 🔒 Bidirectional vault mapping

[📖 Release Notes](./docs/RELEASE_v0.1.0.md)

**[🔗 All Releases](./docs/RELEASES.md)**

---

## 📚 Documentación

### 🎯 Para Nuevos Usuarios (Empieza Aquí)

| Guía | Tiempo | Descripción |
|------|--------|-------------|
| **[QUICK_START.md](./docs/QUICK_START.md)** | 2 min | Instalación y uso básico |
| **SSL/TLS Setup** (README) | 3 min | Configurar certificados para Git/curl/tools |
| **[AUDIT_QUICK_START.md](./docs/AUDIT_QUICK_START.md)** | 5 min | Auditoría rápida de payloads |
| **[THREAT_MODEL.md](./docs/THREAT_MODEL.md)** | 10 min | Qué protegemos y qué no |

### 🔧 Para Auditores (v0.3.0)

| Guía | Descripción |
|------|-------------|
| **[AUDIT_CAPTURES_GUIDE.md](./docs/AUDIT_CAPTURES_GUIDE.md)** | Análisis multi-modo completo (20+ páginas) |
| **[GENERATE_REPORTS_GUIDE.md](./docs/GENERATE_REPORTS_GUIDE.md)** | Generación automática de reportes |
| **[AUTO_FIX_LEAKS_GUIDE.md](./docs/AUTO_FIX_LEAKS_GUIDE.md)** | Detección y corrección automática de fugas |

### 📋 Para Releases

| Tema | Documento |
|------|-----------|
| **v0.3.0 (Current)** | [RELEASE_v0.3.0_NOTES.md](./docs/RELEASE_v0.3.0_NOTES.md) |
| **v0.2.0** | [RELEASE_v0.2.0.md](./docs/RELEASE_v0.2.0.md) |
| **v0.1.0** | [RELEASE_v0.1.0.md](./docs/RELEASE_v0.1.0.md) |
| **All Releases** | [RELEASES.md](./docs/RELEASES.md) |

### 🏗️ Para Desarrolladores

| Tema | Documento |
|------|-----------|
| **Arquitectura** | [architecture.md](./docs/architecture.md) |
| **Setup Completo** | [setup.md](./docs/setup.md) |
| **Scanner (v0.2.0)** | [FASE2_SENSITIVE_DATA_SCANNER.md](./docs/FASE2_SENSITIVE_DATA_SCANNER.md) |
| **Patrones Personalizados** | [FASE2_CUSTOM_PATTERNS.md](./docs/FASE2_CUSTOM_PATTERNS.md) |
| **Hardening Seguridad** | [SECURITY_HARDENING.md](./docs/SECURITY_HARDENING.md) |
| **Runbook Detallado** | [anthropic-audit-proxy.md](./docs/anthropic-audit-proxy.md) |
| **Índice Completo** | [INDEX.md](./docs/INDEX.md) |

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
  -s src/anthropic_payload_capture.py -p 8899
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

### SSL/TLS (Auto-Exportadas)

| Variable | Efecto | Status |
| --- | --- | --- |
| `GIT_SSL_CAINFO` | Certificado CA para `git` | ✅ Auto-generada |
| `CURL_CA_BUNDLE` | Certificado CA para `curl` | ✅ Auto-generada |
| `SSL_CERT_FILE` | Certificado CA para OpenSSL | ✅ Auto-generada |
| `REQUESTS_CA_BUNDLE` | Certificado CA para Python | ✅ Auto-generada |
| `NODE_EXTRA_CA_CERTS` | Certificado CA para Node.js | ✅ Auto-generada |
| `HTTPS_PROXY` | Dirección del proxy (usuario) | Manual: `http://127.0.0.1:8899` |

> ℹ️ Las variables SSL/TLS se generan automáticamente en `~/.klaus-proxy/klaus-env.sh` cuando inicia `claude-proxy`. Usa `source ~/.klaus-proxy/klaus-env.sh` para cargarlas.

> 📖 Tabla completa de flags en [`docs/anthropic-audit-proxy.md`](./docs/anthropic-audit-proxy.md).

---

## 🗂️ Estructura

```text
klaus-proxy-local/
├── src/         # addons de mitmproxy + CLIs (capture, pseudonymize, verify, pair-verify, analyze, cleanup)
├── tests/       # suite pytest (158 tests) — pytest -q
├── docs/        # runbook + MANIFIESTO + MANUAL + plantilla LaunchAgent
└── captures/    # 🔒 DATOS SENSIBLES (gitignored): original/, sent/, .pseudonym_vault.json
```

> ⚠️ **`captures/` nunca se versiona.** Contiene prompts, contenido real de ficheros y
> el vault real↔seudónimo. Está en `.gitignore` y jamás debe subir a este repositorio
> público.

---

Ver sección anterior: [📚 Documentación](#-documentación)

---

## 🧪 Tests

```bash
pytest -q          # 465 tests passing (all passing ✅)
                   # Includes: capture, pseudonymize, verify, audit, vault management
```

### Test Coverage
- ✅ **465 tests passing** (100%)
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
