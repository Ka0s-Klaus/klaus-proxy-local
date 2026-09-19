# 🔧 Cómo Remediar: Payloads NO Pseudonimizados

Cuando ves este error:

```
❌ 2 payloads NOT pseudonymized
❌ Data protection: NEEDS REVIEW
```

Aquí está el proceso paso a paso para identificar y solucionar el problema.

## 🎯 Paso 1: Diagnóstico

Ejecuta el script de diagnóstico:

```bash
python src/Klaus_proxy_local/fix_pseudonymization.py
```

Esto te dirá:
- Cuántos payloads no están pseudonimizados
- Cuál es la causa probable
- Qué soluciones aplicar

### Ejemplo de Output:

```
📊 PAYLOAD STATUS
────────────────────────────────────────────────────────────
  Total Payloads:             4
  Pseudonymized:              2 (50.0%)
  NOT Pseudonymized:          2 (50.0%)

⚙️  CONFIGURATION
────────────────────────────────────────────────────────────
  Config File:                /Users/asantacana/.klaus-proxy/config.json
  Pseudonymization Enabled:   True
  SALT Set:                   True
  Patterns Count:             0  ⚠️  PROBLEMA!

💡 RECOMMENDATIONS
────────────────────────────────────────────────────────────
⚠️  No pseudonymization patterns configured
   FIX: Check ~/.klaus-proxy/config.json
```

## 🔍 Paso 2: Ver Payloads Específicos

```bash
python src/Klaus_proxy_local/fix_pseudonymization.py --show-payloads
```

Output:

```
NON-PSEUDONYMIZED PAYLOADS (2)

1. new_capture_01_181429.json
   Host:    http-intake.logs.us5.datadoghq.com
   Path:    /api/v2/logs
   └─ Likely: Monitoring/logging service (ok to skip)

2. new_capture_02_181432.json
   Host:    api.anthropic.com
   Path:    /api/event_logging/v2/batch
   └─ ACTION: Should be pseudonymized (check config)
```

## 🛠️ Paso 3: Soluciones por Tipo

### CASO 1: Payloads a Datadog/Monitoring (OK - No requiere acción)

```
Host: http-intake.logs.us5.datadoghq.com
Host: logs.datadoghq.com
Host: monitoring.internal.com
```

**Decisión:** ✅ **Seguro ignorar**
- Son servicios de monitoreo internos
- No contienen datos de usuario
- La redacción de secretos en headers es suficiente

**Acción:** Ninguna necesaria.

---

### CASO 2: Payloads a API Anthropic NO pseudonimizados (PROBLEMA)

```
Host: api.anthropic.com
Path: /api/event_logging/v2/batch
```

**Decisión:** ❌ **Necesita pseudonimización**
- Son payloads con potencial de contener PII
- Deben estar pseudonimizados como mínimo

**Soluciones:**

#### Solución A: Habilitar Pseudonimización (Recomendado)

1. Ver configuración actual:
   ```bash
   python src/Klaus_proxy_local/fix_pseudonymization.py --show-config
   ```

2. Editar `~/.klaus-proxy/config.json`:
   ```bash
   nano ~/.klaus-proxy/config.json
   ```

3. Verificar que tenga:
   ```json
   {
     "pseudonymization_enabled": true,
     "salt": "your-salt-here",
     "patterns": {
       "email": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
       "username": "\\b(?:[a-zA-Z0-9_-]{3,16})\\b",
       "path": "(/[a-zA-Z0-9._-]+)+",
       "ip": "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b"
     }
   }
   ```

4. Reiniciar el proxy:
   ```bash
   # Matar proxy anterior
   pkill -f mitmdump
   
   # Iniciar nuevo
   claude-proxy
   ```

5. Hacer nuevas peticiones a través del proxy para verificar

#### Solución B: Excluir Hosts que NO necesitan Pseudonimización

Si un host genuinamente no necesita pseudonimización (ej: Datadog, internal monitoring):

1. Editar `~/.klaus-proxy/config.json`:
   ```json
   {
     "pseudonymization_skip_hosts": [
       "http-intake.logs.us5.datadoghq.com",
       "logs.datadoghq.com",
       "monitoring.internal.com"
     ]
   }
   ```

2. Reiniciar proxy

#### Solución C: Filtrar por Path

Si ciertas rutas no necesitan pseudonimización:

```json
{
  "pseudonymization_skip_paths": [
    "/api/event_logging/v2/batch",
    "/health",
    "/metrics"
  ]
}
```

---

## 📋 Matriz de Decisión Rápida

| Host | Servicio | Acción |
|------|----------|--------|
| `api.anthropic.com` | API Anthropic | ✅ PSEUDONYMIZAR |
| `*.datadoghq.com` | Datadog Monitoring | ⏭️ Omitir |
| `logs.*.es` | Internal Logging | ⏭️ Omitir (si internal) |
| `llm.tools.cloud.*` | Internal LLM Gateway | ✅ PSEUDONYMIZAR |
| `*.internal.com` | Internal Services | ⏭️ Omitir |
| `github.com` | GitHub API | ✅ PSEUDONYMIZAR |

---

## 🔄 Verificar que Funciona

Después de hacer cambios:

### 1. Auditar nuevamente:

```bash
python src/Klaus_proxy_local/audit_all_payloads.py
```

Deberías ver:

```
✅ All payloads pseudonymized and secrets redacted
✅ Data protection: EXCELLENT
```

### 2. Ver en detalle:

```bash
python src/Klaus_proxy_local/fix_pseudonymization.py --show-payloads
```

Deberías ver:

```
❌ No non-pseudonymized payloads found!
✅ All payloads are protected
```

---

## 🚨 Problemas Comunes y Soluciones

### Problema 1: "No pseudonymization patterns configured"

```
⚠️  No pseudonymization patterns configured
   PATTERNS_COUNT: 0
```

**Causa:** El archivo de configuración no tiene patrones.

**Solución:**
```bash
# Regenerar configuración
python -m Klaus_proxy_local.setup

# Selecciona "y" para patrones por defecto
```

---

### Problema 2: "SALT is NOT SET"

```
❌ SALT is NOT SET - pseudonymization cannot work
```

**Causa:** No hay salt configurado.

**Solución:**
```bash
python -m Klaus_proxy_local.setup
```

---

### Problema 3: "Pseudonymization is DISABLED"

```
❌ Pseudonymization is DISABLED in config
```

**Causa:** Está apagada manualmente.

**Solución:**
```bash
# Editar config.json
nano ~/.klaus-proxy/config.json

# Cambiar a:
"pseudonymization_enabled": true
```

---

### Problema 4: Algunos Hosts NO se Pseudonimizan Aunque Debieran

**Causa:** El host no está en `ANTHROPIC_CAPTURE_HOSTS`.

**Solución:**
```bash
# Editar config.json
nano ~/.klaus-proxy/config.json

# Agregar tu host:
"capture_hosts": [
  "api.anthropic.com",
  "llm.tools.cloud.masorange.es",
  "otro-host.com"  # ← Agregar aquí
]
```

---

## 📚 Flujo Completo de Remediación

```
1. Ejecutar diagnóstico
   └─> python fix_pseudonymization.py

2. Ver payloads específicos
   └─> python fix_pseudonymization.py --show-payloads

3. Identificar causa
   ├─ ¿Patterns = 0? → Solución A
   ├─ ¿SALT no set? → python -m Klaus_proxy_local.setup
   ├─ ¿Disabled? → Editar config.json
   └─ ¿Host no capturado? → Agregar a ANTHROPIC_CAPTURE_HOSTS

4. Aplicar solución

5. Reiniciar proxy
   └─> pkill -f mitmdump && claude-proxy

6. Generar nuevos payloads
   └─> export HTTPS_PROXY=http://127.0.0.1:8899
   └─> claude "test"

7. Verificar
   └─> python audit_all_payloads.py
   └─> Deberías ver ✅ EXCELLENT
```

---

## 🎯 Checklist Final

Después de remediar, verifica:

- [ ] Config file tiene `"pseudonymization_enabled": true`
- [ ] Config file tiene `"salt": "..."` (no vacío)
- [ ] Config file tiene `"patterns": {...}` (no vacío)
- [ ] Proxy está reiniciado (`pkill -f mitmdump && claude-proxy`)
- [ ] Nuevos payloads generados (hiciste peticiones a través del proxy)
- [ ] Audit muestra ✅ EXCELLENT
- [ ] No hay outputs ERROR en logs del proxy

---

## 📖 Referencia Rápida

```bash
# Diagnóstico completo
python fix_pseudonymization.py

# Ver payloads no pseudonimizados
python fix_pseudonymization.py --show-payloads

# Ver archivo de config
python fix_pseudonymization.py --show-config

# Auditar todos los payloads
python audit_all_payloads.py

# Auditar detallado
python audit_all_payloads.py --detailed

# Exportar a CSV
python audit_all_payloads.py --export=csv
```

---

## 🆘 Si Nada Funciona

1. **Revisa los logs del proxy:**
   ```bash
   tail -50 ~/.klaus-proxy/proxy.log | grep -i "pseudonym\|error"
   ```

2. **Reinicia completamente:**
   ```bash
   pkill -f mitmdump
   rm ~/.klaus-proxy/captures/sent/*.json
   claude-proxy  # Inicia nuevo
   ```

3. **Regenera configuración:**
   ```bash
   rm ~/.klaus-proxy/config.json
   python -m Klaus_proxy_local.setup
   ```

4. **Crea un nuevo issue con:**
   - Output de `fix_pseudonymization.py`
   - Output de `fix_pseudonymization.py --show-config`
   - Últimas 50 líneas de proxy.log
