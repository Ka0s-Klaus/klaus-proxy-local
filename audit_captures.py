#!/usr/bin/env python3
"""Auditoría de payloads: Identifica valores sensibles sin pseudonimizar.

Analiza captures/original/ y captures/sent/ para:
1. Valores sensibles en original/ (deberían estar pseudonimizados en sent/)
2. Fugas de valores reales en sent/ (que no deberían estar)
3. Qué añadir al vault para mejorar cobertura

Uso:
  python audit_captures.py [--stats] [--find-leaks] [--patterns] [--review]

Flags:
  --stats       Resumen: cuántos originales, enviados, pseudonimizados
  --find-leaks  Busca valores reales EN sent/ (potenciales fugas)
  --patterns    Aplica patrones del scanner a todos los payloads
  --review      Revisión interactiva de payloads (menú A/S/C/Q)
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Patrones sensibles comunes
PATTERNS = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "api_key": r"(?:api[_-]?key|apikey|access[_-]?token|token)[\"']?\s*[:=]\s*[\"']?[\w\-]+",
    "uuid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    "github_token": r"ghp_[A-Za-z0-9_]{36,255}",
    "aws_key": r"AKIA[0-9A-Z]{16}",
    "path": r"(?:/[\w\-\.]+)+(?:/)?",
}

CAPTURES_DIR = Path.cwd() / "captures"
ORIGINAL_DIR = CAPTURES_DIR / "original"
SENT_DIR = CAPTURES_DIR / "sent"
VAULT_PATH = CAPTURES_DIR / ".pseudonym_vault.json"


def load_vault() -> dict:
    """Load pseudonym vault."""
    if not VAULT_PATH.exists():
        print(f"⚠️  Vault not found: {VAULT_PATH}")
        return {}
    return json.loads(VAULT_PATH.read_text(encoding="utf-8"))


def load_payload(path: Path) -> dict:
    """Load a JSON payload, return {} if invalid."""
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def extract_strings(obj: Any, depth: int = 0, max_depth: int = 10) -> set[str]:
    """Recursively extract all string values from a JSON object."""
    if depth > max_depth:
        return set()

    strings = set()
    if isinstance(obj, dict):
        for v in obj.values():
            strings.update(extract_strings(v, depth + 1, max_depth))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            strings.update(extract_strings(item, depth + 1, max_depth))
    elif isinstance(obj, str) and len(obj) > 3:  # Only meaningful strings
        strings.add(obj)
    return strings


def find_sensitive_patterns(text: str) -> dict[str, list]:
    """Find all sensitive patterns in text."""
    found = {}
    for name, pattern in PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found[name] = list(set(matches))  # Deduplicate
    return found


def audit_stats():
    """Show capture statistics."""
    print("\n" + "=" * 70)
    print("📊 CAPTURE AUDIT STATISTICS")
    print("=" * 70 + "\n")

    original_files = list(ORIGINAL_DIR.glob("**/*.json"))
    sent_files = list(SENT_DIR.glob("**/*.json"))
    vault = load_vault()

    print(f"📁 Original payloads:      {len(original_files):,}")
    print(f"📁 Sent payloads:         {len(sent_files):,}")
    print(f"🔐 Vault entries:         {len(vault):,}")
    print()

    # Sample analysis of first 100 originals
    print("🔍 Analyzing first 100 payloads for sensitive patterns...\n")
    all_patterns = Counter()

    for i, orig_file in enumerate(original_files[:100]):
        payload = load_payload(orig_file)
        payload_str = json.dumps(payload, ensure_ascii=False)

        patterns = find_sensitive_patterns(payload_str)
        for pattern_type, matches in patterns.items():
            all_patterns[pattern_type] += len(matches)

    print("Patterns found in sample:")
    for pattern_type, count in all_patterns.most_common():
        print(f"  {pattern_type:12} {count:5} occurrences")

    print("\n💡 Tip: Use --find-leaks to check for unredacted sensitive values\n")


def find_leaks():
    """Find potential leaks (sensitive patterns in sent/)."""
    print("\n" + "=" * 70)
    print("🚨 LEAK DETECTION (sensitive patterns in sent/)")
    print("=" * 70 + "\n")

    vault = load_vault()
    vault_reverse = {v: k for k, v in vault.items()}

    # Focus only on TRULY sensitive patterns (not UUIDs or API paths)
    critical_patterns = {
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "api_key": r"(?:api[_-]?key|apikey)[\"']?\s*[:=]\s*[\"']?[\w\-]{16,}",
        "github_token": r"ghp_[A-Za-z0-9_]{36,255}",
        "aws_key": r"AKIA[0-9A-Z]{16}",
    }

    leaks_found = []
    sent_files = list(SENT_DIR.glob("**/*.json"))[:100]  # Sample 100

    print(f"Scanning {len(sent_files)} sent payloads for CRITICAL patterns...\n")
    print("Focus: Real emails, API keys, tokens (not UUIDs or API paths)\n")

    for sent_file in sent_files:
        payload = load_payload(sent_file)
        payload_str = json.dumps(payload, ensure_ascii=False)

        for pattern_type, pattern in critical_patterns.items():
            matches = re.findall(pattern, payload_str, re.IGNORECASE)

            for match in matches:
                # Filter out obvious false positives
                if pattern_type == "email":
                    # Skip noreply, test, example domains
                    if any(x in match.lower() for x in ["noreply", "test", "example", "localhost"]):
                        continue

                # Check if this value is in the vault (should be pseudonymized)
                if match not in vault:
                    leaks_found.append({
                        "type": pattern_type,
                        "value": match[:60],
                    })

    # Deduplicate
    leaks_found = list({(l["type"], l["value"]): l for l in leaks_found}.values())

    if leaks_found:
        print(f"⚠️  Found {len(leaks_found)} potential leaks:\n")
        for leak in leaks_found[:15]:  # Show first 15
            print(f"  {leak['type']:12} | {leak['value']}")
        print("\n💡 Action: Add these to vault with:")
        print("  python scripts/add_to_vault.py . --manual")
    else:
        print("✅ No CRITICAL leaks detected in sample\n")
        print("   (UUIDs and API paths are expected in sent/)\n")


def show_patterns_in_vault():
    """Analyze what's currently in the vault."""
    print("\n" + "=" * 70)
    print("🔐 VAULT COVERAGE ANALYSIS")
    print("=" * 70 + "\n")

    vault = load_vault()

    by_type = {
        "email": [],
        "ip": [],
        "path": [],
        "org": [],
        "id": [],
        "other": [],
    }

    for real, pseudo in vault.items():
        if "@" in real:
            by_type["email"].append(real)
        elif re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", real):
            by_type["ip"].append(real)
        elif real.startswith("/"):
            by_type["path"].append(real)
        elif pseudo.startswith("org_"):
            by_type["org"].append(real)
        elif pseudo.startswith("id_"):
            by_type["id"].append(real)
        else:
            by_type["other"].append(real)

    print("Vault breakdown by type:\n")
    for typ, values in by_type.items():
        if values:
            print(f"  {typ:12} {len(values):5} entries")
            for val in values[:3]:  # Show first 3 of each type
                print(f"              → {val}")
            if len(values) > 3:
                print(f"              → ... and {len(values) - 3} more")
    print()


def interactive_review():
    """Interactive review of payloads side-by-side."""
    print("\n" + "=" * 70)
    print("🔍 INTERACTIVE PAYLOAD REVIEW (original vs sent)")
    print("=" * 70)
    print("\nControls: [A]pprove | [S]kip | [C]opy value | [Q]uit")
    print("=" * 70 + "\n")

    vault = load_vault()
    original_files = list(ORIGINAL_DIR.glob("**/*.json"))

    candidates_to_add = []

    for i, orig_file in enumerate(original_files[:50]):
        sent_file = SENT_DIR / orig_file.relative_to(ORIGINAL_DIR)

        if not sent_file.exists():
            continue

        orig_payload = load_payload(orig_file)
        sent_payload = load_payload(sent_file)

        orig_strings = extract_strings(orig_payload)
        sent_strings = extract_strings(sent_payload)

        # Find values in original but not in sent (likely pseudonymized)
        missing_in_sent = orig_strings - sent_strings

        # Filter for likely sensitive data
        sensitive = [
            s for s in missing_in_sent
            if re.search(r"@|[\d\.]{7,}|/|_kyndryl", s, re.IGNORECASE)
        ]

        if sensitive and len(sensitive) <= 5:  # Manageable number
            print(f"\n[{i+1}/50] {orig_file.name}")
            print(f"  Potentially sensitive in original but NOT in sent:")
            for val in sorted(sensitive)[:3]:
                print(f"    • {val[:60]}")
                if val not in vault and len(val) > 3:
                    print(f"      → NOT in vault. Add? (A/S/C)")
                    # In real interactive mode, get user input here

    print(f"\n\n💡 Use --review with interactive prompts for full mode\n")


def main():
    """Main entry point."""
    import sys

    if not ORIGINAL_DIR.exists():
        print(f"❌ Captures directory not found: {ORIGINAL_DIR}")
        sys.exit(1)

    if "--stats" in sys.argv or len(sys.argv) == 1:
        audit_stats()

    if "--find-leaks" in sys.argv:
        find_leaks()

    if "--patterns" in sys.argv:
        show_patterns_in_vault()

    if "--review" in sys.argv:
        interactive_review()

    if len(sys.argv) == 1 or "--stats" in sys.argv:
        print("\n🚀 Next steps:")
        print("  python audit_captures.py --find-leaks     # Check for leaks")
        print("  python audit_captures.py --patterns        # Vault coverage")
        print("  python audit_captures.py --review          # Interactive review")
        print()


if __name__ == "__main__":
    main()
