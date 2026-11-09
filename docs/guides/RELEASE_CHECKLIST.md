---
tags: [proyecto/klaus-proxy-local, tipo/guia]
---

# ✅ Checklist de release

Lista de comprobación para preparar una release patch o minor. Sirve para que el número de versión quede igual en todos los sitios. Lo que no esté aquí, no se actualiza automáticamente.

## 1. Versión en el código

Cambia la versión a la nueva en todos estos ficheros:

| Fichero | Qué cambiar |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `product.json` | `"version"` |
| `src/Klaus_proxy_local/__init__.py` | `__version__` |
| `src/Klaus_proxy_local/sensitive_data_scanner.py` | cabecera del docstring |
| `klaus`, `scripts/klaus` | `VERSION="X.Y.Z"` |
| `start.sh`, `run_all.sh` | línea `echo` con la versión |

## 2. Documentación con versión

| Fichero | Qué cambiar |
|---|---|
| `README.md` | insignia de versión, enlace de estado, sección «Inicio rápido», nueva entrada en «Releases» y la fila «Release» de la tabla de documentación |
| `docs/USER_GUIDE.md`, `docs/QUICK_START.md`, `docs/ARCHITECTURE_DEEP_DIVE.md` | línea `**Versión:**` |
| `docs/reports/README.md` | tabla de releases (la nueva marcada como última) |
| `CHANGELOG.md` | sección `[X.Y.Z]` con las entradas y los números de issue |
| `docs/RELEASE_vX.Y.Z_NOTES.md` | notas de la release, sin frontmatter de Obsidian al publicar |

## 3. Comprobación

```bash
bash scripts/verify_release.sh
```

El check de versiones falla si `pyproject.toml`, `__init__.py` y la insignia del README no coinciden.

## 4. Después de fusionar

1. Tag anotado sobre el commit de `main`: `git tag -a vX.Y.Z -m "Proxy Local vX.Y.Z (#issue)"` y `git push origin vX.Y.Z`.
2. GitHub Release con las notas: `gh release create vX.Y.Z --verify-tag --title "Klaus Proxy Local vX.Y.Z" --notes-file <notas sin frontmatter>`.
3. Comprobar con `gh release list` que la release queda marcada como *latest*.

## 🔗 Referencias

- Índice de guías: [README.md](./README.md).
- Estado de las releases: [CHANGELOG.md](../../CHANGELOG.md).
