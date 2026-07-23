# 🤝 Guía de Contribución — Klaus Proxy Local

Gracias por tu interés en contribuir a `Klaus Proxy Local`. Este documento describe el proceso para participar en el proyecto de forma ordenada y efectiva.

---

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

**Qué:** Define el flujo de contribución al proyecto — desde reportar bugs hasta abrir Pull Requests.
**Cómo:** A través del sistema de Issues y Pull Requests de GitHub, siguiendo las convenciones de este documento.
**Para qué:** Garantizar que el código que entra al repositorio es revisado, trazable y de calidad.

---

## 📋 Antes de contribuir

1. Lee el [README.md](./README.md) para entender el propósito del proyecto.
2. Revisa las [Issues abiertas](https://github.com/Ka0s-Klaus/klaus-proxy-local/issues) — puede que alguien ya esté trabajando en lo mismo.
3. Lee el [Código de Conducta](./CODE_OF_CONDUCT.md).

---

## 🐛 Reportar un bug

1. Abre una [nueva Issue](https://github.com/Ka0s-Klaus/klaus-proxy-local/issues/new/choose) usando la plantilla **Bug Report**.
2. Incluye: versión de Python, sistema operativo, pasos para reproducir, comportamiento esperado vs. real.
3. Adjunta logs relevantes (sin credenciales).

## 💡 Proponer una mejora

1. Abre una Issue usando la plantilla **Feature Request** antes de implementar nada.
2. Describe el caso de uso concreto — no solo la funcionalidad.
3. Espera feedback antes de abrir un PR.

---

## 🔀 Flujo de Pull Request

```
Issue abierta → Fork o rama → Implementación → Tests → PR → Review → Merge
```

### Pasos concretos

1. **Crea una rama** desde `main` con el formato `GH-{N}-descripcion-breve` (donde `N` es el número de Issue).
2. **Implementa** los cambios. Un PR = un cambio cohesionado.
3. **Tests**: añade o actualiza tests para cubrir los cambios.
4. **Abre el PR** contra `main` usando la plantilla incluida.
5. **Responde a los comentarios de review** en un plazo razonable.

### Requisitos de un PR válido

- [ ] La Issue correspondiente está referenciada (`Closes #N`)
- [ ] Los tests pasan (`pytest`)
- [ ] No hay credenciales hardcodeadas
- [ ] El código sigue el estilo del proyecto (`ruff`, `black`)
- [ ] La documentación en `docs/` está actualizada si el cambio lo requiere

---

## 🛠️ Setup del entorno de desarrollo

```bash
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Ejecutar tests

```bash
pytest
```

### Linting

```bash
ruff check .
black --check .
```

---

## 📐 Estilo de código

- **Formatter**: `black` (line length 88)
- **Linter**: `ruff`
- **Type hints**: obligatorios en funciones públicas
- **Docstrings**: Google style para módulos y clases públicas
- **Idioma del código**: inglés (variables, funciones, comentarios técnicos)

---

## ❓ ¿Dudas?

Abre una [Discussion](https://github.com/Ka0s-Klaus/klaus-proxy-local/discussions) o comenta en la Issue relevante.
