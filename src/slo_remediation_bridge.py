"""
SLO-Driven Remediation Bridge for Murphy System.

Design Label: DEV-002 — SLO Violation → Improvement Proposal Pipeline
Owner: QA Team / Platform Engineering
Dependencies:
  - OperationalSLOTracker (for SLO compliance data)
  - SelfImprovementEngine (ARCH-001, for proposal generation)
  - EventBackbone (optional, for reactive triggering)

Implements Phase 2 — Development Automation:
  Bridges the OperationalSLOTracker to the SelfImprovementEngine so that
  SLO violations automatically generate improvement proposals that feed
  into the self-automation pipeline.

Flow:
  1. Check SLO compliance via OperationalSLOTracker
  2. For each violated SLO, synthesise an ImprovementProposal
  3. Record the proposal in SelfImprovementEngine
  4. Optionally publish a LEARNING_FEEDBACK event

Safety invariants:
  - Only creates proposals for actually violated SLOs
  - Deduplication: tracks which SLO violations already have proposals
  - Thread-safe operation

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
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class RemediationAction:
    """A remediation action generated from an SLO violation."""
    action_id: str
    slo_target_name: str
    metric: str
    threshold: float
    actual_value: float
    proposal_id: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "slo_target_name": self.slo_target_name,
            "metric": self.metric,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "proposal_id": self.proposal_id,
            "created_at": self.created_at,
        }


class SLORemediationBridge:
    """Bridges SLO violations to automatic improvement proposals.

    Design Label: DEV-002
    Owner: QA Team

    Usage::

        bridge = SLORemediationBridge(
            slo_tracker=tracker,
            improvement_engine=engine,
            event_backbone=backbone,
        )
        actions = bridge.check_and_remediate()
    """

    def __init__(
        self,
        slo_tracker=None,
        improvement_engine=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._slo_tracker = slo_tracker
        self._engine = improvement_engine
        self._event_backbone = event_backbone
        self._tracked_violations: Set[str] = set()
        self._actions: List[RemediationAction] = []

    # ------------------------------------------------------------------
    # Core bridge operation
    # ------------------------------------------------------------------

    def check_and_remediate(self) -> List[RemediationAction]:
        """Check SLO compliance and create proposals for violations.

        Returns a list of remediation actions created this cycle.
        """
        if self._slo_tracker is None:
            logger.debug("No SLO tracker attached; skipping check")
            return []

        try:
            compliance = self._slo_tracker.check_slo_compliance()
        except Exception as exc:
            logger.error("SLO compliance check failed: %s", exc)
            return []

        new_actions: List[RemediationAction] = []

        targets = compliance.get("targets", compliance)
        if isinstance(targets, dict):
            items = targets.items()
        else:
            items = []

        for target_name, result in items:
            if not isinstance(result, dict):
                continue
            if result.get("compliant", True):
                continue

            # Skip if already tracked
            if target_name in self._tracked_violations:
                continue

            actual = result.get("actual", 0)
            threshold = result.get("threshold", 0)
            metric = result.get("metric", target_name)

            action = RemediationAction(
                action_id=f"slo-rem-{uuid.uuid4().hex[:8]}",
                slo_target_name=target_name,
                metric=metric,
                threshold=threshold,
                actual_value=actual,
            )

            # Create proposal in SelfImprovementEngine
            if self._engine is not None:
                try:
                    from self_improvement_engine import ImprovementProposal
                    priority = self._severity_from_gap(actual, threshold, metric)
                    proposal = ImprovementProposal(
                        proposal_id=f"slo-prop-{uuid.uuid4().hex[:8]}",
                        category="slo_violation",
                        description=(
                            f"SLO '{target_name}' violated: {metric}={actual:.4f} "
                            f"(threshold={threshold:.4f})"
                        ),
                        priority=priority,
                        source_pattern=f"slo:{target_name}",
                        suggested_action=self._suggest_action(metric, actual, threshold),
                    )
                    # Inject directly into engine's proposals
                    with self._engine._lock:
                        self._engine._proposals[proposal.proposal_id] = proposal
                    action.proposal_id = proposal.proposal_id
                    logger.info("Created proposal %s for SLO violation '%s'",
                                proposal.proposal_id, target_name)
                except Exception as exc:
                    logger.warning("Failed to create proposal for SLO '%s': %s",
                                   target_name, exc)

            new_actions.append(action)
            with self._lock:
                self._tracked_violations.add(target_name)
                capped_append(self._actions, action)

        # Publish event
        if self._event_backbone is not None and new_actions:
            try:
                from event_backbone import EventType
                self._event_backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "slo_remediation_bridge",
                        "violations_found": len(new_actions),
                        "actions": [a.to_dict() for a in new_actions],
                    },
                    source="slo_remediation_bridge",
                )
            except Exception as exc:
                logger.warning("Failed to publish remediation event: %s", exc)

        return new_actions

    def clear_tracked_violations(self) -> int:
        """Clear tracked violations so they can be re-evaluated. Returns count cleared."""
        with self._lock:
            count = len(self._tracked_violations)
            self._tracked_violations.clear()
        return count

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tracked_violations": len(self._tracked_violations),
                "violation_names": sorted(self._tracked_violations),
                "total_actions": len(self._actions),
                "slo_tracker_attached": self._slo_tracker is not None,
                "engine_attached": self._engine is not None,
                "event_backbone_attached": self._event_backbone is not None,
            }

    def get_actions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._actions[-limit:]
        return [a.to_dict() for a in recent]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _severity_from_gap(actual: float, threshold: float, metric: str) -> str:
        """Determine proposal priority based on how far actual is from threshold."""
        if metric == "success_rate":
            gap = threshold - actual
            if gap > 0.2:
                return "critical"
            elif gap > 0.1:
                return "high"
            else:
                return "medium"
        elif "latency" in metric:
            ratio = actual / threshold if threshold > 0 else 1
            if ratio > 3:
                return "critical"
            elif ratio > 2:
                return "high"
            else:
                return "medium"
        return "medium"

    @staticmethod
    def _suggest_action(metric: str, actual: float, threshold: float) -> str:
        """Generate a human-readable remediation suggestion."""
        if metric == "success_rate":
            return (
                f"Investigate and fix root causes of task failures to raise "
                f"success rate from {actual:.1%} to ≥{threshold:.1%}"
            )
        elif "latency" in metric:
            return (
                f"Optimise task execution to reduce {metric} from "
                f"{actual:.0f}ms to ≤{threshold:.0f}ms"
            )
        elif metric == "approval_ratio":
            return (
                f"Review HITL approval workflow — current ratio {actual:.1%} "
                f"is below target {threshold:.1%}"
            )
        return f"Investigate SLO violation: {metric}={actual} (target={threshold})"
