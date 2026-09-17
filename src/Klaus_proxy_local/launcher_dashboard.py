#!/usr/bin/env python3
"""Launcher para proxy + dashboard."""

import subprocess
import time
import sys
import os
import webbrowser
from pathlib import Path


def main():
    """Start proxy and dashboard."""
    print("🚀 Klaus Proxy Local v0.4.0")
    print("=" * 50)
    print("")

    # Ensure in correct directory
    os.chdir(Path(__file__).parent.parent.parent)

    try:
        print("📦 Starting services...")
        print("")

        # Start proxy
        print("🔌 Starting proxy on 127.0.0.1:8899...")
        proxy_proc = subprocess.Popen(
            [sys.executable, "-m", "Klaus_proxy_local.launcher"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # Wait for proxy to start
        time.sleep(3)

        # Start dashboard
        print("📊 Starting dashboard on http://localhost:9999...")
        dashboard_proc = subprocess.Popen(
            [sys.executable, "-m", "Klaus_proxy_local.dashboard_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        time.sleep(2)

        # Try to open browser
        try:
            webbrowser.open("http://localhost:9999")
            print("🌐 Opening browser...")
        except Exception:
            pass

        print("")
        print("=" * 50)
        print("✅ Klaus Proxy Local is running!")
        print("")
        print("📊 Dashboard:  http://localhost:9999")
        print("🔌 Proxy:      127.0.0.1:8899")
        print("")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        print("")

        # Wait for both processes
        proxy_proc.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping services...")
        proxy_proc.terminate()
        dashboard_proc.terminate()
        try:
            proxy_proc.wait(timeout=5)
            dashboard_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proxy_proc.kill()
            dashboard_proc.kill()
        print("✅ Stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
