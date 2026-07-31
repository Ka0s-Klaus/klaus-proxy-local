# 🔌 Klaus Proxy Local

> **Proxy local de auditoría y seudonimización para el workspace K\*** — intercepta,
> audita y seudonimiza el tráfico que Claude Code envía a la API de Anthropic (y al
> gateway LLM corporativo), sin filtrar datos sensibles.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![Version](https://img.shields.io/badge/version-0.2.0-green)](./docs/RELEASES.md)
[![Status](https://img.shields.io/badge/status-Production%20Ready-success)](./docs/RELEASES.md)
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

## 🚀 Inicio rápido (v0.1.0)

```bash
# Instalar
pip install Klaus-proxy-local

# Terminal 1: arrancar el proxy
claude-proxy

# Terminal 2: usar Claude Code
claude-with-proxy "tu pregunta"
```

✨ **Eso es todo.** La configuración es automática.

---

## 📦 Releases

### v0.2.0 — Sensitive Data Scanner ✅
- 🔍 Multi-tier secret detection (3 tiers independent)
- 📋 20 built-in patterns + custom pattern support
- ⚡ Interactive CLI review workflow ([A]pprove/[S]kip/[C]opy/[Q]uit)
- 🔗 Vault integration with v0.1.0
- 🧪 65+ tests (100% passing)

[📖 Release Notes](./docs/RELEASE_v0.2.0.md) | [📋 Full Details](./docs/RELEASES_DOCUMENTATION.md)

### v0.1.0 — Initial Release ✅
- 🔐 HTTPS proxy + pseudonymization
- 🚀 Zero-configuration setup
- 🛡️ Security hardening (3 critical fixes)
- 🔒 Bidirectional vault mapping

[📖 Release Notes](./docs/RELEASE_v0.1.0.md)

**[📖 All Releases](./docs/RELEASES.md)** | **[🗂️ Release Documentation](./docs/RELEASES_DOCUMENTATION.md)**

---

## 📚 Documentación

Para nuevos usuarios, **empieza aquí:**

- 🟢 **[QUICK_START.md](./docs/QUICK_START.md)** — Cómo instalar y usar (2 minutos)
- 🔵 **[THREAT_MODEL.md](./docs/THREAT_MODEL.md)** — Qué protegemos y qué no
- 📖 **[INDEX.md](./docs/INDEX.md)** — Índice completo de documentación

Para versiones y releases:

| Tema | Documento |
|------|-----------|
| **All Releases** | [RELEASES.md](./docs/RELEASES.md) |
| **v0.2.0 Release** | [RELEASE_v0.2.0.md](./docs/RELEASE_v0.2.0.md) |
| **v0.1.0 Release** | [RELEASE_v0.1.0.md](./docs/RELEASE_v0.1.0.md) |
| **Release History** | [RELEASES_DOCUMENTATION.md](./docs/RELEASES_DOCUMENTATION.md) |

Para desarrolladores y auditoría:

| Tema | Documento |
|------|-----------|
| **Scanner (v0.2.0)** | [FASE2_SENSITIVE_DATA_SCANNER.md](./docs/FASE2_SENSITIVE_DATA_SCANNER.md) |
| **Custom Patterns** | [FASE2_CUSTOM_PATTERNS.md](./docs/FASE2_CUSTOM_PATTERNS.md) |
| **Cómo funciona** | [architecture.md](./docs/architecture.md) |
| **Setup completo** | [setup.md](./docs/setup.md) |
| **Security fixes v0.1.0** | [SECURITY_HARDENING.md](./docs/SECURITY_HARDENING.md) |
| **Runbook detallado** | [anthropic-audit-proxy.md](./docs/anthropic-audit-proxy.md) |
| **Plan de pruebas** | [plan-pruebas-control.md](./docs/plan-pruebas-control.md) |

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

| Variable | Efecto | Por defecto |
| --- | --- | --- |
| `ANTHROPIC_CAPTURE_HOSTS` | Hosts a auditar (coma-separada) | `api.anthropic.com,llm.tools.cloud.customer1.es` |
| `ANTHROPIC_CAPTURE_DIR` | Directorio base de capturas | `captures/` |
| `ANTHROPIC_PSEUDO_ENABLE` | Interruptor de la seudonimización | `1` |
| `ANTHROPIC_PSEUDO_WORD_LITERALS` | Literales con frontera de palabra (org/proj IDs) | — |
| `ANTHROPIC_PSEUDO_PROJECT_ROOT` | Raíz del proyecto **auditado** (palanca de rutas + git) | `cwd` del proceso |
| `ANTHROPIC_PSEUDO_VAULT` | Ruta del vault de seudonimización | `captures/.pseudonym_vault.json` |

> Tabla completa de flags en [`docs/anthropic-audit-proxy.md`](./docs/anthropic-audit-proxy.md).

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
pytest -q          # 158 tests (capture, pseudonymize, verify, pair-verify, analyze, cleanup)
```

---

## 🤝 Contribuir

¿Quieres contribuir? Lee la [guía de contribución](./CONTRIBUTING.md) y el [código de conducta](./CODE_OF_CONDUCT.md).

---

## 🔒 Seguridad

Si encuentras una vulnerabilidad de seguridad, sigue el proceso descrito en [SECURITY.md](./SECURITY.md). **No abras una issue pública.** Nunca subas el contenido de `captures/` ni el vault: son datos sensibles reales.

---

## 📄 Licencia

MIT © [Ka0s-Klaus](https://github.com/Ka0s-Klaus)
