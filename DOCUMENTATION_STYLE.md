# 📚 Guía de Estilo de Documentación

Este documento define el estándar de formato para toda la documentación del proyecto **Klaus-proxy-local** a partir de septiembre 2026.

## 🎯 Estructura de README.md

### Portada
```markdown
# 🔌 Nombre del Proyecto

> **Tagline en negrita.** Contexto adicional.

[![Badge1](url)](url) [![Badge2](url)](url)

---
```

### Sección: "¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?"
```markdown
## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

### ¿Qué hago?
[Descripción del proyecto]

### ¿Cómo lo hago?
[Técnica / Arquitectura]

### ¿Para qué lo hago?
[Problema / Valor]

---
```

### Releases
```markdown
## 📦 Releases

### v1.0.0 — Feature Complete ✅
- ✅ Feature A
- ✅ Feature B

[📖 Release Notes](./docs/RELEASE_v1.0.0.md)

---
```

### Instalación rápida
```markdown
## 🚀 Instalación rápida (v1.0)

### Requisitos
- Python 3.13+
- [Otra req]

### Pasos

\`\`\`bash
pip install project==1.0.0
./start-service.sh
\`\`\`

---
```

### Uso
```markdown
## 🎯 Uso

### Modo 1: API

\`\`\`bash
curl http://localhost:8080/endpoint
\`\`\`

### Modo 2: CLI

\`\`\`bash
cli-command --flag value
\`\`\`

---
```

### Arquitectura
```markdown
## 🏗️ Arquitectura

\`\`\`mermaid
graph TD
    INPUT["🖥️ Input"] --> PROCESS["🔄 Procesamiento"]
    PROCESS --> OUTPUT["✅ Output"]
\`\`\`

**Stack:**
- Componente 1: tech
- Componente 2: tech

---
```

### Documentación
```markdown
## 📚 Documentación

### Para nuevos usuarios

| Guía | Tiempo | Descripción |
|---|---|---|
| [🚀 Quick Start](docs/QUICK_START.md) | 2 min | Setup básico |
| [⚙️ Config](docs/CONFIG.md) | 5 min | Configuración |

### Para desarrolladores

| Doc | Descripción |
|---|---|
| [🏗️ Arquitectura](docs/ARCHITECTURE.md) | Diseño |
| [🛠️ Setup](docs/SETUP.md) | Desarrollo local |

---
```

### Tests
```markdown
## 🧪 Tests

\`\`\`bash
pytest -v
pytest --cov=module --cov-report=html
\`\`\`

✅ 465/465 tests passing (100%)

---
```

### Seguridad
```markdown
## 🔐 Seguridad

Para reportar vulnerabilidades: [SECURITY.md](SECURITY.md)

**⚠️ No abras issues públicas para fallos de seguridad.**

---
```

### Contribuir
```markdown
## 🤝 Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md) y [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

1. Fork
2. Rama: `git checkout -b feat/feature`
3. Commit: `git commit -m "Add feature"`
4. Push y PR

---

## 📄 Licencia

[MIT](LICENSE) © Ka0s-Klaus
```

## 🎨 Emojis estándar

| Sección | Emoji |
|---|---|
| Título | 🔌 (específico) |
| ¿Qué? | 🤔 |
| Releases | 📦 |
| Instalación | 🚀 |
| Uso | 🎯 |
| Arquitectura | 🏗️ |
| Documentación | 📚 |
| Tests | 🧪 |
| Seguridad | 🔐 |
| Contribuir | 🤝 |
| Licencia | 📄 |

## ✅ Checklist de calidad

- [ ] Portada con emoji + tagline + badges
- [ ] Sección "¿Qué? ¿Cómo? ¿Para qué?"
- [ ] Separadores `---` entre secciones
- [ ] Releases con estado y notas
- [ ] Instalación con requisitos y pasos
- [ ] Uso con ejemplos (API + CLI)
- [ ] Arquitectura con Flowchart Mermaid
- [ ] Documentación: tablas de guides por usuario
- [ ] Tests: comando y coverage %
- [ ] Seguridad: política clara
- [ ] Contribuir: pasos + guías
- [ ] Licencia MIT
- [ ] Emojis contextuales

## 📝 Ver README.md como referencia aplicada.
