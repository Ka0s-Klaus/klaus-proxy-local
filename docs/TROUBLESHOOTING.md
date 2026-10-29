# 🛠️ Solución de problemas

> Antes de nada, mira el log: `~/.klaus-proxy/logs/proxy.log` (una línea por petición, sin colores, rotado 5 MB × 5). La salida de la terminal de `claude-proxy` es la misma, con colores.

---

## 📦 Instalación

**`Python ≥3.10 requerido`**: instala Python 3.10 o superior. En macOS, `install.sh` ofrece instalar la 3.13 con Homebrew; en Debian/Ubuntu: `sudo apt install python3 python3-venv`.

**`No se pudo crear el venv … falta el módulo venv/ensurepip`**: en Debian/Ubuntu, instala el paquete que indica el mensaje (`sudo apt install python3.12-venv`, o `python3-venv`) y vuelve a ejecutar `./install.sh`.

**`claude-proxy: command not found`**: añade `~/.local/bin` al `PATH` (el instalador lo avisa con «NO está en PATH»):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc   # o ~/.bashrc
```

---

## ▶️ El proxy no arranca

**`Address already in use` en el puerto 8899**: ya hay otro `claude-proxy` (o un `mitmdump`) escuchando. El puerto es fijo.

```bash
lsof -i :8899          # quién lo usa
kill <PID>             # páralo (Ctrl+C si es tu otra terminal)
```

**Errores al cargar los addons**: `claude-proxy` muestra el commit de los addons cargados («🧩 Addons: …»). Si falta esa línea o sale un error de Python, revisa el log y vuelve a arrancar.

---

## 🔐 Certificados

**Claude Code: `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, `self signed certificate` o `certificate verify failed`**: esa terminal no confía en la CA del proxy.

```bash
source ~/.klaus-proxy/klaus-env.sh       # exporta NODE_EXTRA_CA_CERTS y el bundle de CAs
```

Si persiste, regenera la CA: para `claude-proxy`, borra `~/.mitmproxy/`, vuelve a arrancarlo (crea una CA nueva y regenera `klaus-env.sh` y `ca-bundle.pem`) y vuelve a hacer `source` en cada terminal.

**HTTPS falla fuera del proxy** (`pip`, `git`, `curl` contra otras webs) tras cargar `klaus-env.sh`: tienes un `klaus-env.sh` anterior a v0.5.0, que sustituía el almacén de CAs. Arranca `claude-proxy` una vez para regenerarlo y vuelve a hacer `source`.

---

## 🚧 Claude Code recibe un 502

Respuesta `502` con el texto **«klaus-proxy: request BLOQUEADA (fail-closed)»**: es el **guardián**. Ha bloqueado una petición que el pseudonimizador no procesó, para que no salga sin pseudonimizar.

- Busca en el log `[klaus-guard] BLOQUEADA` y el error anterior (fallo al cargar el addon, excepción…).
- Reinicia `claude-proxy`.

---

## 🔌 Claude Code no pasa por el proxy

No aparecen peticiones en el log ni capturas nuevas.

```bash
echo $HTTPS_PROXY       # en la terminal de Claude Code: debe ser http://127.0.0.1:8899
```

- `HTTPS_PROXY` solo afecta a la terminal donde lo exportas y a los procesos que arranques **después**. Reinicia `claude` tras exportarlo.
- Con `klaus-setup`, abre una terminal **nueva** tras ejecutarlo (o `exec $SHELL`). Si alguna vez usaste `klaus-off`, vuelve con `klaus-on`.

**Con `klaus-setup`, falla el HTTPS de otras herramientas** (pip, git, contenedores…): todo el HTTPS de la terminal pasa por el proxy. Las que no usan el bundle de `klaus-env.sh` no confían en su CA. Usa `klaus-off` en esa terminal.

**Con `klaus-setup`, el proxy no arrancó:** mira `~/.klaus-proxy/logs/autostart.log`.

---

## 📭 No hay capturas

- Solo se capturan y pseudonimizan los hosts de `hosts` en `config.json` (por defecto `api.anthropic.com`). Si usas un gateway propio, añádelo ahí o en `ANTHROPIC_CAPTURE_HOSTS`.
- Las capturas van a `~/.klaus-proxy/captures/original/` y `sent/`. El log muestra una línea `[anthropic-capture] … → sent/<fichero>` por petición.

---

## 🔁 He cambiado el código y el proxy sigue igual

`claude-proxy` ejecuta una **copia inmutable** de los addons, hecha al arrancar (`~/.klaus-proxy/addons/<hash>/`). Así un `git checkout` no cambia ni rompe el proxy en marcha. Para aplicar cambios, reinícialo **desde dentro de un repo**.

Lo mismo con `config.json`: las reglas nuevas (`pseudo_literals`, `pseudo_word_literals`…) se aplican al reiniciar.

---

## 🕵️ Un valor sale en claro

`python3 src/anthropic_pair_verify.py` (desde el clon) marca qué ha salido en claro y en qué capa.

- **Un valor tuyo** (cliente, código de proyecto): añádelo a `pseudo_word_literals` o `pseudo_literals` de `config.json` y reinicia `claude-proxy`. Ponerlo **solo en el vault no basta**.
- **El org/repo de un proyecto**: arranca `claude-proxy` desde ese repo, o añádelo a `pseudo_word_literals`. El aprendizaje por petición solo funciona en los modos de permisos `auto` y `plan`.
- **Un nombre de carpeta suelto** (sin ruta): se protege cuando el vault ya conoce la carpeta, tras aparecer una vez en una ruta; si es corto (< 5) o genérico, no.
- Lo que ya se envió no se puede deshacer; se puede archivar la evidencia (ver [runbook](./anthropic-audit-proxy.md)).

---

## 🧹 El vault tiene entradas que no son datos

Valores como `…`, `|` o `{user}` que entraron antes de v0.5.2. Con `claude-proxy` **parado**:

```bash
python3 scripts/prune_vault.py --dry-run
python3 scripts/prune_vault.py
```

Con el proxy en marcha no sirve: guarda su copia en memoria del vault y volvería a escribirlas.

---

## 🧪 Tests

- No hace falta exportar `ANTHROPIC_PSEUDO_SALT`: `tests/conftest.py` genera una SALT de prueba y aísla `config.json`.
- Plan de tests del dashboard en ⬜: no encontró pytest. Crea el `.venv` del repo ([entorno de desarrollo](./setup.md)) o instala `uv`.

---

## 🆘 Si nada de esto funciona

Abre una issue con la versión (`claude-proxy --version`), el sistema operativo, la versión de Python y las líneas relevantes del log, **sin datos reales**: https://github.com/Ka0s-Klaus/klaus-proxy-local/issues

Si es un problema de seguridad, sigue [SECURITY.md](../SECURITY.md) y no lo publiques.
