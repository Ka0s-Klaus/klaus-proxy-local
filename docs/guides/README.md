---
tags: [proyecto/klaus-proxy-local, tipo/guia]
---

# 📖 Guías

## 📋 Contexto

Todo lo que necesitas para **usar, operar y solucionar problemas** de Klaus Proxy Local. Organizado por audiencia, como una biblioteca: primero encuentra tu sección, luego el libro.

---

## 🚀 Para empezar (nuevos usuarios)

| Guía | Tiempo estimado | Descripción |
|---|---|---|
| [⚡ Quick Start](../QUICK_START.md) | 2 min | Instalación y primer uso |
| [📋 User Guide](../USER_GUIDE.md) | 10 min | Guía completa de uso cotidiano |
| [🎯 Klaus Menu](../KLAUS_MENU.md) | 3 min | Menú interactivo de comandos |

---

## 🛠️ Para mantenedores

| Guía | Descripción |
|---|---|
| [✅ Checklist de release](./RELEASE_CHECKLIST.md) | Dónde cambia la versión y cómo se publica una release |

---

## 🔍 Para auditores

| Guía | Descripción |
|---|---|
| [🕵️ Informe de fugas por proyecto](../USER_GUIDE.md#-informe-de-fugas-por-proyecto) | `klaus-leak-report`: qué no cubre el proxy, qué ha salido y el % de cobertura. **El punto de partida** |
| [🔎 Detectar y aprobar valores](../USER_GUIDE.md#-buscar-secretos-y-nombres-de-negocio-en-un-proyecto) | `klaus-scan`: secretos y nombres de negocio de un proyecto, a las reglas del proxy |
| [🔎 Audit Quick Start](../AUDIT_QUICK_START.md) | Auditoría rápida de payloads capturados |
| [📊 Audit Captures Guide](../AUDIT_CAPTURES_GUIDE.md) | Análisis multi-modo completo de capturas |
| [📈 Generate Reports Guide](../GENERATE_REPORTS_GUIDE.md) | Generación automática de informes |
| [🔍 Audit All Payloads](../AUDIT_ALL_PAYLOADS.md) | Auditoría masiva de todos los payloads |
| [🧯 Simulacro de fugas](./LEAK_DRILL.md) | `klaus-leak-report --drill`: comprobar que un «0 fugas» es fiable |

---

## 🔧 Para troubleshooting y remediación

| Guía | Descripción |
|---|---|
| [🛠️ Troubleshooting](../TROUBLESHOOTING.md) | Solución de problemas comunes |
| [🩺 Fix Pseudonymization](../FIX_PSEUDONYMIZATION.md) | Diagnosticar y corregir payloads no pseudonimizados |
| [🚨 Auto Fix Leaks Guide](../AUTO_FIX_LEAKS_GUIDE.md) | Detección y corrección automática de fugas |
| [🔍 Inspect Anonymizations](../INSPECT_ANONYMIZATIONS.md) | Revisar el estado de las anonymizaciones |

---

## 🔐 Para gestión del vault

| Guía | Descripción |
|---|---|
| [➕ Add to Vault Automatic](../ADD_TO_VAULT_AUTOMATIC.md) | Añadir secretos al vault de forma automática |
| [⚡ Quick Vault Add](../QUICK_VAULT_ADD.md) | Añadir secretos al vault rápidamente |

---

## 🛠️ Para desarrollar

| Guía | Descripción |
|---|---|
| [⚙️ Entorno de desarrollo](../setup.md) | Tests, lint, probar cambios en el proxy y flujo de releases |
| [🔌 Runbook técnico](../anthropic-audit-proxy.md) | Referencia completa: captura, pseudonimización, verificación y variables |

---

## 🔄 Flujo típico de un auditor

Desde la v0.8, el flujo gira alrededor de dos comandos: `klaus-scan` (qué datos sensibles tiene un proyecto) y `klaus-leak-report` (qué ha salido y cuánto cubre el proxy). Las guías de análisis detallado sirven para investigar un caso concreto.

```mermaid
flowchart TD
    A[▶️ claude-proxy en marcha] --> B[💬 Usar Claude Code]
    B --> C[📸 Capturas original/ + sent/]
    C --> D[🕵️ klaus-leak-report --open]
    D --> E{¿0 fugas recientes<br/>y cobertura ≥ 95 %?}
    E -->|sí| F[🧯 klaus-leak-report --drill<br/>¿el 0 es fiable?]
    F --> K[✅ Todo OK]
    E -->|valores sin cubrir| G[🔎 klaus-scan proyecto --reveal<br/>aprobar lo que proteger]
    G --> H[🔄 Reiniciar claude-proxy]
    H --> D
    E -->|fugas que investigar| I[📊 Audit Captures Guide<br/>🩺 Fix Pseudonymization]
    I --> G
    style A fill:#52C46A,color:#fff
    style K fill:#52C46A,color:#fff
    style G fill:#E85454,color:#fff
    style I fill:#E85454,color:#fff
```

---

## 🗄️ Guías antiguas

Las guías de funcionalidades retiradas (monitor TUI, publicación en PyPI…) están en el [archivo histórico](../archive/README.md).

---

## 🔗 Referencias

← [Volver al README principal](../../README.md)
