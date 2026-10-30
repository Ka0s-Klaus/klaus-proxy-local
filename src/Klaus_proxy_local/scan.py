#!/usr/bin/env python3
"""CLI entry point for Klaus Sensitive Data Scanner.

Usage:
    klaus-scan /path/to/project
    klaus-scan /path/to/project --min-confidence MEDIUM
    klaus-scan /path/to/project --counts
    klaus-scan /path/to/project --approve-all

La salida es segura por defecto (#140): cada valor se muestra como un
identificador estable (``⟨categoría·a1b2c3d4·13c⟩``), sin contexto y con rutas
relativas. Si el escaneo lo lanza Claude Code, nada de lo detectado entra en el
contexto del modelo. ``--reveal`` muestra valores y contexto en claro, para
revisarlos en tu terminal.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from typing import NoReturn

from Klaus_proxy_local.business_names import BUSINESS_CATEGORIES
from Klaus_proxy_local.sensitive_data_scanner import (
    Confidence,
    SensitiveDataScanner,
)

_RUN_SALT = secrets.token_hex(16)
# Palabras de las formas jurídicas y dominios que no identifican a nadie
_PATH_WORDS = frozenset(
    {"gmbh", "corp", "corporation", "limited", "holdings", "group", "grupo", "http"}
)


def parse_args(argv: list[str] | None = None) -> dict:
    """Parse command-line arguments."""
    parser = ArgumentParser(
        prog="klaus-scan",
        description=(
            "Klaus Sensitive Data Scanner — detect secrets and business names "
            "(clients, corporate domains, cloud IDs) in your project. The output "
            "never shows the detected values unless --reveal is given."
        ),
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
        default="HIGH",
        help="Minimum confidence level to report (default: HIGH)",
    )

    parser.add_argument(
        "--approve-all",
        action="store_true",
        help="Automatically approve all findings above the threshold (skip review)",
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
        "--no-business",
        action="store_true",
        help="Disable business-name detection (clients, domains, cloud IDs)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (values masked unless --reveal)",
    )

    parser.add_argument(
        "--counts",
        action="store_true",
        help="Only print counts by category and confidence",
    )

    parser.add_argument(
        "--reveal",
        action="store_true",
        help="Show detected values and context in clear (only in your own terminal)",
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
    from Klaus_proxy_local import __version__

    print("\n" + "─" * 60)
    print(f"🔍 Klaus Sensitive Data Scanner v{__version__}")
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
    above_threshold = [f for f in result.findings if f.confidence <= min_confidence]
    print(f"Findings above threshold: {len(above_threshold)}/{len(result.findings)}")
    if result.already_protected:
        print(
            f"Business names already protected in config.json: {result.already_protected}"
        )


# --- Salida segura (#140) -------------------------------------------------------


def _salt() -> str:
    """SALT del proxy: el mismo valor da el mismo identificador entre ejecuciones."""
    salt = os.environ.get("ANTHROPIC_PSEUDO_SALT")
    if salt:
        return salt
    try:
        config = json.loads(
            (Path.home() / ".klaus-proxy" / "config.json").read_text(encoding="utf-8")
        )
        if isinstance(config, dict) and config.get("salt"):
            return str(config["salt"])
    except (OSError, ValueError):
        # Sin config.json legible: SALT aleatoria, estable solo en esta ejecución
        return _RUN_SALT
    return _RUN_SALT


def safe_id(value: str, category: str) -> str:
    """``⟨categoría·hash8·Nc⟩``: no revela ni un carácter del valor."""
    digest = hashlib.sha256(f"{_salt()}\0{value}".encode()).hexdigest()[:8]
    return f"⟨{category}·{digest}·{len(value)}c⟩"


def _mask_value(value: str, category: str = "value") -> str:
    """Mask a sensitive value for safe display (#140: no characters shown)."""
    return safe_id(value, category)


def safe_path(path: Path, root: Path, values: list[str]) -> str:
    """Ruta relativa a la carpeta escaneada; un componente que contenga un
    valor detectado se enmascara."""
    try:
        rel = Path(path).resolve().relative_to(root.resolve())
    except ValueError:
        rel = Path(Path(path).name)
    # Basta con compartir una palabra: «Tailspin Toys» → docs/tailspin-toys/
    tokens = {
        t
        for v in values
        for t in re.split(r"[^a-z0-9]+", v.lower())
        if len(t) >= 4 and t not in _PATH_WORDS
    }
    parts = [
        safe_id(p, "dir") if any(t in p.lower() for t in tokens) else p
        for p in rel.parts
    ]
    return "/".join(parts) or "."


def _display(finding, root: Path, values: list[str], reveal: bool) -> dict:
    """Lo que se muestra de un hallazgo: en claro solo con ``--reveal``."""
    data = {
        "id": safe_id(finding.value, finding.category),
        "category": finding.category,
        "detection_method": finding.detection_method,
        "confidence": finding.confidence.name,
        "file_path": safe_path(finding.file_path, root, values),
        "line_number": finding.line_number,
        "reason": finding.reason,
        "occurrences": finding.occurrences,
    }
    if reveal:
        data["value"] = finding.value
        data["context"] = finding.context
        data["file_path"] = str(finding.file_path)
    return data


def print_counts(result, min_confidence: Confidence) -> None:
    """Solo recuentos por categoría y confianza."""
    counts = Counter(
        (f.category, f.confidence.name)
        for f in result.findings
        if f.confidence <= min_confidence
    )
    print(f"Files scanned: {result.total_files_scanned}")
    for (category, conf), n in sorted(counts.items()):
        print(f"  {conf:<8} {category:<24} {n}")
    if not counts:
        print("  (no findings above threshold)")
    print(f"Business names already protected: {result.already_protected}")


def print_findings(
    result,
    min_confidence: Confidence,
    root: Path | None = None,
    reveal: bool = False,
) -> None:
    """Print findings for review."""
    root = root or Path(".")
    above_threshold = [f for f in result.findings if f.confidence <= min_confidence]
    values = [f.value for f in result.findings]

    if not above_threshold:
        print("\n✨ No findings above threshold")
        return

    print(f"\n\n📋 {len(above_threshold)} Findings to Review")
    print("─" * 60)
    if reveal:
        print("⚠️  --reveal: values and context are shown in clear.")

    for idx, finding in enumerate(above_threshold, 1):
        d = _display(finding, root, values, reveal)
        conf_icon = {
            Confidence.CRITICAL: "🔴",
            Confidence.HIGH: "🟠",
            Confidence.MEDIUM: "🟡",
            Confidence.LOW: "🔵",
        }[finding.confidence]

        print(f"\n[{idx}/{len(above_threshold)}] {conf_icon} {finding.confidence.name}")
        print(f"  File: {d['file_path']}:{finding.line_number}")
        print(f"  Type: {finding.category}")
        print(f"  Method: {finding.detection_method}")
        print(f"  Detected: {d['id']}")
        if finding.occurrences > 1:
            print(f"  Occurrences: {finding.occurrences}")
        if reveal:
            print(f"  Value: {finding.value}")
            if finding.context:
                context = finding.context[:80]
                if len(finding.context) > 80:
                    context += "..."
                print(f"  Context: {context}")
        print(f"  Reason: {finding.reason}")


def interactive_review(
    result,
    min_confidence: Confidence,
    vault_integration=None,
    root: Path | None = None,
    reveal: bool = False,
) -> int:
    """Interactive review of findings above threshold.

    Returns: count of findings approved for vault
    """
    root = root or Path(".")
    above_threshold = [f for f in result.findings if f.confidence <= min_confidence]
    values = [f.value for f in result.findings]

    if not above_threshold:
        return 0

    approved_count = 0
    approve_all_remaining = False

    for idx, finding in enumerate(above_threshold, 1):
        d = _display(finding, root, values, reveal)
        # Confidence indicator
        conf_icon = {
            Confidence.CRITICAL: "🔴",
            Confidence.HIGH: "🟠",
            Confidence.MEDIUM: "🟡",
            Confidence.LOW: "🔵",
        }[finding.confidence]

        print(f"\n[{idx}/{len(above_threshold)}] {conf_icon} {finding.confidence.name}")
        print(f"  File: {d['file_path']}:{finding.line_number}")
        print(f"  Type: {finding.category}")
        print(f"  Method: {finding.detection_method}")
        print(f"  Detected: {d['id']}")
        if reveal:
            print(f"  Value: {finding.value}")
            print(f"\n  Context: {finding.context[:120]}")
        print(f"  Reason: {finding.reason}")

        # Check if already in vault
        if vault_integration:
            existing = vault_integration.check_already_in_vault(finding.value)
            if existing:
                print(f"  ⓘ Already in vault: {existing}")
                continue

        # Get user input
        if approve_all_remaining:
            response = "A"
        else:
            while True:
                response = (
                    input(
                        "\n  Action: [A]pprove / [S]kip / [C]opy value / [L]All / [Q]uit? >> "
                    )
                    .strip()
                    .upper()
                )
                if response in ("A", "S", "C", "L", "Q"):
                    break
                print("  Invalid choice. Use A, S, C, L, or Q")

        if response == "A":
            finding.user_approved = True
            approved_count += 1

            # Add to vault if integration available
            if vault_integration:
                try:
                    prefix = _get_prefix_for_category(finding.category)
                    pseudo = vault_integration.add_finding_to_vault(finding, prefix)
                    print("  ✓ Approved: added to vault and config.json")
                    print(f"     Pseudonym: {pseudo}")
                except Exception as e:
                    print(f"  ⚠️  Approved but vault error: {e}")
            else:
                print("  ✓ Approved")

        elif response == "S":
            print("  ⊘ Skipped")
        elif response == "C":
            # Copy to clipboard (if available); never printed (#140)
            try:
                import subprocess

                subprocess.run(["pbcopy"], input=finding.value.encode(), check=True)
                print("  📋 Copied to clipboard")
            except Exception:
                print("  ⓘ Clipboard unavailable (use --reveal to see the value)")
        elif response == "L":
            approve_all_remaining = True
            finding.user_approved = True
            approved_count += 1

            if vault_integration:
                try:
                    prefix = _get_prefix_for_category(finding.category)
                    pseudo = vault_integration.add_finding_to_vault(finding, prefix)
                    print("  ✓ Approved: added to vault and config.json")
                    print(f"     Pseudonym: {pseudo}")
                except Exception as e:
                    print(f"  ⚠️  Approved but vault error: {e}")
            else:
                print("  ✓ Approved")

            print("  📋 Approving all remaining findings...")
        elif response == "Q":
            print("\n⊘ Review cancelled")
            return approved_count

    return approved_count


def _get_prefix_for_category(category: str) -> str:
    """Determine vault prefix based on finding category."""
    if category in BUSINESS_CATEGORIES:
        return "org"
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
    quiet = args["json"] or args["counts"]

    if not quiet:
        print_header()

    # Validate path
    path = Path(args["path"]).resolve()
    if not path.exists():
        print(f"❌ Error: Path not found: {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"❌ Error: Path is not a directory: {path}")
        sys.exit(1)

    if not quiet:
        print(f"Scanning: {path}")

    # Create scanner
    scanner = SensitiveDataScanner(
        enable_contextual=args["enable_contextual"],
        enable_heuristic=args["enable_heuristic"],
        enable_business=not args["no_business"],
    )

    # Run scan
    def progress_callback(current: int, total: int) -> None:
        if total > 0 and not quiet:
            pct = (current * 100) // total
            bar_len = 40
            filled = (current * bar_len) // total
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r[{bar}] {pct}% ({current}/{total} files)", end="", flush=True)

    result = scanner.scan_directory(path, progress_callback)
    if not quiet:
        print()  # New line after progress bar

    # Parse min confidence
    min_confidence = confidence_from_string(args["min_confidence"])
    above_threshold = [f for f in result.findings if f.confidence <= min_confidence]

    if args["counts"]:
        print_counts(result, min_confidence)
        sys.exit(0)

    # JSON output
    if args["json"]:
        values = [f.value for f in result.findings]
        output = {
            "total_files_scanned": result.total_files_scanned,
            "findings_count": len(above_threshold),
            "already_protected": result.already_protected,
            "revealed": args["reveal"],
            "findings": [
                _display(f, path, values, args["reveal"]) for f in above_threshold
            ],
            "scan_duration_seconds": result.scan_duration_seconds,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Print summary
    print_summary(result, min_confidence)

    # Print findings
    print_findings(result, min_confidence, path, args["reveal"])

    # Initialize vault integration
    vault_integration = None
    try:
        from Klaus_proxy_local.sensitive_data_scanner import VaultIntegration

        vault_integration = VaultIntegration()
    except Exception as e:
        print(f"⚠️  Vault integration unavailable: {e}")

    # Interactive review (unless --approve-all)
    approved_count = 0
    if args["approve_all"]:
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
    elif above_threshold and not sys.stdin.isatty():
        # Sin terminal (p.ej. lanzado por Claude Code) no se puede preguntar (#140)
        print("\nⓘ No interactive terminal: review skipped (use --approve-all)")
    elif above_threshold:
        review = (
            input(f"\n\nReview {len(above_threshold)} finding(s)? [Y/N]: ")
            .strip()
            .upper()
        )
        if review == "Y":
            approved_count = interactive_review(
                result, min_confidence, vault_integration, path, args["reveal"]
            )

    print("\n\n✨ Scan complete")
    print(f"  Files scanned: {result.total_files_scanned}")
    print(f"  Findings: {len(result.findings)}")
    print(f"  Approved for vault: {approved_count}")
    if approved_count:
        print("  Restart claude-proxy to apply the new rules in config.json.")

    sys.exit(0)


if __name__ == "__main__":
    main()
