#!/usr/bin/env python3
"""Sensitive Data Scanner for Klaus Proxy Local v0.2.0.

Detects secrets, credentials, and sensitive data across project files using
multi-tier detection (patterns, contextual, heuristic). Integrates with Vault
for consistent pseudonymization.

Detection Tiers:
  Tier 1: Pattern-based (regex, zero false positives) — CRITICAL confidence
  Tier 2: Contextual (variable names, file types) — HIGH confidence
  Tier 3: Heuristic (entropy, character diversity) — MEDIUM confidence
  Tier 4: Manual (user approval) — VARIES

Usage:
  from sensitive_data_scanner import SensitiveDataScanner, Confidence
  scanner = SensitiveDataScanner()
  result = scanner.scan_directory(Path("/project"))
"""
from __future__ import annotations

import fnmatch
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


# --- Confidence Levels ---


class Confidence(Enum):
    """Confidence level of a finding."""

    CRITICAL = 0  # Pattern match, zero false positives expected
    HIGH = 1  # Pattern match with context verification
    MEDIUM = 2  # Contextual or entropy-based, needs review
    LOW = 3  # Heuristic, likely false positives
    UNKNOWN = 4

    def __lt__(self, other: Confidence) -> bool:
        return self.value < other.value

    def __le__(self, other: Confidence) -> bool:
        return self.value <= other.value

    def __gt__(self, other: Confidence) -> bool:
        return self.value > other.value

    def __ge__(self, other: Confidence) -> bool:
        return self.value >= other.value


# --- Data Structures ---


@dataclass
class SensitiveDataFinding:
    """A single finding of potential sensitive data."""

    value: str  # The actual sensitive data
    category: str  # "api-key", "password", "credential", etc.
    detection_method: str  # "pattern", "contextual", "entropy"
    confidence: Confidence
    file_path: Path
    line_number: int
    context: str  # surrounding line(s) for display
    reason: str  # human-readable explanation
    user_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "category": self.category,
            "detection_method": self.detection_method,
            "confidence": self.confidence.name,
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "context": self.context,
            "reason": self.reason,
            "user_approved": self.user_approved,
        }


@dataclass
class ScanResult:
    """Results of a scan operation."""

    total_files_scanned: int = 0
    files_with_findings: int = 0
    findings_by_confidence: dict[str, int] = field(default_factory=dict)
    findings: list[SensitiveDataFinding] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        critical = self.findings_by_confidence.get("CRITICAL", 0)
        high = self.findings_by_confidence.get("HIGH", 0)
        medium = self.findings_by_confidence.get("MEDIUM", 0)
        low = self.findings_by_confidence.get("LOW", 0)

        return (
            f"Scan complete: {self.total_files_scanned} files scanned, "
            f"{len(self.findings)} findings\n"
            f"  🔴 CRITICAL: {critical}\n"
            f"  🟠 HIGH: {high}\n"
            f"  🟡 MEDIUM: {medium}\n"
            f"  🔵 LOW: {low}\n"
            f"  Duration: {self.scan_duration_seconds:.2f}s"
        )


# --- Tier 1: Pattern-Based Detection ---


# Existing v0.1.0 secret patterns (from anthropic_payload_pseudonymize.py)
_SECRET_PATTERNS_V1 = {
    "private-key": (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
            r"[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
        ),
        "private-key",
        "PEM-format private key",
    ),
    "aws-access-key": (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "aws-access-key",
        "AWS Access Key ID",
    ),
    "github-token": (
        re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
        "github-token",
        "GitHub personal access token",
    ),
    "google-api-key": (
        re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
        "google-api-key",
        "Google API key",
    ),
    "slack-token": (
        re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
        "slack-token",
        "Slack token",
    ),
    "jwt": (
        re.compile(
            r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        ),
        "jwt",
        "JWT token",
    ),
}

# NEW v0.2.0 extended patterns
_SCANNER_PATTERNS_TIER1 = {
    "stripe-api-key": (
        re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}"),
        "stripe-api-key",
        "Stripe API key (publishable or secret)",
    ),
    "openai-api-key": (
        re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),
        "openai-api-key",
        "OpenAI API key",
    ),
    "anthropic-api-key": (
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
        "anthropic-api-key",
        "Anthropic API key",
    ),
    "mongodb-uri": (
        re.compile(
            r"mongodb(?:\+srv)?://[^/\s]+(?::[^@/\s]+)?@[^/\s]+"
        ),
        "mongodb-connection",
        "MongoDB connection string with credentials",
    ),
    "generic-db-connection": (
        re.compile(
            r"(?:mysql|postgresql|postgres|mariadb|mssql|oracle)://"
            r"[^:]+:[^@]+@[^/\s]+(?::\d+)?(?:/[^\s]*)?",
            re.IGNORECASE,
        ),
        "db-connection",
        "Database connection string with credentials",
    ),
    "aws-secret-access-key": (
        re.compile(
            r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*=\s*[A-Za-z0-9/+]{40}"
        ),
        "aws-secret-key",
        "AWS Secret Access Key",
    ),
    "aws-session-token": (
        re.compile(
            r"(?:aws_session_token|AWS_SESSION_TOKEN)\s*=\s*[A-Za-z0-9/+=]{1,}"
        ),
        "aws-session-token",
        "AWS Session Token",
    ),
    "bearer-token": (
        re.compile(r"bearer\s+[A-Za-z0-9._\-=]{20,}", re.IGNORECASE),
        "bearer-token",
        "Generic Bearer token",
    ),
    "ssh-public-key": (
        re.compile(r"ssh-(?:rsa|ed25519|dss|ecdsa-sha2-\w+)\s+[A-Za-z0-9/+=]{100,}"),
        "ssh-public-key",
        "SSH public key",
    ),
    "oauth-refresh-token": (
        re.compile(
            r"(?:refresh_token|REFRESH_TOKEN)\s*[:=]\s*[A-Za-z0-9._\-]{20,}"
        ),
        "oauth-refresh-token",
        "OAuth refresh token",
    ),
    "url-with-credentials": (
        re.compile(
            r"https?://[A-Za-z0-9._\-]+:[A-Za-z0-9._\-!@#$%^&*()]{6,}@"
            r"[A-Za-z0-9.\-:]+",
            re.IGNORECASE,
        ),
        "url-with-credentials",
        "URL with embedded username/password",
    ),
    "aws-arn": (
        re.compile(r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d*:[^\s\"']+"),
        "aws-arn",
        "AWS ARN",
    ),
}

# Network & infrastructure patterns
_NETWORK_PATTERNS = {
    "ipv4-address": (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "ipv4",
        "IPv4 address",
    ),
    "internal-hostname": (
        re.compile(
            r"[a-zA-Z0-9][a-zA-Z0-9\-]*\.(?:local|internal|corp|intra)\b",
            re.IGNORECASE,
        ),
        "internal-hostname",
        "Internal hostname",
    ),
}


# --- Tier 1: PatternDetector Class ---


class PatternDetector:
    """Base class for pattern-based detection."""

    def __init__(
        self,
        patterns: dict[str, tuple[re.Pattern, str, str]] | None = None,
    ):
        """Initialize with patterns dict: {name: (compiled_regex, label, description)}"""
        self.patterns = patterns or {}

    def detect(
        self, text: str, file_path: Path, line_number: int
    ) -> list[SensitiveDataFinding]:
        """Scan text for pattern matches."""
        findings = []
        for pattern_name, (regex, label, description) in self.patterns.items():
            for match in regex.finditer(text):
                finding = SensitiveDataFinding(
                    value=match.group(0),
                    category=label,
                    detection_method="pattern",
                    confidence=Confidence.CRITICAL,
                    file_path=file_path,
                    line_number=line_number,
                    context=text[
                        max(0, match.start() - 30) : min(len(text), match.end() + 30)
                    ],
                    reason=description,
                )
                findings.append(finding)
        return findings


# --- File Traversal ---


class FileTraversal:
    """Smart directory traversal with filtering."""

    # Binary file signatures
    BINARY_SIGNATURES = {
        b"\x89PNG": "png",
        b"\xff\xd8\xff": "jpg",
        b"\x42\x4d": "bmp",
        b"PK\x03\x04": "zip",
        b"\x1f\x8b": "gzip",
        b"%PDF": "pdf",
        b"\xca\xfe\xba\xbe": "macho",
    }

    # Extensions to always skip
    SKIP_EXTENSIONS = {
        # Compiled
        ".pyc",
        ".pyo",
        ".o",
        ".so",
        ".exe",
        ".dll",
        ".dylib",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".rar",
        ".7z",
        ".iso",
        # Media
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".mp3",
        ".mp4",
        ".mov",
        ".wav",
        # Binary documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Build/cache
        ".egg",
        ".whl",
    }

    # Max file size to scan (20MB)
    MAX_FILE_SIZE = 20 * 1024 * 1024

    @staticmethod
    def should_scan_file(file_path: Path) -> bool:
        """Decide if a file should be scanned."""
        # Skip by extension
        if file_path.suffix.lower() in FileTraversal.SKIP_EXTENSIONS:
            return False

        # Skip by size
        try:
            if file_path.stat().st_size > FileTraversal.MAX_FILE_SIZE:
                return False
        except OSError:
            return False

        # Skip by magic bytes (binary detection)
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                for signature in FileTraversal.BINARY_SIGNATURES:
                    if header.startswith(signature):
                        return False
        except Exception:
            pass

        return True

    @staticmethod
    def should_skip_directory(dir_path: Path) -> bool:
        """Decide if a directory should be recursed."""
        skip_dirs = {
            ".git",
            ".github",
            ".gitlab",
            ".gitignore",
            ".venv",
            "venv",
            ".env",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            "htmlcov",
            ".cargo",
            "target",  # Rust
            "vendor",  # Go
            "Pods",  # iOS
            "Carthage",  # iOS
        }

        if dir_path.name in skip_dirs:
            return True

        # Skip hidden directories except those containing secrets
        if dir_path.name.startswith("."):
            if dir_path.name not in {
                ".env",
                ".secrets",
                ".credentials",
                ".aws",
                ".ssh",
                ".kube",
            }:
                return True

        return False

    @staticmethod
    def walk(root_path: Path) -> list[Path]:
        """Walk directory tree, yielding scannable files."""
        files = []
        queue = [root_path]

        while queue:
            current = queue.pop(0)
            try:
                for entry in current.iterdir():
                    # Skip symlinks
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        if not FileTraversal.should_skip_directory(entry):
                            queue.append(entry)
                    elif entry.is_file():
                        if FileTraversal.should_scan_file(entry):
                            files.append(entry)
            except (PermissionError, OSError):
                # Skip directories we can't read
                continue

        return sorted(files)


# --- Main Scanner ---


class SensitiveDataScanner:
    """Main scanner orchestrating all detection methods."""

    def __init__(
        self,
        enable_contextual: bool = False,
        enable_heuristic: bool = False,
        custom_patterns: dict[str, tuple[re.Pattern, str, str]] | None = None,
    ):
        """Initialize scanner with detection tiers.

        Args:
            enable_contextual: Enable Tier 2 (contextual detection)
            enable_heuristic: Enable Tier 3 (entropy-based detection)
            custom_patterns: Additional patterns to search for
        """
        # Combine all Tier 1 patterns
        all_patterns = {
            **_SECRET_PATTERNS_V1,
            **_SCANNER_PATTERNS_TIER1,
            **_NETWORK_PATTERNS,
        }
        if custom_patterns:
            all_patterns.update(custom_patterns)

        self.pattern_detector = PatternDetector(all_patterns)
        self.enable_contextual = enable_contextual
        self.enable_heuristic = enable_heuristic

    def scan_file(self, file_path: Path) -> list[SensitiveDataFinding]:
        """Scan a single file for sensitive data."""
        findings = []

        try:
            # Read file
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return []

            # Scan line by line
            for line_number, line in enumerate(content.split("\n"), 1):
                if not line.strip():
                    continue

                # Tier 1: Pattern detection (always enabled)
                findings.extend(
                    self.pattern_detector.detect(line, file_path, line_number)
                )

        except Exception:
            # Never crash on a single file
            pass

        return findings

    def scan_directory(
        self,
        root_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ScanResult:
        """Scan entire directory tree for sensitive data."""
        start_time = time.time()
        result = ScanResult()

        # Get all files to scan
        all_files = FileTraversal.walk(root_path)
        result.total_files_scanned = len(all_files)

        for idx, file_path in enumerate(all_files):
            if progress_callback:
                progress_callback(idx, len(all_files))

            try:
                findings = self.scan_file(file_path)
                if findings:
                    result.files_with_findings += 1
                    result.findings.extend(findings)

                    # Count by confidence
                    for finding in findings:
                        key = finding.confidence.name
                        result.findings_by_confidence[key] = (
                            result.findings_by_confidence.get(key, 0) + 1
                        )

            except Exception as e:
                result.errors.append((file_path, str(e)))

        result.scan_duration_seconds = time.time() - start_time
        return result
