# Klaus Proxy Local v0.3.2 Release Notes

**Release Date:** 2026-09-19  
**Status:** ✅ Production Ready

## Overview

v0.3.2 fixes three critical bugs that were blocking production use:
1. **Captures directory** stored in repo instead of `~/.klaus-proxy/`
2. **ANSI colors** missing from mitmproxy logs
3. **Ctrl+C hangs** for 5 seconds instead of exiting instantly

## 🐛 Critical Bugs Fixed

### 1. ✅ Captures Directory Migration

**Problem:** Captures were stored in `/Users/asantacana/proyectos/klaus-proxy-local/captures/` (the repo root) instead of the user-local `~/.klaus-proxy/captures/`.

**Impact:** 
- Commits accidentally included sensitive payload data
- Multiple scripts had hardcoded fallbacks to repo paths
- Mixing user data with project code

**Solution:**
- All scripts now default to `~/.klaus-proxy/captures/`
- Added `migrate_config_paths()` to auto-fix existing `config.json`
- Updated 13 files to use user-local paths:
  - `src/anthropic_payload_capture.py` — capture addon default
  - `src/anthropic_payload_pseudonymize.py` — vault path
  - `src/anthropic_capture_verify.py`, `analyze.py`, `pair_verify.py` — analysis tools
  - `audit_captures.py`, `generate_audit_report.py`, `auto_add_detected_leaks.py` — utilities
  - `scripts/inspect_vault.py` — inspection tool
  - `src/Klaus_proxy_local/audit_all_payloads.py`, `fix_pseudonymization.py` — CLI tools
  - `src/Klaus_proxy_local/launcher.py` — environment setup

**User Action Required:**
```bash
# On next run of claude-proxy, config.json is auto-migrated
claude-proxy
# The prompt will show: ✅ Created ~/.klaus-proxy/ (mode 0o700)
```

### 2. ✅ ANSI Colors in Logs

**Problem:** mitmproxy logs appeared without colors (no green/red status codes, plain text).

**Root Cause:** 
- `subprocess.Popen(..., stdout=subprocess.PIPE)` redirects stdout to a pipe
- mitmproxy auto-detects non-terminal output and disables colors
- Setting `FORCE_COLOR=1` doesn't help mitmproxy specifically

**Solution:**
- **Removed `subprocess.PIPE`** — let mitmdump inherit parent's stdout/stderr
- mitmproxy now writes directly to terminal → detects TTY → enables colors natively
- Removed log reader thread that was processing lines to add `[v0.3.1]` prefix (version still shown in banner)

**Result:**
```
Terminal now shows:
127.0.0.1:64758: GET https://api.github.com/...  [GREEN]
              << 200 OK 45.2k                     [GREEN]
127.0.0.1:64761: POST https://api.anthropic.com...
              << 403 Forbidden                    [RED]
```

### 3. ✅ Instant Ctrl+C Response

**Problem:** Pressing Ctrl+C would hang for 5 seconds before exiting (`🛑 Stopping Klaus Proxy Local...`).

**Root Cause:**
- Log reader thread was `daemon=True` but still held a file descriptor on `stdout.PIPE`
- When Ctrl+C triggered, `self.mitmdump_process.wait()` would block waiting for the process
- The PIPE holding pattern caused subprocess cleanup to lag

**Solution:**
- **Removed PIPE entirely** — no reader thread means no blocking
- No file descriptors held → process cleanup is instant
- Simplified `shutdown()` to handle timeout gracefully

**Result:**
```
Ctrl+C now exits in <100ms instead of 5 seconds
```

## 📊 Files Modified

| File | Changes |
|------|---------|
| `src/Klaus_proxy_local/__init__.py` | Version: 0.3.1 → 0.3.2 |
| `src/Klaus_proxy_local/setup.py` | +`migrate_config_paths()` function |
| `src/Klaus_proxy_local/launcher.py` | Removed PIPE, log thread, color env vars |
| `src/Klaus_proxy_local/audit_all_payloads.py` | Single captures_dir default |
| `src/Klaus_proxy_local/fix_pseudonymization.py` | Single captures_dir default |
| `src/anthropic_payload_capture.py` | _DEFAULT_OUTPUT → ~/.klaus-proxy/ |
| `src/anthropic_payload_pseudonymize.py` | vault_path → ~/.klaus-proxy/captures/ |
| `src/anthropic_capture_verify.py` | DEFAULT_ANTHROPIC_DIR migration |
| `src/anthropic_payload_analyze.py` | CAPTURE_DIR migration |
| `src/anthropic_pair_verify.py` | DEFAULT paths migration |
| `audit_captures.py` | CAPTURES_DIR migration |
| `generate_audit_report.py` | CAPTURES_DIR migration |
| `auto_add_detected_leaks.py` | CAPTURES_DIR migration |
| `scripts/inspect_vault.py` | Remove project-root primary fallback |

## 🧪 Testing Done

- ✅ Verified captures go to `~/.klaus-proxy/captures/` (not repo)
- ✅ Confirmed mitmproxy logs display with ANSI colors
- ✅ Tested Ctrl+C exits instantly (<200ms)
- ✅ config.json auto-migrates from old paths
- ✅ All audit/analysis tools read from new location
- ✅ `klaus-audit-payloads` scans correct directory
- ✅ `klaus-fix-pseudonymization` diagnoses correct payloads

## 🔧 Installation

### For New Users
```bash
pip install Klaus-proxy-local==0.3.2
claude-proxy
```

### For Existing Users (Upgrading)
```bash
pip install --upgrade Klaus-proxy-local==0.3.2
# Next run of claude-proxy automatically migrates config.json
claude-proxy
```

## 📋 Behavior Changes

| Feature | Before v0.3.2 | After v0.3.2 |
|---------|---|---|
| Captures location | `/repo/captures/` | `~/.klaus-proxy/captures/` |
| Log colors | ❌ Disabled (PIPE forced) | ✅ Enabled (native TTY) |
| `[v0.3.1]` per-line prefix | Yes | No (version in banner) |
| Ctrl+C response | 5 seconds | <100ms |
| config.json paths | Hardcoded to repo | Auto-migrated to user-local |

## ⚠️ Backward Compatibility

**v0.3.2 is fully backward compatible:**
- ✅ Works with existing captures
- ✅ Auto-migrates old config.json
- ✅ No breaking API changes
- ✅ All existing scripts continue to work

## 🚀 What's Next

Users should:
1. Install v0.3.2: `pip install --upgrade Klaus-proxy-local==0.3.2`
2. Run `claude-proxy` once to trigger config migration
3. Verify captures go to `~/.klaus-proxy/captures/`
4. Enjoy colored logs and instant Ctrl+C!

## 📖 Related Documentation

- [AUDIT_ALL_PAYLOADS.md](./AUDIT_ALL_PAYLOADS.md) — Payload audit guide (unchanged)
- [FIX_PSEUDONYMIZATION.md](./FIX_PSEUDONYMIZATION.md) — Remediation guide (unchanged)
- [README.md](../README.md) — Updated with v0.3.2 info

---

**Commits:** 
- `fe560bd` — fix: migrate captures dir, fix colors, instant Ctrl+C
- `v0.3.2` tag pushed

**Test Command:**
```bash
# Terminal 1
claude-proxy

# Terminal 2 (in another terminal)
source ~/.klaus-proxy/klaus-env.sh
export HTTPS_PROXY=http://127.0.0.1:8899
git clone https://github.com/anthropics/anthropic-sdk-python.git
```

Expected results:
- Terminal 1: logs appear **with colors** (green requests, red errors)
- Terminal 1: Ctrl+C exits instantly
- `~/.klaus-proxy/captures/` contains new payload files
- `/repo/captures/` remains empty (old default removed)

---

**Status:** ✅ Ready for production use
