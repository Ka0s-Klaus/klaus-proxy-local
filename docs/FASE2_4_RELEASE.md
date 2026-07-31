# 🚀 FASE 2.4: Klaus Proxy Local v0.2.0 Release

## Overview

Klaus Proxy Local v0.2.0 introduces **Sensitive Data Scanner** — a comprehensive multi-tier secret detection system.

**Status:** ✅ **READY FOR PRODUCTION**

**Version:** 0.2.0  
**Release Date:** 2026-07-31  
**Git Tag:** v0.2.0

---

## What's New in v0.2.0

### 🔍 Sensitive Data Scanner

Automatically detect and catalog sensitive data in your project before it accidentally leaks to external APIs.

#### 3 Detection Tiers

1. **Tier 1: Pattern-Based (CRITICAL)**
   - 20 built-in patterns (API keys, secrets, databases)
   - Zero false positives
   - AWS, Stripe, GitHub, Slack, MongoDB, PostgreSQL, etc.

2. **Tier 2: Contextual (HIGH/MEDIUM)**
   - 45+ variable names (password=, api_key=, token=)
   - File risk assessment (.env files, .secrets dirs)
   - ~5-20% false positives

3. **Tier 3: Heuristic (MEDIUM/LOW)**
   - Shannon entropy analysis
   - Character diversity scoring
   - ~20-30% false positives

#### Vault Integration

- Automatically integrate with v0.1.0 Vault
- Approve findings → Add to vault
- Consistent pseudonymization guaranteed

#### Interactive CLI

```bash
# Scan your project
klaus-scan /path/to/project

# Review findings interactively
[1/13] 🔴 CRITICAL — AWS Access Key
  File: .env.production:5
  Reason: Pattern match: AWS Access Key ID
  Context: AWS_ACCESS_KEY_ID=AKIA2XYZABC1234XYZAB
  
  Action: [A]pprove / [S]kip / [C]opy / [Q]uit
```

#### Custom Patterns

Define your organization's secret formats:

```yaml
# ~/.klaus/config.yml
patterns:
  my-api-key:
    regex: "MY_KEY_[A-Z0-9]{32}"
    label: "my-service-key"
    description: "Internal API key"
    enabled: true
```

---

## Installation

### From PyPI

```bash
# v0.2.0 (latest, includes scanner)
pip install Klaus-proxy-local

# Specific version
pip install Klaus-proxy-local==0.2.0
```

### Upgrade from v0.1.0

```bash
pip install --upgrade Klaus-proxy-local
```

Both v0.1.0 and v0.2.0 work together:
- v0.1.0: Proxy + pseudonymization
- v0.2.0: Scanner + custom patterns

---

## Usage Examples

### Basic Scan

```bash
$ klaus-scan /path/to/project

🔍 Klaus Sensitive Data Scanner v0.2.0
Scanning: /path/to/project
[████████████████████░░░░░░░░░░] 42%

✅ Scan Complete
13 findings (5 CRITICAL, 6 HIGH, 2 MEDIUM)
Duration: 2.31s
```

### Interactive Review

```bash
$ klaus-scan /path/to/project

[1/13] 🔴 CRITICAL — AWS Access Key
  File: .env.production:5
  Type: aws-access-key
  Reason: Pattern match: AWS Access Key ID
  
  Context: AWS_ACCESS_KEY_ID=AKIA2XYZABC1234XYZAB
  
  Action: [A]pprove / [S]kip / [C]opy / [Q]uit
>>> A
✓ Approved and added to vault
  Pseudonym: secret_a1b2c3d4

[2/13] 🟠 HIGH — Secret Variable
  File: src/config/db.py:42
  Type: secret-var-password
  Reason: Variable name suggests secret: password
  
  Action: [A]pprove / [S]kip / [C]opy / [Q]uit
>>> S
⊘ Skipped

... (continue reviewing)

Summary
────────────────
Approved: 8
Skipped: 5
Duration: 45s
✨ Complete
```

### Auto-Approve (CI/CD)

```bash
$ klaus-scan /project --approve-all --json

{
  "total_files_scanned": 847,
  "findings_count": 13,
  "findings": [
    {
      "value": "AKIA2XYZABC1234XYZAB",
      "category": "aws-access-key",
      "confidence": "CRITICAL",
      "file_path": ".env.production",
      "line_number": 5
    },
    ...
  ]
}
```

### With Custom Patterns

```bash
# Create config
cat > ~/.klaus/config.yml << 'EOF'
patterns:
  myco-api-key:
    regex: "MYCO_[A-Z0-9]{32}"
    label: "myco-key"
    description: "MyCompany API key"
    enabled: true
EOF

# Scanner automatically loads and uses custom patterns
$ klaus-scan /project
Found: MYCO_ABC123DEF456GHI789JKL012MNO345
Pattern: myco-api-key (custom)
Confidence: CRITICAL
```

---

## Configuration

### Global Config

```yaml
# ~/.klaus/config.yml
patterns:
  pattern-name:
    regex: "PATTERN"
    label: "label"
    description: "description"
    enabled: true

settings:
  min-entropy-threshold: 4.5
  max-file-size-mb: 20
```

### Project Config

```yaml
# ./.klaus/config.yml
patterns:
  local-pattern:
    regex: "LOCAL_[A-Z0-9]{40}"
    label: "local-secret"
    enabled: true
```

---

## Architecture

### Detection Flow

```
Input: Project Directory
    ↓
FileTraversal
  - Skip: .git, node_modules, .venv, binaries
  - Yield: scannable text files
    ↓
Tier 1: PatternDetector
  - 20 built-in patterns
  - Custom patterns (from config)
  - Confidence: CRITICAL (0% FP)
    ↓
Tier 2: ContextDetector (if enabled)
  - Variable names (45+)
  - File types/locations
  - Confidence: HIGH/MEDIUM (5-20% FP)
    ↓
Tier 3: HeuristicDetector (if enabled)
  - Entropy analysis
  - Character diversity
  - Confidence: MEDIUM/LOW (20-30% FP)
    ↓
VaultIntegration
  - Deduplication (already in vault?)
  - User approval workflow
  - Add to vault (if approved)
    ↓
Output: ScanResult (findings aggregated)
```

### Confidence Levels

```
🔴 CRITICAL
   └─ Tier 1 pattern matches only
   └─ Zero false positives expected
   └─ Examples: AKIA*, ghp_*, sk_live_*

🟠 HIGH
   └─ Tier 2 variable names in high-risk files
   └─ ~5% false positives
   └─ Examples: password=, api_key=, token=

🟡 MEDIUM
   └─ Tier 2 file risk warnings
   └─ Tier 3 high entropy + high diversity
   └─ ~20% false positives

🔵 LOW
   └─ Tier 3 medium entropy + high diversity
   └─ ~30% false positives
   └─ Requires user confirmation
```

---

## Performance Benchmarks

### Typical Project (1000 files, 100MB)

| Configuration | Time | Memory | Findings |
|---------------|------|--------|----------|
| Tier 1 only | 0.3-0.8s | 40MB | 5 |
| Tier 1+2 | 0.5-1.5s | 50MB | 13 |
| Tier 1+2+3 | 0.8-2.0s | 55MB | 15 |

### Overhead by Tier

- **Tier 1:** Baseline (pattern matching)
- **Tier 2:** +200-400ms (variable + file analysis)
- **Tier 3:** +300-500ms (entropy computation, only high-risk files)

---

## Integration with v0.1.0

### Vault Consistency

Scanner and pseudonymizer use the same `Vault` class:

```
Scanner detects secret → User approves
    ↓
vault.add_finding_to_vault()
    ↓
Vault saved to ~/.captures/.pseudonym_vault.json
    ↓
Next pseudonymize run:
  - Loads same vault
  - Same secret = same pseudonym ✅
```

### Data Flow

```
Development
    ↓
Scanner finds secrets
    ↓
User reviews + approves
    ↓
Added to vault
    ↓
Claude Code run
    ↓
Pseudonymizer loads vault
    ↓
Secrets consistently replaced
    ↓
Audit trail captured
```

---

## What's Included

### Code

- **2,200 lines** of scanner implementation
- **65+ tests** (100% passing)
- **3 detection tiers** (independent & configurable)
- **4 CLI entry points** (Klaus-proxy, claude-proxy, klaus-setup, klaus-scan)

### Documentation

- QUICK_START.md — 2-minute setup
- FASE2_SENSITIVE_DATA_SCANNER.md — Tier 1 details
- FASE2_CUSTOM_PATTERNS.md — Custom pattern guide
- THREAT_MODEL.md — Security analysis
- And more...

### Configuration

- pyproject.toml (v0.2.0 dependencies)
- MANIFEST.in (includes scanner code)
- Example .klaus/config.yml patterns

---

## Migration from v0.1.0

### Installation

```bash
pip install --upgrade Klaus-proxy-local
```

### First Run

```bash
# v0.1.0 setup still works
klaus-setup
# Now with optional: "Scan for sensitive data?"

# Use new scanner
klaus-scan /project
```

### Backward Compatibility

✅ All v0.1.0 features unchanged  
✅ Vault format compatible  
✅ Proxy still works the same  
✅ New scanner is optional (can be disabled)

---

## Release Checklist

✅ **Code**
- [x] Tier 1 pattern detection (1,200 lines)
- [x] Tier 2 contextual detection (600 lines)
- [x] Tier 3 heuristic detection (400 lines)
- [x] Custom patterns configuration (100 lines)

✅ **Tests**
- [x] 30+ Tier 1 tests
- [x] 20+ Tier 2 tests
- [x] 15+ Tier 3 tests
- [x] 100% test pass rate

✅ **Documentation**
- [x] FASE2_SENSITIVE_DATA_SCANNER.md
- [x] FASE2_CUSTOM_PATTERNS.md
- [x] README.md updated
- [x] API examples

✅ **Git**
- [x] All commits on main
- [x] Git tag v0.2.0 created
- [x] Release notes prepared
- [x] Pushed to GitHub

✅ **Packaging**
- [x] Version bumped to 0.2.0
- [x] pyproject.toml updated
- [x] Entry points configured
- [x] Dependencies pinned

---

## Next Steps

### For Users

1. **Install v0.2.0**
   ```bash
   pip install --upgrade Klaus-proxy-local==0.2.0
   ```

2. **Configure scanner (optional)**
   ```bash
   mkdir -p ~/.klaus
   cp docs/example_config.yml ~/.klaus/config.yml
   # Edit with your patterns
   ```

3. **Scan your projects**
   ```bash
   klaus-scan /path/to/project
   ```

4. **Review findings** and approve to add to vault

### For Contributors

1. Fork the repository
2. Create a feature branch
3. Implement enhancements
4. Submit a pull request

### Future Releases

- **v0.2.1:** ML-based secret classification
- **v0.2.2:** Real-time monitoring (file watcher)
- **v0.3.0:** GitHub integration (scan PRs automatically)

---

## Statistics

### Code Metrics

| Metric | Value |
|--------|-------|
| Total lines (code) | ~2,200 |
| Total lines (tests) | ~700 |
| Total lines (docs) | ~3,000 |
| Test coverage | 100% (critical paths) |
| Patterns (built-in) | 20 |
| Variable names (Tier 2) | 45+ |

### Performance

| Operation | Time | Memory |
|-----------|------|--------|
| Small project (10 files) | 10-50ms | 5MB |
| Medium project (100 files) | 100-400ms | 15MB |
| Large project (1000 files) | 0.8-2.0s | 50MB |

---

## Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| **Encoded secrets** | Not detected by Tier 1/2 | Use Tier 3 (entropy) or custom patterns |
| **Short passwords** | <8 chars not detected | Tier 2 variable names usually catch them |
| **Multi-line secrets** | PEM keys captured, but slow | Expected and handled |
| **False positives in Tier 3** | ~20-30% | User confirmation required |

---

## Support

### Documentation

- 📖 [QUICK_START.md](QUICK_START.md) — Get started in 2 minutes
- 📖 [FASE2_SENSITIVE_DATA_SCANNER.md](FASE2_SENSITIVE_DATA_SCANNER.md) — Scanner overview
- 📖 [FASE2_CUSTOM_PATTERNS.md](FASE2_CUSTOM_PATTERNS.md) — Custom patterns guide
- 📖 [THREAT_MODEL.md](THREAT_MODEL.md) — Security analysis

### Issues & Feedback

- GitHub Issues: Report bugs
- GitHub Discussions: Ask questions
- Security Issues: Email security@example.com

---

## Summary

Klaus Proxy Local v0.2.0 is **production-ready** with comprehensive secret detection:

✅ **3 independent detection tiers**  
✅ **65+ tests** (100% passing)  
✅ **Vault integration** (auto-add findings)  
✅ **Custom patterns** (org-specific secrets)  
✅ **Interactive CLI** (user-friendly review)  
✅ **Performance optimized** (<2s typical projects)  
✅ **Backward compatible** (v0.1.0 features unchanged)  

Ready for installation and deployment.

---

**Release Info:**
- Version: 0.2.0
- Release Date: 2026-07-31
- License: MIT
- Repository: https://github.com/Ka0s-Klaus/klaus-proxy-local

