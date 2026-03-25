# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Main Persistent Agent Loop

Wires together the existing Murphy System modules into a persistent agent
loop that learns from the founder and gradually takes over routine
operations.

Training stages (CopilotTenantMode):
    OBSERVER    — watch and learn
    SUGGESTION  — propose actions for founder review
    SUPERVISED  — execute with founder approval
    AUTONOMOUS  — full autonomous operation (graduated tasks only)

Core components wired:
  - LLM Router     (copilot_tenant/llm_router.py)
  - Task Planner   (copilot_tenant/task_planner.py)
  - Decision Learner (copilot_tenant/decision_learner.py)
  - Execution Gateway (copilot_tenant/execution_gateway.py)
  - Graduation Manager (copilot_tenant/graduation_manager.py)
  - Matrix Room    (copilot_tenant/matrix_room.py)
  - Scheduler      (src/scheduler.py)
  - Operations Cycle Engine (src/operations_cycle_engine.py)
  - Self-Healing   (src/self_fix_loop.py)
  - Governance Kernel (src/governance_kernel.py)
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bounded append (CWE-770)
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class CopilotTenantMode(str, Enum):
    OBSERVER   = "observer"    # Stage A: Watch and learn
    SUGGESTION = "suggestion"  # Stage B: Propose actions
    SUPERVISED = "supervised"  # Stage C: Execute with approval
    AUTONOMOUS = "autonomous"  # Stage D: Full auto (graduated tasks only)


# ---------------------------------------------------------------------------
# CopilotTenant
# ---------------------------------------------------------------------------

class CopilotTenant:
    """Persistent internal orchestration agent for the Murphy System.

    Starts in OBSERVER mode.  Mode promotion is gated by the
    GraduationManager.  Emergency stop is always available.
    """

    def __init__(self, founder_email: str = "cpost@murphy.systems") -> None:
        self._founder_email = founder_email
        self._mode           = CopilotTenantMode.OBSERVER
        self._lock           = threading.Lock()
        self._running        = False
        self._cycle_thread: Optional[threading.Thread] = None
        self._cycle_log: List[Dict[str, Any]] = []

        # Wire sub-components
        from copilot_tenant.llm_router        import TenantLLMRouter
        from copilot_tenant.task_planner      import TaskPlanner
        from copilot_tenant.decision_learner  import DecisionLearner
        from copilot_tenant.execution_gateway import ExecutionGateway
        from copilot_tenant.graduation_manager import GraduationManager
        from copilot_tenant.matrix_room       import CopilotMatrixRoom

        self._llm        = TenantLLMRouter()
        self._planner    = TaskPlanner()
        self._learner    = DecisionLearner()
        self._gateway    = ExecutionGateway()
        self._graduation = GraduationManager()
        self._matrix     = CopilotMatrixRoom(founder_email)

        # Optional: scheduler hook
        self._scheduler: Any = None
        try:
            from scheduler import MurphyScheduler
            self._scheduler = MurphyScheduler()
        except Exception as exc:
            logger.debug("MurphyScheduler unavailable: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the persistent agent loop (hourly operations cycle)."""
        with self._lock:
            if self._running:
                logger.warning("CopilotTenant already running")
                return
            self._running = True
        logger.info("CopilotTenant: starting in %s mode for %s",
                    self._mode.value, self._founder_email)
        self._cycle_thread = threading.Thread(
            target=self._loop,
            name="copilot-tenant-loop",
            daemon=True,
        )
        self._cycle_thread.start()

    def stop(self) -> None:
        """Graceful shutdown."""
        with self._lock:
            self._running = False
        logger.info("CopilotTenant: stop requested")
        if self._cycle_thread is not None:
            self._cycle_thread.join(timeout=5)

    def _loop(self) -> None:
        """Background hourly operations loop."""
        import time
        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                self.run_cycle()
            except Exception as exc:
                logger.error("CopilotTenant cycle error: %s", exc)
            time.sleep(3600)  # hourly

    # ------------------------------------------------------------------
    # Operations cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> Dict[str, Any]:
        """One operations cycle: assess → plan → propose/execute → learn."""
        cycle_id   = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("CopilotTenant: starting cycle %s (mode=%s)", cycle_id, self._mode.value)

        # 1. Assess system state
        state = self._planner.assess_system_state()

        # 2. Generate + prioritise task queue
        tasks = self._planner.prioritize(self._planner.generate_task_queue())

        # 3. Register tasks with scheduler if available
        if self._scheduler is not None:
            try:
                task_dicts = [
                    {"task_id": t.task_id, "description": t.description, "priority": t.priority}
                    for t in tasks
                ]
                if hasattr(self._scheduler, "register_copilot_tenant_tasks"):
                    self._scheduler.register_copilot_tenant_tasks(task_dicts)
            except Exception as exc:
                logger.debug("Scheduler register_copilot_tenant_tasks failed: %s", exc)

        # 4. Execute / propose each task
        results: List[Dict[str, Any]] = []
        with self._lock:
            current_mode = self._mode
        for task in tasks:
            result = self._gateway.execute(task, current_mode)
            # Post proposals to Matrix room
            if result.status == "proposed" and result.proposal_id:
                from copilot_tenant.execution_gateway import Proposal
                self._matrix.post_proposal(Proposal(
                    proposal_id=result.proposal_id,
                    task_id=result.task_id,
                    description=task.description,
                    proposed_action=task.description,
                ))
            results.append({
                "task_id":  task.task_id,
                "status":   result.status,
                "proposal": result.proposal_id,
            })

        # 5. Check graduation opportunities
        for task in tasks:
            new_mode = self._graduation.evaluate_task_graduation(task.task_type)
            if new_mode is not None:
                self._graduation.promote_task(task.task_type, new_mode)

        cycle_record = {
            "cycle_id":  cycle_id,
            "mode":      current_mode.value,
            "started_at": started_at,
            "ended_at":  datetime.now(timezone.utc).isoformat(),
            "task_count": len(tasks),
            "results":   results,
            "state_snapshot": state,
        }
        capped_append(self._cycle_log, cycle_record)
        logger.info("CopilotTenant: cycle %s complete (%d tasks)", cycle_id, len(tasks))
        return cycle_record

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def get_mode(self) -> CopilotTenantMode:
        """Current operating mode."""
        with self._lock:
            return self._mode

    def set_mode(self, mode: CopilotTenantMode) -> None:
        """Override the operating mode (founder use only)."""
        with self._lock:
            logger.info("CopilotTenant: mode changed %s → %s", self._mode.value, mode.value)
            self._mode = mode

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Full status including mode, pending proposals, accuracy metrics."""
        with self._lock:
            mode    = self._mode
            running = self._running
        accuracy = self._learner.get_accuracy_metrics()
        graduation_report = self._graduation.get_graduation_report()
        return {
            "founder_email":      self._founder_email,
            "mode":               mode.value,
            "running":            running,
            "cycles_run":         len(self._cycle_log),
            "accuracy_metrics":   accuracy,
            "corpus_size":        self._learner.get_decision_corpus_size(),
            "graduation_report":  graduation_report,
        }
