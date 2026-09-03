#!/usr/bin/env python3
"""Auto-config generation for Klaus Proxy Local (FASE 1.1).

Generates configuration on first run:
  - Random salt (ANTHROPIC_PSEUDO_SALT)
  - Directory structure (~/.klaus-proxy/)
  - config.json with secure permissions

This removes the manual salt configuration burden from FASE 0.
"""
import json
import os
import secrets
from pathlib import Path


def config_dir() -> Path:
    """Directory where user config lives."""
    return Path.home() / ".klaus-proxy"


def config_file() -> Path:
    """Path to config.json."""
    return config_dir() / "config.json"


def capture_dir() -> Path:
    """Base directory for captures (original/ and sent/)."""
    return config_dir() / "captures"


def original_dir() -> Path:
    """Directory for captures/original/."""
    return capture_dir() / "original"


def sent_dir() -> Path:
    """Directory for captures/sent/."""
    return capture_dir() / "sent"


def vault_path() -> Path:
    """Path to pseudonym vault."""
    return capture_dir() / ".vault.json"


def _generate_salt() -> str:
    """Generate a random, cryptographically secure salt.

    Returns a 32-character hex string suitable for ANTHROPIC_PSEUDO_SALT.
    """
    return secrets.token_hex(16)  # 16 bytes = 32 hex chars


def init_config_if_missing() -> dict:
    """Initialize configuration if ~/.klaus-proxy/config.json doesn't exist.

    On first run:
      1. Create ~/.klaus-proxy/ (0o700)
      2. Generate random salt
      3. Write config.json (0o600)
      4. Create captures/{original,sent}/ (0o700 each)

    Returns the configuration dict loaded from or created in config.json.

    Raises:
      OSError: If directory/file operations fail
    """
    cfg_dir = config_dir()
    cfg_file = config_file()

    # Already initialized
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Config corrupted; regenerate
            pass

    # First run: create everything
    print("🔐 Klaus Proxy Local — First-time setup\n")

    # 1. Create config directory (0o700 = owner rwx only)
    cfg_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    print(f"✅ Created {cfg_dir} (mode 0o700)")

    # 2. Generate random salt
    salt = _generate_salt()
    print(f"✅ Generated salt: {salt[:8]}... (saved to config, never shown again)")

    # 3. Build config object
    config = {
        "version": "0.1.0",
        "salt": salt,
        "hosts": [
            "api.anthropic.com",
            "llm.tools.cloud.customer1.es",
        ],
        "capture_dir": str(capture_dir()),
        "vault_path": str(vault_path()),
        "log_level": "info",
    }

    # 4. Write config.json (0o600 = owner rw only)
    cfg_file.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.chmod(cfg_file, 0o600)
    print(f"✅ Config written to {cfg_file} (mode 0o600)")

    # 5. Create capture directories (0o700 each)
    capture_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    for cap_dir in [original_dir(), sent_dir()]:
        cap_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    print(f"✅ Captures directory ready at {capture_dir()}")

    print()
    return config


def load_config() -> dict:
    """Load configuration from ~/.klaus-proxy/config.json.

    Calls init_config_if_missing() if config doesn't exist.

    Returns:
      Dictionary with keys: version, salt, hosts, capture_dir, vault_path, log_level

    Raises:
      OSError: If config file can't be read
      json.JSONDecodeError: If config is invalid JSON
    """
    return init_config_if_missing()
