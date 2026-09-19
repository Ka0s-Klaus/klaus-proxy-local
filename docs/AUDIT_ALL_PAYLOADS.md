# 🔍 Complete Payload Audit Guide

Automatic audit of all captured payloads (original vs sent) with comprehensive analysis and reporting.

## Overview

Klaus Proxy captures every request and response. The **Audit All Payloads** tool analyzes:

- ✅ Pseudonymization effectiveness
- ✅ Secret redaction verification
- ✅ Request/response breakdown by method, host, status code
- ✅ Security assessment (data protection level)
- ✅ Detailed per-payload analysis
- ✅ CSV export for further analysis

## Quick Start

### 1. Summary Only (Recommended for most users)

```bash
klaus-audit-payloads
```

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║                    PAYLOAD AUDIT SUMMARY                       ║
╚════════════════════════════════════════════════════════════════╝

📊 CAPTURE OVERVIEW
────────────────────────────────────────────────────────────
  Total Original Payloads:     0
  Total Sent Payloads:         4
  Match Rate:                  0.0%
  Time Range:                  2026-09-17T18:14:27.274477 → 2026-09-17T18:14:34.274490

🔐 PSEUDONYMIZATION STATUS
────────────────────────────────────────────────────────────
  Pseudonymized:               2/4 (50.0%)
  Secrets Redacted:            4/4 (100.0%)
  Blocked Requests:            0
  
... (rest of summary)
```

### 2. Detailed Report (Per-payload analysis)

```bash
klaus-audit-payloads --detailed
```

Shows every captured payload with:
- File name
- Pseudonymization status (✅ or ❌)
- HTTP method and status code
- URL
- Secrets redaction
- Timestamp

### 3. Export to CSV (For spreadsheets/further analysis)

```bash
klaus-audit-payloads --export=csv
```

Creates `audit_report_YYYYMMDD_HHMMSS.csv` in `~/.klaus-proxy/captures/`

**CSV Columns:**
- file
- variant
- timestamp
- method
- host
- path
- status_code
- pseudonymized
- secrets_redacted
- blocked

## Understanding the Report

### 📊 Capture Overview

| Field | Meaning |
|-------|---------|
| **Total Original Payloads** | Files in `captures/original/` |
| **Total Sent Payloads** | Files in `captures/sent/` |
| **Match Rate** | `original / sent * 100%` (should be ~100%) |
| **Time Range** | First to last capture timestamp |

### 🔐 Pseudonymization Status

| Field | Meaning |
|-------|---------|
| **Pseudonymized** | Count/% of payloads with PII replaced |
| **Secrets Redacted** | Count/% with secrets removed from headers |
| **Blocked Requests** | Count of requests blocked by proxy rules |

### 📋 Request Breakdown

**Methods:** GET, POST, PUT, DELETE, PATCH, etc.

**Hosts:** Which servers were accessed
- api.anthropic.com
- llm.tools.cloud.customer.es
- http-intake.logs.datadoghq.com
- etc.

**Status Codes:** HTTP response codes
- 200 = OK
- 201 = Created
- 202 = Accepted
- 4xx = Client error
- 5xx = Server error

### 🛡️ Security Assessment

**Assessment Levels:**

| Level | Condition | Meaning |
|-------|-----------|---------|
| ✅ **EXCELLENT** | All pseudonymized + secrets redacted | Highest protection |
| ⚠️ **GOOD** | Pseudonymized but some secrets not redacted | Review needed |
| ❌ **NEEDS REVIEW** | Some payloads not pseudonymized | Investigate asap |

## Command Reference

### Basic Usage

```bash
# Summary report (default)
klaus-audit-payloads

# Detailed report
klaus-audit-payloads --detailed

# Export to CSV
klaus-audit-payloads --export=csv

# Custom captures directory
klaus-audit-payloads --captures-dir=/path/to/captures
```

### Interpretation

**✅ Payload Status: OK**
```
1. new_capture_00_181427.json ✅
   Pseudonymized: True
   Secrets Redacted: True
```

This payload was properly processed:
- Personal identifiable information was replaced with pseudonyms
- API keys and tokens were redacted from headers

**❌ Payload Status: NEEDS ATTENTION**
```
2. new_capture_01_181429.json ❌
   Pseudonymized: False
   Secrets Redacted: True
```

This payload was NOT pseudonymized:
- PII like usernames, file paths, IP addresses may have been sent
- But secrets were still redacted (partial protection)

## Common Scenarios

### Scenario 1: Perfect Audit

```
🛡️ SECURITY ASSESSMENT
────────────────────────────────────
✅ All payloads pseudonymized and secrets redacted
✅ Data protection: EXCELLENT
```

**What to do:** ✅ No action needed. Your data is well protected.

---

### Scenario 2: Good Protection (Some Non-Critical Requests)

```
Pseudonymized: 3/4 (75.0%)
Secrets Redacted: 4/4 (100.0%)

🛡️ SECURITY ASSESSMENT
────────────────────────────────────
⚠️ All pseudonymized but some secrets not redacted
⚠️ Data protection: GOOD (review secrets)
```

**What to do:** 
1. Check which payloads weren't pseudonymized (see detailed report)
2. They might be internal requests or monitoring traffic
3. Verify if any secrets were exposed in those payloads

---

### Scenario 3: Needs Immediate Review

```
Pseudonymized: 1/4 (25.0%)
Secrets Redacted: 3/4 (75.0%)

🛡️ SECURITY ASSESSMENT
────────────────────────────────────
❌ 3 payloads NOT pseudonymized
❌ Data protection: NEEDS REVIEW
```

**What to do:**
1. Run detailed report: `klaus-audit-payloads --detailed`
2. Identify which payloads weren't pseudonymized
3. Check what data was exposed in those requests
4. Consider:
   - Adjusting pseudonymization rules
   - Filtering certain hosts/paths
   - Reviewing proxy configuration

## Troubleshooting

### "No payloads found"

```bash
❌ No payloads found in captures directory
   Expected: /Users/yourname/.klaus-proxy/captures/sent/
```

**Solution:**
1. Start the proxy: `claude-proxy`
2. Make some requests through it: `export HTTPS_PROXY=http://127.0.0.1:8899`
3. Then run audit: `klaus-audit-payloads`

### "Error reading captures"

```
⚠️ ERRORS
────────────────────────────────────
• Error reading new_capture_00.json: [error details]
```

**Solution:**
1. Check file permissions: `ls -la ~/.klaus-proxy/captures/sent/`
2. Check if files are valid JSON: `cat ~/.klaus-proxy/captures/sent/new_capture_00.json | python -m json.tool`
3. If corrupted, delete and re-capture: `rm ~/.klaus-proxy/captures/sent/*.json`

### CSV Export Permission Error

```
❌ Error: [Errno 13] Permission denied: '.../audit_report.csv'
```

**Solution:**
```bash
# Check permissions
ls -la ~/.klaus-proxy/captures/

# Fix permissions if needed
chmod 750 ~/.klaus-proxy/captures/
```

## Advanced Usage

### Parse CSV for Specific Analysis

```bash
# Export CSV
klaus-audit-payloads --export=csv

# Count payloads by host (requires 'csvstat' tool)
csvstat ~/.klaus-proxy/captures/audit_report*.csv

# Filter for non-pseudonymized
grep "False,True" ~/.klaus-proxy/captures/audit_report*.csv
```

### Keep Audit History

```bash
# Date-stamped reports (automatic)
ls ~/.klaus-proxy/captures/audit_report_*.csv

# Archive by date
mkdir -p ~/.klaus-proxy/audit_history
mv ~/.klaus-proxy/captures/audit_report_*.csv ~/.klaus-proxy/audit_history/
```

### Integration with Compliance

```bash
# Automated weekly audit
(crontab -l 2>/dev/null; echo "0 2 * * 0 klaus-audit-payloads >> ~/.klaus-proxy/weekly_audit.log") | crontab -

# Check results
tail -100 ~/.klaus-proxy/weekly_audit.log
```

## FAQ

**Q: Why are some payloads not pseudonymized?**

A: Common reasons:
- Internal or system requests (Datadog logs, monitoring)
- Requests to internal corporate gateways
- Requests that don't match pseudonymization rules
- See detailed report to identify which ones

---

**Q: What if pseudonymization is 0%?**

A: Check:
1. Is `ANTHROPIC_PSEUDO_ENABLE=1` set?
2. Are pseudonymization patterns defined?
3. Run proxy with verbose logging: `ANTHROPIC_DEBUG=1 claude-proxy`

---

**Q: Can I delete captures after auditing?**

A: Yes, they're archived in `~/.klaus-proxy/captures/`:
```bash
# Safe to delete after audit
rm -rf ~/.klaus-proxy/captures/sent/*.json
rm -rf ~/.klaus-proxy/captures/original/*.json

# But keep audit reports if needed for compliance
```

---

**Q: How do I automate audits?**

A: Cron job example:
```bash
# Daily audit at 2 AM
0 2 * * * /usr/local/bin/klaus-audit-payloads --export=csv >> /var/log/klaus-audit.log
```

## See Also

- [QUICK_START.md](./QUICK_START.md) — Getting started
- [AUDIT_CAPTURES_GUIDE.md](./AUDIT_CAPTURES_GUIDE.md) — Detailed capture analysis
- [GENERATE_REPORTS_GUIDE.md](./GENERATE_REPORTS_GUIDE.md) — Report generation
