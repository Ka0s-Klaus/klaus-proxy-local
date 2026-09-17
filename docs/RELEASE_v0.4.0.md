# 🚀 Release v0.4.0 — Klaus Monitor TUI

**Fecha:** 2026-09-17  
**Estado:** ✅ Production Ready

---

## 🎯 Lo Nuevo

### ✨ Klaus Monitor — htop-style TUI (Feature Principal)

**El problema:** Monitorizar Klaus Proxy requería ejecutar scripts de auditoría separados. Ahora hay un **dashboard interactivo en tiempo real** tipo htop.

**La solución:**
- Interfaz TUI con 5 paneles integrados
- Actualizaciones cada ~0.8 segundos
- Atajos de teclado ([a]=Audit, [r]=Refresh, [q]=Quit)
- Visualización de tráfico vivo, cobertura del vault, auditoría y alertas

### 📺 Estructura

```
src/Klaus_proxy_local/monitor/
├── app.py                    # Aplicación Textual principal
├── data.py                   # DataSource (polling filesystem)
├── styles.tcss               # CSS Textual
└── panels/
    ├── header.py             # Status y uptime
    ├── stats.py              # Métricas clave
    ├── traffic.py            # Feed de requests vivos
    ├── vault.py              # Cobertura del vault
    ├── audit.py              # Status del último audit
    └── alerts.py             # Leaks detectados
```

### 🎮 Uso

**Standalone (sin proxy):**
```bash
claude-proxy-monitor
```

**Con proxy (en otra terminal):**
```bash
# Terminal 1
claude-proxy

# Terminal 2
claude-proxy-monitor
```

---

## 📊 Paneles

### 📊 STATS
- Requests, Pseudonymized, Blocked, Vault size, Leaks, Req/min

### 🔄 LIVE TRAFFIC
- Últimos 15 requests con timestamp, método, endpoint y status (✅/—/❌)

### 🔐 VAULT COVERAGE
- Desglose por tipo (infra, db-connection, email, api-key, etc.)
- Barras ASCII mostrando proporción

### 📋 AUDIT STATUS
- Resultado del último audit
- Botón `[a]` para ejecutar auditoría

### ⚠️ ALERTS
- Leaks detectados en tiempo real

---

## 📈 Mejoras Internas

1. **DataSource** (data.py):
   - Polling eficiente: solo lee archivos nuevos en captures/
   - Detección de leaks comparando sent/ vs vault
   - Cálculo de estadísticas en tiempo real
   - Thread-safe con locks

2. **Textual App** (app.py):
   - Componentes reactivos
   - Bindings configurables
   - `set_interval()` para actualizaciones periódicas
   - Notificaciones (`.notify()`)

3. **Paneles Independientes**:
   - Cada panel es un widget Textual aislado
   - Reciben datos del DataSource
   - Se re-renderizan solo cuando cambian (reactivos)

---

## ✅ Testing Realizado

- ✅ Monitor arranca en terminal vacía (sin captures)
- ✅ Lee captures existentes correctamente
- ✅ Detecta archivos nuevos en tiempo real
- ✅ Recarga vault cuando cambia
- ✅ Botón `[a]` ejecuta auditoría y actualiza status
- ✅ Paneles se refrescan cada 0.8s
- ✅ Atajos de teclado funcionan
- ✅ `[q]` quita correctamente

---

## 🔧 Cambios de Configuración

### pyproject.toml
- ✅ Version: 0.3.0 → 0.4.0
- ✅ Nueva dependencia: `textual>=0.70.0`
- ✅ Nuevo entrypoint: `claude-proxy-monitor`

### src/Klaus_proxy_local/__init__.py
- ✅ Version: 0.1.0 → 0.4.0

---

## 📚 Documentación

- ✅ `docs/MONITOR_GUIDE.md` — Guía completa de uso
- ✅ `docs/RELEASE_v0.4.0.md` — Release notes (este archivo)
- ✅ README.md — Actualizado con sección Monitor

---

## 🚀 Deploy & Installation

### Instalación local
```bash
pip install -e ".[dev]"
claude-proxy-monitor
```

### Instalación from PyPI (cuando se publique)
```bash
pip install Klaus-proxy-local==0.4.0
claude-proxy-monitor
```

---

## 🎯 Roadmap v0.5.0+

- [ ] Integración `claude-proxy --monitor` (proxy + TUI juntos)
- [ ] Dashboard web (para acceso remoto)
- [ ] Exportación de reportes encriptados
- [ ] Perseverancia de métricas en histórico
- [ ] Gráficos de tendencias (requests/hora, leaks/día)
- [ ] Integración con sistemas de secrets externos (HashiCorp Vault, etc.)

---

## 📝 Notas Técnicas

### Performance
- **Polling interval:** 0.8s (equilibrio entre latencia y CPU)
- **Archivo history:** 500 requests en memoria (útil para "últimas N")
- **Vault reload:** Solo cuando mtime cambia (sin lectura innecesaria)
- **Layout:** Grid de Textual (renderización eficiente)

### Limitaciones Actuales
1. Monitor y Proxy en terminales separadas (integración pendiente)
2. No persiste histórico entre sesiones (por diseño — es temporal)
3. Auditoría se ejecuta de forma bloqueante (issue conocido)

### Seguridad
- ✅ Vault no se visualiza completo (solo estadísticas)
- ✅ Leaks se acortan a 20 chars (no expone valores completos)
- ✅ Monitor corre localmente (sin network)
- ✅ Requiere acceso a captures/ y vault (permisos 0o600)

---

## 🔄 Migración desde v0.3.0

Sin cambios de configuración requeridos. Solo instala la nueva versión:

```bash
pip install --upgrade Klaus-proxy-local==0.4.0
# O en desarrollo:
pip install -e .
```

El proxy (claude-proxy) sigue siendo igual. El monitor es nuevo.

---

## 🙏 Créditos

Klaus Monitor utiliza:
- **Textual** — TUI framework moderno para Python
- Arquitectura reactiva inspirada en htop

---

## ✨ What's Next?

- Integración automatizada en `claude-proxy --monitor`
- Soporte para remote monitoring (WebSockets)
- Alertas configurables (webhooks, email)
- Estadísticas persistentes en SQLite

¡Disfruta Klaus Monitor! 🎉
