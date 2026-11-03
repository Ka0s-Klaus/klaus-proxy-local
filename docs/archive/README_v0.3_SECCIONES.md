# 🗄️ Secciones del README de la época v0.3

> ⚠️ **Archivado en #177.** Estas secciones estaban en el `README.md` hasta la v0.9.0. Describen el proyecto como era en la v0.3: el marcador del bloque de shell («🔐 Klaus Proxy Local — Auto-startup») ya no es el que usa `klaus-setup`, y las novedades son de septiembre de 2026. Lo vigente está en el [README](../../README.md#-terminales-y-certificados).

---

## 🔐 SSL/TLS Certificate Trust (v0.3.0+)

Klaus Proxy now **automatically configures** SSL/TLS certificate trust for all your tools. No more "Client TLS handshake failed" errors.

### How It Works

When you start `claude-proxy`, it automatically generates `~/.klaus-proxy/klaus-env.sh` containing:

```bash
export GIT_SSL_CAINFO="$HOME/.klaus-proxy/ca-bundle.pem"
export CURL_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export SSL_CERT_FILE="$HOME/.klaus-proxy/ca-bundle.pem"
export REQUESTS_CA_BUNDLE="$HOME/.klaus-proxy/ca-bundle.pem"
export NODE_EXTRA_CA_CERTS="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
```

This tells your tools (git, curl, Python, Node.js) to trust the proxy's certificate automatically.

`ca-bundle.pem` = system CAs + the proxy CA, regenerated on every `claude-proxy` start.
The first four variables **replace** the trust store, so pointing them at the proxy CA
alone would break HTTPS that doesn't go through the proxy. `NODE_EXTRA_CA_CERTS` only
**adds** to Node's store, so it uses the proxy CA directly.

### Setup Options

#### Option 1: Every terminal through the proxy (`klaus-setup`)

```bash
klaus-setup          # one-time; answer "y"
exec $SHELL
```

It adds a block between `# >>> Klaus Proxy Local (klaus-setup) >>>` markers to your shell config (bash, zsh or fish; run it again to update it). In every new terminal it:

- ✅ loads `klaus-env.sh` (trust in the proxy CA);
- ✅ starts `claude-proxy` in the background (`nohup`) if it is not running, logging to `~/.klaus-proxy/logs/autostart.log`;
- ✅ exports `HTTPS_PROXY` and `NO_PROXY` (loopback stays direct), so plain `claude` goes through the proxy.

Things to know:

- **All HTTPS of the terminal goes through the proxy** (pip, git, curl, brew…) and each connection is logged in `~/.klaus-proxy/logs/proxy.log`. Only what is audited is decrypted: `api.anthropic.com`, the `hosts` of `config.json` and the host of `ANTHROPIC_BASE_URL` (decrypted, pseudonymized and captured), plus the `capture_only_hosts` (decrypted and captured but **not** pseudonymized, for traffic that would break with pseudonyms, such as the claude.ai MCP connectors at `mcp-proxy.anthropic.com`). Everything else goes through as a TLS tunnel with the server's real certificate, so no tool gets certificate errors; the log records `TÚNEL host:port` (host and time, not contents). `"intercept_all": true` in `config.json` (or `KLAUS_INTERCEPT_ALL=1`) decrypts everything, as before. `klaus-off` / `klaus-on` drop or restore `HTTPS_PROXY` in one terminal.
- **A gateway other than Anthropic must be in `hosts` of `config.json`** (or in `ANTHROPIC_BASE_URL`): otherwise it would be tunnelled without pseudonymization.
- The proxy registers the org/repo of the folder where it **starts**: the first terminal you open. For a different repo, stop it and start `claude-proxy` from that repo.
- Right after opening the first terminal the proxy needs a few seconds to listen.
- To disable it, remove the marked block from your shell config.

#### Option 1b: Only for Claude Code (`claude-with-proxy`)

```bash
claude-with-proxy        # same arguments as claude
```

Installed by `install.sh` in `~/.local/bin`. Loads `klaus-env.sh` and runs `claude` with `HTTPS_PROXY` **only if the proxy is listening**; otherwise it refuses (fail-closed). It doesn't start the proxy.

#### Option 2: Manual (Quick Test)

```bash
# Terminal 1: Start proxy
claude-proxy

# Terminal 2: Load SSL/TLS variables
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

# Now use git, curl, or Claude Code
git clone https://github.com/your-repo
curl https://api.github.com
claude "your question"
```

#### Option 3: Persistent in Shell Config

Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Load Klaus Proxy SSL/TLS configuration
[ -f ~/.klaus-proxy/klaus-env.sh ] && source ~/.klaus-proxy/klaus-env.sh

# Set proxy for HTTPS connections
export HTTPS_PROXY=http://127.0.0.1:8899
```

Then reload:
```bash
exec $SHELL
```

### Usage Examples

**Git Clone (HTTPS)**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

git clone https://github.com/anthropics/anthropic-cli.git
# ✅ Works without certificate errors
```

**Git Push with Proxy**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

git push origin main
# ✅ All HTTPS git operations work
```

**Curl (HTTPS)**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

curl https://api.github.com
# ✅ Proxy's certificate is trusted automatically
```

**Python Requests**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

python3 -c "import requests; print(requests.get('https://api.github.com').status_code)"
# ✅ REQUESTS_CA_BUNDLE is set automatically
```

**Node.js Tools**
```bash
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899

# NODE_EXTRA_CA_CERTS is exported by klaus-env.sh
npm install
# ✅ Works through proxy
```

### What Gets Configured

| Tool | Variable | Configured | Status |
|------|----------|-----------|--------|
| **git** | `GIT_SSL_CAINFO` | ✅ Auto | Works |
| **curl** | `CURL_CA_BUNDLE` | ✅ Auto | Works |
| **OpenSSL** | `SSL_CERT_FILE` | ✅ Auto | Works |
| **Python** | `REQUESTS_CA_BUNDLE` | ✅ Auto | Works |
| **Node.js / Claude Code** | `NODE_EXTRA_CA_CERTS` | ✅ Auto | Works |

### Disable Auto-Startup (If Needed)

If you enabled auto-startup but want to disable it:

1. Remove the Klaus Proxy hook from your shell config:
   - Edit `~/.zshrc` (or `~/.bashrc`)
   - Find the section: `🔐 Klaus Proxy Local — Auto-startup`
   - Delete those lines
   - Save and reload: `exec $SHELL`

2. Or keep the hook but manually start/stop the proxy:
   ```bash
   # Start manually when needed
   claude-proxy
   ```

### Troubleshooting

**"Still getting TLS handshake errors?"**

1. Ensure environment variables are loaded:
   ```bash
   source ~/.klaus-proxy/klaus-env.sh
   env | grep SSL
   # Should show: GIT_SSL_CAINFO, CURL_CA_BUNDLE, SSL_CERT_FILE (→ ~/.klaus-proxy/ca-bundle.pem)
   ```

2. Verify certificate exists:
   ```bash
   file ~/.mitmproxy/mitmproxy-ca-cert.pem
   # Should be: PEM certificate
   ```

3. Check proxy is running:
   ```bash
   pgrep -f mitmdump
   # Should show a PID
   ```

4. Test with verbose output:
   ```bash
   GIT_TRACE=1 git ls-remote https://github.com/anthropics/anthropic-cli.git
   # Should succeed without SSL errors
   ```

---

## ✨ What's New in v0.3.2

### 🐛 Critical Bugs Fixed

| Issue | Before | After |
|-------|--------|-------|
| **Captures location** | `/repo/captures/` ❌ | `~/.klaus-proxy/captures/` ✅ |
| **Log colors** | Disabled (no colors) ❌ | Full ANSI support ✅ |
| **Ctrl+C response** | 5 second hang ❌ | Instant (<100ms) ✅ |

### 🔧 Changes

1. **Captures Migration**
   - All scripts now use `~/.klaus-proxy/captures/` by default
   - Auto-migrates existing `config.json` on startup
   - 13 files updated (capture, analyze, verify, audit scripts)

2. **ANSI Colors Restored**
   - Removed `subprocess.PIPE` that forced mitmproxy to disable colors
   - mitmproxy now inherits parent TTY → detects terminal → enables colors natively
   - Logs show with full color support (green requests, red errors)

3. **Instant Ctrl+C**
   - Removed log reader thread holding file descriptor
   - Process exits in <100ms (was 5 seconds)
   - No hanging on shutdown

### 📖 Documentation

- **[RELEASE_v0.3.2_NOTES.md](../RELEASE_v0.3.2_NOTES.md)** — Complete bugfix details + testing results

### ✅ Backward Compatibility

- ✅ Fully compatible with v0.3.1 and earlier
- ✅ Auto-migrates old `config.json` paths
- ✅ No breaking changes to API or scripts

[📖 Release Notes](../RELEASE_v0.3.2_NOTES.md)

---

## ✨ What's New in v0.3.1

### 🆕 New Commands

| Command | Purpose | Usage |
|---------|---------|-------|
| **`klaus-audit-payloads`** | Audit all captured payloads | `klaus-audit-payloads` |
| **`klaus-fix-pseudonymization`** | Diagnose pseudonymization issues | `klaus-fix-pseudonymization --show-payloads` |

### 🆕 New Features

1. **Automatic Payload Auditing**
   - Executive summary with security assessment
   - Pseudonymization effectiveness metrics
   - Secret redaction verification
   - Breakdown by HTTP method, host, status code
   - CSV export for compliance
   - Security rating: EXCELLENT / GOOD / NEEDS REVIEW

2. **Pseudonymization Diagnostics**
   - Identifies why payloads aren't pseudonymized
   - Shows non-pseudonymized payloads with details
   - Reviews configuration (patterns, SALT, enabled flag)
   - Provides actionable remediation steps
   - Distinguishes safe-to-skip hosts (monitoring) vs. critical (APIs)

3. **SSL/TLS Auto-Configuration**
   - Auto-generates `~/.klaus-proxy/klaus-env.sh`
   - Exports GIT_SSL_CAINFO, CURL_CA_BUNDLE, SSL_CERT_FILE
   - Shell hook auto-loads variables on startup
   - Fixes "Client TLS handshake failed" errors
   - Works with git, curl, Python, Node.js

### 📖 New Documentation

- **[AUDIT_ALL_PAYLOADS.md](../AUDIT_ALL_PAYLOADS.md)** — Complete audit guide (400+ lines)
- **[FIX_PSEUDONYMIZATION.md](../FIX_PSEUDONYMIZATION.md)** — Remediation guide (500+ lines)
- SSL/TLS setup in README with examples for git, curl, Python, Node.js

### 🔧 Improvements

- Capture directory auto-detection (project root or home directory)
- Beautiful unicode-boxed output with status indicators
- Comprehensive error handling and recommendations
- Decision matrix for quick host classification
