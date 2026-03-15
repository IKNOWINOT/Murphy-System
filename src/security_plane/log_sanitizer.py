"""PII detection and sanitization for the Murphy System logging pipeline."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
    """Categories of personally identifiable information."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    API_KEY = "api_key"
    PASSWORD = "password"
    AUTH_TOKEN = "auth_token"
    IP_ADDRESS = "ip_address"


@dataclass
class PIIPattern:
    """A regex-based PII detection rule."""

    pii_type: PIIType
    pattern: str
    replacement: str
    enabled: bool = True


@dataclass
class SanitizationResult:
    """Outcome of a sanitization pass."""

    original_length: int
    sanitized_length: int
    detections: Dict[str, int]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_length": self.original_length,
            "sanitized_length": self.sanitized_length,
            "detections": dict(self.detections),
            "timestamp": self.timestamp.isoformat(),
        }


# ── default patterns ────────────────────────────────────────────────────────

_DEFAULT_PATTERNS: List[PIIPattern] = [
    PIIPattern(
        PIIType.EMAIL,
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}",
        "[REDACTED_EMAIL]",
    ),
    PIIPattern(
        PIIType.CREDIT_CARD,
        r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)",
        "[REDACTED_CC]",
    ),
    PIIPattern(
        PIIType.SSN,
        r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
        "[REDACTED_SSN]",
    ),
    PIIPattern(
        PIIType.PHONE,
        r"(?<!\d)(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}(?!\d)",
        "[REDACTED_PHONE]",
    ),
    PIIPattern(
        PIIType.API_KEY,
        r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*\S+",
        "[REDACTED_API_KEY]",
    ),
    PIIPattern(
        PIIType.PASSWORD,
        r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+",
        "[REDACTED_PASSWORD]",
    ),
    PIIPattern(
        PIIType.AUTH_TOKEN,
        r"(?i)(?:bearer|token)\s+[A-Za-z0-9_\-\.]+",
        "[REDACTED_TOKEN]",
    ),
    PIIPattern(
        PIIType.IP_ADDRESS,
        r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?!\d)",
        "[REDACTED_IP]",
    ),
]


class LogSanitizer:
    """Sensitive data sanitization for Murphy System logs."""

    def __init__(
        self,
        hash_sensitive: bool = True,
        custom_patterns: Optional[List[PIIPattern]] = None,
    ) -> None:
        self._hash_sensitive = hash_sensitive
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = {}
        self._total_sanitized: int = 0

        self._patterns: List[PIIPattern] = list(_DEFAULT_PATTERNS)
        if custom_patterns:
            self._patterns.extend(custom_patterns)

        self._compiled: Dict[PIIType, re.Pattern[str]] = {}
        self._rebuild_compiled()
        logger.info("LogSanitizer initialised with %d patterns", len(self._patterns))

    # ── internal helpers ─────────────────────────────────────────────────

    def _rebuild_compiled(self) -> None:
        self._compiled = {
            p.pii_type: re.compile(p.pattern)
            for p in self._patterns
            if p.enabled
        }

    def _hash_value(self, value: str) -> str:
        digest = hashlib.sha256(value.encode()).hexdigest()[:16]
        return f"[HASH:{digest}]"

    def _replacement_for(self, pii_type: PIIType, match: str) -> str:
        if self._hash_sensitive:
            return self._hash_value(match)
        for p in self._patterns:
            if p.pii_type == pii_type:
                return p.replacement
        return "[REDACTED]"

    # ── public API ───────────────────────────────────────────────────────

    def sanitize(self, text: str) -> str:
        """Sanitize a text string by redacting detected PII."""
        result = text
        with self._lock:
            for pii_type, regex in self._compiled.items():
                def _replace(m: re.Match[str], _t: PIIType = pii_type) -> str:
                    self._stats[_t.value] = self._stats.get(_t.value, 0) + 1
                    return self._replacement_for(_t, m.group())

                result = regex.sub(_replace, result)
            self._total_sanitized += 1
        if result != text:
            logger.debug("PII detected and redacted in text of length %d", len(text))
        return result

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize all string values in a dictionary."""
        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize(value)
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_dict(v) if isinstance(v, dict)
                    else self.sanitize(v) if isinstance(v, str)
                    else v
                    for v in value
                ]
            else:
                sanitized[key] = value
        return sanitized

    def sanitize_log_entries(
        self, entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sanitize a batch of log entry dicts."""
        logger.info("Sanitizing batch of %d log entries", len(entries))
        return [self.sanitize_dict(entry) for entry in entries]

    def scan_text(self, text: str) -> Dict[str, int]:
        """Scan text for PII without redacting. Returns detection counts."""
        counts: Dict[str, int] = {}
        with self._lock:
            for pii_type, regex in self._compiled.items():
                matches = regex.findall(text)
                if matches:
                    counts[pii_type.value] = len(matches)
        return counts

    def add_pattern(self, pattern: PIIPattern) -> None:
        """Add a custom PII detection pattern."""
        with self._lock:
            capped_append(self._patterns, pattern)
            self._rebuild_compiled()
        logger.info("Added PII pattern for %s", pattern.pii_type.value)

    def remove_pattern(self, pii_type: PIIType) -> bool:
        """Remove a pattern by PII type."""
        with self._lock:
            before = len(self._patterns)
            self._patterns = [p for p in self._patterns if p.pii_type != pii_type]
            removed = len(self._patterns) < before
            if removed:
                self._rebuild_compiled()
        if removed:
            logger.info("Removed PII pattern for %s", pii_type.value)
        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get sanitization statistics."""
        with self._lock:
            return {
                "total_sanitized": self._total_sanitized,
                "detections_by_type": dict(self._stats),
                "active_patterns": len(self._compiled),
                "total_patterns": len(self._patterns),
            }

    def retroactive_sanitize(
        self, log_records: List[str]
    ) -> Tuple[List[str], SanitizationResult]:
        """Retroactively sanitize existing log records."""
        logger.info("Retroactive sanitization of %d records", len(log_records))
        original_length = sum(len(r) for r in log_records)
        aggregate: Dict[str, int] = {}

        sanitized_records: List[str] = []
        for record in log_records:
            counts = self.scan_text(record)
            for key, cnt in counts.items():
                aggregate[key] = aggregate.get(key, 0) + cnt
            sanitized_records.append(self.sanitize(record))

        sanitized_length = sum(len(r) for r in sanitized_records)
        result = SanitizationResult(
            original_length=original_length,
            sanitized_length=sanitized_length,
            detections=aggregate,
        )
        logger.info("Retroactive sanitization complete: %s", result.to_dict())
        return sanitized_records, result
