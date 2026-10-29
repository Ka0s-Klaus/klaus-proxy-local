# ⚡ Añadir al Vault — Quick Reference

## TL;DR

```bash
python3 scripts/add_to_vault.py /ruta/a/tu/carpeta
```

Los secretos se detectan y se añaden al vault **y** a las reglas de `~/.klaus-proxy/config.json`. **Reinicia `claude-proxy`** para que se apliquen (#99).

---

## Opciones (por frecuencia de uso)

| Caso | Comando |
|------|---------|
| **Auto-añadir CRITICAL** | `python3 scripts/add_to_vault.py /ruta` |
| **Ver qué haría (sin cambios)** | `python3 scripts/add_to_vault.py /ruta --dry-run` |
| **Revisar antes de añadir** | `python3 scripts/add_to_vault.py /ruta --review` |
| **Incluir HIGH + CRITICAL** | `python3 scripts/add_to_vault.py /ruta --high` |
| **Incluir TODO (CRITICAL+HIGH+MEDIUM)** | `python3 scripts/add_to_vault.py /ruta --all` |
| **Ver detalles** | `python3 scripts/add_to_vault.py /ruta --verbose` |
| **JSON output (scripts)** | `python3 scripts/add_to_vault.py /ruta --json` |

---

## Flujo Recomendado

```bash
# 1. Ver qué detectaría
python3 scripts/add_to_vault.py ./my-project --dry-run

# 2. Si te gusta, añadir
python3 scripts/add_to_vault.py ./my-project

# 3. Verificar qué se añadió
python3 scripts/inspect_vault.py --stats
```

---

## Qué Detecta (CRITICAL)

✅ AWS keys (AKIA)  
✅ GitHub tokens (ghp_)  
✅ Private keys (RSA, DSA, Ed25519)  
✅ API keys (sk-, sk_live_)  
✅ DB connections  
✅ URLs with credentials  
✅ + 15 más

---

## Más Información

- Full guide: `docs/ADD_TO_VAULT_AUTOMATIC.md`
- Inspect: `python3 scripts/inspect_vault.py --help`
- Scan (manual): `python3 scripts/add_to_vault.py --help`

**Version:** 0.3.0  
**Ready to use:** ✅
