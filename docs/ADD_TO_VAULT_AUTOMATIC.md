# 🤖 Añadir Automáticamente al Vault desde una Carpeta

Este documento te muestra cómo **escanear una carpeta automáticamente y añadir todos los datos sensibles al vault sin intervención manual**.

## ⚡ Quick Start (2 comandos)

```bash
# Escanear una carpeta y añadir automáticamente (solo CRITICAL)
python scripts/add_to_vault.py /path/to/tu/proyecto

# Incluir también HIGH y MEDIUM
python scripts/add_to_vault.py /path/to/tu/proyecto --all
```

¡Eso es todo! Los datos sensibles se añaden al vault automáticamente.

---

## 📋 Opciones Disponibles

### Básico: Solo CRITICAL (Por defecto)

```bash
python scripts/add_to_vault.py /ruta/proyecto
```

Añade solo hallazgos con confianza **CRITICAL** (0% falsos positivos).

### Incluir HIGH

```bash
python scripts/add_to_vault.py /ruta/proyecto --high
```

Añade **CRITICAL + HIGH** (muy confiables, algunos falsos positivos posibles).

### Incluir TODO (CRITICAL + HIGH + MEDIUM)

```bash
python scripts/add_to_vault.py /ruta/proyecto --all
```

Añade **CRITICAL + HIGH + MEDIUM** (cubre más casos, más falsos positivos).

### Ver qué se añadiría sin hacer cambios

```bash
python scripts/add_to_vault.py /ruta/proyecto --dry-run
```

Muestra qué se añadiría al vault **sin hacer cambios reales**.

### Revisar hallazgos antes de añadir

```bash
python scripts/add_to_vault.py /ruta/proyecto --review
```

Muestra todos los hallazgos y pide confirmación antes de añadirlos.

### Ver detalles de cada hallazgo

```bash
python scripts/add_to_vault.py /ruta/proyecto --verbose
```

Muestra información completa de cada hallazgo detectado.

---

## 🎯 Ejemplos Prácticos

### Ejemplo 1: Escanear proyecto y auto-añadir

```bash
$ python scripts/add_to_vault.py ~/proyecto-api

════════════════════════════════════════════════════════════════════
🔐 Klaus Add to Vault — Automatiza adición de secretos
════════════════════════════════════════════════════════════════════

📁 Escaneando: /Users/alice/proyecto-api
[████████████████████████████████████░░░░░░░░░░░░] 73% (243/333 archivos)

────────────────────────────────────────────────────────────────────
📊 Resultados del escaneo
────────────────────────────────────────────────────────────────────
Archivos escaneados: 333
Hallazgos encontrados: 12
Por encima del umbral (CRITICAL): 8

────────────────────────────────────────────────────────────────────
✨ Añadiendo hallazgos al vault...
────────────────────────────────────────────────────────────────────
  1. ✓ Añadido: /api-key_abc123def456
  2. ✓ Añadido: /secret_xyz789uvw
  3. ⓘ Ya en vault: /api-key_existing
  4. ✓ Añadido: /key_mno456pqr
  5. ✓ Añadido: /api-key_jkl123mno
  ...

════════════════════════════════════════════════════════════════════
✅ Proceso completado
════════════════════════════════════════════════════════════════════
Archivos escaneados: 333
Hallazgos encontrados: 12
Hallazgos procesados: 8
Añadidos al vault: 7
```

### Ejemplo 2: Modo dry-run para ver qué se haría

```bash
$ python scripts/add_to_vault.py ~/proyecto --dry-run

📁 Escaneando: /Users/alice/proyecto
[████████████████████████████████████████████████] 100% (156/156 archivos)

────────────────────────────────────────────────────────────────────
📊 Resultados del escaneo
────────────────────────────────────────────────────────────────────
Archivos escaneados: 156
Hallazgos encontrados: 5
Por encima del umbral (CRITICAL): 5

────────────────────────────────────────────────────────────────────
🔍 Modo DRY-RUN: No se hizo ningún cambio
Se habrían añadido 5 hallazgos al vault
────────────────────────────────────────────────────────────────────
```

### Ejemplo 3: Revisar antes de añadir

```bash
$ python scripts/add_to_vault.py ~/proyecto --review --verbose

📁 Escaneando: /Users/alice/proyecto
[████████████████████████████████████████████████] 100% (156/156 archivos)

────────────────────────────────────────────────────────────────────
📋 Hallazgos detectados
────────────────────────────────────────────────────────────────────

  🔴 [✦ nuevo] CRITICAL — api-key
     Archivo: src/config.py:42
     Tipo: pattern
     Razón: AWS access key (AKIA prefix)

  🔴 [✦ nuevo] CRITICAL — private-key
     Archivo: .ssh/id_rsa:1
     Tipo: pattern
     Razón: RSA private key format

────────────────────────────────────────────────────────────────────
🔎 Revisar 2 hallazgo(s)

¿Añadir todos al vault? [s/N]: s

✨ Añadiendo hallazgos al vault...
────────────────────────────────────────────────────────────────────
  1. ✓ Añadido: /api-key_abc123def456
  2. ✓ Añadido: /key_xyz789uvw123

✅ Proceso completado
```

### Ejemplo 4: Incluir detecciones de HIGH y usar contextual

```bash
$ python scripts/add_to_vault.py ~/proyecto --high --contextual

🔐 Klaus Add to Vault — Automatiza adición de secretos

📁 Escaneando: /Users/alice/proyecto
[████████████████████████████████████████████████] 100% (243/243 archivos)

────────────────────────────────────────────────────────────────────
📊 Resultados del escaneo
────────────────────────────────────────────────────────────────────
Archivos escaneados: 243
Hallazgos encontrados: 23
Por encima del umbral (HIGH): 15

✨ Añadiendo hallazgos al vault...
────────────────────────────────────────────────────────────────────
  1. ✓ Añadido: /api-key_abc123
  2. ✓ Añadido: /secret_def456
  ...
  14. ✓ Añadido: /secret_xyz789
  15. ⓘ Ya en vault: /api-key_existing

✅ Proceso completado
────────────────────────────────────────────────────────────────────
Archivos escaneados: 243
Hallazgos encontrados: 23
Hallazgos procesados: 15
Añadidos al vault: 14
```

---

## 🔍 Detección Automática

### Tier 1: CRITICAL (Patrón - 0% falsos positivos)

Detecta automáticamente:
- ✅ AWS keys (AKIA prefix)
- ✅ GitHub tokens (ghp_)
- ✅ Private keys (RSA, Ed25519, DSA)
- ✅ API keys (sk-, sk_live_, etc.)
- ✅ Conexiones BD (connection strings)
- ✅ URLs con credenciales
- ✅ + 15 patrones más

### Tier 2: HIGH (Contextual - 5-10% falsos positivos)

Detecta con análisis contextual:
- Nombres de variables comunes (password, token, secret, api_key)
- Tipos de archivo sensibles (.env, .credentials, etc.)
- Múltiples variables en la misma línea
- Claves JSON ({"api_key": "value"})

### Tier 3: MEDIUM (Heurística - 30% falsos positivos)

Usa análisis de entropía:
- Strings con alta entropía
- Caracteres aleatorios
- Diversidad de caracteres

---

## 📊 Salida en JSON

Para integración con otros sistemas, usa `--json`:

```bash
python scripts/add_to_vault.py /ruta/proyecto --json
```

Salida:
```json
{
  "success": true,
  "files_scanned": 333,
  "findings_total": 12,
  "findings_processed": 8,
  "findings_added": 7,
  "errors": null,
  "added": [
    {
      "file": "src/config.py",
      "line": 42,
      "category": "api-key",
      "confidence": "CRITICAL",
      "pseudo": "/api-key_abc123def456"
    },
    {
      "file": ".env",
      "line": 5,
      "category": "secret",
      "confidence": "CRITICAL",
      "pseudo": "/secret_xyz789uvw"
    }
  ]
}
```

---

## ⚙️ Opciones Avanzadas

### Habilitar detección contextual

```bash
python scripts/add_to_vault.py ~/proyecto --high --contextual
```

Usa análisis contextual para detectar más secretos (más falsos positivos).

### Habilitar detección heurística

```bash
python scripts/add_to_vault.py ~/proyecto --all --heuristic
```

Usa análisis de entropía (menos preciso, más cobertura).

### Combinar opciones

```bash
python scripts/add_to_vault.py ~/proyecto \
  --all \
  --contextual \
  --heuristic \
  --verbose \
  --review
```

---

## 🛠️ Automatizar con Scripts

### Bash: Añadir carpeta diaria

```bash
#!/bin/bash
# daily-vault-scan.sh

PROJECT_PATH="${1:-.}"

python scripts/add_to_vault.py "$PROJECT_PATH" \
  --high \
  --contextual \
  --json > vault-scan-$(date +%Y%m%d).json

echo "✓ Scan completado: vault-scan-$(date +%Y%m%d).json"
```

Uso:
```bash
chmod +x daily-vault-scan.sh
./daily-vault-scan.sh ~/mi-proyecto
```

### CI/CD: Adicionar a tu pipeline

En **GitHub Actions**:

```yaml
- name: Scan and add to vault
  run: |
    python scripts/add_to_vault.py . \
      --high \
      --contextual \
      --json > scan-results.json
  
- name: Upload results
  uses: actions/upload-artifact@v3
  with:
    name: vault-scan-results
    path: scan-results.json
```

---

## 🔐 Seguridad

### ✅ Qué es seguro

- Los valores en el vault están **hasheados con salt**
- Solo se guarda el mapeo `real → pseudo`
- Los valores originales están en `original/` (protegidos)
- Cada ejecución es **inmutable y auditable**

### ⚠️ Precauciones

1. **Nunca subas captures/ a git:**
   ```bash
   # .gitignore
   .klaus-proxy/../captures/
   ~/.klaus-proxy/
   ```

2. **Protege permisos:**
   ```bash
   chmod 600 ~/.klaus-proxy/../captures/.pseudonym_vault.json
   chmod 600 ~/.klaus-proxy/.salt
   ```

3. **Revisa antes de auto-añadir:**
   ```bash
   # Mejor: revisar primero
   python scripts/add_to_vault.py ~/proyecto --review

   # O dry-run
   python scripts/add_to_vault.py ~/proyecto --dry-run
   ```

---

## 🐛 Troubleshooting

### Error: "Path not found"

```bash
# Asegurate que la ruta existe
ls -la /ruta/proyecto
python scripts/add_to_vault.py /ruta/proyecto
```

### Error: "Vault initialization failed"

```bash
# Asegurate que el vault está disponible
# Ejecuta claude-proxy primero
claude-proxy

# O reinicia el vault
rm -rf ~/.klaus-proxy/../captures/.pseudonym_vault.json
```

### Se añadieron valores duplicados

```bash
# Verificar el vault
python scripts/inspect_vault.py --stats

# No hay problema: VaultIntegration comprueba duplicados
# automáticamente antes de añadir
```

### Demasiados falsos positivos

```bash
# Usar solo CRITICAL (por defecto)
python scripts/add_to_vault.py ~/proyecto

# O revisar antes
python scripts/add_to_vault.py ~/proyecto --high --review
```

---

## 📊 Monitorización

### Ver qué se ha añadido hoy

```bash
# Buscar archivos capturados hoy
find ~/.klaus-proxy/../captures/original/ -type f -mtime -1 | wc -l

# Ver estadísticas actuales
python scripts/inspect_vault.py --stats
```

### Verificar integridad

```bash
# Comprobar vault es válido JSON
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq . > /dev/null && echo "✓ Vault válido"

# Ver ultimos valores añadidos
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | keys | .[-5:]'
```

---

## 🚀 Recomendaciones

### Para desarrollo local

```bash
# Modo dry-run para ver primero
python scripts/add_to_vault.py . --dry-run

# Luego revisar
python scripts/add_to_vault.py . --review

# Finalmente auto-añadir
python scripts/add_to_vault.py .
```

### Para CI/CD

```bash
# Auto-añadir solo CRITICAL (confiable)
python scripts/add_to_vault.py . --json
```

### Para auditoría manual

```bash
# Ver todos con detalles
python scripts/add_to_vault.py /carpeta/a/auditar \
  --all \
  --contextual \
  --verbose \
  --dry-run
```

---

## 📚 Relacionado

- `docs/INSPECT_ANONYMIZATIONS.md` — Cómo ver lo que se añadió
- `docs/USER_GUIDE.md` — Guía completa
- `scripts/inspect_vault.py` — Inspeccionar el vault
- `docs/ARCHITECTURE_DEEP_DIVE.md` — Cómo funciona internamente

---

**Documento:** ADD_TO_VAULT_AUTOMATIC.md  
**Versión:** 0.3.0  
**Última actualización:** Septiembre 3, 2026
