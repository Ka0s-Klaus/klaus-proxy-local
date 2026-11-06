---
tags: [proyecto/klaus-proxy-local, tipo/release]
---

# Klaus Proxy Local v0.8.1

**Fecha:** 2026-11-03 · **Anterior:** v0.8.0

Release de **corrección**. Al usar de verdad el flujo de la v0.8.0 (aprobar nombres de negocio y medir con `klaus-leak-report`), el informe daba como fuga una regla corta que solo aparecía **dentro** de otra palabra, aunque el proxy hacía bien en no tocarla. Ahora el informe aplica el mismo criterio que el proxy. Además, la guía explica en qué orden hacer las cosas y cómo leer las fugas después de aprobar reglas.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

No hace falta reiniciar `claude-proxy`: el proxy no cambia. La próxima vez que lances `klaus-leak-report`, recalculará todo una vez, porque ha cambiado el verificador, y tardará unos 20 minutos con ~3.900 capturas. Después vuelve a tardar segundos.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🐛 Correcciones

- **El informe de fugas daba como fuga una regla `org` que solo aparecía dentro de otra palabra** (#158). El proxy sustituye las reglas de `pseudo_word_literals` solo como palabra completa: `fabri` no se toca dentro de `tailspinfabri`, y es lo correcto. El verificador por pares, y con él `klaus-leak-report`, las buscaba como subcadena, así que un proyecto podía seguir en 🔴 sin ninguna fuga real. Ahora aplican la misma frontera de palabra que el proxy, también tras un escape (#142), y también para los valores del vault con seudónimo `org_`.

## 📖 Documentación

- **Flujo aprobar → reiniciar → informe** (#159). Hay que reiniciar `claude-proxy` **después** de aprobar en `klaus-scan`: hasta entonces, lo aprobado sigue saliendo en claro.
- **Cómo leer las fugas después de aprobar reglas** (#159). Al aprobar suben a la vez la cobertura y las capturas con fugas, porque el informe busca las reglas de hoy en las capturas antiguas. La guía explica cómo comprobar que no hay fugas posteriores al último reinicio y cuánto dura el 🔴.
- **Problemas frecuentes:** «He aprobado en `klaus-scan` y `config.json` no cambia» y «`klaus-leak-report` sigue en rojo con cobertura del 100 %».

## 🛠️ CI

- **Las releases ya no publican en PyPI** (#165). El workflow pasa a llamarse «Build distribution»: construye el sdist y la wheel, pasa `twine check` y guarda `dist/` como artefacto. Hasta ahora fallaba siempre en el build, así que nunca había publicado nada. La instalación sigue siendo `git clone` + `./install.sh`.
- `actions/checkout` y `actions/upload-artifact` pasan a la v7 (#162, #163).

## 🔬 Verificación en la instalación del autor

Recálculo completo de `klaus-leak-report` (16 proyectos, ~3.900 capturas, 22 minutos), antes y después de #158:

| | v0.8.0 | v0.8.1 |
| --- | --- | --- |
| Capturas con fuga posteriores al último reinicio del proxy | 3 | **0** |
| Capturas con fugas en el histórico | 1357 | 1238 |
| Cobertura | 100 % | 100 % |

Las capturas que dejan de contar eran todas de una regla `org` dentro de otra palabra. No se pierde ninguna fuga de otra categoría.

## 🧪 Calidad

- 835 tests passed, 3 skipped (+2 desde v0.8.0). CI en Python 3.10, 3.11, 3.12 y 3.13.

**Changelog completo:** [`v0.8.0...v0.8.1`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.8.0...v0.8.1) · [CHANGELOG](../CHANGELOG.md)
