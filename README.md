# 🔌 Klaus Proxy Local

> **Proxy local de auditoría y seudonimización para el workspace K\*** — intercepta,
> audita y seudonimiza el tráfico que Claude Code envía a la API de Anthropic (y al
> gateway LLM corporativo), sin filtrar datos sensibles.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
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

## 🚀 Inicio rápido

```bash
# Clonar
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Requisitos: mitmproxy (proxy) y, para desarrollo, pytest
brew install mitmproxy          # o: pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests

# Terminal 1 — arrancar el proxy de auditoría en primer plano (logs en vivo):
mitmdump -s src/anthropic_payload_pseudonymize.py \
         -s src/anthropic_payload_capture.py -p 8899

# Terminal 2 — enrutar un claude NUEVO por el proxy:
HTTPS_PROXY=http://127.0.0.1:8899 HTTP_PROXY=http://127.0.0.1:8899 \
NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem \
claude -p "responde solo con la palabra: pong"

# Verificar en un comando lo que salió del equipo:
python3 src/anthropic_capture_verify.py
```

> El runbook completo (modelo manual con funciones `claude-proxy`/`claude` de `~/.zshrc`,
> LaunchAgent, seudonimización bidireccional) está en
> [`docs/anthropic-audit-proxy.md`](./docs/anthropic-audit-proxy.md).

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
├── src/         # addons de mitmproxy + CLIs (capture, pseudonymize, verify, analyze, cleanup)
├── tests/       # suite pytest (123 tests) — pytest -q
├── docs/        # runbook + MANIFIESTO + MANUAL + plantilla LaunchAgent
└── captures/    # 🔒 DATOS SENSIBLES (gitignored): original/, sent/, .pseudonym_vault.json
```

> ⚠️ **`captures/` nunca se versiona.** Contiene prompts, contenido real de ficheros y
> el vault real↔seudónimo. Está en `.gitignore` y jamás debe subir a este repositorio
> público.

---

## 📚 Documentación

| Documento | Descripción |
| --- | --- |
| [`docs/anthropic-audit-proxy.md`](./docs/anthropic-audit-proxy.md) | Runbook completo: captura, seudonimización, verificación, arranque |
| [`docs/MANIFIESTO_ficheros_embebidos.md`](./docs/MANIFIESTO_ficheros_embebidos.md) | Qué ficheros del repo se embeben en el payload y por qué vía |
| [`docs/MANUAL_limpieza_hardening.md`](./docs/MANUAL_limpieza_hardening.md) | Limpieza + hardening del riesgo *data-at-rest* |

---

## 🧪 Tests

```bash
pytest -q          # 123 tests (capture, pseudonymize, verify, cleanup)
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
