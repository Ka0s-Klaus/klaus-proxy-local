"""Alerts panel showing detected leaks."""

from textual.widgets import Static
from textual.reactive import reactive


class AlertsPanel(Static):
    """Panel showing detected alerts/leaks."""

    detected_leaks: list = reactive([], recompose=True)

    def render(self) -> str:
        if not self.detected_leaks:
            return "OK - No alerts"

        lines = ["ALERTS:"]
        for leak in self.detected_leaks[-3:]:
            leak_short = str(leak)[:35]
            lines.append(f"  {leak_short}")

        return "\n".join(lines)
