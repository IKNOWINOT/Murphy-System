"""
Founder Update Orchestrator for the Murphy System.

Design Label: ARCH-007 — Founder Update Orchestrator
Owner: Backend Team
Dependencies:
  - SelfImprovementEngine (ARCH-001)
  - SelfFixLoop (ARCH-005)
  - BugPatternDetector (DEV-004)
  - DependencyAuditEngine (DEV-005)
  - SelfHealingCoordinator (OBS-004)
  - AutonomousRepairSystem (ARCH-006)
  - InnovationFarmer (ARCH-006)
  - EventBackbone
  - PersistenceManager

Aggregates recommendations from ALL self-improvement subsystems into a
single coordinated founder-level view with five recommendation categories:
  - Maintenance Integrations (scheduled, urgent, preventive)
  - SDK Updates (security, feature, breaking-change, deprecation)
  - Auto-Updates (safe, requires-review, rollback)
  - Auto-Responses to Bug Reports (triage, pattern-match, fix-proposal, workaround)
  - System Operations Analysis (performance-trend, capacity-warning, health-score, cost)

Safety invariants:
  - NEVER modifies source files on disk
  - Generates proposals for human review only
  - Thread-safe: all shared state guarded by Lock
  - Bounded collections with capped_append pattern (CWE-770)
  - Full audit trail via PersistenceManager and EventBackbone
  - Graceful degradation when any subsystem is unavailable

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

# ---------------------------------------------------------------------------
# Optional dependency imports with graceful fallback
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from event_backbone import EventBackbone
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    _BACKBONE_AVAILABLE = False

try:
    from self_improvement_engine import SelfImprovementEngine
    _IMPROVEMENT_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfImprovementEngine = None  # type: ignore[assignment,misc]
    _IMPROVEMENT_AVAILABLE = False

try:
    from self_fix_loop import SelfFixLoop
    _SELF_FIX_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfFixLoop = None  # type: ignore[assignment,misc]
    _SELF_FIX_AVAILABLE = False

try:
    from bug_pattern_detector import BugPatternDetector
    _BUG_DETECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    BugPatternDetector = None  # type: ignore[assignment,misc]
    _BUG_DETECTOR_AVAILABLE = False

try:
    from dependency_audit_engine import DependencyAuditEngine
    _DEP_AUDIT_AVAILABLE = True
except Exception:  # pragma: no cover
    DependencyAuditEngine = None  # type: ignore[assignment,misc]
    _DEP_AUDIT_AVAILABLE = False

try:
    from self_healing_coordinator import SelfHealingCoordinator
    _HEALING_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfHealingCoordinator = None  # type: ignore[assignment,misc]
    _HEALING_AVAILABLE = False

try:
    from autonomous_repair_system import AutonomousRepairSystem
    _REPAIR_AVAILABLE = True
except Exception:  # pragma: no cover
    AutonomousRepairSystem = None  # type: ignore[assignment,misc]
    _REPAIR_AVAILABLE = False

try:
    from innovation_farmer import InnovationFarmer
    _FARMER_AVAILABLE = True
except Exception:  # pragma: no cover
    InnovationFarmer = None  # type: ignore[assignment,misc]
    _FARMER_AVAILABLE = False

try:
    from persistence_manager import PersistenceManager
    _PERSISTENCE_AVAILABLE = True
except Exception:  # pragma: no cover
    PersistenceManager = None  # type: ignore[assignment,misc]
    _PERSISTENCE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

_MAX_RECOMMENDATIONS = 10_000
_MAX_REPORTS = 1_000


class RecommendationType(Enum):
    """All recommendation sub-types produced by the orchestrator."""

    # Maintenance
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"
    MAINTENANCE_URGENT = "maintenance_urgent"
    MAINTENANCE_PREVENTIVE = "maintenance_preventive"

    # SDK / Dependencies
    SDK_SECURITY_UPDATE = "sdk_security_update"
    SDK_FEATURE_UPDATE = "sdk_feature_update"
    SDK_BREAKING_CHANGE = "sdk_breaking_change"
    SDK_DEPRECATION_WARNING = "sdk_deprecation_warning"

    # Auto-Updates
    AUTO_UPDATE_SAFE = "auto_update_safe"
    AUTO_UPDATE_REQUIRES_REVIEW = "auto_update_requires_review"
    AUTO_UPDATE_ROLLBACK = "auto_update_rollback"

    # Bug Response
    BUG_AUTO_TRIAGE = "bug_auto_triage"
    BUG_PATTERN_MATCH = "bug_pattern_match"
    BUG_FIX_PROPOSAL = "bug_fix_proposal"
    BUG_WORKAROUND = "bug_workaround"

    # Operations Analysis
    OPS_PERFORMANCE_TREND = "ops_performance_trend"
    OPS_CAPACITY_WARNING = "ops_capacity_warning"
    OPS_HEALTH_SCORE = "ops_health_score"
    OPS_COST_OPTIMIZATION = "ops_cost_optimization"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FounderRecommendation:
    """A single recommendation generated by the orchestrator."""

    recommendation_id: str
    recommendation_type: RecommendationType
    subsystem_source: str
    title: str
    description: str
    priority: str  # "critical" | "high" | "medium" | "low"
    confidence: float  # 0.0–1.0
    suggested_actions: List[str]
    metadata: Dict[str, Any]
    status: str  # "pending" | "accepted" | "rejected" | "implemented" | "deferred"
    created_at: str
    expires_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type.value,
            "subsystem_source": self.subsystem_source,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "confidence": self.confidence,
            "suggested_actions": list(self.suggested_actions),
            "metadata": dict(self.metadata),
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FounderRecommendation":
        return cls(
            recommendation_id=data["recommendation_id"],
            recommendation_type=RecommendationType(data["recommendation_type"]),
            subsystem_source=data["subsystem_source"],
            title=data["title"],
            description=data["description"],
            priority=data["priority"],
            confidence=float(data.get("confidence", 0.5)),
            suggested_actions=list(data.get("suggested_actions", [])),
            metadata=dict(data.get("metadata", {})),
            status=data.get("status", "pending"),
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
        )


@dataclass
class SubsystemHealthReport:
    """Health snapshot for a single subsystem."""

    subsystem_name: str
    status: str  # "healthy" | "degraded" | "critical" | "unknown"
    last_check: str
    metrics: Dict[str, Any]
    recommendations: List[FounderRecommendation]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subsystem_name": self.subsystem_name,
            "status": self.status,
            "last_check": self.last_check,
            "metrics": dict(self.metrics),
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


@dataclass
class FounderUpdateReport:
    """Full founder update report aggregating all subsystems."""

    report_id: str
    generated_at: str
    overall_health_score: float  # 0.0–1.0
    subsystem_reports: List[SubsystemHealthReport]
    all_recommendations: List[FounderRecommendation]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "overall_health_score": self.overall_health_score,
            "subsystem_reports": [s.to_dict() for s in self.subsystem_reports],
            "all_recommendations": [r.to_dict() for r in self.all_recommendations],
            "summary": dict(self.summary),
        }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class FounderUpdateOrchestrator:
    """ARCH-007 — Founder-level orchestrator that aggregates recommendations
    from all self-improvement subsystems into a single coordinated view.

    Parameters
    ----------
    improvement_engine:
        SelfImprovementEngine instance (optional).
    self_fix_loop:
        SelfFixLoop instance (optional).
    bug_detector:
        BugPatternDetector instance (optional).
    dependency_auditor:
        DependencyAuditEngine instance (optional).
    healing_coordinator:
        SelfHealingCoordinator instance (optional).
    repair_system:
        AutonomousRepairSystem instance (optional).
    innovation_farmer:
        InnovationFarmer instance (optional).
    event_backbone:
        EventBackbone instance (optional).
    persistence_manager:
        PersistenceManager instance (optional).
    max_recommendations:
        Upper bound on the in-memory recommendations list (CWE-770).
    max_reports:
        Upper bound on the in-memory reports history list (CWE-770).
    """

    _PERSISTENCE_KEY = "founder_update_orchestrator"

    def __init__(
        self,
        *,
        improvement_engine: Any = None,
        self_fix_loop: Any = None,
        bug_detector: Any = None,
        dependency_auditor: Any = None,
        healing_coordinator: Any = None,
        repair_system: Any = None,
        innovation_farmer: Any = None,
        event_backbone: Any = None,
        persistence_manager: Any = None,
        max_recommendations: int = _MAX_RECOMMENDATIONS,
        max_reports: int = _MAX_REPORTS,
    ) -> None:
        self._improvement_engine = improvement_engine
        self._self_fix_loop = self_fix_loop
        self._bug_detector = bug_detector
        self._dependency_auditor = dependency_auditor
        self._healing_coordinator = healing_coordinator
        self._repair_system = repair_system
        self._innovation_farmer = innovation_farmer
        self._event_backbone = event_backbone
        self._persistence_manager = persistence_manager

        self._max_recommendations = max_recommendations
        self._max_reports = max_reports

        self._lock = threading.Lock()
        self._recommendations: List[FounderRecommendation] = []
        self._recommendations_index: Dict[str, FounderRecommendation] = {}
        self._reports: List[FounderUpdateReport] = []

        logger.info("FounderUpdateOrchestrator (ARCH-007) initialised.")

    # ------------------------------------------------------------------
    # Public API — report generation
    # ------------------------------------------------------------------

    def generate_full_report(self) -> FounderUpdateReport:
        """Collect recommendations from all subsystems and compile a full report."""
        maintenance = self._collect_maintenance_recommendations()
        sdk = self._collect_sdk_recommendations()
        auto_update = self._collect_auto_update_recommendations()
        bug_response = self._collect_bug_response_recommendations()
        operations = self._collect_operations_recommendations()

        all_recs = maintenance + sdk + auto_update + bug_response + operations

        with self._lock:
            for rec in all_recs:
                if rec.recommendation_id not in self._recommendations_index:
                    capped_append(self._recommendations, rec, self._max_recommendations)
                    self._recommendations_index[rec.recommendation_id] = rec

        subsystem_reports = self._build_subsystem_reports(all_recs)
        overall_score = self._calculate_health_score(subsystem_reports)

        by_type: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for rec in all_recs:
            by_type[rec.recommendation_type.value] = by_type.get(rec.recommendation_type.value, 0) + 1
            by_priority[rec.priority] = by_priority.get(rec.priority, 0) + 1
            by_status[rec.status] = by_status.get(rec.status, 0) + 1

        summary = {
            "total_recommendations": len(all_recs),
            "by_type": by_type,
            "by_priority": by_priority,
            "by_status": by_status,
            "overall_health_score": overall_score,
        }

        report = FounderUpdateReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_health_score=overall_score,
            subsystem_reports=subsystem_reports,
            all_recommendations=all_recs,
            summary=summary,
        )

        with self._lock:
            capped_append(self._reports, report, self._max_reports)

        self._emit_event("founder_report_generated", {
            "report_id": report.report_id,
            "overall_health_score": overall_score,
            "total_recommendations": len(all_recs),
        })

        return report

    def get_recommendations(
        self,
        *,
        subsystem: Optional[str] = None,
        priority: Optional[str] = None,
        recommendation_type: Optional[RecommendationType] = None,
        status: Optional[str] = None,
    ) -> List[FounderRecommendation]:
        """Return filtered recommendations."""
        with self._lock:
            recs = list(self._recommendations)

        if subsystem is not None:
            recs = [r for r in recs if r.subsystem_source == subsystem]
        if priority is not None:
            recs = [r for r in recs if r.priority == priority]
        if recommendation_type is not None:
            recs = [r for r in recs if r.recommendation_type == recommendation_type]
        if status is not None:
            recs = [r for r in recs if r.status == status]

        return recs

    def get_recommendation(self, recommendation_id: str) -> Optional[FounderRecommendation]:
        """Return a single recommendation by ID, or None if not found."""
        with self._lock:
            return self._recommendations_index.get(recommendation_id)

    def get_reports(self) -> List[FounderUpdateReport]:
        """Return all historical reports (newest last)."""
        with self._lock:
            return list(self._reports)

    # ------------------------------------------------------------------
    # Recommendation lifecycle
    # ------------------------------------------------------------------

    def accept_recommendation(self, recommendation_id: str) -> bool:
        """Accept a pending recommendation. Returns True on success."""
        with self._lock:
            rec = self._recommendations_index.get(recommendation_id)
            if rec is None:
                logger.warning("accept_recommendation: ID not found: %s", recommendation_id)
                return False
            if rec.status != "pending":
                logger.warning(
                    "accept_recommendation: cannot accept recommendation in status '%s'", rec.status
                )
                return False
            rec.status = "accepted"

        self._emit_event("recommendation_accepted", {"recommendation_id": recommendation_id})
        return True

    def reject_recommendation(self, recommendation_id: str, reason: str = "") -> bool:
        """Reject a pending recommendation. Returns True on success."""
        with self._lock:
            rec = self._recommendations_index.get(recommendation_id)
            if rec is None:
                logger.warning("reject_recommendation: ID not found: %s", recommendation_id)
                return False
            if rec.status not in ("pending", "accepted"):
                logger.warning(
                    "reject_recommendation: cannot reject recommendation in status '%s'", rec.status
                )
                return False
            rec.status = "rejected"
            rec.metadata["rejection_reason"] = reason

        self._emit_event("recommendation_rejected", {
            "recommendation_id": recommendation_id,
            "reason": reason,
        })
        return True

    def defer_recommendation(self, recommendation_id: str, until: str) -> bool:
        """Defer a pending recommendation until a given ISO datetime string."""
        with self._lock:
            rec = self._recommendations_index.get(recommendation_id)
            if rec is None:
                logger.warning("defer_recommendation: ID not found: %s", recommendation_id)
                return False
            if rec.status != "pending":
                logger.warning(
                    "defer_recommendation: cannot defer recommendation in status '%s'", rec.status
                )
                return False
            rec.status = "deferred"
            rec.expires_at = until
            rec.metadata["deferred_until"] = until

        return True

    def mark_implemented(self, recommendation_id: str) -> bool:
        """Mark a recommendation as implemented. Returns True on success."""
        with self._lock:
            rec = self._recommendations_index.get(recommendation_id)
            if rec is None:
                return False
            if rec.status != "accepted":
                return False
            rec.status = "implemented"

        return True

    # ------------------------------------------------------------------
    # Subsystem-specific collectors
    # ------------------------------------------------------------------

    def _collect_maintenance_recommendations(self) -> List[FounderRecommendation]:
        """Collect maintenance recommendations from healing coordinator and repair system."""
        recs: List[FounderRecommendation] = []
        now = datetime.now(timezone.utc).isoformat()

        # From SelfHealingCoordinator
        if self._healing_coordinator is not None:
            try:
                health = getattr(self._healing_coordinator, "get_health_status", None)
                if callable(health):
                    status = health()
                    if isinstance(status, dict):
                        remediation_count = status.get("active_remediations", 0)
                        if remediation_count and int(remediation_count) > 0:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.MAINTENANCE_URGENT,
                                source="self_healing_coordinator",
                                title="Active remediations in progress",
                                description=(
                                    f"SelfHealingCoordinator has {remediation_count} active "
                                    "remediation(s) running. Review coordinator status."
                                ),
                                priority="high",
                                confidence=0.9,
                                actions=["Review active remediations", "Verify system stability"],
                                metadata={"active_remediations": remediation_count},
                                created_at=now,
                            ))
                        else:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.MAINTENANCE_SCHEDULED,
                                source="self_healing_coordinator",
                                title="Routine healing coordinator health check",
                                description="SelfHealingCoordinator is healthy. Schedule routine maintenance window.",
                                priority="low",
                                confidence=0.8,
                                actions=["Schedule next maintenance window", "Review remediation history"],
                                metadata=status,
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting from SelfHealingCoordinator: %s", exc)

        # From AutonomousRepairSystem
        if self._repair_system is not None:
            try:
                diag = getattr(self._repair_system, "run_diagnostics", None)
                if callable(diag):
                    result = diag()
                    if isinstance(result, dict):
                        issues = result.get("issues", [])
                        if issues:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.MAINTENANCE_URGENT,
                                source="autonomous_repair_system",
                                title=f"Autonomous repair system detected {len(issues)} issue(s)",
                                description=(
                                    "AutonomousRepairSystem diagnostics found issues requiring attention."
                                ),
                                priority="high",
                                confidence=0.85,
                                actions=["Review diagnostic report", "Approve repair proposals"],
                                metadata={"issue_count": len(issues), "issues_preview": issues[:3]},
                                created_at=now,
                            ))
                        else:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.MAINTENANCE_PREVENTIVE,
                                source="autonomous_repair_system",
                                title="Preventive repair system check recommended",
                                description="No active issues detected. Consider preventive maintenance scan.",
                                priority="low",
                                confidence=0.7,
                                actions=["Run full diagnostic scan", "Review immune memory entries"],
                                metadata=result,
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting from AutonomousRepairSystem: %s", exc)

        if not recs:
            recs.append(self._make_rec(
                rec_type=RecommendationType.MAINTENANCE_SCHEDULED,
                source="founder_update_orchestrator",
                title="No subsystem maintenance signals available",
                description=(
                    "Healing coordinator and repair system are not connected. "
                    "Connect subsystems for richer maintenance recommendations."
                ),
                priority="low",
                confidence=0.5,
                actions=["Wire SelfHealingCoordinator", "Wire AutonomousRepairSystem"],
                metadata={},
                created_at=now,
            ))

        return recs

    def _collect_sdk_recommendations(self) -> List[FounderRecommendation]:
        """Collect SDK/dependency recommendations from DependencyAuditEngine and InnovationFarmer."""
        recs: List[FounderRecommendation] = []
        now = datetime.now(timezone.utc).isoformat()

        if self._dependency_auditor is not None:
            try:
                audit = getattr(self._dependency_auditor, "get_audit_summary", None)
                if callable(audit):
                    summary = audit()
                    if isinstance(summary, dict):
                        vulnerable = summary.get("vulnerable_count", 0)
                        outdated = summary.get("outdated_count", 0)
                        deprecated = summary.get("deprecated_count", 0)

                        if vulnerable and int(vulnerable) > 0:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.SDK_SECURITY_UPDATE,
                                source="dependency_audit_engine",
                                title=f"{vulnerable} vulnerable dependency(ies) detected",
                                description=(
                                    "DependencyAuditEngine found dependencies with known security "
                                    "vulnerabilities. Immediate update recommended."
                                ),
                                priority="critical",
                                confidence=0.95,
                                actions=[
                                    "Review vulnerability report",
                                    "Apply security patches",
                                    "Test after update",
                                ],
                                metadata={"vulnerable_count": vulnerable},
                                created_at=now,
                            ))

                        if outdated and int(outdated) > 0:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.SDK_FEATURE_UPDATE,
                                source="dependency_audit_engine",
                                title=f"{outdated} outdated dependency(ies) available for update",
                                description="Feature updates are available for some dependencies.",
                                priority="medium",
                                confidence=0.8,
                                actions=["Review changelog", "Test in staging", "Apply update"],
                                metadata={"outdated_count": outdated},
                                created_at=now,
                            ))

                        if deprecated and int(deprecated) > 0:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.SDK_DEPRECATION_WARNING,
                                source="dependency_audit_engine",
                                title=f"{deprecated} deprecated dependency(ies) in use",
                                description="Some dependencies are deprecated and should be replaced.",
                                priority="medium",
                                confidence=0.85,
                                actions=["Identify replacements", "Plan migration", "Update code"],
                                metadata={"deprecated_count": deprecated},
                                created_at=now,
                            ))

                        # Check for breaking changes
                        breaking = summary.get("breaking_change_count", 0)
                        if breaking and int(breaking) > 0:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.SDK_BREAKING_CHANGE,
                                source="dependency_audit_engine",
                                title=f"{breaking} dependency(ies) with breaking changes detected",
                                description="Some available updates contain breaking API changes.",
                                priority="high",
                                confidence=0.9,
                                actions=[
                                    "Review breaking change notes",
                                    "Update dependent code",
                                    "Run full test suite",
                                ],
                                metadata={"breaking_change_count": breaking},
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting SDK recs from DependencyAuditEngine: %s", exc)

        if self._innovation_farmer is not None:
            try:
                harvest = getattr(self._innovation_farmer, "get_latest_harvest", None)
                if callable(harvest):
                    result = harvest()
                    if isinstance(result, dict) and result.get("proposals"):
                        count = len(result["proposals"])
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.SDK_FEATURE_UPDATE,
                            source="innovation_farmer",
                            title=f"{count} open-source innovation proposal(s) available",
                            description=(
                                "InnovationFarmer has harvested new open-source techniques and "
                                "feature ideas relevant to the Murphy System."
                            ),
                            priority="low",
                            confidence=0.7,
                            actions=["Review proposals", "Evaluate feasibility", "Schedule implementation"],
                            metadata={"proposal_count": count},
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting from InnovationFarmer: %s", exc)

        if not recs:
            recs.append(self._make_rec(
                rec_type=RecommendationType.SDK_FEATURE_UPDATE,
                source="founder_update_orchestrator",
                title="No SDK/dependency signals available",
                description=(
                    "DependencyAuditEngine and InnovationFarmer are not connected. "
                    "Connect subsystems for SDK update recommendations."
                ),
                priority="low",
                confidence=0.5,
                actions=["Wire DependencyAuditEngine", "Wire InnovationFarmer"],
                metadata={},
                created_at=now,
            ))

        return recs

    def _collect_auto_update_recommendations(self) -> List[FounderRecommendation]:
        """Collect auto-update recommendations from self-fix loop and repair system."""
        recs: List[FounderRecommendation] = []
        now = datetime.now(timezone.utc).isoformat()

        if self._self_fix_loop is not None:
            try:
                report = getattr(self._self_fix_loop, "get_last_report", None)
                if callable(report):
                    last = report()
                    if last is not None:
                        plans = getattr(last, "completed_plans", []) or []
                        failed = getattr(last, "failed_plans", []) or []

                        if plans:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.AUTO_UPDATE_SAFE,
                                source="self_fix_loop",
                                title=f"{len(plans)} self-fix plan(s) successfully verified",
                                description=(
                                    "SelfFixLoop has verified remediation plans that are safe to promote."
                                ),
                                priority="medium",
                                confidence=0.85,
                                actions=["Review completed plans", "Accept and implement"],
                                metadata={"completed_count": len(plans)},
                                created_at=now,
                            ))

                        if failed:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.AUTO_UPDATE_REQUIRES_REVIEW,
                                source="self_fix_loop",
                                title=f"{len(failed)} self-fix plan(s) require human review",
                                description=(
                                    "Some fix plans failed automated verification and require "
                                    "human review before proceeding."
                                ),
                                priority="high",
                                confidence=0.9,
                                actions=["Review failed plans", "Determine root cause", "Retry or escalate"],
                                metadata={"failed_count": len(failed)},
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting auto-update recs from SelfFixLoop: %s", exc)

        if self._repair_system is not None:
            try:
                rollback = getattr(self._repair_system, "get_rollback_candidates", None)
                if callable(rollback):
                    candidates = rollback()
                    if candidates:
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.AUTO_UPDATE_ROLLBACK,
                            source="autonomous_repair_system",
                            title=f"{len(candidates)} rollback candidate(s) identified",
                            description=(
                                "AutonomousRepairSystem identified updates that may need rollback."
                            ),
                            priority="high",
                            confidence=0.8,
                            actions=["Review rollback candidates", "Verify current state", "Execute rollback"],
                            metadata={"rollback_count": len(candidates)},
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting rollback recs from AutonomousRepairSystem: %s", exc)

        if not recs:
            recs.append(self._make_rec(
                rec_type=RecommendationType.AUTO_UPDATE_SAFE,
                source="founder_update_orchestrator",
                title="No auto-update signals available",
                description=(
                    "SelfFixLoop and AutonomousRepairSystem are not connected. "
                    "Connect subsystems for auto-update recommendations."
                ),
                priority="low",
                confidence=0.5,
                actions=["Wire SelfFixLoop", "Wire AutonomousRepairSystem"],
                metadata={},
                created_at=now,
            ))

        return recs

    def _collect_bug_response_recommendations(self) -> List[FounderRecommendation]:
        """Collect bug response recommendations from BugPatternDetector and SelfImprovementEngine."""
        recs: List[FounderRecommendation] = []
        now = datetime.now(timezone.utc).isoformat()

        if self._bug_detector is not None:
            try:
                patterns = getattr(self._bug_detector, "get_active_patterns", None)
                if callable(patterns):
                    active = patterns()
                    if isinstance(active, list) and active:
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.BUG_PATTERN_MATCH,
                            source="bug_pattern_detector",
                            title=f"{len(active)} active bug pattern(s) detected",
                            description=(
                                "BugPatternDetector has identified recurring failure patterns "
                                "that require attention."
                            ),
                            priority="high",
                            confidence=0.9,
                            actions=[
                                "Review pattern details",
                                "Assign to engineering team",
                                "Track resolution",
                            ],
                            metadata={"pattern_count": len(active)},
                            created_at=now,
                        ))

                triage = getattr(self._bug_detector, "get_triage_queue", None)
                if callable(triage):
                    queue = triage()
                    if isinstance(queue, list) and queue:
                        critical = [b for b in queue if getattr(b, "severity", "") == "critical"]
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.BUG_AUTO_TRIAGE,
                            source="bug_pattern_detector",
                            title=f"{len(queue)} bug report(s) in triage queue ({len(critical)} critical)",
                            description=(
                                "Automated triage has classified incoming bug reports. "
                                "Human review required for critical items."
                            ),
                            priority="critical" if critical else "medium",
                            confidence=0.85,
                            actions=[
                                "Review triage results",
                                "Confirm priority classifications",
                                "Assign owners",
                            ],
                            metadata={"total": len(queue), "critical": len(critical)},
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting bug recs from BugPatternDetector: %s", exc)

        if self._improvement_engine is not None:
            try:
                proposals = getattr(self._improvement_engine, "get_pending_proposals", None)
                if callable(proposals):
                    pending = proposals()
                    if isinstance(pending, list) and pending:
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.BUG_FIX_PROPOSAL,
                            source="self_improvement_engine",
                            title=f"{len(pending)} fix proposal(s) pending review",
                            description=(
                                "SelfImprovementEngine has generated fix proposals from "
                                "learned patterns. Review and accept/reject."
                            ),
                            priority="medium",
                            confidence=0.8,
                            actions=["Review proposals", "Approve or reject", "Track implementation"],
                            metadata={"pending_count": len(pending)},
                            created_at=now,
                        ))

                workarounds = getattr(self._improvement_engine, "get_workarounds", None)
                if callable(workarounds):
                    ws = workarounds()
                    if isinstance(ws, list) and ws:
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.BUG_WORKAROUND,
                            source="self_improvement_engine",
                            title=f"{len(ws)} workaround(s) available",
                            description=(
                                "Temporary workarounds have been identified for known issues. "
                                "Consider applying until permanent fixes are ready."
                            ),
                            priority="low",
                            confidence=0.7,
                            actions=["Review workarounds", "Apply as needed", "Plan permanent fixes"],
                            metadata={"workaround_count": len(ws)},
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting bug recs from SelfImprovementEngine: %s", exc)

        if not recs:
            recs.append(self._make_rec(
                rec_type=RecommendationType.BUG_AUTO_TRIAGE,
                source="founder_update_orchestrator",
                title="No bug response signals available",
                description=(
                    "BugPatternDetector and SelfImprovementEngine are not connected. "
                    "Connect subsystems for bug response recommendations."
                ),
                priority="low",
                confidence=0.5,
                actions=["Wire BugPatternDetector", "Wire SelfImprovementEngine"],
                metadata={},
                created_at=now,
            ))

        return recs

    def _collect_operations_recommendations(self) -> List[FounderRecommendation]:
        """Collect operations analysis recommendations from all available subsystems."""
        recs: List[FounderRecommendation] = []
        now = datetime.now(timezone.utc).isoformat()

        if self._self_fix_loop is not None:
            try:
                metrics = getattr(self._self_fix_loop, "get_metrics", None)
                if callable(metrics):
                    m = metrics()
                    if isinstance(m, dict):
                        success_rate = m.get("success_rate", None)
                        if success_rate is not None:
                            priority = "low"
                            if float(success_rate) < 0.5:
                                priority = "critical"
                            elif float(success_rate) < 0.75:
                                priority = "high"
                            elif float(success_rate) < 0.9:
                                priority = "medium"

                            recs.append(self._make_rec(
                                rec_type=RecommendationType.OPS_PERFORMANCE_TREND,
                                source="self_fix_loop",
                                title=f"Self-fix loop success rate: {success_rate:.1%}",
                                description=(
                                    f"The self-fix loop reports a {success_rate:.1%} success rate. "
                                    "Monitor for declining trends."
                                ),
                                priority=priority,
                                confidence=0.9,
                                actions=["Review loop telemetry", "Identify failure modes"],
                                metadata=m,
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting ops recs from SelfFixLoop: %s", exc)

        if self._improvement_engine is not None:
            try:
                score = getattr(self._improvement_engine, "get_confidence_score", None)
                if callable(score):
                    cs = score()
                    if cs is not None:
                        priority = "low" if float(cs) >= 0.7 else ("medium" if float(cs) >= 0.5 else "high")
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.OPS_HEALTH_SCORE,
                            source="self_improvement_engine",
                            title=f"System improvement confidence score: {cs:.2f}",
                            description=(
                                f"SelfImprovementEngine reports a confidence score of {cs:.2f}. "
                                "Scores below 0.7 indicate learning degradation."
                            ),
                            priority=priority,
                            confidence=0.85,
                            actions=["Review calibration data", "Adjust learning parameters"],
                            metadata={"confidence_score": cs},
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting health score from SelfImprovementEngine: %s", exc)

        if self._healing_coordinator is not None:
            try:
                capacity = getattr(self._healing_coordinator, "get_capacity_metrics", None)
                if callable(capacity):
                    cap = capacity()
                    if isinstance(cap, dict):
                        usage = cap.get("usage_percent", None)
                        if usage is not None and float(usage) > 80:
                            recs.append(self._make_rec(
                                rec_type=RecommendationType.OPS_CAPACITY_WARNING,
                                source="self_healing_coordinator",
                                title=f"Capacity usage at {usage:.0f}%",
                                description=(
                                    f"SelfHealingCoordinator reports {usage:.0f}% capacity usage. "
                                    "Consider scaling or optimizing."
                                ),
                                priority="high" if float(usage) > 90 else "medium",
                                confidence=0.9,
                                actions=["Review capacity metrics", "Plan scaling strategy"],
                                metadata=cap,
                                created_at=now,
                            ))
            except Exception as exc:
                logger.debug("Error collecting capacity recs from SelfHealingCoordinator: %s", exc)

        if self._dependency_auditor is not None:
            try:
                cost = getattr(self._dependency_auditor, "get_cost_analysis", None)
                if callable(cost):
                    c = cost()
                    if isinstance(c, dict) and c.get("optimization_opportunities"):
                        ops_count = len(c["optimization_opportunities"])
                        recs.append(self._make_rec(
                            rec_type=RecommendationType.OPS_COST_OPTIMIZATION,
                            source="dependency_audit_engine",
                            title=f"{ops_count} cost optimization opportunity(ies) identified",
                            description=(
                                "Dependency analysis has identified opportunities to reduce "
                                "infrastructure costs."
                            ),
                            priority="medium",
                            confidence=0.75,
                            actions=["Review cost analysis", "Prioritize optimizations", "Implement changes"],
                            metadata=c,
                            created_at=now,
                        ))
            except Exception as exc:
                logger.debug("Error collecting cost recs from DependencyAuditEngine: %s", exc)

        if not recs:
            recs.append(self._make_rec(
                rec_type=RecommendationType.OPS_HEALTH_SCORE,
                source="founder_update_orchestrator",
                title="No operational signals available",
                description=(
                    "No operational subsystems are connected. "
                    "Connect subsystems for operational analysis recommendations."
                ),
                priority="low",
                confidence=0.5,
                actions=["Wire subsystems for operational insights"],
                metadata={},
                created_at=now,
            ))

        return recs

    # ------------------------------------------------------------------
    # Health scoring
    # ------------------------------------------------------------------

    def _calculate_health_score(self, reports: List[SubsystemHealthReport]) -> float:
        """Calculate overall health score (0.0–1.0) from subsystem reports."""
        if not reports:
            return 0.5

        _STATUS_SCORE = {
            "healthy": 1.0,
            "degraded": 0.5,
            "critical": 0.1,
            "unknown": 0.5,
        }

        scores = [_STATUS_SCORE.get(r.status, 0.5) for r in reports]
        return round(sum(scores) / len(scores), 4)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """Persist recommendations and report history. Returns True on success."""
        if self._persistence_manager is None:
            return False

        try:
            with self._lock:
                data = {
                    "recommendations": [r.to_dict() for r in self._recommendations],
                    "reports": [r.to_dict() for r in self._reports],
                }
            save = getattr(self._persistence_manager, "save", None)
            if callable(save):
                save(self._PERSISTENCE_KEY, data)
                return True
        except Exception as exc:
            logger.warning("FounderUpdateOrchestrator.save_state failed: %s", exc)

        return False

    def load_state(self) -> bool:
        """Restore recommendations and report history. Returns True on success."""
        if self._persistence_manager is None:
            return False

        try:
            load = getattr(self._persistence_manager, "load", None)
            if callable(load):
                data = load(self._PERSISTENCE_KEY)
                if data is None:
                    return False

                recs = []
                idx: Dict[str, FounderRecommendation] = {}
                for rd in data.get("recommendations", []):
                    try:
                        rec = FounderRecommendation.from_dict(rd)
                        recs.append(rec)
                        idx[rec.recommendation_id] = rec
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Skipping malformed recommendation: %s", exc)

                with self._lock:
                    self._recommendations = recs
                    self._recommendations_index = idx

                return True
        except Exception as exc:
            logger.warning("FounderUpdateOrchestrator.load_state failed: %s", exc)

        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_rec(
        self,
        *,
        rec_type: RecommendationType,
        source: str,
        title: str,
        description: str,
        priority: str,
        confidence: float,
        actions: List[str],
        metadata: Dict[str, Any],
        created_at: str,
    ) -> FounderRecommendation:
        return FounderRecommendation(
            recommendation_id=str(uuid.uuid4()),
            recommendation_type=rec_type,
            subsystem_source=source,
            title=title,
            description=description,
            priority=priority,
            confidence=max(0.0, min(1.0, confidence)),
            suggested_actions=list(actions),
            metadata=dict(metadata),
            status="pending",
            created_at=created_at,
        )

    def _build_subsystem_reports(
        self, all_recs: List[FounderRecommendation]
    ) -> List[SubsystemHealthReport]:
        """Group recommendations by subsystem and derive health status."""
        by_source: Dict[str, List[FounderRecommendation]] = {}
        for rec in all_recs:
            by_source.setdefault(rec.subsystem_source, []).append(rec)

        reports = []
        now = datetime.now(timezone.utc).isoformat()
        for source, recs in by_source.items():
            priorities = {r.priority for r in recs}
            if "critical" in priorities:
                status = "critical"
            elif "high" in priorities:
                status = "degraded"
            else:
                status = "healthy"

            reports.append(SubsystemHealthReport(
                subsystem_name=source,
                status=status,
                last_check=now,
                metrics={"recommendation_count": len(recs)},
                recommendations=recs,
            ))

        return reports

    def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit an event via EventBackbone if available."""
        if self._event_backbone is None:
            return
        try:
            emit = getattr(self._event_backbone, "emit", None)
            if callable(emit):
                emit(event_type, payload)
        except Exception as exc:
            logger.debug("EventBackbone emit failed: %s", exc)


__all__ = [
    "RecommendationType",
    "FounderRecommendation",
    "SubsystemHealthReport",
    "FounderUpdateReport",
    "FounderUpdateOrchestrator",
]
