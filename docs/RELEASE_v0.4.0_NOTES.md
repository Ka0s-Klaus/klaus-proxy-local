# Klaus Proxy Local v0.4.0

**Fecha:** 2026-10-28 · **Anterior:** v0.3.3

Esta versión hace que **la instalación funcione de principio a fin en un equipo limpio**, añade el dashboard de auditoría y la detección por ruta para acercarse al 99,9 % de pseudonimización, y **cierra una exposición de red**: el proxy dejaba de ser accesible desde la LAN.

## ⚠️ Importante: actualiza si usas una versión anterior

Hasta v0.3.3, `claude-proxy` escuchaba en **todas las interfaces** (`*:8899`). Cualquier equipo de tu red podía usarlo como proxy abierto y meter tráfico en tus capturas. Desde v0.4.0 solo escucha en `127.0.0.1` (#47).

## 📦 Instalación

El paquete **no está publicado en PyPI**. Se instala desde el repositorio:

```bash
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
./install.sh --check   # opcional: verifica prerequisitos
./install.sh
```

Requisitos: macOS o Linux, Python ≥ 3.13 para el instalador (en macOS lo instala vía Homebrew si falta) y git.

El instalador:
1. Crea un venv en `~/.local/share/klaus/venv` e instala el paquete con mitmproxy.
2. Enlaza `claude-proxy`, `klaus-*` y `klaus-audit-dashboard` en `~/.local/bin`.
3. Genera `~/.klaus-proxy/config.json` (con SALT aleatoria), la CA de mitmproxy y `~/.klaus-proxy/klaus-env.sh`.

> La instalación es *editable*: no borres ni muevas el clon. Para actualizar: `git pull && ./install.sh`.

**Actualizar desde v0.3.x:** `git pull && ./install.sh`. Se conservan tu `config.json`, la SALT y las capturas.

## 🚀 Uso

```bash
# Terminal 1
claude-proxy

# Terminal 2
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude
```

## ✨ Novedades
- **Instalador bootstrap** `install.sh` con venv global (#33).
- **Dashboard HTML de auditoría**: `klaus-audit-dashboard --open` (#35).
- **Detección por ruta** `/v1/messages*`: pseudonimiza aunque el gateway no esté en `config.json` (#41).
- **Flag `pseudo_ran`** y métrica del dashboard basada en peticiones procesadas, con umbral ≥ 99 % (#41).

## 🐛 Correcciones
- 🔒 El proxy solo escucha en `127.0.0.1` (#47).
- `install.sh` ya no falla al generar la CA: resuelve `mitmdump` desde el venv y no necesita TTY (#43).
- `klaus-audit-dashboard` se enlaza en `~/.local/bin` (#43).
- `pseudo_literals` persisten entre reinicios (#29).
- Los hosts se leen de `config.json`; eliminado el placeholder `customer1.es` (#37).
- CodeQL #58: comparación de hosts exacta en lugar de por subcadena (#45).

## 🧪 Calidad
- CI desbloqueado: Lint (ruff + black) y Test vuelven a ejecutarse en cada PR (#45).
- Matriz de tests: Python 3.10, 3.11, 3.12 y 3.13.
- 487 tests passed, 2 skipped.
- Instalación verificada de principio a fin en macOS 26.7 con Python 3.15 y mitmproxy 12.3.1.

**Changelog completo:** [`v0.3.3...v0.4.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.3.3...v0.4.0)
