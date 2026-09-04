#!/usr/bin/env python3
"""Smart proxy launcher for Klaus Proxy Local (FASE 1.3).

Orchestrates:
- Auto-config generation (setup.py)
- Auto-cert generation (certs.py)
- mitmdump launch with addons
- Status dashboard

Usage:
  claude-proxy           # Start the proxy (entry point in pyproject.toml)
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from Klaus_proxy_local import __version__
from Klaus_proxy_local.certs import (
    ensure_mitmproxy_certs,
    mitmproxy_cert_dir,
    mitmproxy_cert_file,
    generate_mitmproxy_certs,
)
from Klaus_proxy_local.setup import init_config_if_missing


class ProxyLauncher:
    """Smart proxy launcher with auto-setup orchestration."""

    HOST = "127.0.0.1"
    PORT = 8899

    def __init__(self) -> None:
        """Initialize launcher."""
        self.config = None
        self.cert_file = None
        self.mitmdump_process = None

    def regenerate_certs_if_needed(self) -> None:
        """Regenerate mitmproxy certificates if they might be corrupted.

        Detects and fixes certificate issues automatically:
        - Deletes old/corrupted certificates
        - Regenerates fresh ones
        - Ensures client can trust the proxy
        """
        cert_file = mitmproxy_cert_file()
        cert_dir = mitmproxy_cert_dir()

        # Check if cert might be corrupted (empty, too small, etc.)
        if cert_file.exists():
            size = cert_file.stat().st_size
            if size < 100:  # Valid PEM certs are at least a few KB
                print("⚠️  Certificate appears corrupted (too small)")
                print(f"   Regenerating from {cert_dir}...\n")
                shutil.rmtree(cert_dir, ignore_errors=True)

        # Regenerate if missing or was deleted
        if not cert_file.exists():
            print("🔒 Generating mitmproxy certificates...\n")
            if not generate_mitmproxy_certs():
                raise RuntimeError(
                    f"❌ Failed to generate certificates at {cert_file}"
                )

    def ensure_prerequisites(self) -> None:
        """Ensure config and certs exist before launching proxy.

        Raises:
          RuntimeError: If setup or cert generation fails.
        """
        print("⚙️  Setting up Klaus Proxy Local...\n")

        # Step 1: Auto-generate config
        try:
            self.config = init_config_if_missing()
            print("✅ Configuration ready")
            print("   Location: ~/.klaus-proxy/config.json\n")

            # Export SALT to environment if not already set
            if "ANTHROPIC_PSEUDO_SALT" not in os.environ:
                salt = self.config.get("salt")
                if salt:
                    os.environ["ANTHROPIC_PSEUDO_SALT"] = salt
                    print(f"✅ Exported ANTHROPIC_PSEUDO_SALT from config\n")
        except Exception as e:
            raise RuntimeError(f"❌ Config setup failed: {e}")

        # Step 2: Auto-regenerate or ensure certs
        try:
            self.regenerate_certs_if_needed()
            self.cert_file = ensure_mitmproxy_certs()
            print("✅ Certificates ready")
            print(f"   Location: {self.cert_file}\n")
        except RuntimeError as e:
            raise RuntimeError(f"❌ Cert setup failed: {e}")

    def show_dashboard(self) -> None:
        """Show startup dashboard."""
        print("=" * 70)
        print(f"🔐 Klaus Proxy Local — Running (v{__version__})")
        print("=" * 70)
        print("")
        print(f"🎯 Listening on:          {self.HOST}:{self.PORT}")
        print("📁 Config:                ~/.klaus-proxy/config.json")
        print("📋 Captures:              ~/.klaus-proxy/captures/")
        print(f"🔒 Certificate:           {self.cert_file}")
        print("✅ Auto-configuration:    ALL CERTIFICATES + ENV VARS SET")
        print("")
        print("📖 Usage (NO configuration needed):")
        print("  Terminal 1 (this one):   Keep this running")
        print(f"  Terminal 2:              export HTTPS_PROXY=http://{self.HOST}:{self.PORT}")
        print("                           claude 'your question'")
        print("")
        print("🔐 TLS Certificate Trust:  AUTOMATIC (regenerated if needed)")
        print("")
        print("🛑 To stop: Press Ctrl+C")
        print("=" * 70)
        print("")

    def process_log_line(self, line: str) -> str:
        """Add version prefix to log lines with timestamps.

        Transforms: [14:18:53.157][anthropic-pseudo] message
        Into:       [v0.1.0][14:18:53.157][anthropic-pseudo] message
        """
        # Match lines starting with a timestamp in format [HH:MM:SS.mmm]
        # Handles variations: [HH:MM:SS], [HH:MM:SS.m], [HH:MM:SS.mm], [HH:MM:SS.mmm], etc.
        if re.match(r"^\[\d{2}:\d{2}:\d{2}(\.\d+)?\]", line):
            return f"[v{__version__}]{line}"
        return line

    def stream_logs(self, stream, is_stderr: bool = False) -> None:
        """Stream logs from mitmdump process, adding version prefix."""
        try:
            for line in iter(stream.readline, ""):
                if line:
                    processed_line = self.process_log_line(line.rstrip())
                    if is_stderr:
                        print(processed_line, file=sys.stderr)
                    else:
                        print(processed_line)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def launch_mitmdump(self) -> None:
        """Launch mitmdump with pseudonymization and capture addons.

        Auto-configures environment variables for clients:
        - NODE_EXTRA_CA_CERTS: Path to mitmproxy CA certificate
        - NODE_TLS_REJECT_UNAUTHORIZED: Disabled as fallback if needed

        Raises:
          RuntimeError: If mitmdump fails to start.
        """
        # Addons path (relative to project root)
        addons_dir = Path(__file__).resolve().parents[2] / "src"
        pseudonymize_addon = addons_dir / "anthropic_payload_pseudonymize.py"
        capture_addon = addons_dir / "anthropic_payload_capture.py"

        # Verify addons exist
        if not pseudonymize_addon.exists():
            raise RuntimeError(
                f"❌ Pseudonymization addon not found: {pseudonymize_addon}\n"
                f"   Make sure Klaus Proxy is installed in development mode: pip install -e ."
            )
        if not capture_addon.exists():
            raise RuntimeError(
                f"❌ Capture addon not found: {capture_addon}\n"
                f"   Make sure Klaus Proxy is installed in development mode: pip install -e ."
            )

        # Build mitmdump command
        # Addons must come BEFORE port: pseudonymize (request rewrite)
        # then capture (evidence collection)
        # NOTE: No -q flag to show all logs with version prefix
        mitmdump_cmd = [
            "mitmdump",
            "-s",
            str(pseudonymize_addon),
            "-s",
            str(capture_addon),
            "-p",
            str(self.PORT),
        ]

        try:
            print("🚀 Starting mitmdump...")
            print(f"   Command: {' '.join(mitmdump_cmd)}\n")

            # Set up environment with certificate trust configuration
            env = os.environ.copy()
            env["NODE_EXTRA_CA_CERTS"] = str(mitmproxy_cert_file())
            # Fallback for NodeJS/npm tools that don't respect NODE_EXTRA_CA_CERTS
            env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
            # Ensure ANTHROPIC_PSEUDO_SALT is set (from config or env)
            if "ANTHROPIC_PSEUDO_SALT" in os.environ:
                env["ANTHROPIC_PSEUDO_SALT"] = os.environ["ANTHROPIC_PSEUDO_SALT"]

            self.mitmdump_process = subprocess.Popen(
                mitmdump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
            )

            # Start thread to stream logs with version prefix
            log_thread = threading.Thread(
                target=self.stream_logs, args=(self.mitmdump_process.stdout, False)
            )
            log_thread.daemon = True
            log_thread.start()

            # Small delay to let mitmdump start
            import time

            time.sleep(1)

            # Check if process is still alive
            if self.mitmdump_process.poll() is not None:
                raise RuntimeError(
                    "❌ mitmdump failed to start.\n"
                    "   Make sure mitmproxy is installed: pip install mitmproxy"
                )

        except FileNotFoundError:
            raise RuntimeError(
                "❌ mitmdump not found in PATH.\n"
                "   Install mitmproxy:\n"
                "   brew install mitmproxy   (macOS)\n"
                "   apt install mitmproxy    (Ubuntu)\n"
                "   pip install mitmproxy    (anywhere)"
            )

    def handle_signal(self, signum, frame) -> None:
        """Handle Ctrl+C gracefully."""
        print("\n\n🛑 Stopping Klaus Proxy Local...")
        self.shutdown()
        sys.exit(0)

    def shutdown(self) -> None:
        """Shutdown proxy cleanly."""
        if self.mitmdump_process:
            try:
                self.mitmdump_process.terminate()
                self.mitmdump_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mitmdump_process.kill()
                self.mitmdump_process.wait()
            print("✅ Proxy stopped")

    def run(self) -> None:
        """Run the proxy (entry point).

        Orchestrates:
        1. Ensure prerequisites (config + certs)
        2. Show dashboard
        3. Launch mitmdump
        4. Keep running until Ctrl+C
        """
        try:
            # Phase 1: Setup
            self.ensure_prerequisites()

            # Phase 2: Show status
            self.show_dashboard()

            # Phase 3: Launch proxy
            self.launch_mitmdump()

            # Phase 4: Keep running
            signal.signal(signal.SIGINT, self.handle_signal)
            signal.signal(signal.SIGTERM, self.handle_signal)

            # Wait forever (until Ctrl+C)
            self.mitmdump_process.wait()

        except RuntimeError as e:
            print(f"{e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            self.shutdown()
            sys.exit(1)


def main() -> None:
    """Entry point for claude-proxy command."""
    launcher = ProxyLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
