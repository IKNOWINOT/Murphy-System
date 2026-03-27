# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Swarm Rosetta Bridge — Murphy System

Lightweight adapter that publishes swarm execution events into the Rosetta
state-management system so all 7 swarm subsystems appear in the unified
agent-state document.

Every method is opt-in and gracefully degrades: if Rosetta is unavailable
the bridge is a no-op and the swarm continues normally.

Subsystems wired
────────────────
  1. TrueSwarmSystem          — phase completion + artifact counts
  2. SwarmProposalGenerator   — proposal created + step execution results
  3. CollaborativeTaskOrchestrator — orchestration start/finish
  4. DurableSwarmOrchestrator — task lifecycle (spawn / complete / fail)
  5. SelfCodebaseSwarm        — proposal / build events
  6. WorkflowDAGEngine        — workflow registration + execution
  7. LLMSwarmController       — swarmauto execution results

Usage::

    from swarm_rosetta_bridge import SwarmRosettaBridge

    bridge = SwarmRosettaBridge(rosetta_manager=my_rosetta)

    # Call from any subsystem:
    bridge.on_phase_complete("EXPAND", artifacts=12, gates=3)
    bridge.on_step_executed(step_id="step_1", result={"status": "completed"})
    bridge.on_proposal_created(proposal_id="prop_123", task="build API")

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_AGENT_ID = "murphy-swarm"
_MAX_RECENT_EVENTS = 200   # CWE-770: bounded history


class SwarmRosettaBridge:
    """Publishes swarm lifecycle events to the Rosetta state document.

    All public methods are thread-safe and never raise — any internal error is
    logged at DEBUG level and silently suppressed so the swarm itself is never
    blocked by a Rosetta write failure.
    """

    def __init__(self, rosetta_manager: Optional[Any] = None) -> None:
        """
        Args:
            rosetta_manager: A ``RosettaManager`` instance (or None to disable
                             Rosetta publishing while keeping the bridge alive
                             for metrics/logging).
        """
        self._rosetta = rosetta_manager
        self._lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []
        self._stats: Dict[str, int] = {
            "phases_completed": 0,
            "steps_executed": 0,
            "proposals_created": 0,
            "builds_completed": 0,
            "workflows_registered": 0,
            "dag_executions": 0,
            "tasks_spawned": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

    # ------------------------------------------------------------------
    # TrueSwarmSystem — phase / artifact events
    # ------------------------------------------------------------------

    def on_phase_complete(
        self,
        phase: str,
        artifacts: int = 0,
        gates: int = 0,
        confidence_impact: float = 0.0,
        murphy_risk: float = 0.0,
    ) -> None:
        """Called when TrueSwarmSystem.execute_phase() finishes."""
        with self._lock:
            self._stats["phases_completed"] += 1
        self._emit("phase_complete", {
            "phase": phase,
            "artifacts": artifacts,
            "gates": gates,
            "confidence_impact": confidence_impact,
            "murphy_risk": murphy_risk,
        })

    # ------------------------------------------------------------------
    # SwarmProposalGenerator — proposal / execution events
    # ------------------------------------------------------------------

    def on_proposal_created(self, proposal_id: str, task: str, confidence: float = 0.0) -> None:
        """Called when SwarmProposalGenerator.generate_proposal() completes."""
        with self._lock:
            self._stats["proposals_created"] += 1
        self._emit("proposal_created", {
            "proposal_id": proposal_id,
            "task": task[:200],
            "confidence": confidence,
        })

    def on_step_executed(
        self,
        step_id: Any,
        description: str = "",
        status: str = "completed",
        cost: float = 0.0,
    ) -> None:
        """Called after each proposal step executes."""
        with self._lock:
            self._stats["steps_executed"] += 1
        self._emit("step_executed", {
            "step_id": str(step_id),
            "description": description[:200],
            "status": status,
            "cost": cost,
        })

    # ------------------------------------------------------------------
    # CollaborativeTaskOrchestrator
    # ------------------------------------------------------------------

    def on_orchestration_start(self, task: str, budget: float) -> None:
        """Called at the start of CollaborativeTaskOrchestrator.orchestrate()."""
        self._emit("orchestration_start", {"task": task[:200], "budget": budget})

    def on_orchestration_complete(
        self,
        task: str,
        steps_completed: int,
        total_cost: float,
        status: str = "completed",
    ) -> None:
        """Called when CollaborativeTaskOrchestrator.orchestrate() finishes."""
        self._emit("orchestration_complete", {
            "task": task[:200],
            "steps_completed": steps_completed,
            "total_cost": total_cost,
            "status": status,
        })

    # ------------------------------------------------------------------
    # DurableSwarmOrchestrator — task lifecycle
    # ------------------------------------------------------------------

    def on_task_spawned(self, task_id: str, description: str = "", budget: float = 0.0) -> None:
        """Called when DurableSwarmOrchestrator.spawn_task() is invoked."""
        with self._lock:
            self._stats["tasks_spawned"] += 1
        self._emit("task_spawned", {"task_id": task_id, "description": description[:200], "budget": budget})

    def on_task_completed(self, task_id: str, cost: float = 0.0) -> None:
        """Called when DurableSwarmOrchestrator.complete_task() is invoked."""
        with self._lock:
            self._stats["tasks_completed"] += 1
        self._emit("task_completed", {"task_id": task_id, "cost": cost})

    def on_task_failed(self, task_id: str, reason: str = "") -> None:
        """Called when DurableSwarmOrchestrator.fail_task() is invoked."""
        with self._lock:
            self._stats["tasks_failed"] += 1
        self._emit("task_failed", {"task_id": task_id, "reason": reason[:200]})

    # ------------------------------------------------------------------
    # SelfCodebaseSwarm — build events
    # ------------------------------------------------------------------

    def on_build_complete(
        self,
        session_id: str,
        mode: str = "",
        domain: str = "",
        sections: int = 0,
    ) -> None:
        """Called when SelfCodebaseSwarm.build_package() finishes."""
        with self._lock:
            self._stats["builds_completed"] += 1
        self._emit("build_complete", {
            "session_id": session_id,
            "mode": mode,
            "domain": domain,
            "sections": sections,
        })

    # ------------------------------------------------------------------
    # WorkflowDAGEngine
    # ------------------------------------------------------------------

    def on_workflow_registered(self, workflow_id: str, steps: int = 0) -> None:
        """Called when WorkflowDAGEngine.register_workflow() succeeds."""
        with self._lock:
            self._stats["workflows_registered"] += 1
        self._emit("workflow_registered", {"workflow_id": workflow_id, "steps": steps})

    def on_dag_execution_complete(
        self,
        execution_id: str,
        status: str = "completed",
        steps_completed: int = 0,
    ) -> None:
        """Called when WorkflowDAGEngine.execute_workflow() finishes."""
        with self._lock:
            self._stats["dag_executions"] += 1
        self._emit("dag_execution_complete", {
            "execution_id": execution_id,
            "status": status,
            "steps_completed": steps_completed,
        })

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return cumulative event statistics."""
        with self._lock:
            return dict(self._stats)

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent *limit* events (newest first)."""
        with self._lock:
            return list(reversed(self._event_log[-limit:]))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Record the event locally and push a delta to Rosetta."""
        now = datetime.now(timezone.utc).isoformat()
        event: Dict[str, Any] = {"type": event_type, "ts": now, **payload}

        # Bounded in-memory log (CWE-770)
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > _MAX_RECENT_EVENTS:
                del self._event_log[: _MAX_RECENT_EVENTS // 10]

        if self._rosetta is None:
            return

        try:
            self._rosetta.update_state(
                _AGENT_ID,
                {
                    "metadata": {
                        f"last_{event_type}_at": now,
                        "swarm_stats": self.get_stats(),
                    }
                },
            )
        except Exception as exc:
            logger.debug("SwarmRosettaBridge._emit Rosetta write failed (%s)", exc)


# ---------------------------------------------------------------------------
# Module-level singleton convenience (lazy, thread-safe)
# ---------------------------------------------------------------------------

_bridge_instance: Optional[SwarmRosettaBridge] = None
_bridge_lock = threading.Lock()


def get_bridge(rosetta_manager: Optional[Any] = None) -> SwarmRosettaBridge:
    """Return the module-level SwarmRosettaBridge singleton.

    On the first call, pass a ``rosetta_manager`` to connect to Rosetta.
    Subsequent calls return the same instance regardless of the argument.
    """
    global _bridge_instance
    with _bridge_lock:
        if _bridge_instance is None:
            _bridge_instance = SwarmRosettaBridge(rosetta_manager)
    return _bridge_instance


__all__ = [
    "SwarmRosettaBridge",
    "get_bridge",
]
