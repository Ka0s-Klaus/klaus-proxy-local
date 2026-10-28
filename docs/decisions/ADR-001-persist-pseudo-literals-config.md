# 🧭 ADR-001: Persistir literales de pseudonimización en config.json

> **Issue:** [#28 — fix: ANTHROPIC_PSEUDO_LITERALS se pierde al reiniciar el proxy](https://github.com/Ka0s-Klaus/klaus-proxy-local/issues/28)
> **Estado:** ✅ Implementado

---

## 📋 Contexto

El proxy lee los literales sensibles personalizados (`ANTHROPIC_PSEUDO_LITERALS`, `ANTHROPIC_PSEUDO_WORD_LITERALS`) desde variables de entorno, que el usuario añadía manualmente a `~/.klaus-proxy/klaus-env.sh`.

El problema: `generate_env_vars_file()` **sobreescribe ese fichero en cada reinicio**, borrando las variables añadidas. Es como escribir la lista de la compra en una pizarra que alguien borra cada mañana.

---

## 🔍 Opciones evaluadas

### Opción A: Sección protegida en `klaus-env.sh`
Añadir un bloque `# BEGIN CUSTOM` / `# END CUSTOM` que el generador respete.
- ✅ Sin cambios en el proxy
- ❌ Frágil: cualquier regeneración completa lo rompe
- ❌ El fichero mezcla responsabilidades (SSL + pseudonimización)

### Opción B ✅ — Leer desde `config.json` (elegida)
Añadir `pseudo_literals` y `pseudo_word_literals` como arrays en `config.json`. `build_rules()` los lee como fuente de verdad persistente, además de las env vars.
- ✅ Sobrevive reinicios sin depender del env file
- ✅ `config.json` ya es la fuente de verdad del resto de la configuración
- ✅ Las env vars siguen funcionando con prioridad (útil para overrides temporales)
- ✅ Un solo sitio donde el usuario gestiona sus literales

### Opción C: Fichero separado `~/.klaus-proxy/custom-env.sh`
Un fichero que el usuario edita y nunca se sobreescribe, cargado desde el arranque.
- ✅ Sin tocar el código del proxy
- ❌ Requiere instrucciones de onboarding adicionales
- ❌ Proliferación de ficheros de configuración

---

## ✅ Decisión

**Opción B**: `config.json` como fuente de verdad para literales persistentes.

---

## 🔧 Implementación

```mermaid
flowchart TD
    A[▶️ Proxy arranca] --> B[build_rules()]
    B --> C[Leer env vars\nANTHROPIC_PSEUDO_LITERALS\nANTHROPIC_PSEUDO_WORD_LITERALS]
    B --> D[Leer ~/.klaus-proxy/config.json\npseudo_literals\npseudo_word_literals]
    C --> E[Fusionar — env vars tienen prioridad\nconfig.json aporta los que falten]
    D --> E
    E --> F[Rules completas con\ntodos los literales]
    F --> G[Pseudonimización activa\ntras cualquier reinicio ✅]
    style G fill:#52C46A,color:#fff
    style A fill:#4A90D9,color:#fff
```

**Ficheros modificados:**

| Fichero | Cambio |
|---|---|
| `src/anthropic_payload_pseudonymize.py` | `build_rules()` lee `pseudo_literals` y `pseudo_word_literals` de `config.json` |
| `src/Klaus_proxy_local/setup.py` | Config por defecto incluye ambos campos como arrays vacíos |

**Estructura de `config.json` tras el fix:**
```json
{
  "pseudo_literals": ["asantacana1970"],
  "pseudo_word_literals": ["usuario_empresa", "empresa", "Cliente", "clientex"]
}
```

---

## 📌 Consecuencias

- ➕ Los literales sensibles sobreviven reinicios del proxy
- ➕ Un solo punto de gestión: `~/.klaus-proxy/config.json`
- ➕ Compatible hacia atrás: configs existentes sin esos campos funcionan igual (default `[]`)
- ➖ El usuario debe editar `config.json` para añadir nuevos literales (futuro: comando `klaus-add-literal`)

---

## 🔗 Referencias

- Issue: [#28](https://github.com/Ka0s-Klaus/klaus-proxy-local/issues/28)
- ← [Índice de decisiones](./README.md)
- ← [README principal](../../README.md)
