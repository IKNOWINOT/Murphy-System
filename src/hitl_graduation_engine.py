# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
HITL Graduation Engine for Murphy System Runtime

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

This module implements the mathematical core that decides when processes
graduate from human-in-the-loop (HITL) oversight to automated operation.
Every HITL item carries its own AI recommendation.

Key capabilities:
- Graduation score formula: G = S × (1 - R) × I
- Mode transitions: manual → supervised → automated
- Always-available rollback to any previous mode
- Per-item AI recommendations with reasoning, confidence, and suggested actions
- Thread-safe operation with UTC ISO timestamps
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.2,
}

GRADUATION_THRESHOLD = 0.85
SUPERVISED_THRESHOLD = 0.60

VALID_MODES = ("manual", "supervised", "automated")


# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------

@dataclass
class HITLRecommendation:
    """AI recommendation for a single HITL item."""
    item_id: str
    current_mode: str          # "manual" | "supervised" | "automated"
    recommended_mode: str
    graduation_score: float    # the G value
    success_rate: float
    risk_score: float
    impact_score: float
    reasoning: str             # human-readable explanation of WHY
    confidence: float          # 0.0-1.0 how confident the engine is
    suggested_actions: List[str]
    rollback_plan: str         # how to revert if automated fails
    created_at: str


@dataclass
class HITLItem:
    """A tracked HITL process item."""
    item_id: str
    domain: str
    description: str
    severity: str = "medium"
    consequence_factor: float = 0.5
    current_mode: str = "manual"
    mode_history: List[str] = field(default_factory=list)
    latest_recommendation: Optional[HITLRecommendation] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Core engine
# ------------------------------------------------------------------

class HITLGraduationEngine:
    """Mathematical core for HITL graduation decisions.

    Computes graduation scores and generates AI recommendations for each
    HITL item by wiring together WingmanProtocol, GoldenPathBridge, and
    TelemetryAdapter signals.
    """

    def __init__(self, telemetry_adapter=None) -> None:
        self._telemetry = telemetry_adapter

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    def compute_success_rate(self, wingman_protocol, pair_id: str) -> float:
        """Compute success rate from WingmanProtocol validation history.

        Returns approved / total, or 0.0 when there is no history.
        """
        history = wingman_protocol.get_validation_history(pair_id)
        total = len(history)
        if total == 0:
            return 0.0
        approved = sum(1 for r in history if r.get("approved"))
        return approved / total

    def compute_risk_score(
        self,
        success_rate: float,
        severity: str,
        consequence_factor: float,
    ) -> float:
        """Compute risk score: R = severity_weight × (1 - S) × consequence_factor."""
        weight = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["medium"])
        return weight * (1.0 - success_rate) * consequence_factor

    def compute_impact_score(
        self,
        time_blocked: float,
        cycle_time: float,
    ) -> float:
        """Compute production impact: I = time_blocked / cycle_time, clamped 0-1."""
        if cycle_time <= 0:
            return 0.0
        raw = time_blocked / cycle_time
        return max(0.0, min(1.0, raw))

    def compute_graduation_score(
        self,
        success_rate: float,
        risk_score: float,
        impact_score: float,
    ) -> float:
        """Compute G = S × (1 - R) × I."""
        return success_rate * (1.0 - risk_score) * impact_score

    # ------------------------------------------------------------------
    # Recommendation generation
    # ------------------------------------------------------------------

    def recommend_mode(self, current_mode: str, graduation_score: float) -> str:
        """Determine the recommended mode based on graduation score."""
        if graduation_score >= GRADUATION_THRESHOLD:
            return "automated"
        if graduation_score >= SUPERVISED_THRESHOLD:
            return "supervised"
        return "manual"

    def build_recommendation(
        self,
        item: HITLItem,
        wingman_protocol,
        pair_id: str,
        cycle_time: float = 3600.0,
        time_blocked: float = 0.0,
        golden_path_bridge=None,
    ) -> HITLRecommendation:
        """Generate a full HITLRecommendation for an item."""
        success_rate = self.compute_success_rate(wingman_protocol, pair_id)
        risk_score = self.compute_risk_score(
            success_rate, item.severity, item.consequence_factor
        )
        impact_score = self.compute_impact_score(time_blocked, cycle_time)
        graduation_score = self.compute_graduation_score(
            success_rate, risk_score, impact_score
        )

        recommended_mode = self.recommend_mode(item.current_mode, graduation_score)

        # Build human-readable reasoning
        reasoning = self._build_reasoning(
            item, success_rate, risk_score, impact_score, graduation_score, recommended_mode
        )

        # Confidence: higher when graduation score is decisively above or below thresholds
        confidence = self._compute_confidence(graduation_score, recommended_mode)

        # Suggested actions
        suggested_actions = self._build_suggested_actions(
            item, recommended_mode, graduation_score, success_rate
        )

        # Rollback plan
        rollback_plan = (
            f"To revert {item.item_id}, call rollback_item('{item.item_id}'). "
            f"The process will return to '{item.current_mode}' mode immediately. "
            "All subsequent validations will require human approval."
        )

        # Collect graduation metrics via TelemetryAdapter
        if self._telemetry is not None:
            try:
                self._telemetry.collect_metric(
                    metric_type="performance",
                    metric_name="hitl_graduation_score",
                    value=graduation_score,
                    labels={
                        "item_id": item.item_id,
                        "domain": item.domain,
                        "severity": item.severity,
                        "current_mode": item.current_mode,
                        "recommended_mode": recommended_mode,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("TelemetryAdapter.collect_metric failed: %s", exc)

        return HITLRecommendation(
            item_id=item.item_id,
            current_mode=item.current_mode,
            recommended_mode=recommended_mode,
            graduation_score=round(graduation_score, 6),
            success_rate=round(success_rate, 6),
            risk_score=round(risk_score, 6),
            impact_score=round(impact_score, 6),
            reasoning=reasoning,
            confidence=round(confidence, 6),
            suggested_actions=suggested_actions,
            rollback_plan=rollback_plan,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_reasoning(
        self,
        item: HITLItem,
        success_rate: float,
        risk_score: float,
        impact_score: float,
        graduation_score: float,
        recommended_mode: str,
    ) -> str:
        if graduation_score >= GRADUATION_THRESHOLD:
            return (
                f"This process has achieved {graduation_score:.0%} graduation score. "
                f"Murphy recommends transitioning to {recommended_mode}. "
                "You'll still receive reports. Rollback available anytime."
            )
        if graduation_score >= SUPERVISED_THRESHOLD:
            needed = GRADUATION_THRESHOLD - graduation_score
            return (
                f"Graduation score {graduation_score:.0%} qualifies for supervised mode "
                f"(threshold {SUPERVISED_THRESHOLD:.0%}). "
                f"Full automation requires {needed:.0%} more improvement. "
                f"Success rate is {success_rate:.0%}, risk score {risk_score:.2f}, "
                f"production impact {impact_score:.2f}."
            )
        return (
            f"Graduation score {graduation_score:.0%} is below supervised threshold "
            f"({SUPERVISED_THRESHOLD:.0%}). Process stays in manual mode. "
            f"Success rate is {success_rate:.0%} (need higher validation approval rate), "
            f"risk score {risk_score:.2f} for severity '{item.severity}', "
            f"production impact {impact_score:.2f}."
        )

    def _compute_confidence(self, graduation_score: float, recommended_mode: str) -> float:
        """Confidence is highest when score is clearly above/below thresholds."""
        if recommended_mode == "automated":
            margin = graduation_score - GRADUATION_THRESHOLD
        elif recommended_mode == "supervised":
            distance_from_lower = graduation_score - SUPERVISED_THRESHOLD
            distance_from_upper = GRADUATION_THRESHOLD - graduation_score
            margin = min(distance_from_lower, distance_from_upper)
        else:
            margin = SUPERVISED_THRESHOLD - graduation_score

        # Map margin (0–1 range) to a 0.5–1.0 confidence range
        return min(1.0, 0.5 + margin * 2.0)

    def _build_suggested_actions(
        self,
        item: HITLItem,
        recommended_mode: str,
        graduation_score: float,
        success_rate: float,
    ) -> List[str]:
        actions: List[str] = []
        if recommended_mode == "automated":
            actions.append(
                f"Transition '{item.item_id}' to automated mode via graduate_item()."
            )
            actions.append("Set up monitoring alerts for the first 48 hours post-graduation.")
            actions.append("Review rollback plan with the team before enabling automation.")
        elif recommended_mode == "supervised":
            actions.append(
                f"Transition '{item.item_id}' to supervised mode via graduate_item()."
            )
            actions.append(
                f"Continue validation runs until success rate exceeds "
                f"{GRADUATION_THRESHOLD:.0%} to unlock full automation."
            )
            if success_rate < 0.9:
                actions.append(
                    "Investigate recent validation failures to improve success rate."
                )
        else:
            actions.append(
                "Increase approval rate by reviewing and resolving validation failures."
            )
            actions.append(
                f"Target success rate above {SUPERVISED_THRESHOLD:.0%} for supervised mode."
            )
            if graduation_score < 0.2:
                actions.append(
                    "Consider reducing consequence_factor if risk score is inflated."
                )
        return actions


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

class HITLRegistry:
    """Tracks all HITL items with their current mode, history, and recommendations.

    Thread-safe registry that stores HITLItem instances, evaluates them
    against WingmanProtocol validation data, and manages mode transitions
    including rollback.
    """

    def __init__(self, telemetry_adapter=None) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, HITLItem] = {}
        self._pair_map: Dict[str, str] = {}   # item_id -> pair_id
        self._engine = HITLGraduationEngine(telemetry_adapter=telemetry_adapter)

    # ------------------------------------------------------------------
    # Item management
    # ------------------------------------------------------------------

    def register_item(
        self,
        item_id: str,
        domain: str,
        description: str,
        severity: str = "medium",
        consequence_factor: float = 0.5,
    ) -> HITLItem:
        """Register a new HITL item and return it."""
        if severity not in SEVERITY_WEIGHTS:
            severity = "medium"
        item = HITLItem(
            item_id=item_id,
            domain=domain,
            description=description,
            severity=severity,
            consequence_factor=consequence_factor,
            current_mode="manual",
            mode_history=["manual"],
        )
        with self._lock:
            self._items[item_id] = item
        logger.info(
            "Registered HITL item %s in domain '%s' (severity=%s)",
            item_id, domain, severity,
        )
        return item

    def get_item(self, item_id: str) -> Optional[HITLItem]:
        """Return an item by id, or None if not found."""
        with self._lock:
            return self._items.get(item_id)

    def list_items(
        self,
        domain: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> List[HITLItem]:
        """List all items, optionally filtered by domain and/or mode."""
        with self._lock:
            items = list(self._items.values())
        if domain is not None:
            items = [i for i in items if i.domain == domain]
        if mode is not None:
            items = [i for i in items if i.current_mode == mode]
        return items

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_item(
        self,
        item_id: str,
        wingman_protocol,
        pair_id: Optional[str] = None,
        cycle_time: float = 3600.0,
        time_blocked: float = 0.0,
        golden_path_bridge=None,
    ) -> HITLRecommendation:
        """Evaluate a single item and store the latest recommendation.

        If *pair_id* is not provided, the engine uses the pair_id previously
        associated with this item (via a prior evaluate_item call), or falls
        back to the item_id itself as the pair_id key.
        """
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"HITL item '{item_id}' is not registered.")

        resolved_pair_id = pair_id or self._pair_map.get(item_id, item_id)
        if pair_id is not None:
            with self._lock:
                self._pair_map[item_id] = pair_id

        recommendation = self._engine.build_recommendation(
            item=item,
            wingman_protocol=wingman_protocol,
            pair_id=resolved_pair_id,
            cycle_time=cycle_time,
            time_blocked=time_blocked,
            golden_path_bridge=golden_path_bridge,
        )

        with self._lock:
            item.latest_recommendation = recommendation

        logger.info(
            "Evaluated HITL item %s: G=%.4f, recommended_mode=%s",
            item_id, recommendation.graduation_score, recommendation.recommended_mode,
        )
        return recommendation

    def evaluate_all(
        self,
        wingman_protocol,
        cycle_time: float = 3600.0,
        time_blocked: float = 0.0,
        golden_path_bridge=None,
    ) -> List[HITLRecommendation]:
        """Evaluate every registered item and return all recommendations."""
        with self._lock:
            item_ids = list(self._items.keys())
        results: List[HITLRecommendation] = []
        for iid in item_ids:
            rec = self.evaluate_item(
                item_id=iid,
                wingman_protocol=wingman_protocol,
                cycle_time=cycle_time,
                time_blocked=time_blocked,
                golden_path_bridge=golden_path_bridge,
            )
            results.append(rec)
        return results

    # ------------------------------------------------------------------
    # Mode transitions
    # ------------------------------------------------------------------

    def graduate_item(self, item_id: str, new_mode: str) -> bool:
        """Transition an item to a new mode.

        Returns True on success, False if the item is not found or the
        mode is invalid.
        """
        if new_mode not in VALID_MODES:
            logger.warning(
                "graduate_item: invalid mode '%s' for item %s", new_mode, item_id
            )
            return False
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return False
            item.mode_history.append(item.current_mode)
            item.current_mode = new_mode
        logger.info("Graduated HITL item %s to mode '%s'", item_id, new_mode)
        return True

    def rollback_item(self, item_id: str) -> bool:
        """Roll back an item to its previous mode.

        Always succeeds as long as there is a previous mode in the history.
        Returns True on success, False if the item is not found or there is
        no history to roll back to.
        """
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return False
            if not item.mode_history:
                return False
            previous_mode = item.mode_history.pop()
            item.current_mode = previous_mode
        logger.info("Rolled back HITL item %s to mode '%s'", item_id, previous_mode)
        return True

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Return a summary dict suitable for UI consumption."""
        with self._lock:
            items = list(self._items.values())

        mode_counts: Dict[str, int] = {"manual": 0, "supervised": 0, "automated": 0}
        domain_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        graduation_candidates: List[str] = []
        total_items = len(items)

        for item in items:
            mode_counts[item.current_mode] = mode_counts.get(item.current_mode, 0) + 1
            domain_counts[item.domain] = domain_counts.get(item.domain, 0) + 1
            severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1
            if (
                item.latest_recommendation is not None
                and item.latest_recommendation.recommended_mode != item.current_mode
            ):
                graduation_candidates.append(item.item_id)

        return {
            "total_items": total_items,
            "mode_counts": mode_counts,
            "domain_counts": domain_counts,
            "severity_counts": severity_counts,
            "graduation_candidates": graduation_candidates,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
