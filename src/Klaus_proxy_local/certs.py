#!/usr/bin/env python3
"""Auto-cert generation for Klaus Proxy Local (FASE 1.2).

Generates mitmproxy certificate on first run:
  - Detects if mitmproxy is installed
  - Checks if cert already exists
  - Runs mitmproxy to generate cert if missing
  - Verifies cert exists before returning

This removes the manual mitmproxy cert setup burden.
"""
import subprocess
import sys
from pathlib import Path


def mitmproxy_cert_dir() -> Path:
    """Directory where mitmproxy stores certificates."""
    return Path.home() / ".mitmproxy"


def mitmproxy_cert_file() -> Path:
    """Path to the mitmproxy CA certificate."""
    return mitmproxy_cert_dir() / "mitmproxy-ca-cert.pem"


def is_mitmproxy_installed() -> bool:
    """Check if mitmproxy is installed and accessible.

    Returns:
      True if `mitmproxy --version` succeeds, False otherwise.

    Note:
      This is a best-effort check. Mitmproxy might be installed
      but not in PATH, or might be installed via Homebrew.
    """
    try:
        result = subprocess.run(
            ["mitmproxy", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def generate_mitmproxy_certs() -> bool:
    """Generate mitmproxy certificates by running mitmproxy.

    Starts mitmproxy for a few seconds to trigger cert generation.
    Mitmproxy auto-generates certs on first run and stores them in ~/.mitmproxy/.

    Returns:
      True if cert generation succeeded, False on error.

    Note:
      This runs `mitmproxy -q` (quiet mode) with a 3-second timeout.
      The timeout allows cert generation to complete without waiting
      for the interactive prompt.
    """
    try:
        # Start mitmproxy in quiet mode with a timeout
        # The -q flag suppresses interactive output
        subprocess.run(
            ["mitmproxy", "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        # This is EXPECTED: mitmproxy runs indefinitely, we timeout after 3s
        # By that time, certs have been generated
        pass
    except (FileNotFoundError, OSError) as e:
        print(f"❌ Failed to run mitmproxy: {e}", file=sys.stderr)
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
