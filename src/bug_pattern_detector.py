"""
Bug Pattern Detector for Murphy System.

Design Label: DEV-004 — Automated Bug Pattern Detection & Reporting
Owner: Backend Team / QA Team
Dependencies:
  - LogAnalysisEngine (OBS-003, for log pattern feeds)
  - SelfImprovementEngine (ARCH-001, for proposal injection)
  - EventBackbone (publishes LEARNING_FEEDBACK on bug detection)
  - PersistenceManager (for durable bug reports)

Implements Phase 2 — Development Automation:
  Analyses error logs and exception data to detect recurring bug
  patterns, classify their severity, and generate structured bug
  reports. Optionally injects improvement proposals into
  SelfImprovementEngine for automated fix suggestions.

Flow:
  1. Ingest error records (message, stack trace, component, timestamp)
  2. Normalise and fingerprint errors for pattern matching
  3. Detect recurring patterns via frequency analysis
  4. Classify pattern severity (critical/high/medium/low)
  5. Generate bug reports with pattern details and fix suggestions
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies source code
  - Bounded: configurable max errors and patterns
  - Conservative: only flags patterns with sufficient frequency
  - Audit trail: every detection cycle is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import uuid
from collections import Counter, defaultdict
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ERRORS = 50_000
_MAX_PATTERNS = 5_000
_MIN_OCCURRENCES_FOR_PATTERN = 3

_CRITICAL_THRESHOLD = 20
_HIGH_THRESHOLD = 10
_MEDIUM_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ErrorRecord:
    """A single ingested error record."""
    error_id: str
    message: str
    stack_trace: str = ""
    component: str = ""
    error_type: str = ""
    tags: List[str] = field(default_factory=list)
    fingerprint: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "message": self.message,
            "stack_trace": self.stack_trace[:500],
            "component": self.component,
            "error_type": self.error_type,
            "tags": list(self.tags),
            "fingerprint": self.fingerprint,
            "recorded_at": self.recorded_at,
        }


@dataclass
class BugPattern:
    """A recurring error pattern detected by analysis."""
    pattern_id: str
    fingerprint: str
    representative_message: str
    occurrences: int
    severity: str = "medium"
    component: str = ""
    error_type: str = ""
    first_seen: str = ""
    last_seen: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "fingerprint": self.fingerprint,
            "representative_message": self.representative_message,
            "occurrences": self.occurrences,
            "severity": self.severity,
            "component": self.component,
            "error_type": self.error_type,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class BugReport:
    """A generated bug report summarising detected patterns."""
    report_id: str
    total_errors_analysed: int
    patterns_detected: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    patterns: List[BugPattern] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_errors_analysed": self.total_errors_analysed,
            "patterns_detected": self.patterns_detected,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "patterns": [p.to_dict() for p in self.patterns],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# BugPatternDetector
# ---------------------------------------------------------------------------

class BugPatternDetector:
    """Automated bug pattern detection and reporting from error data.

    Design Label: DEV-004
    Owner: Backend Team / QA Team

    Usage::

        detector = BugPatternDetector(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        detector.ingest_error(message="Connection timeout", component="api-gw")
        report = detector.run_detection_cycle()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        improvement_engine=None,
        max_errors: int = _MAX_ERRORS,
        max_patterns: int = _MAX_PATTERNS,
        min_occurrences: int = _MIN_OCCURRENCES_FOR_PATTERN,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._improvement = improvement_engine
        self._errors: List[ErrorRecord] = []
        self._patterns: List[BugPattern] = []
        self._reports: List[BugReport] = []
        self._max_errors = max_errors
        self._max_patterns = max_patterns
        self._min_occurrences = min_occurrences

    # ------------------------------------------------------------------
    # Error ingestion
    # ------------------------------------------------------------------

    def ingest_error(
        self,
        message: str,
        stack_trace: str = "",
        component: str = "",
        error_type: str = "",
        tags: Optional[List[str]] = None,
    ) -> ErrorRecord:
        """Ingest a single error record."""
        fingerprint = self._compute_fingerprint(message, error_type, component)
        record = ErrorRecord(
            error_id=f"err-{uuid.uuid4().hex[:8]}",
            message=message,
            stack_trace=stack_trace,
            component=component,
            error_type=error_type,
            tags=tags or [],
            fingerprint=fingerprint,
        )
        with self._lock:
            if len(self._errors) >= self._max_errors:
                evict = max(1, self._max_errors // 10)
                self._errors = self._errors[evict:]
            self._errors.append(record)
        logger.info("Ingested error %s (fingerprint=%s)", record.error_id, fingerprint[:12])
        return record

    # ------------------------------------------------------------------
    # Detection cycle
    # ------------------------------------------------------------------

    def run_detection_cycle(self) -> BugReport:
        """Analyse ingested errors and detect recurring patterns."""
        with self._lock:
            errors = list(self._errors)

        # Group by fingerprint
        groups: Dict[str, List[ErrorRecord]] = defaultdict(list)
        for err in errors:
            groups[err.fingerprint].append(err)

        patterns: List[BugPattern] = []
        for fp, errs in groups.items():
            if len(errs) < self._min_occurrences:
                continue
            severity = self._classify_severity(len(errs))
            rep = errs[-1]  # most recent as representative
            pattern = BugPattern(
                pattern_id=f"pat-{uuid.uuid4().hex[:8]}",
                fingerprint=fp,
                representative_message=rep.message[:500],
                occurrences=len(errs),
                severity=severity,
                component=rep.component,
                error_type=rep.error_type,
                first_seen=errs[0].recorded_at,
                last_seen=errs[-1].recorded_at,
                suggested_fix=self._suggest_fix(rep.message, rep.error_type),
            )
            patterns.append(pattern)

        # Sort by severity then occurrences
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        patterns.sort(key=lambda p: (sev_order.get(p.severity, 9), -p.occurrences))

        # Bound patterns
        if len(patterns) > self._max_patterns:
            patterns = patterns[: self._max_patterns]

        # Build report
        report = BugReport(
            report_id=f"bug-{uuid.uuid4().hex[:8]}",
            total_errors_analysed=len(errors),
            patterns_detected=len(patterns),
            critical_count=sum(1 for p in patterns if p.severity == "critical"),
            high_count=sum(1 for p in patterns if p.severity == "high"),
            medium_count=sum(1 for p in patterns if p.severity == "medium"),
            low_count=sum(1 for p in patterns if p.severity == "low"),
            patterns=patterns,
        )

        with self._lock:
            self._patterns = patterns
            capped_append(self._reports, report)

        # Inject proposals if improvement engine is attached
        if self._improvement is not None:
            for p in patterns:
                if p.severity in ("critical", "high"):
                    self._inject_proposal(p)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "Bug detection cycle: %d errors → %d patterns (C=%d H=%d M=%d L=%d)",
            report.total_errors_analysed, report.patterns_detected,
            report.critical_count, report.high_count,
            report.medium_count, report.low_count,
        )
        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent ingested errors."""
        with self._lock:
            errors = list(self._errors)
        return [e.to_dict() for e in errors[-limit:]]

    def get_patterns(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return detected bug patterns."""
        with self._lock:
            patterns = list(self._patterns)
        return [p.to_dict() for p in patterns[:limit]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return generated bug reports."""
        with self._lock:
            reports = list(self._reports)
        return [r.to_dict() for r in reports[-limit:]]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return detector status summary."""
        with self._lock:
            return {
                "total_errors": len(self._errors),
                "total_patterns": len(self._patterns),
                "total_reports": len(self._reports),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
                "improvement_attached": self._improvement is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_fingerprint(message: str, error_type: str, component: str) -> str:
        """Compute a stable fingerprint for error deduplication."""
        normalised = re.sub(r"\b\d+\b", "N", message.lower().strip())
        normalised = re.sub(r"\s+", " ", normalised)
        raw = f"{error_type}:{component}:{normalised}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _classify_severity(occurrences: int) -> str:
        """Classify bug pattern severity based on frequency."""
        if occurrences >= _CRITICAL_THRESHOLD:
            return "critical"
        if occurrences >= _HIGH_THRESHOLD:
            return "high"
        if occurrences >= _MEDIUM_THRESHOLD:
            return "medium"
        return "low"

    @staticmethod
    def _suggest_fix(message: str, error_type: str) -> str:
        """Generate a basic fix suggestion from error characteristics."""
        msg_lower = message.lower()
        if "timeout" in msg_lower:
            return "Investigate connection timeouts — increase timeout, add retry logic, or check network."
        if "memory" in msg_lower or "oom" in msg_lower:
            return "Investigate memory pressure — profile memory usage, add limits, or scale resources."
        if "permission" in msg_lower or "auth" in msg_lower:
            return "Investigate permission/auth errors — verify credentials, RBAC, and token expiry."
        if "null" in msg_lower or "none" in msg_lower:
            return "Investigate null/None references — add null checks and input validation."
        if "connection" in msg_lower:
            return "Investigate connection issues — check service health, DNS, and connection pools."
        return "Review error details and stack trace for root cause analysis."

    def _inject_proposal(self, pattern: BugPattern) -> None:
        """Inject an improvement proposal for a detected bug pattern."""
        try:
            from self_improvement_engine import ExecutionOutcome, OutcomeType
            outcome = ExecutionOutcome(
                task_id=f"bug-{pattern.pattern_id}",
                session_id="bug_detector",
                outcome=OutcomeType.FAILURE,
                metrics={
                    "task_type": pattern.component or "unknown",
                    "error_type": pattern.error_type,
                    "fingerprint": pattern.fingerprint,
                    "occurrences": pattern.occurrences,
                },
            )
            self._improvement.record_outcome(outcome)
            self._improvement.generate_proposals()
        except Exception as exc:
            logger.debug("Improvement injection skipped: %s", exc)

    def _publish_event(self, report: BugReport) -> None:
        """Publish a LEARNING_FEEDBACK event for bug detection."""
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "bug_pattern_detector",
                    "action": "detection_cycle_complete",
                    "report_id": report.report_id,
                    "patterns_detected": report.patterns_detected,
                    "critical_count": report.critical_count,
                    "high_count": report.high_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="bug_pattern_detector",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
