# 🏗️ Arquitectura

## 📋 Contexto

Aquí vive todo lo que explica **cómo está construido** Klaus Proxy Local. Como los planos de un edificio: antes de tocar el código, hay que saber qué hay dónde y por qué está así.

---

## 📄 Documentos

| Documento | Descripción |
|---|---|
| [🔬 Arquitectura](../ARCHITECTURE_DEEP_DIVE.md) | Arranque, los 4 addons, reglas de pseudonimización, garantías y límites |
| [🔌 Anthropic Audit Proxy](../anthropic-audit-proxy.md) | Runbook técnico completo del proxy: flags, modos y operación |
| [⚙️ Entorno de desarrollo](../setup.md) | Tests, lint y cómo probar cambios en el proxy |

---

## 🔄 Flujo de alto nivel

```mermaid
flowchart TD
    A[🖥️ Claude Code] -->|HTTPS_PROXY=8899| B[🔀 mitmproxy :8899]
    B --> C{🔐 addon: pseudonymize}
    B --> H{🚧 addon: guard<br/>502 si no se pseudonimizó}
    C -->|datos pseudonimizados| D[🌐 api.anthropic.com]
    D -->|respuesta| C
    C -->|datos reales restaurados| A
    B --> E{📸 addon: capture}
    E -->|datos reales| F[📁 captures/original/]
    E -->|datos pseudonimizados| G[📁 captures/sent/]
    style A fill:#4A90D9,color:#fff
    style D fill:#E8744A,color:#fff
    style F fill:#E85454,color:#fff
    style G fill:#52C46A,color:#fff
```

> 💡 **Cómo leerlo:** Klaus se sienta entre Claude Code y la API como un guardia de seguridad en la puerta. Revisa cada petición, la pseudonimiza antes de que salga, guarda una copia de lo que llegó y de lo que salió, y bloquea lo que no haya podido pseudonimizar.

---

## 🔗 Referencias

← [Volver al README principal](../../README.md)
