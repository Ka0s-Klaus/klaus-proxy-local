#!/usr/bin/env python3
"""CLI entry point for Klaus Sensitive Data Scanner.

Usage:
    klaus-scan /path/to/project
    klaus-scan /path/to/project --min-confidence HIGH
    klaus-scan /path/to/project --approve-all
"""
from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import NoReturn

from Klaus_proxy_local.sensitive_data_scanner import (
    Confidence,
    SensitiveDataScanner,
)


def parse_args(argv: list[str] | None = None) -> dict:
    """Parse command-line arguments."""
    parser = ArgumentParser(
        prog="klaus-scan",
        description="Klaus Sensitive Data Scanner — detect secrets in your project",
    )

    parser.add_argument(
        "path",
        type=str,
        help="Path to project directory to scan",
    )

    parser.add_argument(
        "--min-confidence",
        type=str,
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default="CRITICAL",
        help="Minimum confidence level to report (default: CRITICAL)",
    )

    parser.add_argument(
        "--approve-all",
        action="store_true",
        help="Automatically approve all CRITICAL findings (skip review)",
    )

    parser.add_argument(
        "--enable-contextual",
        action="store_true",
        help="Enable contextual detection (variable names, file types)",
    )

    parser.add_argument(
        "--enable-heuristic",
        action="store_true",
        help="Enable heuristic detection (entropy analysis)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    return vars(parser.parse_args(argv))


def confidence_from_string(s: str) -> Confidence:
    """Convert string to Confidence enum."""
    mapping = {
        "CRITICAL": Confidence.CRITICAL,
        "HIGH": Confidence.HIGH,
        "MEDIUM": Confidence.MEDIUM,
        "LOW": Confidence.LOW,
    }
    return mapping[s]


def print_header() -> None:
    """Print scanner header."""
    print("\n" + "─" * 60)
    print("🔍 Klaus Sensitive Data Scanner v0.2.0")
    print("─" * 60 + "\n")


def print_summary(result, min_confidence: Confidence) -> None:
    """Print scan summary."""
    print("\n" + "─" * 60)
    print("✅ Scan Complete")
    print("─" * 60)

    summary = result.summary()
    print(summary)

    print(f"\nMinimum confidence threshold: {min_confidence.name}")

    # Count findings above threshold
    above_threshold = [
        f for f in result.findings if f.confidence <= min_confidence
    ]
    print(f"Findings above threshold: {len(above_threshold)}/{len(result.findings)}")


def print_findings(result, min_confidence: Confidence) -> None:
    """Print findings for review."""
    above_threshold = [
        f for f in result.findings if f.confidence <= min_confidence
    ]

    if not above_threshold:
        print("\n✨ No findings above threshold")
        return

    print(f"\n\n📋 {len(above_threshold)} Findings to Review")
    print("─" * 60)

    for idx, finding in enumerate(above_threshold, 1):
        # Confidence indicator
        conf_icon = {
            Confidence.CRITICAL: "🔴",
            Confidence.HIGH: "🟠",
            Confidence.MEDIUM: "🟡",
            Confidence.LOW: "🔵",
        }[finding.confidence]

        print(f"\n[{idx}/{len(above_threshold)}] {conf_icon} {finding.confidence.name}")
        print(f"  File: {finding.file_path}:{finding.line_number}")
        print(f"  Type: {finding.category}")
        print(f"  Method: {finding.detection_method}")
        print(f"\n  Context:")

        # Show context (limit length)
        context = finding.context[:80]
        if len(finding.context) > 80:
            context += "..."
        print(f"    {context}")

        print(f"\n  Reason: {finding.reason}")


def interactive_review(result, min_confidence: Confidence, vault_integration=None) -> int:
    """Interactive review of findings above threshold.

    Returns: count of findings approved for vault
    """
    above_threshold = [
        f for f in result.findings if f.confidence <= min_confidence
    ]

    if not above_threshold:
        return 0

    approved_count = 0

    for idx, finding in enumerate(above_threshold, 1):
        # Confidence indicator
        conf_icon = {
            Confidence.CRITICAL: "🔴",
            Confidence.HIGH: "🟠",
            Confidence.MEDIUM: "🟡",
            Confidence.LOW: "🔵",
        }[finding.confidence]

        print(f"\n[{idx}/{len(above_threshold)}] {conf_icon} {finding.confidence.name}")
        print(f"  File: {finding.file_path}:{finding.line_number}")
        print(f"  Type: {finding.category}")
        print(f"  Method: {finding.detection_method}")
        print(f"  Reason: {finding.reason}")
        print(f"\n  Context: {finding.context[:120]}")

        # Check if already in vault
        if vault_integration:
            existing = vault_integration.check_already_in_vault(finding.value)
            if existing:
                print(f"  ⓘ Already in vault: {existing}")
                continue

        # Get user input
        while True:
            response = (
                input(
                    "\n  Action: [A]pprove / [S]kip / [C]opy value / [Q]uit? >> "
                ).strip().upper()
            )
            if response in ("A", "S", "C", "Q"):
                break
            print("  Invalid choice. Use A, S, C, or Q")

        if response == "A":
            finding.user_approved = True
            approved_count += 1

            # Add to vault if integration available
            if vault_integration:
                try:
                    prefix = _get_prefix_for_category(finding.category)
                    pseudo = vault_integration.add_finding_to_vault(finding, prefix)
                    print(f"  ✓ Approved and added to vault")
                    print(f"     Pseudonym: {pseudo}")
                except Exception as e:
                    print(f"  ⚠️  Approved but vault error: {e}")
            else:
                print(f"  ✓ Approved")

        elif response == "S":
            print(f"  ⊘ Skipped")
        elif response == "C":
            # Copy to clipboard (if available)
            try:
                import subprocess

                subprocess.run(
                    ["pbcopy"], input=finding.value.encode(), check=True
                )
                print(f"  📋 Copied to clipboard")
            except Exception:
                print(f"  ⓘ Value: {finding.value}")
        elif response == "Q":
            print("\n⊘ Review cancelled")
            return approved_count

    return approved_count


def _get_prefix_for_category(category: str) -> str:
    """Determine vault prefix based on finding category."""
    if "api-key" in category or "token" in category:
        return "api-key"
    elif "password" in category or "secret" in category:
        return "secret"
    elif "connection" in category or "db" in category:
        return "db-connection"
    elif "key" in category:
        return "key"
    elif "host" in category or "ip" in category:
        return "infra"
    else:
        return "data"


def main(argv: list[str] | None = None) -> NoReturn:
    """Main entry point."""
    args = parse_args(argv)

    print_header()

    # Validate path
    path = Path(args["path"]).resolve()
    if not path.exists():
        print(f"❌ Error: Path not found: {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"❌ Error: Path is not a directory: {path}")
        sys.exit(1)

    print(f"Scanning: {path}")

    # Create scanner
    scanner = SensitiveDataScanner(
        enable_contextual=args["enable_contextual"],
        enable_heuristic=args["enable_heuristic"],
    )

    # Run scan
    def progress_callback(current: int, total: int) -> None:
        if total > 0:
            pct = (current * 100) // total
            bar_len = 40
            filled = (current * bar_len) // total
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r[{bar}] {pct}% ({current}/{total} files)", end="", flush=True)

    result = scanner.scan_directory(path, progress_callback)
    print()  # New line after progress bar

    # Parse min confidence
    min_confidence = confidence_from_string(args["min_confidence"])

    # Print summary
    print_summary(result, min_confidence)

    # Print findings
    print_findings(result, min_confidence)

    # JSON output
    if args["json"]:
        import json

        above_threshold = [
            f for f in result.findings if f.confidence <= min_confidence
        ]
        output = {
            "total_files_scanned": result.total_files_scanned,
            "findings_count": len(above_threshold),
            "findings": [f.to_dict() for f in above_threshold],
            "scan_duration_seconds": result.scan_duration_seconds,
        }
        print("\n" + json.dumps(output, indent=2))
        sys.exit(0)

    # Initialize vault integration
    vault_integration = None
    try:
        from Klaus_proxy_local.sensitive_data_scanner import VaultIntegration

        vault_integration = VaultIntegration()
    except Exception as e:
        print(f"⚠️  Vault integration unavailable: {e}")

    # Interactive review (unless --approve-all)
    if args["approve_all"]:
        above_threshold = [
            f for f in result.findings if f.confidence <= min_confidence
        ]
        approved_count = 0
        for finding in above_threshold:
            finding.user_approved = True
            approved_count += 1
            if vault_integration:
                try:
                    prefix = _get_prefix_for_category(finding.category)
                    vault_integration.add_finding_to_vault(finding, prefix)
                except Exception:
                    pass
        print(f"\n✓ Auto-approved {approved_count} findings (added to vault)")
    else:
        # Ask user to review
        above_threshold = [
            f for f in result.findings if f.confidence <= min_confidence
        ]
        if above_threshold:
            review = input(
                f"\n\nReview {len(above_threshold)} finding(s)? [Y/N]: "
            ).strip().upper()
            if review == "Y":
                approved_count = interactive_review(result, min_confidence, vault_integration)
            else:
                approved_count = 0
        else:
            approved_count = 0

    print(f"\n\n✨ Scan complete")
    print(f"  Files scanned: {result.total_files_scanned}")
    print(f"  Findings: {len(result.findings)}")
    print(f"  Approved for vault: {approved_count}")

    sys.exit(0)


if __name__ == "__main__":
    main()
