"""Vault coverage panel."""

from textual.widgets import Static
from textual.reactive import reactive
from ..data import ProxyStats


class VaultPanel(Static):
    """Panel showing vault coverage by type."""

    stats: ProxyStats = reactive(ProxyStats(), recompose=True)

    def render(self) -> str:
        if not self.stats or not self.stats.vault_types:
            return "Loading vault..."

        lines = []

        sorted_types = sorted(
            self.stats.vault_types.items(),
            key=lambda x: x[1],
            reverse=True
        )[:6]

        max_count = max((c for _, c in sorted_types), default=1)

        for type_name, count in sorted_types:
            bar_width = 12
            filled = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = "#" * filled + "-" * (bar_width - filled)
            pct = (count / self.stats.vault_size * 100) if self.stats.vault_size > 0 else 0
            line = f"{type_name:10} {count:>3} [{bar}] {pct:>5.1f}%"
            lines.append(line)

        lines.append("-" * 40)
        lines.append(f"{'Total':10} {self.stats.vault_size:>3}")

        return "\n".join(lines)
