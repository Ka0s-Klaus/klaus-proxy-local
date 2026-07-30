# 🛡️ Threat Model — Klaus Proxy Local

> **What we protect. What we don't. Why.**

**Status:** ✅ Published  
**Version:** v0.1.0  
**Last updated:** 2026-07-30  
**Related:** [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) | [security.md](./security.md)

---

## 📋 Executive Summary

Klaus Proxy Local protects **data in transit to external APIs**, not against **local system compromise** or **malicious clients**.

```mermaid
graph TB
    USER["🖥️ Your Machine"]
    CLAUDE["Claude Code<br/>(client)"]
    PROXY["🔐 Klaus Proxy<br/>(local, yours)"]
    ANTHROPIC["🌐 Anthropic API<br/>(external)"]
    
    USER -->|your code| CLAUDE
    CLAUDE -->|encrypted HTTPS| PROXY
    PROXY -->|pseudonymized<br/>data| ANTHROPIC
    ANTHROPIC -->|response| PROXY
    PROXY -->|real values<br/>restored| CLAUDE
    
    style USER fill:#90EE90
    style CLAUDE fill:#87CEEB
    style PROXY fill:#FFD700
    style ANTHROPIC fill:#DDA0DD
```

---

## ✅ What We Protect Against

### 1️⃣ Network Eavesdropping

**Threat:** ISP, router, NSA intercepts your HTTPS traffic to Anthropic

**Protection:**
- ✅ HTTPS encryption (end-to-end, Anthropic's TLS)
- ✅ Klaus Proxy validates certificates (mitmproxy does this)
- ✅ No raw data sent to external APIs

**Confidence:** 🟢 **Strong**  
*HTTPS is industry-standard; we trust TLS.*

---

### 2️⃣ Source Code Leaks

**Threat:** Anthropic logs see your project structure and file contents

**Protection:**
- ✅ File paths pseudonymized before transmission
- ✅ File contents seudonimized (variable names, strings)
- ✅ Evidence captured locally (you can audit it)

**Example:**
```
Real:          /home/dev/secret-project/src/payment.py
Anthropic sees: /proj_a1b2c3d4/src/payment.py
You see:       /home/dev/secret-project/src/payment.py (in logs)
```

**Confidence:** 🟢 **Strong**  
*Longest-prefix-first matching prevents accidental exposure.*

---

### 3️⃣ Git Identity Leaks

**Threat:** Anthropic logs reveal your git username, email, remote origin

**Protection:**
- ✅ `git config user.name` seudonimized
- ✅ `git config user.email` seudonimized
- ✅ Remote origin tokens stripped (org/repo names seudonimized)

**Example:**
```
Real:          dev@company.com, "My Corp Org", "secret-project"
Anthropic sees: email_m4n5o6p7, "org_x9y8z7w6", "proj_k1l2m3n4"
```

**Confidence:** 🟢 **Strong**  
*Git metadata is standard attack surface.*

---

### 4️⃣ API Key Exposure

**Threat:** Your Anthropic API key sent in plaintext, intercepted or logged

**Protection:**
- ✅ API key (x-api-key, Authorization headers) redacted **irreversibly**
- ✅ Redaction happens in capture (never stored in plaintext)
- ✅ Cannot be reverted (placeholder `«REDACTED:api-key»`)

**Example:**
```
Real request:  x-api-key: sk-ant-abc123xyz789...
Your disk:     x-api-key: «REDACTED:api-key»
Anthropic sees: x-api-key: «REDACTED:api-key»
```

**Confidence:** 🟢 **Strong**  
*Redaction is irreversible; secret stays yours.*

---

### 5️⃣ IP Address Leaks

**Threat:** Anthropic logs show your office IP or home network

**Protection:**
- ✅ IPv4 addresses (A.B.C.D) seudonimized
- ✅ IPv6 addresses seudonimized
- ⚠️  Exception: loopback (127.0.0.1), public DNS (8.8.8.8) logged as-is

**Example:**
```
Real:          203.0.113.42 (your office)
Anthropic sees: ip_f0o0b4r7 (unidentifiable)
```

**Confidence:** 🟡 **Medium**  
*Exception list errs on side of usability; review if paranoid.*

---

### 6️⃣ Email Address Leaks

**Threat:** Anthropic logs reveal company domain and email patterns

**Protection:**
- ✅ All email addresses seudonimized (regex match)
- ✅ Including embedded emails in file contents

**Example:**
```
Real:          dev@company.com, john+test@corp.co.uk
Anthropic sees: email_a1b2c3d4, email_x9y8z7w6
```

**Confidence:** 🟢 **Strong**  
*Regex covers most formats.*

---

### 7️⃣ Tier-1 Secrets (Credentials)

**Threat:** Private keys, AWS keys, GitHub tokens leaked in clipboard/prompts

**Protection:**
- ✅ PEM private keys detected and redacted
- ✅ AWS access keys (AKIA...) redacted
- ✅ GitHub tokens (ghp_, ghs_, etc.) redacted
- ✅ JWT tokens redacted
- ✅ Slack tokens redacted
- ✅ Google API keys redacted
- ✅ Generic `secret=value` patterns (opt-in, default OFF)

**Example:**
```
Real:          -----BEGIN RSA PRIVATE KEY----- ... -----END RSA PRIVATE KEY-----
Captured:      «REDACTED:private-key»
Anthropic sees: «REDACTED:private-key»
```

**Confidence:** 🟢 **Strong**  
*Redaction is irreversible; secret stays on your machine.*

---

## ❌ What We DON'T Protect Against

### 1️⃣ Root Access / Local Privilege Escalation

**Threat:** Attacker with `sudo` access to your machine

**Why we can't protect:**
- They can read any file, including vault, config, captures
- They can patch the proxy code in memory
- They can keylog your keyboard

**Mitigation:**
- Use full-disk encryption (FileVault on macOS, BitLocker on Windows, LUKS on Linux)
- Use strong password for your account
- Use SELinux or AppArmor if available

**Note:** Klaus Proxy assumes **you are the system owner**.

---

### 2️⃣ Backdoored Claude Code

**Threat:** Claude Code CLI itself is compromised or malicious

**Why we can't protect:**
- Klaus Proxy only intercepts network traffic
- If Claude Code exfiltrates data over a different channel, we can't see it
- If Claude Code logs everything before sending, we can't prevent it

**Mitigation:**
- Install Claude Code from official sources only
- Use `pip install --only-binary` to avoid running malicious setup.py
- Check `pip show claude-code` to verify installation path

**Note:** Klaus Proxy trusts the tools you install.

---

### 3️⃣ Memory Dumps / Cold Boot Attacks

**Threat:** Attacker reboots your machine, dumps RAM, extracts keys

**Why we can't protect:**
- Data in memory before pseudonymization is plaintext
- No tool can prevent memory extraction with physical access

**Mitigation:**
- Set strong BIOS/firmware password
- Use TPM (Trusted Platform Module) if available
- Enable secure boot

---

### 4️⃣ Compromised mitmproxy or OpenSSL

**Threat:** mitmproxy or OpenSSL has a 0-day vulnerability

**Why we can't protect:**
- We depend on these tools for HTTPS interception
- If they're exploited, we can't prevent it

**Mitigation:**
- Keep dependencies up to date: `pip install --upgrade mitmproxy`
- Monitor security advisories
- Use official sources only

---

### 5️⃣ Accidental Leaks (User Error)

**Threat:** You copy a sensitive file to cloud storage, email, or Slack

**Why we can't protect:**
- Klaus Proxy intercepts API traffic, not all file operations
- If you `cp captures/ ~/Dropbox/`, that's on you

**Mitigation:**
- Treat `~/.klaus-proxy/captures/` like a vault (don't copy it)
- Use `.gitignore` to prevent accidental commits
- Review captures before sharing evidence

---

### 6️⃣ Timing Attacks

**Threat:** Anthropic analyzes request frequency/timing to infer patterns

**Why we can't protect:**
- We can't hide the fact that you're using Claude Code
- Timing patterns (when you work, how often you ask) are metadata

**Mitigation:**
- If you're paranoid: use a VPN (adds latency, masks timing)
- If you're not: Klaus Proxy already hides what you're saying

---

## 🔄 What's Pseudonymized vs. Redacted

| Data | Action | Reversible? | Stored Where? |
|------|--------|-------------|---------------|
| File paths | Pseudonymized | ✅ Yes (vault) | `/proj_a1b2c3d4` |
| Usernames | Pseudonymized | ✅ Yes (vault) | `id_x9y8z7w6` |
| Git identity | Pseudonymized | ✅ Yes (vault) | `id_...` |
| Emails | Pseudonymized | ✅ Yes (vault) | `email_...` |
| IPs | Pseudonymized | ✅ Yes (vault) | `ip_...` |
| **Tier-1 secrets** | **Redacted** | ❌ No | `«REDACTED:type»` |
| API keys | Redacted | ❌ No | `«REDACTED»` |

---

## 📊 Threat Matrix

```
Priority | Threat | Klaus Protects? | Note
---------|--------|-----------------|------
🔴 CRITICAL | Anthropic logs your code | ✅ Yes | Pseudonymized
🔴 CRITICAL | ISP sees your data | ✅ Yes | HTTPS encrypted
🔴 CRITICAL | API key leaked | ✅ Yes | Irreversibly redacted
🟠 HIGH | Your office IP exposed | ✅ Yes | Pseudonymized
🟠 HIGH | Git identity revealed | ✅ Yes | Pseudonymized
🟡 MEDIUM | Timing analysis | ❌ No | Use VPN if paranoid
🔵 LOW | Local root access | ❌ No | Use full-disk encryption
🔵 LOW | Claude Code is malware | ❌ No | Trust your tools
```

---

## ⚡ How It Works (30-Second Version)

```
┌─────────────────────────────────────────────────┐
│ 1. You write a prompt that mentions "/home/dev" │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. Claude Code sends to http://127.0.0.1:8899   │
│    (your local proxy)                            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. Klaus Proxy intercepts:                      │
│    - Replaces "/home/dev" → "/proj_a1b2c3d4"   │
│    - Saves both versions (captured)             │
│    - Forwards seudonimized version to Anthropic │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 4. Anthropic sees:                              │
│    "Read /proj_a1b2c3d4/file.txt"              │
│    (no idea what that path is)                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 5. Response comes back:                         │
│    "Contents of /proj_a1b2c3d4/file.txt:"      │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 6. Klaus Proxy reverts:                         │
│    Replaces "/proj_a1b2c3d4" → "/home/dev"    │
│    Sends to Claude Code                         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 7. You see:                                     │
│    "Contents of /home/dev/file.txt:"           │
│    (your real paths, Claude Code works normally)│
└─────────────────────────────────────────────────┘
```

---

## 📋 Security Checklist for Users

Before using Klaus Proxy:

- [ ] I understand what it protects (data pseudonymization)
- [ ] I understand what it doesn't protect (local admin, malware)
- [ ] I trust the tools I'm using (Claude Code, mitmproxy, Python)
- [ ] I have disk encryption enabled (macOS FileVault, Windows BitLocker, etc.)
- [ ] I review captures before sharing evidence with others
- [ ] I don't commit `~/.klaus-proxy/` to git

---

## 🤝 Responsible Disclosure

Found a security issue? See [security.md](./security.md) for how to report safely.

---

## 🔗 See Also

- [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) — v0.1.0 fixes
- [security.md](./security.md) — Security policy & disclosure
- [architecture.md](./architecture.md) — How it works technically
- [plan-pruebas-control.md](./plan-pruebas-control.md) — Test plan

---

**Last reviewed:** 2026-07-30  
**Status:** ✅ Approved for v0.1.0  
**Confidence:** 🟢 Medium-High
