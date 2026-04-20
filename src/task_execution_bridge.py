"""
Task Execution Bridge for Murphy System.

Design Label: WIRE-003 — SelfAutomationOrchestrator → LLM Prompt-Chain Bridge
Owner: Platform Engineering
Dependencies:
  - SelfAutomationOrchestrator (ARCH-002)
  - GateBypassController (GATE-001)
  - EventBackbone (optional)

Consumes tasks from the SelfAutomationOrchestrator, evaluates them
against the GateBypassController, and produces structured
TaskExecutionPlan objects.  Tasks above LOW risk are always held for
human-in-the-loop (HITL) review.  The bridge **never executes code**
— it only creates execution plans and prompt chains.

Safety invariants:
  - Never executes code directly
  - CRITICAL/HIGH/MEDIUM risk tasks always held for HITL review
  - Maximum tasks per cycle is bounded (default 5)
  - All decisions published to EventBackbone
  - Thread-safe operation with Lock

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

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_AUTO_PROCEED_RISK_LEVELS = frozenset({"minimal", "low"})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TaskExecutionPlan:
    """Structured execution plan produced by the bridge.

    Contains the prompt chain steps, gate bypass decision, HITL flag,
    and task metadata.  The plan is never executed automatically for
    CRITICAL/HIGH risk tasks.
    """
    plan_id: str
    task_id: str
    task_title: str
    task_type: str
    prompt_chain: Dict[str, str]
    bypass_granted: bool
    risk_level: str
    require_human_review: bool
    gate_reason: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    status: str = "pending"   # pending | approved | rejected | auto_approved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "task_title": self.task_title,
            "task_type": self.task_type,
            "prompt_chain_steps": list(self.prompt_chain.keys()),
            "bypass_granted": self.bypass_granted,
            "risk_level": self.risk_level,
            "require_human_review": self.require_human_review,
            "gate_reason": self.gate_reason,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "rejected_at": self.rejected_at,
            "status": self.status,
        }


@dataclass
class CycleExecutionSummary:
    """Summary returned by run_execution_cycle()."""
    cycle_id: str
    tasks_evaluated: int
    tasks_auto_approved: int
    tasks_held_for_review: int
    tasks_failed: int
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "tasks_evaluated": self.tasks_evaluated,
            "tasks_auto_approved": self.tasks_auto_approved,
            "tasks_held_for_review": self.tasks_held_for_review,
            "tasks_failed": self.tasks_failed,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class TaskExecutionBridge:
    """Bridges SelfAutomationOrchestrator tasks through GateBypassController.

    Design Label: WIRE-003
    Owner: Platform Engineering

    For each task returned by the orchestrator:
    - Classifies risk via GateBypassController
    - LOW/MINIMAL risk → auto-approved, TaskExecutionPlan created,
      TASK_SUBMITTED event published, orchestrator.complete_task() called
    - MEDIUM/HIGH/CRITICAL risk → held for HITL review,
      require_human_review=True, LEARNING_FEEDBACK event published
    - Never executes code; only creates execution plans

    Usage::

        bridge = TaskExecutionBridge(
            orchestrator=orchestrator,
            event_backbone=backbone,
            gate_bypass_controller=gate_ctrl,
        )
        summary = bridge.run_execution_cycle()
    """

    def __init__(
        self,
        orchestrator=None,
        event_backbone=None,
        gate_bypass_controller=None,
        max_tasks_per_cycle: int = 5,
    ) -> None:
        self._lock = threading.Lock()
        self._orchestrator = orchestrator
        self._backbone = event_backbone
        self._gate_ctrl = gate_bypass_controller
        self._max_tasks_per_cycle = max(1, int(max_tasks_per_cycle))

        # Plans indexed by plan_id and task_id
        self._plans: Dict[str, TaskExecutionPlan] = {}
        self._pending_review: Dict[str, TaskExecutionPlan] = {}  # task_id → plan

        # Stats
        self._total_evaluated: int = 0
        self._total_auto_approved: int = 0
        self._total_held: int = 0
        self._total_failed: int = 0
        self._cycle_history: List[CycleExecutionSummary] = []

    # ------------------------------------------------------------------
    # Core cycle
    # ------------------------------------------------------------------

    def run_execution_cycle(self) -> CycleExecutionSummary:
        """Process up to max_tasks_per_cycle tasks from the orchestrator.

        Returns a CycleExecutionSummary.
        """
        cycle_id = f"exec-{uuid.uuid4().hex[:8]}"
        tasks_evaluated = 0
        tasks_auto_approved = 0
        tasks_held = 0
        tasks_failed = 0

        if self._orchestrator is None:
            logger.debug("TaskExecutionBridge: no orchestrator attached, skipping cycle")
            return CycleExecutionSummary(
                cycle_id=cycle_id,
                tasks_evaluated=0,
                tasks_auto_approved=0,
                tasks_held_for_review=0,
                tasks_failed=0,
            )

        for _ in range(self._max_tasks_per_cycle):
            try:
                task = self._orchestrator.get_next_task()
            except Exception as exc:
                logger.warning("TaskExecutionBridge: get_next_task() failed: %s", exc)
                break

            if task is None:
                break  # No more tasks

            tasks_evaluated += 1
            task_type = str(getattr(task, "category", "self_improvement") or "self_improvement")

            # Mark as IN_PROGRESS immediately so get_next_task() won't return
            # the same task again in subsequent iterations of this cycle.
            try:
                self._orchestrator.start_task(task.task_id)
            except Exception as exc:
                logger.debug("TaskExecutionBridge: start_task() failed: %s", exc)

            # --- Gate evaluation ---
            bypass_granted = False
            risk_level = "medium"
            gate_reason = "no_gate_controller_default_hold"
            require_review = True

            if self._gate_ctrl is not None:
                try:
                    decision = self._gate_ctrl.evaluate(task_type)
                    bypass_granted = bool(decision.bypass_granted)
                    raw_risk = getattr(decision, "risk_level", "medium")
                    risk_level = str(raw_risk.value if hasattr(raw_risk, "value") else raw_risk)
                    gate_reason = str(getattr(decision, "reason", ""))
                    require_review = risk_level.lower() not in _AUTO_PROCEED_RISK_LEVELS or not bypass_granted
                except Exception as exc:
                    logger.warning("TaskExecutionBridge: gate evaluation failed for task %s: %s",
                                   task.task_id, exc)
                    require_review = True
                    gate_reason = f"gate_error: {exc}"
            else:
                # No gate controller — always hold for review (safest default)
                require_review = True

            # --- Build prompt chain ---
            prompt_chain: Dict[str, str] = {}
            try:
                if hasattr(self._orchestrator, "generate_full_chain"):
                    prompt_chain = self._orchestrator.generate_full_chain(task) or {}
                else:
                    prompt_chain = {
                        "analysis": f"Analyse task: {task.title}",
                        "planning": f"Plan implementation for: {task.description}",
                    }
            except Exception as exc:
                logger.warning("TaskExecutionBridge: generate_full_chain() failed: %s", exc)
                prompt_chain = {
                    "analysis": f"Analyse task: {getattr(task, 'title', task.task_id)}",
                }

            plan = TaskExecutionPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                task_id=task.task_id,
                task_title=getattr(task, "title", task.task_id),
                task_type=task_type,
                prompt_chain=prompt_chain,
                bypass_granted=bypass_granted,
                risk_level=risk_level,
                require_human_review=require_review,
                gate_reason=gate_reason,
            )

            with self._lock:
                self._plans[plan.plan_id] = plan

            if require_review:
                plan.status = "pending"
                with self._lock:
                    self._pending_review[task.task_id] = plan
                tasks_held += 1

                # Notify via EventBackbone
                self._publish_event("learning_feedback", {
                    "source": "TaskExecutionBridge",
                    "event": "task_held_for_hitl",
                    "task_id": task.task_id,
                    "plan_id": plan.plan_id,
                    "risk_level": risk_level,
                    "reason": gate_reason,
                })
                logger.info(
                    "TaskExecutionBridge: task %s held for HITL (risk=%s reason=%s)",
                    task.task_id, risk_level, gate_reason,
                )
            else:
                # Auto-approve and complete
                plan.status = "auto_approved"
                plan.approved_at = datetime.now(timezone.utc).isoformat()

                self._publish_event("task_submitted", plan.to_dict())

                try:
                    self._orchestrator.complete_task(task.task_id, result={"plan_id": plan.plan_id})
                except Exception as exc:
                    logger.warning("TaskExecutionBridge: complete_task() failed: %s", exc)
                    tasks_failed += 1
                    if self._gate_ctrl is not None:
                        try:
                            self._gate_ctrl.record_failure(task_type)
                        except Exception:
                            logger.debug("Suppressed exception in task_execution_bridge")
                    continue

                if self._gate_ctrl is not None:
                    try:
                        self._gate_ctrl.record_success(task_type)
                    except Exception as exc:
                        logger.debug("TaskExecutionBridge: record_success() failed: %s", exc)

                tasks_auto_approved += 1
                logger.info(
                    "TaskExecutionBridge: task %s auto-approved (risk=%s)",
                    task.task_id, risk_level,
                )

        summary = CycleExecutionSummary(
            cycle_id=cycle_id,
            tasks_evaluated=tasks_evaluated,
            tasks_auto_approved=tasks_auto_approved,
            tasks_held_for_review=tasks_held,
            tasks_failed=tasks_failed,
        )

        with self._lock:
            self._total_evaluated += tasks_evaluated
            self._total_auto_approved += tasks_auto_approved
            self._total_held += tasks_held
            self._total_failed += tasks_failed
            capped_append(self._cycle_history, summary, max_size=100)

        logger.info(
            "TaskExecutionBridge cycle %s: evaluated=%d auto=%d held=%d failed=%d",
            cycle_id, tasks_evaluated, tasks_auto_approved, tasks_held, tasks_failed,
        )
        return summary

    # ------------------------------------------------------------------
    # HITL workflow
    # ------------------------------------------------------------------

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Return all tasks currently held for human review."""
        with self._lock:
            return [p.to_dict() for p in self._pending_review.values()
                    if p.status == "pending"]

    def approve_task(self, task_id: str) -> bool:
        """Approve a HITL-held task and complete it in the orchestrator.

        Returns True if the task was found and approved.
        """
        with self._lock:
            plan = self._pending_review.get(task_id)

        if plan is None or plan.status != "pending":
            logger.debug("TaskExecutionBridge.approve_task: task %s not found or not pending", task_id)
            return False

        plan.status = "approved"
        plan.approved_at = datetime.now(timezone.utc).isoformat()

        if self._orchestrator is not None:
            try:
                self._orchestrator.complete_task(task_id, result={"plan_id": plan.plan_id, "approved": True})
            except Exception as exc:
                logger.warning("TaskExecutionBridge.approve_task: complete_task failed: %s", exc)

        if self._gate_ctrl is not None:
            try:
                self._gate_ctrl.record_success(plan.task_type)
            except Exception as exc:
                logger.debug("TaskExecutionBridge.approve_task: record_success failed: %s", exc)

        self._publish_event("task_submitted", {
            **plan.to_dict(),
            "hitl_approved": True,
        })

        with self._lock:
            self._pending_review.pop(task_id, None)

        logger.info("TaskExecutionBridge: task %s approved via HITL", task_id)
        return True

    def reject_task(self, task_id: str, reason: str = "") -> bool:
        """Reject a HITL-held task and fail it in the orchestrator.

        Returns True if the task was found and rejected.
        """
        with self._lock:
            plan = self._pending_review.get(task_id)

        if plan is None or plan.status != "pending":
            logger.debug("TaskExecutionBridge.reject_task: task %s not found or not pending", task_id)
            return False

        plan.status = "rejected"
        plan.rejected_at = datetime.now(timezone.utc).isoformat()

        if self._orchestrator is not None:
            try:
                self._orchestrator.fail_task(task_id, reason=reason or "rejected_by_human")
            except Exception as exc:
                logger.warning("TaskExecutionBridge.reject_task: fail_task failed: %s", exc)

        if self._gate_ctrl is not None:
            try:
                self._gate_ctrl.record_failure(plan.task_type)
            except Exception as exc:
                logger.debug("TaskExecutionBridge.reject_task: record_failure failed: %s", exc)

        self._publish_event("learning_feedback", {
            "source": "TaskExecutionBridge",
            "event": "task_rejected_by_human",
            "task_id": task_id,
            "plan_id": plan.plan_id,
            "reason": reason,
        })

        with self._lock:
            self._pending_review.pop(task_id, None)

        logger.info("TaskExecutionBridge: task %s rejected via HITL (reason=%s)", task_id, reason)
        return True

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return execution statistics."""
        with self._lock:
            return {
                "total_evaluated": self._total_evaluated,
                "total_auto_approved": self._total_auto_approved,
                "total_held_for_review": self._total_held,
                "total_failed": self._total_failed,
                "pending_review_count": len([p for p in self._pending_review.values()
                                             if p.status == "pending"]),
                "cycles_completed": len(self._cycle_history),
                "max_tasks_per_cycle": self._max_tasks_per_cycle,
                "orchestrator_attached": self._orchestrator is not None,
                "gate_controller_attached": self._gate_ctrl is not None,
                "event_backbone_attached": self._backbone is not None,
            }

    def get_cycle_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent cycle summaries."""
        with self._lock:
            return [s.to_dict() for s in self._cycle_history[-limit:]]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish_event(self, event_type_name: str, payload: Dict[str, Any]) -> None:
        """Publish an event to the EventBackbone if available."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            evt = EventType[event_type_name.upper()]
            self._backbone.publish(evt, payload)
        except KeyError:
            logger.debug("TaskExecutionBridge: unknown event type %s", event_type_name)
        except Exception as exc:
            logger.debug("TaskExecutionBridge: publish failed (%s): %s", event_type_name, exc)
