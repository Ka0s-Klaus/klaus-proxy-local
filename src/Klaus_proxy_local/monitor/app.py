"""Klaus Monitor TUI Application - Main Textual App."""

import subprocess
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult, App
from textual.containers import Grid
from textual.widgets import Footer, Static
from textual.binding import Binding

from .data import DataSource
from .panels.header import HeaderPanel
from .panels.stats import StatsPanel
from .panels.traffic import TrafficPanel
from .panels.vault import VaultPanel
from .panels.audit import AuditPanel
from .panels.alerts import AlertsPanel


class KlausMonitorApp(App):
    """Klaus Monitor TUI Application - htop-style monitoring."""

    BINDINGS = [
        Binding("a", "run_audit", "Audit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
        ("?", "show_help", "Help"),
    ]

    TITLE = "Klaus Monitor v0.4.0"
    SUB_TITLE = "Real-time proxy and audit monitoring"

    CSS = """
    Screen {
        background: $surface;
    }

    #header-panel {
        height: 2;
        dock: top;
        border: solid $primary;
        padding: 0 1;
    }

    #main-grid {
        layout: grid;
        grid-size: 3 3;
        grid-rows: 1fr 1fr 1fr;
        grid-columns: 1fr 2fr 1fr;
        height: 1fr;
    }

    #stats-panel {
        border: solid $primary;
        padding: 1 2;
    }

    #traffic-panel {
        border: solid $primary;
        padding: 1 2;
        row-span: 2;
    }

    #vault-panel {
        border: solid $primary;
        padding: 1 2;
        row-span: 2;
    }

    #audit-panel {
        border: solid $primary;
        padding: 1 2;
        column-span: 2;
    }

    #alerts-panel {
        border: solid $primary;
        padding: 1 2;
    }
    """

    def __init__(self, captures_dir: Optional[str] = None):
        super().__init__()
        self.data_source = DataSource(captures_dir)
        self.last_audit_check = datetime.now()

    def compose(self) -> ComposeResult:
        """Compose the layout."""
        yield HeaderPanel(id="header-panel")

        with Grid(id="main-grid"):
            yield StatsPanel(id="stats-panel")
            yield TrafficPanel(self.data_source, id="traffic-panel")
            yield VaultPanel(id="vault-panel")
            yield AuditPanel(id="audit-panel")
            yield AlertsPanel(id="alerts-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize and start polling."""
        # Set panel titles
        try:
            self.query_one("#header-panel", HeaderPanel).border_title = "KLAUS MONITOR"
            self.query_one("#stats-panel", StatsPanel).border_title = "📊 STATS"
            self.query_one("#traffic-panel", TrafficPanel).border_title = "🔄 LIVE TRAFFIC"
            self.query_one("#vault-panel", VaultPanel).border_title = "🔐 VAULT"
            self.query_one("#audit-panel", AuditPanel).border_title = "📋 AUDIT"
            self.query_one("#alerts-panel", AlertsPanel).border_title = "⚠️  ALERTS"
        except Exception as e:
            print(f"Error setting titles: {e}")

        # Initial poll to load data
        self.update_stats()

        # Start polling every 0.8 seconds
        self.set_interval(0.8, self.update_stats)

    def update_stats(self) -> None:
        """Update all panels from data source."""
        try:
            # Poll data source
            stats = self.data_source.poll()

            # Update header
            header = self.query_one("#header-panel", HeaderPanel)
            header.uptime = stats.uptime

            # Update stats panel
            stats_panel = self.query_one("#stats-panel", StatsPanel)
            stats_panel.stats = stats

            # Update vault panel
            vault_panel = self.query_one("#vault-panel", VaultPanel)
            vault_panel.stats = stats

            # Update audit panel
            audit_panel = self.query_one("#audit-panel", AuditPanel)
            audit_panel.last_audit_status = stats.last_audit_status
            audit_panel.last_audit_time = stats.last_audit_time

            # Update alerts panel
            alerts_panel = self.query_one("#alerts-panel", AlertsPanel)
            alerts_panel.detected_leaks = stats.detected_leaks

        except Exception as e:
            # Silently fail - don't crash the UI
            pass

    def action_run_audit(self) -> None:
        """Run audit in background."""
        self.notify("Running audit...", timeout=2)
        try:
            result = subprocess.run(
                ["python3", "full_audit_with_fixes.py", "--no-fix"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                self.data_source.stats.last_audit_status = "ok"
                self.data_source.stats.last_audit_time = datetime.now()
                self.notify("✅ Audit completed - No leaks detected", timeout=3)
            else:
                if "FUGA" in result.stdout or "leak" in result.stdout.lower():
                    self.data_source.stats.last_audit_status = "leaks"
                    self.notify("⚠️  Audit found leaks", timeout=3)
                else:
                    self.data_source.stats.last_audit_status = "unknown"
                    self.notify("Audit completed", timeout=3)
        except subprocess.TimeoutExpired:
            self.notify("Audit timeout", timeout=3)
        except Exception as e:
            self.notify(f"Audit error: {e}", timeout=3)

    def action_refresh(self) -> None:
        """Force refresh."""
        self.update_stats()
        self.notify("Refreshed", timeout=1)

    def action_show_help(self) -> None:
        """Show help information."""
        help_text = """Klaus Monitor - htop-style TUI

[a]=Audit [r]=Refresh [q]=Quit [?]=Help"""
        self.notify(help_text, timeout=5)
