#!/usr/bin/env python3
"""Full audit workflow with automatic leak fixing.

Complete pipeline:
1. Generate audit report (capture statistics, leak detection, coverage)
2. Show results
3. If leaks found, offer to auto-add them to vault
4. Re-verify that pseudonymization is working

Usage:
  python full_audit_with_fixes.py [--auto] [--no-fix]

Flags:
  --auto      Auto-add detected leaks without confirmation
  --no-fix    Skip auto-fix (just generate report)
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    print(f"\n{'=' * 70}")
    print(f"🔧 {description}")
    print(f"{'=' * 70}\n")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0 and result.stderr:
        print("❌ Error:", result.stderr, file=sys.stderr)

    return result.returncode, result.stdout


def extract_leak_count(output: str) -> int:
    """Extract leak count from audit output."""
    for line in output.split("\n"):
        if "Fugas detectadas" in line:
            # Try to extract number
            import re

            match = re.search(r"(\d+)\s*-\s*", line)
            if match:
                return int(match.group(1))
    return 0


def main():
    """Main entry point."""
    auto_mode = "--auto" in sys.argv
    no_fix = "--no-fix" in sys.argv

    print("\n" + "=" * 70)
    print("🔍 AUDITORÍA COMPLETA CON CORRECCIÓN AUTOMÁTICA")
    print("=" * 70)

    # Step 1: Generate report
    print("\n📊 Paso 1: Generando reporte de auditoría...")
    exit_code, output = run_command(
        [sys.executable, "generate_audit_report.py"],
        "Generador de Reportes"
    )

    if exit_code != 0:
        print("❌ Error generando reporte")
        sys.exit(1)

    # Extract leak count
    leak_count = extract_leak_count(output)

    # Step 2: Check for leaks
    if leak_count == 0:
        print("\n" + "=" * 70)
        print("✅ RESULTADO: CERO FUGAS")
        print("=" * 70)
        print("\n🎉 Pseudonimización funcionando perfectamente")
        print("   No requiere acciones correctivas\n")
        return

    # Step 3: Offer to fix leaks
    print("\n" + "=" * 70)
    print(f"⚠️  RESULTADO: {leak_count} FUGA(S) DETECTADA(S)")
    print("=" * 70)

    if no_fix:
        print("\n💡 Para auto-añadir estas fugas al vault:")
        print("   python auto_add_detected_leaks.py --auto\n")
        return

    # Step 4: Auto-fix leaks
    print("\n🔧 Paso 2: Auto-añadiendo fugas detectadas al vault...")

    fix_cmd = [sys.executable, "auto_add_detected_leaks.py"]
    if auto_mode:
        fix_cmd.append("--auto")

    exit_code, fix_output = run_command(fix_cmd, "Auto-Corrector de Fugas")

    if exit_code != 0:
        print("⚠️  Algunas fugas podrían no haberse añadido correctamente")
    else:
        # Step 5: Re-verify
        print("\n🔍 Paso 3: Re-verificando pseudonimización...")

        verify_cmd = [sys.executable, "audit_captures.py", "--find-leaks"]
        exit_code, verify_output = run_command(verify_cmd, "Verificación Final")

        # Check for "No CRITICAL leaks"
        if "No CRITICAL leaks detected" in verify_output:
            print("\n" + "=" * 70)
            print("✅ RESULTADO FINAL: PSEUDONIMIZACIÓN CORRECTA")
            print("=" * 70)
            print("\n🎉 Todas las fugas han sido añadidas y pseudonimizadas correctamente\n")
        else:
            print("\n⚠️  Algunas fugas persisten. Revisa manually:")
            print("   python audit_captures.py --find-leaks\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado por el usuario\n")
        sys.exit(1)
