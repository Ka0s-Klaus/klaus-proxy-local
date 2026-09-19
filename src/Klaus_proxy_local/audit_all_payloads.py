#!/usr/bin/env python3
"""Automatic audit of all captured payloads (original vs sent).

Comprehensive analysis with summary:
  - Count original vs sent payloads
  - Compare pseudonymization effectiveness
  - Detect secrets redaction
  - Generate executive summary
  - Create detailed audit report

Usage:
  python audit_all_payloads.py                # Summary only
  python audit_all_payloads.py --detailed     # Detailed analysis
  python audit_all_payloads.py --export=csv   # Export to CSV
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional


class PayloadAuditor:
    """Audit all captured payloads for security and pseudonymization."""

    def __init__(self, captures_dir: Optional[Path] = None):
        """Initialize auditor.

        Args:
            captures_dir: Path to captures directory. Defaults to ~/.klaus-proxy/captures/
        """
        if captures_dir is None:
            captures_dir = Path.home() / ".klaus-proxy" / "captures"

        self.captures_dir = captures_dir
        self.original_dir = captures_dir / "original"
        self.sent_dir = captures_dir / "sent"

        self.original_payloads = []
        self.sent_payloads = []
        self.errors = []

    def load_payloads(self) -> Tuple[int, int]:
        """Load all payloads from captures directories.

        Returns:
            Tuple of (original_count, sent_count)
        """
        # Load original payloads
        if self.original_dir.exists():
            for file_path in sorted(self.original_dir.glob("*.json")):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        self.original_payloads.append(
                            {"file": file_path.name, "data": data}
                        )
                except (json.JSONDecodeError, IOError) as e:
                    self.errors.append(f"Error reading {file_path.name}: {e}")

        # Load sent payloads
        if self.sent_dir.exists():
            for file_path in sorted(self.sent_dir.glob("*.json")):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        self.sent_payloads.append(
                            {"file": file_path.name, "data": data}
                        )
                except (json.JSONDecodeError, IOError) as e:
                    self.errors.append(f"Error reading {file_path.name}: {e}")

        return len(self.original_payloads), len(self.sent_payloads)

    def analyze_pseudonymization(self) -> Dict:
        """Analyze pseudonymization across all payloads.

        Returns:
            Dictionary with pseudonymization statistics
        """
        pseudonymized_count = 0
        secrets_redacted_count = 0
        blocked_count = 0
        methods = Counter()
        hosts = Counter()
        status_codes = Counter()

        for payload in self.sent_payloads:
            data = payload["data"]
            if data.get("pseudonymized"):
                pseudonymized_count += 1
            if data.get("secrets_redacted"):
                secrets_redacted_count += 1
            if data.get("blocked"):
                blocked_count += 1

            methods[data.get("method", "UNKNOWN")] += 1
            hosts[data.get("host", "UNKNOWN")] += 1
            status_codes[data.get("status_code", "UNKNOWN")] += 1

        return {
            "total_sent": len(self.sent_payloads),
            "pseudonymized": pseudonymized_count,
            "secrets_redacted": secrets_redacted_count,
            "blocked": blocked_count,
            "methods": dict(methods),
            "hosts": dict(hosts),
            "status_codes": dict(status_codes),
        }

    def get_time_range(self) -> Tuple[str, str]:
        """Get earliest and latest capture times.

        Returns:
            Tuple of (earliest_time, latest_time)
        """
        times = []
        for payload in self.original_payloads + self.sent_payloads:
            captured_at = payload["data"].get("captured_at")
            if captured_at:
                times.append(captured_at)

        if not times:
            return "N/A", "N/A"

        times.sort()
        return times[0], times[-1]

    def generate_summary(self) -> str:
        """Generate executive summary of audit.

        Returns:
            Formatted summary string
        """
        orig_count, sent_count = len(self.original_payloads), len(self.sent_payloads)
        analysis = self.analyze_pseudonymization()
        earliest, latest = self.get_time_range()

        # Calculate match rate
        match_rate = (orig_count / sent_count * 100) if sent_count > 0 else 0

        summary = f"""
╔════════════════════════════════════════════════════════════════╗
║                    PAYLOAD AUDIT SUMMARY                       ║
╚════════════════════════════════════════════════════════════════╝

📊 CAPTURE OVERVIEW
{'─' * 60}
  Total Original Payloads:     {orig_count}
  Total Sent Payloads:         {sent_count}
  Match Rate:                  {match_rate:.1f}%
  Time Range:                  {earliest} → {latest}

🔐 PSEUDONYMIZATION STATUS
{'─' * 60}
  Pseudonymized:               {analysis['pseudonymized']}/{sent_count} ({analysis['pseudonymized']/sent_count*100:.1f}%)
  Secrets Redacted:            {analysis['secrets_redacted']}/{sent_count} ({analysis['secrets_redacted']/sent_count*100:.1f}%)
  Blocked Requests:            {analysis['blocked']}

📋 REQUEST BREAKDOWN
{'─' * 60}
  Methods:
"""
        for method, count in sorted(
            analysis["methods"].items(), key=lambda x: x[1], reverse=True
        ):
            summary += f"    • {method}: {count}\n"

        summary += f"\n  Hosts:\n"
        for host, count in sorted(
            analysis["hosts"].items(), key=lambda x: x[1], reverse=True
        ):
            summary += f"    • {host}: {count}\n"

        summary += f"\n  Status Codes:\n"
        for code, count in sorted(
            analysis["status_codes"].items(), key=lambda x: x[1], reverse=True
        ):
            summary += f"    • {code}: {count}\n"

        # Security assessment
        summary += f"\n🛡️  SECURITY ASSESSMENT\n{'─' * 60}\n"
        if analysis["pseudonymized"] == sent_count and analysis["secrets_redacted"] == sent_count:
            summary += "  ✅ All payloads pseudonymized and secrets redacted\n"
            summary += "  ✅ Data protection: EXCELLENT\n"
        elif analysis["pseudonymized"] == sent_count:
            summary += "  ⚠️  All pseudonymized but some secrets not redacted\n"
            summary += "  ⚠️  Data protection: GOOD (review secrets)\n"
        else:
            summary += f"  ❌ {sent_count - analysis['pseudonymized']} payloads NOT pseudonymized\n"
            summary += "  ❌ Data protection: NEEDS REVIEW\n"

        if self.errors:
            summary += f"\n⚠️  ERRORS\n{'─' * 60}\n"
            for error in self.errors[:5]:
                summary += f"  • {error}\n"
            if len(self.errors) > 5:
                summary += f"  ... and {len(self.errors) - 5} more errors\n"

        summary += f"\n{'═' * 60}\n"
        summary += f"Generated: {datetime.now().isoformat()}\n"
        summary += f"Captures directory: {self.captures_dir}\n"

        return summary

    def generate_detailed_report(self) -> str:
        """Generate detailed report with per-payload analysis.

        Returns:
            Formatted detailed report string
        """
        report = self.generate_summary()

        report += f"\n\n📋 DETAILED PAYLOAD ANALYSIS\n{'═' * 60}\n\n"

        # Sent payloads detail
        report += f"SENT PAYLOADS ({len(self.sent_payloads)})\n{'─' * 60}\n"
        for idx, payload in enumerate(self.sent_payloads, 1):
            data = payload["data"]
            status = "✅" if data.get("pseudonymized") else "❌"
            report += f"\n  {idx}. {payload['file']} {status}\n"
            report += f"     Method: {data.get('method')} {data.get('status_code')}\n"
            report += f"     URL: {data.get('url')}\n"
            report += f"     Pseudonymized: {data.get('pseudonymized')}\n"
            report += f"     Secrets Redacted: {data.get('secrets_redacted')}\n"
            report += f"     Blocked: {data.get('blocked')}\n"
            report += f"     Timestamp: {data.get('captured_at')}\n"

        return report

    def export_csv(self, output_file: Optional[Path] = None) -> Path:
        """Export audit results to CSV.

        Args:
            output_file: Path to CSV file. Defaults to captures_dir/audit_report.csv

        Returns:
            Path to exported CSV file
        """
        if output_file is None:
            output_file = self.captures_dir / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        import csv

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "file",
                    "variant",
                    "timestamp",
                    "method",
                    "host",
                    "path",
                    "status_code",
                    "pseudonymized",
                    "secrets_redacted",
                    "blocked",
                ],
            )
            writer.writeheader()

            for payload in self.sent_payloads:
                data = payload["data"]
                writer.writerow(
                    {
                        "file": payload["file"],
                        "variant": "sent",
                        "timestamp": data.get("captured_at"),
                        "method": data.get("method"),
                        "host": data.get("host"),
                        "path": data.get("path"),
                        "status_code": data.get("status_code"),
                        "pseudonymized": data.get("pseudonymized"),
                        "secrets_redacted": data.get("secrets_redacted"),
                        "blocked": data.get("blocked"),
                    }
                )

        return output_file


def main():
    """Entry point for audit script."""
    parser = argparse.ArgumentParser(
        prog="audit-all-payloads",
        description="Automatic audit of all captured payloads",
        epilog="Examples:\n"
               "  audit_all_payloads.py                # Summary\n"
               "  audit_all_payloads.py --detailed     # Detailed report\n"
               "  audit_all_payloads.py --export=csv   # Export to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Generate detailed report (per-payload analysis)",
    )

    parser.add_argument(
        "--export",
        choices=["csv"],
        help="Export results to specified format",
    )

    parser.add_argument(
        "--captures-dir",
        type=Path,
        help="Path to captures directory (default: ~/.klaus-proxy/captures)",
    )

    args = parser.parse_args()

    try:
        auditor = PayloadAuditor(captures_dir=args.captures_dir)

        # Load payloads
        orig_count, sent_count = auditor.load_payloads()

        if sent_count == 0:
            print("❌ No payloads found in captures directory")
            print(f"   Expected: {auditor.captures_dir}/sent/")
            sys.exit(1)

        # Generate and display report
        if args.detailed:
            report = auditor.generate_detailed_report()
        else:
            report = auditor.generate_summary()

        print(report)

        # Export if requested
        if args.export == "csv":
            csv_file = auditor.export_csv()
            print(f"\n✅ Report exported to: {csv_file}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
