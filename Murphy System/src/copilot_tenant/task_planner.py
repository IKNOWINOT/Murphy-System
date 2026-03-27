# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Task Planner (Priority Sequencer)

Determines what the Copilot Tenant should work on next by combining:
  - src/readiness_bootstrap_orchestrator.py  (capability readiness)
  - src/operations_cycle_engine.py           (operational priorities)
  - src/scheduler.py                         (scheduled tasks)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from readiness_bootstrap_orchestrator import ReadinessBootstrapOrchestrator
    _READINESS_AVAILABLE = True
except Exception:  # pragma: no cover
    ReadinessBootstrapOrchestrator = None  # type: ignore[assignment,misc]
    _READINESS_AVAILABLE = False

try:
    from operations_cycle_engine import OperationsCycleEngine
    _OPS_CYCLE_AVAILABLE = True
except Exception:  # pragma: no cover
    OperationsCycleEngine = None  # type: ignore[assignment,misc]
    _OPS_CYCLE_AVAILABLE = False

try:
    from scheduler import MurphyScheduler
    _SCHEDULER_AVAILABLE = True
except Exception:  # pragma: no cover
    MurphyScheduler = None  # type: ignore[assignment,misc]
    _SCHEDULER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PlannedTask:
    task_id: str                = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str              = "generic"
    description: str            = ""
    priority: float             = 0.5          # 0.0 (low) … 1.0 (critical)
    domain: str                 = "general"
    source: str                 = "task_planner"
    proposed_at: str            = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any]    = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TaskPlanner
# ---------------------------------------------------------------------------

class TaskPlanner:
    """Determines what needs doing next and orders tasks by priority.

    Uses the readiness orchestrator to evaluate which capabilities are ready,
    the operations cycle engine for current operational priorities, and the
    scheduler for time-based tasks.
    """

    def __init__(self) -> None:
        self._readiness: Any  = None
        self._ops_cycle: Any  = None
        self._scheduler: Any  = None
        self._initialize()

    def _initialize(self) -> None:
        if _READINESS_AVAILABLE:
            try:
                self._readiness = ReadinessBootstrapOrchestrator()
            except Exception as exc:
                logger.debug("ReadinessBootstrapOrchestrator init failed: %s", exc)
        if _OPS_CYCLE_AVAILABLE:
            try:
                self._ops_cycle = OperationsCycleEngine()
            except Exception as exc:
                logger.debug("OperationsCycleEngine init failed: %s", exc)
        if _SCHEDULER_AVAILABLE:
            try:
                self._scheduler = MurphyScheduler()
            except Exception as exc:
                logger.debug("MurphyScheduler init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess_system_state(self) -> Dict[str, Any]:
        """Return a snapshot of system capability and operational readiness."""
        state: Dict[str, Any] = {
            "assessed_at": datetime.now(timezone.utc).isoformat(),
            "readiness":   {},
            "ops_status":  {},
            "scheduler":   {},
        }
        if self._readiness is not None:
            try:
                state["readiness"] = (
                    self._readiness.get_readiness_status()
                    if hasattr(self._readiness, "get_readiness_status")
                    else {}
                )
            except Exception as exc:
                logger.debug("readiness assessment failed: %s", exc)
        if self._ops_cycle is not None:
            try:
                state["ops_status"] = (
                    self._ops_cycle.get_status()
                    if hasattr(self._ops_cycle, "get_status")
                    else {}
                )
            except Exception as exc:
                logger.debug("ops cycle status failed: %s", exc)
        if self._scheduler is not None:
            try:
                state["scheduler"] = self._scheduler.get_status()
            except Exception as exc:
                logger.debug("scheduler status failed: %s", exc)
        return state

    def generate_task_queue(self) -> List[PlannedTask]:
        """Build a raw (unordered) list of candidate tasks."""
        tasks: List[PlannedTask] = []
        # Operational cycle tasks
        if self._ops_cycle is not None:
            try:
                ops_tasks = (
                    self._ops_cycle.get_pending_tasks()
                    if hasattr(self._ops_cycle, "get_pending_tasks")
                    else []
                )
                for t in ops_tasks:
                    tasks.append(PlannedTask(
                        task_type=t.get("type", "ops_cycle"),
                        description=t.get("description", ""),
                        priority=float(t.get("priority", 0.5)),
                        domain=t.get("domain", "operations"),
                        source="ops_cycle_engine",
                        metadata=t,
                    ))
            except Exception as exc:
                logger.debug("ops cycle task fetch failed: %s", exc)
        # Readiness-driven tasks
        if self._readiness is not None:
            try:
                gaps = (
                    self._readiness.get_capability_gaps()
                    if hasattr(self._readiness, "get_capability_gaps")
                    else []
                )
                for gap in gaps:
                    tasks.append(PlannedTask(
                        task_type="capability_gap",
                        description=f"Close capability gap: {gap}",
                        priority=0.7,
                        domain="readiness",
                        source="readiness_orchestrator",
                        metadata={"gap": gap},
                    ))
            except Exception as exc:
                logger.debug("readiness gap fetch failed: %s", exc)
        # Default heartbeat task
        if not tasks:
            tasks.append(PlannedTask(
                task_type="heartbeat",
                description="Periodic system health check",
                priority=0.3,
                domain="monitoring",
                source="task_planner",
            ))
        return tasks

    def prioritize(self, tasks: List[PlannedTask]) -> List[PlannedTask]:
        """Return tasks sorted descending by priority."""
        return sorted(tasks, key=lambda t: t.priority, reverse=True)
