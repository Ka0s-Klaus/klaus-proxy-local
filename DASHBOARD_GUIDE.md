# Klaus Monitor Dashboard v0.4.0

Interfaz web en tiempo real para monitorear Klaus Proxy Local.

## Inicio rápido

### Opción 1: Script bash (recomendado)
```bash
./start.sh
```

Esto:
- Instala el paquete
- Inicia el proxy (puerto 8899)
- Inicia el dashboard (http://localhost:9999)
- Abre el navegador automáticamente si es posible

### Opción 2: Comandos separados
Terminal 1:
```bash
claude-proxy
```

Terminal 2:
```bash
python3 -m Klaus_proxy_local.dashboard_server
```

Luego abre http://localhost:9999 en tu navegador.

## Paneles del Dashboard

### 📊 STATS
Métricas en tiempo real:
- **Requests**: Total de solicitudes capturadas
- **Pseudonymized**: Solicitudes con datos pseudonimizados
- **Blocked**: Solicitudes bloqueadas
- **Vault Size**: Número de secretos en el vault
- **Leaks Found**: Fugas detectadas
- **Requests/min**: Tasa de solicitudes por minuto

### 🔄 LIVE TRAFFIC
Feed en tiempo real de las últimas 15 solicitudes:
- **Time**: Timestamp (HH:MM:SS)
- **Method**: GET, POST, etc.
- **Endpoint**: Path de la solicitud
- **Status**: ✓ (pseudonimizado), ❌ (bloqueado), – (normal)

### 🔐 VAULT COVERAGE
Análisis de secretos por tipo:
- Muestra los 8 tipos principales
- Visualización con barras de progreso
- Porcentaje del vault total

### 📋 AUDIT STATUS
Último estado de auditoría:
- Timestamp del último audit
- Resumen de resultados
- Estado de fugas detectadas

### ⚠️ ALERTS
Alertas activas:
- Leaks detectadas en tiempo real
- Información de la fuga

## Arquitectura

### DataSource (monitor_data.py)
```python
DataSource
├── poll()              # Polling cada 0.8s
├── get_recent_requests()
├── get_stats()
└── _resolve_captures_dir()  # Lectura de config.json
```

Integración:
- Lee `~/.klaus-proxy/captures/sent/` (archivos JSON)
- Carga `captures/.pseudonym_vault.json`
- Calcula métricas de pseudonimización en tiempo real

### FastAPI Server (dashboard_server.py)
```
/                 → dashboard.html
/api/stats       → JSON con stats actuales
/ws              → WebSocket para live updates (0.8s)
```

### Frontend (dashboard.html)
- Single-page HTML/CSS/JS
- WebSocket para live updates con fallback a HTTP polling
- Responsive grid layout
- Color-coded status indicators

## Configuración

### Directorio de capturas
Por defecto: `~/.klaus-proxy/captures/`

Para cambiar:
```bash
# Editar ~/.klaus-proxy/config.json
{
  "capture_dir": "/custom/path/captures"
}
```

El dashboard y proxy leerán automáticamente este valor.

## Monitoreo

El dashboard actualiza cada 0.8 segundos con:
- Stats: requests, pseudonymized_count, blocked_count, vault_size
- Traffic: últimas 15 solicitudes con metadata
- Vault: desglose por tipos de secretos
- Uptime y requests por minuto

## Troubleshooting

### El dashboard no carga
1. Verifica que `http://localhost:9999` sea accesible
2. Revisa la consola del navegador (F12) para errores
3. Verifica que el servidor está corriendo: `ps aux | grep dashboard`

### No hay datos en el dashboard
1. Verifica que el proxy está capturando: `ls ~/.klaus-proxy/captures/sent/`
2. Envía una solicitud a través del proxy
3. Espera a que se actualice (cada 0.8s)

### Directorio de capturas incorrecto
1. Verifica `~/.klaus-proxy/config.json`
2. Asegúrate que `capture_dir` existe
3. Reinicia el dashboard

## Desarrollo

### Instalar en modo desarrollo
```bash
pip install -e ".[dev]"
```

### Ejecutar servidor local
```bash
python3 -m Klaus_proxy_local.dashboard_server
```

### Ejecutar con debug
```bash
PYTHONUNBUFFERED=1 python3 -m Klaus_proxy_local.dashboard_server
```

## Notas

- WebSocket auto-fallback: Si la conexión WebSocket falla, el dashboard usa HTTP polling cada 1s
- Historial: Se mantienen las últimas 500 solicitudes en memoria
- Performance: Polling de filesystem optimizado con tracking de mtime
- Thread-safe: DataSource usa locks para acceso concurrente
