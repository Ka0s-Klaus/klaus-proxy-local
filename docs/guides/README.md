# 📖 Guías

## 📋 Contexto

Todo lo que necesitas para **usar, operar y solucionar problemas** de Klaus Proxy Local. Organizado por audiencia, como una biblioteca: primero encuentra tu sección, luego el libro.

---

## 🚀 Para empezar (nuevos usuarios)

| Guía | Tiempo estimado | Descripción |
|---|---|---|
| [⚡ Quick Start](../QUICK_START.md) | 2 min | Instalación y primer uso |
| [📋 User Guide](../USER_GUIDE.md) | 10 min | Guía completa de uso cotidiano |
| [🖥️ Monitor Guide](../MONITOR_GUIDE.md) | 5 min | TUI de monitorización en tiempo real |
| [🎯 Klaus Menu](../KLAUS_MENU.md) | 3 min | Menú interactivo de comandos |

---

## 🔍 Para auditores

| Guía | Descripción |
|---|---|
| [🔎 Audit Quick Start](../AUDIT_QUICK_START.md) | Auditoría rápida de payloads capturados |
| [📊 Audit Captures Guide](../AUDIT_CAPTURES_GUIDE.md) | Análisis multi-modo completo de capturas |
| [📈 Generate Reports Guide](../GENERATE_REPORTS_GUIDE.md) | Generación automática de informes |
| [🔍 Audit All Payloads](../AUDIT_ALL_PAYLOADS.md) | Auditoría masiva de todos los payloads |

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

## 🚢 Para releases y despliegues

| Guía | Descripción |
|---|---|
| [🚀 Deployment Runbook](../DEPLOYMENT_RUNBOOK.md) | Proceso completo de despliegue a producción |

---

## 🔄 Flujo típico de un auditor

```mermaid
flowchart TD
    A[▶️ Arrancar proxy] --> B[💬 Usar Claude Code]
    B --> C[📸 Capturas generadas]
    C --> D{¿Auditoría rápida\no completa?}
    D -->|rápida| E[⚡ Audit Quick Start]
    D -->|completa| F[📊 Audit Captures Guide]
    E --> G[📋 Revisar resultados]
    F --> G
    G --> H{¿Hay issues?}
    H -->|pseudonimización| I[🩺 Fix Pseudonymization]
    H -->|fugas detectadas| J[🚨 Auto Fix Leaks]
    H -->|no issues| K[✅ Todo OK]
    I --> G
    J --> G
    style A fill:#52C46A,color:#fff
    style K fill:#52C46A,color:#fff
    style I fill:#E85454,color:#fff
    style J fill:#E85454,color:#fff
```

---

## 🔗 Referencias

← [Volver al README principal](../../README.md)
