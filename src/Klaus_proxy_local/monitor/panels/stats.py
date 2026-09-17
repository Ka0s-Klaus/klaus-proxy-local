"""Stats panel showing key metrics."""

from textual.widgets import Static
from textual.reactive import reactive
from ..data import ProxyStats


class StatsPanel(Static):
    """Panel showing key statistics."""

    stats: ProxyStats = reactive(ProxyStats(), recompose=True)

    def render(self) -> str:
        if not self.stats:
            return "Loading..."

        lines = [
            f"Requests:  {self.stats.total_requests:>6,d}",
            f"Pseudonym: {self.stats.pseudonymized_count:>6,d}",
            f"Blocked:   {self.stats.blocked_count:>6,d}",
            f"Vault:     {self.stats.vault_size:>6,d}",
            f"Leaks:     {len(self.stats.detected_leaks):>6,d}",
            f"Req/min:   {self.stats.requests_last_minute:>6,d}",
        ]
        return "\n".join(lines)
