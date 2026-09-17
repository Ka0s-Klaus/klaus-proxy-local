"""Alerts panel showing detected leaks."""

from textual.widgets import Static
from textual.reactive import reactive


class AlertsPanel(Static):
    """Panel showing detected alerts/leaks."""

    detected_leaks: list = reactive([])

    def render(self) -> str:
        if not self.detected_leaks:
            return "No alerts"

        lines = ["⚠️  ALERTS:"]
        for leak in self.detected_leaks[-5:]:  # Show last 5
            lines.append(f"  • {leak}")

        return "\n".join(lines)
