---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.12.3

**Fecha:** 2026-11-09 · **Anterior:** v0.12.2

Release **patch**. Corrige la configuración del vault al arrancar y añade comprobaciones de auditoría. Ningún cambio de comportamiento para las peticiones del cliente.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

**Reinicia `claude-proxy`.** Hasta que no se reinicia, el proxy en marcha sigue con el código anterior. Es necesario reiniciar para que el arranque aplique la migración de `config.json`.

`config.json`, la SALT, el vault y las capturas se conservan. Si `vault_path` apuntaba a `captures/.vault.json`, se corrige a `captures/.pseudonym_vault.json` (copia de seguridad antes del cambio).

## 🐛 Correcciones

### 🔐 Migración de `vault_path` al arrancar (#240, #241)

`migrate_config_paths()` corrige `capture_dir` y `vault_path` tras una actualización, pero solo la llamaba `setup.load_config`, que nadie usa. El arranque no la aplicaba, así que `vault_path` podía seguir apuntando a un fichero inexistente.

Ahora `init_config_if_missing` (la función que el lanzador llama al arrancar) aplica la migración cuando ya existe `config.json`. La configuración correcta no se reescribe.

### 🔒 Vault único (#242, #243)

Se comprobó que todos los escritores del vault usan `captures/.pseudonym_vault.json`: el pseudonimizador, el scanner, `add_to_vault.py` y `prune_vault.py`. Ningún componente escribe en `.vault.json`.

El riesgo que queda es la variable `ANTHROPIC_PSEUDO_VAULT`, que redirige todos los escritores. La auditoría EFDEF ahora avisa si aparece en `klaus-env.sh` o en el entorno.

## 🧭 Cambios

### 📋 Sección EFDEF del dashboard (#238, #239)

- Vault: `config.json:vault_path` debe apuntar al único vault válido.
- CLAUDE.md: comprueba los campos de la sección 22 (organización, repositorio, usuario y Proyecto Kanban) y las etapas del flujo, dentro de sus secciones.
- README: falla si un enlace relativo no existe (sección 23.4).
- Permisos: `config.json` en 600 y la carpeta de trazas solo para el propietario.
- `docs/trazabilidad.md` debe existir.

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| CI de las PR #239, #241 y #243 (lint, tests 3.10–3.13, seguridad) | ✅ |
| Migración real de `config.json` tras reiniciar el proxy | ✅ (corrección manual previa, con copia de seguridad; la migración automática se comprobará al reiniciar) |
| Auditoría EFDEF tras la corrección | ✅ 19/19 |

## 🔗 Enlaces

- Issue de la release: #244
- Vault y migración: #240 / PR #241; #242 / PR #243
- Auditoría EFDEF: #238 / PR #239
- Anterior: [RELEASE_v0.12.2_NOTES.md](./RELEASE_v0.12.2_NOTES.md)
