"""Traffic panel showing live requests."""

from textual.widgets import Static, RichLog
from rich.text import Text
from ..data import DataSource


class TrafficPanel(Static):
    """Panel showing live request traffic."""

    def __init__(self, data_source: DataSource, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_source = data_source

    def render(self) -> str:
        requests = self.data_source.get_recent_requests(limit=15)

        lines = []
        for req in requests:
            time_str = req.timestamp.strftime("%H:%M:%S")
            method_str = f"{req.method:4}"
            endpoint_str = req.endpoint[:30].ljust(30)

            # Status indicator
            if req.blocked:
                status = "❌"
            elif req.pseudonymized:
                status = "✅"
            else:
                status = "—"

            line = f"{time_str} {method_str} {endpoint_str} {status}"
            lines.append(line)

        return "\n".join(lines) if lines else "Waiting for requests..."
