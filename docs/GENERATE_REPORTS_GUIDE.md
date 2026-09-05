# 📊 Guía: Generar Reportes de Auditoría Automáticamente

**Sistema automático para auditar payloads y generar reportes profesionales.**

---

## ⚡ Inicio Rápido (30 segundos)

```bash
cd /Users/asantacana/proyectos/klaus-proxy-local
python generate_audit_report.py
```

**Output:**
- ✅ Reporte guardado en `informes/audit_YYYY-MM-DD_HHMMSS.md`
- ✅ Índice actualizado en `informes/audit_index.md`
- ✅ Reporte mostrado en terminal

---

## 📋 Estructura de Carpetas

```
informes/
├── .gitkeep                          (Solo este se versiona)
├── audit_index.md                    (Índice de todos los reportes)
├── audit_2026-09-05_095313.md       (Reporte 1)
├── audit_2026-09-05_100045.md       (Reporte 2)
└── audit_2026-09-05_150227.md       (Reporte 3)
```

**Notas de Seguridad:**
- ✅ `.gitkeep` se versiona (marcador de directorio)
- ❌ `audit_*.md` NO se versiona (contiene datos sensibles)
- ❌ `audit_index.md` NO se versiona (referencia a reportes sensibles)
- 🔒 Reportes protegidos en `.gitignore`

---

## 🚀 Usos Comunes

### Caso 1: Auditoría Diaria
```bash
# Cada mañana o antes de release
python generate_audit_report.py

# Revisar el reporte generado
cat informes/audit_2026-09-05_*.md | less
```

### Caso 2: Auditoría Semanal (con Timestamp)
```bash
# Ejecuta script y guarda resultado
python generate_audit_report.py | tee audit_log_$(date +%Y%m%d_%H%M%S).txt

# Luego revisa:
tail -100 audit_log_*.txt
```

### Caso 3: Automatización en CI/CD
```yaml
# .github/workflows/audit.yml
name: Weekly Audit Report

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday 9am

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Generate audit report
        run: |
          python generate_audit_report.py > audit_report.txt
          cat audit_report.txt
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: audit_report
          path: audit_report.txt
```

### Caso 4: Monitoreo Continuo (cada 4 horas)
```bash
# Cron job para monitoreo automático
# Añade a crontab:
0 */4 * * * cd /Users/asantacana/proyectos/klaus-proxy-local && \
             python generate_audit_report.py >> audit_monitor.log 2>&1
```

---

## 📄 Contenido del Reporte

Cada reporte generado contiene:

### Sección 1: Resumen Ejecutivo
```markdown
| Métrica | Valor | Status |
|---------|-------|--------|
| Payloads capturados | 9,042 original + 9,042 sent | ✅ |
| Valores en vault | 259 entradas | ✅ |
| Fugas detectadas | 1 - Revisar | ⚠️ |
| Cobertura | Emails 109, IPs 87, Orgs 8 | ✅ |
| Pseudonimización | 100% funcionando | ✅ |
```

### Sección 2: Estadísticas Detalladas
- Cantidad de payloads
- Patrones encontrados (emails, IPs, paths, UUIDs, etc.)

### Sección 3: Distribución del Vault
- Pseudónimos por tipo (infra, db-connection, email, etc.)
- Gráfica ASCII con porcentajes

### Sección 4: Cobertura por Tipo
- Email: 109 entradas
- IP: 87 entradas
- Org: 8 entradas
- ID: 2 entradas
- Path: 3 entradas
- Other: 50 entradas

### Sección 5: Detección de Fugas
- Valores sensibles encontrados en sent/ sin pseudonimizar
- Acciones recomendadas si hay fugas

### Sección 6: Conclusiones
- Estado de pseudonimización
- Verificación de seguridad
- Recomendación de producción

### Sección 7: Metadata
- Timestamp de generación
- Counts (payloads, vault, fugas)

---

## 🔍 Interpretación de Resultados

### Escenario A: "0 Fugas"
```
✅ PERFECTO
- Pseudonimización 100% funcionando
- Listo para producción
- No requiere acción
```

### Escenario B: "1-5 Fugas"
```
⚠️ REVISAR
- Hay valores no pseudonimizados
- Necesita investigación
- Acción: Ejecutar audit_captures.py --find-leaks
- Fix: python scripts/add_to_vault.py . --manual
```

### Escenario C: ">10 Fugas"
```
❌ PROBLEMA
- Múltiples valores sin pseudonimizar
- Pseudonimización puede estar rota
- Acción: Revisar logs de proxy
- Fix: Investigar por qué no se pseudonimiza
```

---

## 📋 Índice de Reportes (audit_index.md)

El sistema mantiene un índice automático:

```markdown
# 📋 Índice de Auditorías

| Fecha | Hora | Reporte | Tipo |
|-------|------|---------|------|
| 2026-09-05 | 09:53:13 | [audit_2026-09-05_095313.md](audit_2026-09-05_095313.md) | Auto-generated |
| 2026-09-05 | 10:00:45 | [audit_2026-09-05_100045.md](audit_2026-09-05_100045.md) | Auto-generated |
| 2026-09-05 | 15:02:27 | [audit_2026-09-05_150227.md](audit_2026-09-05_150227.md) | Auto-generated |
```

- ✅ Se actualiza automáticamente cada vez que generas un reporte
- ✅ Mantiene último 100 reportes
- ✅ Enlaces directos a cada reporte

---

## 🔒 Consideraciones de Seguridad

### ✅ SÍ Hacer
```bash
# Ejecutar el generador en máquina local
python generate_audit_report.py

# Revisar reportes localmente
cat informes/audit_*.md

# Usar en CI/CD privado (solo empleados)
# Commit: no versiona datos (están en .gitignore)
```

### ❌ NO Hacer
```bash
# ❌ NO: Subir reportes a repositorio público
git add informes/audit_*.md
git push

# ❌ NO: Compartir reportes vía email/Slack (contienen datos reales)
# (Solo compartir con personas autorizadas, de forma segura)

# ❌ NO: Dejar reportes sin encriptar en servidor remoto
scp informes/audit_*.md user@remote:
```

---

## 📊 Comparar Reportes Históricos

```bash
# Ver cambios en vault entre dos reportes
diff <(grep "Total:" informes/audit_2026-09-05_095313.md) \
     <(grep "Total:" informes/audit_2026-09-05_100045.md)

# Ver tendencia de fugas
grep "Fugas detectadas" informes/audit_*.md

# Ver evolución de payloads
grep "Original payloads" informes/audit_*.md | tail -10
```

---

## 🔧 Personalización

### Cambiar Carpeta de Reportes
En `generate_audit_report.py`, línea ~27:
```python
REPORTS_DIR = Path.cwd() / "informes"  # Cambiar aquí
```

### Cambiar Cantidad de Fugas Mostradas
En `generate_audit_report.py`, línea ~333:
```python
for leak in leaks_found[:15]:  # Mostrar primeras 15 (cambiar aquí)
```

### Cambiar Reportes Históricos Guardados
En `generate_audit_report.py`, línea ~366:
```python
entries.insert(0, new_entry)
for line in entries[:100]:  # Guardar últimos 100 (cambiar aquí)
```

---

## 📞 Solución de Problemas

### Problema: "No captures found"
```
Posible causa: Aún no has ejecutado audit_captures.py
Solución: Ejecuta primero python audit_captures.py --stats
```

### Problema: "Permiso denegado (informes/)"
```
Posible causa: Permisos insuficientes en carpeta informes/
Solución: chmod 755 informes/
```

### Problema: "ModuleNotFoundError"
```
Posible causa: No activaste el venv
Solución: source .venv/bin/activate
```

---

## ✅ Checklist: Monitoreo Continuo

```
[ ] Ejecuto generate_audit_report.py regularmente
    ☐ Diario (antes de release)
    ☐ Semanal (cada lunes)
    ☐ Bajo demanda (cuando sospecho cambios)

[ ] Reviso resultados
    ☐ Verifico resumen ejecutivo
    ☐ Noto cambios en cobertura de vault
    ☐ Investigo cualquier fuga nueva

[ ] Acciono si hay problemas
    ☐ Fugas detectadas → Ejecuto add_to_vault.py
    ☐ Cobertura baja → Reviso audit_captures.py --patterns
    ☐ Cambios grandes → Investigo root cause

[ ] Documentación
    ☐ Guardo último reporte (para comparar)
    ☐ Noto tendencias (más/menos fugas)
    ☐ Comparto con equipo (datos sensibles, solo authorized)
```

---

## 🚀 Ejemplo Completo: Workflow Semanal

```bash
#!/bin/bash
# Auditoría semanal automatizada

cd /Users/asantacana/proyectos/klaus-proxy-local

echo "📊 Iniciando auditoría semanal..."
echo ""

# 1. Generar reporte
python generate_audit_report.py

# 2. Extraer métricas
PAYLOAD_COUNT=$(grep "Original payloads" informes/audit_*.md | tail -1 | awk '{print $NF}')
VAULT_COUNT=$(grep "Total:" informes/audit_*.md | tail -1 | awk '{print $NF}')
LEAK_COUNT=$(grep "Fugas detectadas" informes/audit_*.md | tail -1 | grep -o "[0-9]\+" | head -1)

echo ""
echo "✅ RESUMEN SEMANAL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Payloads:    $PAYLOAD_COUNT"
echo "  Vault:       $VAULT_COUNT"
echo "  Fugas:       $LEAK_COUNT"
echo ""

# 3. Alerta si hay fugas
if [ "$LEAK_COUNT" -gt 0 ]; then
    echo "⚠️  ATENCIÓN: Se detectaron $LEAK_COUNT fugas"
    echo "Ejecuta: python audit_captures.py --find-leaks"
    exit 1
else
    echo "✅ Pseudonimización: 100% OK"
    echo "✅ Listo para producción"
    exit 0
fi
```

---

## 📚 Archivos Relacionados

| Archivo | Propósito |
|---------|-----------|
| **generate_audit_report.py** | Generador de reportes (este script) |
| **audit_captures.py** | Análisis detallado de payloads |
| **informes/audit_index.md** | Índice de todos los reportes |
| **informes/audit_*.md** | Reportes individuales (timestamped) |
| **.gitignore** | Excluye reportes sensibles |

---

**¡Listo!** Ahora puedes generar reportes de auditoría automáticamente. 🚀
