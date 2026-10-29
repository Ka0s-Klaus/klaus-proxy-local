# 🗄️ Archivo histórico

Documentos que describen el proyecto **tal como era en un momento pasado**. Se conservan por trazabilidad, pero **no reflejan la funcionalidad actual**: pueden citar comandos, opciones, rutas o recuentos de tests que ya no existen.

Para el estado actual, ve al [README](../../README.md), a la [guía de inicio rápido](../QUICK_START.md) o al [runbook técnico](../anthropic-audit-proxy.md).

| Documento | Qué recoge | Por qué está archivado |
| --- | --- | --- |
| [EXECUTIVE_SUMMARY.md](./EXECUTIVE_SUMMARY.md) | Resumen ejecutivo de v0.3.0 | Estado de v0.3.0; promete que añadir al vault protege un valor, lo que no era cierto hasta #99 |
| [FIX_SUMMARY.md](./FIX_SUMMARY.md) | Correcciones de septiembre de 2026 | Registro de un momento; recuentos de tests antiguos |
| [AUDIT_RESULTS_20260905.md](./AUDIT_RESULTS_20260905.md) | Resultado de una auditoría del 2026-09-05 | Registro de un momento; usa opciones de `add_to_vault.py` que no existen |
| [MONITOR_GUIDE.md](./MONITOR_GUIDE.md) | Monitor TUI | El monitor se eliminó en v0.3.3 y `--monitor` en #103 |
| [RELEASE_v0.3.0.md](./RELEASE_v0.3.0.md) | Anuncio de v0.3.0 | Duplica las [notas de v0.3.0](../RELEASE_v0.3.0_NOTES.md) |
| [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) | Instalación y «despliegue» de v0.3.0 | Instalación desde PyPI, puerto configurable y SALT en `~/.klaus-proxy/.salt`, que no existen; la instalación vigente está en el [inicio rápido](../QUICK_START.md) |
| [RELEASE_INSTRUCTIONS.md](./RELEASE_INSTRUCTIONS.md) | Publicar en PyPI con `twine` | El paquete no se publica en PyPI; las releases son tags y GitHub Releases |
| [KLAUS_MENU_FIX_COMPLETE.md](./KLAUS_MENU_FIX_COMPLETE.md) | Corrección del menú `klaus` | Registro de un PR; la guía vigente es [KLAUS_MENU.md](../KLAUS_MENU.md) |
| [PRUEBA_FUGA_Y_REMEDIACION.md](./PRUEBA_FUGA_Y_REMEDIACION.md) | Prueba de una fuga y su remedio | Registro de una prueba puntual |
| [PR_TEMPLATE.md](./PR_TEMPLATE.md) | Plantilla de PR | Duplicaba la vigente, [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md) |
| [DOCUMENTATION_STYLE.md](./DOCUMENTATION_STYLE.md) | Guía de estilo de la documentación | Cita documentos que nunca existieron |

Las notas de cada release (`docs/RELEASE_v*_NOTES.md`) y el [CHANGELOG](../../CHANGELOG.md) también son históricos por naturaleza, pero se quedan en su sitio: cada una describe su versión.
