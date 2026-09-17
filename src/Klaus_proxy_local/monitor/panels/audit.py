"""Audit status panel."""

from datetime import datetime
from typing import Optional
from textual.widgets import Static
from textual.reactive import reactive


class AuditPanel(Static):
    """Panel showing last audit status."""

    last_audit_status: str = reactive("unknown")
    last_audit_time: Optional[datetime] = reactive(None)

    def render(self) -> str:
        if self.last_audit_time:
            time_str = self.last_audit_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Never"

        status_icon = "✅" if self.last_audit_status == "ok" else "⚠️" if self.last_audit_status == "leaks" else "❓"
        status_text = {
            "ok": "No CRITICAL leaks detected",
            "leaks": "LEAKS DETECTED - Review required",
            "unknown": "Not run yet"
        }.get(self.last_audit_status, "Unknown status")

        return f"{status_icon} {status_text}\nLast run: {time_str}\n\n[a] Run audit now"
