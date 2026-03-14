"""
Resource Scaling Controller for Murphy System.

Design Label: ADV-004 — Capacity Prediction, Scaling Decisions & Cost Tracking
Owner: DevOps Team / Platform Engineering
Dependencies:
  - EventBackbone (publishes LEARNING_FEEDBACK on scaling decisions)
  - PersistenceManager (for durable scaling history)
  - SelfOptimisationEngine (ADV-003, optional, for bottleneck data)

Implements Phase 6 — Advanced Self-Automation (continued):
  Monitors resource utilisation, predicts capacity needs using
  simple trend analysis, recommends scaling actions, and tracks
  cost impact of scaling decisions.

Flow:
  1. Record resource utilisation snapshots (cpu, memory, disk, connections)
  2. Analyse utilisation trends (moving average, growth rate)
  3. Predict when resources will exceed thresholds
  4. Recommend scaling actions (scale_up, scale_down, no_action)
  5. Record scaling decisions with cost estimates
  6. Publish events for downstream automation

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Conservative: scale-up recommended only when consistently above threshold
  - Cost-aware: all scaling decisions include cost estimates
  - Bounded: configurable max snapshots and decisions
  - Human-in-the-loop: scale-up above cost threshold requires approval
  - Audit trail: every scaling decision is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
# Scaling tuning constants
# ---------------------------------------------------------------------------

_PREDICTION_STEPS = 10       # Steps ahead to project utilisation trend
_SCALE_DOWN_RATIO = 0.5      # Mean must be below threshold × this ratio to scale down
_MIN_SAMPLES_FOR_SCALE_DOWN = 5  # Minimum samples required to recommend scale-down

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ScalingAction(str, Enum):
    """Possible scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResourceSnapshot:
    """A single resource utilisation snapshot."""
    snapshot_id: str
    resource_type: str       # cpu, memory, disk, connections
    utilisation: float       # 0.0 - 1.0 (percentage)
    capacity: float          # total available
    component: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "resource_type": self.resource_type,
            "utilisation": self.utilisation,
            "capacity": self.capacity,
            "component": self.component,
            "recorded_at": self.recorded_at,
        }


@dataclass
class ScalingRecommendation:
    """A scaling recommendation based on trend analysis."""
    recommendation_id: str
    resource_type: str
    component: str
    action: ScalingAction
    current_utilisation: float
    predicted_utilisation: float   # forecast
    threshold: float
    estimated_cost: float = 0.0
    reason: str = ""
    requires_approval: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "resource_type": self.resource_type,
            "component": self.component,
            "action": self.action.value,
            "current_utilisation": round(self.current_utilisation, 4),
            "predicted_utilisation": round(self.predicted_utilisation, 4),
            "threshold": self.threshold,
            "estimated_cost": round(self.estimated_cost, 2),
            "reason": self.reason,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }


@dataclass
class ScalingDecision:
    """A recorded scaling decision (approval / execution)."""
    decision_id: str
    recommendation_id: str
    action: ScalingAction
    approved: bool = False
    actual_cost: float = 0.0
    executed_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "recommendation_id": self.recommendation_id,
            "action": self.action.value,
            "approved": self.approved,
            "actual_cost": round(self.actual_cost, 2),
            "executed_at": self.executed_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# ResourceScalingController
# ---------------------------------------------------------------------------

class ResourceScalingController:
    """Capacity prediction, scaling decisions and cost tracking.

    Design Label: ADV-004
    Owner: DevOps Team / Platform Engineering

    Usage::

        controller = ResourceScalingController(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        controller.record_snapshot(resource_type="cpu", utilisation=0.72)
        recommendations = controller.recommend_scaling()
    """

    _DEFAULT_THRESHOLDS: Dict[str, float] = {
        "cpu": 0.80,
        "memory": 0.85,
        "disk": 0.90,
        "connections": 0.75,
    }

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_snapshots: int = 50_000,
        cost_approval_threshold: float = 100.0,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._snapshots: List[ResourceSnapshot] = []
        self._recommendations: List[ScalingRecommendation] = []
        self._decisions: List[ScalingDecision] = []
        self._max_snapshots = max_snapshots
        self._cost_approval_threshold = cost_approval_threshold

    # ------------------------------------------------------------------
    # Snapshot recording
    # ------------------------------------------------------------------

    def record_snapshot(
        self,
        resource_type: str,
        utilisation: float,
        capacity: float = 1.0,
        component: str = "",
    ) -> ResourceSnapshot:
        """Record a resource utilisation snapshot. Returns the created snapshot."""
        snapshot = ResourceSnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
            resource_type=resource_type.lower(),
            utilisation=utilisation,
            capacity=capacity,
            component=component,
        )
        with self._lock:
            if len(self._snapshots) >= self._max_snapshots:
                # Evict oldest 10 %
                evict = max(1, self._max_snapshots // 10)
                self._snapshots = self._snapshots[evict:]
            self._snapshots.append(snapshot)
        logger.info(
            "Recorded snapshot %s: %s utilisation=%.2f",
            snapshot.snapshot_id, resource_type, utilisation,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Utilisation analysis
    # ------------------------------------------------------------------

    def analyse_utilisation(
        self,
        resource_type: Optional[str] = None,
        window: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """Analyse utilisation trends across resource types.

        Returns a dict keyed by ``"resource_type:component"`` with statistics
        computed over the most recent *window* snapshots per group.
        """
        with self._lock:
            snapshots = list(self._snapshots)

        # Group snapshots by (resource_type, component)
        groups: Dict[str, List[ResourceSnapshot]] = defaultdict(list)
        for snap in snapshots:
            if resource_type and snap.resource_type != resource_type.lower():
                continue
            key = f"{snap.resource_type}:{snap.component}"
            groups[key].append(snap)

        results: Dict[str, Dict[str, Any]] = {}
        for key, snaps in groups.items():
            recent = snaps[-window:]
            values = [s.utilisation for s in recent]
            mean = sum(values) / (len(values) or 1) if values else 0.0
            trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0.0
            results[key] = {
                "mean": round(mean, 4),
                "max": round(max(values), 4) if values else 0.0,
                "min": round(min(values), 4) if values else 0.0,
                "trend": round(trend, 4),
                "samples": len(recent),
            }

        return results

    # ------------------------------------------------------------------
    # Scaling recommendations
    # ------------------------------------------------------------------

    def recommend_scaling(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        cost_per_scale_up: float = 10.0,
    ) -> List[ScalingRecommendation]:
        """Generate scaling recommendations based on trend analysis."""
        effective_thresholds = dict(self._DEFAULT_THRESHOLDS)
        if thresholds:
            effective_thresholds.update(thresholds)

        analysis = self.analyse_utilisation()
        recommendations: List[ScalingRecommendation] = []

        for key, stats in analysis.items():
            resource_type, component = key.split(":", 1)
            threshold = effective_thresholds.get(resource_type, 0.80)
            mean = stats["mean"]
            trend = stats["trend"]
            predicted = mean + trend * _PREDICTION_STEPS
            samples = stats["samples"]

            if predicted > threshold:
                action = ScalingAction.SCALE_UP
                estimated_cost = cost_per_scale_up
                reason = (
                    f"Predicted utilisation {predicted:.2%} exceeds "
                    f"threshold {threshold:.0%} for {resource_type}"
                )
            elif mean < threshold * _SCALE_DOWN_RATIO and samples > _MIN_SAMPLES_FOR_SCALE_DOWN:
                action = ScalingAction.SCALE_DOWN
                estimated_cost = 0.0
                reason = (
                    f"Mean utilisation {mean:.2%} well below threshold "
                    f"{threshold:.0%} — scale-down possible"
                )
            else:
                action = ScalingAction.NO_ACTION
                estimated_cost = 0.0
                reason = "Utilisation within acceptable range"

            rec = ScalingRecommendation(
                recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                resource_type=resource_type,
                component=component,
                action=action,
                current_utilisation=mean,
                predicted_utilisation=predicted,
                threshold=threshold,
                estimated_cost=estimated_cost,
                reason=reason,
                requires_approval=estimated_cost > self._cost_approval_threshold,
            )
            recommendations.append(rec)

        with self._lock:
            self._recommendations.extend(recommendations)

        # Persist recommendations
        if self._pm is not None:
            for rec in recommendations:
                try:
                    self._pm.save_document(
                        doc_id=rec.recommendation_id,
                        document=rec.to_dict(),
                    )
                except Exception as exc:
                    logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(recommendations)

        logger.info(
            "Generated %d scaling recommendations", len(recommendations),
        )
        return recommendations

    # ------------------------------------------------------------------
    # Decision recording
    # ------------------------------------------------------------------

    def record_decision(
        self,
        recommendation_id: str,
        approved: bool,
        actual_cost: float = 0.0,
    ) -> ScalingDecision:
        """Record a scaling decision for a recommendation."""
        # Resolve the action from the matching recommendation
        action = ScalingAction.NO_ACTION
        with self._lock:
            for rec in self._recommendations:
                if rec.recommendation_id == recommendation_id:
                    action = rec.action
                    break

        decision = ScalingDecision(
            decision_id=f"dec-{uuid.uuid4().hex[:8]}",
            recommendation_id=recommendation_id,
            action=action,
            approved=approved,
            actual_cost=actual_cost,
            executed_at=datetime.now(timezone.utc).isoformat() if approved else "",
        )
        with self._lock:
            capped_append(self._decisions, decision)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=decision.decision_id,
                    document=decision.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        logger.info(
            "Recorded scaling decision %s (approved=%s, cost=%.2f)",
            decision.decision_id, approved, actual_cost,
        )
        return decision

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_snapshots(
        self,
        resource_type: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent snapshots, optionally filtered."""
        with self._lock:
            snapshots = list(self._snapshots)
        if resource_type:
            snapshots = [s for s in snapshots if s.resource_type == resource_type.lower()]
        if component is not None:
            snapshots = [s for s in snapshots if s.component == component]
        return [s.to_dict() for s in snapshots[-limit:]]

    def get_recommendations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent scaling recommendations."""
        with self._lock:
            return [r.to_dict() for r in self._recommendations[-limit:]]

    def get_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent scaling decisions."""
        with self._lock:
            return [d.to_dict() for d in self._decisions[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return controller status summary."""
        with self._lock:
            total_cost = sum(d.actual_cost for d in self._decisions)
            return {
                "total_snapshots": len(self._snapshots),
                "total_recommendations": len(self._recommendations),
                "total_decisions": len(self._decisions),
                "total_cost": round(total_cost, 2),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, recommendations: List[ScalingRecommendation]) -> None:
        """Publish a LEARNING_FEEDBACK event with scaling recommendations."""
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "resource_scaling_controller",
                    "recommendations": [r.to_dict() for r in recommendations],
                },
                source="resource_scaling_controller",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
