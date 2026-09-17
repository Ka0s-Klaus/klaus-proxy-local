"""Header panel showing proxy status and uptime."""

from datetime import timedelta
from textual.widgets import Static
from textual.reactive import reactive


class HeaderPanel(Static):
    """Header showing proxy status and uptime."""

    proxy_status: str = reactive("RUNNING")
    uptime: timedelta = reactive(timedelta(0))

    def render(self) -> str:
        status_icon = "🟢" if self.proxy_status == "RUNNING" else "🔴"
        uptime_str = self._format_timedelta(self.uptime)
        return f"{status_icon} Proxy: {self.proxy_status:8}  Port: 8899  Uptime: {uptime_str}  Captures: captures/"

    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
