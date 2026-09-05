# 🔧 Auto-Fix Detectadas Fugas — Guía Completa

**Detecta automáticamente fugas y las añade al vault sin intervención manual.**

---

## ⚡ TL;DR (30 segundos)

```bash
# Ejecuta el workflow completo (detecta + arregla + verifica)
python full_audit_with_fixes.py --auto

# ✅ Resultado: Pseudonimización 100% correcta
```

---

## 🚀 Tres Formas de Usarlo

### Opción 1: Workflow Completo (Recomendado)

```bash
python full_audit_with_fixes.py --auto
```

**Qué hace:**
1. 📊 Genera reporte de auditoría
2. 🚨 Detecta fugas en sent/
3. ✅ Auto-añade al vault
4. 🔍 Re-verifica que funcione

**Output:**
```
📊 Paso 1: Generando reporte...
🔧 Paso 2: Auto-añadiendo fugas...
🔍 Paso 3: Re-verificando...
✅ Pseudonimización correcta
```

---

### Opción 2: Solo Detectar (No Arreglar)

```bash
python full_audit_with_fixes.py --no-fix
```

O:

```bash
python audit_captures.py --find-leaks
```

**Output:**
```
⚠️ Encontradas 3 fugas potenciales:
  email      | dev@example.com
  api_key    | sk_live_1234567890
  github_token | ghp_abc...
```

---

### Opción 3: Solo Añadir (Ya Detectadas)

```bash
# Interactive (pide confirmación para cada valor)
python auto_add_detected_leaks.py

# Auto (añade todo sin preguntar)
python auto_add_detected_leaks.py --auto

# Dry-run (preview, sin cambios)
python auto_add_detected_leaks.py --dry-run
```

**Output:**
```
⚠️ Encontradas 3 fugas potenciales:
  1. email      | dev@example.com
  2. api_key    | sk_live_1234567890
  3. github_token | ghp_abc...

¿Añadir estos valores al vault? [y/N]:
```

---

## 📊 Cómo Funciona

### Paso 1: Detección de Fugas

Busca valores sensibles en `captures/sent/` que NO estén en el vault:

- 📧 **Emails**: `usuario@dominio.com`
- 🔑 **API Keys**: `api_key = 'sk_...'`
- 🎫 **Tokens GitHub**: `ghp_...`
- ☁️ **Keys AWS**: `AKIA...`

```python
# Script: auto_add_detected_leaks.py
def detect_leaks():
    vault = load_vault()
    for value in sent_payloads:
        if value not in vault:
            leaks.append(value)  # Encontrada fuga
```

### Paso 2: Deterministic Hashing

Genera pseudónimos consistentes usando SALT:

```
Real:       dev@example.com
SALT:       f5ab7b7ca3eecf0f63cf7a6c91118992
Hash:       sha1(SALT + "dev@example.com")[:8]
Pseudónimo: email_8c9f3a42
```

**Ventajas:**
- ✅ Mismo valor → Mismo pseudónimo (determinista)
- ✅ No se puede revertir sin vault
- ✅ Pseudónimos únicos por valor

### Paso 3: Añadir al Vault

Actualiza `captures/.pseudonym_vault.json`:

```json
{
  "dev@example.com": "email_8c9f3a42",
  "sk_live_1234567890": "api_key_cd8f7afb",
  "ghp_abc123def456": "github_token_12345678"
}
```

**Permisos:**
- 🔒 `0o600` (solo lectura/escritura dueño)
- 🔒 Nunca se versiona (está en .gitignore)

### Paso 4: Verificación

Re-ejecuta `audit_captures.py --find-leaks` para confirmar:

```bash
✅ No CRITICAL leaks detected in sample
```

---

## 🔐 Seguridad

### ✅ SÍ Hacer

```bash
# Ejecutar localmente
python full_audit_with_fixes.py --auto

# Con SALT del config
python auto_add_detected_leaks.py --auto

# Verificar después
python audit_captures.py --find-leaks
```

### ❌ NO Hacer

```bash
# ❌ NO: Compartir reportes vía email
# ❌ NO: Subir informes a repositorio público
# ❌ NO: Almacenar reportes sin encriptar en servidor
```

---

## 📋 Flujos de Trabajo

### Flujo 1: Fix Automático (Para CI/CD)

```bash
#!/bin/bash
python full_audit_with_fixes.py --auto

if [ $? -eq 0 ]; then
    echo "✅ Auditoría exitosa"
    exit 0
else
    echo "❌ Auditoría falló"
    exit 1
fi
```

### Flujo 2: Fix con Confirmación (Manual)

```bash
#!/bin/bash

# 1. Generar reporte
python generate_audit_report.py

# 2. Mostrar fugas
echo ""
echo "Fugas detectadas:"
python audit_captures.py --find-leaks

# 3. Confirmar con usuario
read -p "¿Añadir fugas detectadas al vault? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python auto_add_detected_leaks.py --auto
    python audit_captures.py --find-leaks
fi
```

### Flujo 3: Monitoreo Continuo (Cron)

```bash
# Añade a crontab -e:
0 */4 * * * cd /path && python full_audit_with_fixes.py --auto >> audit.log 2>&1
```

---

## 🎯 Ejemplos Prácticos

### Ejemplo 1: Workflow Manual Completo

```bash
# Terminal
$ python full_audit_with_fixes.py

# Output:
# 📊 Paso 1: Generando reporte...
# ✅ Reporte guardado: informes/audit_2026-09-05_100406.md
#
# ⚠️  RESULTADO: 1 FUGA DETECTADA
# 
# 🔧 Paso 2: Auto-añadiendo fugas detectadas...
# ¿Añadir estos valores al vault? [y/N]: y
# ✅ 1 valor añadido (260 total en vault)
#
# 🔍 Paso 3: Re-verificando...
# ✅ No CRITICAL leaks detected
#
# 🎉 Pseudonimización correcta
```

### Ejemplo 2: Solo Preview (--dry-run)

```bash
$ python auto_add_detected_leaks.py --dry-run

# Output:
# ⚠️ Encontradas 3 fugas:
#   1. email      | dev@example.com
#   2. api_key    | sk_live_...
#   3. github_token | ghp_...
#
# ➕ Añadiendo:
#    Real:       dev@example.com
#    Pseudónimo: email_8c9f3a42
#
# 💡 (Dry-run mode: no se realizaron cambios)
```

### Ejemplo 3: Auto-fix sin Salida

```bash
$ python full_audit_with_fixes.py --auto >/dev/null 2>&1 && \
  echo "✅ OK" || echo "❌ FAILED"

✅ OK
```

---

## 🔍 Troubleshooting

### Problema: "ANTHROPIC_PSEUDO_SALT no encontrado"

**Solución:**
```bash
# Opción 1: Generar y exportar
export ANTHROPIC_PSEUDO_SALT=$(python -c 'import secrets; print(secrets.token_hex(16))')

# Opción 2: O usar launcher (genera config.json)
python -m Klaus_proxy_local.launcher
```

### Problema: "No captures found"

**Solución:**
```bash
# Ejecuta primero el proxy para generar captures/
claude-proxy
# (En otra terminal, usa Claude)
```

### Problema: "Permission denied on .pseudonym_vault.json"

**Solución:**
```bash
chmod 600 captures/.pseudonym_vault.json
```

---

## 📊 Interpretación de Resultados

### Resultado: "✅ No CRITICAL leaks detected"

```
🎉 PERFECTO
- Pseudonimización 100% funcionando
- Todas las fugas han sido corregidas
- Listo para producción
```

### Resultado: "⚠️ 5 leaks found"

```
Opciones:
1. Auto-añadir: python auto_add_detected_leaks.py --auto
2. Revisar manualmente: grep -r "valor" captures/sent/
3. Investigar origen: audit_captures.py --review
```

---

## 📈 Métricas y Monitoreo

### Ver histórico de vault

```bash
# Tamaño del vault a lo largo del tiempo
grep "Total en vault" informes/audit_*.md | tail -5

# Tendencia de fugas
grep "Fugas detectadas" informes/audit_*.md | tail -10
```

### Dashboard simple

```bash
#!/bin/bash
echo "🔐 Klaus Proxy Vault Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
VAULT_SIZE=$(grep "Total en vault" informes/audit_*.md | tail -1 | awk '{print $(NF-1)}')
echo "Vault entries:  $VAULT_SIZE"
echo "Last audit:     $(date -r informes/audit_*.md | tail -1)"
echo ""
echo "Status:"
python audit_captures.py --find-leaks | grep -E "(detected|No CRITICAL)"
```

---

## 🚀 Integración en CI/CD

### GitHub Actions

```yaml
name: Auto-Fix Audit

on:
  schedule:
    - cron: '0 9 * * 1'  # Lunes 9 AM
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run full audit with auto-fix
        run: |
          export ANTHROPIC_PSEUDO_SALT=$(python -c 'import secrets; print(secrets.token_hex(16))')
          python full_audit_with_fixes.py --auto

      - name: Upload audit report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: audit_report
          path: informes/audit_*.md
```

---

## ✅ Checklist: Usar Auto-Fix

```
[ ] Ejecuto full_audit_with_fixes.py --auto regularmente
    ☐ Antes de cada release
    ☐ Semanalmente (cron)
    ☐ Bajo demanda cuando sospecho cambios

[ ] Verifico resultados
    ☐ Reviso reporte generado
    ☐ Confirmo "No CRITICAL leaks detected"
    ☐ Noto cambios en vault size

[ ] Monitoreo a largo plazo
    ☐ Comparo histórico de fugas
    ☐ Investigo si hay aumento de fugas
    ☐ Reviso qué patrones se detectan
```

---

## 📚 Archivos Relacionados

| Archivo | Propósito |
|---------|-----------|
| **full_audit_with_fixes.py** | Workflow completo (detecta + arregla + verifica) |
| **auto_add_detected_leaks.py** | Auto-añadir leaks al vault |
| **audit_captures.py** | Análisis manual de payloads |
| **generate_audit_report.py** | Generar reportes |
| **.gitignore** | Excluye informes (contienen datos sensibles) |

---

## 🎯 Resumen Rápido

```
┌─────────────────────────────────────────────────────────┐
│ OPCIÓN                       COMANDO                    │
├─────────────────────────────────────────────────────────┤
│ Workflow completo (automático) python full_audit...     │
│ Workflow con confirmación      python full_audit...     │
│ Solo preview (--dry-run)       python auto_add_...      │
│ Solo detectar                  python audit_captures... │
│ Auto-add detectadas            python auto_add_...      │
│ Generar reporte                python generate_audit... │
└─────────────────────────────────────────────────────────┘
```

---

**¡Listo! Ahora tus fugas se detectan y arreglan automáticamente.** 🚀
