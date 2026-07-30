# 🚀 Quick Start — Klaus Proxy Local

> **Get started in 2 minutes.**

**Status:** ✅ Ready for v0.1.0  
**Audience:** Individual developers  
**Related:** [THREAT_MODEL.md](./THREAT_MODEL.md) | [architecture.md](./architecture.md) | [setup.md](./setup.md)

---

## 🤔 What is Klaus Proxy?

Klaus Proxy is a **privacy tool** that sits between your Claude Code and Anthropic's API.

- 🔐 **Your data stays yours** — sensitive info is pseudonymized before leaving your machine
- 📋 **You control the evidence** — captures stored locally, never synced
- 🎯 **No configuration** — just install and run
- ❌ **Fail-closed** — if the proxy stops, Claude Code stops (never leaks without audit)

**Example:**
```
Your prompt:   "Read /home/dev/secret-project/main.py and fix the bug"
Anthropic sees: "Read /proj_a1b2c3d4/main.py and fix the bug"
You see:       "Read /home/dev/secret-project/main.py and fix the bug"
               (Claude Code works normally)
```

See [THREAT_MODEL.md](./THREAT_MODEL.md) for what's protected and what's not.

---

## ⚡ 3 Ways to Use Klaus Proxy

Pick the one that fits your workflow.

### **Option 1: Wrapper Script** (Recommended 🟢)

**Works everywhere.** Doesn't modify your shell config.

#### Install
```bash
pip install Klaus-proxy-local
```

#### Use
```bash
# Terminal 1: Start the proxy
claude-proxy

# Terminal 2: Use Claude Code (in a different terminal)
claude-with-proxy "your question"
```

**Pros:**
- ✅ Works on bash, zsh, fish, PowerShell, CMD
- ✅ Doesn't modify your config files
- ✅ Manual opt-in (only when you use `claude-with-proxy`)

**Cons:**
- ⚠️ You must use `claude-with-proxy` instead of `claude`

---

### **Option 2: Auto-Enable** (Recommended for daily use 🟡)

**Automatic.** One-time setup, then Klaus Proxy activates whenever it's running.

#### Install
```bash
pip install Klaus-proxy-local
```

#### One-time setup
```bash
klaus-setup
```

You'll see:
```
🔐 Klaus Proxy Local Setup

Shell detected: zsh
Config file: ~/.zshrc

Enable Klaus Proxy auto-startup? [y/N]: 
```

Answer `y` and reload your shell:
```bash
exec $SHELL
```

#### Use
```bash
# Terminal 1: Start the proxy
claude-proxy

# Terminal 2: Use Claude Code normally
claude "your question"
# Automatically routed through proxy if it's running
```

**Pros:**
- ✅ Fully automatic (just use `claude` as normal)
- ✅ Works on bash, zsh, fish, PowerShell

**Cons:**
- ⚠️ Modifies your shell config (~/.zshrc, ~/.bashrc, etc.)
- ⚠️ Environment variables only active if proxy is running

---

### **Option 3: Manual** (For advanced users 🔵)

**Explicit control.** You manage environment variables yourself.

```bash
# Set environment variables before running Claude Code
export HTTPS_PROXY=http://127.0.0.1:8899
export HTTP_PROXY=http://127.0.0.1:8899
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem

# Terminal 1: Start proxy
claude-proxy

# Terminal 2: Use Claude Code
claude "your question"
```

**Pros:**
- ✅ Explicit (you know exactly what's happening)
- ✅ Works anywhere

**Cons:**
- ⚠️ Manual setup every shell session
- ⚠️ Easy to forget

---

## 🎯 Complete Example (Option 1 — Recommended)

### Step 1: Install
```bash
$ pip install Klaus-proxy-local
Successfully installed Klaus-proxy-local-0.1.0
```

### Step 2: Terminal 1 — Start the proxy
```bash
$ claude-proxy

🔐 Klaus Proxy Local v0.1.0

✅ Config initialized at ~/.klaus-proxy/
✅ Certificates ready
📡 Proxy listening on http://127.0.0.1:8899

✨ Ready. Start Claude Code in another terminal with:
   claude-with-proxy "your question"

Press Ctrl+C to stop
```

### Step 3: Terminal 2 — Use Claude Code
```bash
$ claude-with-proxy "explain this code snippet"

✅ Proxy detected on 127.0.0.1:8899

> [loads Claude Code and routes through proxy]
```

### Step 4: After you're done
Press Ctrl+C in Terminal 1 to stop the proxy.

Check what was captured:
```bash
$ anthropic-capture-verify

🔍 Verification Report

✅ Destination: llm.tools.cloud.customer1.es/v1/messages
✅ Secrets redacted: Authorization = «REDACTED»
✅ No plaintext leaks: 14 values checked
✅ Pseudonymization active: 8 seudónimos detected

✅ TODO CORRECTO
```

---

## 📍 Where Are My Captures?

All captures stored locally:

```
~/.klaus-proxy/
├── captures/
│   ├── original/          # What your code actually contains
│   │   └── 20260730_143015_anthropic_payload.json
│   ├── sent/              # What actually left your machine
│   │   └── 20260730_143015_anthropic_payload.json
│   └── .vault.json        # Mapping (real ↔ pseudonym)
├── config.json            # Your configuration
└── .mitmproxy-ca-cert.pem # SSL certificate
```

**Important:**
- ✅ These files are **yours** — you control them
- ✅ Never synced to internet
- ✅ Never committed to git (they're gitignored)
- ✅ Delete them anytime: `rm -rf ~/.klaus-proxy/captures/`

---

## ❓ FAQ

### Q: What if the proxy crashes?
**A:** Claude Code will hang waiting for the proxy and eventually timeout. It will **never** send unaudited data. (This is by design — fail-closed.)

**Solution:** Restart the proxy in Terminal 1.

---

### Q: Can I use Klaus Proxy with multiple projects?
**A:** Yes! All captures go to the same vault. The mapping is per-machine, not per-project.

---

### Q: How much overhead does this add?
**A:** Minimal. Klaus Proxy adds ~50-200ms latency (one extra hop) and ~5% CPU. The bottleneck is still Claude Code's inference.

---

### Q: Can I disable Klaus Proxy for specific requests?
**A:** Not easily. The proxy is all-or-nothing. If you need unproxied requests, stop the proxy and use `claude` directly.

---

### Q: What if I want to share captures with others?
**A:** The captures contain your real data (paths, usernames, emails). **Don't share them publicly.** If you need to share as evidence:

1. Review the captures:
   ```bash
   ls ~/.klaus-proxy/captures/sent/
   ```
2. Share **only** the `sent/` directory (already pseudonymized)
3. **Never** share the vault (`..pseudonym_vault.json`) — it reveals the mapping

---

### Q: What's the vault file?
**A:** It's the **real ↔ pseudonym mapping**. Example:

```json
{
  "/home/dev/secret-project": "/proj_a1b2c3d4",
  "dev@company.com": "email_m4n5o6p7",
  "myusername": "id_x9y8z7w6"
}
```

**Important:** This file is `chmod 0o600` (only you can read it). **Never share it.**

---

### Q: What if I disconnect the internet?
**A:** Klaus Proxy works locally. If you disconnect before using Claude Code, the request will fail (can't reach Anthropic). Klaus Proxy can't help with that.

---

### Q: Does this work on Windows?
**A:** Yes. Use PowerShell:

```powershell
# Option 1: Wrapper
claude-with-proxy "your question"

# Option 2: Auto-enable (PowerShell profile)
klaus-setup

# Option 3: Manual env vars
$env:HTTPS_PROXY = "http://127.0.0.1:8899"
$env:HTTP_PROXY = "http://127.0.0.1:8899"
claude "your question"
```

---

### Q: Does this work on Linux?
**A:** Yes. Same as macOS:

```bash
# Option 1: Wrapper
claude-with-proxy "your question"

# Option 2: Auto-enable (bash/zsh/fish)
klaus-setup

# Option 3: Manual env vars
export HTTPS_PROXY=http://127.0.0.1:8899
claude "your question"
```

---

### Q: What if Klaus Proxy has a bug?
**A:** Report it to [SECURITY.md](./security.md). If it's critical, don't disclose publicly until it's fixed.

---

## 📚 Learn More

| Topic | Document |
|-------|----------|
| **How does it work?** | [architecture.md](./architecture.md) |
| **What's protected?** | [THREAT_MODEL.md](./THREAT_MODEL.md) |
| **Full setup guide** | [setup.md](./setup.md) |
| **Security fixes** | [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) |

---

## ✅ Quick Checklist

- [ ] `pip install Klaus-proxy-local` works
- [ ] `claude-proxy` starts without errors
- [ ] `claude-with-proxy "test"` routes through proxy
- [ ] `~/.klaus-proxy/` directory created
- [ ] `anthropic-capture-verify` shows captures
- [ ] Ready to use!

---

**Next steps:**
1. Choose your method (Option 1 recommended)
2. Start the proxy
3. Use Claude Code
4. Check captures with `anthropic-capture-verify`
5. Read [THREAT_MODEL.md](./THREAT_MODEL.md) to understand what's protected

---

**Questions?** See [THREAT_MODEL.md](./THREAT_MODEL.md) FAQ or [security.md](./security.md).

---

**Version:** v0.1.0  
**Last updated:** 2026-07-30  
**Status:** ✅ Ready for release
