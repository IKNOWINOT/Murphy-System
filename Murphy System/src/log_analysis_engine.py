"""
Log Analysis Engine for Murphy System.

Design Label: OBS-003 — RAG-Powered Log Pattern Detection
Owner: Backend Team
Dependencies: RAGVectorIntegration (for semantic search), EventBackbone (optional)

Implements Phase 1 — Observability & Monitoring:
  - Ingests structured log entries into a searchable corpus
  - Detects recurring error patterns using frequency analysis
  - Generates concise error reports grouped by pattern
  - Publishes LEARNING_FEEDBACK events when patterns are detected  [OBS-003b]

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded history: configurable max entries prevents memory leaks
  - Pure Python stdlib — no external dependencies

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class LogLevel(str, Enum):
    """Standard log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_SEVERITY_ORDER = {
    LogLevel.DEBUG: 0,
    LogLevel.INFO: 1,
    LogLevel.WARNING: 2,
    LogLevel.ERROR: 3,
    LogLevel.CRITICAL: 4,
}


@dataclass
class LogEntry:
    """A single structured log entry."""
    message: str
    level: LogLevel = LogLevel.INFO
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class ErrorPattern:
    """A detected recurring error pattern."""
    pattern_id: str
    category: str
    sample_message: str
    occurrences: int
    first_seen: str
    last_seen: str
    sources: List[str] = field(default_factory=list)
    severity: LogLevel = LogLevel.ERROR

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "category": self.category,
            "sample_message": self.sample_message,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "sources": self.sources,
            "severity": self.severity.value,
        }


@dataclass
class ErrorReport:
    """An auto-generated report summarising detected error patterns."""
    report_id: str
    patterns: List[ErrorPattern]
    total_entries_analysed: int
    error_count: int
    warning_count: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_entries_analysed": self.total_entries_analysed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "pattern_count": len(self.patterns),
            "patterns": [p.to_dict() for p in self.patterns],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# LogAnalysisEngine
# ---------------------------------------------------------------------------

class LogAnalysisEngine:
    """RAG-powered log pattern detection and error reporting.

    Design Label: OBS-003
    Owner: Backend Team

    Usage::

        engine = LogAnalysisEngine(event_backbone=backbone)
        engine.ingest(LogEntry(message="Connection refused", level=LogLevel.ERROR, source="db"))
        engine.ingest(LogEntry(message="Connection refused", level=LogLevel.ERROR, source="db"))
        report = engine.generate_report()
        patterns = engine.detect_patterns()
    """

    def __init__(
        self,
        event_backbone=None,
        rag_integration=None,
        max_entries: int = 10_000,
        pattern_threshold: int = 2,
    ) -> None:
        self._lock = threading.Lock()
        self._entries: List[LogEntry] = []
        self._max_entries = max_entries
        self._pattern_threshold = pattern_threshold
        self._event_backbone = event_backbone
        self._rag = rag_integration
        self._reports: List[ErrorReport] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, entry: LogEntry) -> str:
        """Ingest a single log entry. Returns the entry_id."""
        with self._lock:
            self._entries.append(entry)
            # Bounded buffer
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        # Optional RAG indexing
        if self._rag is not None:
            try:
                self._rag.ingest_document(
                    text=entry.message,
                    title=f"log-{entry.entry_id}",
                    source=entry.source or "log_analysis",
                    metadata={"level": entry.level.value, "timestamp": entry.timestamp},
                )
            except Exception as exc:
                logger.debug("RAG ingestion skipped: %s", exc)

        return entry.entry_id

    def ingest_batch(self, entries: List[LogEntry]) -> int:
        """Ingest multiple log entries. Returns count ingested."""
        for e in entries:
            self.ingest(exc)
        return len(entries)

    # ------------------------------------------------------------------
    # Pattern detection
    # ------------------------------------------------------------------

    def detect_patterns(self, min_level: LogLevel = LogLevel.WARNING) -> List[ErrorPattern]:
        """Detect recurring patterns in error/warning log entries.

        Groups entries by normalised message text, returns patterns that
        appear at least ``pattern_threshold`` times.
        """
        with self._lock:
            entries = list(self._entries)

        min_sev = _SEVERITY_ORDER.get(min_level, 2)
        relevant = [
            e for e in entries
            if _SEVERITY_ORDER.get(e.level, 0) >= min_sev
        ]

        # Group by normalised message (lowercase, strip digits for grouping)
        groups: Dict[str, List[LogEntry]] = defaultdict(list)
        for e in relevant:
            key = self._normalise_message(e.message)
            groups[key].append(exc)

        patterns: List[ErrorPattern] = []
        for key, group in groups.items():
            if len(group) < self._pattern_threshold:
                continue
            timestamps = sorted(e.timestamp for e in group)
            max_sev = max(group, key=lambda e: _SEVERITY_ORDER.get(e.level, 0))
            sources = sorted(set(e.source for e in group if e.source))
            patterns.append(ErrorPattern(
                pattern_id=f"logpat-{uuid.uuid4().hex[:8]}",
                category=key[:80],
                sample_message=group[0].message,
                occurrences=len(group),
                first_seen=timestamps[0],
                last_seen=timestamps[-1],
                sources=sources[:10],
                severity=max_sev.level,
            ))

        # Sort by occurrences descending
        patterns.sort(key=lambda p: p.occurrences, reverse=True)

        # Publish to EventBackbone if attached
        if self._event_backbone is not None and patterns:
            try:
                from event_backbone import EventType
                self._event_backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "log_analysis_engine",
                        "pattern_count": len(patterns),
                        "patterns": [p.to_dict() for p in patterns[:5]],
                    },
                    source="log_analysis_engine",
                )
            except Exception as exc:
                logger.warning("Failed to publish LEARNING_FEEDBACK: %s", exc)

        return patterns

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self) -> ErrorReport:
        """Generate a comprehensive error report from current log entries."""
        with self._lock:
            entries = list(self._entries)

        error_count = sum(1 for e in entries if e.level in (LogLevel.ERROR, LogLevel.CRITICAL))
        warning_count = sum(1 for e in entries if e.level == LogLevel.WARNING)
        patterns = self.detect_patterns()

        report = ErrorReport(
            report_id=f"logrpt-{uuid.uuid4().hex[:8]}",
            patterns=patterns,
            total_entries_analysed=len(entries),
            error_count=error_count,
            warning_count=warning_count,
        )

        with self._lock:
            self._reports.append(report)
            if len(self._reports) > 50:
                self._reports = self._reports[-50:]

        logger.info(
            "Log report generated: %d entries, %d errors, %d warnings, %d patterns",
            len(entries), error_count, warning_count, len(patterns),
        )
        return report

    # ------------------------------------------------------------------
    # Search (RAG integration)
    # ------------------------------------------------------------------

    def search_logs(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Semantic search over ingested logs via RAG. Returns empty if no RAG attached."""
        if self._rag is None:
            return []
        try:
            result = self._rag.search(query=query, top_k=top_k)
            return result.get("results", [])
        except Exception as exc:
            logger.warning("RAG search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "max_entries": self._max_entries,
                "pattern_threshold": self._pattern_threshold,
                "reports_generated": len(self._reports),
                "rag_attached": self._rag is not None,
                "event_backbone_attached": self._event_backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_message(msg: str) -> str:
        """Normalise a log message for pattern grouping.

        Lowercases, strips leading/trailing whitespace, and replaces
        sequences of digits with ``<N>`` so that messages like
        'Connection refused on port 5432' and 'Connection refused on port 3306'
        are grouped together.
        """
        import re
        normalised = msg.strip().lower()
        normalised = re.sub(r"\d+", "<N>", normalised)
        return normalised
