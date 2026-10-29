# ⚡ Auditoría Rápida de Captures (5 minutos)

**Tienes 18,043 payloads capturados. ¿Hay valores sensibles sin pseudonimizar?**

## 🚀 Ejecución Rápida

```bash
cd ~/proyectos/klaus-proxy-local

# Paso 1: Ver panorama
python3 audit_captures.py --stats

# Paso 2: Buscar FUGAS CRÍTICAS (valores reales en sent/)
python3 audit_captures.py --find-leaks

# Paso 3: Analizar cobertura del vault
python3 audit_captures.py --patterns

# Paso 4 (Opcional): Revisar muestras interactivas
python3 audit_captures.py --review
```

**Tiempo total: 2-5 minutos**

---

## 📊 Qué Esperar

### Si todo está bien (esperado):
```
✅ No CRITICAL leaks detected in sample
```

### Si hay problemas:
```
⚠️  Found 5 potential leaks
  email        | equipo@cliente-x.example
  ip           | 160.79.104.20
  path         | /sensitive/path
```

**→ Acción:** revisa la lista: `--find-leaks` es una búsqueda por patrones sobre una muestra y da falsos positivos (p. ej. `python@3.13` como email). Si son valores reales, protégelos como en el [caso 4](#caso-4-encontré-valores-que-faltan-añádelos).

> La comprobación de referencia es `python3 src/anthropic_pair_verify.py`: compara cada petición original con lo enviado, sin muestreo.

---

## 🎯 Flujos por Caso

### Caso 1: "Solo quiero verificar rápido"
```bash
python3 audit_captures.py --find-leaks
# Si output = "✅ No leaks" → TODO OK
```

### Caso 2: "Necesito saber qué valores tengo en vault"
```bash
python3 audit_captures.py --patterns
# Ver desglose: emails, IPs, rutas, orgs, identidades
```

### Caso 3: "Sospecho que hay valores sin pseudonimizar"
```bash
python3 audit_captures.py --stats
python3 audit_captures.py --review
# Revisar interactivamente 50 payloads
```

### Caso 4: "Encontré valores que faltan, añádelos"
```bash
# Opción A: a mano, en ~/.klaus-proxy/config.json
#   "pseudo_word_literals": ["cliente-x", "PRJ-2041"]   ← tokens (frontera de palabra)
#   "pseudo_literals": ["Cliente Uno S.A."]             ← con espacios o barras

# Opción B: las fugas que ha detectado --find-leaks (pide confirmación)
python3 auto_add_detected_leaks.py --dry-run   # ver qué añadiría
python3 auto_add_detected_leaks.py

# Opción C: secretos de una carpeta de tu disco
python3 scripts/add_to_vault.py ~/proyectos/mi-repo --review
```

En los tres casos, **reinicia `claude-proxy`**: las reglas de `config.json` se cargan al arrancar. Añadir un valor solo al vault no lo protege.

---

## ✅ Checklist Básico

```
[ ] Ejecuté audit_captures.py --find-leaks → ✅ No leaks
[ ] Ejecuté audit_captures.py --patterns → Visto cobertura
[ ] Si hay leaks reales: los añadí a config.json y reinicié claude-proxy
[ ] Lo comprobé en peticiones nuevas con src/anthropic_pair_verify.py
```

---

## 📁 Archivos

- **audit_captures.py** — Script análisis (este directorio)
- **AUDIT_CAPTURES_GUIDE.md** — Guía completa y detallada
- **scripts/add_to_vault.py** — Herramienta para añadir valores

¿Necesitas ayuda con algo específico? Pregunta aquí o consulta AUDIT_CAPTURES_GUIDE.md
