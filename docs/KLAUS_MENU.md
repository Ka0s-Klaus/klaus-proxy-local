# Klaus Menu — Interactive CLI for Audit & Scan

## Overview

`klaus` is an interactive bash menu that simplifies access to the three main security auditing commands:

- 🔍 **SCAN** — Find secrets and sensitive data in your project
- 📊 **AUDIT** — Audit captured payloads for security effectiveness
- 🔧 **FIX** — Diagnose pseudonymization issues

## Installation

### Option 1: Copy to PATH (Recommended)

```bash
# Copy the script to your local bin directory
cp ~/proyectos/klaus-proxy-local/klaus ~/.local/bin/

# Make it executable (should already be, but just in case)
chmod +x ~/.local/bin/klaus

# Verify installation
klaus --help
```

### Option 2: Create Symlink

```bash
# Create symlink in local bin
ln -s ~/proyectos/klaus-proxy-local/klaus ~/.local/bin/klaus

# Verify
klaus --help
```

### Option 3: Use Directly from Project

```bash
# Run directly from the project root
~/proyectos/klaus-proxy-local/klaus
```

## Usage

### Interactive Mode

```bash
# Launch the interactive menu
$ klaus

# Select an option:
#   1) 🔍 SCAN                 - Find secrets/sensitive data in project
#   2) 📊 AUDIT                - Audit captured payloads
#   3) 🔧 FIX                  - Diagnose pseudonymization issues
#   4) ❓ HELP                 - Show help
#   5) ❌ EXIT                 - Exit
```

### Command-Line Mode (Direct Invocation)

```bash
# SCAN: Find secrets in a project
klaus scan /path/to/project
klaus scan . --min-confidence HIGH
klaus scan ~/my-repo --approve-all

# AUDIT: Audit captured payloads
klaus audit
klaus audit --detailed
klaus audit --export csv

# FIX: Diagnose pseudonymization issues
klaus fix
klaus fix --show-payloads
klaus fix --show-config

# Help and version
klaus --help
klaus --version
```

## Detailed Command Reference

### 1. SCAN — Find Secrets

**Purpose:** Detect API keys, credentials, and sensitive data in a project directory.

**Interactive Options:**
```
Enter path to scan (default: .)
Confidence level: CRITICAL | HIGH | MEDIUM | LOW
Approve all findings without review? (y/N)
```

**Direct Usage:**
```bash
# Scan with default settings (CRITICAL confidence)
klaus scan ~/my-project

# Scan with HIGH confidence (less strict, more findings)
klaus scan ~/my-project --min-confidence HIGH

# Skip manual review for all findings
klaus scan ~/my-project --approve-all

# Enable advanced detection methods
klaus scan ~/my-project --enable-contextual --enable-heuristic

# Output as JSON
klaus scan ~/my-project --json
```

**Output:**
- Summary of findings by confidence level
- For each finding:
  - Filename
  - Line number
  - Finding type (API key, token, etc.)
  - Confidence level
  - Interactive prompt: Approve (A), Skip (S), Copy (C), Approve All (L), Quit (Q)

**Example Workflow:**
```
$ klaus scan ~/my-project --min-confidence HIGH

Found 3 findings:

1. ~/.ssh/id_rsa (SSH private key) - CRITICAL
   Approve? (a/s/c/l/q): a
   ✅ Added to vault

2. .env.example (AWS_SECRET_ACCESS_KEY) - HIGH
   Approve? (a/s/c/l/q): s
   ⏭️  Skipped

3. config.json (AUTH_TOKEN) - HIGH
   Approve? (a/s/c/l/q): a
   ✅ Added to vault
```

---

### 2. AUDIT — Audit Captured Payloads

**Purpose:** Analyze all payloads captured by Klaus Proxy for pseudonymization effectiveness and security.

**Interactive Options:**
```
Report mode:
  1) Summary (default) - High-level overview
  2) Detailed - Per-payload analysis
  3) Export to CSV - For compliance/audit trails
```

**Direct Usage:**
```bash
# Summary report (default)
klaus audit

# Detailed per-payload breakdown
klaus audit --detailed

# Export to CSV (date-stamped filename)
klaus audit --export csv

# Custom captures directory
klaus audit --captures-dir ~/.klaus-proxy/captures
```

**Output (Summary):**
```
╔════════════════════════════════════════════════════════════════╗
║                    PAYLOAD AUDIT SUMMARY                       ║
╚════════════════════════════════════════════════════════════════╝

📊 CAPTURE OVERVIEW
────────────────────────────────────────────────────────────
  Total Original Payloads:     10368
  Total Sent Payloads:         10368
  Match Rate:                  100.0%

🔐 PSEUDONYMIZATION STATUS
────────────────────────────────────────────────────────────
  Pseudonymized:               731/10368 (7.1%)
  Secrets Redacted:            10368/10368 (100.0%)
  Blocked Requests:            163

🛡️  SECURITY ASSESSMENT
────────────────────────────────────────────────────────────
  ✅ All secrets properly redacted
  ⚠️ Only 7.1% pseudonymized (review pattern coverage)
  Status: GOOD
```

**Output (Detailed):**
```
📋 DETAILED PAYLOAD ANALYSIS
═══════════════════════════════════════════════════════════

SENT PAYLOADS (10368)
───────────────────────────────────────────────────────────
  1. 20260919_120124_anthropic_payload.json ✅
     Method: POST, Status: 200
     URL: https://api.anthropic.com/v1/messages
     Pseudonymized: true
     Secrets Redacted: true
     Timestamp: 2026-09-19T12:01:24Z
```

---

### 3. FIX — Diagnose Pseudonymization Issues

**Purpose:** Identify why payloads aren't being pseudonymized and provide remediation steps.

**Interactive Options:**
```
Diagnostic options:
  1) Summary report (default)
  2) Show non-pseudonymized payloads
  3) Show current configuration
```

**Direct Usage:**
```bash
# Diagnostic summary
klaus fix

# List all non-pseudonymized payloads
klaus fix --show-payloads

# Review current configuration
klaus fix --show-config

# Custom captures directory
klaus fix --captures-dir ~/.klaus-proxy/captures
```

**Output (Summary):**
```
🔧 PSEUDONYMIZATION DIAGNOSTIC
═════════════════════════════════════════════════════════════

📊 STATUS
─────────────────────────────────────────────────────────────
  ✅ Pseudonymization is ENABLED
  ✅ SALT is SET (a848b93e0d59...)
  ✅ Patterns configured: 5 custom patterns

⚠️ FINDINGS
─────────────────────────────────────────────────────────────
  ❌ 2 payloads NOT pseudonymized (0.02%)
     • Host: monitoring.internal.com (safe to skip)
     • Host: datadog.com (monitoring service)

💡 RECOMMENDATIONS
─────────────────────────────────────────────────────────────
  1. These are monitoring services — safe to exclude
  2. No action needed unless you want to pseudonymize them
  3. To include them, add patterns to ~/.klaus-proxy/config.json
```

**Output (Show Payloads):**
```
Non-pseudonymized Payloads:
───────────────────────────────────────────────────────────

Host: monitoring.internal.com
  Path: /api/metrics
  Files: 
    - 20260919_110532_anthropic_payload.json
    - 20260919_110604_anthropic_payload.json

Host: datadog.com
  Path: /api/v1/series
  Files:
    - 20260919_115438_anthropic_payload.json
```

---

## Examples

### Example 1: Complete Security Audit Workflow

```bash
# 1. Scan project for secrets
$ klaus
1
. 
1
y

# (Approves secrets to vault)

# 2. Audit captured payloads
$ klaus
2
2

# (Shows detailed payload analysis)

# 3. Check pseudonymization status
$ klaus
3
1

# (Shows diagnostic report)
```

### Example 2: Automated Compliance Export

```bash
# Export audit report for compliance
$ klaus audit --export csv
audit_report_20260919_143020.csv

# Import into Excel for audit trail
open ~/.klaus-proxy/captures/audit_report_*.csv
```

### Example 3: Fix Pseudonymization Issues

```bash
# Find the issue
$ klaus fix

# See exactly which payloads are affected
$ klaus fix --show-payloads

# Review configuration to understand why
$ klaus fix --show-config

# Make changes to ~/.klaus-proxy/config.json
# Then restart proxy:
$ claude-proxy
```

---

## Configuration

### Captures Directory

By default, `klaus` uses `~/.klaus-proxy/captures/`. To use a different directory:

```bash
# All commands support --captures-dir
klaus scan --captures-dir /custom/path ...
klaus audit --captures-dir /custom/path
klaus fix --captures-dir /custom/path
```

### Configuration File

Klaus Proxy configuration is stored in `~/.klaus-proxy/config.json`:

```json
{
  "version": "0.1.0",
  "salt": "a848b93e0d59848486bec45d5bfda780",
  "hosts": [
    "api.anthropic.com",
    "llm.tools.cloud.customer1.es"
  ],
  "capture_dir": "/Users/asantacana/.klaus-proxy/captures",
  "vault_path": "/Users/asantacana/.klaus-proxy/captures/.pseudonym_vault.json",
  "log_level": "info"
}
```

To view this in the menu:

```bash
$ klaus
3
3
```

---

## Troubleshooting

### Script Not Found

```bash
# If klaus is not in PATH:
/path/to/klaus --help

# Or use the full path
~/proyectos/klaus-proxy-local/klaus --help
```

### Colors Not Showing

The script uses ANSI colors by default. If colors aren't showing:

```bash
# Run with NO_COLOR environment variable
NO_COLOR=1 klaus

# Or upgrade your terminal to support ANSI colors
```

### Permission Denied

```bash
# Make the script executable
chmod +x ~/.local/bin/klaus
chmod +x ~/proyectos/klaus-proxy-local/klaus
```

### Python Module Not Found

If you see "ModuleNotFoundError: No module named 'Klaus_proxy_local'":

```bash
# Reinstall Klaus Proxy Local in development mode
cd ~/proyectos/klaus-proxy-local
pip install -e .
```

---

## Integration with Existing Workflow

### Add to Shell Startup

```bash
# Add to ~/.zshrc or ~/.bashrc
alias k=klaus

# Then use: k instead of klaus
```

### Shell Function Integration

```bash
# Add to ~/.zshrc for quick audits
audit() {
  klaus audit "$@"
}

fix() {
  klaus fix "$@"
}

scan() {
  klaus scan "$@"
}

# Then use:
$ audit --detailed
$ fix --show-payloads
$ scan ~/my-project
```

### CI/CD Integration

```bash
# In your CI pipeline (e.g., GitHub Actions)
- name: Scan for secrets
  run: |
    cp ~/proyectos/klaus-proxy-local/klaus /usr/local/bin/
    klaus scan . --json > scan_results.json
    
- name: Audit payloads
  run: |
    klaus audit --export csv
```

---

## Version History

- **v0.3.2** — Initial release of interactive Klaus Menu
  - SCAN command with confidence levels and approval workflow
  - AUDIT command with summary/detailed/CSV modes
  - FIX command with diagnostic and configuration viewing
  - Interactive menu with help system
  - Direct command-line invocation support

---

## License

MIT (same as Klaus Proxy Local)

---

**Need help?** Run `klaus --help` or `klaus help` in the menu.
