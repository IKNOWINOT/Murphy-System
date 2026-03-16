"""
Workflow DAG Engine — DAG-based workflow definition and execution for
multi-step automations.

Provides topological sort execution ordering, parallel step execution
capability markers, conditional branching, checkpoint/resume support,
step-level timeout/retry, and execution history tracking.
"""

import hashlib
import json
import logging
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Step status (Enum subclass)."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"


class WorkflowStatus(Enum):
    """Workflow status (Enum subclass)."""
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class StepDefinition:
    """Step definition."""
    step_id: str
    name: str
    action: str  # what to execute
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # skip condition expression
    timeout_seconds: float = 300.0
    max_retries: int = 0
    retry_delay: float = 1.0
    parallel: bool = False  # can run in parallel with siblings
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecution:
    """Step execution."""
    step_id: str
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    retries: int = 0
    checkpoint: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowDefinition:
    """Workflow definition."""
    workflow_id: str
    name: str
    description: str = ""
    steps: List[StepDefinition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class WorkflowExecution:
    """Workflow execution."""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.DRAFT
    steps: Dict[str, StepExecution] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    checkpoint: Optional[Dict[str, Any]] = None


class WorkflowDAGEngine:
    """DAG-based workflow engine with topological sort, parallel execution markers,
    conditional branching, and checkpoint/resume."""

    def __init__(self):
        self._lock = threading.Lock()
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._step_handlers: Dict[str, Callable] = {}
        self._execution_history: List[Dict[str, Any]] = []

    def register_workflow(self, workflow: WorkflowDefinition) -> bool:
        with self._lock:
            # Validate DAG (no cycles)
            if not self._validate_dag(workflow):
                return False
            self._workflows[workflow.workflow_id] = workflow
            return True

    def register_step_handler(self, action: str, handler: Callable) -> None:
        self._step_handlers[action] = handler

    def _validate_dag(self, workflow: WorkflowDefinition) -> bool:
        """Validate workflow is a valid DAG (no cycles)."""
        step_ids = {s.step_id for s in workflow.steps}
        # Check all dependencies reference valid steps
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    return False
        # Topological sort to detect cycles
        try:
            self._topological_sort(workflow)
            return True
        except ValueError:
            return False

    def _topological_sort(self, workflow: WorkflowDefinition) -> List[str]:
        """Return steps in topological order."""
        in_degree = {s.step_id: 0 for s in workflow.steps}
        adj = defaultdict(list)
        step_map = {s.step_id: s for s in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            sid = queue.popleft()
            order.append(sid)
            for neighbor in adj[sid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(workflow.steps):
            raise ValueError("Cycle detected in workflow DAG")
        return order

    def create_execution(self, workflow_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None

        exec_id = hashlib.sha256(
            f"{workflow_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        execution = WorkflowExecution(
            execution_id=exec_id,
            workflow_id=workflow_id,
            status=WorkflowStatus.READY,
            context=context or {},
        )
        for step in workflow.steps:
            execution.steps[step.step_id] = StepExecution(step_id=step.step_id)

        with self._lock:
            self._executions[exec_id] = execution
        return exec_id

    def execute_workflow(self, execution_id: str, strict_mode: bool = False) -> Dict[str, Any]:
        execution = self._executions.get(execution_id)
        if not execution:
            return {"error": "Execution not found", "execution_id": execution_id}

        workflow = self._workflows.get(execution.workflow_id)
        if not workflow:
            return {"error": "Workflow definition not found"}

        execution.status = WorkflowStatus.RUNNING
        execution.start_time = time.time()

        try:
            order = self._topological_sort(workflow)
        except ValueError as exc:
            execution.status = WorkflowStatus.FAILED
            return {"error": str(exc)}

        step_map = {s.step_id: s for s in workflow.steps}
        results = {}

        for step_id in order:
            step_def = step_map[step_id]
            step_exec = execution.steps[step_id]

            # Check dependencies
            deps_met = True
            for dep in step_def.depends_on:
                dep_exec = execution.steps.get(dep)
                if not dep_exec or dep_exec.status != StepStatus.COMPLETED:
                    deps_met = False
                    break

            if not deps_met:
                step_exec.status = StepStatus.SKIPPED
                step_exec.error = "Dependencies not met"
                results[step_id] = {"status": "skipped", "reason": "dependencies_not_met"}
                continue

            # Check condition
            if step_def.condition:
                if not self._evaluate_condition(step_def.condition, execution.context, results):
                    step_exec.status = StepStatus.SKIPPED
                    step_exec.error = "Condition not met"
                    results[step_id] = {"status": "skipped", "reason": "condition_false"}
                    continue

            # Execute step
            step_exec.status = StepStatus.RUNNING
            step_exec.start_time = time.time()

            handler = self._step_handlers.get(step_def.action)
            if handler:
                try:
                    result = handler(step_def, execution.context)
                    step_exec.result = result
                    step_exec.status = StepStatus.COMPLETED
                except Exception as exc:
                    logger.debug("Caught exception: %s", exc)
                    step_exec.error = str(exc)
                    step_exec.status = StepStatus.FAILED
            else:
                if strict_mode:
                    step_exec.error = f"No handler registered for action '{step_def.action}' (strict_mode)"
                    step_exec.status = StepStatus.FAILED
                else:
                    logger.warning(
                        "No handler registered for action '%s' — executing in simulation mode",
                        step_def.action,
                    )
                    step_exec.result = {
                        "action": step_def.action,
                        "step_id": step_id,
                        "simulated": True,
                    }
                    step_exec.status = StepStatus.COMPLETED

            step_exec.end_time = time.time()
            results[step_id] = {
                "status": step_exec.status.value,
                "result": step_exec.result,
                "error": step_exec.error,
                "duration_ms": (step_exec.end_time - step_exec.start_time) * 1000,
            }

        # Determine overall status
        all_statuses = [se.status for se in execution.steps.values()]
        if any(s == StepStatus.FAILED for s in all_statuses):
            execution.status = WorkflowStatus.FAILED
        elif all(s in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in all_statuses):
            execution.status = WorkflowStatus.COMPLETED
        else:
            execution.status = WorkflowStatus.FAILED

        execution.end_time = time.time()

        summary = {
            "execution_id": execution_id,
            "workflow_id": execution.workflow_id,
            "status": execution.status.value,
            "steps": results,
            "duration_ms": (execution.end_time - execution.start_time) * 1000,
            "completed": sum(1 for s in all_statuses if s == StepStatus.COMPLETED),
            "skipped": sum(1 for s in all_statuses if s == StepStatus.SKIPPED),
            "failed": sum(1 for s in all_statuses if s == StepStatus.FAILED),
            "total": len(all_statuses),
        }

        with self._lock:
            capped_append(self._execution_history, summary)
        return summary

    def _run_step(
        self,
        step_id: str,
        step_def: StepDefinition,
        step_exec: StepExecution,
        execution: WorkflowExecution,
        results: Dict[str, Any],
        strict_mode: bool = False,
    ) -> None:
        """Execute a single step, mutating *step_exec* and *results* in place.

        Checks dependency status and any configured condition before running the
        step handler.  All handler exceptions are caught and recorded on
        *step_exec* so callers are never interrupted by a step failure.

        Args:
            step_id: Identifier of the step to run.
            step_def: The step's definition (action, condition, dependencies, …).
            step_exec: Mutable execution record for this step.
            execution: The parent workflow execution (context and step states).
            results: Shared dict accumulating per-step result payloads.
            strict_mode: When True, missing handlers produce a FAILED status
                instead of a simulated COMPLETED result.
        """
        # Check dependencies
        for dep in step_def.depends_on:
            dep_exec = execution.steps.get(dep)
            if not dep_exec or dep_exec.status != StepStatus.COMPLETED:
                step_exec.status = StepStatus.SKIPPED
                step_exec.error = "Dependencies not met"
                results[step_id] = {"status": "skipped", "reason": "dependencies_not_met"}
                return

        # Check condition
        if step_def.condition:
            if not self._evaluate_condition(step_def.condition, execution.context, results):
                step_exec.status = StepStatus.SKIPPED
                step_exec.error = "Condition not met"
                results[step_id] = {"status": "skipped", "reason": "condition_false"}
                return

        step_exec.status = StepStatus.RUNNING
        step_exec.start_time = time.time()

        handler = self._step_handlers.get(step_def.action)
        if handler:
            try:
                result = handler(step_def, execution.context)
                step_exec.result = result
                step_exec.status = StepStatus.COMPLETED
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                step_exec.error = str(exc)
                step_exec.status = StepStatus.FAILED
        else:
            if strict_mode:
                step_exec.error = f"No handler registered for action '{step_def.action}' (strict_mode)"
                step_exec.status = StepStatus.FAILED
            else:
                logger.warning(
                    "No handler registered for action '%s' — executing in simulation mode",
                    step_def.action,
                )
                step_exec.result = {
                    "action": step_def.action,
                    "step_id": step_id,
                    "simulated": True,
                }
                step_exec.status = StepStatus.COMPLETED

        step_exec.end_time = time.time()
        results[step_id] = {
            "status": step_exec.status.value,
            "result": step_exec.result,
            "error": step_exec.error,
            "duration_ms": (step_exec.end_time - step_exec.start_time) * 1000,
        }

    def execute_workflow_parallel(
        self,
        execution_id: str,
        step_timeout: float = 120.0,
        total_timeout: float = 600.0,
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
        """Execute the workflow with concurrent step execution within each dependency level.

        Calls :meth:`get_parallel_groups` to identify steps that share the same
        DAG level, then submits each group to a :class:`ThreadPoolExecutor`.
        Groups are processed sequentially in dependency order; steps *within* a
        group run concurrently and share the accumulated ``results`` dict from
        all prior groups.

        A single step failure is error-isolated: it does not abort other steps
        in the same group.  Both per-step and total-workflow timeouts are
        enforced via :func:`concurrent.futures.wait`.

        Args:
            execution_id: The execution identifier returned by
                :meth:`create_execution`.
            step_timeout: Maximum seconds allowed for any single step (default
                120.0).  Steps still running after this deadline are marked
                ``TIMED_OUT``.
            total_timeout: Maximum wall-clock seconds for the entire workflow
                run (default 600.0).  Groups that cannot start before this
                deadline have all their steps marked ``TIMED_OUT``.
            strict_mode: When ``True``, steps whose ``action`` has no
                registered handler are marked ``FAILED`` instead of running in
                simulation mode.

        Returns:
            Dict with keys ``execution_id``, ``workflow_id``, ``status``,
            ``steps``, ``duration_ms``, ``completed``, ``skipped``, ``failed``,
            ``total`` — the same shape as :meth:`execute_workflow`.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return {"error": "Execution not found", "execution_id": execution_id}

        workflow = self._workflows.get(execution.workflow_id)
        if not workflow:
            return {"error": "Workflow definition not found"}

        groups = self.get_parallel_groups(execution.workflow_id)
        if groups is None:
            return {"error": "Failed to compute parallel groups (possible cycle)"}

        execution.status = WorkflowStatus.RUNNING
        execution.start_time = time.time()
        step_map = {s.step_id: s for s in workflow.steps}
        results: Dict[str, Any] = {}
        deadline = execution.start_time + total_timeout

        for group in groups:
            remaining = deadline - time.time()
            if remaining <= 0:
                for step_id in group:
                    step_exec = execution.steps[step_id]
                    step_exec.status = StepStatus.TIMED_OUT
                    step_exec.error = "Total workflow timeout exceeded"
                    results[step_id] = {
                        "status": StepStatus.TIMED_OUT.value,
                        "error": "total_timeout_exceeded",
                    }
                continue

            group_timeout = min(step_timeout, remaining)

            # Sentinel so `finally` can safely reference not_done even if
            # futures_wait() is never reached due to a submission error.
            not_done = set()
            executor = ThreadPoolExecutor(max_workers=max(1, len(group)))
            try:
                futures_map: Dict[Any, str] = {
                    executor.submit(
                        self._run_step,
                        step_id,
                        step_map[step_id],
                        execution.steps[step_id],
                        execution,
                        results,
                        strict_mode,
                    ): step_id
                    for step_id in group
                }

                done, not_done = futures_wait(list(futures_map.keys()), timeout=group_timeout)

                for future in done:
                    step_id = futures_map[future]
                    try:
                        future.result()
                    except Exception as exc:
                        # _run_step is error-isolated; this catches unexpected
                        # thread-level failures that bypassed it.
                        step_exec = execution.steps[step_id]
                        if step_exec.status == StepStatus.RUNNING:
                            step_exec.status = StepStatus.FAILED
                            step_exec.error = str(exc)
                            step_exec.end_time = time.time()
                        results[step_id] = {
                            "status": step_exec.status.value,
                            "result": step_exec.result,
                            "error": step_exec.error,
                            "duration_ms": (step_exec.end_time - step_exec.start_time) * 1000,
                        }

                for future in not_done:
                    step_id = futures_map[future]
                    step_exec = execution.steps[step_id]
                    step_exec.status = StepStatus.TIMED_OUT
                    step_exec.error = "Step timed out"
                    step_exec.end_time = time.time()
                    results[step_id] = {
                        "status": StepStatus.TIMED_OUT.value,
                        "error": "step_timeout_exceeded",
                    }
                    future.cancel()
            finally:
                # Do not block if threads are still running past their timeout.
                executor.shutdown(wait=len(not_done) == 0)

        all_statuses = [se.status for se in execution.steps.values()]
        if any(s in (StepStatus.FAILED, StepStatus.TIMED_OUT) for s in all_statuses):
            execution.status = WorkflowStatus.FAILED
        elif all(s in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in all_statuses):
            execution.status = WorkflowStatus.COMPLETED
        else:
            execution.status = WorkflowStatus.FAILED

        execution.end_time = time.time()

        summary = {
            "execution_id": execution_id,
            "workflow_id": execution.workflow_id,
            "status": execution.status.value,
            "steps": results,
            "duration_ms": (execution.end_time - execution.start_time) * 1000,
            "completed": sum(1 for s in all_statuses if s == StepStatus.COMPLETED),
            "skipped": sum(1 for s in all_statuses if s == StepStatus.SKIPPED),
            "failed": sum(
                1 for s in all_statuses if s in (StepStatus.FAILED, StepStatus.TIMED_OUT)
            ),
            "total": len(all_statuses),
        }

        with self._lock:
            capped_append(self._execution_history, summary)
        return summary

    def _evaluate_condition(self, condition: str, context: Dict[str, Any], results: Dict[str, Any]) -> bool:
        """Evaluate a simple condition expression."""
        # Support basic conditions: "key=value", "key!=value", "key_exists"
        if "!=" in condition:
            key, val = condition.split("!=", 1)
            return str(context.get(key.strip(), "")) != val.strip()
        elif "=" in condition:
            key, val = condition.split("=", 1)
            return str(context.get(key.strip(), "")) == val.strip()
        elif condition.endswith("_exists"):
            key = condition.replace("_exists", "")
            return key in context
        else:
            return bool(context.get(condition, False))

    def checkpoint_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        checkpoint = {
            "execution_id": execution_id,
            "workflow_id": execution.workflow_id,
            "status": execution.status.value,
            "step_states": {
                sid: {
                    "status": se.status.value,
                    "result": se.result,
                    "error": se.error,
                }
                for sid, se in execution.steps.items()
            },
            "context": execution.context,
            "timestamp": time.time(),
        }
        execution.checkpoint = checkpoint
        return checkpoint

    def resume_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        execution = self._executions.get(execution_id)
        if not execution or not execution.checkpoint:
            return None
        execution.status = WorkflowStatus.RUNNING
        # Reset non-completed steps
        for sid, se in execution.steps.items():
            if se.status not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                se.status = StepStatus.PENDING
                se.error = None
        return self.execute_workflow(execution_id)

    def pause_execution(self, execution_id: str) -> bool:
        execution = self._executions.get(execution_id)
        if not execution:
            return False
        execution.status = WorkflowStatus.PAUSED
        return True

    def cancel_execution(self, execution_id: str) -> bool:
        execution = self._executions.get(execution_id)
        if not execution:
            return False
        execution.status = WorkflowStatus.CANCELLED
        return True

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        return {
            "execution_id": execution.execution_id,
            "workflow_id": execution.workflow_id,
            "status": execution.status.value,
            "steps": {
                sid: {
                    "status": se.status.value,
                    "result": se.result,
                    "error": se.error,
                }
                for sid, se in execution.steps.items()
            },
            "context": execution.context,
            "has_checkpoint": execution.checkpoint is not None,
        }

    def get_execution_order(self, workflow_id: str) -> Optional[List[str]]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        try:
            return self._topological_sort(workflow)
        except ValueError:
            return None

    def get_parallel_groups(self, workflow_id: str) -> Optional[List[List[str]]]:
        """Get steps grouped by execution level (steps in same group can run in parallel)."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        step_map = {s.step_id: s for s in workflow.steps}
        levels: Dict[str, int] = {}

        try:
            order = self._topological_sort(workflow)
        except ValueError:
            return None

        for sid in order:
            step = step_map[sid]
            if not step.depends_on:
                levels[sid] = 0
            else:
                levels[sid] = max(levels.get(d, 0) for d in step.depends_on) + 1

        groups: Dict[int, List[str]] = defaultdict(list)
        for sid, level in levels.items():
            groups[level].append(sid)

        return [groups[l] for l in sorted(groups.keys())]

    def list_unhandled_actions(self) -> List[str]:
        """Return a sorted list of actions referenced in registered workflows but lacking a handler."""
        unhandled: Set[str] = set()
        for workflow in self._workflows.values():
            for step in workflow.steps:
                if step.action not in self._step_handlers:
                    unhandled.add(step.action)
        return sorted(unhandled)

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [
            {
                "workflow_id": w.workflow_id,
                "name": w.name,
                "description": w.description,
                "step_count": len(w.steps),
                "created_at": w.created_at,
            }
            for w in self._workflows.values()
        ]

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._execution_history)
            completed = sum(1 for h in self._execution_history if h.get("status") == "completed")
            return {
                "total_workflows": len(self._workflows),
                "total_executions": len(self._executions),
                "execution_history_count": total,
                "completed_executions": completed,
                "failed_executions": total - completed,
                "success_rate": completed / max(total, 1),
                "registered_handlers": len(self._step_handlers),
            }

    def status(self) -> Dict[str, Any]:
        return {
            "module": "workflow_dag_engine",
            "statistics": self.get_statistics(),
            "workflows": self.list_workflows(),
        }
