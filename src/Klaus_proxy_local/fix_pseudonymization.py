#!/usr/bin/env python3
"""Diagnose and fix pseudonymization issues.

When payloads are NOT pseudonymized, this tool helps identify why and fix it.

Usage:
  python fix_pseudonymization.py                # Diagnose issues
  python fix_pseudonymization.py --show-payloads  # Show non-pseudonymized payloads
  python fix_pseudonymization.py --enable     # Force enable pseudonymization
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


class PseudonymizationDiagnostic:
    """Diagnose pseudonymization issues and suggest fixes."""

    def __init__(self, captures_dir: Optional[Path] = None):
        """Initialize diagnostic.

        Args:
            captures_dir: Path to captures directory.
                         Defaults to project root captures/ or ~/.klaus-proxy/captures/
        """
        if captures_dir is None:
            # Try project root first (when running from project directory)
            project_root = Path.cwd() / "captures"
            if project_root.exists():
                captures_dir = project_root
            else:
                # Fallback to user home .klaus-proxy
                captures_dir = Path.home() / ".klaus-proxy" / "captures"

        self.captures_dir = captures_dir
        self.sent_dir = captures_dir / "sent"
        self.config_dir = Path.home() / ".klaus-proxy"
        self.config_file = self.config_dir / "config.json"

        self.non_pseudonymized = []
        self.pseudonymized = []

    def load_payloads(self) -> int:
        """Load sent payloads and categorize by pseudonymization status.

        Returns:
            Total count of payloads
        """
        if not self.sent_dir.exists():
            return 0

        for file_path in sorted(self.sent_dir.glob("*.json")):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    payload = {
                        "file": file_path.name,
                        "data": data,
                        "path": file_path,
                    }

                    if data.get("pseudonymized"):
                        self.pseudonymized.append(payload)
                    else:
                        self.non_pseudonymized.append(payload)
            except (json.JSONDecodeError, IOError):
                pass

        return len(self.non_pseudonymized) + len(self.pseudonymized)

    def analyze_non_pseudonymized(self) -> Dict:
        """Analyze why payloads are NOT pseudonymized.

        Returns:
            Dictionary with analysis by host/path
        """
        by_host = {}
        by_path = {}

        for payload in self.non_pseudonymized:
            data = payload["data"]
            host = data.get("host", "UNKNOWN")
            path = data.get("path", "UNKNOWN")
            method = data.get("method", "UNKNOWN")
            url = data.get("url", "UNKNOWN")

            if host not in by_host:
                by_host[host] = []
            by_host[host].append(
                {"method": method, "path": path, "url": url, "file": payload["file"]}
            )

            if path not in by_path:
                by_path[path] = []
            by_path[path].append({"host": host, "method": method, "file": payload["file"]})

        return {"by_host": by_host, "by_path": by_path}

    def check_config(self) -> Dict:
        """Check pseudonymization configuration.

        Returns:
            Configuration status dictionary
        """
        config = {}

        # Check if config file exists
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                return {"error": f"Cannot read config: {e}"}

        return {
            "config_file": str(self.config_file),
            "exists": self.config_file.exists(),
            "pseudonymization_enabled": config.get("pseudonymization_enabled", True),
            "salt_set": bool(config.get("salt")),
            "patterns_count": len(config.get("patterns", {})),
        }

    def generate_diagnostic_report(self) -> str:
        """Generate comprehensive diagnostic report.

        Returns:
            Formatted diagnostic report
        """
        total = self.load_payloads()
        config = self.check_config()
        analysis = self.analyze_non_pseudonymized()

        report = f"""
╔════════════════════════════════════════════════════════════════╗
║           PSEUDONYMIZATION DIAGNOSTIC REPORT                   ║
╚════════════════════════════════════════════════════════════════╝

📊 PAYLOAD STATUS
{'─' * 60}
  Total Payloads:             {total}
  Pseudonymized:              {len(self.pseudonymized)} ({len(self.pseudonymized)/total*100:.1f}%)
  NOT Pseudonymized:          {len(self.non_pseudonymized)} ({len(self.non_pseudonymized)/total*100:.1f}%)

⚙️  CONFIGURATION
{'─' * 60}
  Config File:                {config.get('config_file')}
  Exists:                     {config.get('exists')}
  Pseudonymization Enabled:   {config.get('pseudonymization_enabled')}
  SALT Set:                   {config.get('salt_set')}
  Patterns Count:             {config.get('patterns_count')}

"""

        if len(self.non_pseudonymized) > 0:
            report += f"🔍 NON-PSEUDONYMIZED BREAKDOWN\n{'─' * 60}\n\n"

            report += "BY HOST:\n"
            for host, payloads in analysis["by_host"].items():
                report += f"  {host} ({len(payloads)} payloads)\n"
                for payload in payloads[:3]:  # Show first 3
                    report += (
                        f"    • {payload['method']} {payload['path']} "
                        f"({payload['file']})\n"
                    )
                if len(payloads) > 3:
                    report += f"    ... and {len(payloads) - 3} more\n"
                report += "\n"

            report += f"\nBY PATH:\n"
            for path, payloads in sorted(
                analysis["by_path"].items(), key=lambda x: len(x[1]), reverse=True
            )[:5]:
                report += f"  {path} ({len(payloads)} payloads)\n"

        report += f"\n💡 RECOMMENDATIONS\n{'─' * 60}\n"
        report += self._get_recommendations(config, analysis, total)

        return report

    def _get_recommendations(self, config: Dict, analysis: Dict, total: int) -> str:
        """Generate recommendations based on diagnostic results.

        Args:
            config: Configuration status
            analysis: Analysis results
            total: Total payload count

        Returns:
            Formatted recommendations string
        """
        recommendations = ""

        # Check if pseudonymization is disabled
        if not config.get("pseudonymization_enabled"):
            recommendations += (
                "❌ Pseudonymization is DISABLED in config\n"
                "   FIX: Enable in ~/.klaus-proxy/config.json\n"
                '   Set: "pseudonymization_enabled": true\n\n'
            )

        # Check SALT
        if not config.get("salt_set"):
            recommendations += (
                "❌ SALT is NOT SET - pseudonymization cannot work\n"
                "   FIX: Run: python -m Klaus_proxy_local.setup\n"
                "   This will generate a random SALT\n\n"
            )

        # Check patterns
        if config.get("patterns_count", 0) == 0:
            recommendations += (
                "⚠️  No pseudonymization patterns configured\n"
                "   FIX: Check ~/.klaus-proxy/config.json\n"
                "   Should have: 'patterns': { 'email': ..., 'username': ... }\n\n"
            )

        # Analyze hosts not being pseudonymized
        by_host = analysis.get("by_host", {})
        non_pseudonymized_hosts = list(by_host.keys())

        if "api.anthropic.com" in non_pseudonymized_hosts or "llm.tools" in non_pseudonymized_hosts[0] if non_pseudonymized_hosts else False:
            recommendations += (
                "⚠️  Internal/Third-party services NOT pseudonymized\n"
                "   These might be intentional (internal logs, monitoring)\n"
                '   HOSTS: ' + ", ".join(non_pseudonymized_hosts[:3]) + "\n"
                "   SOLUTION: Check if these should be pseudonymized\n"
                "   - If YES: Update ANTHROPIC_CAPTURE_HOSTS\n"
                "   - If NO: Safe to ignore\n\n"
            )

        if not recommendations:
            recommendations += (
                "✅ No obvious pseudonymization issues detected\n"
                "   Non-pseudonymized payloads might be:\n"
                "   • Internal/monitoring requests (Datadog, etc.)\n"
                "   • Internal corporate gateways\n"
                "   • System requests not requiring pseudonymization\n"
                "   \n"
                "   TO INVESTIGATE FURTHER:\n"
                "   Run: python fix_pseudonymization.py --show-payloads\n"
                "   Review the detailed payload list\n"
            )

        return recommendations

    def show_non_pseudonymized_payloads(self) -> str:
        """Show detailed view of non-pseudonymized payloads.

        Returns:
            Formatted payload details
        """
        if len(self.non_pseudonymized) == 0:
            return "✅ No non-pseudonymized payloads found!"

        output = f"""
╔════════════════════════════════════════════════════════════════╗
║         NON-PSEUDONYMIZED PAYLOADS ({len(self.non_pseudonymized)})        ║
╚════════════════════════════════════════════════════════════════╝

"""
        for idx, payload in enumerate(self.non_pseudonymized, 1):
            data = payload["data"]
            output += f"\n{idx}. {payload['file']}\n"
            output += f"   Host:        {data.get('host')}\n"
            output += f"   Method:      {data.get('method')}\n"
            output += f"   Path:        {data.get('path')}\n"
            output += f"   URL:         {data.get('url')}\n"
            output += f"   Status:      {data.get('status_code')}\n"
            output += f"   Timestamp:   {data.get('captured_at')}\n"
            output += f"   Blocked:     {data.get('blocked')}\n"

        output += f"\n\n💡 ANALYSIS\n{'─' * 60}\n"
        output += "Common reasons for non-pseudonymization:\n\n"

        # Group by host
        by_host = {}
        for payload in self.non_pseudonymized:
            host = payload["data"].get("host", "UNKNOWN")
            if host not in by_host:
                by_host[host] = 0
            by_host[host] += 1

        for host, count in sorted(by_host.items(), key=lambda x: x[1], reverse=True):
            output += f"  {host}: {count} payloads\n"
            if "datadog" in host.lower() or "logs" in host.lower():
                output += "    └─ Likely: Monitoring/logging service (ok to skip)\n"
            elif "anthropic" in host:
                output += "    └─ ACTION: Should be pseudonymized (check config)\n"
            elif ".es" in host or ".cloud" in host:
                output += "    └─ ACTION: Internal gateway (check if needs pseudonymization)\n"
            else:
                output += "    └─ ACTION: Investigate why not pseudonymized\n"

        return output

    def show_config_file(self) -> str:
        """Show current configuration file.

        Returns:
            Formatted config file content
        """
        if not self.config_file.exists():
            return f"❌ Config file not found: {self.config_file}"

        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)

            output = f"""
╔════════════════════════════════════════════════════════════════╗
║              CONFIGURATION FILE CONTENTS                       ║
╚════════════════════════════════════════════════════════════════╝

File: {self.config_file}

"""
            output += json.dumps(config, indent=2)

            return output
        except Exception as e:
            return f"❌ Error reading config: {e}"


def main():
    """Entry point for diagnostic script."""
    parser = argparse.ArgumentParser(
        prog="fix-pseudonymization",
        description="Diagnose and fix pseudonymization issues",
        epilog="Examples:\n"
               "  fix_pseudonymization.py                  # Diagnostic report\n"
               "  fix_pseudonymization.py --show-payloads  # Show unpseudonymized payloads\n"
               "  fix_pseudonymization.py --show-config    # Show configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--show-payloads",
        action="store_true",
        help="Show detailed list of non-pseudonymized payloads",
    )

    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration file",
    )

    parser.add_argument(
        "--captures-dir",
        type=Path,
        help="Path to captures directory",
    )

    args = parser.parse_args()

    try:
        diagnostic = PseudonymizationDiagnostic(captures_dir=args.captures_dir)
        diagnostic.load_payloads()

        if args.show_payloads:
            report = diagnostic.show_non_pseudonymized_payloads()
        elif args.show_config:
            report = diagnostic.show_config_file()
        else:
            report = diagnostic.generate_diagnostic_report()

        print(report)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
