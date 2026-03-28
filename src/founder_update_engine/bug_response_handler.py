"""
Founder Update Engine — Bug Response Handler

Design Label: ARCH-007 — Founder Update Engine: Bug Response Handler
Owner: Backend Team
Dependencies:
  - RecommendationEngine (ARCH-007) — recommendation creation
  - BugPatternDetector (DEV-004) — error classification and pattern analysis
  - SelfImprovementEngine (ARCH-001) — proposal injection for high-severity issues
  - PersistenceManager — durable response history
  - EventBackbone — event publishing

Ingests structured bug reports, classifies them by severity and category,
generates human-readable auto-response drafts, and surfaces BUG_RESPONSE
and SECURITY recommendations for Founder review.

Workflow per report:
  1. Normalise the incoming report
  2. Feed the error data into BugPatternDetector (if available)
  3. Classify severity (critical / high / medium / low)
  4. Identify category (crash / security / performance / regression / other)
  5. Generate root-cause hypotheses and suggested actions
  6. Draft an auto-response message for the reporter
  7. Create recommendations via RecommendationEngine
  8. Persist and publish

Safety invariants:
  - NEVER modifies source files on disk
  - All actions are proposals; execution requires explicit approval
  - Thread-safe: all shared state guarded by Lock
  - Bounded: response history capped to prevent unbounded growth

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_RESPONSE_HISTORY = 1_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BugSeverity(str, Enum):
    """Severity tier for an incoming bug report."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugCategory(str, Enum):
    """Functional category of a bug report."""

    CRASH = "crash"
    SECURITY = "security"
    PERFORMANCE = "performance"
    REGRESSION = "regression"
    DATA_LOSS = "data_loss"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BugReport:
    """An incoming bug report to be processed.

    Attributes:
        report_id: Unique identifier (auto-generated if not provided).
        title: Short title summarising the bug.
        description: Full description from the reporter.
        component: Name of the affected Murphy subsystem or module.
        severity: Reporter-supplied severity hint (normalised by handler).
        stack_trace: Optional stack trace string.
        reporter: Email or identifier of the reporter (may be anonymous).
        tags: Free-form labels for routing or triage.
        received_at: UTC timestamp when the report was received.
    """

    title: str
    description: str
    component: str = ""
    severity: str = "medium"
    stack_trace: str = ""
    reporter: str = "anonymous"
    tags: List[str] = field(default_factory=list)
    report_id: str = field(default_factory=lambda: f"br-{uuid.uuid4().hex[:8]}")
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "title": self.title,
            "description": self.description,
            "component": self.component,
            "severity": self.severity,
            "stack_trace": self.stack_trace,
            "reporter": self.reporter,
            "tags": self.tags,
            "received_at": self.received_at.isoformat(),
        }


@dataclass
class BugResponse:
    """Auto-generated response record for a single bug report.

    Attributes:
        response_id: Unique identifier.
        report_id: ID of the originating bug report.
        classified_severity: Handler-classified severity (may differ from reported).
        category: Functional category identified by the handler.
        root_cause_hypotheses: List of plausible root causes.
        suggested_actions: Structured action items for the engineering team.
        response_draft: Human-readable draft response to the reporter.
        recommendation_ids: IDs of recommendations generated for this report.
        generated_at: UTC timestamp when the response was generated.
        related_pattern_ids: Pattern IDs from BugPatternDetector that match.
    """

    response_id: str
    report_id: str
    classified_severity: BugSeverity
    category: BugCategory
    root_cause_hypotheses: List[str]
    suggested_actions: List[Dict[str, Any]]
    response_draft: str
    recommendation_ids: List[str]
    generated_at: datetime
    related_pattern_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "report_id": self.report_id,
            "classified_severity": self.classified_severity.value,
            "category": self.category.value,
            "root_cause_hypotheses": self.root_cause_hypotheses,
            "suggested_actions": self.suggested_actions,
            "response_draft": self.response_draft,
            "recommendation_ids": self.recommendation_ids,
            "generated_at": self.generated_at.isoformat(),
            "related_pattern_ids": self.related_pattern_ids,
        }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class BugResponseHandler:
    """Ingests bug reports and generates classified auto-responses.

    Design Label: ARCH-007
    Owner: Backend Team

    Integrates with:
    - BugPatternDetector  — feeds errors in, retrieves matching patterns
    - RecommendationEngine — creates BUG_RESPONSE / SECURITY recommendations
    - SelfImprovementEngine — injects proposals for critical/high findings

    Usage::

        handler = BugResponseHandler(
            recommendation_engine=rec_engine,
            bug_detector=detector,
            persistence_manager=pm,
        )
        report = BugReport(
            title="Null pointer in billing module",
            description="Crash during invoice generation",
            component="billing",
            severity="high",
            stack_trace="...",
        )
        response = handler.ingest(report)
        print(response.response_draft)
    """

    _PERSISTENCE_DOC_KEY = "founder_update_engine_bug_response_handler"

    # Keywords used for category classification
    _SECURITY_KEYWORDS = frozenset(
        {"injection", "xss", "csrf", "auth", "password", "token", "exploit", "vuln", "sql"}
    )
    _CRASH_KEYWORDS = frozenset(
        {"traceback", "exception", "crash", "null", "none", "attributeerror", "typeerror",
         "keyerror", "indexerror", "segfault", "killed"}
    )
    _PERF_KEYWORDS = frozenset(
        {"slow", "timeout", "latency", "memory", "cpu", "oom", "leak", "bottleneck"}
    )
    _REGRESSION_KEYWORDS = frozenset(
        {"worked", "used to", "regression", "broke", "after update", "after deploy"}
    )
    _DATA_LOSS_KEYWORDS = frozenset(
        {"lost", "deleted", "corrupt", "missing data", "disappeared", "overwrite"}
    )

    def __init__(
        self,
        recommendation_engine=None,
        bug_detector=None,
        improvement_engine=None,
        event_backbone=None,
        persistence_manager=None,
    ) -> None:
        self._rec_engine = recommendation_engine
        self._bug_detector = bug_detector
        self._improvement_engine = improvement_engine
        self._event_backbone = event_backbone
        self._persistence = persistence_manager

        self._responses: List[BugResponse] = []
        self._lock = threading.Lock()

        self._load_state()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def ingest(self, report: BugReport) -> BugResponse:
        """Process a bug report end-to-end and return a :class:`BugResponse`.

        Steps:
        1. Feed error data into BugPatternDetector.
        2. Classify severity and category.
        3. Generate hypotheses, actions, and response draft.
        4. Create recommendations.
        5. Persist and publish.

        Args:
            report: The incoming bug report.

        Returns:
            :class:`BugResponse` with full classification and auto-response.
        """
        # 1. Feed into BugPatternDetector
        related_patterns: List[str] = []
        if self._bug_detector is not None:
            try:
                self._bug_detector.ingest_error(
                    message=report.description,
                    stack_trace=report.stack_trace,
                    component=report.component,
                    error_type=report.severity,
                    tags=report.tags,
                )
                # Run a detection cycle to get fresh patterns
                bug_report = self._bug_detector.run_detection_cycle()
                related_patterns = [
                    p.get("pattern_id", "")
                    for p in bug_report.patterns
                    if p.component == report.component
                ] if hasattr(bug_report, "patterns") else []
            except Exception as exc:
                logger.debug("BugResponseHandler: BugPatternDetector failed: %s", exc)

        # 2. Classify
        severity = self._classify_severity(report)
        category = self._classify_category(report)

        # 3. Generate content
        hypotheses = self._generate_hypotheses(report, category)
        actions = self._generate_actions(report, severity, category)
        draft = self._generate_draft(report, severity, category, hypotheses)

        # 4. Create recommendations
        rec_ids: List[str] = []
        if self._rec_engine is not None:
            recs = self._generate_recommendations(report, severity, category)
            rec_ids = [r.id for r in recs]
            with self._rec_engine._lock:
                for r in recs:
                    self._rec_engine._recommendations[r.id] = r

        # 5. Build response
        response = BugResponse(
            response_id=f"resp-{uuid.uuid4().hex[:8]}",
            report_id=report.report_id,
            classified_severity=severity,
            category=category,
            root_cause_hypotheses=hypotheses,
            suggested_actions=actions,
            response_draft=draft,
            recommendation_ids=rec_ids,
            generated_at=datetime.now(timezone.utc),
            related_pattern_ids=related_patterns,
        )

        with self._lock:
            if len(self._responses) >= _MAX_RESPONSE_HISTORY:
                self._responses = self._responses[-(_MAX_RESPONSE_HISTORY - 1):]
            self._responses.append(response)

        self._save_state()
        self._publish_event(report, response)

        logger.info(
            "BugResponseHandler: report %s → severity=%s category=%s recs=%d",
            report.report_id,
            severity.value,
            category.value,
            len(rec_ids),
        )
        return response

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_responses(self, limit: int = 20) -> List[BugResponse]:
        """Return the most recent auto-responses (newest first).

        Args:
            limit: Maximum number of responses to return.
        """
        with self._lock:
            return list(reversed(self._responses[-limit:]))

    def get_response_by_report_id(self, report_id: str) -> Optional[BugResponse]:
        """Find the response for a specific report ID.

        Args:
            report_id: The report ID to look up.

        Returns:
            The matching :class:`BugResponse`, or ``None`` if not found.
        """
        with self._lock:
            for resp in reversed(self._responses):
                if resp.report_id == report_id:
                    return resp
        return None

    def get_status(self) -> Dict[str, Any]:
        """Return summary statistics."""
        with self._lock:
            total = len(self._responses)
            by_severity: Dict[str, int] = {}
            by_category: Dict[str, int] = {}
            for r in self._responses:
                by_severity[r.classified_severity.value] = (
                    by_severity.get(r.classified_severity.value, 0) + 1
                )
                by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        return {
            "total_responses": total,
            "by_severity": by_severity,
            "by_category": by_category,
        }

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _classify_severity(self, report: BugReport) -> BugSeverity:
        """Derive a canonical severity from the report."""
        reported = report.severity.lower().strip()
        if reported in ("critical", "blocker"):
            return BugSeverity.CRITICAL
        if reported in ("high", "major"):
            return BugSeverity.HIGH
        if reported in ("medium", "normal", "moderate"):
            return BugSeverity.MEDIUM
        if reported in ("low", "minor", "trivial"):
            return BugSeverity.LOW

        # Heuristic: escalate based on keywords
        text = (report.title + " " + report.description + " " + report.stack_trace).lower()
        if any(k in text for k in ("critical", "data loss", "security breach", "crash")):
            return BugSeverity.HIGH
        return BugSeverity.MEDIUM

    def _classify_category(self, report: BugReport) -> BugCategory:
        """Identify the functional category of the bug."""
        text = (report.title + " " + report.description + " " + report.stack_trace).lower()
        if any(k in text for k in self._SECURITY_KEYWORDS):
            return BugCategory.SECURITY
        if any(k in text for k in self._DATA_LOSS_KEYWORDS):
            return BugCategory.DATA_LOSS
        if any(k in text for k in self._CRASH_KEYWORDS):
            return BugCategory.CRASH
        if any(k in text for k in self._PERF_KEYWORDS):
            return BugCategory.PERFORMANCE
        if any(k in text for k in self._REGRESSION_KEYWORDS):
            return BugCategory.REGRESSION
        return BugCategory.OTHER

    # ------------------------------------------------------------------
    # Content generation
    # ------------------------------------------------------------------

    def _generate_hypotheses(
        self, report: BugReport, category: BugCategory
    ) -> List[str]:
        """Generate plausible root-cause hypotheses."""
        hypotheses: List[str] = []
        component = report.component or "the affected module"

        if category == BugCategory.CRASH:
            hypotheses += [
                f"Unhandled exception or null reference in {component}.",
                "Missing input validation allowing an unexpected state.",
            ]
            if report.stack_trace:
                hypotheses.append("Stack trace indicates a logic error in the call path.")
        elif category == BugCategory.SECURITY:
            hypotheses += [
                "Insufficient input sanitisation in an API endpoint.",
                "Authentication or authorisation bypass in the request flow.",
            ]
        elif category == BugCategory.PERFORMANCE:
            hypotheses += [
                f"Inefficient query or loop in {component} under load.",
                "Memory leak or resource not being released after use.",
            ]
        elif category == BugCategory.REGRESSION:
            hypotheses += [
                "A recent deployment changed behaviour of a shared dependency.",
                "Configuration drift between environments.",
            ]
        elif category == BugCategory.DATA_LOSS:
            hypotheses += [
                "Destructive operation without a prior backup or confirmation step.",
                "Race condition between concurrent write operations.",
            ]
        else:
            hypotheses.append(f"Unexpected behaviour in {component} under specific conditions.")

        return hypotheses

    def _generate_actions(
        self,
        report: BugReport,
        severity: BugSeverity,
        category: BugCategory,
    ) -> List[Dict[str, Any]]:
        """Generate structured action items for the engineering team."""
        actions: List[Dict[str, Any]] = [
            {
                "action": "triage",
                "description": f"Reproduce bug in development environment for {report.component or 'affected module'}.",
                "priority": severity.value,
            },
        ]

        if category == BugCategory.SECURITY:
            actions.insert(
                0,
                {
                    "action": "security_review",
                    "description": "Immediate security review required. Assess exploitability.",
                    "priority": "critical",
                },
            )
        if severity in (BugSeverity.CRITICAL, BugSeverity.HIGH):
            actions.append(
                {
                    "action": "hotfix_assessment",
                    "description": "Assess whether a hotfix release is required.",
                    "priority": severity.value,
                }
            )
        actions.append(
            {
                "action": "write_regression_test",
                "description": "Add a regression test to prevent recurrence.",
                "priority": "medium",
            }
        )
        return actions

    def _generate_draft(
        self,
        report: BugReport,
        severity: BugSeverity,
        category: BugCategory,
        hypotheses: List[str],
    ) -> str:
        """Generate a human-readable response draft for the reporter."""
        greeting = f"Thank you for your report (ID: {report.report_id})."
        ack = (
            f"We have received your {severity.value}-severity {category.value} report "
            f"regarding '{report.title}'."
        )
        if category == BugCategory.SECURITY:
            detail = (
                "Your report has been escalated to our security team for immediate review. "
                "We take security issues very seriously and will prioritise resolution."
            )
        elif severity == BugSeverity.CRITICAL:
            detail = (
                "This issue has been flagged as critical and assigned to our on-call team. "
                "We are working on a resolution urgently."
            )
        elif severity == BugSeverity.HIGH:
            detail = (
                "This issue has been assigned high priority and will be addressed in our "
                "next sprint or sooner if a hotfix is warranted."
            )
        else:
            detail = (
                "This issue has been logged and will be triaged in our regular bug review. "
                "We appreciate your patience."
            )

        hyp_text = ""
        if hypotheses:
            hyp_text = (
                "\n\nOur initial investigation suggests the following potential cause(s):\n"
                + "\n".join(f"  • {h}" for h in hypotheses[:2])
            )

        return f"{greeting}\n\n{ack}\n\n{detail}{hyp_text}\n\nBest regards,\nMurphy Engineering Team"

    # ------------------------------------------------------------------
    # Recommendation generation
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        report: BugReport,
        severity: BugSeverity,
        category: BugCategory,
    ) -> list:
        """Create BUG_RESPONSE (and optionally SECURITY) recommendations."""
        from .recommendation_engine import (
            RecommendationType,
            RecommendationPriority,
            RecommendationEngine,
        )

        recs = []

        # Always generate a BUG_RESPONSE recommendation
        priority_map = {
            BugSeverity.CRITICAL: RecommendationPriority.CRITICAL,
            BugSeverity.HIGH: RecommendationPriority.HIGH,
            BugSeverity.MEDIUM: RecommendationPriority.MEDIUM,
            BugSeverity.LOW: RecommendationPriority.LOW,
        }

        recs.append(
            RecommendationEngine._make_recommendation(
                subsystem=report.component or "unknown",
                rec_type=RecommendationType.BUG_RESPONSE,
                priority=priority_map.get(severity, RecommendationPriority.MEDIUM),
                title=f"Bug response: {report.title[:80]}",
                description=(
                    f"Bug report {report.report_id} received for '{report.component}'. "
                    f"Severity: {severity.value}. Category: {category.value}. "
                    f"Reporter: {report.reporter}."
                ),
                rationale=f"Incoming bug report classified {severity.value}/{category.value}.",
                actions=[
                    {
                        "action": "review_bug_report",
                        "report_id": report.report_id,
                        "component": report.component,
                        "severity": severity.value,
                    }
                ],
                impact={
                    "risk": severity.value,
                    "effort": "medium",
                    "benefit": "quality",
                },
                auto_applicable=False,
                requires_founder_approval=severity in (BugSeverity.CRITICAL, BugSeverity.HIGH),
                source={
                    "engine": "BugResponseHandler",
                    "report_id": report.report_id,
                    "category": category.value,
                },
            )
        )

        # Additional SECURITY recommendation for security-category bugs
        if category == BugCategory.SECURITY:
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem=report.component or "unknown",
                    rec_type=RecommendationType.SECURITY,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"Security bug: {report.title[:80]}",
                    description=(
                        f"Bug report {report.report_id} indicates a potential security issue "
                        f"in '{report.component}'. Immediate review required."
                    ),
                    rationale="Bug category classified as SECURITY — escalating to security review.",
                    actions=[
                        {
                            "action": "security_review",
                            "report_id": report.report_id,
                            "component": report.component,
                        }
                    ],
                    impact={"risk": "critical", "effort": "high", "benefit": "security"},
                    auto_applicable=False,
                    requires_founder_approval=True,
                    source={
                        "engine": "BugResponseHandler",
                        "report_id": report.report_id,
                        "category": "security",
                    },
                )
            )

        return recs

    # ------------------------------------------------------------------
    # Persistence & events
    # ------------------------------------------------------------------

    def _save_state(self) -> None:
        if self._persistence is None:
            return
        try:
            with self._lock:
                data = {"responses": [r.to_dict() for r in self._responses]}
            self._persistence.save_document(self._PERSISTENCE_DOC_KEY, data)
        except Exception as exc:
            logger.debug("BugResponseHandler: failed to save state: %s", exc)

    def _load_state(self) -> None:
        if self._persistence is None:
            return
        try:
            data = self._persistence.load_document(self._PERSISTENCE_DOC_KEY)
            if not data:
                return
            with self._lock:
                for r_dict in data.get("responses", []):
                    try:
                        self._responses.append(
                            BugResponse(
                                response_id=r_dict["response_id"],
                                report_id=r_dict["report_id"],
                                classified_severity=BugSeverity(r_dict["classified_severity"]),
                                category=BugCategory(r_dict["category"]),
                                root_cause_hypotheses=r_dict.get("root_cause_hypotheses", []),
                                suggested_actions=r_dict.get("suggested_actions", []),
                                response_draft=r_dict.get("response_draft", ""),
                                recommendation_ids=r_dict.get("recommendation_ids", []),
                                generated_at=datetime.fromisoformat(r_dict["generated_at"]),
                                related_pattern_ids=r_dict.get("related_pattern_ids", []),
                            )
                        )
                    except Exception as exc:
                        logger.debug("BugResponseHandler: failed to load response: %s", exc)
        except Exception as exc:
            logger.debug("BugResponseHandler: failed to load state: %s", exc)

    def _publish_event(self, report: BugReport, response: BugResponse) -> None:
        if self._event_backbone is None:
            return
        try:
            from event_backbone import EventType  # type: ignore

            self._event_backbone.publish(
                EventType.LEARNING_FEEDBACK,
                {
                    "source": "BugResponseHandler",
                    "report_id": report.report_id,
                    "response_id": response.response_id,
                    "severity": response.classified_severity.value,
                    "category": response.category.value,
                    "recommendations": response.recommendation_ids,
                },
            )
        except Exception as exc:
            logger.debug("BugResponseHandler: event publish failed: %s", exc)
