# Klaus Proxy Local v0.5.0

**Fecha:** 2026-10-29 · **Anterior:** v0.4.0

Esta versión hace que la pseudonimización **proteja cualquier proyecto sin configurarlo**, **cierra dos formas de que una petición saliera sin pseudonimizar** y añade el **histórico al audit dashboard**. Todo lo que trae se detectó revisando capturas reales.

## ⚠️ Importante: qué hacer al actualizar

```bash
git pull && ./install.sh
```

Después:

1. **Reinicia `claude-proxy` desde dentro de un repo.** Desde esta versión ejecuta los addons desde un snapshot (#71): los cambios en `src/` solo se aplican al reiniciar. Arrancado dentro de un repo, además registra su org/repo y la carpeta de proyectos (#61, #42).
2. **Vuelve a cargar `~/.klaus-proxy/klaus-env.sh`** en las terminales abiertas (`source ~/.klaus-proxy/klaus-env.sh`). La versión anterior sustituía el almacén de CAs y rompía HTTPS fuera del proxy (#53).
3. **El dashboard está en `informes/audit-dashboard.html`**, ya no en `docs/reports/web/` (#77).

Tu `config.json`, la SALT, el vault y las capturas se conservan.

## 📦 Instalación

El paquete **no está publicado en PyPI**. Se instala desde el repositorio:

```bash
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
./install.sh
```

Requisitos y detalles del instalador: [notas de v0.4.0](./RELEASE_v0.4.0_NOTES.md#-instalación).

## 🚀 Uso

```bash
# Terminal 1 (desde dentro de tu repo)
claude-proxy

# Terminal 2
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
claude

# Auditoría con histórico
klaus-audit-dashboard --open
```

## 🛡️ Privacidad y seguridad

- **Guardián fail-closed** (#71). mitmproxy recarga los addons cuando cambian en disco y, si la recarga fallaba, seguía funcionando sin el pseudonimizador: las peticiones salían en claro (verificado). Ahora `claude-proxy` ejecuta un snapshot inmutable en `~/.klaus-proxy/addons/<hash>/`, y el nuevo addon `klaus_pseudo_guard.py` bloquea con 502 cualquier petición que el pseudonimizador no haya procesado.
- **Org/repo de cualquier proyecto** (#61, #63, #65). La protección dependía del directorio desde el que se lanzaba `claude-proxy`. Ahora el org/repo se guarda en `config.json` y además se aprende de los remotes que envía Claude Code en cada petición (modos `auto` y `plan`). Los nombres de repo con puntos (`user.github.io`) ya se reconocen.
- **`pseudo_patterns`** (#42): regex en `config.json`. Al arrancar se registra la carpeta de proyectos, de modo que los nombres de todos ellos quedan ocultos en las rutas aunque no tengan remote o vayan truncados. Hay un patrón integrado para el usuario de cualquier `/Users/<u>` o `/home/<u>`.
- **El audit dashboard ya no se versiona** (#77): llevaba los datos reales de la auditoría en el repo público.

## ✨ Novedades

- **Histórico del audit dashboard** (#77): cada ejecución guarda su informe en `informes/`. Un selector abre cualquier informe anterior y un panel muestra los cambios respecto al previo (estados, métricas ▲/▼, checks EFDEF y hosts).
- **Logs en disco** (#55): `~/.klaus-proxy/logs/proxy.log`, rotado (5 MB × 5), sin colores y con una línea por petición.
- **Dashboard de arranque**: muestra los org/repo protegidos, los `pseudo_patterns` activos y el commit de los addons cargados.

## 🐛 Correcciones

- **Claude Code operaba con rutas e IPs falsas** (#67): un seudónimo partido entre dos fragmentos del streaming no se restauraba (`cd /proj_…`, `ENOTFOUND`). Ahora se restaura por bloque.
- **La versión de Claude Code se tomaba por una IP** (#57): `cc_version=2.1.312.625` salía como `ip_…`.
- **Claude Code fallaba con `UNABLE_TO_VERIFY_LEAF_SIGNATURE`** y **Ctrl+C dejaba colgado `claude-proxy`** (#51).
- **`klaus-env.sh` rompía HTTPS fuera del proxy** (#53): ahora usa `ca-bundle.pem` (CAs del sistema + CA del proxy).
- **El plan de tests del dashboard fallaba con «No module named pytest»** (#82): el venv instalado no trae pytest. Ahora usa el `.venv` del repo o `uv` y, si no hay ninguno, sale ⬜ con instrucciones.
- **`anthropic-pair-verify`**: sin falsos positivos de IPv4/email (#59) y **7× más rápido** (#73).

## 📝 Limitaciones conocidas

- El aprendizaje de org/repo por petición solo funciona en los modos de permisos `auto` y `plan` (desde la 2.ª petición). En `manual`, `acceptEdits` y `dontAsk` protegen los tokens ya guardados (#68).
- Las rutas codificadas con guiones (`-Users-u-proyectos-<repo>-…`) solo las cubren los word-literals, no los `pseudo_patterns`.

## 🧪 Calidad

- 625 tests passed, 3 skipped (+138 desde v0.4.0). CI en Python 3.10, 3.11, 3.12 y 3.13; CodeQL sin alertas.
- Cada corrección se verificó contra capturas reales y, cuando afectaba al proxy, con un `mitmdump` de prueba o con `claude -p` a través del proxy.
- Documentación revisada (#79): runbook, dashboard, README y 21 enlaces rotos.

**Changelog completo:** [`v0.4.0...v0.5.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.4.0...v0.5.0) · [CHANGELOG](../CHANGELOG.md)
