# 📊 Informes

## 📋 Contexto

Los **informes de auditoría** se generan en local, en `informes/` (que no se versiona: contienen datos reales de tus capturas). Aquí solo se documenta cómo generarlos, junto con las notas de cada release.

---

## 🌐 Audit dashboard

| Dashboard | Descripción | Cómo generar |
|---|---|---|
| 🔍 Audit Dashboard (`informes/audit-dashboard.html`) | 5 planes de auditoría (seguridad, pseudonimización, actividad, tests, EFDEF), histórico de informes y cambios respecto al anterior | `klaus-audit-dashboard --open` |

→ [Documentación completa del dashboard](./web/README.md)

Otros informes locales:

| Herramienta | Qué genera |
|---|---|
| `anthropic-pair-verify` | Validación por pares `original` ↔ `sent`: fugas en claro y secretos ([runbook](../anthropic-audit-proxy.md)) |
| `klaus-audit-payloads` | Estadísticas de pseudonimización por payload ([guía](../AUDIT_ALL_PAYLOADS.md)) |
| `generate_audit_report.py` | Informes Markdown en `informes/audit_*.md` ([guía](../GENERATE_REPORTS_GUIDE.md)) |

---

## 🚀 Notas de releases

| Versión | Documento |
|---|---|
| **v0.7.0** (última) | [RELEASE_v0.7.0_NOTES.md](../RELEASE_v0.7.0_NOTES.md) |
| v0.6.1 | [RELEASE_v0.6.1_NOTES.md](../RELEASE_v0.6.1_NOTES.md) |
| v0.6.0 | [RELEASE_v0.6.0_NOTES.md](../RELEASE_v0.6.0_NOTES.md) |
| v0.5.2 | [RELEASE_v0.5.2_NOTES.md](../RELEASE_v0.5.2_NOTES.md) |
| v0.5.1 | [RELEASE_v0.5.1_NOTES.md](../RELEASE_v0.5.1_NOTES.md) |
| v0.5.0 | [RELEASE_v0.5.0_NOTES.md](../RELEASE_v0.5.0_NOTES.md) |
| v0.4.0 | [RELEASE_v0.4.0_NOTES.md](../RELEASE_v0.4.0_NOTES.md) |
| v0.3.2 | [RELEASE_v0.3.2_NOTES.md](../RELEASE_v0.3.2_NOTES.md) |
| v0.3.1 | [RELEASE_v0.3.1_NOTES.md](../RELEASE_v0.3.1_NOTES.md) |
| v0.3.0 | [RELEASE_v0.3.0_NOTES.md](../RELEASE_v0.3.0_NOTES.md) |

Las releases se publican como tags y [GitHub Releases](https://github.com/Ka0s-Klaus/klaus-proxy-local/releases); el paquete no se publica en PyPI.

---

## 🗄️ Informes antiguos

Los resúmenes y resultados de auditoría de versiones anteriores están en el [archivo histórico](../archive/README.md). No reflejan la funcionalidad actual.

---

## 🔗 Referencias

← [Volver al README principal](../../README.md)
