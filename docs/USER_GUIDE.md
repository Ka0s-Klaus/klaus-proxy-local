# Klaus Proxy Local - User Guide

## Overview

Klaus Proxy Local is a **privacy-first audit proxy** for Claude Code. It sits between your CLI and Anthropic's API, intercepting requests to audit what you send, redacting secrets, and ensuring compliance.

**Key Benefits:**
- ✅ See exactly what Claude sends to Anthropic
- ✅ Secrets automatically redacted (pseudonymized)
- ✅ Audit trail for compliance
- ✅ Zero configuration needed (auto-setup)

## Installation

```bash
# From PyPI
pip install Klaus-proxy-local

# Or from source
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
pip install -e .
```

## Quick Start (2 minutes)

### Terminal 1: Start the proxy

```bash
claude-proxy
```

**First run:** Auto-generates config, certificates, and shell integration.

Output:
```
🚀 Klaus Proxy Local
  ▶️  Proxy running at http://127.0.0.1:8899
  📁 Captures in: ~/.klaus-proxy/../captures/
  🔑 Vault at: ~/.klaus-proxy/../captures/.pseudonym_vault.json
  ⚙️  Config at: ~/.klaus-proxy/config.json
```

### Terminal 2: Use Claude Code with proxy

**macOS/Linux:**
```bash
export HTTPS_PROXY=http://127.0.0.1:8899
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca.pem
claude "write me a hello world"
```

**Windows (PowerShell):**
```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:8899"
$env:NODE_EXTRA_CA_CERTS = "$env:USERPROFILE\.mitmproxy\mitmproxy-ca.pem"
claude "write me a hello world"
```

**Or use the auto-setup aliases:**
```bash
# These are auto-created by claude-proxy on first run
claude-with-proxy "your prompt here"
```

## What Gets Captured

### Before (Real data)

```json
{
  "messages": [
    {
      "content": "Read /home/alice/secrets.env and analyze for SQL vulnerabilities"
    }
  ]
}
```

### After (Pseudonymized)

```json
{
  "messages": [
    {
      "content": "Read /proj_a1b2c3d4/secrets.env and analyze for SQL vulnerabilities"
    }
  ]
}
```

### Captured

```
captures/
├── original/
│   └── 20260903_120000_payload.json  ← Your REAL paths, emails, IPs
├── sent/
│   └── 20260903_120000_payload.json  ← Pseudonymized before sending
└── .pseudonym_vault.json              ← The mapping (keep SECRET!)
```

## Understanding the Vault

The `.pseudonym_vault.json` file is the **key to your audit trail**:

```json
{
  "real_to_pseudo": {
    "/home/alice/project": "/proj_a1b2c3d4",
    "alice": "/user_x9y8z7w6",
    "alice@example.com": "/email_z9y8x7w6"
  },
  "pseudo_to_real": {
    "/proj_a1b2c3d4": "/home/alice/project",
    "/user_x9y8z7w6": "alice",
    "/email_z9y8x7w6": "alice@example.com"
  }
}
```

**⚠️ IMPORTANT:** This file contains your real values encrypted by hash. Keep it secret!

```bash
# Secure it
chmod 600 ~/.klaus-proxy/../captures/.pseudonym_vault.json
```

## Audit Workflow

### Step 1: Review what was sent

```bash
cat ~/.klaus-proxy/../captures/sent/latest_payload.json | jq .
```

No real values visible! Only pseudonyms.

### Step 2: Reference the vault

If you need to know what a pseudonym represents:

```bash
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.pseudo_to_real."<pseudonym>"'
```

### Step 3: Delete when done

```bash
rm -rf ~/.klaus-proxy/../captures/*
```

Captures are NOT versioned (see `.gitignore`).

## Security Scanning

Klaus Proxy also scans outgoing payloads for accidental secret leaks:

```bash
# Launch the scanner
klaus-scan
```

**Detection includes:**
- API keys (AWS, OpenAI, GitHub, etc.)
- Database credentials
- Private keys
- OAuth tokens
- High-entropy strings

**Review findings:**
```bash
cat ~/.klaus-proxy/../captures/scan_results.json | jq '.findings[] | {category, confidence}'
```

## Configuration

### Environment Variables

Set before running `claude-proxy`:

```bash
export ANTHROPIC_CAPTURE_HOSTS="api.anthropic.com,my-llm-gateway.com"
export ANTHROPIC_CAPTURE_DIR="./my-captures/"
export ANTHROPIC_PSEUDO_ENABLE=1
```

### Config File

Edit `~/.klaus-proxy/config.json`:

```json
{
  "capture_dir": "./captures/",
  "capture_hosts": [
    "api.anthropic.com",
    "llm.tools.cloud.customer1.es"
  ],
  "enable_pseudonymization": true,
  "enable_scanning": true
}
```

## Troubleshooting

### Q: Port 8899 already in use

```bash
# Find what's using it
lsof -i :8899

# Kill it
kill -9 <PID>

# Or use a different port
ANTHROPIC_PROXY_PORT=9000 claude-proxy
```

### Q: "certificate verify failed" errors

```bash
# Regenerate certs
rm -rf ~/.mitmproxy/
claude-proxy
# (Will auto-regenerate on startup)
```

### Q: Where are my captures?

```bash
ls -la ~/.klaus-proxy/../captures/
# or
echo $ANTHROPIC_CAPTURE_DIR
```

### Q: How do I disable pseudonymization temporarily?

```bash
export ANTHROPIC_PSEUDO_ENABLE=0
claude-with-proxy "test"
```

### Q: Can I use this with other Claude clients?

Currently: Claude Code CLI only.

Future: Claude Desktop, web access, etc.

## Performance

Klaus Proxy adds minimal overhead:

- **Request latency:** +5ms (pseudonymization)
- **Response latency:** +2ms (restoration)
- **Memory:** ~50MB

## Privacy Statement

- ✅ Captures are **local only** (never uploaded)
- ✅ Vault is **encrypted by hash** (cannot be reversed without salt)
- ✅ Salt is **environment-based** (ANTHROPIC_PSEUDO_SALT)
- ✅ Proxy runs on **localhost:8899** (not accessible remotely)

## Getting Help

- **Issues:** https://github.com/Ka0s-Klaus/klaus-proxy-local/issues
- **Docs:** https://github.com/Ka0s-Klaus/klaus-proxy-local/tree/main/docs
- **Security:** See SECURITY.md
