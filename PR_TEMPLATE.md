# PR: Fix Python 3 Compatibility in Klaus Interactive Menu

## Title
```
fix: replace all python with python3 in klaus menu functions
```

## Description

### Problem

The Klaus interactive menu had incomplete Python 3 compatibility. While some references to `python` were changed to `python3` in the direct CLI mode, the interactive menu functions still called `python -m` which caused:

```
/Users/asantacana/.local/bin/klaus: line 224: python: command not found
```

This error occurred when users selected:
- **Option 2 (AUDIT)** — Interactive menu called `cmd_audit()` function with `python -m Klaus_proxy_local.audit_all_payloads`
- **Option 1 (SCAN)** — Interactive menu called `cmd_scan()` function with `python -m Klaus_proxy_local.scan`
- **Option 3 (FIX)** — Interactive menu called `cmd_fix()` function with `python -m Klaus_proxy_local.fix_pseudonymization`

### Root Cause

macOS does not have `python` in PATH (only `python3`). The previous incomplete fix only changed the direct CLI code path but missed the interactive menu function implementations.

### Solution

Replaced all remaining `python -m` calls with `python3 -m` in all three command handler functions.

### Changes Made

#### File: `klaus` (main interactive script)

| Function | Line | Changed |
|----------|------|---------|
| `cmd_scan()` | 183 | `python -m` → `python3 -m` |
| `cmd_audit()` | 224 | `python -m` → `python3 -m` |
| `cmd_fix()` | 265 | `python -m` → `python3 -m` |

Also updated:
- `scripts/klaus` (distribution copy)
- `~/.local/bin/klaus` (installed binary)

### Verification

✅ **No remaining python -m references:**
```bash
$ grep -n "python -m" ./klaus
# Result: (no output - all fixed)
```

✅ **Python 3 is available:**
```
$ which python3
/usr/bin/python3

$ python3 --version
Python 3.9.6
```

### Testing Instructions

After merge, verify all menu options work correctly:

**Interactive menu mode:**
```bash
klaus
# Select each option:
# 0) CONFIG — Shows installation details ✅
# 1) SCAN — Runs scanner (now uses python3) ✅
# 2) AUDIT — Audits payloads (now uses python3) ✅
# 3) FIX — Diagnoses issues (now uses python3) ✅
# 4) HELP — Shows help ✅
# 5) EXIT — Exits cleanly ✅
```

**Direct CLI mode:**
```bash
klaus scan . --min-confidence HIGH
klaus audit-payloads --detailed
klaus fix-pseudonymization --show-payloads
```

### Impact

- **Scope:** Minor — Platform compatibility fix for macOS
- **Breaking Changes:** None
- **Dependencies:** None (Python 3 is already required)
- **Backwards Compatibility:** Fully compatible

### Related

- Fixes Klaus interactive menu failing on macOS when selecting AUDIT/SCAN/FIX options
- Completes Python 3 migration started in previous commit

---

## How to Create This PR

Since automated creation encountered authentication issues, you can create this PR manually:

### Option 1: Using GitHub Web UI (Easiest)

1. Go to: https://github.com/Ka0s-Klaus/klaus-proxy-local/pulls
2. Click **"New pull request"** (green button)
3. Set:
   - Base branch: `main`
   - Compare branch: `main` (current branch already has the commit)
4. Copy-paste the title and description above
5. Add label: `bug` and `platform-compatibility`
6. Click **"Create pull request"**

### Option 2: Using GitHub CLI (After Re-authentication)

```bash
# Re-authenticate with GitHub
gh auth login -h github.com

# Then create the PR
gh pr create --title "fix: replace all python with python3 in klaus menu functions" \
  --body "$(cat PR_TEMPLATE.md)" \
  --label "bug,platform-compatibility"
```

### Option 3: Using git + GitHub Web

```bash
# Verify the commit is ready
git log --oneline -1
# Output should be: d9c9839 fix: replace all python with python3 in klaus menu functions

# Push the branch (if not already pushed)
git push origin main

# Then manually create PR on GitHub web UI
```

---

## Commit Details

```
Author: Claude Haiku 4.5 <noreply@anthropic.com>
Date:   2026-09-19

Commit: d9c9839
Message: fix: replace all python with python3 in klaus menu functions

Changes:
  - cmd_scan() function: python -m → python3 -m (line 183)
  - cmd_audit() function: python -m → python3 -m (line 224)
  - cmd_fix() function: python -m → python3 -m (line 265)

Status: ✅ Ready for PR
```

---

**Note:** If you encounter authentication issues, the simplest approach is to use the GitHub Web UI at https://github.com/Ka0s-Klaus/klaus-proxy-local/pulls
