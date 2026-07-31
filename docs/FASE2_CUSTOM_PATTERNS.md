# 🎯 Custom Patterns Configuration — Klaus Proxy Local v0.2.0

## Overview

Klaus Proxy Local v0.2.0 allows you to define **custom secret patterns** specific to your organization or project.

**Location:** `~/.klaus/config.yml` (global) or `./.klaus/config.yml` (project-specific)

**Format:** YAML with pattern definitions

---

## Quick Start

### 1. Create Configuration File

```bash
mkdir -p ~/.klaus
cat > ~/.klaus/config.yml << 'EOF'
patterns:
  my-api-key:
    regex: "MY_KEY_[A-Z0-9]{32}"
    label: "my-service-key"
    description: "Internal API key for MyService"
    enabled: true

  internal-token:
    regex: "token-[a-f0-9]{40}"
    label: "internal-token"
    description: "Internal service token"
    enabled: true
EOF
```

### 2. Use Scanner

```bash
# Scanner automatically loads ~/.klaus/config.yml
klaus-scan /project

# Or explicitly specify config
# (not yet implemented in CLI, available via API)
```

### 3. Custom Patterns Will Be Detected

```
Found: "MY_KEY_ABC123DEF456GHI789JKL012MNO345"
Pattern: my-api-key (internal)
Confidence: CRITICAL
```

---

## Configuration Format

### Full Schema

```yaml
patterns:
  pattern-name:                          # Unique identifier
    regex: "REGEX_PATTERN"               # Regex pattern (required)
    label: "pattern-label"               # Label for findings (required)
    description: "Human-readable desc"   # Description (required)
    enabled: true                        # Enable/disable (default: true)

settings:
  min-entropy-threshold: 4.5             # Entropy threshold (default: 4.5)
  max-file-size-mb: 20                   # Max file size (default: 20)
  skip-common-false-positives: true      # Skip URLs, UUIDs, hex (default: true)
```

### Pattern Examples

#### 1. Simple Service Token

```yaml
patterns:
  acme-service-token:
    regex: "acme_[a-z0-9]{48}"
    label: "acme-token"
    description: "ACME service authentication token"
    enabled: true
```

**Detects:** `acme_abc123def456ghi789jkl012mnopqrstuvwxyz012345`

#### 2. Database Connection Format

```yaml
patterns:
  internal-postgres-url:
    regex: "postgres://admin:[A-Za-z0-9_!@#$%^&*]{8,}@db-[a-z0-9]+\\.internal:\\d{4}"
    label: "internal-db-url"
    description: "Internal PostgreSQL connection URL"
    enabled: true
```

**Detects:** `postgres://admin:secret123@db-prod.internal:5432`

#### 3. Encoded API Key

```yaml
patterns:
  slack-webhook-encoded:
    regex: "https://hooks\\.slack\\.com/services/T[A-Z0-9]{8}/B[A-Z0-9]{8}/[A-Za-z0-9_-]{24}"
    label: "slack-webhook"
    description: "Slack webhook URL"
    enabled: true
```

**Detects:** Full Slack webhook URLs

#### 4. Environment Variable with Secret

```yaml
patterns:
  service-config-value:
    regex: "SERVICE_[A-Z_]+=([A-Za-z0-9_\\-!@#$%]{12,})"
    label: "service-config"
    description: "Service configuration with sensitive value"
    enabled: true
```

**Detects:** `SERVICE_API_KEY=abc123def456ghi789`

---

## How Patterns Are Used

### 1. **Pattern Matching**
- Regex is applied to each line of each file
- Matches become findings with **CRITICAL confidence**
- Same as built-in patterns (Tier 1)

### 2. **Integration with Tiers**
```
Tier 1 (Pattern):
  ├─ Built-in patterns (20)
  └─ Custom patterns (from config)
     
Tier 2 (Contextual):
  ├─ Variable names (45+)
  └─ File types/locations

Tier 3 (Heuristic):
  └─ Entropy + diversity
```

### 3. **Order of Evaluation**
1. Custom patterns (if defined)
2. Built-in patterns (always)
3. Contextual detection (if enabled)
4. Heuristic detection (if enabled)

---

## Configuration Locations

### Global Configuration

```
~/.klaus/config.yml          # User-level config
~/.klaus/config.json         # Alternative (JSON)
```

**Applies to:** All projects scanned by this user

### Project-Specific Configuration

```
./.klaus/config.yml          # Project root
./.klaus/config.json         # Alternative (JSON)
```

**Applies to:** Only this project (overrides global)

**Priority:** Project-specific > Global > Defaults

---

## YAML vs JSON

Both formats supported. Choose what works for your setup.

### YAML Example
```yaml
patterns:
  my-pattern:
    regex: "pattern_[A-Z]{10}"
    label: "my-label"
    description: "My pattern"
    enabled: true
```

### JSON Equivalent
```json
{
  "patterns": {
    "my-pattern": {
      "regex": "pattern_[A-Z]{10}",
      "label": "my-label",
      "description": "My pattern",
      "enabled": true
    }
  }
}
```

---

## Advanced Usage

### Disable Specific Patterns

```yaml
patterns:
  my-pattern:
    enabled: false              # Won't be used in scans
```

### Organization-Wide Patterns

Create `~/.klaus/config.yml` with your company's patterns:

```yaml
patterns:
  acme-api-key:
    regex: "ACME_[A-Z0-9]{32}"
    label: "acme-key"
    description: "ACME Corp API key"
    enabled: true

  acme-oauth-token:
    regex: "oauth_[a-f0-9]{64}"
    label: "acme-oauth"
    description: "ACME Corp OAuth token"
    enabled: true

  acme-internal-secret:
    regex: "INT_SECRET_[A-Za-z0-9_]{40,}"
    label: "acme-internal"
    description: "ACME internal secret"
    enabled: true
```

All users inherit these patterns automatically.

### Project-Override Patterns

Team with different secret format? Override in project:

```yaml
# ./.klaus/config.yml (in project root)
patterns:
  project-specific-key:
    regex: "PROJ_[A-Z0-9]{48}"
    label: "proj-key"
    description: "Project-specific API key"
    enabled: true
```

---

## Testing Your Patterns

### Manual Test

```bash
# Create a test file
echo 'api_key = "ACME_ABC123DEF456GHI789JKL012MNO345"' > test.env

# Scan (will load ~/.klaus/config.yml automatically)
klaus-scan .

# Should find your custom pattern
```

### Validation

```bash
# Check pattern syntax
python3 -c "
import re
pattern = 'ACME_[A-Z0-9]{32}'
re.compile(pattern)  # If this doesn't error, pattern is valid
print('✓ Pattern is valid')
"
```

---

## Troubleshooting

### Pattern Not Matching

**Problem:** You defined a pattern but it's not detecting your secret

**Solutions:**
1. Verify regex syntax: `python3 -c "import re; re.compile('YOUR_REGEX')"`
2. Check file is being scanned (not in .gitignore or excluded directory)
3. Verify pattern `enabled: true`
4. Test regex against actual secret value

### Invalid YAML/JSON

**Problem:** `Error loading config from ~/.klaus/config.yml: ...`

**Solutions:**
1. Validate YAML: `python3 -m yaml ~/.klaus/config.yml`
2. Check indentation (YAML uses 2 spaces, not tabs)
3. Escape special characters in regex: `"PATTERN\\[test\\]"`

### Configuration Not Loading

**Problem:** Custom patterns aren't being used

**Solutions:**
1. Verify config file exists: `cat ~/.klaus/config.yml`
2. Check file permissions: `ls -la ~/.klaus/config.yml`
3. Test manual loading: `python3 -c "from Klaus_proxy_local.sensitive_data_scanner import ConfigurationLoader; print(ConfigurationLoader.load_config())"`

---

## Best Practices

### 1. **Specific Patterns First**

```yaml
# ✓ GOOD: Specific to your service
acme-api-key:
  regex: "ACME_[A-Z0-9]{32}"

# ✗ LESS IDEAL: Too generic
generic-key:
  regex: "[A-Z0-9]{32}"  # Will match many things
```

### 2. **Unique Prefixes**

```yaml
# ✓ GOOD: Unlikely to appear elsewhere
pattern:
  regex: "MY_UNIQUE_PREFIX_[A-Z0-9]{24}"

# ✗ PROBLEMATIC: Common pattern
pattern:
  regex: "key_[a-z]+"  # Matches "key_board", etc.
```

### 3. **Document Your Patterns**

```yaml
patterns:
  internal-api-token:
    regex: "INT_API_[a-f0-9]{40}"
    label: "internal-api-token"
    description: "Internal API authentication token (40 hex chars)"
    enabled: true
```

### 4. **Test Before Deploying**

```bash
# Add to ~/.klaus/config.yml and test:
echo 'test = "INT_API_ABC123DEF456GHI789JKL012MNO345PQR678"' > /tmp/test.env
klaus-scan /tmp/test.env
# Verify your pattern is detected as CRITICAL
```

---

## Examples: Real-World Patterns

### AWS-Style Service Key

```yaml
patterns:
  mycompany-service-key:
    regex: "MYCO_SK_[A-Z0-9]{40}"
    label: "myco-service-key"
    description: "MyCompany service authentication key"
    enabled: true
```

### GitHub-Like Token

```yaml
patterns:
  internal-github-pat:
    regex: "ghp_internal_[A-Za-z0-9_]{36}"
    label: "internal-github-pat"
    description: "Internal GitHub Personal Access Token"
    enabled: true
```

### Database Connection

```yaml
patterns:
  corporate-db-url:
    regex: "db://[^:]+:[^@]+@db\\.corporate\\.internal:\\d+"
    label: "corp-db-url"
    description: "Corporate database connection string"
    enabled: true
```

### Kubernetes Secret

```yaml
patterns:
  k8s-service-account:
    regex: "k8s_sa_[A-Za-z0-9_\\-]{32}"
    label: "k8s-service-account"
    description: "Kubernetes service account token"
    enabled: true
```

---

## Reference

### Regex Quick Reference

| Pattern | Matches |
|---------|---------|
| `[A-Z]` | Single uppercase letter |
| `[a-z]` | Single lowercase letter |
| `[0-9]` | Single digit |
| `[A-Za-z0-9]` | Letter or digit |
| `_` | Underscore |
| `-` | Hyphen |
| `{n}` | Exactly n times |
| `{n,}` | n or more times |
| `{n,m}` | Between n and m times |
| `+` | One or more |
| `*` | Zero or more |
| `.` | Any character (except newline) |
| `\\.` | Literal dot (escaped) |

### Common Patterns

```yaml
# Uppercase hexadecimal (32 chars)
"[A-F0-9]{32}"

# Lowercase alphanumeric (40 chars)
"[a-z0-9]{40}"

# Mixed case with special chars (20+ chars)
"[A-Za-z0-9_\\-]{20,}"

# Format: PREFIX_XXXX_YYYY
"PREFIX_[A-Z0-9]{4}_[A-Z0-9]{4}"
```

---

## Integration with Vault

Custom patterns are treated the same as built-in patterns:

1. **Detected** → Added to findings (CRITICAL confidence)
2. **User Approves** → Added to vault.json
3. **Pseudonymizer Uses** → Consistent hashing with all other secrets

```
Custom Pattern Match
    ↓
SensitiveDataFinding (CRITICAL)
    ↓
User Approves in Interactive Review
    ↓
vault.add_finding_to_vault() 
    ↓
Stored as: "secret_xxxxx" → original value
    ↓
Next pseudonymize run: consistent mapping ✅
```

---

## Summary

✅ Define patterns specific to your organization  
✅ Global or project-specific configuration  
✅ YAML or JSON format  
✅ Enable/disable patterns as needed  
✅ Integrated with Vault for automatic pseudonymization  
✅ CRITICAL confidence (same as built-in patterns)  

Custom patterns give you the flexibility to detect your internal secret formats without waiting for updates to Klaus Proxy Local.

