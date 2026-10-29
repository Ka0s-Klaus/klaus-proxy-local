# Klaus Proxy Local v0.6.0

**Fecha:** 2026-10-29 · **Anterior:** v0.5.2

Release menor. **Cada terminal pasa por el proxy y ninguna herramienta da errores de certificado:** `klaus-setup` arranca el proxy y exporta `HTTPS_PROXY` en cada terminal nueva, y el proxy solo descifra el tráfico de la API del LLM. El resto pasa en túnel y queda registrado. Además, los valores añadidos al vault se protegen de verdad, la SALT deja de mostrarse y la documentación está revisada contra lo que hace el código.

## ⬆️ Actualizar

```bash
git pull && ./install.sh     # instala también claude-with-proxy en ~/.local/bin
```

1. **Reinicia `claude-proxy`** desde dentro de un repo, para que cargue el addon nuevo. Al arrancar, el log muestra `🔓 Se descifra solo: …` con la lista de hosts.
2. **Opcional, cada terminal por el proxy:** ejecuta `klaus-setup` (responde `y`) y después `exec $SHELL`. Sustituye el hook de versiones anteriores, que no exportaba `HTTPS_PROXY`.
3. **Si usas un gateway LLM propio,** comprueba que está en `hosts` de `~/.klaus-proxy/config.json` o en `ANTHROPIC_BASE_URL`. Si no está en ninguno de los dos, ahora iría en túnel **sin pseudonimizar** (ver más abajo).

`config.json`, la SALT, el vault y las capturas se conservan.

## 🖥️ Cada terminal por el proxy (#105, #116)

### `klaus-setup`

Añade a `~/.zshrc`, `~/.bashrc` o la configuración de fish un bloque entre marcadores `# >>> Klaus Proxy Local (klaus-setup) >>>`. En cada terminal nueva:

- carga `klaus-env.sh` (confianza en la CA del proxy);
- arranca `claude-proxy` en segundo plano con `nohup` si no está en marcha (log en `~/.klaus-proxy/logs/autostart.log`);
- exporta `HTTPS_PROXY` y `NO_PROXY` (el tráfico a loopback no pasa por el proxy). **Basta con escribir `claude`.**
- define `klaus-off` / `klaus-on`, que quitan o restauran el proxy en esa terminal.

Antes el hook no exportaba `HTTPS_PROXY`: `claude` no pasaba por el proxy aunque estuviera en marcha. Volver a ejecutar `klaus-setup` sustituye el bloque y el hook antiguo. PowerShell deja de estar soportado, como el resto de Windows.

### `claude-with-proxy`

Para quien prefiera no tocar el shell. `install.sh` lo enlaza en `~/.local/bin`. Carga `klaus-env.sh` (antes faltaba y Claude Code rechazaba el certificado del proxy) y **se niega a lanzar `claude` si el proxy no está escuchando**. No arranca el proxy.

### Solo se descifra la API del LLM (#116)

Con `klaus-setup`, todo el HTTPS de la terminal pasa por el proxy: pip, git, brew, gh, podman… Si el proxy lo descifrara todo, cada herramienta que no confíe en su CA daría errores de certificado. El addon nuevo **`klaus_tls_passthrough`** decide en cada conexión:

| Destino | Qué hace el proxy | En el log |
| --- | --- | --- |
| `anthropic.com`, `claude.ai` y subdominios; `hosts` de `config.json`; host de `ANTHROPIC_BASE_URL` (entorno o `~/.claude/settings.json`) | Descifra, pseudonimiza y captura, como hasta ahora | Línea por petición |
| Cualquier otro host | Túnel TLS sin descifrar: el cliente ve el certificado real del servidor | `TÚNEL host:puerto (sin descifrar)` |

```bash
grep TÚNEL ~/.klaus-proxy/logs/proxy.log | tail
```

- Del tráfico en túnel se registran el host, el puerto y la hora, **no el contenido**. Ver el contenido exige descifrarlo, y eso solo funciona si la herramienta confía en la CA del proxy.
- `"intercept_all": true` en `config.json`, o `KLAUS_INTERCEPT_ALL=1` al arrancar `claude-proxy`, vuelven a descifrarlo todo, como antes.
- **Si el addon no carga,** mitmproxy lo descifra todo: falla hacia el lado seguro, con errores de certificado en otras herramientas pero sin que el tráfico de la API salga sin pseudonimizar.

**Lo que tienes que saber:**

- **Gateways LLM:** la defensa de «host desconocido con ruta de LLM» del pseudonimizador solo ve lo que se descifra. Un gateway que no esté en `hosts` ni en `ANTHROPIC_BASE_URL` iría en túnel sin pseudonimizar.
- **Org/repo:** el proxy registra el org/repo de la carpeta donde arranca, que con `klaus-setup` es la de la primera terminal que abras. Para otro repo, páralo y arráncalo desde ese repo.
- **Primera terminal:** nada más abrirla, el proxy tarda unos segundos en empezar a escuchar.

## 🛡️ Privacidad

- **Los valores añadidos al vault se pseudonimizan de verdad** (#99). `scripts/add_to_vault.py`, `klaus-scan --approve-all` y `auto_add_detected_leaks.py` los escribían solo en el vault, pero el proxy solo sustituye lo que casa con una regla. Ahora también los añaden a `config.json`: a `pseudo_word_literals` si son un único token y a `pseudo_literals` si no.
- **`klaus-fix-pseudonymization --show-config` ya no muestra la SALT** (#106). Si lo ejecutaba un agente, la SALT viajaba a la API en claro dentro del resultado de la herramienta.
- **Fuera los datos reales de terceros del repositorio** (#108): emails, nombres de cliente y rutas de usuario en ficheros versionados, sustituidos por valores ficticios.

## 🔧 Correcciones

- **`klaus-fix-pseudonymization` da diagnósticos reales** (#110). Antes leía claves de `config.json` que el proxy no usa y siempre avisaba de que no había patrones. Ahora usa `pseudo_ran`, separa las peticiones sin cuerpo y comprueba la SALT, `hosts`, las reglas y `ANTHROPIC_PSEUDO_ENABLE`.
- **`install.sh` acepta Python ≥ 3.10** (#101), no solo 3.13. Si falta `python3-venv`, dice qué paquete instalar. Probado de principio a fin en Debian 13 (Python 3.13) y Ubuntu 24.04 (Python 3.12).
- **El menú `klaus` usa el Python del venv** (#103). Antes fallaba con «No module named Klaus_proxy_local».

## 📚 Documentación (#98)

Revisada contra la funcionalidad real:

- **Reescritos:** inicio rápido, guía de uso, troubleshooting, arquitectura y diagnóstico de pseudonimización.
- **Corregidos:** runbook, README y el resto de guías.
- **Archivados en `docs/archive/`:** once documentos de versiones pasadas.

En esta versión se documentan además el hook, el wrapper y el addon de passthrough en el README, el inicio rápido, la guía de uso, la arquitectura, el runbook y el troubleshooting.

## 🗑️ Eliminado

- **`claude-proxy --monitor`** (#103). El monitor TUI se eliminó en v0.3.3 y la opción solo imprimía un aviso.

## 🔬 Verificación

- **Passthrough probado con un `mitmdump` real** y una CA que el sistema no conoce:
  - pypi.org y github.com responden 200 con su certificado real y quedan como `TÚNEL` en el log.
  - api.anthropic.com se sigue descifrando: sin la CA del proxy da error de certificado y con ella responde la API.
- **Hook ejecutado en zsh y bash:** arranca el proxy si falta, exporta las variables, y `klaus-off`/`klaus-on` funcionan. En fish solo se ha revisado la sintaxis.
- **`claude-with-proxy`:** sin proxy se niega a lanzar `claude`; con el proxy escuchando lo lanza con `HTTPS_PROXY` y la CA.

## 🧪 Calidad

- 699 tests passed, 3 skipped (+33 desde v0.5.2). CI en Python 3.10, 3.11, 3.12 y 3.13.

## 📝 Limitaciones conocidas

- El aprendizaje de org/repo por petición sigue funcionando solo en los modos de permisos `auto` y `plan` (#68).
- El hook de fish no se ha ejecutado en un fish real.

**Changelog completo:** [`v0.5.2...v0.6.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.5.2...v0.6.0) · [CHANGELOG](../CHANGELOG.md)
