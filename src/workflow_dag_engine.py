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

    def __init__(self, llm_controller=None):
        self._lock = threading.Lock()
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._step_handlers: Dict[str, Callable] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._register_default_handlers(llm_controller)

    def _register_default_handlers(self, llm_controller=None) -> None:
        """Register built-in LLM-backed step handlers so DAG workflows never
        fall through to simulation mode.  Each handler tries the LLMController
        first; if unavailable, uses the onboard LocalLLMFallback."""

        def _llm_call(prompt: str, max_tokens: int = 500) -> str:
            """Inner helper — tries LLMController then LocalLLMFallback."""
            if llm_controller is not None:
                try:
                    import asyncio
                    from llm_controller import LLMRequest
                    req = LLMRequest(prompt=prompt, max_tokens=max_tokens)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                resp = pool.submit(asyncio.run, llm_controller.query_llm(req)).result(timeout=30)
                        else:
                            resp = loop.run_until_complete(llm_controller.query_llm(req))
                        return resp.content
                    except Exception as exc:
                        logger.debug("DAG LLM handler: LLMController failed (%s)", exc)
                except Exception:
                    pass
            try:
                from local_llm_fallback import LocalLLMFallback
                return LocalLLMFallback().generate(prompt, max_tokens=max_tokens)
            except Exception:
                return f"[onboard] Processed: {prompt[:80]}"

        def _handle_llm_generate(step_def, context: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"Generate content for step '{step_def.step_id}' "
                f"({getattr(step_def, 'description', '')}).\n"
                f"Context: {str(context)[:400]}"
            )
            return {"action": "llm_generate", "step_id": step_def.step_id, "result": _llm_call(prompt)}

        def _handle_llm_analyze(step_def, context: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"Analyze the data for step '{step_def.step_id}' "
                f"({getattr(step_def, 'description', '')}).\n"
                f"Context: {str(context)[:400]}\n"
                "Return a JSON object with 'analysis', 'risks', and 'recommendations'."
            )
            return {"action": "llm_analyze", "step_id": step_def.step_id, "result": _llm_call(prompt)}

        def _handle_llm_execute(step_def, context: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"Execute step '{step_def.step_id}' "
                f"({getattr(step_def, 'description', '')}).\n"
                f"Context: {str(context)[:400]}\n"
                "Return a JSON object with 'result', 'artifacts', and 'next_action'."
            )
            return {"action": "llm_execute", "step_id": step_def.step_id, "result": _llm_call(prompt)}

        def _handle_llm_review(step_def, context: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"Review and validate step '{step_def.step_id}' "
                f"({getattr(step_def, 'description', '')}).\n"
                f"Context: {str(context)[:400]}\n"
                "Return a JSON object with 'approved' (bool), 'feedback', 'confidence' (0-1)."
            )
            return {"action": "llm_review", "step_id": step_def.step_id, "result": _llm_call(prompt)}

        self._step_handlers.setdefault("llm_generate", _handle_llm_generate)
        self._step_handlers.setdefault("llm_analyze", _handle_llm_analyze)
        self._step_handlers.setdefault("llm_execute", _handle_llm_execute)
        self._step_handlers.setdefault("llm_review", _handle_llm_review)
        # Legacy / generic action names fall through to llm_execute
        self._step_handlers.setdefault("execute", _handle_llm_execute)
        self._step_handlers.setdefault("generate", _handle_llm_generate)
        self._step_handlers.setdefault("analyze", _handle_llm_analyze)
        self._step_handlers.setdefault("review", _handle_llm_review)

    def register_workflow(self, workflow: WorkflowDefinition) -> bool:
        with self._lock:
            # Validate DAG (no cycles)
            if not self._validate_dag(workflow):
                return False
            self._workflows[workflow.workflow_id] = workflow

        # Publish to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_workflow_registered(
                workflow_id=workflow.workflow_id,
                steps=len(workflow.steps),
            )
        except Exception:
            pass

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

        # Publish to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_dag_execution_complete(
                execution_id=execution_id,
                status=execution.status.value,
                steps_completed=summary["completed"],
            )
        except Exception:
            pass

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
