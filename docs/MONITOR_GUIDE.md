# 🎮 Klaus Monitor — htop-style TUI Guide

Klaus Monitor es una interfaz interactiva tipo **htop** para monitorizar Klaus Proxy Local en tiempo real. Muestra estadísticas, tráfico vivo, cobertura del vault, auditoría y alertas en una única terminal.

---

## ⚡ Uso Rápido

### Opción 1: Monitor Standalone (sin proxy)
```bash
claude-proxy-monitor
```

### Opción 2: Proxy + Monitor Juntos (aún no integrado)
```bash
claude-proxy  # Terminal 1
claude-proxy-monitor  # Terminal 2
```

---

## 📺 Layout de Paneles

```
┌─────────────────── KLAUS MONITOR ─────────────────────┐
│ 🟢 Proxy: RUNNING  Port: 8899  Uptime: 00:02:34  Captures: captures/
├────────┬─────────────────────────────┬──────────────────────┤
│ 📊     │ 🔄 LIVE TRAFFIC             │ 🔐 VAULT COVERAGE    │
│ STATS  │ ──────────────────────────  │ ─────────────────── │
│        │ 16:25:01 POST /v1/mes.. ✅  │ infra    97 ████████ │
│ Reqs:  │ 16:25:00 POST /v1/mes.. ✅  │ db-conn  84 ███████  │
│ 1,234  │ 16:24:59 POST /api/ev.. —   │ email    24 ██       │
│        │ 16:24:58 POST /v1/mes.. ⚠️  │ api-key  18 █        │
│ Pseudo:│ 16:24:57 GET  /mcp.... —    │ ip       17 █        │
│ 1,189  │ 16:24:56 POST /v1/mes.. ✅  │ org       8          │
│        │                              │ Total:  260          │
├────────┴─────────────────────────────┤                      │
│ 📋 AUDIT STATUS                      │                      │
│ ✅ No CRITICAL leaks  [a] Run audit  │                      │
├──────────────────────────────────────┴──────────────────────┤
│ ⚠️  ALERTS: No alerts                                        │
├──────────────────────────────────────────────────────────────┤
│ [a]=Audit [r]=Refresh [q]=Quit [?]=Help                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 Paneles Detallados

### 📊 STATS — Estadísticas Clave
- **Requests**: Total de requests capturados
- **Pseudon.**: Requests que fueron pseudonimizados
- **Blocked**: Requests bloqueados (fail-closed)
- **Vault**: Entradas actuales en el vault
- **Leaks**: Fugas potenciales detectadas
- **Req/min**: Requests en el último minuto

### 🔄 LIVE TRAFFIC — Feed en Tiempo Real
- Últimos ~15 requests capturados
- Formato: `HH:MM:SS METHOD ENDPOINT STATUS`
- Status indicators:
  - `✅` — Pseudonimizado correctamente
  - `—` — No pseudonimizado (telemetría/eventos)
  - `❌` — Bloqueado (fail-closed)

### 🔐 VAULT COVERAGE — Cobertura del Vault
- Desglose de tipos de secretos pseudonimizados
- Barras de progreso mostrando proporción
- Tipos principales:
  - `infra` — IPs privadas, hostnames internos
  - `db-connection` — Connection strings
  - `email` — Direcciones de correo
  - `api-key` — Tokens, claves API
  - `ip` — IPs públicas
  - `org` — Nombres de organización

### 📋 AUDIT STATUS — Último Audit
- Status del último audit ejecutado:
  - `✅ No CRITICAL leaks` — OK, listo para producción
  - `⚠️ LEAKS DETECTED` — Revisar antes de usar
  - `❓ Not run yet` — Ejecutar audit
- Timestamp del último audit
- Botón `[a]` para ejecutar audit ahora

### ⚠️ ALERTS — Alertas y Leaks
- Leaks detectados en tiempo real
- Compara valores en `sent/` contra vault
- Muestra últimas 5 alertas

---

## ⌨️ Atajos de Teclado

| Atajo | Acción | Descripción |
|-------|--------|-------------|
| `[a]` | Audit | Ejecuta auditoría (genera reporte + verifica fugas) |
| `[r]` | Refresh | Fuerza actualización de todos los paneles |
| `[q]` | Quit | Salir (solo monitor, proxy sigue corriendo) |
| `[?]` | Help | Muestra ayuda |

---

## 📊 Interpretación de Datos

### Escenario: Todo Verde ✅
```
Requests: 1,234
Pseudon.: 1,200
Leaks:      0
Vault:    260

✅ No CRITICAL leaks detected
```
**Status:** PERFECTO — Pseudonimización funcionando 100%.

### Escenario: Leaks Detectados ⚠️
```
Leaks: 3
Detected:
  • email: dev@example.com
  • api_key: sk_live_1234...
```
**Acción:** Ejecuta `[a]` para auditoría completa o `[r]` para refresh.

### Escenario: Vault Pequeño
```
Vault: 50 (bajo para 1,000+ requests)
```
**Acción:** Considera ejecutar `python scripts/add_to_vault.py . --scan-captures` para enriquecer el vault.

---

## 🔄 Flujo de Uso Típico

### 1. Iniciar Monitor
```bash
# Terminal 1: Proxy (opcional)
claude-proxy

# Terminal 2: Monitor (obligatorio)
claude-proxy-monitor
```

### 2. Monitorizar en Tiempo Real
- El panel TRAFFIC se actualiza cada ~0.8s
- El panel STATS agrupa cada segundo
- Los ALERTS aparecen inmediatamente si se detecta una fuga

### 3. Ejecutar Auditoría
```
Dentro del monitor:
  Presiona [a]
  Espera notificación: "Audit completed"
  Revisa panel AUDIT STATUS
```

### 4. Revisar Fugas (si las hay)
```
Si hay leaks detectados:
  • Panel ALERTS muestra qué se filtró
  • Ejecuta desde otra terminal:
    python auto_add_detected_leaks.py --auto
  • Presiona [r] en el monitor para refresh
```

---

## 🛠️ Troubleshooting

### Monitor no arranca
```
Error: "ModuleNotFoundError: No module named 'textual'"

Solución:
pip install "textual>=0.70.0"
pip install -e .
```

### No hay datos visibles
```
Posibles causas:
1. Proxy aún no ha capturado nada
2. Captures dir es diferente (~/.klaus-proxy/captures vs ./captures)

Solución:
1. Envía requests a través del proxy primero
2. O ejecuta: export CAPTURES_DIR=~/.klaus-proxy/captures
```

### Audit times out
```
Si presionas [a] y dice "timeout":
1. Hay demasiados payloads (>50,000)
2. O el sistema está lento

Solución:
Ejecuta audit manualmente:
python full_audit_with_fixes.py --no-fix &
```

---

## 📈 Métricas Avanzadas

### Req/min
- Contador de requests en el último minuto
- Indicador de tráfico vivo
- Si es 0: puede haber lag en captures o proxy inactivo

### Vault Coverage %
- Porcentaje de cada tipo vs total
- Bajo coverage (<20% en una categoría) = faltan patrones
- Alto coverage (>80%) = bien configurado

### Pseudonymization Rate
- Pseudon. / Requests * 100 = %
- Debe ser ~90-95% (el resto es telemetría)
- Si es <80%: revisar si patrones funcionan correctamente

---

## 🔐 Notas de Seguridad

1. **Monitor no almacena datos** — Solo visualiza en tiempo real
2. **Vault no se visualiza completo** — Solo estadísticas agregadas
3. **Leaks detectados aparecen acotados** — Primeros 20 chars solamente
4. **Terminal no se captura** — Monitor corre localmente en tu máquina

---

## 📚 Comandos Relacionados

```bash
# Auditoría manual (si quieres más control)
python audit_captures.py --find-leaks
python full_audit_with_fixes.py --no-fix

# Ver vault directamente (cuidado con secretos reales)
python scripts/inspect_vault.py

# Añadir valores a vault
python scripts/add_to_vault.py . --manual

# Generar reporte detallado
python generate_audit_report.py
```

---

## 🚀 Próximos Pasos

- Monitor arrancará automáticamente con `claude-proxy --monitor` (integración pendiente)
- Dashboard web (v0.5.0) para acceso remoto
- Exportación de reportes encriptados
