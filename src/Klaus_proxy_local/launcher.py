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
import signal
import subprocess
import sys
from pathlib import Path

from Klaus_proxy_local.certs import ensure_mitmproxy_certs
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

    def ensure_prerequisites(self) -> None:
        """Ensure config and certs exist before launching proxy.

        Raises:
          RuntimeError: If setup or cert generation fails.
        """
        print("⚙️  Setting up Klaus Proxy Local...\n")

        # Step 1: Auto-generate config
        try:
            self.config = init_config_if_missing()
            print(f"✅ Configuration ready")
            print(f"   Location: ~/.klaus-proxy/config.json\n")
        except Exception as e:
            raise RuntimeError(f"❌ Config setup failed: {e}")

        # Step 2: Auto-generate certs
        try:
            self.cert_file = ensure_mitmproxy_certs()
            print(f"✅ Certificates ready")
            print(f"   Location: {self.cert_file}\n")
        except RuntimeError as e:
            raise RuntimeError(f"❌ Cert setup failed: {e}")

    def show_dashboard(self) -> None:
        """Show startup dashboard."""
        print("=" * 60)
        print("🔐 Klaus Proxy Local — Running")
        print("=" * 60)
        print(f"")
        print(f"🎯 Listening on:        {self.HOST}:{self.PORT}")
        print(f"📁 Config:              ~/.klaus-proxy/config.json")
        print(f"📋 Captures:            ~/.klaus-proxy/captures/")
        print(f"🔒 Certificate:         {self.cert_file}")
        print(f"")
        print("📖 Usage:")
        print(f"  Terminal 1 (this one): Keep this running")
        print(f"  Terminal 2: export HTTP_PROXY=http://{self.HOST}:{self.PORT}")
        print(f"              export HTTPS_PROXY=http://{self.HOST}:{self.PORT}")
        print(f"              claude 'your question'")
        print(f"")
        print("🛑 To stop: Press Ctrl+C")
        print("=" * 60)
        print("")

    def launch_mitmdump(self) -> None:
        """Launch mitmdump with pseudonymization and capture addons.

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
        mitmdump_cmd = [
            "mitmdump",
            "-s",
            str(pseudonymize_addon),
            "-s",
            str(capture_addon),
            "-p",
            str(self.PORT),
            "-q",  # quiet mode
        ]

        try:
            print(f"🚀 Starting mitmdump...")
            print(f"   Command: {' '.join(mitmdump_cmd)}\n")

            self.mitmdump_process = subprocess.Popen(
                mitmdump_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Small delay to let mitmdump start
            import time

            time.sleep(1)

            # Check if process is still alive
            if self.mitmdump_process.poll() is not None:
                _, stderr = self.mitmdump_process.communicate()
                raise RuntimeError(
                    f"❌ mitmdump failed to start:\n{stderr}\n"
                    f"   Make sure mitmproxy is installed: pip install mitmproxy"
                )

        except FileNotFoundError:
            raise RuntimeError(
                f"❌ mitmdump not found in PATH.\n"
                f"   Install mitmproxy:\n"
                f"   brew install mitmproxy   (macOS)\n"
                f"   apt install mitmproxy    (Ubuntu)\n"
                f"   pip install mitmproxy    (anywhere)"
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
