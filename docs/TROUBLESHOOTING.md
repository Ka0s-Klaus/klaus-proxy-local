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

**Con `klaus-setup`, falla el HTTPS de otras herramientas** (pip, git, contenedores…): no debería, porque solo se descifran los hosts de la API y el resto va en túnel con su certificado real. Comprueba en `~/.klaus-proxy/logs/proxy.log` que aparece `🔓 Se descifra solo: …` al arrancar y `TÚNEL host:puerto` para esa herramienta. Si el host que falla aparece en la lista de descifrados, o tienes `"intercept_all": true`, esa herramienta necesita confiar en la CA del proxy; mientras tanto, `klaus-off` en esa terminal.

**Un gateway LLM propio no se seudonimiza:** si no está en `hosts` de `config.json` ni en `ANTHROPIC_BASE_URL`, va en túnel sin descifrar. Añádelo a `hosts` y reinicia `claude-proxy`.

**Con `klaus-setup`, el proxy no arrancó:** mira `~/.klaus-proxy/logs/autostart.log`.

---

## 📭 No hay capturas

- Solo se capturan los hosts de `hosts` (que además se pseudonimizan) y de `capture_only_hosts` (sin pseudonimizar) en `config.json`; por defecto, `api.anthropic.com`. Si usas un gateway propio, añádelo a `hosts`.
- Si `ANTHROPIC_CAPTURE_HOSTS` está exportada en la terminal donde arrancas el proxy, **sustituye** a `hosts` de `config.json` para la captura. Si no la necesitas: `unset ANTHROPIC_CAPTURE_HOSTS` y reinicia `claude-proxy`.
- Para ver qué tráfico pasa por el proxy sin capturarse, mira la sección «Hosts no capturados» del dashboard (`klaus-audit-dashboard --open`).
- Las capturas van a `~/.klaus-proxy/captures/original/` y `sent/`. El log muestra una línea `[anthropic-capture] … → sent/<fichero>` por petición.

---

## 🗑️ Han desaparecido capturas antiguas

Desde la retención de capturas (#132), al arrancar `claude-proxy` se borran los pares `original/` + `sent/` de más de **30 días**; la terminal lo indica con `🧹 Retención de capturas: …`. Lo borrado no se puede recuperar.

- Para conservar más: `capture_retention_days` en `config.json` (`0` = sin límite).
- Para guardar capturas concretas: muévelas a `~/.klaus-proxy/captures/archive/`, que no se toca.
- Antes de reiniciar, `klaus-prune-captures --dry-run` muestra qué se borraría.

---

## ❓ `anthropic_pair_verify.py` dice «No hay pares que verificar»

Si además indica que hay capturas sin `original/`, es que `capture_originals` está a `false` en `config.json`: solo se guarda lo enviado, y sin originales no hay comparación por pares. Vuelve a ponerlo a `true` (o quítalo) y reinicia `claude-proxy`; las capturas nuevas se podrán verificar.

---

## 🧩 Quiero auditar los conectores MCP de claude.ai

Pasan por `mcp-proxy.anthropic.com`. Si lo añades a `hosts`, los conectores recibirán seudónimos y pueden fallar (una búsqueda por un valor real no encontrará nada). Para auditarlos sin tocar la petición, añádelo a `capture_only_hosts`:

```json
"capture_only_hosts": ["mcp-proxy.anthropic.com"]
```

Reinicia `claude-proxy`. Las capturas llevan `"capture_only": true`, los secretos redactados y no cuentan como fugas.

---

## 📝 El log dice «config.json ilegible»

`[anthropic-pseudo] WARN config.json ilegible (…)`: `~/.klaus-proxy/config.json` no se puede leer o no es JSON válido, normalmente por una edición a mano (una coma de más, comillas sin cerrar). **Mientras tanto no se aplican tus `pseudo_literals`, `pseudo_word_literals` ni `pseudo_patterns`**: solo las reglas integradas.

```bash
python3 -m json.tool ~/.klaus-proxy/config.json   # señala la línea del error
```

Corrígelo (o recupera una copia `config.json.bak-*` si la tienes) y reinicia `claude-proxy`.

---

## 🔁 He cambiado el código y el proxy sigue igual

`claude-proxy` ejecuta una **copia inmutable** de los addons, hecha al arrancar (`~/.klaus-proxy/addons/<hash>/`). Así un `git checkout` no cambia ni rompe el proxy en marcha. Para aplicar cambios, reinícialo **desde dentro de un repo**.

Lo mismo con `config.json`: las reglas nuevas (`pseudo_literals`, `pseudo_word_literals`…) se aplican al reiniciar.

---

## 🕵️ Un valor sale en claro

`python3 src/anthropic_pair_verify.py` (desde el clon) marca qué ha salido en claro y en qué capa.

- **Un valor tuyo** (cliente, código de proyecto): añádelo a `pseudo_word_literals` o `pseudo_literals` de `config.json` y reinicia `claude-proxy`. Ponerlo **solo en el vault no basta**.
- **El org/repo de un proyecto**: clónalo en la carpeta de proyectos y ejecuta `klaus-scan-repos` (o arranca `claude-proxy` desde ese repo), o añádelo a `pseudo_word_literals`. El aprendizaje por petición solo funciona en los modos de permisos `auto` y `plan`.
- **Un nombre de carpeta suelto** (sin ruta): se protege cuando el vault ya conoce la carpeta, tras aparecer una vez en una ruta; si es corto (< 5) o genérico, no.
- Lo que ya se envió no se puede deshacer; se puede archivar la evidencia (ver [runbook](./anthropic-audit-proxy.md)).

---

## ✅ He aprobado en `klaus-scan` y `config.json` no cambia

- **¿Has aprobado?** Hay que responder `Y` a `Review N finding(s)?` y pulsar `A` en cada hallazgo. Al terminar, el resumen dice `Approved for vault: N`. Sin terminal interactiva (lanzado por Claude Code) no se pregunta nada: usa `--approve-all` o lánzalo tú.
- **¿Falla con «ANTHROPIC_PSEUDO_SALT environment variable is required»?** Es anterior a la v0.8.0 (#156). Actualiza con `git pull && ./install.sh`.
- **Para comprobarlo:** la fecha de modificación de `~/.klaus-proxy/config.json` debe ser posterior a la aprobación, y `pseudo_word_literals` y `pseudo_literals` deben tener más entradas.
- **Después, reinicia `claude-proxy`.** Si lo reiniciaste antes de aprobar, las reglas nuevas aún no se aplican.

---

## 🔴 `klaus-leak-report` sigue en rojo con cobertura del 100 %

Es lo esperado justo después de aprobar reglas. El informe busca tus reglas actuales en las capturas antiguas, así que lo enviado antes de aprobarlas ahora cuenta como fuga. El proyecto sigue en 🔴 hasta que esas capturas superen los 30 días.

- **Para saber si hay fugas ahora:** mira solo las capturas con fugas posteriores al último reinicio de `claude-proxy` (última línea `🧩 Addons:` de `~/.klaus-proxy/logs/proxy.log`). Más detalle en la [guía de uso](./USER_GUIDE.md#cómo-leer-las-fugas-después-de-aprobar-reglas).
- **Si hay alguna posterior de categoría `org`:** puede ser el falso positivo de una regla que aparece dentro de otra palabra (#158).
- **Si hay otra posterior:** ver «Un valor sale en claro».

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
