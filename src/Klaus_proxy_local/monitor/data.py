"""DataSource for Klaus Monitor - polls captures and vault in real-time."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import threading
import time


@dataclass
class RequestInfo:
    """Single request metadata."""
    timestamp: datetime
    method: str
    path: str
    endpoint: str
    pseudonymized: bool
    blocked: bool
    host: str = "api.anthropic.com"


@dataclass
class ProxyStats:
    """Real-time proxy statistics."""
    total_requests: int = 0
    pseudonymized_count: int = 0
    blocked_count: int = 0
    vault_size: int = 0
    vault_types: Dict[str, int] = field(default_factory=dict)
    last_request_time: Optional[datetime] = None
    requests_last_minute: int = 0
    endpoint_counts: Dict[str, int] = field(default_factory=dict)
    detected_leaks: List[str] = field(default_factory=list)
    last_audit_time: Optional[datetime] = None
    last_audit_status: str = "unknown"
    uptime: timedelta = field(default_factory=timedelta)


class DataSource:
    """Polls captures/ and .pseudonym_vault.json for real-time metrics."""

    def __init__(self, captures_dir: Optional[str] = None):
        """Initialize data source.

        Args:
            captures_dir: Path to captures directory. If None, tries config.json, then falls back to "./captures"
        """
        self.captures_dir = self._resolve_captures_dir(captures_dir)
        self.sent_dir = Path(self.captures_dir) / "sent"
        self.original_dir = Path(self.captures_dir) / "original"
        self.vault_path = Path(self.captures_dir) / ".pseudonym_vault.json"

        self.stats = ProxyStats()
        self.request_history: List[RequestInfo] = []
        self.vault: Dict[str, str] = {}
        self.vault_mtime = 0.0
        self.last_seen_file_count = 0
        self.start_time = datetime.now()

        # Thread-safe access
        self._lock = threading.Lock()

    def _resolve_captures_dir(self, captures_dir: Optional[str]) -> str:
        """Resolve captures directory from config or defaults."""
        if captures_dir:
            return captures_dir

        # Try ~/.klaus-proxy/config.json
        config_path = Path.home() / ".klaus-proxy" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    if "capture_dir" in config:
                        return config["capture_dir"]
            except Exception:
                pass

        # Fallback to ./captures
        return str(Path.cwd() / "captures")

    def _load_vault(self) -> Dict[str, str]:
        """Load and cache vault from .pseudonym_vault.json."""
        if not self.vault_path.exists():
            return {}

        try:
            current_mtime = self.vault_path.stat().st_mtime
            if current_mtime != self.vault_mtime:
                with open(self.vault_path) as f:
                    self.vault = json.load(f)
                self.vault_mtime = current_mtime
        except Exception:
            pass

        return self.vault

    def _parse_request_file(self, file_path: Path) -> Optional[RequestInfo]:
        """Parse a single request JSON file."""
        try:
            with open(file_path) as f:
                data = json.load(f)

            timestamp = datetime.fromisoformat(data.get("captured_at", datetime.now().isoformat()))
            method = data.get("method", "UNKNOWN")
            path = data.get("path", "/unknown")
            pseudonymized = data.get("pseudonymized", False)
            blocked = data.get("blocked", False)
            host = data.get("host", "api.anthropic.com")

            # Shorten path for display
            endpoint = path[:30] + "..." if len(path) > 30 else path

            return RequestInfo(
                timestamp=timestamp,
                method=method,
                path=path,
                endpoint=endpoint,
                pseudonymized=pseudonymized,
                blocked=blocked,
                host=host,
            )
        except Exception:
            return None

    def _detect_leaks(self, sent_file: Path) -> List[str]:
        """Detect potential leaks in a sent request."""
        leaks = []
        try:
            with open(sent_file) as f:
                content = f.read()

            # Simple heuristic: look for email/api_key patterns not in vault
            vault_keys = set(self.vault.keys())

            # Look for email pattern
            import re
            emails = re.findall(r'[\w\.-]+@[\w\.-]+', content)
            for email in emails:
                if email not in vault_keys and not email.startswith(("noreply@", "test@", "example@")):
                    leaks.append(f"email: {email}")

            # Look for sk_ pattern (API keys)
            api_keys = re.findall(r'sk_[a-zA-Z0-9_]{20,}', content)
            for key in api_keys:
                if key not in vault_keys:
                    leaks.append(f"api_key: {key[:20]}...")
        except Exception:
            pass

        return leaks

    def poll(self) -> ProxyStats:
        """Poll captures/ and vault; return updated stats."""
        with self._lock:
            # Reload vault
            self._load_vault()

            # Ensure directories exist
            if not self.sent_dir.exists():
                self.sent_dir.mkdir(parents=True, exist_ok=True)

            # Count files and process new ones
            sent_files = sorted(self.sent_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            current_file_count = len(sent_files)

            # Only process new files
            new_files = sent_files[:max(0, current_file_count - self.last_seen_file_count)]

            for file_path in new_files:
                req = self._parse_request_file(file_path)
                if req:
                    self.request_history.append(req)
                    self.stats.total_requests += 1
                    self.stats.last_request_time = req.timestamp

                    if req.pseudonymized:
                        self.stats.pseudonymized_count += 1
                    if req.blocked:
                        self.stats.blocked_count += 1

                    # Track endpoint counts
                    self.stats.endpoint_counts[req.endpoint] = self.stats.endpoint_counts.get(req.endpoint, 0) + 1

                    # Check for leaks
                    leaks = self._detect_leaks(file_path)
                    if leaks:
                        self.stats.detected_leaks.extend(leaks)

            self.last_seen_file_count = current_file_count

            # Update vault stats
            self.stats.vault_size = len(self.vault)
            self._update_vault_types()

            # Calculate requests in last minute
            now = datetime.now()
            one_minute_ago = now - timedelta(minutes=1)
            self.stats.requests_last_minute = sum(
                1 for r in self.request_history
                if r.timestamp >= one_minute_ago
            )

            # Keep only last 500 requests in history
            if len(self.request_history) > 500:
                self.request_history = self.request_history[-500:]

            # Update uptime
            self.stats.uptime = datetime.now() - self.start_time

            return self.stats

    def _update_vault_types(self):
        """Analyze vault and count by prefix type."""
        self.stats.vault_types.clear()
        for real_val, pseudo_val in self.vault.items():
            # Extract prefix from pseudonym
            if "_" in pseudo_val:
                prefix = pseudo_val.split("_")[0]
            else:
                prefix = pseudo_val[:5]

            self.stats.vault_types[prefix] = self.stats.vault_types.get(prefix, 0) + 1

    def get_recent_requests(self, limit: int = 50) -> List[RequestInfo]:
        """Get most recent requests."""
        with self._lock:
            return self.request_history[-limit:][::-1]

    def get_stats(self) -> ProxyStats:
        """Get current stats snapshot."""
        with self._lock:
            return self.stats
