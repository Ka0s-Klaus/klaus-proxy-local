# Klaus Proxy Local v0.5.2

**Fecha:** 2026-10-29 · **Anterior:** v0.5.1

Release de parche de **pseudonimización**. Los nombres de las carpetas de proyectos se protegen también cuando aparecen fuera de una ruta, y el vault deja de llenarse de valores que no son datos. Las dos mejoras salen de vigilar en directo una sesión de Claude Code en otro repositorio a través del proxy.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

1. **Reinicia `claude-proxy`** desde dentro de un repo, para que cargue las reglas nuevas.
2. **Opcional, limpia el vault.** Con `claude-proxy` **parado**:

   ```bash
   python3 scripts/prune_vault.py --dry-run   # qué se quitaría
   python3 scripts/prune_vault.py             # quitar, con copia de seguridad
   ```

   Después vuelve a arrancar `claude-proxy`. Con el proxy en marcha no sirve: guarda su copia en memoria del vault y volvería a escribir las entradas. El script se niega a continuar si el puerto 8899 está escuchando.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🛡️ Privacidad

### Carpetas de proyectos fuera de una ruta (#93)

`pseudo_patterns` solo sustituía el nombre de una carpeta de proyectos dentro de una ruta (`/Users/<u>/proyectos/<carpeta>`). Vigilando una sesión en otro repositorio salieron en claro dos nombres que el vault ya conocía:

- como **nombre de fichero**: el `@import` de un `CLAUDE.md` apuntaba a `<carpeta>/<carpeta>.md`;
- como **raíz del árbol de directorios** de un README.

Ahora los nombres de carpeta del vault se sustituyen también como palabra completa, con el mismo seudónimo que en la ruta, así que la respuesta del modelo se restaura igual. Para no reemplazar palabras corrientes, solo se aplica a nombres de 5 caracteres o más que no sean genéricos (`scripts`, `tests`, `tools`…) ni estén en `pseudo_pattern_ignore`.

De paso cubre las **rutas codificadas con guiones** (`-Users-u-proyectos-<carpeta>-…`) de carpetas ya conocidas, una limitación de v0.5.0.

Se desactiva con `ANTHROPIC_PSEUDO_DIR_WORDS=0`.

### Vault sin marcadores ni puntuación (#92)

El patrón de usuarios `/Users/<u>` registraba cualquier cosa tras `/Users/` o `/home/`: los marcadores con que se tapa un nombre (`…`, `|`, `«X»`, `{user}`), una sola letra o `Shared`. Ensuciaba el vault, desfiguraba el texto que llegaba al modelo y el verificador lo tomaba por fuga.

- Los patrones ignoran ahora los valores sin letras ni números, de un solo carácter, los marcadores de plantilla (`{…}`, `<…>`, `«…»`, `$VAR`, `%VAR%`) y, como usuario, los nombres genéricos (`Shared`, `Guest`, `root`, `user`…).
- **`pseudo_pattern_ignore`** en `config.json` excluye valores concretos que por su forma no se distinguen de un dato real, como los usuarios de ejemplo de unos tests.
- **`scripts/prune_vault.py`** quita del vault los valores que ya habían entrado.

## 🔬 Verificación

- `anthropic-pair-verify` marca como fuga `[dir]` un nombre de carpeta que reaparece suelto en lo enviado, y deja de marcar los valores ignorados.
- Con los dos casos reales y una copia del vault, los nombres de carpeta en claro pasaron de 3 y 1 a 0, con restauración idéntica.

## 🧪 Calidad

- 666 tests passed, 3 skipped (+32 desde v0.5.1). CI en Python 3.10, 3.11, 3.12 y 3.13.
- Los tests que dependen del usuario de la máquina se comprueban también simulando el entorno de CI.

## 📝 Limitaciones conocidas

- Un nombre de carpeta solo se protege fuera de una ruta cuando el vault ya lo conoce, es decir, después de haber aparecido al menos una vez dentro de una ruta.
- El aprendizaje de org/repo por petición sigue funcionando solo en los modos de permisos `auto` y `plan` (#68).

**Changelog completo:** [`v0.5.1...v0.5.2`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.5.1...v0.5.2) · [CHANGELOG](../CHANGELOG.md)
