"""
Upload Content Reviewer — Pre-upload security and PII scan for agent run recordings.

Design Label: YT-005 — Pre-Upload Content Safety Gate
Owner: Security Team / Platform Engineering
Dependencies:
  - security_audit_scanner (_SECURITY_PATTERNS)
  - security_plane/log_sanitizer (PII patterns)
  - agent_run_recorder (AgentRunRecording)

Scans recording content for secrets, PII, API keys, DB URLs, and internal paths
before allowing upload to YouTube. Supports auto-redaction with re-verification.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: max 500 review results in history
  - Conservative: flags potential issues for human review

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import copy
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_REVIEW_HISTORY = 500
_REDACTED = "[REDACTED]"

# ---------------------------------------------------------------------------
# Content-specific patterns (beyond code patterns in security_audit_scanner)
# ---------------------------------------------------------------------------

_CONTENT_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "deepinfra_api_key",
        "pattern": r"\bgsk_[A-Za-z0-9]{20,}\b",
        "severity": "critical",
        "description": "Groq API key detected",
    },
    {
        "name": "openai_api_key",
        "pattern": r"\bsk-[A-Za-z0-9_-]{20,}\b",
        "severity": "critical",
        "description": "OpenAI API key detected",
    },
    {
        "name": "slack_token",
        "pattern": r"\bxoxb-[A-Za-z0-9_-]{24,}\b",
        "severity": "critical",
        "description": "Slack bot token detected",
    },
    {
        "name": "bearer_token",
        "pattern": r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}\b",
        "severity": "critical",
        "description": "Bearer token detected",
    },
    {
        "name": "generic_api_key",
        "pattern": r"""(?:api[_\-]?key|apikey|access[_\-]?token|secret[_\-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{16,}""",
        "severity": "high",
        "description": "Generic API key or access token assignment detected",
    },
    {
        "name": "postgresql_url",
        "pattern": r"postgresql://[^\s\"']+",
        "severity": "high",
        "description": "PostgreSQL connection URL with potential credentials",
    },
    {
        "name": "redis_url",
        "pattern": r"redis://[^\s\"']+",
        "severity": "high",
        "description": "Redis connection URL detected",
    },
    {
        "name": "mongodb_url",
        "pattern": r"mongodb://[^\s\"']+",
        "severity": "high",
        "description": "MongoDB connection URL detected",
    },
    {
        "name": "email_address",
        "pattern": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "severity": "medium",
        "description": "Email address (PII) detected",
    },
    {
        "name": "phone_number",
        "pattern": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "severity": "medium",
        "description": "Phone number (PII) detected",
    },
    {
        "name": "ssn_pattern",
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "severity": "high",
        "description": "SSN-like pattern (PII) detected",
    },
    {
        "name": "internal_path",
        "pattern": r"(?:/home/[a-zA-Z0-9_\-]+|/Users/[a-zA-Z0-9_\-]+|C:\\Users\\[^\\]+)",
        "severity": "low",
        "description": "Internal file path revealing user directory",
    },
    {
        "name": "dotenv_value",
        "pattern": r"(?:^|\s)[A-Z_]{3,}=[^\s]{8,}",
        "severity": "medium",
        "description": "Possible .env variable assignment with value",
    },
    {
        "name": "private_key_header",
        "pattern": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "severity": "critical",
        "description": "Private key block detected",
    },
    {
        "name": "aws_access_key",
        "pattern": r"\bAKIA[0-9A-Z]{16}\b",
        "severity": "critical",
        "description": "AWS access key ID detected",
    },
]

_COMPILED_PATTERNS = [
    {**p, "regex": re.compile(p["pattern"], re.MULTILINE)}
    for p in _CONTENT_PATTERNS
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single content safety finding."""

    finding_id: str
    field_name: str
    pattern_name: str
    severity: str
    description: str
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "field_name": self.field_name,
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "description": self.description,
            "snippet": self.snippet,
        }


@dataclass
class ContentReviewResult:
    """Full result of a pre-upload content review."""

    review_id: str
    run_id: str
    is_safe: bool
    findings: List[Finding]
    redacted_recording: Optional[Any]
    reviewed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "run_id": self.run_id,
            "is_safe": self.is_safe,
            "findings_count": len(self.findings),
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "findings": [f.to_dict() for f in self.findings],
            "has_redacted_version": self.redacted_recording is not None,
            "reviewed_at": self.reviewed_at,
        }


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

class UploadContentReviewer:
    """
    Scans an AgentRunRecording for secrets, PII, and sensitive data
    before allowing YouTube upload.

    Usage::

        reviewer = UploadContentReviewer()
        result = reviewer.review(recording)
        if not result.is_safe:
            result2 = reviewer.review(recording, auto_redact=True)
            if result2.is_safe:
                upload(result2.redacted_recording)
    """

    def __init__(self, max_history: int = _MAX_REVIEW_HISTORY) -> None:
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history

    def review(
        self,
        recording: Any,
        auto_redact: bool = False,
    ) -> ContentReviewResult:
        """
        Scan a recording for sensitive content.

        Args:
            recording: AgentRunRecording instance
            auto_redact: If True, attempt to redact findings and include
                         sanitised recording in result.

        Returns:
            ContentReviewResult with is_safe flag and findings list.
        """
        import uuid as _uuid

        review_id = _uuid.uuid4().hex[:12]
        findings: List[Finding] = []

        text_fields = self._extract_text_fields(recording)
        for field_name, text in text_fields.items():
            findings.extend(self._scan_text(field_name, text))

        is_safe = len(findings) == 0
        redacted: Optional[Any] = None

        if not is_safe and auto_redact:
            redacted = self._redact_recording(recording, findings)
            re_findings: List[Finding] = []
            re_fields = self._extract_text_fields(redacted)
            for field_name, text in re_fields.items():
                re_findings.extend(self._scan_text(field_name, text))
            if not re_findings:
                is_safe = True
                findings = []
            else:
                findings = re_findings

        result = ContentReviewResult(
            review_id=review_id,
            run_id=recording.run_id,
            is_safe=is_safe,
            findings=findings,
            redacted_recording=redacted,
        )

        with self._lock:
            capped_append(self._history, result.to_dict(), max_size=self._max_history)

        if is_safe:
            logger.info("Content review PASSED review_id=%s run_id=%s", review_id, recording.run_id)
        else:
            logger.warning(
                "Content review BLOCKED review_id=%s run_id=%s findings=%d critical=%d",
                review_id,
                recording.run_id,
                len(findings),
                result.critical_count,
            )
        return result

    def _extract_text_fields(self, recording: Any) -> Dict[str, str]:
        """Extract all text-bearing fields from a recording."""
        fields: Dict[str, str] = {}

        for attr in ("task_description", "task_type", "status", "system_version"):
            val = getattr(recording, attr, "")
            if val:
                fields[attr] = str(val)

        terminal = getattr(recording, "terminal_output", [])
        if terminal:
            fields["terminal_output"] = "\n".join(str(line) for line in terminal)

        for idx, step in enumerate(getattr(recording, "steps", [])):
            step_text = self._flatten_dict(step)
            if step_text:
                fields[f"step_{idx}"] = step_text

        for idx, dec in enumerate(getattr(recording, "hitl_decisions", [])):
            dec_text = self._flatten_dict(dec)
            if dec_text:
                fields[f"hitl_decision_{idx}"] = dec_text

        meta = getattr(recording, "metadata", {})
        if meta:
            fields["metadata"] = self._flatten_dict(meta)

        return fields

    def _flatten_dict(self, data: Any, depth: int = 0) -> str:
        """Recursively flatten dict/list to a searchable string."""
        if depth > 5:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            parts = []
            for val in data.values():
                parts.append(self._flatten_dict(val, depth + 1))
            return " ".join(parts)
        if isinstance(data, (list, tuple)):
            return " ".join(self._flatten_dict(item, depth + 1) for item in data)
        return str(data)

    def _scan_text(self, field_name: str, text: str) -> List[Finding]:
        """Scan a text blob against all content patterns."""
        findings: List[Finding] = []
        import uuid as _uuid

        for pattern_def in _COMPILED_PATTERNS:
            for match in pattern_def["regex"].finditer(text):
                snippet = match.group()[:60]
                if len(match.group()) > 60:
                    snippet += "…"
                findings.append(Finding(
                    finding_id=f"cf-{_uuid.uuid4().hex[:8]}",
                    field_name=field_name,
                    pattern_name=pattern_def["name"],
                    severity=pattern_def["severity"],
                    description=pattern_def["description"],
                    snippet=snippet,
                ))
        return findings

    def _redact_recording(self, recording: Any, findings: List[Finding]) -> Any:
        """
        Return a deep-copied recording with sensitive strings replaced
        by [REDACTED].
        """
        redacted = copy.deepcopy(recording)

        patterns_to_redact = [
            _COMPILED_PATTERNS[idx]["regex"]
            for idx in range(len(_COMPILED_PATTERNS))
        ]

        def _redact_string(text: str) -> str:
            for rgx in patterns_to_redact:
                text = rgx.sub(_REDACTED, text)
            return text

        def _redact_value(val: Any) -> Any:
            if isinstance(val, str):
                return _redact_string(val)
            if isinstance(val, dict):
                return {k: _redact_value(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_redact_value(item) for item in val]
            return val

        for attr in ("task_description", "task_type", "status", "system_version"):
            current = getattr(redacted, attr, None)
            if current is not None:
                setattr(redacted, attr, _redact_value(current))

        if hasattr(redacted, "terminal_output"):
            redacted.terminal_output = [
                _redact_string(line) for line in redacted.terminal_output
            ]

        if hasattr(redacted, "steps"):
            redacted.steps = [_redact_value(s) for s in redacted.steps]

        if hasattr(redacted, "hitl_decisions"):
            redacted.hitl_decisions = [_redact_value(d) for d in redacted.hitl_decisions]

        if hasattr(redacted, "metadata"):
            redacted.metadata = _redact_value(redacted.metadata)

        return redacted

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent review history."""
        with self._lock:
            return list(self._history[-limit:])
