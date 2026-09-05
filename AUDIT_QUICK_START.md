# ⚡ Auditoría Rápida de Captures (5 minutos)

**Tienes 18,043 payloads capturados. ¿Hay valores sensibles sin pseudonimizar?**

## 🚀 Ejecución Rápida

```bash
cd /Users/asantacana/proyectos/klaus-proxy-local

# Paso 1: Ver panorama
python audit_captures.py --stats

# Paso 2: Buscar FUGAS CRÍTICAS (valores reales en sent/)
python audit_captures.py --find-leaks

# Paso 3: Analizar cobertura del vault
python audit_captures.py --patterns

# Paso 4 (Opcional): Revisar muestras interactivas
python audit_captures.py --review
```

**Tiempo total: 2-5 minutos**

---

## 📊 Qué Esperar

### Si todo está bien (esperado):
```
✅ No obvious leaks detected in sample
✅ Vault: 259 entries covering emails (111), IPs (42), paths (45)
✅ Pseudonimización: 100% funcionando
```

### Si hay problemas:
```
⚠️  Found 5 potential leaks
  email        | dev@masorange.example
  ip           | 160.79.104.20
  path         | /sensitive/path
```

**→ Acción:** Añade al vault
```bash
python scripts/add_to_vault.py . --manual
```

---

## 🎯 Flujos por Caso

### Caso 1: "Solo quiero verificar rápido"
```bash
python audit_captures.py --find-leaks
# Si output = "✅ No leaks" → TODO OK
```

### Caso 2: "Necesito saber qué valores tengo en vault"
```bash
python audit_captures.py --patterns
# Ver desglose: emails, IPs, rutas, orgs, identidades
```

### Caso 3: "Sospecho que hay valores sin pseudonimizar"
```bash
python audit_captures.py --stats
python audit_captures.py --review
# Revisar interactivamente 50 payloads
```

### Caso 4: "Encontré valores que faltan, añádelos"
```bash
# Opción A: Manual
python scripts/add_to_vault.py . --manual
# Ingresa valor cuando te pida

# Opción B: Desde archivo
echo "dev@example.com" > new_values.txt
python scripts/add_to_vault.py . --from-file new_values.txt --review

# Opción C: Automático desde captures
python scripts/add_to_vault.py . --scan-captures --review
```

---

## ✅ Checklist Básico

```
[ ] Ejecuté audit_captures.py --find-leaks → ✅ No leaks
[ ] Ejecuté audit_captures.py --patterns → Visto cobertura
[ ] Si hay leaks: Añadí valores al vault con add_to_vault.py
[ ] Re-ejecuté audit → Verificar fix
```

---

## 📁 Archivos

- **audit_captures.py** — Script análisis (este directorio)
- **AUDIT_CAPTURES_GUIDE.md** — Guía completa y detallada
- **scripts/add_to_vault.py** — Herramienta para añadir valores

¿Necesitas ayuda con algo específico? Pregunta aquí o consulta AUDIT_CAPTURES_GUIDE.md
