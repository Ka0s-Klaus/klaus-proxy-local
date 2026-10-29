# Klaus Proxy Local v0.5.1

**Fecha:** 2026-10-29 · **Anterior:** v0.5.0

Release de parche centrada en el **audit dashboard**: los avisos de prompt injection pasan de ser una hora suelta a decir qué texto saltó, de dónde venía y qué hacer con él.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
```

No hace falta reiniciar `claude-proxy`: los cambios son solo del dashboard. `config.json`, la SALT, el vault, las capturas y el histórico de `informes/` se conservan.

Si vienes de v0.4.0 o anterior, sigue antes los pasos de las [notas de v0.5.0](./RELEASE_v0.5.0_NOTES.md) («Importante: qué hacer al actualizar»).

## ✨ Novedades

### Avisos de prompt injection con detalle (#86)

Antes: `⚠️ 1 patrones de injection detectados: 2026-10-29T11:44:28`. Ahora cada aviso muestra:

- hora, endpoint y fichero de la captura;
- patrones encontrados y **origen**: mensaje del usuario, resultado de una herramienta (Read, Bash, WebFetch…) o `count_tokens`;
- **fuente**: el fichero, la URL o el comando que produjo el texto;
- un fragmento con la coincidencia resaltada;
- en cuántas peticiones aparece: un texto reenviado en el historial cuenta **una sola vez**;
- su **id** y el comando para marcarlo como revisado.

### Qué hacer con cada aviso (#88)

Debajo de los avisos, el dashboard indica los pasos:

- **Falso positivo** (código, documentación o una conversación sobre injection): márcalo como revisado.
- **Sospechoso** (un fichero, una web o una salida que da órdenes a Claude): no sigas esa sesión, localiza la fuente, revisa lo que hizo Claude después (`git status`, `git diff`), elimina o aísla la fuente, rota credenciales si procede y márcalo como revisado con una nota.

```bash
klaus-audit-dashboard --mark-reviewed 3f9c0a1b2d4e 7a8b9c0d1e2f --note "doc del detector"
```

Los ids se guardan en `audit_injection_reviewed` de `~/.klaus-proxy/config.json`. Los avisos revisados no cuentan para el estado del plan y se muestran plegados con su nota. Para que uno vuelva a contar, borra su entrada.

## 🐛 Correcciones

- **El repo disparaba su propio detector** (#86): el código, los tests y la documentación del detector contenían las frases literales, y cada lectura con Claude Code producía un aviso nuevo. Ya no las contienen, y un test lo comprueba.
- **La fuente se cortaba en rutas largas** (#88): ahora se conserva el final de la ruta, que es lo que identifica el fichero.
- **Fragmentos con `</script>`** (#86): el JSON incrustado en la página escapa `<`, así que un fragmento con `</script>` ya no rompe el HTML ni inyecta código.

## 🧪 Calidad

- 634 tests passed, 3 skipped (+9 desde v0.5.0). CI en Python 3.10, 3.11, 3.12 y 3.13.
- **Prueba controlada:** un README simulado de una dependencia, con una instrucción oculta en un comentario HTML, leído con Read a través del proxy. El dashboard lo marcó con origen «resultado de Read», la ruta del fichero, el fragmento, la captura y el id. La prueba destapó el corte de rutas largas, ya corregido.

**Changelog completo:** [`v0.5.0...v0.5.1`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.5.0...v0.5.1) · [CHANGELOG](../CHANGELOG.md)
