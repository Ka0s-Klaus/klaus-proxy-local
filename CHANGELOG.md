# Changelog

All notable changes to Klaus Proxy Local are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.3] — 2026-09-20

### Fixed
- **Progress feedback for large directory scans** — Added "Indexing files..." visual feedback during file traversal to prevent appearing frozen when scanning large directories like `/Users/usuario`
- **Documentation version consistency** — Synchronized version references across all modules (README, docstrings, install commands)
- **Test version assertions** — Updated tests to assert correct version (0.3.3)
- **Invalid ruff version constraint** — Changed from non-existent 0.16.5 to valid 0.8.0+
- **Broken shell scripts** — Removed references to non-existent `dashboard_server` module from start.sh and run_all.sh
- **Vault filename documentation** — Corrected vault file name from `.vault.json` to `.pseudonym_vault.json`
- **Outdated docstrings** — Updated module docstrings with current version and removed non-existent CLI flags

### Deprecated
- **Klaus Monitor (claude-proxy-monitor)** — Removed in v0.3.3; use `klaus-audit-payloads` for auditing instead

---

## [0.3.2] — 2026-09-19

### Added
- Klaus Menu v0.3.2 enhancements
- Python3 compatibility improvements
- Improved CLI feedback and user experience

### Fixed
- Python command path issues in Klaus Menu
- Shell expansion handling with `set -u`

---

## [0.3.1] — 2026-09-15

### Added
- `klaus-audit-payloads` CLI for comprehensive payload auditing
- `klaus-fix-pseudonymization` CLI for diagnosing and fixing pseudonymization issues
- Multi-mode audit system (summary, detailed, CSV export)
- SSL/TLS truststore auto-generation (GIT_SSL_CAINFO, CURL_CA_BUNDLE)

### Fixed
- Truststore handshake errors
- Pseudonymization consistency issues

---

## [0.3.0] — 2026-09-04

### Added
- **Three-tier sensitive data detection** (v0.2.0+):
  - Tier 1: Pattern-based detection (20+ regex patterns for common secrets)
  - Tier 2: Contextual detection (variable names, JSON keys, file types)
  - Tier 3: Heuristic detection (entropy analysis, character diversity)
- **Custom pattern support** — Users can add their own detection patterns
- **Vault integration** — Persistent pseudonym mapping with bidirectional reversal
- **Comprehensive testing** — 465 unit and integration tests covering all detection tiers
- **Klaus Menu** — Interactive bash menu for scan, audit, and fix operations
- **Production-ready deployment** — CI/CD validation, security scanning, code quality checks

### Fixed
- SALT generation hardening
- File permission security (vault: 0o600, parent: 0o700)
- Unreversible pseudonym detection
- Zero-configuration setup (certs, config, shell hooks auto-generated)

---

## [0.2.0] — 2026-08-15

### Added
- Multi-tier sensitive data scanner architecture
- Pattern-based secret detection
- Contextual analysis layer
- Heuristic entropy-based detection
- Project-wide secret scanning (`klaus-scan` CLI)

### Fixed
- Detection accuracy across multiple secret types
- False positive reduction through multi-tier validation

---

## [0.1.0] — 2026-07-30

### Added
- Initial release: Klaus Proxy Local
- mitmproxy-based HTTPS interception
- Basic payload capture and pseudonymization
- Zero-config setup (automatic cert and config generation)
- Fail-closed guarantee (proxy must run for requests to leave machine)
- Wrapper scripts for multiple shells (bash, zsh, fish, PowerShell)
- Core addons:
  - `anthropic_payload_capture.py` — Capture original/sent pairs
  - `anthropic_payload_pseudonymize.py` — Rewrite/restore payloads
  - `anthropic_capture_verify.py` — Verify captured data integrity
  - `anthropic_pair_verify.py` — Pair-level diff verification
  - `anthropic_artifacts_cleanup.py` — Clean Claude Code disk artifacts
- Installation helpers for Python, wrapper scripts, and shell integration
- Production-ready launcher with mitmproxy orchestration

---

## Links to Detailed Release Notes

- [v0.3.3 Release Notes](./docs/RELEASE_v0.3.3_NOTES.md) (if available)
- [v0.3.2 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md)
- [v0.3.1 Release Notes](./docs/RELEASE_v0.3.1_NOTES.md)
- [v0.3.0 Release Notes](./docs/RELEASE_v0.3.0_NOTES.md)
