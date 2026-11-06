# Klaus Proxy Local v0.10.0

**Fecha:** 2026-11-06 · **Anterior:** v0.9.0

Release **minor** con endurecimiento de seguridad (hosts de LLM de proyecto), la interfaz `klaus-alerts` para revisar los avisos del centinela y el centinela de fugas con recarga en caliente de reglas. Incluye también los cambios de la versión 0.9.1, que existió en el código pero nunca se publicó como release.

## ⬆️ Actualizar

```bash
git pull && ./install.sh
klaus-leak-report --drill   # comprueba la instalación: debe salir todo ✅
```

Reinicia `claude-proxy` si cambió el código del addon (el proxy usa una copia de los addons). La recarga de reglas no lo necesita.

`config.json`, la SALT, el vault y las capturas se conservan.

## 🔐 Seguridad

### 🚧 Hosts de LLM de proyecto sin aprobar (#193)

Los hosts de `ANTHROPIC_BASE_URL` que aparecen en `.claude/settings.json` o `.claude/settings.local.json` de tus repos (`projects_dirs`) ya no se dejan pasar sin auditar.

- El proxy responde **403** y avisa en el log, una vez por host.
- Para usarlo, añade el host a `hosts` en `config.json`.
- La configuración se relee cada 60 s, sin reiniciar.
- **Limitación:** solo cubre los repos de `projects_dirs`.

## ✨ Novedades

### 🖥️ `klaus-alerts`: revisar los avisos del centinela (#189)

Comando aparte que muestra en tiempo real los avisos de `alerts.jsonl`, agrupados por sesión.

| Tecla | Acción |
| --- | --- |
| `a` | Aprobar |
| `f` | Falso positivo |
| `s` | Ignorar en la sesión |
| `v` | Ver contexto (solo en pantalla) |
| `c` | Silenciar categoría |

El valor se recupera de la captura local y nunca se guarda. Nueva clave `sentinel_silenced_categories` en `config.json`. Decisiones en [ADR-002](./decisions/ADR-002-centinela-klaus-alerts.md).

### 🛡️ Centinela de fugas y recarga en caliente de reglas (#187)

- Un dato nuevo sin regla que aparece en una petición genera un aviso tras el envío, agrupado por sesión y sin valores en claro (`~/.klaus-proxy/alerts.jsonl`).
- Umbral MEDIUM por defecto, configurable con `sentinel_min_confidence`.
- Las reglas y el vault se recargan cuando cambian en disco: una regla aprobada se aplica en la siguiente petición sin reiniciar `claude-proxy`.
- `klaus-leak-report --drill` comprueba también el centinela.

### 🔬 Spike del centinela de fugas (#185)

`scripts/spike_centinela.py` mide, en solo lectura, el coste (p95 ≈ 2 ms por petición) y el ruido de un centinela que avisaría de datos nuevos tras cada envío. Con umbral MEDIUM, 82 avisos sin cubrir en 30 días; los 9 HIGH revisados a mano son datos sensibles reales. Informe: [spike-centinela.md](./reports/spike-centinela.md).

## 🐛 Correcciones

- **`main` vuelve a estar en verde** (#182). El CI fallaba en lint y en los tests de versión. Ahora esos tests comparan `__version__` con `pyproject.toml`, así que no hay que tocarlos en cada release. `requires-python` vuelve a `>=3.10` (#175) y `requirements-dev.txt` instala desde `pyproject.toml`.
- **`klaus-leak-report` perdía capturas al quitar un proyecto** (#180). La caché no se invalidaba al cambiar la lista de proyectos. Ahora la clave de caché incluye una huella de los proyectos y sus remotes. **La primera ejecución tras actualizar recalcula todas las capturas.**

## 📚 Documentación

- CHANGELOG `[Unreleased]` y guía de usuario actualizados con el aviso de hosts de proyecto (#193).

## 🔬 Verificación

| Comprobación | Resultado |
| --- | --- |
| `pytest` (Python 3.13, venv temporal) | 883 passed, 2 skipped |
| `ruff check .` | ✅ |
| `black --check` | ✅ |
| `klaus-leak-report --drill` en la instalación del autor | Pendiente de ejecutar tras instalar |

## 🧪 Calidad

- CI en Python 3.10, 3.11, 3.12 y 3.13.

**Changelog completo:** [`v0.9.0...v0.10.0`](https://github.com/Ka0s-Klaus/klaus-proxy-local/compare/v0.9.0...v0.10.0) · [CHANGELOG](../CHANGELOG.md)
