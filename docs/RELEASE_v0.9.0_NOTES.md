# Klaus Proxy Local v0.9.0

**Fecha:** 2026-11-03 · **Anterior:** v0.8.1

Release **minor** con una funcionalidad nueva: el **simulacro de fugas**. Hasta ahora, cuando `klaus-leak-report` decía «0 fugas», no había forma de saber si el proxy lo estaba cubriendo todo o si el detector se había roto y ya no veía nada. Es como una alarma de incendios que nunca ha sonado. `--drill` provoca una fuga falsa a propósito y comprueba que la alarma suena.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
klaus-leak-report --drill   # comprueba la instalación: debe salir todo ✅
```

No hace falta reiniciar `claude-proxy`: el proxy no cambia. Tampoco hay recálculo largo de `klaus-leak-report`. El simulacro no usa la caché, y el informe normal solo recalcula una vez porque ha cambiado su propio código.

`config.json`, la SALT, el vault y las capturas se conservan.

## ✨ Novedades

### 🧯 `klaus-leak-report --drill` (#171)

```text
🧯 Simulacro de fugas (directorio temporal, sin tocar tus capturas)
  ✅ 🔥 El detector ve la fuga simulada: palabra protegida
  ✅ 🛡️ El proxy sustituye el canario: palabra protegida
  ✅ 🔥 El detector ve la fuga simulada: email
  ✅ 🛡️ El proxy sustituye el canario: email
  ✅ 🔥 El detector ve la fuga simulada: ruta del home
  ✅ 🛡️ El proxy sustituye el canario: ruta del home
  ✅ 🛡️ La captura de control, seudonimizada por el proxy, sale limpia
  ✅ 📁 La captura se atribuye a su proyecto por el directorio de trabajo
  ✅ 🔴 El informe marcaría el proyecto como crítico
✅ El detector y el proxy responden como deben.
```

- **Usa tus reglas reales**, pero en un directorio temporal: no toca capturas, vault, caché ni `informes/`, no muestra valores y no hace peticiones de red.
- **Tres capas:** una palabra protegida y un email inventados, y la regla real de la ruta de tu carpeta personal.
- **Dos pares:** uno con la fuga simulada, que el detector **tiene** que ver, y otro de control seudonimizado por el proxy real, que **no** debe dar fuga.
- **Código de salida:** `0` si todo pasa y `1` si algo falla, con la capa concreta. Úsalo después de actualizar, de tocar `config.json` o antes de presentar un informe de «0 fugas».

Guía completa: [Simulacro de fugas](./guides/LEAK_DRILL.md).

## 🐛 Correcciones

- **El paquete anunciaba Python 3.9** (#175). Quitado el classifier `Python :: 3.9`, y `ruff`/`black` pasan a `py310`. Coincide con `requires-python >= 3.10` y con el CI. No cambia el formato ni el lint del código.

## 🔬 Verificación en la instalación del autor

| Comprobación | Resultado |
| --- | --- |
| `klaus-leak-report --drill` | 9/9 ✅ |
| `klaus-leak-report` | 0 fugas · 17 proyectos 🟢 · cobertura global 99,8 % · ~3.900 capturas |

## 🧪 Calidad

- 841 tests passed, 2 skipped (+6 desde v0.8.1). CI en Python 3.10, 3.11, 3.12 y 3.13.
- Cobertura total 82 % (`leak_report.py`: 95 %). `ruff` y `black` limpios.

**Changelog completo:** [`v0.8.1...v0.9.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.8.1...v0.9.0) · [CHANGELOG](../CHANGELOG.md)
