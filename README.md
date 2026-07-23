# 🔌 Klaus Proxy Local

> **Local HTTP proxy for K\* AI Workspace** — routes and manages API calls to Claude/Anthropic endpoints locally.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![K*](https://img.shields.io/badge/K%2A-AI%20Workspace-purple)](https://github.com/Ka0s-Klaus)

---

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

### ¿Qué hago?
`Klaus Proxy Local` es un proxy HTTP local que actúa como intermediario entre las herramientas del workspace K\* (Claude Code, Continue.dev, scripts de automatización) y la API de Anthropic/Claude. Expone una interfaz compatible con la API de Anthropic para que cualquier cliente pueda conectarse sin configuración adicional.

### ¿Cómo lo hago?
- Levanta un servidor HTTP local (puerto configurable, por defecto `8080`)
- Recibe peticiones de cualquier cliente compatible con la API de Anthropic
- Añade funcionalidades transversales: caché semántico, logging, rate limiting, métricas
- Reenvía la petición al endpoint real de Anthropic o a un proveedor alternativo

### ¿Y para qué lo hago?
- **Reducir costes**: caché semántico evita llamadas repetidas a la API
- **Observabilidad**: logging centralizado de todas las inferencias
- **Flexibilidad**: cambiar de modelo o proveedor sin tocar los clientes
- **Desarrollo local**: trabajar sin depender de la conectividad a la API de Anthropic

---

## 🚀 Inicio rápido

```bash
# Clonar el repositorio
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tu ANTHROPIC_API_KEY

# Levantar el proxy
python -m klaus_proxy
```

El proxy queda disponible en `http://localhost:8080`.

---

## ⚙️ Configuración

| Variable | Descripción | Por defecto |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | API key de Anthropic | *requerida* |
| `PROXY_PORT` | Puerto del servidor local | `8080` |
| `PROXY_HOST` | Host de escucha | `127.0.0.1` |
| `CACHE_ENABLED` | Activar caché semántico | `false` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

---

## 📚 Documentación

La documentación completa del proyecto vive en [`docs/`](./docs/):

| Documento | Descripción |
| --- | --- |
| _(pendiente)_ | Arquitectura del proxy |
| _(pendiente)_ | Guía de configuración avanzada |
| _(pendiente)_ | Integración con Continue.dev y Claude Code |

---

## 🤝 Contribuir

¿Quieres contribuir? Lee la [guía de contribución](./CONTRIBUTING.md) y el [código de conducta](./CODE_OF_CONDUCT.md).

---

## 🔒 Seguridad

Si encuentras una vulnerabilidad de seguridad, sigue el proceso descrito en [SECURITY.md](./SECURITY.md). **No abras una issue pública.**

---

## 📄 Licencia

MIT © [Ka0s-Klaus](https://github.com/Ka0s-Klaus)
