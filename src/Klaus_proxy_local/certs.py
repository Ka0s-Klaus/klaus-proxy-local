#!/usr/bin/env python3
"""Auto-cert generation for Klaus Proxy Local (FASE 1.2).

Generates mitmproxy certificate on first run:
  - Detects if mitmproxy is installed
  - Checks if cert already exists
  - Runs mitmproxy to generate cert if missing
  - Verifies cert exists before returning

This removes the manual mitmproxy cert setup burden.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def mitmproxy_cert_dir() -> Path:
    """Directory where mitmproxy stores certificates."""
    return Path.home() / ".mitmproxy"


def mitmproxy_cert_file() -> Path:
    """Path to the mitmproxy CA certificate."""
    return mitmproxy_cert_dir() / "mitmproxy-ca-cert.pem"


def mitm_executable(name: str) -> str:
    """Resolve a mitmproxy binary (``mitmproxy``, ``mitmdump``).

    Looks in PATH first and falls back to the directory of the running
    interpreter, so binaries installed in the Klaus venv are found even
    when that venv is not in PATH (e.g. when launched via the
    ``~/.local/bin`` symlinks created by install.sh).

    Returns:
      Full path to the binary, or ``name`` unchanged if not found.
    """
    found = shutil.which(name)
    if found:
        return found
    sibling = Path(sys.executable).parent / name
    if sibling.is_file():
        return str(sibling)
    return name


def is_mitmproxy_installed() -> bool:
    """Check if mitmproxy is installed and accessible.

    Returns:
      True if `mitmdump --version` succeeds, False otherwise.

    Note:
      This is a best-effort check. Mitmproxy might be installed
      but not in PATH, or might be installed via Homebrew.
    """
    try:
        result = subprocess.run(
            [mitm_executable("mitmdump"), "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def generate_mitmproxy_certs() -> bool:
    """Generate mitmproxy certificates by running mitmdump.

    Starts mitmdump for a few seconds to trigger cert generation.
    Mitmproxy auto-generates certs on first run and stores them in ~/.mitmproxy/.

    Returns:
      True if cert generation succeeded, False on error.

    Note:
      This runs headless `mitmdump -q` on an ephemeral localhost port with a
      3-second timeout. The interactive `mitmproxy` console cannot be used
      here: without a TTY it crashes before generating the CA (#43).
    """
    try:
        # Headless, quiet, ephemeral port (-p 0) to avoid clashing with a
        # running proxy on 8899 or anything else on 8080
        subprocess.run(
            [
                mitm_executable("mitmdump"),
                "-q",
                "--listen-host",
                "127.0.0.1",
                "-p",
                "0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        # This is EXPECTED: mitmdump runs indefinitely, we timeout after 3s
        # By that time, certs have been generated
        pass
    except (FileNotFoundError, OSError) as e:
        print(f"❌ Failed to run mitmdump: {e}", file=sys.stderr)
        return False

    # Verify cert file exists
    cert_file = mitmproxy_cert_file()
    return cert_file.exists()


def ensure_mitmproxy_certs() -> Path:
    """Ensure mitmproxy certificates exist; generate if missing.

    On first run:
      1. Check if cert already exists at ~/.mitmproxy/mitmproxy-ca-cert.pem
      2. If it exists, return the path
      3. If not, verify mitmproxy is installed
      4. Run mitmproxy to generate certs (timeout after 3s)
      5. Verify cert exists
      6. Return the path

    Returns:
      Path to the mitmproxy CA certificate (~/.mitmproxy/mitmproxy-ca-cert.pem)

    Raises:
      RuntimeError: If mitmproxy is not installed or cert generation fails.

    Note:
      This function is idempotent: it's safe to call multiple times.
      On subsequent calls, the existing cert is returned immediately.
    """
    cert_file = mitmproxy_cert_file()

    # Already generated
    if cert_file.exists():
        return cert_file

    print("🔒 Generating mitmproxy certificates...")
    print("   (this takes ~3 seconds, runs once)")

    # Verify mitmproxy is installed
    if not is_mitmproxy_installed():
        raise RuntimeError(
            "❌ mitmproxy not found. Install with:\n"
            "  brew install mitmproxy   (macOS)\n"
            "  apt install mitmproxy    (Ubuntu)\n"
            "  pip install mitmproxy    (anywhere)\n"
        )

    # Generate certs
    if not generate_mitmproxy_certs():
        raise RuntimeError(
            f"❌ Failed to generate mitmproxy certificates.\n"
            f"   Expected cert at: {cert_file}\n"
        )

    print(f"✅ Certificates ready at {cert_file}")
    return cert_file


def generate_env_vars_file(cert_file: Path) -> Path:
    """Generate shell environment variables file for SSL certificate trust.

    Creates ~/.klaus-proxy/klaus-env.sh that exports:
      - GIT_SSL_CAINFO: For git HTTPS connections
      - CURL_CA_BUNDLE: For curl SSL/TLS verification
      - SSL_CERT_FILE: For general SSL/TLS tools

    This allows clients (git, curl, etc.) to trust the proxy's certificate
    without requiring system-wide certificate installation.

    Args:
      cert_file: Path to the mitmproxy CA certificate

    Returns:
      Path to the generated environment file (~/.klaus-proxy/klaus-env.sh)
    """
    klaus_dir = Path.home() / ".klaus-proxy"
    klaus_dir.mkdir(parents=True, exist_ok=True)

    env_file = klaus_dir / "klaus-env.sh"

    # Generate the shell script content
    content = f"""#!/bin/bash
# 🔐 Klaus Proxy Local — Environment Variables
# Auto-generated by Klaus Proxy. Source this file to configure SSL/TLS
# Usage: source ~/.klaus-proxy/klaus-env.sh

# Certificate path for git, curl, and other SSL/TLS tools
export GIT_SSL_CAINFO="{cert_file}"
export CURL_CA_BUNDLE="{cert_file}"
export SSL_CERT_FILE="{cert_file}"

# Optional: For Python-based tools
export REQUESTS_CA_BUNDLE="{cert_file}"

# Optional: For Node.js-based tools (already handled by proxy launcher)
# export NODE_EXTRA_CA_CERTS="{cert_file}"
"""

    try:
        env_file.write_text(content)
        env_file.chmod(0o644)
        return env_file
    except Exception as e:
        raise RuntimeError(f"Failed to generate environment file: {e}")
