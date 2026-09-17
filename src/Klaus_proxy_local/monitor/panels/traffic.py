"""Traffic panel showing live requests."""

from textual.widgets import Static
from ..data import DataSource


class TrafficPanel(Static):
    """Panel showing live request traffic."""

    def __init__(self, data_source: DataSource, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_source = data_source

    def render(self) -> str:
        requests = self.data_source.get_recent_requests(limit=12)

        if not requests:
            return "Waiting for requests...\n\n(Send API calls\nvia proxy)"

        lines = []
        for req in requests:
            time_str = req.timestamp.strftime("%H:%M:%S")
            method_str = f"{req.method:4}"
            endpoint_short = req.endpoint[:25] if len(req.endpoint) > 25 else req.endpoint
            endpoint_str = endpoint_short.ljust(25)

            if req.blocked:
                status = "X"
            elif req.pseudonymized:
                status = "*"
            else:
                status = "-"

            line = f"{time_str} {method_str} {endpoint_str} [{status}]"
            lines.append(line)

        return "\n".join(lines)
