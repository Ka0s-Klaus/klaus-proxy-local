# 🔍 Cómo Inspeccionar Anonimizaciones en Klaus Proxy Local

Este documento te muestra exactamente dónde están guardadas las anonimizaciones y cómo consultarlas.

## 📍 Ubicaciones de los Datos

Klaus Proxy Local guarda las anonimizaciones en varios lugares:

### 1. **Vault Principal** (Mapeo completo)
```
~/.klaus-proxy/../captures/.pseudonym_vault.json
```

Contiene:
- `real_to_pseudo`: Valores reales → Pseudonimizados
- `pseudo_to_real`: Pseudonimizados → Valores reales

### 2. **Capturas Originales** (Valores REALES)
```
~/.klaus-proxy/../captures/original/
```

Archivos JSON con los valores REALES que se enviaron.
**⚠️ SENSIBLE - Guardar en lugar seguro**

### 3. **Capturas Enviadas** (Valores PSEUDONIMIZADOS)
```
~/.klaus-proxy/../captures/sent/
```

Archivos JSON con los valores PSEUDONIMIZADOS que se enviaron a la API.

### 4. **Configuración**
```
~/.klaus-proxy/config.json    # Configuración del proxy
~/.klaus-proxy/.salt          # SALT para hashing (NO compartir)
```

---

## 🛠️ Métodos para Inspeccionar

### Método 1: Script Python (RECOMENDADO)

El más fácil de usar:

```bash
# Ver estadísticas generales
python scripts/inspect_vault.py

# Ver todas las anonimizaciones
python scripts/inspect_vault.py --all

# Buscar una anonimización específica
python scripts/inspect_vault.py --search "user@example.com"

# Ver mapeo real → pseudo
python scripts/inspect_vault.py --forward

# Ver mapeo pseudo → real
python scripts/inspect_vault.py --reverse

# Listar capturas
python scripts/inspect_vault.py --captures original
python scripts/inspect_vault.py --captures sent
```

### Método 2: Comandos Linux/macOS

#### Ver el vault completo:
```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq .
```

#### Ver solo mapeo real → pseudo:
```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo'
```

#### Ver solo mapeo pseudo → real:
```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.pseudo_to_real'
```

#### Contar cuántas anonimizaciones hay:
```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | length'
```

#### Buscar un valor específico:
```bash
grep "usuario" ~/.klaus-proxy/../captures/.pseudonym_vault.json
```

#### Ver primeras 10 líneas del vault:
```bash
head -20 ~/.klaus-proxy/../captures/.pseudonym_vault.json
```

### Método 3: Listar archivos de capturas

#### Ver capturas originales:
```bash
ls -lh ~/.klaus-proxy/../captures/original/
```

#### Ver capturas enviadas:
```bash
ls -lh ~/.klaus-proxy/../captures/sent/
```

#### Contar archivos de captura:
```bash
ls ~/.klaus-proxy/../captures/original/ | wc -l
```

---

## 📊 EJEMPLOS PRÁCTICOS

### Ejemplo 1: Ver todas las anonimizaciones

```bash
$ python scripts/inspect_vault.py --all

📋 TODAS LAS ANONIMIZACIONES
════════════════════════════════════════════════════════════════

Total de mapeos: 5

1. Valor real:
   └─ /home/alice/project
   Pseudonimizado:
   └─ /proj_a1b2c3d4

2. Valor real:
   └─ alice@example.com
   Pseudonimizado:
   └─ /email_x9y8z7w6

3. Valor real:
   └─ sk-ant-1234567890abcdefghij
   Pseudonimizado:
   └─ /key_abc123def456
```

### Ejemplo 2: Buscar una anonimización

```bash
$ python scripts/inspect_vault.py --search "alice"

🔍 BUSCANDO: 'alice'
════════════════════════════════════════════════════════════════

✓ Encontrado (como valor REAL):
  Real: alice@example.com
  Pseudo: /email_x9y8z7w6

✓ Encontrado (como valor REAL):
  Real: /home/alice/project
  Pseudo: /proj_a1b2c3d4
```

### Ejemplo 3: Ver estadísticas

```bash
$ python scripts/inspect_vault.py

📊 ESTADÍSTICAS DEL VAULT
════════════════════════════════════════════════════════════════

Total de anonimizaciones: 5

Por categoría:
  • API Keys: 1 (20.0%)
  • Emails: 1 (20.0%)
  • Rutas: 2 (40.0%)
  • Otros: 1 (20.0%)
```

### Ejemplo 4: Ver JSON formateado

```bash
$ cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo' | head -20

{
  "/home/alice/project": "/proj_a1b2c3d4",
  "alice@example.com": "/email_x9y8z7w6",
  "sk-ant-xyz": "/key_abc123"
}
```

---

## 🔐 SEGURIDAD

### ⚠️ IMPORTANTE

- **NUNCA** subir `~/.klaus-proxy/../captures/` a git
- **NUNCA** compartir `.pseudonym_vault.json`
- **NUNCA** exponer `.salt` (needed for reverting)
- **NUNCA** compartir capturas en `original/`

Estos archivos contienen información SENSIBLE y son específicos de tu usuario.

### Proteger tus anonimizaciones

```bash
# Asegurar permisos
chmod 600 ~/.klaus-proxy/../captures/.pseudonym_vault.json
chmod 600 ~/.klaus-proxy/.salt

# Verificar permisos
ls -l ~/.klaus-proxy/.salt
ls -l ~/.klaus-proxy/../captures/.pseudonym_vault.json

# Eliminar capturas antiguas (cuando no las necesites)
rm -rf ~/.klaus-proxy/../captures/original/*
rm -rf ~/.klaus-proxy/../captures/sent/*
```

---

## 🎯 CASOS DE USO COMUNES

### 1. Verificar si un email está anonimizado

```bash
python scripts/inspect_vault.py --search "user@example.com"
```

### 2. Saber cuántos valores hemos pseudonimizado

```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | length'
```

### 3. Ver la ruta original de un proyecto

```bash
# Si el pseudo es /proj_a1b2c3d4
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.pseudo_to_real."/proj_a1b2c3d4"'
```

### 4. Auditar qué se envió a la API

```bash
# Ver capturas pseudonimizadas enviadas
ls -la ~/.klaus-proxy/../captures/sent/ | head -10
```

### 5. Limpiar anonimizaciones antiguas

```bash
# CUIDADO: Esto elimina TODO el historial de anonimizaciones
rm ~/.klaus-proxy/../captures/.pseudonym_vault.json

# Klaus-proxy generará un nuevo vault en la próxima ejecución
```

---

## 📋 ESTRUCTURA DEL VAULT

El archivo `.pseudonym_vault.json` tiene esta estructura:

```json
{
  "real_to_pseudo": {
    "valor_real_1": "pseudonimo_1",
    "valor_real_2": "pseudonimo_2",
    "valor_real_3": "pseudonimo_3"
  },
  "pseudo_to_real": {
    "pseudonimo_1": "valor_real_1",
    "pseudonimo_2": "valor_real_2",
    "pseudonimo_3": "valor_real_3"
  }
}
```

### Propiedades

- **real_to_pseudo**: Mapeo de valores reales a pseudonimizados
  - Usado cuando se ENVÍA a la API (request)
  
- **pseudo_to_real**: Mapeo inverso (pseudonimizado a real)
  - Usado cuando se RECIBE de la API (response)

---

## 💡 TIPS

### Buscar valores por patrón

```bash
# Ver todas las rutas
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | to_entries[] | select(.key | startswith("/")) | .value'

# Ver todos los emails
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | to_entries[] | select(.key | contains("@")) | .value'

# Ver todos los API keys
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | to_entries[] | select(.key | startswith("sk-")) | .value'
```

### Exportar para auditoría

```bash
# Crear copia de backup (MANTENER SEGURO)
cp ~/.klaus-proxy/../captures/.pseudonym_vault.json ~/vault_backup.json

# Restringir permisos
chmod 600 ~/vault_backup.json
```

---

## 📞 TROUBLESHOOTING

### No encuentro el vault

```bash
# Asegúrate de haber ejecutado claude-proxy antes
# El vault se crea en la primera ejecución

# Verifica la ruta
ls -la ~/.klaus-proxy/../captures/

# Si no existe, crea los directorios
mkdir -p ~/.klaus-proxy/../captures/original
mkdir -p ~/.klaus-proxy/../captures/sent
```

### El vault está vacío

```bash
# Significa que no se ha enviado nada a través del proxy
# Ejecuta:
claude-proxy

# En otro terminal:
export HTTPS_PROXY=http://127.0.0.1:8899
claude "test"
```

### No puedo leer el JSON

```bash
# Instala jq
brew install jq  # macOS
apt install jq   # Linux

# O usa Python
python -m json.tool ~/.klaus-proxy/../captures/.pseudonym_vault.json
```

---

## ✅ VERIFICACIÓN

Para verificar que todo está guardado correctamente:

```bash
# 1. Comprobar que el vault existe
test -f ~/.klaus-proxy/../captures/.pseudonym_vault.json && echo "✅ Vault encontrado"

# 2. Verificar que es JSON válido
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq . > /dev/null && echo "✅ JSON válido"

# 3. Contar anonimizaciones
echo "Anonimizaciones: $(cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | length')"

# 4. Ver que hay capturas
echo "Capturas originales: $(ls ~/.klaus-proxy/../captures/original/ | wc -l)"
echo "Capturas enviadas: $(ls ~/.klaus-proxy/../captures/sent/ | wc -l)"
```

---

**Documento:** INSPECT_ANONYMIZATIONS.md  
**Versión:** 0.3.0  
**Última actualización:** Septiembre 3, 2026
