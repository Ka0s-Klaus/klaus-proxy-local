---
tags: [proyecto/klaus-proxy-local, tipo/guia, proxy/instalacion]
---

# 🔌 Klaus Proxy Local

> **Proxy local de auditoría, pseudonimización y detección automática de fugas** — intercepta,
> audita y pseudonimiza el tráfico que Claude Code envía a la API de Anthropic (y al
> gateway LLM corporativo), con análisis multi-modo y corrección automática de fugas.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Version](https://img.shields.io/badge/version-0.10.0-green)](./docs/RELEASE_v0.10.0_NOTES.md)
[![Tests](https://img.shields.io/badge/tests-929%20passed-brightgreen)](./.github/workflows/ci.yml)
[![Status](https://img.shields.io/badge/status-Production%20Ready-success)](./docs/RELEASE_v0.10.0_NOTES.md)
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
  con cinco addons Python de [`src/`](./src), cargados desde un snapshot inmutable:
  `klaus_file_log.py` (log en disco), `klaus_tls_passthrough.py` (solo descifra lo que se
  audita; el resto va en túnel), `anthropic_payload_pseudonymize.py` (reescribe/revierte),
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

## 🚀 Inicio rápido (v0.11.0)

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

# Terminal 3: ¿qué datos sensibles hay y salen protegidos?
klaus-scan ~/proyectos/mi-repo   # detecta secretos y nombres de negocio; apruebas los que proteger
#   (tras aprobar, reinicia claude-proxy para que se apliquen)
klaus-leak-report --open         # por proyecto: qué no cubre el proxy, qué ha salido y % de cobertura
klaus-leak-report --drill        # simulacro: comprueba que un «0 fugas» es fiable
klaus-startup-scan --dry-run     # qué hallazgos añadiría el escaneo de inicio al vault (sin escribir)
klaus-trazas                    # estadísticas e integridad de trazas de IA (logs/trazas, solo lectura)
klaus-install-wrappers           # reinstala los wrappers claude-with-proxy (lo hace klaus-setup)
klaus-install-python             # comprueba Python 3.13 y lo instala si falta (manual)

# Terminal 3 alternativo: auditar payloads (CLI)
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

# Retención de capturas (30 días por defecto; capture_retention_days en config.json)
klaus-prune-captures --dry-run

# Tras clonar un repo: proteger su org/repo (luego reinicia claude-proxy)
klaus-scan-repos --dry-run
```

**Opcional, sin terminal 1 ni `export`:**

- **`klaus-setup`** añade a tu `~/.zshrc` (o `~/.bashrc`, fish) un bloque que, en cada terminal nueva, carga `klaus-env.sh`, arranca `claude-proxy` en segundo plano si no está en marcha y exporta `HTTPS_PROXY`. Basta con `claude`. Ver [opciones de configuración](#opciones-de-configuración).
- **`claude-with-proxy`** (lo instala `install.sh`): lanza `claude` por el proxy solo si está escuchando; si no, no lo ejecuta.

> ⚠️ La instalación es *editable*: el venv apunta al clon del repositorio. **No borres
> ni muevas esa carpeta.** Para actualizar: `git pull && ./install.sh`.

✨ **Eso es todo.** `install.sh` y `claude-proxy` generan la configuración, la SALT y los certificados, y protegen el org/repo y la carpeta de proyectos desde el primer arranque. Para proteger un valor propio (un cliente, un código interno), añádelo a `pseudo_word_literals` o `pseudo_literals` de `~/.klaus-proxy/config.json` y reinicia el proxy ([guía de uso](./docs/USER_GUIDE.md)).

---

## 🔐 Terminales y certificados

Cada vez que arranca, `claude-proxy` genera `~/.klaus-proxy/klaus-env.sh`, que hace que git, curl, Python y Node confíen en la CA del proxy:

```bash
export GIT_SSL_CAINFO="$HOME/.klaus-proxy/ca-bundle.pem"
export CURL_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export SSL_CERT_FILE="$HOME/.klaus-proxy/ca-bundle.pem"
export REQUESTS_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export NODE_EXTRA_CA_CERTS="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
```

`ca-bundle.pem` = CAs del sistema + CA del proxy, y se regenera en cada arranque. Las cuatro primeras variables **sustituyen** el almacén de confianza; por eso no apuntan solo a la CA del proxy, o romperían el HTTPS que no pasa por él. `NODE_EXTRA_CA_CERTS` solo **añade** al almacén de Node, así que usa la CA del proxy directamente.

### Opciones de configuración

| Opción | Cómo | Qué hace |
| --- | --- | --- |
| ⭐ **`klaus-setup`** | `klaus-setup` (responde `y`) y `exec $SHELL` | Añade a tu shell (bash, zsh o fish) un bloque entre `# >>> Klaus Proxy Local (klaus-setup) >>>` y `# <<< … <<<`. En cada terminal nueva: carga `klaus-env.sh`, arranca `claude-proxy` en segundo plano si no está en marcha (log en `~/.klaus-proxy/logs/autostart.log`) y exporta `HTTPS_PROXY` y `NO_PROXY` (loopback directo). Basta con `claude` |
| 🎯 **`claude-with-proxy`** | `claude-with-proxy` (mismos argumentos que `claude`) | Lo instala `install.sh`. Carga `klaus-env.sh` y lanza `claude` por el proxy **solo si está escuchando**; si no, no lo ejecuta (fail-closed). No arranca el proxy |
| ✋ **Manual** | `source ~/.klaus-proxy/klaus-env.sh` y `export HTTPS_PROXY=http://127.0.0.1:8899` | Para una terminal concreta, con `claude-proxy` arrancado en otra |

Lo que conviene saber de `klaus-setup`:

- **Todo el HTTPS de la terminal pasa por el proxy** (pip, git, curl, brew…) y cada conexión queda en `~/.klaus-proxy/logs/proxy.log`. **Solo se descifra lo que se audita:** `api.anthropic.com`, los `hosts` de `config.json` y el host de `ANTHROPIC_BASE_URL`, que se descifran, seudonimizan y capturan; y los `capture_only_hosts`, que se descifran y capturan **sin** seudonimizar. Es para tráfico que dejaría de funcionar con seudónimos, como los conectores MCP de claude.ai. El resto va en túnel con el certificado real del servidor, así que ninguna herramienta da errores de certificado; el log apunta `TÚNEL host:puerto` (host y hora, no contenido).
- **Un gateway que no sea de Anthropic tiene que estar en `hosts`** de `config.json` (o en `ANTHROPIC_BASE_URL`). Si no, iría en túnel sin seudonimizar.
- **`klaus-off` / `klaus-on`** quitan o restauran `HTTPS_PROXY` en una terminal. `"intercept_all": true` en `config.json` (o `KLAUS_INTERCEPT_ALL=1`) lo descifra todo.
- El proxy se arranca desde la **primera** terminal que abres, y protege el org/repo de esa carpeta y los de toda la carpeta de proyectos (#134). Tarda unos segundos en escuchar.
- **Para desactivarlo**, borra el bloque marcado de tu configuración de shell. Si vienes de una versión antigua, volver a ejecutar `klaus-setup` sustituye el bloque anterior («Auto-startup (FASE 1.5)»).

¿Errores de certificado? Comprueba que `env | grep SSL` muestra `~/.klaus-proxy/ca-bundle.pem` y que el proxy está en marcha (`pgrep -f mitmdump`). Más casos en [Troubleshooting](./docs/TROUBLESHOOTING.md).

> 🗄️ Las secciones de la época v0.3 (certificados en inglés y «What's New in v0.3.1 / v0.3.2») están en el [archivo histórico](./docs/archive/README_v0.3_SECCIONES.md).

---

## 📦 Releases

### v0.11.0 — Trazas de IA y arranque robusto ✅
- 🧾 `klaus-trazas`: estadísticas e integridad de las trazas de ejecuciones con IA, según [la especificación](./docs/trazabilidad.md) (#206, #207)
- 🧩 Instrumentación de trazas (`start_trace`, `record_event`, `end_trace`), esquema JSON y filtro de redacción (#210, #211)
- 🔌 `claude-proxy` libera el puerto 8899 si lo ocupa un proxy previo (#202, #203)
- 🔗 `install.sh` enlaza todos los comandos de `pyproject.toml` (#208, #209)
- ✅ **929 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.11.0_NOTES.md)

### v0.10.0 — Hosts de proyecto bloqueados y klaus-alerts ✅
- 🔐 Un host de LLM definido solo en la configuración de un proyecto se bloquea hasta que lo apruebes en `config.json` (#193)
- 🖥️ `klaus-alerts`: interfaz para revisar los avisos del centinela (#189)
- 🛡️ Centinela de fugas y recarga en caliente de reglas (#187)
- ✅ **883 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.10.0_NOTES.md)

### v0.9.0 — Simulacro de fugas ✅
- 🧯 `klaus-leak-report --drill`: siembra fugas falsas en un directorio temporal y comprueba que el detector las ve y que el proxy las sustituye, para que un «0 fugas» sea fiable (#171)
- 📦 El paquete deja de anunciar Python 3.9, que nunca ha estado soportado (#175)
- ✅ **841 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.9.0_NOTES.md)

### v0.8.1 — Informe de fugas sin falsos positivos de palabra ✅
- 🕵️ `klaus-leak-report` y el verificador ya no cuentan como fuga una regla que solo aparece dentro de otra palabra, igual que el proxy (#158)
- 📦 Las releases solo construyen el paquete; ya no publican en PyPI (#165)
- 📖 Guía del flujo aprobar → reiniciar → informe y de cómo leer las fugas tras aprobar reglas (#159)
- ✅ **835 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.8.1_NOTES.md)

### v0.8.0 — Fugas y cobertura por proyecto ✅
- 🕵️ `klaus-leak-report`: qué datos sensibles tiene cada proyecto, cuáles no cubre el proxy, cuáles han salido y su % de cobertura; tarjeta en el dashboard (#146)
- 🔎 `klaus-scan` detecta nombres de negocio (clientes, dominios, IDs cloud) y su salida ya no revela valores (#140)
- 🔒 El proxy redacta las claves de Anthropic, OpenAI y Stripe, las contraseñas de conexiones y los Bearer, sin tocar el login (#148); un nombre tras `\b` ya no sale en claro (#142)
- ✅ **833 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.8.0_NOTES.md)

### v0.7.0 — Retención de capturas y todos tus repos protegidos al arrancar ✅
- ⚠️ 🧹 **Retención de capturas: 30 días por defecto.** Al primer arranque tras actualizar se borran los pares de más de 30 días (`capture_retention_days`, `0` = sin límite; `captures/archive/` no se toca) (#132)
- 🔒 `capture_originals: false`: solo se guarda `sent/`, sin datos reales en claro en disco (#132)
- 🛡️ `claude-proxy` protege al arrancar el org/repo de todos los repos de la carpeta de proyectos; `klaus-scan-repos` tras clonar (#134)
- 📊 Dashboard: tarjeta «Proyectos protegidos» (#136)
- ✅ **746 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.7.0_NOTES.md)

### v0.6.1 — Auditar sin pseudonimizar y descifrar solo lo que se audita ✅
- 🔍 `capture_only_hosts`: audita un host sin pseudonimizarlo, por ejemplo los conectores MCP de claude.ai (#125)
- 🔓 Solo se descifra lo que se audita: la renovación del token OAuth y las descargas de Claude Code van en túnel (#125)
- 📊 Dashboard: sección «Hosts no capturados» y tabla de hosts coherente con `config.json` (#123)
- 🐛 La captura lee `hosts` de `config.json` (#119); aviso si `config.json` no se puede leer (#121)
- ✅ **718 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.6.1_NOTES.md)

### v0.6.0 — Cada terminal por el proxy, sin errores de certificado ✅
- 🖥️ `klaus-setup` hace que cada terminal nueva arranque el proxy y exporte `HTTPS_PROXY`: basta con `claude`; `claude-with-proxy` lo instala `install.sh` (#105)
- 🔓 Solo se descifra la API del LLM; el resto del HTTPS (pip, git, brew…) pasa en túnel con su certificado real y queda registrado (#116)
- 🔐 Los valores añadidos al vault se pseudonimizan de verdad (#99); `--show-config` ya no muestra la SALT (#106); diagnósticos reales en `klaus-fix-pseudonymization` (#110)
- 🐧 `install.sh` acepta Python ≥ 3.10, probado en Debian 13 y Ubuntu 24.04 (#101); documentación revisada (#98)
- ✅ **699 tests passing** en Python 3.10–3.13

[📖 Release Notes](./docs/RELEASE_v0.6.0_NOTES.md)

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

[📖 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md) | [📋 What's New](./docs/archive/README_v0.3_SECCIONES.md#-whats-new-in-v032)

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
| [🧯 Simulacro de fugas](./docs/guides/LEAK_DRILL.md) | `klaus-leak-report --drill`: ¿el detector ve una fuga? |
| [🧾 Trazabilidad IA](./docs/trazabilidad.md) | Especificación de trazas de ejecuciones con IA y el comando `klaus-trazas` |
| [🚀 Release v0.10.0](./docs/RELEASE_v0.10.0_NOTES.md) | Notas de la última release |

---

## 🔬 Desarrollo (desde el repositorio)

```bash
# Clonar
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Setup de desarrollo
python3 -m venv .venv
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
| `ANTHROPIC_CAPTURE_HOSTS` | Hosts a auditar (coma-separada); sustituye a `hosts` de `config.json` | `hosts` de `config.json` (`api.anthropic.com`) |
| `ANTHROPIC_CAPTURE_DIR` | Directorio base de capturas | `captures/` |
| `ANTHROPIC_PSEUDO_ENABLE` | Interruptor de la seudonimización | `1` |
| `ANTHROPIC_PSEUDO_WORD_LITERALS` | Literales con frontera de palabra (org/proj IDs) | — |
| `ANTHROPIC_PSEUDO_PROJECT_ROOT` | Raíz del proyecto **auditado** (palanca de rutas + git) | `cwd` del proceso |
| `ANTHROPIC_PSEUDO_VAULT` | Ruta del vault de seudonimización | `captures/.pseudonym_vault.json` |
| `KLAUS_LOG_DIR` | Directorio del log del proxy (`proxy.log`) | `~/.klaus-proxy/logs/` |
| `ANTHROPIC_PSEUDO_USER_DIRS` | Patrón integrado de usuarios en `/Users/<u>` y `/home/<u>` | `1` |

### Protección de org/repo

El org y el nombre del repo se pseudonimizan como *word-literals*. Cada vez que `claude-proxy` arranca **dentro de un repo git**, añade el org/repo de su `origin` a `pseudo_word_literals` en `~/.klaus-proxy/config.json`. Desde ese momento quedan protegidos aunque el proxy se arranque desde otro directorio.

- **Al arrancar, `claude-proxy` protege también todos los repos de tu carpeta de proyectos** (#134). Recorre `projects_dirs` hasta 3 niveles (`~/proyectos/cliente-x/repo`) y añade a `pseudo_word_literals` el org/repo de **todos** sus remotes, no solo `origin`. Si un repo tiene un `user.email` o `user.name` propio, distinto del global, va a `pseudo_literals`. Sin `projects_dirs`, usa la carpeta padre del repo desde el que arrancas y las que ya están en `pseudo_patterns`; nunca el home. Se saltan los directorios ocultos y `node_modules`.
  - El log solo da recuentos (`🛡️  org/repo de 16 repos protegidos (18 tokens, 2 nuevos)`), nunca los nombres.
  - **Tras clonar un repo**, ejecuta `klaus-scan-repos` y reinicia `claude-proxy`. `klaus-scan-repos --dry-run` dice cuántos se añadirían sin escribir nada.
- El dashboard de arranque muestra cuántos tokens hay protegidos (`🛡️  Protected org/repo:    18 tokens`), sin nombrarlos, y avisa en amarillo si no hay ninguno.
- Además, el proxy **aprende el org/repo de cada petición**: Claude Code envía los remotes de git del proyecto en el que trabaja, y el pseudonimizador los protege antes de reescribir esa misma petición y los guarda en `pseudo_word_literals`. En el log aparece `🛡️ org/repo nuevo protegido: …`.
- Los nombres genéricos (`docs`, `api`, `test`, `app`…) no se aprenden, porque se pseudonimizaría esa palabra en todo el texto. Se avisa una vez en el log; si son privados, añádelos a mano.
- ⚠️ Ese campo es interno de Claude Code y **depende del modo de permisos** (verificado con Claude Code 2.1.312):

  | Modo | ¿Envía los remotes? | ¿Se aprende el org/repo? |
  | --- | --- | --- |
  | `auto` | Sí | Sí |
  | `plan` | Sí, desde la 2ª petición | Sí, desde la 2ª petición |
  | `manual`, `acceptEdits`, `dontAsk` | No | No |

  En `plan`, y en `auto` mientras Claude Code aún no ha leído el estado de git, la **primera** petición de un repo nuevo sale antes de aprenderlo.

- **Para proteger un repo en cualquier modo**, haz que esté en `pseudo_word_literals` antes de trabajar en él. Basta con clonarlo en la carpeta de proyectos y ejecutar `klaus-scan-repos` (o reiniciar `claude-proxy`); también puedes añadir sus tokens a mano.

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
pytest -q          # 841 passed, 2 skipped
                   # Includes: capture, pseudonymize, guard, verify, audit, dashboard, vault
```

### Test Coverage
- ✅ **841 tests passing** en Python 3.10–3.13 (CI)
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
