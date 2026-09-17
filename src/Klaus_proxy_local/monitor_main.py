"""Entry point for standalone Klaus Monitor (without proxy)."""

import sys
from .monitor.app import KlausMonitorApp


def main():
    """Run Klaus Monitor TUI standalone."""
    app = KlausMonitorApp()
    app.run()


if __name__ == "__main__":
    main()
