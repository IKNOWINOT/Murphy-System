"""
Automation Loop Connector for Murphy System.

Design Label: DEV-001 — Closed-Loop Feedback Automation
Owner: Platform Engineering
Dependencies:
  - SelfImprovementEngine (ARCH-001)
  - SelfAutomationOrchestrator (ARCH-002)
  - EventBackbone (for event-driven triggering)
  - HealthMonitor (OBS-001, for health-aware scheduling)

Implements Phase 2 — Development Automation:
  Wires the SelfImprovementEngine feedback cycle into the
  SelfAutomationOrchestrator task queue so that detected failure
  patterns automatically generate improvement tasks and detected
  success patterns feed back into confidence calibration.

Loop flow:
  1. EventBackbone delivers TASK_COMPLETED / TASK_FAILED events
  2. AutomationLoopConnector records outcomes in SelfImprovementEngine
  3. Periodically runs pattern extraction → proposal generation
  4. Converts high-priority proposals into orchestrator tasks
  5. Persists state via PersistenceManager

Safety invariants:
  - Only proposals above a configurable priority threshold create tasks
  - Duplicate detection: won't create tasks for already-tracked proposals
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

# Priority thresholds — only proposals at or above this level auto-create tasks
_PRIORITY_TO_INT = {"critical": 1, "high": 2, "medium": 3, "low": 4}


@dataclass
class LoopCycleResult:
    """Summary of a single automation loop cycle."""
    cycle_id: str
    outcomes_recorded: int
    patterns_detected: int
    proposals_generated: int
    tasks_created: int
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "outcomes_recorded": self.outcomes_recorded,
            "patterns_detected": self.patterns_detected,
            "proposals_generated": self.proposals_generated,
            "tasks_created": self.tasks_created,
            "completed_at": self.completed_at,
        }


class AutomationLoopConnector:
    """Closed-loop connector between improvement engine and orchestrator.

    Design Label: DEV-001
    Owner: Platform Engineering

    Usage::

        connector = AutomationLoopConnector(
            improvement_engine=engine,
            orchestrator=orchestrator,
            event_backbone=backbone,
        )
        # Events flow automatically; or trigger manually:
        result = connector.run_cycle()
    """

    def __init__(
        self,
        improvement_engine=None,
        orchestrator=None,
        event_backbone=None,
        auto_task_priority_threshold: str = "high",
    ) -> None:
        self._lock = threading.Lock()
        self._engine = improvement_engine
        self._orchestrator = orchestrator
        self._event_backbone = event_backbone
        self._priority_threshold = _PRIORITY_TO_INT.get(auto_task_priority_threshold, 2)
        self._tracked_proposals: Set[str] = set()
        self._cycle_history: List[LoopCycleResult] = []
        self._pending_outcomes: List[Dict[str, Any]] = []

        if self._event_backbone is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to task completion/failure events."""
        try:
            from event_backbone import EventType

            def _on_task_completed(event) -> None:
                payload = event.payload if hasattr(event, "payload") else {}
                self._queue_outcome(payload, "success")

            def _on_task_failed(event) -> None:
                payload = event.payload if hasattr(event, "payload") else {}
                self._queue_outcome(payload, "failure")

            self._event_backbone.subscribe(EventType.TASK_COMPLETED, _on_task_completed)
            self._event_backbone.subscribe(EventType.TASK_FAILED, _on_task_failed)
            logger.info("AutomationLoopConnector subscribed to EventBackbone")
        except Exception as exc:
            logger.warning("Failed to subscribe to EventBackbone: %s", exc)

    def _queue_outcome(self, payload: Dict[str, Any], outcome_type: str) -> None:
        """Queue an outcome for the next cycle."""
        with self._lock:
            capped_append(self._pending_outcomes, {
                "task_id": payload.get("task_id", f"evt-{uuid.uuid4().hex[:8]}"),
                "session_id": payload.get("session_id", "auto"),
                "outcome": outcome_type,
                "metrics": payload.get("metrics", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def run_cycle(self) -> LoopCycleResult:
        """Execute one full automation feedback cycle.

        Steps:
        1. Drain pending outcomes → SelfImprovementEngine
        2. Extract patterns
        3. Generate proposals
        4. Convert high-priority proposals into orchestrator tasks
        5. Persist state
        """
        cycle_id = f"loop-{uuid.uuid4().hex[:8]}"
        outcomes_recorded = 0
        patterns_detected = 0
        proposals_generated = 0
        tasks_created = 0

        # 1. Record pending outcomes
        if self._engine is not None:
            with self._lock:
                pending = list(self._pending_outcomes)
                self._pending_outcomes.clear()

            for raw in pending:
                try:
                    from self_improvement_engine import ExecutionOutcome, OutcomeType
                    outcome = ExecutionOutcome(
                        task_id=raw["task_id"],
                        session_id=raw["session_id"],
                        outcome=OutcomeType(raw["outcome"]),
                        metrics=raw.get("metrics", {}),
                        timestamp=raw.get("timestamp"),
                    )
                    self._engine.record_outcome(outcome)
                    outcomes_recorded += 1
                except Exception as exc:
                    logger.warning("Failed to record outcome: %s", exc)

            # 2. Extract patterns
            try:
                patterns = self._engine.extract_patterns()
                patterns_detected = len(patterns)
            except Exception as exc:
                logger.warning("Pattern extraction failed: %s", exc)

            # 3. Generate proposals
            try:
                proposals = self._engine.generate_proposals()
                proposals_generated = len(proposals)
            except Exception as exc:
                logger.warning("Proposal generation failed: %s", exc)
                proposals = []

            # 4. Convert qualifying proposals → orchestrator tasks
            if self._orchestrator is not None:
                for prop in proposals:
                    p_int = _PRIORITY_TO_INT.get(prop.priority, 99)
                    if p_int > self._priority_threshold:
                        continue
                    if prop.proposal_id in self._tracked_proposals:
                        continue
                    try:
                        from self_automation_orchestrator import TaskCategory
                        cat = self._map_category(prop.category)
                        self._orchestrator.create_task(
                            title=f"[AUTO] {prop.description}",
                            category=cat,
                            priority=p_int,
                            description=f"Auto-generated from proposal {prop.proposal_id}: "
                                        f"{prop.suggested_action}",
                        )
                        with self._lock:
                            self._tracked_proposals.add(prop.proposal_id)
                        tasks_created += 1
                    except Exception as exc:
                        logger.warning("Failed to create task for proposal %s: %s",
                                       prop.proposal_id, exc)

            # 5. Persist
            try:
                self._engine.save_state()
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                pass
            if self._orchestrator is not None:
                try:
                    self._orchestrator.save_state()
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    pass

        result = LoopCycleResult(
            cycle_id=cycle_id,
            outcomes_recorded=outcomes_recorded,
            patterns_detected=patterns_detected,
            proposals_generated=proposals_generated,
            tasks_created=tasks_created,
        )

        with self._lock:
            capped_append(self._cycle_history, result, max_size=100)

        logger.info(
            "Automation loop cycle %s: outcomes=%d patterns=%d proposals=%d tasks=%d",
            cycle_id, outcomes_recorded, patterns_detected, proposals_generated, tasks_created,
        )
        return result

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "pending_outcomes": len(self._pending_outcomes),
                "tracked_proposals": len(self._tracked_proposals),
                "cycles_completed": len(self._cycle_history),
                "priority_threshold": self._priority_threshold,
                "engine_attached": self._engine is not None,
                "orchestrator_attached": self._orchestrator is not None,
                "event_backbone_attached": self._event_backbone is not None,
            }

    def get_cycle_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._cycle_history[-limit:]
        return [r.to_dict() for r in recent]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _map_category(proposal_category: str) -> Any:
        """Map a SelfImprovementEngine category to a TaskCategory."""
        from self_automation_orchestrator import TaskCategory
        mapping = {
            "routing": TaskCategory.QUALITY_GAP,
            "gating": TaskCategory.QUALITY_GAP,
            "delivery": TaskCategory.INTEGRATION_GAP,
            "confidence": TaskCategory.QUALITY_GAP,
            "timeout": TaskCategory.QUALITY_GAP,
        }
        return mapping.get(proposal_category, TaskCategory.SELF_IMPROVEMENT)
