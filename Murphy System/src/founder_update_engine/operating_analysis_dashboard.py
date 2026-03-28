"""
Founder Update Engine — Operating Analysis Dashboard

Design Label: ARCH-007 — Founder Update Engine: Operating Analysis Dashboard
Owner: Backend Team
Dependencies:
  - SubsystemRegistry (ARCH-007) — subsystem health and update history
  - RecommendationEngine (ARCH-007) — recommendation surfacing
  - BugPatternDetector (DEV-004) — active bug pattern counts
  - SelfHealingCoordinator (OBS-004) — recovery attempt history
  - DependencyAuditEngine (DEV-005) — latest audit report
  - PersistenceManager — durable snapshot history
  - EventBackbone — event publishing

Aggregates operational data from all registered Murphy subsystems into a
single dashboard snapshot.  Runs periodic analysis and generates
PERFORMANCE and MAINTENANCE recommendations when degraded conditions are
detected.

Snapshot contents:
  - Per-subsystem health summary (healthy / degraded / failed / unknown)
  - Fleet-wide health scores
  - Active bug patterns (from BugPatternDetector)
  - Recent self-healing recovery attempts
  - Dependency vulnerability counts (from DependencyAuditEngine)
  - Open recommendation counts by type
  - Analysis-generated PERFORMANCE / MAINTENANCE recommendations

Safety invariants:
  - NEVER modifies source files on disk
  - All findings are proposals only
  - Thread-safe: all shared state guarded by Lock
  - Bounded: snapshot history capped to prevent unbounded growth

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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SNAPSHOT_HISTORY = 200


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubsystemHealthSummary:
    """Health summary for a single subsystem within a dashboard snapshot.

    Attributes:
        name: Subsystem name.
        health_status: healthy / degraded / failed / unknown.
        pending_recommendations: Count of open recommendations.
        last_updated: ISO timestamp of the last applied update, or None.
        update_count: Number of updates in the update history.
    """

    name: str
    health_status: str
    pending_recommendations: int
    last_updated: Optional[str]
    update_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "health_status": self.health_status,
            "pending_recommendations": self.pending_recommendations,
            "last_updated": self.last_updated,
            "update_count": self.update_count,
        }


@dataclass
class DashboardSnapshot:
    """A point-in-time operational snapshot of the Murphy System.

    Attributes:
        snapshot_id: Unique identifier.
        total_subsystems: Total subsystems registered.
        healthy_count: Subsystems with health_status == healthy.
        degraded_count: Subsystems with health_status == degraded.
        failed_count: Subsystems with health_status == failed.
        unknown_count: Subsystems with health_status == unknown.
        health_score: Float 0.0–1.0 — fraction of healthy subsystems.
        active_bug_patterns: Count of active bug patterns from BugPatternDetector.
        critical_bug_patterns: Count of critical-severity bug patterns.
        recent_recovery_attempts: Count of self-healing attempts in the last snapshot window.
        recovery_success_rate: Float 0.0–1.0 — fraction of successful recoveries.
        open_vulnerability_count: Count of open dependency vulnerabilities.
        open_recommendations: Total open recommendations across all types.
        subsystem_summaries: Per-subsystem health detail.
        recommendations_generated: Count of new recommendations created this cycle.
        analysis_notes: Human-readable notes from the analysis pass.
        captured_at: UTC timestamp of the snapshot.
    """

    snapshot_id: str
    total_subsystems: int
    healthy_count: int
    degraded_count: int
    failed_count: int
    unknown_count: int
    health_score: float
    active_bug_patterns: int
    critical_bug_patterns: int
    recent_recovery_attempts: int
    recovery_success_rate: float
    open_vulnerability_count: int
    open_recommendations: int
    subsystem_summaries: List[SubsystemHealthSummary]
    recommendations_generated: int
    analysis_notes: List[str]
    captured_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "total_subsystems": self.total_subsystems,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "failed_count": self.failed_count,
            "unknown_count": self.unknown_count,
            "health_score": round(self.health_score, 4),
            "active_bug_patterns": self.active_bug_patterns,
            "critical_bug_patterns": self.critical_bug_patterns,
            "recent_recovery_attempts": self.recent_recovery_attempts,
            "recovery_success_rate": round(self.recovery_success_rate, 4),
            "open_vulnerability_count": self.open_vulnerability_count,
            "open_recommendations": self.open_recommendations,
            "subsystem_summaries": [s.to_dict() for s in self.subsystem_summaries],
            "recommendations_generated": self.recommendations_generated,
            "analysis_notes": self.analysis_notes,
            "captured_at": self.captured_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class OperatingAnalysisDashboard:
    """Aggregates operational data and surfaces recommendations for the Founder.

    Design Label: ARCH-007
    Owner: Backend Team

    Integrates with:
    - SubsystemRegistry      — iterates all registered subsystems for health data
    - RecommendationEngine   — reads open recommendation counts; writes new ones
    - BugPatternDetector     — reads active bug patterns and severity breakdown
    - SelfHealingCoordinator — reads recent recovery history
    - DependencyAuditEngine  — reads latest dependency vulnerability count

    Usage::

        dashboard = OperatingAnalysisDashboard(
            registry=registry,
            recommendation_engine=rec_engine,
            bug_detector=detector,
            healing_coordinator=coordinator,
            dependency_audit=dep_audit,
            persistence_manager=pm,
        )
        snapshot = dashboard.capture_snapshot()
        print(f"Health score: {snapshot.health_score:.0%}")
    """

    _PERSISTENCE_DOC_KEY = "founder_update_engine_operating_dashboard"

    # Thresholds that trigger automatic recommendations
    _HEALTH_SCORE_WARN = 0.80        # below this → PERFORMANCE rec
    _HEALTH_SCORE_CRITICAL = 0.50    # below this → MAINTENANCE rec (high priority)
    _BUG_PATTERN_WARN = 5            # more than this → MAINTENANCE rec
    _RECOVERY_RATE_WARN = 0.70       # below this → MAINTENANCE rec
    _VULN_WARN = 3                   # more than this → SECURITY rec

    def __init__(
        self,
        registry=None,
        recommendation_engine=None,
        bug_detector=None,
        healing_coordinator=None,
        dependency_audit=None,
        event_backbone=None,
        persistence_manager=None,
    ) -> None:
        self._registry = registry
        self._rec_engine = recommendation_engine
        self._bug_detector = bug_detector
        self._healing_coordinator = healing_coordinator
        self._dep_audit = dependency_audit
        self._event_backbone = event_backbone
        self._persistence = persistence_manager

        self._snapshots: List[DashboardSnapshot] = []
        self._lock = threading.Lock()

        self._load_state()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def capture_snapshot(self) -> DashboardSnapshot:
        """Aggregate operational data and produce a new :class:`DashboardSnapshot`.

        Steps:
        1. Collect subsystem health from SubsystemRegistry.
        2. Collect active bug patterns from BugPatternDetector.
        3. Collect recovery history from SelfHealingCoordinator.
        4. Collect vulnerability counts from DependencyAuditEngine.
        5. Collect open recommendation counts from RecommendationEngine.
        6. Compute aggregate scores.
        7. Run analysis pass and generate recommendations.
        8. Persist and publish.

        Returns:
            :class:`DashboardSnapshot` describing current system health.
        """
        # 1. Subsystem health
        subsystem_summaries, health_counts = self._collect_subsystem_health()
        total = sum(health_counts.values())
        healthy = health_counts.get("healthy", 0)
        health_score = (healthy / total) if total > 0 else 1.0

        # 2. Bug patterns
        active_bugs, critical_bugs = self._collect_bug_patterns()

        # 3. Recovery history
        recent_attempts, success_rate = self._collect_recovery_history()

        # 4. Vulnerability counts
        open_vulns = self._collect_vulnerability_count()

        # 5. Open recommendations
        open_recs = self._collect_open_recommendations()

        # 6. Analysis + new recommendations
        notes: List[str] = []
        new_recs = self._run_analysis(
            health_score=health_score,
            active_bugs=active_bugs,
            critical_bugs=critical_bugs,
            success_rate=success_rate,
            open_vulns=open_vulns,
            degraded_count=health_counts.get("degraded", 0),
            failed_count=health_counts.get("failed", 0),
            notes=notes,
        )

        snapshot = DashboardSnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
            total_subsystems=total,
            healthy_count=healthy,
            degraded_count=health_counts.get("degraded", 0),
            failed_count=health_counts.get("failed", 0),
            unknown_count=health_counts.get("unknown", 0),
            health_score=health_score,
            active_bug_patterns=active_bugs,
            critical_bug_patterns=critical_bugs,
            recent_recovery_attempts=recent_attempts,
            recovery_success_rate=success_rate,
            open_vulnerability_count=open_vulns,
            open_recommendations=open_recs,
            subsystem_summaries=subsystem_summaries,
            recommendations_generated=len(new_recs),
            analysis_notes=notes,
            captured_at=datetime.now(timezone.utc),
        )

        with self._lock:
            if len(self._snapshots) >= _MAX_SNAPSHOT_HISTORY:
                self._snapshots = self._snapshots[-(_MAX_SNAPSHOT_HISTORY - 1):]
            self._snapshots.append(snapshot)

        self._save_state()
        self._publish_event(snapshot)

        logger.info(
            "OperatingAnalysisDashboard: snapshot %s — score=%.2f %d/%d healthy, "
            "bugs=%d vulns=%d open_recs=%d new_recs=%d",
            snapshot.snapshot_id,
            health_score,
            healthy,
            total,
            active_bugs,
            open_vulns,
            open_recs,
            len(new_recs),
        )
        return snapshot

    def get_latest_snapshot(self) -> Optional[DashboardSnapshot]:
        """Return the most recent snapshot, or ``None`` if none have been captured."""
        with self._lock:
            return self._snapshots[-1] if self._snapshots else None

    def get_snapshot_history(self, limit: int = 20) -> List[DashboardSnapshot]:
        """Return the most recent snapshots (newest first).

        Args:
            limit: Maximum number of snapshots to return.
        """
        with self._lock:
            return list(reversed(self._snapshots[-limit:]))

    def get_status(self) -> Dict[str, Any]:
        """Return summary statistics for the dashboard."""
        with self._lock:
            total = len(self._snapshots)
            latest = self._snapshots[-1].to_dict() if self._snapshots else None
        return {
            "total_snapshots": total,
            "latest_snapshot": latest,
        }

    # ------------------------------------------------------------------
    # Data collection helpers
    # ------------------------------------------------------------------

    def _collect_subsystem_health(
        self,
    ) -> tuple:
        """Return (summaries, health_counts) from SubsystemRegistry."""
        summaries: List[SubsystemHealthSummary] = []
        counts: Dict[str, int] = {"healthy": 0, "degraded": 0, "failed": 0, "unknown": 0}

        if self._registry is None:
            return summaries, counts

        try:
            subsystems = self._registry.get_all_subsystems()
            for sub in subsystems:
                status = sub.health_status if sub.health_status in counts else "unknown"
                counts[status] = counts.get(status, 0) + 1
                summaries.append(
                    SubsystemHealthSummary(
                        name=sub.name,
                        health_status=sub.health_status,
                        pending_recommendations=sub.pending_recommendations,
                        last_updated=sub.last_updated.isoformat() if sub.last_updated else None,
                        update_count=len(sub.update_history),
                    )
                )
        except Exception as exc:
            logger.debug("OperatingAnalysisDashboard: registry collection failed: %s", exc)

        return summaries, counts

    def _collect_bug_patterns(self) -> tuple:
        """Return (active_count, critical_count) from BugPatternDetector."""
        if self._bug_detector is None:
            return 0, 0
        try:
            patterns = self._bug_detector.get_patterns(limit=200)
            active = len(patterns)
            critical = sum(1 for p in patterns if p.get("severity") == "critical")
            return active, critical
        except Exception as exc:
            logger.debug("OperatingAnalysisDashboard: bug_detector collection failed: %s", exc)
            return 0, 0

    def _collect_recovery_history(self) -> tuple:
        """Return (recent_count, success_rate) from SelfHealingCoordinator."""
        if self._healing_coordinator is None:
            return 0, 1.0
        try:
            history = self._healing_coordinator.get_history(limit=50)
            if not history:
                return 0, 1.0
            successes = sum(1 for h in history if h.get("status") == "success")
            return len(history), successes / len(history)
        except Exception as exc:
            logger.debug(
                "OperatingAnalysisDashboard: healing_coordinator collection failed: %s", exc
            )
            return 0, 1.0

    def _collect_vulnerability_count(self) -> int:
        """Return count of open vulnerabilities from DependencyAuditEngine."""
        if self._dep_audit is None:
            return 0
        try:
            reports = self._dep_audit.get_reports(limit=1)
            if reports:
                return reports[0].get("total_findings", 0)
        except Exception as exc:
            logger.debug(
                "OperatingAnalysisDashboard: dep_audit collection failed: %s", exc
            )
        return 0

    def _collect_open_recommendations(self) -> int:
        """Return count of pending/approved recommendations from RecommendationEngine."""
        if self._rec_engine is None:
            return 0
        try:
            with self._rec_engine._lock:
                return sum(
                    1
                    for r in self._rec_engine._recommendations.values()
                    if r.status in ("pending", "approved")
                )
        except Exception as exc:
            logger.debug(
                "OperatingAnalysisDashboard: rec_engine collection failed: %s", exc
            )
            return 0

    # ------------------------------------------------------------------
    # Analysis pass
    # ------------------------------------------------------------------

    def _run_analysis(
        self,
        *,
        health_score: float,
        active_bugs: int,
        critical_bugs: int,
        success_rate: float,
        open_vulns: int,
        degraded_count: int,
        failed_count: int,
        notes: List[str],
    ) -> list:
        """Evaluate current metrics and generate recommendations.

        Returns list of new Recommendation objects (already stored in engine).
        """
        if self._rec_engine is None:
            return []

        from .recommendation_engine import (
            RecommendationType,
            RecommendationPriority,
            RecommendationEngine,
        )

        recs = []

        # -- Health score thresholds -------------------------------------------
        if health_score < self._HEALTH_SCORE_CRITICAL:
            notes.append(
                f"Health score critical: {health_score:.0%} — {failed_count} subsystem(s) failed."
            )
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem="fleet",
                    rec_type=RecommendationType.MAINTENANCE,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"Critical fleet health: {health_score:.0%} healthy",
                    description=(
                        f"System health has dropped below the critical threshold "
                        f"({self._HEALTH_SCORE_CRITICAL:.0%}). "
                        f"{failed_count} subsystem(s) are in FAILED state."
                    ),
                    rationale="Health score below critical threshold requires immediate attention.",
                    actions=[
                        {
                            "action": "investigate_failed_subsystems",
                            "failed_count": failed_count,
                        }
                    ],
                    impact={"risk": "critical", "effort": "high", "benefit": "stability"},
                    auto_applicable=False,
                    requires_founder_approval=True,
                    source={
                        "engine": "OperatingAnalysisDashboard",
                        "health_score": health_score,
                    },
                )
            )
        elif health_score < self._HEALTH_SCORE_WARN:
            notes.append(
                f"Health score degraded: {health_score:.0%} — {degraded_count} subsystem(s) degraded."
            )
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem="fleet",
                    rec_type=RecommendationType.PERFORMANCE,
                    priority=RecommendationPriority.HIGH,
                    title=f"Degraded fleet health: {health_score:.0%} healthy",
                    description=(
                        f"System health is below the warning threshold "
                        f"({self._HEALTH_SCORE_WARN:.0%}). "
                        f"{degraded_count} subsystem(s) are DEGRADED."
                    ),
                    rationale="Health score below warning threshold; intervention recommended.",
                    actions=[
                        {
                            "action": "investigate_degraded_subsystems",
                            "degraded_count": degraded_count,
                        }
                    ],
                    impact={"risk": "high", "effort": "medium", "benefit": "stability"},
                    auto_applicable=False,
                    requires_founder_approval=False,
                    source={
                        "engine": "OperatingAnalysisDashboard",
                        "health_score": health_score,
                    },
                )
            )

        # -- Bug patterns -----------------------------------------------------
        if active_bugs > self._BUG_PATTERN_WARN:
            notes.append(
                f"Elevated bug patterns: {active_bugs} active ({critical_bugs} critical)."
            )
            priority = (
                RecommendationPriority.CRITICAL
                if critical_bugs > 0
                else RecommendationPriority.HIGH
            )
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem="bug_pattern_detector",
                    rec_type=RecommendationType.MAINTENANCE,
                    priority=priority,
                    title=f"High bug pattern count: {active_bugs} active patterns",
                    description=(
                        f"BugPatternDetector has detected {active_bugs} active patterns "
                        f"({critical_bugs} critical). Review and remediate recurring failures."
                    ),
                    rationale=f"Bug patterns exceed warning threshold ({self._BUG_PATTERN_WARN}).",
                    actions=[
                        {
                            "action": "review_bug_patterns",
                            "active_count": active_bugs,
                            "critical_count": critical_bugs,
                        }
                    ],
                    impact={"risk": "high", "effort": "medium", "benefit": "quality"},
                    auto_applicable=False,
                    requires_founder_approval=critical_bugs > 0,
                    source={
                        "engine": "OperatingAnalysisDashboard",
                        "active_bugs": active_bugs,
                    },
                )
            )

        # -- Recovery rate -----------------------------------------------------
        if success_rate < self._RECOVERY_RATE_WARN:
            notes.append(f"Self-healing recovery rate low: {success_rate:.0%}.")
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem="self_healing_coordinator",
                    rec_type=RecommendationType.MAINTENANCE,
                    priority=RecommendationPriority.HIGH,
                    title=f"Low self-healing success rate: {success_rate:.0%}",
                    description=(
                        f"The SelfHealingCoordinator recovery success rate has dropped to "
                        f"{success_rate:.0%} (threshold: {self._RECOVERY_RATE_WARN:.0%}). "
                        "Review recovery procedures."
                    ),
                    rationale="Recovery rate below threshold indicates unreliable self-healing.",
                    actions=[
                        {
                            "action": "review_recovery_procedures",
                            "success_rate": round(success_rate, 4),
                        }
                    ],
                    impact={"risk": "high", "effort": "medium", "benefit": "reliability"},
                    auto_applicable=False,
                    requires_founder_approval=False,
                    source={
                        "engine": "OperatingAnalysisDashboard",
                        "recovery_success_rate": success_rate,
                    },
                )
            )

        # -- Vulnerabilities --------------------------------------------------
        if open_vulns > self._VULN_WARN:
            notes.append(f"Open vulnerability count elevated: {open_vulns} findings.")
            recs.append(
                RecommendationEngine._make_recommendation(
                    subsystem="dependency_audit_engine",
                    rec_type=RecommendationType.SECURITY,
                    priority=RecommendationPriority.HIGH,
                    title=f"Dependency vulnerabilities: {open_vulns} open findings",
                    description=(
                        f"DependencyAuditEngine reports {open_vulns} open vulnerability "
                        "findings. Review and update affected packages."
                    ),
                    rationale=f"Vulnerability count exceeds warning threshold ({self._VULN_WARN}).",
                    actions=[
                        {
                            "action": "review_vulnerabilities",
                            "finding_count": open_vulns,
                        }
                    ],
                    impact={"risk": "high", "effort": "medium", "benefit": "security"},
                    auto_applicable=False,
                    requires_founder_approval=False,
                    source={
                        "engine": "OperatingAnalysisDashboard",
                        "open_vulns": open_vulns,
                    },
                )
            )

        if not notes:
            notes.append("All metrics within normal operating thresholds.")

        # Store new recommendations
        if recs:
            with self._rec_engine._lock:
                for r in recs:
                    self._rec_engine._recommendations[r.id] = r

        return recs

    # ------------------------------------------------------------------
    # Persistence & events
    # ------------------------------------------------------------------

    def _save_state(self) -> None:
        if self._persistence is None:
            return
        try:
            with self._lock:
                data = {"snapshots": [s.to_dict() for s in self._snapshots]}
            self._persistence.save_document(self._PERSISTENCE_DOC_KEY, data)
        except Exception as exc:
            logger.debug("OperatingAnalysisDashboard: failed to save state: %s", exc)

    def _load_state(self) -> None:
        if self._persistence is None:
            return
        try:
            data = self._persistence.load_document(self._PERSISTENCE_DOC_KEY)
            if not data:
                return
            with self._lock:
                for s_dict in data.get("snapshots", []):
                    try:
                        summaries = [
                            SubsystemHealthSummary(**ss)
                            for ss in s_dict.get("subsystem_summaries", [])
                        ]
                        self._snapshots.append(
                            DashboardSnapshot(
                                snapshot_id=s_dict["snapshot_id"],
                                total_subsystems=s_dict.get("total_subsystems", 0),
                                healthy_count=s_dict.get("healthy_count", 0),
                                degraded_count=s_dict.get("degraded_count", 0),
                                failed_count=s_dict.get("failed_count", 0),
                                unknown_count=s_dict.get("unknown_count", 0),
                                health_score=s_dict.get("health_score", 1.0),
                                active_bug_patterns=s_dict.get("active_bug_patterns", 0),
                                critical_bug_patterns=s_dict.get("critical_bug_patterns", 0),
                                recent_recovery_attempts=s_dict.get(
                                    "recent_recovery_attempts", 0
                                ),
                                recovery_success_rate=s_dict.get("recovery_success_rate", 1.0),
                                open_vulnerability_count=s_dict.get(
                                    "open_vulnerability_count", 0
                                ),
                                open_recommendations=s_dict.get("open_recommendations", 0),
                                subsystem_summaries=summaries,
                                recommendations_generated=s_dict.get(
                                    "recommendations_generated", 0
                                ),
                                analysis_notes=s_dict.get("analysis_notes", []),
                                captured_at=datetime.fromisoformat(s_dict["captured_at"]),
                            )
                        )
                    except Exception as exc:
                        logger.debug(
                            "OperatingAnalysisDashboard: failed to load snapshot: %s", exc
                        )
        except Exception as exc:
            logger.debug("OperatingAnalysisDashboard: failed to load state: %s", exc)

    def _publish_event(self, snapshot: DashboardSnapshot) -> None:
        if self._event_backbone is None:
            return
        try:
            from event_backbone import EventType  # type: ignore

            self._event_backbone.publish(
                EventType.SYSTEM_HEALTH,
                {
                    "source": "OperatingAnalysisDashboard",
                    "snapshot_id": snapshot.snapshot_id,
                    "health_score": snapshot.health_score,
                    "failed_count": snapshot.failed_count,
                    "active_bug_patterns": snapshot.active_bug_patterns,
                    "open_vulnerability_count": snapshot.open_vulnerability_count,
                    "recommendations_generated": snapshot.recommendations_generated,
                },
            )
        except Exception as exc:
            logger.debug("OperatingAnalysisDashboard: event publish failed: %s", exc)
