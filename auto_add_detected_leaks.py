#!/usr/bin/env python3
"""Auto-add detected leaks to vault with confirmation.

Detects leaks in captures/sent/, shows them, and adds to vault with confirmation.

Workflow:
1. Scan captures/sent/ for unredacted sensitive values
2. Show what was found
3. Ask user to confirm each value before adding
4. Add to vault with deterministic salt-based hashing
5. Verify by re-scanning to confirm fixes

Usage:
  python auto_add_detected_leaks.py [--auto] [--dry-run]

Flags:
  --auto      Add all leaks without confirmation
  --dry-run   Show what would be added, don't modify vault
"""

import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Optional

CAPTURES_DIR = Path.cwd() / "captures"
SENT_DIR = CAPTURES_DIR / "sent"
VAULT_PATH = CAPTURES_DIR / ".pseudonym_vault.json"


def load_vault() -> dict:
    """Load pseudonym vault."""
    if not VAULT_PATH.exists():
        return {}
    return json.loads(VAULT_PATH.read_text(encoding="utf-8"))


def save_vault(vault: dict) -> None:
    """Save vault with secure permissions."""
    vault_json = json.dumps(vault, indent=2, ensure_ascii=False)
    VAULT_PATH.write_text(vault_json, encoding="utf-8")
    os.chmod(VAULT_PATH, 0o600)


def load_payload(path: Path) -> dict:
    """Load a JSON payload."""
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def get_salt() -> str:
    """Get ANTHROPIC_PSEUDO_SALT from environment or config."""
    # Try environment first
    salt = os.environ.get("ANTHROPIC_PSEUDO_SALT")
    if salt:
        return salt

    # Try config.json
    config_file = Path.home() / ".klaus-proxy" / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if "salt" in config:
                return config["salt"]
        except Exception:
            pass

    raise RuntimeError(
        "⚠️  ANTHROPIC_PSEUDO_SALT no encontrado.\n"
        "\n"
        "Opciones:\n"
        "1. Export env var: export ANTHROPIC_PSEUDO_SALT=<salt>\n"
        "2. O ejecuta el launcher: python -m Klaus_proxy_local.launcher\n"
        "   (Genera config.json automáticamente)\n"
    )


def hash_value(value: str) -> str:
    """Generate hash for pseudonym."""
    salt = get_salt()
    return hashlib.sha1((salt + "::" + value).encode("utf-8")).hexdigest()[:8]


def detect_leaks() -> list[dict]:
    """Detect unredacted sensitive values in sent/."""
    vault = load_vault()

    critical_patterns = {
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "api_key": r"(?:api[_-]?key|apikey)[\"']?\s*[:=]\s*[\"']?[\w\-]{16,}",
        "github_token": r"ghp_[A-Za-z0-9_]{36,255}",
        "aws_key": r"AKIA[0-9A-Z]{16}",
    }

    leaks = []
    sent_files = list(SENT_DIR.glob("**/*.json"))[:100]

    for sent_file in sent_files:
        payload = load_payload(sent_file)
        payload_str = json.dumps(payload, ensure_ascii=False)

        for pattern_type, pattern in critical_patterns.items():
            matches = re.findall(pattern, payload_str, re.IGNORECASE)

            for match in matches:
                if pattern_type == "email":
                    if any(x in match.lower() for x in ["noreply", "test", "example", "localhost"]):
                        continue

                if match not in vault:
                    leaks.append({"type": pattern_type, "value": match, "hash": hash_value(match)})

    return list({l["value"]: l for l in leaks}.values())


def determine_prefix(value: str, pattern_type: str) -> str:
    """Determine pseudonym prefix based on value and type."""
    if "@" in value:
        return "email"
    elif re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", value):
        return "ip"
    elif pattern_type == "api_key":
        return "api_key"
    elif pattern_type == "github_token":
        return "github_token"
    elif pattern_type == "aws_key":
        return "aws_key"
    else:
        return pattern_type


def prompt_user(question: str, default: str = "n") -> bool:
    """Prompt user for yes/no confirmation."""
    valid = {"yes": True, "y": True, "no": False, "n": False}

    if default == "y":
        prompt_text = " [Y/n]: "
    else:
        prompt_text = " [y/N]: "

    while True:
        choice = input(question + prompt_text).lower().strip()

        if choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("  Ingresa 'yes' o 'no' (o 'y'/'n')")


def main():
    """Main entry point."""
    import sys

    auto_mode = "--auto" in sys.argv
    dry_run = "--dry-run" in sys.argv

    print("\n" + "=" * 70)
    print("🔧 AUTO-AÑADIR FUGAS DETECTADAS AL VAULT")
    print("=" * 70 + "\n")

    # Detect leaks
    print("🔍 Escaneando captures/sent/ para detectar fugas...\n")
    leaks = detect_leaks()

    if not leaks:
        print("✅ No se detectaron fugas críticas\n")
        return

    print(f"⚠️  Encontradas {len(leaks)} fugas potenciales:\n")

    # Show leaks
    for i, leak in enumerate(leaks[:20], 1):
        print(f"  {i}. {leak['type']:12} | {leak['value'][:60]}")

    if len(leaks) > 20:
        print(f"  ... y {len(leaks) - 20} más")

    print()

    # Confirm action (skip in dry-run)
    if not auto_mode and not dry_run:
        if not prompt_user("¿Añadir estos valores al vault?", default="n"):
            print("\n❌ Cancelado. No se realizaron cambios.\n")
            return

    # Load vault
    vault = load_vault()
    added_count = 0
    skipped_count = 0

    print("\n" + "-" * 70)
    print("📝 PROCESO DE AÑADIR AL VAULT")
    print("-" * 70 + "\n")

    for leak in leaks:
        value = leak["value"]
        pattern_type = leak["type"]
        prefix = determine_prefix(value, pattern_type)
        pseudo_hash = leak["hash"]
        pseudo = f"{prefix}_{pseudo_hash}"

        # Skip if already in vault
        if value in vault:
            print(f"⏭️  Saltando (ya en vault):")
            print(f"    {value[:60]} → {pseudo}\n")
            skipped_count += 1
            continue

        # Show what will be added
        print(f"➕ Añadiendo:")
        print(f"    Real:       {value[:60]}")
        print(f"    Pseudónimo: {pseudo}")
        print(f"    Tipo:       {pattern_type}\n")

        if not dry_run:
            vault[value] = pseudo
            added_count += 1

    if dry_run:
        print("\n💡 (Dry-run mode: no se realizaron cambios)\n")
    else:
        # Save vault
        if added_count > 0:
            print("-" * 70)
            print(f"💾 Guardando {added_count} nuevas entradas en vault...\n")
            save_vault(vault)
            print(f"✅ Vault actualizado: {VAULT_PATH}")
            print(f"   Permisos: 0o600 (solo lectura/escritura dueño)\n")

    # Summary
    print("=" * 70)
    print("📊 RESUMEN")
    print("=" * 70 + "\n")
    print(f"  Fugas detectadas:  {len(leaks)}")
    print(f"  Nuevas entradas:   {added_count}")
    print(f"  Ya en vault:       {skipped_count}")
    print(f"  Total en vault:    {len(vault)}")

    if added_count > 0 and not dry_run:
        print("\n✅ Valores añadidos correctamente")
        print("\n🔍 Próximo paso: Ejecuta audit_captures.py --find-leaks")
        print("   para verificar que se pseudonimizaron correctamente\n")
    elif dry_run:
        print("\n💡 Para aplicar los cambios, ejecuta sin --dry-run")
    else:
        print("\n✅ No había nuevas fugas para añadir\n")


if __name__ == "__main__":
    main()
