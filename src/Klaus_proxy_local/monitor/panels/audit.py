"""Audit status panel."""

from datetime import datetime
from typing import Optional
from textual.widgets import Static
from textual.reactive import reactive


class AuditPanel(Static):
    """Panel showing last audit status."""

    last_audit_status: str = reactive("unknown", recompose=True)
    last_audit_time: Optional[datetime] = reactive(None, recompose=True)

    def render(self) -> str:
        if self.last_audit_time:
            time_str = self.last_audit_time.strftime("%H:%M:%S")
        else:
            time_str = "Never"

        if self.last_audit_status == "ok":
            status_icon = "OK"
            status_text = "No leaks detected"
        elif self.last_audit_status == "leaks":
            status_icon = "!!"
            status_text = "Leaks found!"
        else:
            status_icon = "??"
            status_text = "Not run yet"

        return f"[{status_icon}] {status_text}\nLast: {time_str}\n\nPress [a] to audit"
