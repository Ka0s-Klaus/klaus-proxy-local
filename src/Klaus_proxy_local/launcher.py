#!/usr/bin/env python3
"""Smart proxy launcher for Klaus Proxy Local (FASE 1.3).

Orchestrates:
- Auto-config generation (setup.py)
- Auto-cert generation (certs.py)
- mitmdump launch with addons
- Status dashboard

Usage:
  claude-proxy              # Start the proxy (entry point in pyproject.toml)
"""
import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from Klaus_proxy_local import __version__, capture_retention, scan_repos
from Klaus_proxy_local.addons_snapshot import ADDON_FILES, snapshot_addons
from Klaus_proxy_local.certs import (
    ensure_mitmproxy_certs,
    generate_env_vars_file,
    generate_mitmproxy_certs,
    mitm_executable,
    mitmproxy_cert_dir,
    mitmproxy_cert_file,
)
from Klaus_proxy_local.setup import (
    init_config_if_missing,
    remember_projects_root,
    remember_repo_tokens,
)


class ProxyLauncher:
    """Smart proxy launcher with auto-setup orchestration."""

    HOST = "127.0.0.1"
    PORT = 8899

    def __init__(self) -> None:
        """Initialize launcher."""
        self.config = None
        self.cert_file = None
        self.mitmdump_process = None
        self.protected_tokens: list[str] = []
        self.pattern_count = 0
        self.addons_info: dict = {}

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
                raise RuntimeError(f"❌ Failed to generate certificates at {cert_file}")

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
                    print("✅ Exported ANTHROPIC_PSEUDO_SALT from config\n")
        except Exception as e:
            raise RuntimeError(f"❌ Config setup failed: {e}")

        # Step 1b: Remember org/repo of the current repo, so they stay protected
        # even if the proxy is later started from elsewhere (#61)
        added, self.protected_tokens = remember_repo_tokens()
        if added:
            print(f"✅ Org/repo added to protected list: {', '.join(added)}\n")

        # Step 1c: Protect the names of every sibling project directory (#42)
        root, self.pattern_count = remember_projects_root()
        if root:
            print(f"✅ Project names under {root}/ are now pseudonymized\n")

        # Step 1d: Protect org/repo of every repo in the projects folder (#134)
        self.protect_project_repos()

        # Step 1e: Drop captures older than capture_retention_days (#132)
        self.apply_capture_retention()

        # Step 2: Auto-regenerate or ensure certs
        try:
            self.regenerate_certs_if_needed()
            self.cert_file = ensure_mitmproxy_certs()
            print("✅ Certificates ready")
            print(f"   Location: {self.cert_file}\n")

            # Step 2b: Generate environment variables file for SSL/TLS trust
            env_file = generate_env_vars_file(self.cert_file)
            print("✅ Environment variables file generated")
            print(f"   Location: {env_file}\n")
        except RuntimeError as e:
            raise RuntimeError(f"❌ Cert setup failed: {e}")

    def protect_project_repos(self) -> None:
        """Protege el org/repo de todos los repos de la carpeta de proyectos (#134).

        Solo muestra recuentos. Un fallo no impide arrancar: el resto de
        protecciones sigue en pie.
        """
        try:
            lines = scan_repos.scan_and_protect()
        except Exception as e:  # noqa: BLE001 - exploración best-effort
            print(f"⚠️  Exploración de repos no aplicada: {type(e).__name__}: {e}\n")
            return
        print("\n".join(lines) + "\n")
        self.protected_tokens = scan_repos.load_config().get(
            "pseudo_word_literals", self.protected_tokens
        )

    def apply_capture_retention(self) -> None:
        """Borra los pares de capturas más antiguos que la retención (#132).

        Un fallo de disco no impide arrancar: la retención es mantenimiento.
        """
        config = self.config or {}
        try:
            summary = capture_retention.prune_captures(
                capture_retention.captures_dir(config),
                capture_retention.retention_days(config),
            )
        except OSError as e:
            print(f"⚠️  Retención de capturas no aplicada: {e}\n")
            return
        print(capture_retention.describe(summary) + "\n")

    def show_dashboard(self) -> None:
        """Show startup dashboard."""
        env_file = Path.home() / ".klaus-proxy" / "klaus-env.sh"
        print("")
        print("╔" + "═" * 68 + "╗")
        print(
            f"║ 🔐 Klaus Proxy Local v{__version__} — Running                              ║"
        )
        print("╚" + "═" * 68 + "╝")
        print("")
        print(f"🎯 Listening on:          {self.HOST}:{self.PORT}")
        print("📁 Config:                ~/.klaus-proxy/config.json")
        print("📋 Captures:              ~/.klaus-proxy/captures/")
        print("📝 Logs:                  ~/.klaus-proxy/logs/proxy.log")
        if self.protected_tokens:
            # Solo el recuento: los nombres son justo lo que se protege (#134)
            print(
                f"🛡️  Protected org/repo:    {len(self.protected_tokens)} "
                "tokens (pseudo_word_literals)"
            )
        else:
            print(
                "\033[33m⚠️  Protected org/repo:    NONE — start claude-proxy once "
                "inside each repo\n   (or add them to pseudo_word_literals in "
                "~/.klaus-proxy/config.json)\033[0m"
            )
        if self.pattern_count:
            print(f"🗂️  pseudo_patterns:       {self.pattern_count} active")
        print(f"🔒 Certificate:           {self.cert_file}")
        print("✅ Auto-configuration:    ALL CERTIFICATES + ENV VARS SET")
        print("")
        print("📖 USAGE (NO configuration needed):")
        print("  Terminal 1 (keep this running):")
        print("    $ claude-proxy")
        print("")
        print("  Terminal 2 (new terminal):")
        print("    $ source ~/.klaus-proxy/klaus-env.sh")
        print(f"    $ export HTTPS_PROXY=http://{self.HOST}:{self.PORT}")
        print("    $ claude 'your question'")
        print("")
        print("🔐 TLS Certificate Trust:  AUTOMATIC")
        print(f"   SSL/TLS vars → {env_file}")
        print("")
        print("🛑 To stop: Press Ctrl+C")
        print("╔" + "═" * 68 + "╗")
        print("║ Ready. Use another terminal to run 'claude' with the proxy.      ║")
        print("╚" + "═" * 68 + "╝")
        print("")

    def launch_mitmdump(self) -> None:
        """Launch mitmdump with pseudonymization and capture addons.

        Client trust (NODE_EXTRA_CA_CERTS & co.) is not set here: clients get
        it by sourcing ~/.klaus-proxy/klaus-env.sh (#51).

        Raises:
          RuntimeError: If mitmdump fails to start.
        """
        # Addons path (relative to project root)
        addons_dir = Path(__file__).resolve().parents[2] / "src"
        pseudonymize_addon = addons_dir / "anthropic_payload_pseudonymize.py"
        capture_addon = addons_dir / "anthropic_payload_capture.py"
        file_log_addon = addons_dir / "klaus_file_log.py"
        guard_addon = addons_dir / "klaus_pseudo_guard.py"

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
        if not file_log_addon.exists():
            raise RuntimeError(
                f"❌ File log addon not found: {file_log_addon}\n"
                f"   Make sure Klaus Proxy is installed in development mode: pip install -e ."
            )
        if not guard_addon.exists():
            raise RuntimeError(
                f"❌ Guard addon not found: {guard_addon}\n"
                f"   Make sure Klaus Proxy is installed in development mode: pip install -e ."
            )

        # Run mitmdump from an immutable copy: mitmproxy hot-reloads -s scripts,
        # so loading them from the clone let checkouts swap (or break) the
        # pseudonymizer of a running proxy (#71)
        snapshot_dir, self.addons_info = snapshot_addons(addons_dir)
        addon_paths = [str(snapshot_dir / name) for name in ADDON_FILES]

        # Build mitmdump command
        # Addons must come BEFORE port, in ADDON_FILES order: file log first so
        # it is attached when the others log on load (#55), TLS passthrough for
        # non-API hosts (#105), pseudonymize (request rewrite), capture
        # (evidence), guard last (fail-closed, #71)
        # NOTE: No -q flag to show all logs with version prefix
        mitmdump_cmd = [mitm_executable("mitmdump")]
        for path in addon_paths:
            mitmdump_cmd += ["-s", path]
        mitmdump_cmd += [
            # Loopback only: without this mitmproxy binds every interface and
            # becomes an open proxy for the whole LAN (#47)
            "--listen-host",
            self.HOST,
            "-p",
            str(self.PORT),
        ]

        try:
            print(
                f"🧩 Addons: {self.addons_info.get('commit', '?')} "
                f"(snapshot {snapshot_dir})"
            )
            print("🚀 Starting mitmdump...")
            print(f"   Command: {' '.join(mitmdump_cmd)}\n")

            env = os.environ.copy()
            # Ensure ANTHROPIC_PSEUDO_SALT is set (from config or env)
            if "ANTHROPIC_PSEUDO_SALT" in os.environ:
                env["ANTHROPIC_PSEUDO_SALT"] = os.environ["ANTHROPIC_PSEUDO_SALT"]
            # Ensure ANTHROPIC_CAPTURE_DIR is set for the capture addon
            if "ANTHROPIC_CAPTURE_DIR" in os.environ:
                env["ANTHROPIC_CAPTURE_DIR"] = os.environ["ANTHROPIC_CAPTURE_DIR"]
            elif self.config and "capture_dir" in self.config:
                env["ANTHROPIC_CAPTURE_DIR"] = self.config["capture_dir"]
            else:
                env["ANTHROPIC_CAPTURE_DIR"] = str(
                    Path.home() / ".klaus-proxy" / "captures"
                )

            # Launch mitmdump without PIPE to preserve colors and enable fast Ctrl+C
            # mitmproxy inherits parent stdout/stderr → ANSI colors work natively
            # No log reader thread → no blocking on Ctrl+C
            self.mitmdump_process = subprocess.Popen(
                mitmdump_cmd,
                env=env,
            )

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
        """Turn SIGTERM into KeyboardInterrupt so run() does the shutdown.

        Never call shutdown() from here: the handler runs while the main
        thread is inside Popen.wait() holding its non-reentrant waitpid
        lock, and waiting again from the handler deadlocks (#51).
        """
        raise KeyboardInterrupt

    def shutdown(self) -> None:
        """Shutdown proxy cleanly and quickly."""
        if self.mitmdump_process:
            try:
                # Try gentle terminate first with short timeout
                self.mitmdump_process.terminate()
                try:
                    self.mitmdump_process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    # If still running, kill it forcefully
                    self.mitmdump_process.kill()
                    try:
                        self.mitmdump_process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        # Process will be cleaned up by OS
                        pass
            except Exception:
                # If anything goes wrong, just force kill
                try:
                    self.mitmdump_process.kill()
                except Exception:
                    pass

    def run(self) -> None:
        """Run the proxy (entry point).

        Orchestrates:
        1. Ensure prerequisites (config + certs)
        2. Show dashboard
        3. Launch mitmdump
        4. Keep running until Ctrl+C
        """
        # Before mitmdump starts, so an early SIGTERM can't orphan it.
        # SIGINT already raises KeyboardInterrupt.
        signal.signal(signal.SIGTERM, self.handle_signal)

        try:
            # Phase 1: Setup
            self.ensure_prerequisites()

            # Phase 2: Show status
            self.show_dashboard()

            # Phase 3: Launch proxy
            self.launch_mitmdump()

            # Phase 4: Keep running
            # Wait forever (until Ctrl+C)
            self.mitmdump_process.wait()

        except RuntimeError as e:
            print(f"{e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            # Ignore further signals during shutdown to prevent recursion
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            print("\n\n🛑 Stopping Klaus Proxy Local...")
            self.shutdown()
            print("✅ Proxy stopped")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            self.shutdown()
            sys.exit(1)


def main(argv=None) -> None:
    """Entry point for claude-proxy command."""
    parser = argparse.ArgumentParser(
        prog="claude-proxy",
        description="Klaus Proxy Local - Privacy-first proxy for Anthropic API",
        epilog="Examples:\n  claude-proxy              # Start the proxy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    parser.parse_args(argv)

    launcher = ProxyLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
