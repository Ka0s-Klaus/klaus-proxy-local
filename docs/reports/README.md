# 📊 Informes

## 📋 Contexto

Aquí viven los **resultados y evidencias** del proyecto: auditorías realizadas, resúmenes ejecutivos y notas de cada release. Como el historial médico del paciente: todo lo que ha pasado, cuándo y con qué resultado.

---

## 🌐 Dashboards interactivos (web/)

| Dashboard | Descripción | Cómo generar |
|---|---|---|
| [🔍 Audit Dashboard](./web/audit-dashboard.html) | 5 planes de auditoría: seguridad, pseudonimización, actividad, tests, EFDEF | `python3 scripts/generate_audit_dashboard.py --open` |

→ [Ver documentación completa de dashboards](./web/README.md)

---

## 🔍 Auditorías y análisis

| Informe | Fecha | Descripción |
|---|---|---|
| [📊 Executive Summary](../EXECUTIVE_SUMMARY.md) | — | Resumen ejecutivo del estado del sistema |
| [🔧 Fix Summary](../FIX_SUMMARY.md) | — | Resumen de todas las correcciones aplicadas |
| [📋 Audit Results](../AUDIT_RESULTS_20260905.md) | 2026-09-05 | Resultados de auditoría de payloads |

---

## 🚀 Notas de releases

| Versión | Estado | Documento |
|---|---|---|
| **v0.3.2** | ✅ Actual | [RELEASE_v0.3.2_NOTES.md](../RELEASE_v0.3.2_NOTES.md) |
| **v0.3.1** | ✅ Anterior | [RELEASE_v0.3.1_NOTES.md](../RELEASE_v0.3.1_NOTES.md) |
| **v0.3.0** | ✅ Anterior | [RELEASE_v0.3.0.md](../RELEASE_v0.3.0.md) |
| **Instrucciones** | — | [RELEASE_INSTRUCTIONS.md](../RELEASE_INSTRUCTIONS.md) |

---

## 🔄 Ciclo de vida de un informe

```mermaid
flowchart LR
    A[🎯 Evento\nauditado] --> B[📸 Captura\ngenerada]
    B --> C[🔍 Análisis\nautomático]
    C --> D[📄 Informe\ngenerado]
    D --> E[📁 docs/reports/\narchivado]
    E --> F[🔗 Referenciado\ndesde README.md]
    style A fill:#4A90D9,color:#fff
    style E fill:#52C46A,color:#fff
    style F fill:#9B59B6,color:#fff
```

> 💡 **Convención de nombres:** los informes de auditoría usan fecha `AUDIT_RESULTS_YYYYMMDD.md`. Los informes de release usan `RELEASE_vX.Y.Z_NOTES.md`. Así de fácil es saber cuándo se generó algo con solo mirar el nombre.

---

## 🔗 Referencias

← [Volver al README principal](../../README.md)
