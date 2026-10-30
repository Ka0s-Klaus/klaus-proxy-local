# Klaus Proxy Local v0.7.0

**Fecha:** 2026-10-30 · **Anterior:** v0.6.1

Release de control. Las capturas tienen por fin una retención, y **`claude-proxy` protege al arrancar todos los repos de tu carpeta de proyectos**, no solo el repo desde el que se lanza. El dashboard de auditoría muestra qué proyectos están bajo el paraguas del proxy.

## ⬆️ Actualizar

> ⚠️ **Esta versión borra capturas.** En el primer arranque de `claude-proxy` tras actualizar se borran los pares `original/` + `sent/` de **más de 30 días**. Si quieres conservarlos, haz una de estas dos cosas **antes de reiniciar**:
>
> - añade `"capture_retention_days": 0` (sin límite) u otro número de días a `~/.klaus-proxy/config.json`;
> - mueve lo que quieras guardar a `~/.klaus-proxy/captures/archive/`, que no se toca nunca.
>
> Para ver qué se borraría sin borrar nada: `klaus-prune-captures --dry-run` (tras `./install.sh`).

```bash
git pull && ./install.sh
```

1. **Decide la retención** (ver el aviso) y después **reinicia `claude-proxy`**. Al arrancar verás:
   - `🧹 Retención de capturas: 30 días · borrados N pares (…)`;
   - `🛡️  org/repo de N repos protegidos (T tokens, M nuevos)`.
2. **Si tus repos no cuelgan todos de la misma carpeta,** indícalas en `config.json`:

   ```json
   "projects_dirs": ["~/proyectos", "~/trabajo"]
   ```

`config.json`, la SALT, el vault y `captures/archive/` se conservan.

## 🧹 Retención de capturas (#132)

Cada petición lleva la conversación entera, así que las capturas crecen rápido (~1,5 MB por petición), y `original/` guarda datos reales en claro.

- **`capture_retention_days`** en `config.json`: por defecto `30`; `0` = sin límite.
- **Se aplica al arrancar `claude-proxy`**, o a mano con `klaus-prune-captures [--dry-run] [--days N]`.
- **Solo se borran pares de `original/` y `sent/`** con fecha en el nombre. El vault, `captures/archive/` y cualquier otro fichero no se tocan.
- **Si el borrado falla** (permisos, disco), el proxy arranca igualmente y lo avisa.
- **El dashboard de auditoría** muestra la retención activa, la captura más antigua y el último borrado.

### `capture_originals: false`

Para quien no quiera datos reales en claro en disco: solo se guarda `sent/`. Ocupa la mitad, pero **no hay verificación por pares**: `anthropic-pair-verify` explica por qué no encuentra pares, y el dashboard calcula los planes con `sent/`. Por defecto sigue en `true`.

## 🛡️ Todos tus repos protegidos al arrancar (#134)

Hasta ahora `claude-proxy` solo protegía el org/repo del repo desde el que arrancaba (#61), y el resto se aprendía por petición, solo en los modos `auto` y `plan` (#68). Un repo recién clonado que se listaba o se revisaba **desde otro repo** salía en claro.

Ahora, al arrancar:

- **Recorre `projects_dirs`** hasta 3 niveles (`~/proyectos/cliente-x/repo`). Sin `projects_dirs`, usa la carpeta padre del repo actual y las que ya están en `pseudo_patterns`. Nunca recorre el home ni `/`, y se salta los directorios ocultos, `node_modules`, `venv` y los enlaces simbólicos.
- **Lee todos los remotes** de cada repo, no solo `origin`, y añade su org/repo a `pseudo_word_literals`.
- **Identidad git propia del repo:** si un repo tiene un `user.email` o `user.name` local distinto del global, lo añade a `pseudo_literals`.
- **Los nombres genéricos** (`docs`, `api`…) no se añaden y se avisa, como hasta ahora.
- **Comando nuevo `klaus-scan-repos [--dry-run]`** para aplicarlo justo después de clonar; luego reinicia `claude-proxy`.

**La salida solo da recuentos.** El dashboard de arranque tampoco lista ya los org/repo protegidos: muestra cuántos hay. Esa salida puede acabar en el contexto del modelo.

## 📊 Dashboard: «🛡️ Proyectos protegidos» (#136)

Tarjeta nueva en el plan de Seguridad, con una fila por cada repo de la carpeta de proyectos:

| Columna | Qué muestra |
| --- | --- |
| Repo | Carpeta y org/repo de cada remote |
| Estado | ✅ Protegido · ✅ Sin remote · ⚠️ Nombre genérico · ❌ Falta proteger |
| Seudónimo | Lo que ve Anthropic, según el vault |
| Última petición | Última vez que el repo apareció en una petición (modos `auto` y `plan`) |

> ⚠️ **La tarjeta muestra los nombres reales de tus repos.** El informe es local (`informes/` no se versiona): no compartas el HTML tal cual.

## 🔬 Verificación en la instalación del autor

Comprobado solo con recuentos, sin mostrar nombres:

- **Antes de esta versión:** con 16 repos clonados en la carpeta de proyectos, 13 nombres de repo estaban sin proteger, y 8 de ellos ya habían salido en claro en un listado de remotes hecho desde otro repo.
- **Con #134:** los 16 repos quedan protegidos. En las peticiones posteriores al reinicio, los valores protegidos aparecen en `original/` y ninguno en `sent/`.
- **Con #136:** el dashboard da 16 de 16 repos protegidos.
- **Con #132:** la retención se aplicó al arrancar sin borrar nada, porque no había capturas de más de 30 días, y `original/` y `sent/` siguieron emparejadas.

## 🧪 Calidad

- 746 tests passed, 3 skipped (+28 desde v0.6.1). CI en Python 3.10, 3.11, 3.12 y 3.13.
- Los tests no tocan las capturas ni el `config.json` reales: hay fixtures que aíslan `ANTHROPIC_CAPTURE_DIR` y `config.json`, también para `klaus-scan-repos`.

## 📝 Limitaciones conocidas

- La «última petición» de la tarjeta y el aprendizaje de org/repo por petición solo funcionan en los modos de permisos `auto` y `plan` (#68).
- Un repo clonado fuera de `projects_dirs`, o a más de 3 niveles, se sigue protegiendo solo al arrancar desde él o por petición.
- **El proxy protege identificadores** (org/repo, usuario, email, rutas, tus reglas) y redacta credenciales. El contenido del código que se lee sale tal cual, salvo lo que casen tus reglas.

**Changelog completo:** [`v0.6.1...v0.7.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.6.1...v0.7.0) · [CHANGELOG](../CHANGELOG.md)
