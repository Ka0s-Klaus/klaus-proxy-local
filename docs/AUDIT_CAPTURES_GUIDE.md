# 🔍 Auditoría de Payloads: Guía Completa

**Objetivo:** Revisar todos los payloads capturados en `captures/original/` y `captures/sent/` para identificar valores sensibles que deberían estar pseudonimizados pero no están en el vault.

**Estado Actual:**
- 📁 **18,043 payloads** capturados (original/ + sent/)
- 🔐 **259 valores** en vault (.pseudonym_vault.json)
- ✅ **465 tests** pasando

---

## 📋 Flujo de Auditoría

### Paso 1: Estadísticas y Resumen (`--stats`)

**Comando:**
```bash
python3 audit_captures.py --stats
```

**Qué hace:**
- Muestra cantidad de payloads en original/ y sent/
- Escanea primeros 100 payloads para detectar patrones sensibles
- Clasifica por tipo: emails, IPs, rutas, API keys, UUIDs, etc.

**Ejemplo de salida:**
```
📊 CAPTURE AUDIT STATISTICS
========================================

📁 Original payloads:      9,021
📁 Sent payloads:         9,021
🔐 Vault entries:         259

🔍 Analyzing first 100 payloads for sensitive patterns...

Patterns found in sample:
  email          45 occurrences
  path           23 occurrences
  ip             18 occurrences
  uuid           12 occurrences
  api_key         3 occurrences
```

**Interpretación:**
- Si hay muchos emails/IPs en la muestra → probablemente necesites revisar coverage del vault
- Si hay pocos → vault cubre bien los patrones principales

---

### Paso 2: Detección de Fugas (`--find-leaks`)

**Comando:**
```bash
python3 audit_captures.py --find-leaks
```

**Qué hace:**
- Escanea payloads en `sent/` buscando valores sensibles
- Valida que NO sean pseudónimos (pseudónimos empiezan con `id_`, `email_`, `ip_`, etc.)
- Reporta qué valores reales se filtraron (NO deberían estar)

**Ejemplo de salida:**
```
🚨 LEAK DETECTION (sensitive patterns in sent/)
========================================

Scanning 100 sent payloads...

⚠️  Found 5 potential leaks:

  email        | soporte@cliente-x.example
  ip           | 160.79.104.10
  path         | /Users/<usuario>/proyectos
  email        | equipo@cliente-x.example
  uuid         | 550e8400-e29b-41d4-a716-446655440000
```

**Significado:**
- ✅ Si **0 leaks** → Pseudonimización funcionando perfectamente
- ⚠️ Si hay **leaks** → puede haber valores que no se pseudonimizaron. Es una búsqueda por patrones sobre una muestra: revisa la lista, porque da falsos positivos.

**Qué hacer si son valores reales:**
```bash
# Opción A: a mano, en ~/.klaus-proxy/config.json
#   "pseudo_word_literals": ["cliente-x"]      ← tokens (frontera de palabra)
#   "pseudo_literals": ["Cliente Uno S.A."]    ← con espacios o barras

# Opción B: las fugas detectadas por --find-leaks (pide confirmación)
python3 auto_add_detected_leaks.py --dry-run
python3 auto_add_detected_leaks.py
```

Después, **reinicia `claude-proxy`**. Añadir un valor solo al vault no lo protege: tiene que estar en las reglas de `config.json`.

---

### Paso 3: Análisis de Cobertura del Vault (`--patterns`)

**Comando:**
```bash
python3 audit_captures.py --patterns
```

**Qué hace:**
- Desglose completo del vault por tipo de dato
- Muestra emails, IPs, rutas, orgs, identidades almacenadas
- Identifica qué categorías están bien cubiertas y cuáles no

**Ejemplo de salida:**
```
🔐 VAULT COVERAGE ANALYSIS
========================================

Vault breakdown by type:

  email          111 entries
              → noreply@anthropic.com
              → soporte@cliente-x.example
              → equipo@cliente-x.example
              → ... and 108 more

  ip             42 entries
              → 34.144.244.100
              → 160.79.104.10
              → 127.0.0.1
              → ... and 39 more

  path           45 entries
              → ~/proyectos/cliente-x-b2b
              → /Users/usuario
              → ... and 43 more

  org            15 entries
              → acme-global-delivery
              → cliente-x-b2b
              → ... and 13 more

  id             28 entries
              → usuario_empresa
              → usuario
              → ... and 26 more

  other          18 entries
```

**Interpretación:**
- Si una categoría tiene muy pocos valores → probablemente falten patrones
- IPs: 42 valores = bien cubierto
- Emails: 111 valores = excelente cobertura
- Rutas: 45 valores = bueno

---

### Paso 4: Revisión Interactiva (`--review`)

**Comando:**
```bash
python3 audit_captures.py --review
```

**Qué hace:**
- Abre revisión lado a lado: `original/` vs `sent/`
- Muestra valores en original que desaparecen en sent/ (fueron pseudonimizados)
- Permite validar manualmente si se pseudonimizó correctamente

**Controles:**
- `[A]` Approve — Pseudonimización correcta, continúa
- `[S]` Skip — No es sensible, ignora
- `[C]` Copy — Copia el valor (para analizar después)
- `[Q]` Quit — Termina revisión

**Ejemplo:**
```
[1/50] msg_20260905_143022.json
  Potentially sensitive in original but NOT in sent:
    • ana.garcia@empresa.example
      → NOT in vault. Add? (A/S/C)
    • ~/proyectos/cliente-x-b2b
      → Already in vault ✓
    • equipo@cliente-x.example
      → NOT in vault. Add? (A/S/C)
```

---

## 🎯 Flujo Recomendado (Paso a Paso)

### Para Primera Auditoría Completa

```bash
# 1. Ver panorama general
python3 audit_captures.py --stats

# 2. Buscar problemas críticos (fugas)
python3 audit_captures.py --find-leaks

# 3. Analizar cobertura actual
python3 audit_captures.py --patterns

# 4. Revisión interactiva de muestras
python3 audit_captures.py --review
```

### Ejemplo Completo:

```bash
cd ~/proyectos/klaus-proxy-local

# Terminal 1: Ver estadísticas
python3 audit_captures.py --stats
# Output: 9,021 payloads, 259 vault entries, 45 emails encontrados

# Terminal 1: Buscar fugas reales
python3 audit_captures.py --find-leaks
# Output: ✅ No obvious leaks detected (EXCELENTE)

# Terminal 1: Analizar cobertura
python3 audit_captures.py --patterns
# Output: Emails 111, IPs 42, Paths 45 (buena cobertura)

# Terminal 1: Revisar muestras interactivas
python3 audit_captures.py --review
# Output: Revisa primeros 50 payloads lado a lado
```

---

## 🔧 Si Encuentras Valores Faltantes

Un valor real que aparece en `sent/` salió sin pseudonimizar porque ninguna regla lo reconoce. Protégelo:

```bash
# Opción A: a mano, en ~/.klaus-proxy/config.json
#   "pseudo_word_literals": ["cliente-x"]      ← tokens (frontera de palabra)
#   "pseudo_literals": ["Cliente Uno S.A."]    ← con espacios o barras

# Opción B: las fugas detectadas por --find-leaks (pide confirmación)
python3 auto_add_detected_leaks.py --dry-run
python3 auto_add_detected_leaks.py
```

Después, **reinicia `claude-proxy`**. Añadir un valor solo al vault no lo protege: tiene que estar en las reglas de `config.json`.

Para secretos de una carpeta de tu disco (claves, tokens, `.env`), usa `python3 scripts/add_to_vault.py ~/proyectos/mi-repo --review` ([guía](./ADD_TO_VAULT_AUTOMATIC.md)).

Comprueba el resultado en peticiones **nuevas** con `python3 src/anthropic_pair_verify.py`: las ya enviadas no cambian.

---

## 📊 Interpretación de Resultados

### Escenario A: "0 Leaks, 259 Vault Entries"
```
✅ PERFECTO
- No hay fugas de valores sensibles en sent/
- Cobertura del vault es completa
- Ninguna fuga detectada en la muestra

Acción: confirmar con python3 src/anthropic_pair_verify.py (sin muestreo)
```

### Escenario B: "5 Leaks Detected"
```
⚠️ ACCIÓN REQUERIDA
- Algunos valores sensibles se filtraron en sent/
- NO debería ocurrir (bug potencial o configuración incompleta)

Acción:
1. Identifica qué valores se filtraron
2. Añádelos manualmente al vault
3. Re-ejecuta audit para verificar
4. Investiga por qué se filtraron (revisar regex patterns)
```

### Escenario C: "Low Vault Coverage"
```
⚠️ MEJORA SUGERIDA
- Vault tiene entradas para patrones comunes
- Pero puede haber valores "raros" no capturados

Acción:
1. Aumenta coverage de patrones (Tier 1, Tier 2, Tier 3)
2. Añade valores "edge case" encontrados
3. Re-test con full captures/
```

---

## 🔐 Seguridad: Qué NO Revisar Directamente

⚠️ **NUNCA hagas esto:**
```bash
# ❌ NO: Ver vault values completo (contiene valores REALES)
cat captures/.pseudonym_vault.json | head -20

# ❌ NO: Copiar vault a repositorio público
git add captures/.pseudonym_vault.json  # NEVER!

# ❌ NO: Distribuir output de audit_captures.py si contiene valores reales
```

✅ **SIEMPRE:**
```bash
# ✅ SÍ: Los scripts muestran solo primeros 50 chars
# ✅ SÍ: Vault está en .gitignore (nunca se versiona)
# ✅ SÍ: Output de audit va a archivo local (no repositorio)
```

---

## 📝 Checklist: Después de Auditoría

```
Después de ejecutar audit_captures.py:

□ Documentación:
  ☐ Registra fecha de auditoría
  ☐ Nota: "X payloads revisados, Y leaks encontrados"
  ☐ Vault: "Z entries, cobertura > 95%"

□ Correcciones (si hay leaks):
  ☐ Identifica valores filtrados
  ☐ Añádelos a vault (scripts/add_to_vault.py)
  ☐ Re-ejecuta audit para verificar
  ☐ Documenta qué se corrigió

□ CI/CD:
  ☐ Considera: pytest integration tests + audit in CI
  ☐ Semanal o pre-release: Ejecutar audit_captures.py

□ Release:
  ☐ Si cero leaks: OK para producción
  ☐ Si hay leaks: Fix primero, audit después, LUEGO release
```

---

## 🚀 Ejemplos Prácticos

### Ejemplo 1: Auditoría Rápida (5 minutos)
```bash
cd ~/proyectos/klaus-proxy-local

# 1. Estadísticas
python3 audit_captures.py --stats
# → Output: Resumen de capturados

# 2. Detectar leaks críticos
python3 audit_captures.py --find-leaks
# → Output: ✅ No leaks (o ⚠️ N leaks found)

echo "✅ Audit complete"
```

### Ejemplo 2: Auditoría Profunda (20 minutos)
```bash
# 1. Todo lo anterior +
python3 audit_captures.py --patterns
# → Output: Desglose por tipo de dato

# 2. Revisar muestras
python3 audit_captures.py --review
# → Proceso interactivo, 50 payloads

# 3. Si hay valores reales: añadirlos a config.json o
python3 auto_add_detected_leaks.py   # y reiniciar claude-proxy

# 4. Verificar nuevamente
python3 audit_captures.py --find-leaks
```

### Ejemplo 3: Integración Automated
```bash
# En GitHub Actions (.github/workflows/audit.yml):
- name: Audit captures for leaks
  run: |
    python3 audit_captures.py --stats > audit_report.txt
    python3 audit_captures.py --find-leaks >> audit_report.txt
    python3 audit_captures.py --patterns >> audit_report.txt
    if grep -q "potential leaks" audit_report.txt; then
      echo "⚠️  Leaks detected in audit"
      exit 1
    fi

- name: Upload audit report
  uses: actions/upload-artifact@v3
  with:
    name: audit_report
    path: audit_report.txt
```

---

## 📚 Archivos Relacionados

| Archivo | Propósito |
|---------|-----------|
| **audit_captures.py** | Script de análisis (este archivo) |
| **scripts/add_to_vault.py** | Añadir valores al vault |
| **scripts/inspect_vault.py** | Inspeccionar vault (búsquedas) |
| **captures/original/** | Payloads reales (SIN pseudonimizar) |
| **captures/sent/** | Payloads enviados (pseudonimizados) |
| **captures/.pseudonym_vault.json** | Mapeo real ↔ pseudónimo |

---

## ✅ Done!

Una vez hayas ejecutado todos los pasos:

1. ✅ Conoces cantidad exacta de payloads y vault entries
2. ✅ Verificas que NO hay fugas en sent/
3. ✅ Analizas cobertura por tipo de dato
4. ✅ Revisas muestras interactivamente si necesario
5. ✅ Añades valores faltantes si los encuentras

**Klaus Proxy Local está AUDITADO y SEGURO** 🔐
