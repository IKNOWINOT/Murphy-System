"""
System Update Recommendation Engine for Murphy System.

Design Label: ARCH-008 — System Update Recommendation Engine
Owner: Backend Team / Platform Engineering
Dependencies:
  - SelfImprovementEngine (ARCH-001, ImprovementProposal objects)
  - BugPatternDetector (DEV-004, BugReport / patterns)
  - DependencyAuditEngine (DEV-005, DependencyAuditReport findings)
  - HealthMonitor (operational_completeness, health status)
  - AutonomousRepairSystem (ARCH-006, repair proposals)
  - SelfAutomationOrchestrator (ARCH-002, task lifecycle data)
  - EventBackbone (publishes SYSTEM_HEALTH events on recommendation cycles)
  - PersistenceManager (for durable recommendation history)

Implements a unified recommendation pipeline:
  1. Collect  — gather signals from all registered subsystems
  2. Analyze  — correlate signals across subsystems
  3. Prioritize — score and rank by severity, frequency, impact, confidence
  4. Format   — produce recommendations in all applicable forms
  5. Persist  — save recommendation cycles to PersistenceManager
  6. Publish  — emit events via EventBackbone

Multi-form recommendation types (per subsystem):
  - MaintenanceRecommendation — service restarts, config reloads, etc.
  - SDKUpdateRecommendation   — version bumps, breaking change warnings
  - AutoUpdateAction          — safe-to-auto-update vs requires-review
  - BugReportResponse         — pattern-matched fixes, severity, ETA
  - OperationalAnalysis       — resource trends, bottlenecks, forecasts

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock
  - NEVER modifies source files on disk
  - All recommendations are proposals; auto_applicable=True only for low-risk items
  - Bounded: max recommendations per cycle, max history size
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
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RECOMMENDATIONS = 1_000
_MAX_HISTORY = 200
_PERSIST_DOC_ID = "system_update_recommendation_engine_state"

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RecommendationType(str, Enum):
    """Classification of recommendation forms."""

    MAINTENANCE = "maintenance"
    SDK_UPDATE = "sdk_update"
    AUTO_UPDATE = "auto_update"
    BUG_REPORT_RESPONSE = "bug_report_response"
    OPERATIONAL_ANALYSIS = "operational_analysis"


# ---------------------------------------------------------------------------
# Core recommendation dataclass
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    """A single unified recommendation produced by the engine."""

    recommendation_id: str
    subsystem: str
    recommendation_type: RecommendationType
    priority: str  # critical / high / medium / low
    confidence_score: float  # 0.0 – 1.0
    description: str
    suggested_action: str
    estimated_effort: str  # e.g. "< 1h", "1–4h", "1–3d"
    risk_level: str  # low / medium / high
    auto_applicable: bool
    requires_review: bool
    related_proposals: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    status: str = "active"  # active / acknowledged / dismissed
    dismissed_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        # Safety invariant: if requires_review is True, auto_applicable must be False
        if self.requires_review:
            self.auto_applicable = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "subsystem": self.subsystem,
            "recommendation_type": self.recommendation_type.value,
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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Recommendation":
        return cls(
            recommendation_id=data["recommendation_id"],
            subsystem=data["subsystem"],
            recommendation_type=RecommendationType(data["recommendation_type"]),
            priority=data["priority"],
            confidence_score=data["confidence_score"],
            description=data["description"],
            suggested_action=data["suggested_action"],
            estimated_effort=data["estimated_effort"],
            risk_level=data["risk_level"],
            auto_applicable=data["auto_applicable"],
            requires_review=data["requires_review"],
            related_proposals=data.get("related_proposals", []),
            created_at=data.get("created_at"),
            status=data.get("status", "active"),
            dismissed_reason=data.get("dismissed_reason"),
        )


# ---------------------------------------------------------------------------
# Specialised recommendation form dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MaintenanceRecommendation:
    """Maintenance integration action recommendation."""

    recommendation_id: str
    action_type: str  # restart / config_reload / cache_clear / log_rotation / health_check_schedule
    target_service: str
    description: str
    priority: str
    auto_applicable: bool = False
    requires_review: bool = True
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class SDKUpdateRecommendation:
    """SDK / dependency update recommendation."""

    recommendation_id: str
    package_name: str
    current_version: str
    recommended_version: str
    breaking_changes: bool
    migration_guide: Optional[str]
    compatibility_notes: str
    priority: str
    requires_review: bool = True
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class AutoUpdateAction:
    """Auto-update decision for a package."""

    recommendation_id: str
    package_name: str
    target_version: str
    safe_to_auto_update: bool
    requires_review: bool
    rollback_plan: str
    risk_assessment: str
    priority: str
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class BugReportResponse:
    """Auto-response to a detected bug report."""

    recommendation_id: str
    bug_pattern_id: str
    severity: str
    known_fix_available: bool
    suggested_patch: Optional[str]
    eta_estimate: str
    affected_component: str
    priority: str
    requires_review: bool = True
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class OperationalAnalysis:
    """System operation analysis result."""

    recommendation_id: str
    analysis_type: str  # resource_utilization / performance_bottleneck / capacity_forecast / cost_anomaly
    metric_name: str
    current_value: float
    threshold_value: float
    trend: str  # improving / stable / degrading
    forecast_summary: str
    priority: str
    requires_review: bool = False
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Cycle report dataclass
# ---------------------------------------------------------------------------


@dataclass
class RecommendationCycleReport:
    """Aggregated output of a single recommendation cycle."""

    cycle_id: str
    started_at: str
    completed_at: Optional[str]
    subsystems_queried: List[str]
    subsystems_available: List[str]
    total_recommendations: int
    recommendations_by_type: Dict[str, int]
    recommendations_by_subsystem: Dict[str, int]
    recommendations_by_priority: Dict[str, int]
    recommendations: List[Recommendation]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "subsystems_queried": self.subsystems_queried,
            "subsystems_available": self.subsystems_available,
            "total_recommendations": self.total_recommendations,
            "recommendations_by_type": self.recommendations_by_type,
            "recommendations_by_subsystem": self.recommendations_by_subsystem,
            "recommendations_by_priority": self.recommendations_by_priority,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class SystemUpdateRecommendationEngine:
    """Unified system update recommendation engine.

    Aggregates signals from all self-improvement subsystems and produces
    multi-form update recommendations for operator review.

    Design Label: ARCH-008 — System Update Recommendation Engine
    Owner: Backend Team / Platform Engineering

    Usage::

        engine = SystemUpdateRecommendationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
            improvement_engine=sie,
            bug_detector=bpd,
            dependency_audit=dae,
            health_monitor=hm,
            repair_system=ars,
            orchestrator=sao,
        )
        report = engine.run_recommendation_cycle()
    """

    _PERSIST_DOC_ID = _PERSIST_DOC_ID

    _MAX_RECOMMENDATIONS = _MAX_RECOMMENDATIONS
    _MAX_HISTORY = _MAX_HISTORY

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        improvement_engine=None,
        bug_detector=None,
        dependency_audit=None,
        health_monitor=None,
        repair_system=None,
        orchestrator=None,
        max_recommendations: int = _MAX_RECOMMENDATIONS,
        max_history: int = _MAX_HISTORY,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._improvement = improvement_engine
        self._bug_detector = bug_detector
        self._dependency_audit = dependency_audit
        self._health_monitor = health_monitor
        self._repair_system = repair_system
        self._orchestrator = orchestrator
        self._max_recommendations = max_recommendations
        self._max_history = max_history

        # Active recommendations keyed by recommendation_id
        self._recommendations: Dict[str, Recommendation] = {}

        # Cycle history (summary dicts)
        self._history: List[Dict[str, Any]] = []

        # Custom collector registry: name → callable returning List[Dict]
        self._collectors: Dict[str, Callable[[], List[Dict[str, Any]]]] = {}

    # ------------------------------------------------------------------
    # Subsystem registration
    # ------------------------------------------------------------------

    def register_subsystem(self, name: str, collector: Callable[[], List[Dict[str, Any]]]) -> None:
        """Register an extensible data collector for a named subsystem.

        Args:
            name: Unique subsystem identifier.
            collector: Zero-arg callable returning a list of signal dicts.
        """
        with self._lock:
            self._collectors[name] = collector
        logger.debug("Registered custom subsystem collector: %s", name)

    # ------------------------------------------------------------------
    # Recommendation pipeline
    # ------------------------------------------------------------------

    def run_recommendation_cycle(
        self, subsystems: Optional[List[str]] = None
    ) -> RecommendationCycleReport:
        """Run a full recommendation cycle.

        Args:
            subsystems: Optional list of subsystem names to restrict the cycle to.
                        If None all available subsystems are queried.

        Returns:
            RecommendationCycleReport with all produced recommendations.
        """
        cycle_id = f"cycle-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []
        new_recs: List[Recommendation] = []
        subsystems_available: List[str] = []

        # Step 1 — Collect
        signals = self._collect(subsystems, subsystems_available, errors)

        # Step 2 — Analyze (cross-subsystem correlation)
        correlated = self._analyze(signals)

        # Step 3 — Prioritize
        prioritized = self._prioritize(correlated)

        # Step 4 — Format into Recommendation objects
        for raw in prioritized:
            rec = self._format_recommendation(raw)
            new_recs.append(rec)

        # Enforce per-cycle limit (truncate lowest priority)
        new_recs = new_recs[: self._max_recommendations]

        completed_at = datetime.now(timezone.utc).isoformat()

        # Step 5 — Merge into active recommendations (bounded)
        with self._lock:
            for rec in new_recs:
                if len(self._recommendations) >= self._max_recommendations:
                    # Evict oldest low-priority item
                    self._evict_one()
                self._recommendations[rec.recommendation_id] = rec

        # Build cycle report
        by_type: Dict[str, int] = {}
        by_sub: Dict[str, int] = {}
        by_pri: Dict[str, int] = {}
        for rec in new_recs:
            by_type[rec.recommendation_type.value] = by_type.get(rec.recommendation_type.value, 0) + 1
            by_sub[rec.subsystem] = by_sub.get(rec.subsystem, 0) + 1
            by_pri[rec.priority] = by_pri.get(rec.priority, 0) + 1

        report = RecommendationCycleReport(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            subsystems_queried=list(subsystems) if subsystems else list(self._collectors.keys()) + [
                "improvement_engine", "bug_detector", "dependency_audit",
                "health_monitor", "repair_system", "orchestrator",
            ],
            subsystems_available=subsystems_available,
            total_recommendations=len(new_recs),
            recommendations_by_type=by_type,
            recommendations_by_subsystem=by_sub,
            recommendations_by_priority=by_pri,
            recommendations=new_recs,
            errors=errors,
        )

        # Step 6 — Persist and publish
        history_entry = report.to_dict()
        # Don't store full recommendation list in history to save space
        history_entry_summary = {k: v for k, v in history_entry.items() if k != "recommendations"}
        with self._lock:
            self._history.append(history_entry_summary)
            if len(self._history) > self._max_history:
                del self._history[: len(self._history) - self._max_history]

        self.save_state()
        self._publish_cycle_event(report)

        logger.info(
            "Recommendation cycle %s complete: %d recommendations from %d subsystems",
            cycle_id,
            len(new_recs),
            len(subsystems_available),
        )
        return report

    # ------------------------------------------------------------------
    # Pipeline internals
    # ------------------------------------------------------------------

    def _collect(
        self,
        subsystems: Optional[List[str]],
        available_out: List[str],
        errors_out: List[str],
    ) -> List[Dict[str, Any]]:
        """Collect signals from all subsystems. Gracefully degrades on failure."""
        signals: List[Dict[str, Any]] = []

        def _try_collect(name: str, fn: Callable) -> None:
            try:
                results = fn()
                if results:
                    available_out.append(name)
                    signals.extend(results)
            except Exception as exc:
                errors_out.append(f"{name}: {exc}")
                logger.debug("Subsystem collection failed (%s): %s", name, exc)

        # Built-in subsystem collectors
        builtins: Dict[str, Callable] = {
            "improvement_engine": self._collect_improvement_engine,
            "bug_detector": self._collect_bug_detector,
            "dependency_audit": self._collect_dependency_audit,
            "health_monitor": self._collect_health_monitor,
            "repair_system": self._collect_repair_system,
            "orchestrator": self._collect_orchestrator,
        }

        all_collectors = {**builtins, **self._collectors}

        for name, fn in all_collectors.items():
            if subsystems is not None and name not in subsystems:
                continue
            _try_collect(name, fn)

        return signals

    def _collect_improvement_engine(self) -> List[Dict[str, Any]]:
        if self._improvement is None:
            return []
        proposals = self._improvement.generate_proposals()
        results = []
        for p in proposals:
            results.append({
                "source": "improvement_engine",
                "signal_type": "improvement_proposal",
                "id": getattr(p, "proposal_id", str(uuid.uuid4())),
                "priority": getattr(p, "priority", "medium"),
                "description": getattr(p, "description", ""),
                "suggested_action": getattr(p, "suggested_action", ""),
                "category": getattr(p, "category", "general"),
            })
        return results

    def _collect_bug_detector(self) -> List[Dict[str, Any]]:
        if self._bug_detector is None:
            return []
        reports = self._bug_detector.get_reports(limit=50)
        results = []
        for r in reports:
            results.append({
                "source": "bug_detector",
                "signal_type": "bug_report",
                "id": r.get("report_id", str(uuid.uuid4())),
                "priority": r.get("severity", "medium"),
                "description": r.get("summary", ""),
                "patterns_detected": r.get("patterns_detected", 0),
                "critical_count": r.get("critical_count", 0),
                "high_count": r.get("high_count", 0),
            })
        return results

    def _collect_dependency_audit(self) -> List[Dict[str, Any]]:
        if self._dependency_audit is None:
            return []
        reports = self._dependency_audit.get_reports(limit=20)
        results = []
        for r in reports:
            for finding in r.get("findings", []):
                results.append({
                    "source": "dependency_audit",
                    "signal_type": "dependency_finding",
                    "id": finding.get("advisory_id", str(uuid.uuid4())),
                    "priority": finding.get("severity", "medium"),
                    "package_name": finding.get("dependency_name", ""),
                    "current_version": finding.get("installed_version", ""),
                    "recommended_version": finding.get("fixed_in_version", ""),
                    "description": finding.get("title", ""),
                    "cve_id": finding.get("cve_id", ""),
                })
        return results

    def _collect_health_monitor(self) -> List[Dict[str, Any]]:
        if self._health_monitor is None:
            return []
        health = self._health_monitor.get_system_health()
        results = []
        overall = health.get("overall_status", "unknown")
        if overall in ("degraded", "unhealthy"):
            components = health.get("components", {})
            for comp, status in components.items():
                if status in ("degraded", "unhealthy"):
                    results.append({
                        "source": "health_monitor",
                        "signal_type": "component_health",
                        "id": f"health-{comp}",
                        "priority": "critical" if status == "unhealthy" else "high",
                        "component": comp,
                        "status": status,
                        "description": f"Component '{comp}' is {status}",
                    })
        return results

    def _collect_repair_system(self) -> List[Dict[str, Any]]:
        if self._repair_system is None:
            return []
        proposals = self._repair_system.get_proposals()
        results = []
        for p in proposals:
            results.append({
                "source": "repair_system",
                "signal_type": "repair_proposal",
                "id": p.get("proposal_id", str(uuid.uuid4())),
                "priority": p.get("priority", "medium"),
                "description": p.get("description", ""),
                "suggested_action": p.get("suggested_action", ""),
                "component": p.get("component", ""),
            })
        return results

    def _collect_orchestrator(self) -> List[Dict[str, Any]]:
        if self._orchestrator is None:
            return []
        gaps = self._orchestrator.get_open_gaps()
        results = []
        for g in gaps:
            results.append({
                "source": "orchestrator",
                "signal_type": "open_gap",
                "id": g.get("gap_id", str(uuid.uuid4())),
                "priority": g.get("priority", "low"),
                "description": g.get("description", ""),
                "area": g.get("area", ""),
            })
        return results

    def _analyze(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Correlate signals across subsystems to improve priority and confidence.

        Key correlation: bug pattern + dependency advisory for same component
        → raises priority and confidence of the resulting SDK update recommendation.
        """
        if not signals:
            return []

        # Index bug signals by component/package
        bug_components: Dict[str, List[Dict]] = {}
        dep_packages: Dict[str, List[Dict]] = {}
        for sig in signals:
            if sig.get("signal_type") == "bug_report":
                # Bug reports don't always carry component directly; use description heuristic
                comp = sig.get("description", "")[:40]
                bug_components.setdefault(comp, []).append(sig)
            elif sig.get("signal_type") == "dependency_finding":
                pkg = sig.get("package_name", "")
                dep_packages.setdefault(pkg, []).append(sig)

        correlated = []
        for sig in signals:
            enriched = dict(sig)

            # Cross-subsystem correlation: dependency finding with active bug patterns
            if sig.get("signal_type") == "dependency_finding":
                pkg = sig.get("package_name", "")
                # Check if any bug report description mentions this package
                for bug_key in bug_components:
                    if pkg and pkg.lower() in bug_key.lower():
                        # Correlated: upgrade priority
                        current_priority = enriched.get("priority", "medium")
                        if current_priority == "medium":
                            enriched["priority"] = "high"
                        elif current_priority == "low":
                            enriched["priority"] = "medium"
                        enriched["correlated_with"] = "bug_detector"
                        enriched["correlation_boost"] = True
                        break

            correlated.append(enriched)

        return correlated

    def _prioritize(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort signals by priority (critical → high → medium → low) and compute confidence."""
        for sig in signals:
            # Assign confidence score based on signal type and data richness
            score = 0.5
            signal_type = sig.get("signal_type", "")
            if signal_type == "dependency_finding":
                cve = sig.get("cve_id", "")
                score = 0.9 if cve else 0.7
            elif signal_type == "bug_report":
                critical = sig.get("critical_count", 0)
                high = sig.get("high_count", 0)
                score = min(0.95, 0.6 + critical * 0.05 + high * 0.02)
            elif signal_type == "component_health":
                score = 0.95 if sig.get("status") == "unhealthy" else 0.8
            elif signal_type == "improvement_proposal":
                score = 0.65
            elif signal_type == "repair_proposal":
                score = 0.75
            elif signal_type == "open_gap":
                score = 0.5

            if sig.get("correlation_boost"):
                score = min(1.0, score + 0.1)

            sig["confidence_score"] = round(score, 3)

        return sorted(
            signals,
            key=lambda s: _PRIORITY_ORDER.get(s.get("priority", "low"), 3),
        )

    def _format_recommendation(self, signal: Dict[str, Any]) -> Recommendation:
        """Translate a raw signal dict into a typed Recommendation object."""
        signal_type = signal.get("signal_type", "")
        source = signal.get("source", "unknown")
        priority = signal.get("priority", "medium")
        confidence = signal.get("confidence_score", 0.5)
        description = signal.get("description", "No description provided.")
        sig_id = signal.get("id", uuid.uuid4().hex[:12])

        # Determine recommendation type and form-specific fields
        if signal_type == "dependency_finding":
            rec_type = RecommendationType.SDK_UPDATE
            suggested_action = (
                f"Update {signal.get('package_name', 'package')} from "
                f"{signal.get('current_version', '?')} to "
                f"{signal.get('recommended_version', 'latest')}."
            )
            risk = "high" if priority in ("critical", "high") else "medium"
            auto_applicable = False
            requires_review = True
            effort = "< 1h"

        elif signal_type == "bug_report":
            rec_type = RecommendationType.BUG_REPORT_RESPONSE
            patterns = signal.get("patterns_detected", 0)
            suggested_action = (
                f"Investigate {patterns} detected pattern(s) and apply suggested patches. "
                "Review bug report for automated fix candidates."
            )
            risk = "high" if priority in ("critical", "high") else "medium"
            auto_applicable = False
            requires_review = True
            effort = "1–4h"

        elif signal_type == "component_health":
            rec_type = RecommendationType.MAINTENANCE
            component = signal.get("component", "unknown")
            status = signal.get("status", "unknown")
            suggested_action = (
                f"Investigate and restore component '{component}' (current status: {status}). "
                "Consider service restart or config reload."
            )
            risk = "high" if status == "unhealthy" else "medium"
            auto_applicable = status != "unhealthy"
            requires_review = status == "unhealthy"
            effort = "< 1h"

        elif signal_type == "repair_proposal":
            rec_type = RecommendationType.MAINTENANCE
            suggested_action = signal.get("suggested_action", "Apply repair proposal.")
            risk = "medium"
            auto_applicable = False
            requires_review = True
            effort = "1–4h"

        elif signal_type == "improvement_proposal":
            rec_type = RecommendationType.OPERATIONAL_ANALYSIS
            suggested_action = signal.get("suggested_action", "Review and apply improvement proposal.")
            risk = "low"
            auto_applicable = priority in ("low", "medium")
            requires_review = priority in ("critical", "high")
            effort = "1–3d"

        elif signal_type == "open_gap":
            rec_type = RecommendationType.OPERATIONAL_ANALYSIS
            area = signal.get("area", "")
            suggested_action = (
                f"Address open gap in area '{area}'. "
                "Review task queue and assign resources."
            )
            risk = "low"
            auto_applicable = False
            requires_review = False
            effort = "1–3d"

        else:
            rec_type = RecommendationType.OPERATIONAL_ANALYSIS
            suggested_action = "Review signal and take appropriate action."
            risk = "low"
            auto_applicable = False
            requires_review = True
            effort = "unknown"

        rec_id = f"rec-{uuid.uuid4().hex[:12]}"
        return Recommendation(
            recommendation_id=rec_id,
            subsystem=source,
            recommendation_type=rec_type,
            priority=priority,
            confidence_score=confidence,
            description=description,
            suggested_action=suggested_action,
            estimated_effort=effort,
            risk_level=risk,
            auto_applicable=auto_applicable,
            requires_review=requires_review,
            related_proposals=[sig_id],
        )

    def _evict_one(self) -> None:
        """Remove the lowest-priority, oldest active recommendation (must hold _lock)."""
        if not self._recommendations:
            return
        worst: Optional[str] = None
        worst_order = -1
        for rid, rec in self._recommendations.items():
            if rec.status == "active":
                order = _PRIORITY_ORDER.get(rec.priority, 3)
                if order > worst_order:
                    worst_order = order
                    worst = rid
        if worst:
            del self._recommendations[worst]

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_recommendations(
        self,
        subsystem: Optional[str] = None,
        rec_type: Optional[RecommendationType] = None,
        priority: Optional[str] = None,
    ) -> List[Recommendation]:
        """Return active recommendations with optional filters.

        Args:
            subsystem: Filter by subsystem name.
            rec_type: Filter by RecommendationType.
            priority: Filter by priority string.

        Returns:
            Sorted list of matching Recommendation objects.
        """
        with self._lock:
            recs = list(self._recommendations.values())

        filtered = []
        for rec in recs:
            if rec.status == "dismissed":
                continue
            if subsystem is not None and rec.subsystem != subsystem:
                continue
            if rec_type is not None and rec.recommendation_type != rec_type:
                continue
            if priority is not None and rec.priority != priority:
                continue
            filtered.append(rec)

        return sorted(
            filtered,
            key=lambda r: (_PRIORITY_ORDER.get(r.priority, 3), r.created_at or ""),
        )

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            total = len(self._recommendations)
            by_priority: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for rec in self._recommendations.values():
                by_priority[rec.priority] = by_priority.get(rec.priority, 0) + 1
                by_type[rec.recommendation_type.value] = by_type.get(rec.recommendation_type.value, 0) + 1
            cycles = len(self._history)

        return {
            "engine": "SystemUpdateRecommendationEngine",
            "design_label": "ARCH-008",
            "total_active_recommendations": total,
            "recommendations_by_priority": by_priority,
            "recommendations_by_type": by_type,
            "cycles_completed": cycles,
            "subsystems_registered": list(self._collectors.keys()),
            "persistence_available": self._pm is not None,
            "event_backbone_available": self._backbone is not None,
        }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent recommendation cycle summaries.

        Args:
            limit: Maximum number of history entries to return.

        Returns:
            List of cycle summary dicts, most recent first.
        """
        with self._lock:
            history = list(reversed(self._history))
        return history[:limit]

    def acknowledge_recommendation(self, recommendation_id: str) -> bool:
        """Mark a recommendation as acknowledged.

        Args:
            recommendation_id: ID of the recommendation to acknowledge.

        Returns:
            True if found and updated, False otherwise.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None:
                return False
            rec.status = "acknowledged"
        logger.info("Recommendation acknowledged: %s", recommendation_id)
        return True

    def dismiss_recommendation(self, recommendation_id: str, reason: str) -> bool:
        """Dismiss a recommendation with a reason.

        Args:
            recommendation_id: ID of the recommendation to dismiss.
            reason: Reason for dismissal (stored in audit trail).

        Returns:
            True if found and updated, False otherwise.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None:
                return False
            rec.status = "dismissed"
            rec.dismissed_reason = reason
        logger.info("Recommendation dismissed: %s — %s", recommendation_id, reason)
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """Persist current engine state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._pm is None:
            logger.debug("No PersistenceManager attached; skipping save_state")
            return False
        with self._lock:
            state = {
                "recommendations": {
                    rid: rec.to_dict()
                    for rid, rec in self._recommendations.items()
                },
                "history": list(self._history),
            }
        try:
            self._pm.save_document(self._PERSIST_DOC_ID, state)
            logger.info("SystemUpdateRecommendationEngine state persisted")
            return True
        except Exception as exc:
            logger.error("Failed to persist SystemUpdateRecommendationEngine state: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore engine state from PersistenceManager.

        Returns True on success, False if persistence is unavailable or
        no prior state exists.
        """
        if self._pm is None:
            logger.debug("No PersistenceManager attached; skipping load_state")
            return False
        try:
            state = self._pm.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:
            logger.error("Failed to load SystemUpdateRecommendationEngine state: %s", exc)
            return False
        if state is None:
            logger.debug("No prior SystemUpdateRecommendationEngine state found")
            return False
        with self._lock:
            raw_recs = state.get("recommendations", {})
            self._recommendations = {}
            for rid, rdata in raw_recs.items():
                try:
                    self._recommendations[rid] = Recommendation.from_dict(rdata)
                except Exception as exc:
                    logger.warning("Could not restore recommendation %s: %s", rid, exc)

            self._history = list(state.get("history", []))

        logger.info("SystemUpdateRecommendationEngine state restored from persistence")
        return True

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    def _publish_cycle_event(self, report: RecommendationCycleReport) -> None:
        """Publish a SYSTEM_HEALTH event after a recommendation cycle."""
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "system_update_recommendation_engine",
                    "action": "recommendation_cycle_complete",
                    "cycle_id": report.cycle_id,
                    "total_recommendations": report.total_recommendations,
                    "subsystems_available": report.subsystems_available,
                    "by_priority": report.recommendations_by_priority,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="system_update_recommendation_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
