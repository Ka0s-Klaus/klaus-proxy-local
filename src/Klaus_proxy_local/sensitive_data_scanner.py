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
import sys
import math


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


# --- Tier 2: Contextual Detection ---


class ContextualAnalyzer:
    """Detects sensitive data by analyzing variable names and context."""

    # High-confidence secret variable names
    SECRET_VAR_NAMES = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "apikey",
        "api_key",
        "api-key",
        "key",
        "credential",
        "credentials",
        "auth",
        "authtoken",
        "access_token",
        "refresh_token",
        "session_token",
        "jwt",
        "bearer",
        "client_secret",
        "client_id",
        "app_secret",
        "app_id",
        "private_key",
        "rsa_key",
        "ssh_key",
        "gpg_key",
        "encryption_key",
        "decrypt_key",
        "db_password",
        "db_user",
        "db_host",
        "database_url",
        "connection_string",
        "aws_secret_access_key",
        "aws_access_key_id",
        "aws_session_token",
        "github_token",
        "gitlab_token",
        "bitbucket_token",
        "slack_token",
        "slack_webhook",
        "discord_webhook",
        "stripe_key",
        "openai_key",
        "anthropic_key",
    }

    @staticmethod
    def analyze_line(line: str) -> list[tuple[str, str]]:
        """Find potential secrets by variable name context.

        Returns: [(value, var_name)]
        """
        findings = []

        for var_name in ContextualAnalyzer.SECRET_VAR_NAMES:
            # Case-insensitive match with word boundary
            pattern = r"(?<![a-zA-Z0-9_])" + re.escape(var_name) + r"(?![a-zA-Z0-9_])"
            if not re.search(pattern, line, re.IGNORECASE):
                continue

            # Try to extract value (various assignment formats)
            # Format 1: var = "value"
            match = re.search(
                r"(?<![a-zA-Z0-9_])"
                + re.escape(var_name)
                + r"(?![a-zA-Z0-9_])\s*[:=]\s*[\"']([^\"']{4,})[\"']",
                line,
                re.IGNORECASE,
            )
            if match:
                findings.append((match.group(1), var_name))
                continue

            # Format 2: var=value (no spaces)
            match = re.search(
                r"(?<![a-zA-Z0-9_])"
                + re.escape(var_name)
                + r"(?![a-zA-Z0-9_])=([^\s\"']+)",
                line,
                re.IGNORECASE,
            )
            if match:
                value = match.group(1).rstrip(",;)")
                if len(value) >= 4:
                    findings.append((value, var_name))
                continue

            # Format 3: "var": "value" (JSON)
            match = re.search(
                r'["\']'
                + re.escape(var_name)
                + r'["\']\\s*:\\s*["\']([^"\']{4,})["\']',
                line,
                re.IGNORECASE,
            )
            if match:
                findings.append((match.group(1), var_name))

        return findings


class FileContextAnalyzer:
    """Analyzes file type and location for secret indicators."""

    # Files almost certainly containing secrets
    HIGH_RISK_FILENAMES = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".env.secret",
        ".env.private",
        "secret.yaml",
        "secret.yml",
        "secrets.json",
        "credentials.json",
        ".credentials",
        ".netrc",
        "config.production.json",
        "config.prod.json",
        ".aws/credentials",
        ".ssh/config",
        ".ssh/authorized_keys",
        ".docker/config.json",
        ".kube/config",
        "terraform.tfvars",
        "terraform.tfvars.json",
        "ansible-vault",
        ".vault-pass",
        ".private-key",
        ".pem",
        ".key",
    }

    # File extensions commonly containing secrets
    HIGH_RISK_EXTENSIONS = {
        ".env",
        ".key",
        ".pem",
        ".p8",
        ".p12",
        ".pfx",
        ".jks",
        ".keystore",
        ".privkey",
    }

    @staticmethod
    def file_risk_level(file_path: Path) -> str:
        """Estimate how likely this file is to contain secrets.

        Returns: "critical", "high", "medium", "low"
        """
        filename = file_path.name

        # Check exact filename matches
        if filename in FileContextAnalyzer.HIGH_RISK_FILENAMES:
            return "critical"

        # Check extensions
        if file_path.suffix in FileContextAnalyzer.HIGH_RISK_EXTENSIONS:
            return "critical"

        # Check path contains high-risk directory names
        for parent in file_path.parents:
            if parent.name in {".env", ".secrets", ".credentials", ".aws", ".ssh", ".kube"}:
                return "high"

        # Config files: high scrutiny
        if file_path.suffix in {".yaml", ".yml", ".json", ".toml", ".ini", ".conf"}:
            return "high"

        # Code files: medium scrutiny
        if file_path.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".sh", ".bash"}:
            return "medium"

        return "low"


class ContextDetector:
    """Tier 2: Contextual detection (variable names, file types)."""

    def __init__(self):
        self.contextual_analyzer = ContextualAnalyzer()
        self.file_analyzer = FileContextAnalyzer()

    def detect_in_line(self, line: str, file_path: Path, line_number: int) -> list[SensitiveDataFinding]:
        """Detect by analyzing variable names and patterns."""
        findings = []
        for value, var_name in self.contextual_analyzer.analyze_line(line):
            finding = SensitiveDataFinding(
                value=value,
                category=f"secret-var-{var_name}",
                detection_method="contextual",
                confidence=Confidence.HIGH,
                file_path=file_path,
                line_number=line_number,
                context=line[:120],
                reason=f"Variable name suggests secret: {var_name}",
            )
            findings.append(finding)
        return findings

    def detect_by_file_type(
        self, file_path: Path
    ) -> Optional[SensitiveDataFinding]:
        """Warn if file is high-risk (may contain secrets)."""
        risk = self.file_analyzer.file_risk_level(file_path)
        if risk in ("critical", "high"):
            return SensitiveDataFinding(
                value=str(file_path),
                category="high-risk-file",
                detection_method="contextual",
                confidence=Confidence.MEDIUM,
                file_path=file_path,
                line_number=0,
                context=f"File: {file_path.name}",
                reason=f"High-risk file type/location ({risk}). May contain secrets.",
            )
        return None


# --- Tier 2: Vault Integration ---


def _import_vault():
    """Lazy import of Vault from pseudonymizer to avoid circular deps."""
    try:
        import sys
        from pathlib import Path

        # Add src directory to path
        src_path = Path(__file__).resolve().parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from anthropic_payload_pseudonymize import Vault

        return Vault
    except ImportError:
        return None


class VaultIntegration:
    """Integrates scanner findings with Vault for pseudonymization."""

    def __init__(self):
        self.Vault = _import_vault()
        self._vault = None

    def get_vault(self):
        """Load or create vault (lazy loading)."""
        if self._vault is None:
            if self.Vault is None:
                raise RuntimeError(
                    "Cannot import Vault class. Ensure pseudonymizer is available."
                )
            self._vault = self.Vault.load()
        return self._vault

    def add_finding_to_vault(
        self, finding: SensitiveDataFinding, prefix: str = "secret"
    ) -> str:
        """Add a finding to the vault as a reversible entry.

        Args:
            finding: The finding to add
            prefix: Prefix for pseudonym (e.g., "secret", "credential", "api-key")

        Returns:
            The generated pseudonym
        """
        vault = self.get_vault()
        pseudo = vault.map(finding.value, prefix)
        vault.save()
        return pseudo

    def check_already_in_vault(self, value: str) -> Optional[str]:
        """Check if a value is already in the vault.

        Returns:
            The pseudonym if found, None otherwise
        """
        vault = self.get_vault()
        return vault.real_to_pseudo.get(value)

    def save_vault(self) -> Path:
        """Explicitly save vault to disk.

        Returns:
            Path to vault file
        """
        vault = self.get_vault()
        return vault.save()


# --- Tier 3: Heuristic Detection (Entropy & Diversity) ---


class EntropyAnalyzer:
    """Detects potential secrets using Shannon entropy analysis."""

    # Entropy thresholds (bits per character)
    ENTROPY_THRESHOLDS = {
        "low": 3.5,      # Normal English text
        "medium": 4.5,   # Could be secret
        "high": 5.5,     # Very likely secret
    }

    @staticmethod
    def shannon_entropy(text: str) -> float:
        """Calculate Shannon entropy of text (bits/char).

        Higher entropy = more random = likely secret.
        Normal text: 3-4 bits/char
        Random secrets: 5-6 bits/char
        """
        if not text:
            return 0.0

        from collections import Counter

        freq = Counter(text)
        entropy = 0.0
        for count in freq.values():
            p = count / len(text)
            entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def classify_entropy(text: str) -> tuple[str, float]:
        """Classify string by entropy level.

        Returns: (level, entropy_value)
        """
        entropy = EntropyAnalyzer.shannon_entropy(text)

        # Adjust for length: longer high-entropy strings are more suspicious
        length_factor = min(1.0, len(text) / 20)
        adjusted_entropy = entropy * length_factor

        if adjusted_entropy >= EntropyAnalyzer.ENTROPY_THRESHOLDS["high"]:
            return "high", adjusted_entropy
        elif adjusted_entropy >= EntropyAnalyzer.ENTROPY_THRESHOLDS["medium"]:
            return "medium", adjusted_entropy
        else:
            return "low", adjusted_entropy


class CharacterDiversityAnalyzer:
    """Analyzes character set diversity (suggests secret if mixed)."""

    @staticmethod
    def analyze_charset(text: str) -> tuple[float, str]:
        """Analyze character set diversity.

        Returns: (diversity_score, charset_type)
        - diversity_score: 0-1, higher = more diverse
        - charset_type: 'alphanumeric', 'mixed', 'high-entropy'
        """
        has_lower = any(c.islower() for c in text)
        has_upper = any(c.isupper() for c in text)
        has_digit = any(c.isdigit() for c in text)
        has_symbol = any(c in "!@#$%^&*()_-+=[]{}|;:,./<>?~`\\\"'" for c in text)

        charset_count = sum([has_lower, has_upper, has_digit, has_symbol])
        diversity = charset_count / 4.0

        if has_symbol and (has_lower or has_upper) and has_digit:
            charset_type = "high-entropy"
        elif charset_count >= 3:
            charset_type = "mixed"
        else:
            charset_type = "alphanumeric"

        return diversity, charset_type


class HeuristicDetector:
    """Tier 3: Heuristic detection (entropy + diversity)."""

    # Length heuristics
    MIN_SECRET_LENGTH = 8  # Secrets usually >= 8 chars
    MAX_SECRET_LENGTH = 64  # Secrets usually <= 64 chars

    def __init__(self):
        self.entropy_analyzer = EntropyAnalyzer()
        self.diversity_analyzer = CharacterDiversityAnalyzer()

    def detect_suspicious_strings(
        self, line: str, file_path: Path, line_number: int
    ) -> list[SensitiveDataFinding]:
        """Detect suspicious strings by entropy + diversity + length.

        Returns findings with MEDIUM/LOW confidence based on heuristics.
        """
        findings = []

        # Split into tokens (heuristic: anything 8-64 chars)
        import re

        tokens = re.findall(r"\S{8,64}", line)

        for token in tokens:
            # Skip common false positives
            if self._is_likely_false_positive(token):
                continue

            # Analyze entropy
            entropy_level, entropy_val = self.entropy_analyzer.classify_entropy(token)

            # Analyze diversity
            diversity, charset = self.diversity_analyzer.analyze_charset(token)

            # Confidence scoring
            # Both high entropy AND high diversity = strong signal
            if (
                entropy_level in ("high", "medium")
                and diversity >= 0.75
                and charset in ("high-entropy", "mixed")
            ):
                confidence = (
                    Confidence.MEDIUM
                    if entropy_level == "high"
                    else Confidence.LOW
                )

                finding = SensitiveDataFinding(
                    value=token,
                    category="suspicious-string",
                    detection_method="entropy",
                    confidence=confidence,
                    file_path=file_path,
                    line_number=line_number,
                    context=line[:120],
                    reason=f"High entropy ({entropy_val:.2f}) + diverse charset ({charset}) + length ({len(token)})",
                )
                findings.append(finding)

        return findings

    @staticmethod
    def _is_likely_false_positive(token: str) -> bool:
        """Detect tokens that are likely false positives."""
        # Skip URLs
        if token.startswith("http"):
            return True
        if "://" in token:
            return True

        # Skip common valid tokens
        if token.startswith("v") and all(
            c.isdigit() or c == "." for c in token[1:]
        ):
            return True  # Version numbers like v1.2.3

        # Skip UUIDs
        if token.count("-") == 4:  # UUID pattern
            return True

        # Skip hex strings (not necessarily secrets)
        if all(c in "0123456789abcdefABCDEF" for c in token):
            return True

        # Skip base64 strings (harder to distinguish)
        if len(token) < 16:
            return True  # Too short to be reliable secret

        return False


# --- Main Scanner ---


class SensitiveDataScanner:
    """Main scanner orchestrating all detection methods."""

    def __init__(
        self,
        enable_contextual: bool = True,
        enable_heuristic: bool = False,
        enable_vault_integration: bool = True,
        custom_patterns: dict[str, tuple[re.Pattern, str, str]] | None = None,
    ):
        """Initialize scanner with detection tiers.

        Args:
            enable_contextual: Enable Tier 2 (contextual detection) — default True
            enable_heuristic: Enable Tier 3 (entropy-based detection) — default False
            enable_vault_integration: Enable Vault integration (requires pseudonymizer)
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
        self.context_detector = ContextDetector() if enable_contextual else None
        self.heuristic_detector = HeuristicDetector() if enable_heuristic else None
        self.vault_integration = (
            VaultIntegration() if enable_vault_integration else None
        )

    def scan_file(self, file_path: Path) -> list[SensitiveDataFinding]:
        """Scan a single file for sensitive data."""
        findings = []

        try:
            # Check file risk level (Tier 2)
            if self.context_detector:
                file_warning = self.context_detector.detect_by_file_type(file_path)
                if file_warning:
                    findings.append(file_warning)

            # Read file
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return findings

            # Scan line by line
            for line_number, line in enumerate(content.split("\n"), 1):
                if not line.strip():
                    continue

                # Tier 1: Pattern detection (always enabled)
                tier1_findings = self.pattern_detector.detect(line, file_path, line_number)
                findings.extend(tier1_findings)

                # Tier 2: Contextual detection (high-risk files)
                if self.context_detector and self.context_detector.file_analyzer.file_risk_level(file_path) in ("critical", "high"):
                    tier2_findings = self.context_detector.detect_in_line(
                        line, file_path, line_number
                    )
                    findings.extend(tier2_findings)

                # Tier 3: Heuristic detection (entropy + diversity)
                # Only on high-risk files to reduce false positives
                if self.heuristic_detector and self.context_detector and self.context_detector.file_analyzer.file_risk_level(file_path) in ("critical", "high"):
                    tier3_findings = self.heuristic_detector.detect_suspicious_strings(
                        line, file_path, line_number
                    )
                    findings.extend(tier3_findings)

                # Skip already-in-vault items (if vault integration enabled)
                if self.vault_integration:
                    findings = [
                        f
                        for f in findings
                        if not self.vault_integration.check_already_in_vault(f.value)
                    ]

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
