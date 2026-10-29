# 🔧 Diagnosticar la pseudonimización

> Qué hacer si sospechas que algo ha salido sin pseudonimizar. Hay dos preguntas distintas y una herramienta para cada una.

| Pregunta | Herramienta |
| --- | --- |
| ¿**Pasaron** todas las peticiones por el pseudonimizador? | `klaus-fix-pseudonymization` |
| ¿Ha **salido** algún valor real en lo enviado? | `python3 src/anthropic_pair_verify.py` (desde el clon) |

Una petición puede pasar por el pseudonimizador y aun así llevar un valor real, si ninguna regla lo reconoce: por eso hacen falta las dos.

---

## 1️⃣ ¿Pasaron todas por el pseudonimizador?

```bash
klaus-fix-pseudonymization
```

```
📊 PAYLOAD STATUS
  Total Payloads:             3625
  Processed by pseudonymizer: 3059 (84.4%)
  Without body (GET…):        566 (15.6%)
  NOT processed (with body):  0 (0.0%)

⚙️  CONFIGURATION
  ANTHROPIC_PSEUDO_ENABLE:    1 (this shell)
  SALT Set:                   True
  Audited hosts:              api.anthropic.com
  Custom rules:               7 (pseudo_literals + pseudo_word_literals + pseudo_patterns)

💡 RECOMMENDATIONS
✅ Every request with a body went through the pseudonymizer
```

- **Processed:** el pseudonimizador revisó la petición, haya tenido que sustituir algo o no.
- **Without body:** peticiones GET y similares; no hay nada que pseudonimizar.
- **NOT processed (with body):** lo que hay que investigar. Lo normal es 0.

Si hay peticiones sin procesar:

```bash
klaus-fix-pseudonymization --show-payloads    # cuáles, a qué host y ruta
klaus-fix-pseudonymization --show-config      # config.json (la SALT sale oculta)
```

| Causa | Cómo se ve | Solución |
| --- | --- | --- |
| El proxy se arrancó con `ANTHROPIC_PSEUDO_ENABLE=0` | Peticiones procesadas pero sin cambios, o el aviso en las recomendaciones | Reinicia `claude-proxy` sin esa variable |
| Host que no está en `hosts` y cuya ruta no es de LLM | Host distinto de `api.anthropic.com` | Añádelo a `hosts` de `config.json` y reinicia `claude-proxy` |
| Capturas anteriores al campo `pseudo_ran` (#38) | Fechas antiguas | Nada: no se puede saber a posteriori |

> Si el pseudonimizador **no está cargado**, el guardián bloquea la petición con un 502 y no sale: no aparece como «no procesada», sino como bloqueada en el log.

---

## 2️⃣ ¿Ha salido algún valor real?

```bash
python3 src/anthropic_pair_verify.py               # todos los pares original ↔ sent
python3 src/anthropic_pair_verify.py <fichero>     # un par
python3 src/anthropic_pair_verify.py --survivors   # tokens del original que llegaron intactos al sent
```

Marca cada valor real que reaparece en lo enviado y la capa que lo detectó (email, IPv4, ruta, identidad, org, `pattern`, `dir`, vault). Detalle en el [runbook](./anthropic-audit-proxy.md).

### Si sale un valor real

Ninguna regla lo reconoce. Añádelo a `~/.klaus-proxy/config.json` y **reinicia `claude-proxy`**:

```json
{
  "pseudo_word_literals": ["cliente-x", "PRJ-2041"],
  "pseudo_literals": ["Cliente Uno S.A."]
}
```

- `pseudo_word_literals`: solo como palabra completa; para tokens.
- `pseudo_literals`: en cualquier parte del texto; para valores con espacios o barras.
- Para un patrón (p. ej. todos los `CLIENTE-1234`), usa `pseudo_patterns` (ver [runbook](./anthropic-audit-proxy.md)).
- Añadirlo **solo al vault** no sirve: el vault solo guarda el seudónimo de lo que ya casa con una regla.

Casos frecuentes:

| Lo que sale | Por qué | Solución |
| --- | --- | --- |
| El org/repo de un proyecto | `claude-proxy` no se arrancó desde ese repo y el modo de permisos no es `auto` ni `plan` | Arranca `claude-proxy` desde el repo, o añádelo a `pseudo_word_literals` |
| Un nombre de carpeta suelto | El vault aún no la conoce, o es corto (< 5) o genérico | Añádelo a `pseudo_word_literals` |
| Un valor que antes salió | Lo ya enviado no cambia, y una sesión abierta lo reenvía en su historial | Abre una sesión nueva de Claude Code |

Comprueba el resultado en peticiones **nuevas**.

---

## 🔗 Relacionado

- [Solución de problemas](./TROUBLESHOOTING.md)
- [Guía de uso](./USER_GUIDE.md): qué se protege y cómo añadir valores
- [Audit dashboard](./reports/web/README.md)
