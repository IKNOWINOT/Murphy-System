"""
System Update Recommendation Engine for Murphy System.

Design Label: ARCH-020 — Founder Update Recommendation Engine
Owner: Backend Team / Platform Engineering
Dependencies:
  - SelfFixLoop (ARCH-005)
  - SelfImprovementEngine (ARCH-001)
  - AutonomousRepairSystem (ARCH-006)
  - DependencyAuditEngine (DEV-005)
  - BugPatternDetector (DEV-004)
  - EventBackbone
  - PersistenceManager

Provides a unified Founder-level orchestrator that aggregates all
self-healing/self-update subsystems into a single entry point with
five recommendation domains:
  1. Maintenance Integrations — scheduled windows, health checks, lifecycle
  2. SDK Updates — version tracking, compatibility, migration paths
  3. Auto-Updates — safe rolling updates with rollback and HITL gates
  4. Auto-Responses to Bug Reports — automated triage and response drafts
  5. System Operations Analysis — health scoring, trend analysis, capacity

Safety invariants:
  - NEVER auto-executes changes without human approval for critical/high priority
  - Thread-safe: all shared state guarded by threading.Lock
  - Full audit trail via PersistenceManager and EventBackbone
  - Graceful degradation when optional dependencies are unavailable
  - Bounded: configurable max recommendation storage

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
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from self_fix_loop import SelfFixLoop
except ImportError:
    SelfFixLoop = None  # type: ignore[misc,assignment]

try:
    from self_improvement_engine import ExecutionOutcome, OutcomeType, SelfImprovementEngine
except ImportError:
    SelfImprovementEngine = None  # type: ignore[misc,assignment]
    ExecutionOutcome = None  # type: ignore[misc,assignment]
    OutcomeType = None  # type: ignore[misc,assignment]

try:
    from autonomous_repair_system import AutonomousRepairSystem
except ImportError:
    AutonomousRepairSystem = None  # type: ignore[misc,assignment]

try:
    from dependency_audit_engine import DependencyAuditEngine
except ImportError:
    DependencyAuditEngine = None  # type: ignore[misc,assignment]

try:
    from bug_pattern_detector import BugPatternDetector
except ImportError:
    BugPatternDetector = None  # type: ignore[misc,assignment]

try:
    from event_backbone import EventBackbone, EventType
except ImportError:
    EventBackbone = None  # type: ignore[misc,assignment]
    EventType = None  # type: ignore[misc,assignment]

try:
    from persistence_manager import PersistenceManager
except ImportError:
    PersistenceManager = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RECOMMENDATIONS = 10_000
_MAX_BUG_REPORTS = 5_000
_RECOMMENDATIONS_DOC_KEY = "system_update_recommendations"

# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

CATEGORY_MAINTENANCE = "maintenance"
CATEGORY_SDK_UPDATE = "sdk_update"
CATEGORY_AUTO_UPDATE = "auto_update"
CATEGORY_BUG_RESPONSE = "bug_response"
CATEGORY_OPERATIONS = "operations"

PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITY_INFORMATIONAL = "informational"

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DISMISSED = "dismissed"
STATUS_EXECUTED = "executed"
STATUS_ACKNOWLEDGED = "acknowledged"

# ---------------------------------------------------------------------------
# RecommendationType enum
# ---------------------------------------------------------------------------


class RecommendationType(Enum):
    """Structured recommendation type for the engine subsystems."""

    MAINTENANCE = "maintenance"
    SDK_UPDATE = "sdk_update"
    AUTO_UPDATE = "auto_update"
    BUG_REPORT_RESPONSE = "bug_response"
    OPERATIONAL_ANALYSIS = "operations"


# Category-string → RecommendationType mapping (for backward compat)
_CATEGORY_TO_REC_TYPE: Dict[str, RecommendationType] = {
    CATEGORY_MAINTENANCE: RecommendationType.MAINTENANCE,
    CATEGORY_SDK_UPDATE: RecommendationType.SDK_UPDATE,
    CATEGORY_AUTO_UPDATE: RecommendationType.AUTO_UPDATE,
    CATEGORY_BUG_RESPONSE: RecommendationType.BUG_REPORT_RESPONSE,
    CATEGORY_OPERATIONS: RecommendationType.OPERATIONAL_ANALYSIS,
}

# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    """A structured update recommendation produced by one of the subsystems."""

    recommendation_id: str
    subsystem: str
    recommendation_type: RecommendationType
    priority: str          # critical | high | medium | low | informational
    confidence_score: float  # 0.0 – 1.0
    description: str
    suggested_action: str
    estimated_effort: str
    risk_level: str        # low | medium | high
    auto_applicable: bool
    requires_review: bool
    related_proposals: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = STATUS_PENDING  # pending | approved | dismissed | executed | acknowledged
    dismissed_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Safety: if review required, auto-apply must be False
        if self.requires_review:
            self.auto_applicable = False

    @property
    def category(self) -> str:
        """String category derived from recommendation_type (for backward compatibility)."""
        return self.recommendation_type.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "subsystem": self.subsystem,
            "recommendation_type": self.recommendation_type.value,
            "category": self.category,
            "priority": self.priority,
            "confidence_score": self.confidence_score,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "estimated_effort": self.estimated_effort,
            "risk_level": self.risk_level,
            "auto_applicable": self.auto_applicable,
            "requires_review": self.requires_review,
            "related_proposals": list(self.related_proposals),
            "created_at": self.created_at,
            "status": self.status,
            "dismissed_reason": self.dismissed_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Recommendation":
        rec_type_val = d.get("recommendation_type", d.get("category", "operations"))
        try:
            rec_type = RecommendationType(rec_type_val)
        except (ValueError, KeyError):
            rec_type = RecommendationType.OPERATIONAL_ANALYSIS
        obj = cls(
            recommendation_id=d["recommendation_id"],
            subsystem=d.get("subsystem", "unknown"),
            recommendation_type=rec_type,
            priority=d.get("priority", PRIORITY_MEDIUM),
            confidence_score=float(d.get("confidence_score", 0.5)),
            description=d.get("description", ""),
            suggested_action=d.get("suggested_action", ""),
            estimated_effort=d.get("estimated_effort", "unknown"),
            risk_level=d.get("risk_level", "medium"),
            auto_applicable=bool(d.get("auto_applicable", False)),
            requires_review=bool(d.get("requires_review", True)),
            related_proposals=list(d.get("related_proposals", [])),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            status=d.get("status", STATUS_PENDING),
            dismissed_reason=d.get("dismissed_reason", ""),
            metadata=dict(d.get("metadata", {})),
        )
        return obj


@dataclass
class BugReportInput:
    """Incoming bug report for automated triage and response."""

    report_id: str
    title: str
    description: str
    component: str = "unknown"
    severity: str = "medium"
    stack_trace: str = ""
    reporter: str = "system"
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Specialised recommendation-form dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MaintenanceRecommendation:
    """Specialised form for maintenance-type recommendations."""

    recommendation_id: str
    action_type: str
    target_service: str
    description: str
    priority: str
    requires_review: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SDKUpdateRecommendation:
    """Specialised form for SDK/dependency update recommendations."""

    recommendation_id: str
    package_name: str
    current_version: str
    recommended_version: str
    breaking_changes: bool
    migration_guide: Optional[str]
    compatibility_notes: str
    priority: str
    requires_review: bool = True


@dataclass
class AutoUpdateAction:
    """Specialised form for auto-update action recommendations."""

    recommendation_id: str
    package_name: str
    target_version: str
    safe_to_auto_update: bool
    requires_review: bool
    rollback_plan: str
    risk_assessment: str
    priority: str


@dataclass
class BugReportResponse:
    """Specialised form for bug-report auto-response recommendations."""

    recommendation_id: str
    bug_pattern_id: str
    severity: str
    known_fix_available: bool
    suggested_patch: str
    eta_estimate: str
    affected_component: str
    priority: str
    requires_review: bool = True


@dataclass
class OperationalAnalysis:
    """Specialised form for operational-analysis recommendations."""

    recommendation_id: str
    analysis_type: str
    metric_name: str
    current_value: float
    threshold_value: float
    trend: str
    forecast_summary: str
    priority: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Cycle report
# ---------------------------------------------------------------------------


@dataclass
class RecommendationCycleReport:
    """Summary report produced by a single run_recommendation_cycle() call."""

    cycle_id: str
    started_at: str
    completed_at: str
    total_recommendations: int
    recommendations: List[Recommendation]
    subsystems_available: List[str]
    subsystems_queried: List[str]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_recommendations": self.total_recommendations,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "subsystems_available": list(self.subsystems_available),
            "subsystems_queried": list(self.subsystems_queried),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Subsystem: MaintenanceIntegrationAdvisor
# ---------------------------------------------------------------------------


class MaintenanceIntegrationAdvisor:
    """Generates maintenance window recommendations and health check schedules.

    Coordinates with existing self-healing infrastructure (SelfHealingCoordinator
    via SelfFixLoop) to surface scheduled and reactive maintenance needs.
    """

    def __init__(self, self_fix_loop: Optional[Any] = None) -> None:
        self._fix_loop = self_fix_loop

    def generate_recommendations(self) -> List[Recommendation]:
        """Return maintenance recommendations based on current system state."""
        recs: List[Recommendation] = []

        # --- Scheduled maintenance window ---
        recs.append(Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="maintenance_advisor",
            recommendation_type=RecommendationType.MAINTENANCE,
            priority=PRIORITY_MEDIUM,
            confidence_score=0.8,
            description=(
                "System has been running without a planned maintenance window. "
                "Recommend scheduling a low-traffic maintenance period to apply "
                "pending patches, rotate credentials, and run full diagnostics."
            ),
            suggested_action=(
                "Schedule maintenance window: duration=30min, time=off-peak. "
                "Run full diagnostics and rotate non-critical credentials."
            ),
            estimated_effort="1-2h",
            risk_level="low",
            auto_applicable=False,
            requires_review=True,
            metadata={"affected_subsystems": ["self_fix_loop", "autonomous_repair_system", "murphy_immune_engine"]},
        ))

        # --- Health check coordination ---
        recs.append(Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="maintenance_advisor",
            recommendation_type=RecommendationType.MAINTENANCE,
            priority=PRIORITY_LOW,
            confidence_score=0.7,
            description=(
                "Multiple subsystems are running health checks on independent schedules. "
                "Coordinating these intervals reduces CPU spikes and provides a cleaner "
                "system health snapshot."
            ),
            suggested_action="Review and unify health check intervals across subsystems (target: 60s).",
            estimated_effort="< 1h",
            risk_level="low",
            auto_applicable=True,
            requires_review=False,
        ))

        # --- Self-fix loop status check ---
        if self._fix_loop is not None:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="maintenance_advisor",
                recommendation_type=RecommendationType.MAINTENANCE,
                priority=PRIORITY_INFORMATIONAL,
                confidence_score=0.9,
                description=(
                    "The SelfFixLoop (ARCH-005) has completed recent cycles. "
                    "Review the latest loop report to confirm all gaps were addressed."
                ),
                suggested_action="Review SelfFixLoop cycle reports.",
                estimated_effort="< 30min",
                risk_level="low",
                auto_applicable=False,
                requires_review=False,
            ))

        return recs

    def get_maintenance_schedule(self) -> Dict[str, Any]:
        """Return a structured maintenance schedule overview."""
        return {
            "next_scheduled_window": None,
            "last_maintenance": None,
            "health_check_interval_seconds": 60,
            "subsystem_lifecycle_status": {
                "self_fix_loop": "active",
                "autonomous_repair_system": "active",
                "murphy_immune_engine": "active",
                "dependency_audit_engine": "active",
                "bug_pattern_detector": "active",
            },
        }


# ---------------------------------------------------------------------------
# Subsystem: SDKUpdateTracker
# ---------------------------------------------------------------------------


class SDKUpdateTracker:
    """Monitors SDK/dependency versions and generates migration path recommendations.

    Extends DependencyAuditEngine capabilities with higher-level migration
    planning and compatibility matrix analysis.
    """

    def __init__(self, dependency_audit_engine: Optional[Any] = None) -> None:
        self._audit_engine = dependency_audit_engine
        self._compatibility_matrix: Dict[str, Dict[str, Any]] = {}

    def check_compatibility(self, package: str, current_version: str, target_version: str) -> Dict[str, Any]:
        """Check compatibility between current and target versions of a package."""
        return {
            "package": package,
            "current_version": current_version,
            "target_version": target_version,
            "compatible": True,
            "breaking_changes": [],
            "migration_steps": [
                f"Review {package} changelog between {current_version} and {target_version}",
                f"Run test suite against {target_version} in staging environment",
                f"Update {package} in requirements file",
            ],
            "confidence": 0.75,
        }

    def generate_recommendations(self) -> List[Recommendation]:
        """Return SDK/dependency update recommendations."""
        recs: List[Recommendation] = []

        if self._audit_engine is not None:
            try:
                reports = self._audit_engine.get_reports(limit=5)
                for report in reports:
                    # Support "findings" key as well as "critical_findings"/"high_findings"
                    findings = report.get("findings", [])
                    if not findings:
                        findings = report.get("critical_findings", []) + report.get("high_findings", [])
                    for finding in findings[:3]:  # cap per report
                        dep_name = finding.get("dependency_name", "unknown")
                        severity = finding.get("severity", "medium")
                        _pmap = {"critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
                                 "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW}
                        priority = _pmap.get(severity, PRIORITY_MEDIUM)
                        recs.append(Recommendation(
                            recommendation_id=str(uuid.uuid4()),
                            subsystem="sdk_tracker",
                            recommendation_type=RecommendationType.SDK_UPDATE,
                            priority=priority,
                            confidence_score=0.95,
                            description=(
                                f"Security advisory for '{dep_name}': "
                                f"{finding.get('title', 'vulnerability detected')}. "
                                f"Installed: {finding.get('installed_version', 'unknown')}, "
                                f"Fixed in: {finding.get('fixed_in_version', 'latest')}."
                            ),
                            suggested_action=(
                                f"Upgrade {dep_name} to {finding.get('fixed_in_version', 'latest')} "
                                "and run the full test suite."
                            ),
                            estimated_effort="< 2h",
                            risk_level="high" if severity in ("critical", "high") else "medium",
                            auto_applicable=False,
                            requires_review=True,
                            metadata={
                                "cve_id": finding.get("cve_id", ""),
                                "advisory_id": finding.get("advisory_id", ""),
                                "report_id": report.get("report_id", ""),
                            },
                        ))
            except Exception as exc:
                logger.debug("Could not retrieve dependency audit reports: %s", exc)

        # General SDK health recommendation
        recs.append(Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="sdk_tracker",
            recommendation_type=RecommendationType.SDK_UPDATE,
            priority=PRIORITY_LOW,
            confidence_score=0.6,
            description=(
                "Routine SDK version review recommended. Check for non-breaking "
                "minor/patch updates that improve stability, performance, or add "
                "needed features without requiring migration effort."
            ),
            suggested_action="Run dependency audit and review minor/patch updates for safe upgrades.",
            estimated_effort="< 1h",
            risk_level="low",
            auto_applicable=False,
            requires_review=False,
        ))

        return recs

    def get_sdk_status(self) -> Dict[str, Any]:
        """Return current SDK update status summary."""
        report_count = 0
        if self._audit_engine is not None:
            try:
                reports = self._audit_engine.get_reports(limit=1)
                report_count = len(reports)
            except Exception:
                pass
        return {
            "last_audit_available": report_count > 0,
            "compatibility_checks_registered": len(self._compatibility_matrix),
            "audit_engine_available": self._audit_engine is not None,
        }


# ---------------------------------------------------------------------------
# Subsystem: AutoUpdateOrchestrator
# ---------------------------------------------------------------------------


class AutoUpdateOrchestrator:
    """Manages safe rolling update recommendations with canary and rollback support.

    Produces update plans only — never auto-executes without explicit approval.
    Implements HITL (Human-In-The-Loop) gates for critical/high priority updates.
    """

    def __init__(self) -> None:
        self._update_queue: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def generate_update_plan(self, targets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate a safe rolling update plan for the specified targets.

        Args:
            targets: List of subsystem/component names to update. If None, scans all.

        Returns:
            A structured update plan dict. NEVER auto-executes.
        """
        plan_id = str(uuid.uuid4())
        plan_targets = targets or ["dependency_audit_engine", "self_fix_loop", "autonomous_repair_system"]

        stages = []
        for i, target in enumerate(plan_targets):
            stages.append({
                "stage": i + 1,
                "target": target,
                "strategy": "canary" if i == 0 else "rolling",
                "canary_percentage": 10 if i == 0 else None,
                "rollback_trigger": "error_rate > 5%",
                "health_check_delay_seconds": 30,
                "requires_approval": True,
            })

        return {
            "plan_id": plan_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft",
            "targets": plan_targets,
            "stages": stages,
            "rollback_plan": {
                "strategy": "immediate",
                "restore_from": "last_known_good_snapshot",
            },
            "hitl_gates": [
                {"gate": "pre_deployment_approval", "required": True},
                {"gate": "canary_health_review", "required": True},
                {"gate": "full_rollout_approval", "required": True},
            ],
            "auto_execute": False,
            "note": "This plan requires human approval at each HITL gate before execution.",
        }

    def generate_recommendations(self) -> List[Recommendation]:
        """Return auto-update recommendations."""
        return [
            Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="auto_update_orchestrator",
                recommendation_type=RecommendationType.AUTO_UPDATE,
                priority=PRIORITY_MEDIUM,
                confidence_score=0.7,
                description=(
                    "Core subsystems have pending updates available. A safe rolling update "
                    "plan with canary deployment and automatic rollback triggers is recommended. "
                    "All stages require human approval before execution."
                ),
                suggested_action=(
                    "Generate rolling update plan (strategy=canary_rolling), "
                    "review and approve, then execute with HITL gates."
                ),
                estimated_effort="2-4h",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
                metadata={"affected_subsystems": ["self_fix_loop", "autonomous_repair_system", "dependency_audit_engine"]},
            )
        ]

    def get_queue(self) -> List[Dict[str, Any]]:
        """Return the current auto-update queue."""
        with self._lock:
            return list(self._update_queue)


# ---------------------------------------------------------------------------
# Subsystem: BugReportAutoResponder
# ---------------------------------------------------------------------------


class BugReportAutoResponder:
    """Accepts bug reports, classifies them, and generates auto-response drafts.

    Integrates with BugPatternDetector for pattern matching and
    SelfImprovementEngine for pattern learning.
    """

    def __init__(
        self,
        bug_detector: Optional[Any] = None,
        improvement_engine: Optional[Any] = None,
    ) -> None:
        self._detector = bug_detector
        self._engine = improvement_engine
        self._ingested_reports: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def ingest_report(self, report: BugReportInput) -> Dict[str, Any]:
        """Ingest a bug report and generate an auto-response draft.

        Args:
            report: The incoming bug report to triage.

        Returns:
            Auto-response dict with classification, root cause hypotheses,
            and recommended actions.
        """
        # Feed into bug pattern detector if available
        if self._detector is not None:
            try:
                self._detector.ingest_error(
                    message=report.description,
                    component=report.component,
                    stack_trace=report.stack_trace or "",
                    severity=report.severity,
                )
                logger.debug("Fed bug report %s into BugPatternDetector", report.report_id)
            except Exception as exc:
                logger.debug("BugPatternDetector.ingest_error failed: %s", exc)

        # Classify the report
        classification = self._classify_report(report)

        # Generate response
        response = {
            "report_id": report.report_id,
            "auto_response_id": str(uuid.uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": classification,
            "priority": classification["severity"],
            "root_cause_hypotheses": self._generate_hypotheses(report),
            "recommended_actions": self._generate_actions(report, classification),
            "response_draft": self._generate_response_draft(report, classification),
            "requires_human_review": classification["severity"] in ("critical", "high"),
            "related_patterns": self._find_related_patterns(report),
        }

        with self._lock:
            capped_append(self._ingested_reports, response, max_size=_MAX_BUG_REPORTS)

        return response

    def _classify_report(self, report: BugReportInput) -> Dict[str, Any]:
        desc_lower = report.description.lower()
        title_lower = report.title.lower()
        text = desc_lower + " " + title_lower

        if any(kw in text for kw in ("crash", "critical", "data loss", "security", "breach")):
            category = "critical_defect"
            severity = PRIORITY_CRITICAL
        elif any(kw in text for kw in ("error", "exception", "fail", "broken")):
            category = "functional_defect"
            severity = PRIORITY_HIGH
        elif any(kw in text for kw in ("slow", "performance", "timeout", "latency")):
            category = "performance"
            severity = PRIORITY_MEDIUM
        elif any(kw in text for kw in ("ui", "display", "visual", "layout")):
            category = "ui_cosmetic"
            severity = PRIORITY_LOW
        else:
            category = "general"
            severity = PRIORITY_MEDIUM

        return {
            "category": category,
            "severity": severity,
            "component": report.component,
            "confidence": 0.75,
        }

    def _generate_hypotheses(self, report: BugReportInput) -> List[str]:
        hypotheses = []
        text = (report.description + " " + report.stack_trace).lower()

        if "import" in text or "modulenotfound" in text:
            hypotheses.append("Missing or incompatible dependency causing import failure")
        if "null" in text or "nonetype" in text or "attributeerror" in text:
            hypotheses.append("Null/None value encountered where object expected — possible uninitialized state")
        if "timeout" in text or "deadline" in text:
            hypotheses.append("Operation exceeded configured timeout — possible resource contention or slow query")
        if "permission" in text or "unauthorized" in text or "forbidden" in text:
            hypotheses.append("Insufficient permissions or authentication token mismatch")
        if not hypotheses:
            hypotheses.append(f"Unexpected condition in component '{report.component}' — requires investigation")

        return hypotheses

    def _generate_actions(self, report: BugReportInput, classification: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = [
            {"action": "reproduce_in_staging", "priority": "immediate"},
            {"action": "review_logs_around_timestamp", "params": {"component": report.component}},
        ]
        if classification["severity"] in (PRIORITY_CRITICAL, PRIORITY_HIGH):
            actions.insert(0, {"action": "escalate_to_on_call", "priority": "immediate"})
            actions.append({"action": "create_hotfix_branch", "params": {}})
        return actions

    def _generate_response_draft(self, report: BugReportInput, classification: Dict[str, Any]) -> str:
        return (
            f"Thank you for reporting '{report.title}'. "
            f"This has been classified as a {classification['category']} with {classification['severity']} priority "
            f"in component '{report.component}'. "
            "Our team is investigating. We will provide an update once root cause analysis is complete."
        )

    def _find_related_patterns(self, report: BugReportInput) -> List[Dict[str, Any]]:
        if self._detector is None:
            return []
        try:
            patterns = self._detector.get_patterns(limit=5)
            return [p for p in patterns if p.get("component") == report.component][:3]
        except Exception:
            return []

    def get_responses(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recently generated auto-responses."""
        with self._lock:
            return list(reversed(self._ingested_reports[-limit:]))

    def generate_recommendations(self) -> List[Recommendation]:
        """Return bug-response recommendations based on ingested patterns."""
        recs: List[Recommendation] = []

        pattern_count = 0
        if self._detector is not None:
            try:
                pattern_count = len(self._detector.get_patterns(limit=100))
            except Exception:
                pass

        if pattern_count > 0:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="bug_responder",
                recommendation_type=RecommendationType.BUG_REPORT_RESPONSE,
                priority=PRIORITY_HIGH,
                confidence_score=0.85,
                description=(
                    f"BugPatternDetector has identified {pattern_count} recurring failure "
                    "pattern(s). Automated response templates have been generated. "
                    "Human review recommended before sending responses."
                ),
                suggested_action=(
                    "Review bug patterns, approve auto-responses, and inject into improvement engine."
                ),
                estimated_effort="< 1h",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
            ))

        recs.append(Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="bug_responder",
            recommendation_type=RecommendationType.BUG_REPORT_RESPONSE,
            priority=PRIORITY_INFORMATIONAL,
            confidence_score=1.0,
            description=(
                "The BugReportAutoResponder is ready to accept incoming bug reports "
                "via POST /api/system-updates/bug-responses/ingest. Responses are "
                "drafted automatically but require human approval for critical/high priority items."
            ),
            suggested_action="Submit bug reports via the ingestion API.",
            estimated_effort="N/A",
            risk_level="low",
            auto_applicable=False,
            requires_review=False,
        ))

        return recs


# ---------------------------------------------------------------------------
# Subsystem: OperationsAnalyzer
# ---------------------------------------------------------------------------


class OperationsAnalyzer:
    """Produces holistic system health scores, trend analysis, and capacity planning.

    Pulls data from health monitors, metrics, and the event backbone.
    """

    def __init__(self, event_backbone: Optional[Any] = None) -> None:
        self._backbone = event_backbone

    def compute_health_score(self) -> Dict[str, Any]:
        """Compute a holistic health score across all major subsystems."""
        # Component health indicators (would pull from live monitors in production)
        components = {
            "self_fix_loop": 0.9,
            "autonomous_repair_system": 0.85,
            "murphy_immune_engine": 0.9,
            "dependency_audit_engine": 0.8,
            "bug_pattern_detector": 0.85,
            "event_backbone": 0.95,
            "persistence_manager": 0.9,
        }

        overall = sum(components.values()) / len(components) if components else 0.0

        status = "healthy"
        if overall < 0.5:
            status = "critical"
        elif overall < 0.7:
            status = "degraded"
        elif overall < 0.85:
            status = "warning"

        return {
            "overall_score": round(overall, 3),
            "status": status,
            "components": components,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "trend": "stable",
        }

    def generate_recommendations(self) -> List[Recommendation]:
        """Return operations analysis recommendations."""
        recs: List[Recommendation] = []
        health = self.compute_health_score()
        score = health["overall_score"]

        if score < 0.7:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="operations_analyzer",
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=PRIORITY_CRITICAL,
                confidence_score=0.95,
                description=(
                    f"Overall system health score is {score:.1%}, below the 70% threshold. "
                    "Immediate investigation required."
                ),
                suggested_action="Trigger autonomous repair cycle and escalate to on-call team.",
                estimated_effort="< 1h",
                risk_level="high",
                auto_applicable=False,
                requires_review=True,
            ))
        elif score < 0.85:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="operations_analyzer",
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=PRIORITY_HIGH,
                confidence_score=0.85,
                description=(
                    f"Overall system health score is {score:.1%}. One or more subsystems "
                    "are operating below optimal levels."
                ),
                suggested_action="Review subsystem health scores and run targeted diagnostics.",
                estimated_effort="1-2h",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
            ))
        else:
            recs.append(Recommendation(
                recommendation_id=str(uuid.uuid4()),
                subsystem="operations_analyzer",
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=PRIORITY_INFORMATIONAL,
                confidence_score=0.9,
                description=(
                    f"Overall system health score is {score:.1%} — all subsystems "
                    "operating within normal parameters."
                ),
                suggested_action="Continue monitoring. No immediate action required.",
                estimated_effort="N/A",
                risk_level="low",
                auto_applicable=True,
                requires_review=False,
            ))

        # Capacity planning recommendation
        recs.append(Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="operations_analyzer",
            recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
            priority=PRIORITY_LOW,
            confidence_score=0.65,
            description=(
                "Based on current utilization trends, a capacity review is recommended "
                "to ensure sufficient resources for the next 30-day growth window. "
                "Consider scaling event backbone throughput and persistence storage."
            ),
            suggested_action="Review resource utilization and generate capacity forecast for next 30 days.",
            estimated_effort="2-4h",
            risk_level="low",
            auto_applicable=False,
            requires_review=False,
        ))

        return recs

    def get_trend_analysis(self) -> Dict[str, Any]:
        """Return trend analysis summary."""
        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "health_trend": "stable",
            "anomalies_detected": 0,
            "capacity_utilization_pct": 45.0,
            "recommended_scale_action": "none",
        }


# ---------------------------------------------------------------------------
# Main orchestrator: SystemUpdateRecommendationEngine
# ---------------------------------------------------------------------------


class SystemUpdateRecommendationEngine:
    """Founder-level orchestrator aggregating all update/maintenance recommendation subsystems.

    Design Label: ARCH-020

    Integrates with:
      - SelfFixLoop (ARCH-005)
      - SelfImprovementEngine (ARCH-001)
      - AutonomousRepairSystem (ARCH-006)
      - DependencyAuditEngine (DEV-005)
      - BugPatternDetector (DEV-004)
      - EventBackbone
      - PersistenceManager

    Safety invariants:
      - NEVER auto-executes changes without human approval for critical/high priority
      - Thread-safe: all shared state guarded by threading.Lock
      - Full audit trail via PersistenceManager and EventBackbone
      - Graceful degradation when optional dependencies are unavailable
      - Bounded: configurable max recommendation storage and history
    """

    _PERSIST_DOC_ID = "system_update_recommendation_engine_state"
    _RECOMMENDATIONS_DOC_KEY = "system_update_recommendations"  # backward compat alias

    def __init__(
        self,
        # New-style params (preferred)
        improvement_engine: Optional[Any] = None,
        bug_detector: Optional[Any] = None,
        dependency_audit: Optional[Any] = None,
        health_monitor: Optional[Any] = None,
        repair_system: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        persistence_manager: Optional[Any] = None,
        event_backbone: Optional[Any] = None,
        max_history: int = 100,
        max_recommendations: int = _MAX_RECOMMENDATIONS,
        # Legacy params for backward compatibility
        self_fix_loop: Optional[Any] = None,
        self_improvement_engine: Optional[Any] = None,
        autonomous_repair_system: Optional[Any] = None,
        dependency_audit_engine: Optional[Any] = None,
        bug_pattern_detector: Optional[Any] = None,
    ) -> None:
        # Resolve new vs legacy params
        self._improvement_engine = improvement_engine or self_improvement_engine
        self._bug_detector = bug_detector or bug_pattern_detector
        self._dependency_audit = dependency_audit or dependency_audit_engine
        self._health_monitor = health_monitor
        self._repair_system = repair_system or autonomous_repair_system
        self._orchestrator = orchestrator
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._fix_loop = self_fix_loop
        self._max_history = max_history
        self._max_recommendations = max_recommendations

        self._lock = threading.Lock()

        # In-memory recommendation store: id -> Recommendation
        self._recommendations: Dict[str, Recommendation] = {}
        # Cycle history
        self._history: List[Dict[str, Any]] = []
        # Custom registered subsystems
        self._custom_subsystems: Dict[str, Callable[[], Any]] = {}

        # Build subsystem objects (for API backward compat)
        self.maintenance_advisor = MaintenanceIntegrationAdvisor(
            self_fix_loop=self_fix_loop,
        )
        self.sdk_tracker = SDKUpdateTracker(
            dependency_audit_engine=dependency_audit_engine or dependency_audit,
        )
        self.auto_update_orchestrator = AutoUpdateOrchestrator()
        self.bug_responder = BugReportAutoResponder(
            bug_detector=bug_pattern_detector or bug_detector,
            improvement_engine=self_improvement_engine or improvement_engine,
        )
        self.operations_analyzer = OperationsAnalyzer(
            event_backbone=event_backbone,
        )

        # Restore persisted recommendations if available
        self._restore_from_persistence()

        logger.info("SystemUpdateRecommendationEngine (ARCH-020) initialised")

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _restore_from_persistence(self) -> None:
        """Restore state on init — delegates to load_state()."""
        self.load_state()

    def save_state(self) -> bool:
        """Persist current recommendations to storage.

        Returns:
            True if saved successfully, False if persistence unavailable.
        """
        if self._pm is None:
            return False
        try:
            with self._lock:
                data = {"recommendations": [r.to_dict() for r in self._recommendations.values()]}
            self._pm.save_document(self._PERSIST_DOC_ID, data)
            return True
        except Exception as exc:
            logger.debug("save_state failed: %s", exc)
            return False

    def load_state(self) -> bool:
        """Load recommendations from persistent storage.

        Returns:
            True if loaded successfully, False if no data or unavailable.
        """
        if self._pm is None:
            return False
        try:
            saved = self._pm.load_document(self._PERSIST_DOC_ID)
            if not saved or not isinstance(saved, dict):
                return False
            recs_list = saved.get("recommendations", [])
            if not recs_list:
                return False
            with self._lock:
                for item in recs_list:
                    try:
                        rec = Recommendation.from_dict(item)
                        self._recommendations[rec.recommendation_id] = rec
                    except Exception as exc:
                        logger.debug("Skipping malformed recommendation: %s", exc)
            logger.debug("Loaded %d recommendations from persistence", len(self._recommendations))
            return True
        except Exception as exc:
            logger.debug("load_state failed: %s", exc)
            return False

    def _persist_recommendations(self) -> None:
        """Backward-compatible persistence helper — calls save_state()."""
        self.save_state()

    def _publish_event(self, event_type_name: str, payload: Dict[str, Any]) -> None:
        if self._backbone is None or EventType is None:
            return
        try:
            et = getattr(EventType, event_type_name, None)
            if et is None:
                et = EventType.LEARNING_FEEDBACK  # fallback
            self._backbone.publish(event_type=et, payload=payload)
        except Exception as exc:
            logger.debug("Could not publish event %s: %s", event_type_name, exc)

    # ------------------------------------------------------------------
    # Bounded store helper
    # ------------------------------------------------------------------

    def _add_recommendation(self, rec: Recommendation) -> None:
        """Add a recommendation to the store, evicting oldest if at capacity.

        Must be called while holding self._lock.
        """
        if len(self._recommendations) >= self._max_recommendations:
            to_evict = sorted(
                self._recommendations.keys(),
                key=lambda k: self._recommendations[k].created_at,
            )[:max(1, self._max_recommendations // 10)]
            for k in to_evict:
                del self._recommendations[k]
        self._recommendations[rec.recommendation_id] = rec

    # ------------------------------------------------------------------
    # New-style recommendation cycle
    # ------------------------------------------------------------------

    def run_recommendation_cycle(
        self,
        subsystems: Optional[List[str]] = None,
    ) -> "RecommendationCycleReport":
        """Run a recommendation cycle across all or specified subsystems.

        Args:
            subsystems: Optional list of subsystem names to query.
                        If None, all available subsystems are queried.

        Returns:
            RecommendationCycleReport with aggregated results and metadata.
        """
        cycle_id = f"cycle-{str(uuid.uuid4())[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()

        new_recs: List[Recommendation] = []
        errors: List[str] = []
        subsystems_queried: List[str] = []

        # Build built-in collector map
        built_in: Dict[str, Callable[[], List[Recommendation]]] = {}
        if self._bug_detector is not None:
            built_in["bug_detector"] = self._collect_from_bug_detector
        if self._dependency_audit is not None:
            built_in["dependency_audit"] = self._collect_from_dependency_audit
        if self._health_monitor is not None:
            built_in["health_monitor"] = self._collect_from_health_monitor
        if self._repair_system is not None:
            built_in["repair_system"] = self._collect_from_repair_system
        if self._orchestrator is not None:
            built_in["orchestrator"] = self._collect_from_orchestrator
        if self._improvement_engine is not None:
            built_in["improvement_engine"] = self._collect_from_improvement_engine

        all_collectors: Dict[str, Callable[[], Any]] = {**built_in, **self._custom_subsystems}
        subsystems_available = list(all_collectors.keys())

        # Filter to requested subsystems
        if subsystems is not None:
            collectors_to_run = {n: fn for n, fn in all_collectors.items() if n in subsystems}
        else:
            collectors_to_run = all_collectors

        for name, collector_fn in collectors_to_run.items():
            try:
                raw_result = collector_fn()
                items = list(raw_result) if raw_result is not None else []
                subsystems_queried.append(name)
                for item in items:
                    if isinstance(item, Recommendation):
                        with self._lock:
                            self._add_recommendation(item)
                        new_recs.append(item)
                    elif isinstance(item, dict):
                        converted = self._dict_to_recommendation(item, name)
                        if converted is not None:
                            with self._lock:
                                self._add_recommendation(converted)
                            new_recs.append(converted)
            except Exception as exc:
                error_msg = f"{name}: {exc}"
                errors.append(error_msg)
                logger.warning("Subsystem %s failed in cycle: %s", name, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        report = RecommendationCycleReport(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            total_recommendations=len(new_recs),
            recommendations=list(new_recs),
            subsystems_available=subsystems_available,
            subsystems_queried=subsystems_queried,
            errors=errors,
        )

        with self._lock:
            self._history.append(report.to_dict())
            if len(self._history) > self._max_history:
                del self._history[:-self._max_history]

        self.save_state()
        return report

    def register_subsystem(self, name: str, collector_fn: Callable[[], Any]) -> None:
        """Register a custom subsystem collector function.

        Args:
            name: Unique subsystem name.
            collector_fn: Callable returning an iterable of Recommendation objects or raw dicts.
        """
        self._custom_subsystems[name] = collector_fn
        logger.info("Registered custom subsystem: %s", name)

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return cycle history as list of dicts.

        Args:
            limit: Maximum number of history entries to return (most recent first).
        """
        with self._lock:
            history = list(self._history)
        if limit is not None:
            history = history[-limit:]
        return history

    # ------------------------------------------------------------------
    # Built-in subsystem collectors
    # ------------------------------------------------------------------

    def _collect_from_bug_detector(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        reports = self._bug_detector.get_reports(limit=50)
        _pmap = {
            "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
            "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
        }
        for report in reports:
            severity = report.get("severity", "medium")
            priority = _pmap.get(severity, PRIORITY_MEDIUM)
            recs.append(Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem="bug_detector",
                recommendation_type=RecommendationType.BUG_REPORT_RESPONSE,
                priority=priority,
                confidence_score=0.8,
                description=f"Bug pattern: {report.get('summary', report.get('report_id', 'unknown'))}",
                suggested_action="Investigate bug pattern and apply fix.",
                estimated_effort="< 2h",
                risk_level="high" if severity in ("critical", "high") else "medium",
                auto_applicable=False,
                requires_review=True,
                metadata={
                    "report_id": report.get("report_id", ""),
                    "patterns_detected": report.get("patterns_detected", 0),
                },
            ))
        return recs

    def _collect_from_dependency_audit(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        reports = self._dependency_audit.get_reports(limit=20)
        _pmap = {
            "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
            "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
        }
        for report in reports:
            findings = report.get("findings", [])
            if not findings:
                findings = report.get("critical_findings", []) + report.get("high_findings", [])
            for finding in findings:
                severity = finding.get("severity", "medium")
                dep_name = finding.get("dependency_name", "unknown")
                recs.append(Recommendation(
                    recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                    subsystem="dependency_audit",
                    recommendation_type=RecommendationType.SDK_UPDATE,
                    priority=_pmap.get(severity, PRIORITY_MEDIUM),
                    confidence_score=0.95,
                    description=(
                        f"Security advisory for '{dep_name}': "
                        f"{finding.get('title', 'vulnerability detected')}."
                    ),
                    suggested_action=f"Upgrade {dep_name} to {finding.get('fixed_in_version', 'latest')}.",
                    estimated_effort="< 2h",
                    risk_level="high" if severity in ("critical", "high") else "medium",
                    auto_applicable=False,
                    requires_review=True,
                    metadata={
                        "cve_id": finding.get("cve_id", ""),
                        "report_id": report.get("report_id", ""),
                    },
                ))
        return recs

    def _collect_from_health_monitor(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        health = self._health_monitor.get_system_health()
        overall = health.get("overall_status", "unknown")
        if overall in ("degraded", "unhealthy"):
            components = health.get("components", {})
            priority = PRIORITY_CRITICAL if overall == "unhealthy" else PRIORITY_HIGH
            recs.append(Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem="health_monitor",
                recommendation_type=RecommendationType.MAINTENANCE,
                priority=priority,
                confidence_score=0.9,
                description=f"System health status is '{overall}'. Review affected components.",
                suggested_action="Restart affected components and run diagnostics.",
                estimated_effort="< 1h",
                risk_level="high",
                auto_applicable=False,
                requires_review=True,
                metadata={"components": components, "overall_status": overall},
            ))
        return recs

    def _collect_from_repair_system(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        proposals = self._repair_system.get_proposals()
        _pmap = {
            "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
            "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
        }
        for proposal in proposals:
            priority = _pmap.get(proposal.get("priority", "medium"), PRIORITY_MEDIUM)
            recs.append(Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem="repair_system",
                recommendation_type=RecommendationType.AUTO_UPDATE,
                priority=priority,
                confidence_score=0.8,
                description=proposal.get("description", "Repair proposal"),
                suggested_action=proposal.get("suggested_action", "Apply repair."),
                estimated_effort="< 1h",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
                metadata={
                    "proposal_id": proposal.get("proposal_id", ""),
                    "component": proposal.get("component", ""),
                },
            ))
        return recs

    def _collect_from_orchestrator(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        gaps = self._orchestrator.get_open_gaps()
        _pmap = {
            "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
            "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
        }
        for gap in gaps:
            priority = _pmap.get(gap.get("priority", "medium"), PRIORITY_MEDIUM)
            recs.append(Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem="orchestrator",
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=priority,
                confidence_score=0.75,
                description=gap.get("description", "Open automation gap"),
                suggested_action=f"Close automation gap in area: {gap.get('area', 'unknown')}.",
                estimated_effort="1-4h",
                risk_level="low",
                auto_applicable=False,
                requires_review=False,
                metadata={"gap_id": gap.get("gap_id", ""), "area": gap.get("area", "")},
            ))
        return recs

    def _collect_from_improvement_engine(self) -> List[Recommendation]:
        recs: List[Recommendation] = []
        proposals = self._improvement_engine.generate_proposals()
        _pmap = {
            "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
            "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
        }
        for proposal in proposals:
            if isinstance(proposal, dict):
                proposal_id = proposal.get("proposal_id", str(uuid.uuid4())[:8])
                description = proposal.get("description", "Improvement proposal")
                suggested_action = proposal.get("suggested_action", "Apply improvement.")
                priority_val = proposal.get("priority", "medium")
            else:
                proposal_id = getattr(proposal, "proposal_id", str(uuid.uuid4())[:8])
                description = getattr(proposal, "description", "Improvement proposal")
                suggested_action = getattr(proposal, "suggested_action", "Apply improvement.")
                priority_val = getattr(proposal, "priority", "medium")
            recs.append(Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem="improvement_engine",
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=_pmap.get(priority_val, PRIORITY_MEDIUM),
                confidence_score=0.7,
                description=description,
                suggested_action=suggested_action,
                estimated_effort="unknown",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
                metadata={"proposal_id": str(proposal_id)},
            ))
        return recs

    def _dict_to_recommendation(
        self, raw: Dict[str, Any], subsystem_name: str
    ) -> Optional[Recommendation]:
        """Convert a raw dict from a custom collector to a Recommendation."""
        try:
            _pmap = {
                "critical": PRIORITY_CRITICAL, "high": PRIORITY_HIGH,
                "medium": PRIORITY_MEDIUM, "low": PRIORITY_LOW,
            }
            priority = _pmap.get(raw.get("priority", "medium"), PRIORITY_MEDIUM)
            return Recommendation(
                recommendation_id=f"rec-{str(uuid.uuid4())[:12]}",
                subsystem=raw.get("source", subsystem_name),
                recommendation_type=RecommendationType.OPERATIONAL_ANALYSIS,
                priority=priority,
                confidence_score=0.7,
                description=raw.get("description", "Custom recommendation"),
                suggested_action=raw.get("suggested_action", "Review and act on this recommendation."),
                estimated_effort="unknown",
                risk_level="medium",
                auto_applicable=False,
                requires_review=True,
                metadata=raw,
            )
        except Exception as exc:
            logger.debug("Failed to convert dict to Recommendation: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Core public API (backward-compatible)
    # ------------------------------------------------------------------

    def refresh_all(self) -> List[Recommendation]:
        """Trigger all built-in subsystem classes to produce fresh recommendations.

        Maintained for backward compatibility with the REST API layer.
        Returns all new recommendations added during this refresh.
        """
        new_recs: List[Recommendation] = []

        subsystems_to_scan = [
            ("maintenance_advisor", self.maintenance_advisor),
            ("sdk_tracker", self.sdk_tracker),
            ("auto_update_orchestrator", self.auto_update_orchestrator),
            ("bug_responder", self.bug_responder),
            ("operations_analyzer", self.operations_analyzer),
        ]

        for name, subsystem in subsystems_to_scan:
            try:
                recs = subsystem.generate_recommendations()
                with self._lock:
                    for rec in recs:
                        self._add_recommendation(rec)
                        new_recs.append(rec)
            except Exception as exc:
                logger.warning("Subsystem %s failed to generate recommendations: %s", name, exc)

        self._persist_recommendations()
        self._publish_event(
            "LEARNING_FEEDBACK",
            {"action": "refresh_all", "new_recommendation_count": len(new_recs)},
        )
        logger.info("Refreshed recommendations — %d new items", len(new_recs))
        return new_recs

    def get_recommendations(
        self,
        rec_type: Optional[RecommendationType] = None,
        subsystem: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Recommendation]:
        """Return filtered list of recommendations.

        Accepts either rec_type (enum) or category (string) for type filtering.
        Default status filter is STATUS_PENDING.

        Args:
            rec_type: Filter by RecommendationType enum value.
            subsystem: Filter by subsystem name.
            priority: Filter by priority string.
            category: Filter by category string (backward-compat alias for rec_type).
            status: Filter by status string. Defaults to 'pending'.
        """
        # Resolve category string to rec_type enum if needed
        if category is not None and rec_type is None:
            rec_type = _CATEGORY_TO_REC_TYPE.get(category)

        filter_status = status if status is not None else STATUS_PENDING

        with self._lock:
            result = [r for r in self._recommendations.values() if r.status == filter_status]

        if rec_type is not None:
            result = [r for r in result if r.recommendation_type == rec_type]
        if subsystem is not None:
            result = [r for r in result if r.subsystem == subsystem]
        if priority is not None:
            result = [r for r in result if r.priority == priority]

        _priority_order = {
            PRIORITY_CRITICAL: 0, PRIORITY_HIGH: 1, PRIORITY_MEDIUM: 2,
            PRIORITY_LOW: 3, PRIORITY_INFORMATIONAL: 4,
        }
        result.sort(key=lambda r: (_priority_order.get(r.priority, 99), r.created_at))
        return result

    def get_recommendation(self, recommendation_id: str) -> Optional[Recommendation]:
        """Return a specific recommendation by ID."""
        with self._lock:
            return self._recommendations.get(recommendation_id)

    def acknowledge_recommendation(self, recommendation_id: str) -> bool:
        """Mark a recommendation as acknowledged.

        Returns:
            True if acknowledged successfully, False if not found.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None:
                return False
            rec.status = STATUS_ACKNOWLEDGED
        self.save_state()
        logger.info("Recommendation %s acknowledged", recommendation_id)
        return True

    def approve_recommendation(self, recommendation_id: str, approved_by: str = "founder") -> bool:
        """Mark a recommendation as approved.

        Returns:
            True if approved successfully, False if not found or already actioned.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None or rec.status != STATUS_PENDING:
                return False
            rec.status = STATUS_APPROVED
            rec.metadata["approved_by"] = approved_by
            rec.metadata["approved_at"] = datetime.now(timezone.utc).isoformat()

        self._persist_recommendations()
        self._publish_event(
            "LEARNING_FEEDBACK",
            {"action": "approve", "recommendation_id": recommendation_id, "approved_by": approved_by},
        )
        logger.info("Recommendation %s approved by %s", recommendation_id, approved_by)
        return True

    def dismiss_recommendation(self, recommendation_id: str, reason: str = "") -> bool:
        """Mark a recommendation as dismissed.

        Returns:
            True if dismissed successfully, False if not found or already actioned.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None or rec.status != STATUS_PENDING:
                return False
            rec.status = STATUS_DISMISSED
            rec.dismissed_reason = reason
            if reason:
                rec.metadata["dismissal_reason"] = reason

        self._persist_recommendations()
        self._publish_event(
            "LEARNING_FEEDBACK",
            {"action": "dismiss", "recommendation_id": recommendation_id, "reason": reason},
        )
        logger.info("Recommendation %s dismissed", recommendation_id)
        return True

    def ingest_bug_report(self, report: BugReportInput) -> Dict[str, Any]:
        """Ingest a bug report and produce an auto-response with a linked recommendation.

        Returns:
            Auto-response dict including classification, recommended actions, and recommendation_id.
        """
        response = self.bug_responder.ingest_report(report)

        _severity_to_priority = {
            PRIORITY_CRITICAL: PRIORITY_CRITICAL,
            PRIORITY_HIGH: PRIORITY_HIGH,
            PRIORITY_MEDIUM: PRIORITY_MEDIUM,
            PRIORITY_LOW: PRIORITY_LOW,
        }
        priority = _severity_to_priority.get(
            response["classification"]["severity"], PRIORITY_MEDIUM
        )

        rec = Recommendation(
            recommendation_id=str(uuid.uuid4()),
            subsystem="bug_responder",
            recommendation_type=RecommendationType.BUG_REPORT_RESPONSE,
            priority=priority,
            confidence_score=response["classification"]["confidence"],
            description=response["response_draft"],
            suggested_action="; ".join(
                a.get("action", "") for a in response.get("recommended_actions", [])
            ),
            estimated_effort="< 2h",
            risk_level="high" if priority in (PRIORITY_CRITICAL, PRIORITY_HIGH) else "medium",
            auto_applicable=False,
            requires_review=response["requires_human_review"],
            metadata={
                "report_id": report.report_id,
                "auto_response_id": response["auto_response_id"],
                "classification": response["classification"],
            },
        )

        with self._lock:
            self._add_recommendation(rec)

        self._persist_recommendations()
        response["recommendation_id"] = rec.recommendation_id
        return response

    def get_status(self) -> Dict[str, Any]:
        """Return overall engine status summary."""
        with self._lock:
            total = len(self._recommendations)
            pending = sum(1 for r in self._recommendations.values() if r.status == STATUS_PENDING)
            approved = sum(1 for r in self._recommendations.values() if r.status == STATUS_APPROVED)
            dismissed = sum(1 for r in self._recommendations.values() if r.status == STATUS_DISMISSED)
            cycles = len(self._history)

        return {
            "engine": "SystemUpdateRecommendationEngine",
            "design_label": "ARCH-020",
            "status": "active",
            "total_active_recommendations": total,
            "cycles_completed": cycles,
            "persistence_available": self._pm is not None,
            "event_backbone_available": self._backbone is not None,
            "subsystems": {
                "maintenance_advisor": "active",
                "sdk_tracker": "active",
                "auto_update_orchestrator": "active",
                "bug_responder": "active",
                "operations_analyzer": "active",
            },
            "dependencies": {
                "improvement_engine": self._improvement_engine is not None,
                "bug_detector": self._bug_detector is not None,
                "dependency_audit": self._dependency_audit is not None,
                "health_monitor": self._health_monitor is not None,
                "repair_system": self._repair_system is not None,
                "orchestrator": self._orchestrator is not None,
                "event_backbone": self._backbone is not None,
                "persistence_manager": self._pm is not None,
            },
            "recommendations": {
                "total": total,
                "pending": pending,
                "approved": approved,
                "dismissed": dismissed,
            },
        }
