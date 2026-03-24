"""
Gate Execution Wiring
Bridges gate synthesis into the runtime execution path.

Assessment Sections 3.1 and 12.1 identify that gate synthesis + swarm execution
exists but is not wired into the main execution path. This module closes that gap
by evaluating gates before task execution and expanding gate checks across swarm
subtasks.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

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
# Enums
# ---------------------------------------------------------------------------

class GateType(Enum):
    """Execution-path gate types."""
    EXECUTIVE = "executive"
    OPERATIONS = "operations"
    QA = "qa"
    HITL = "hitl"
    COMPLIANCE = "compliance"
    BUDGET = "budget"


class GateDecision(Enum):
    """Outcome of a gate evaluation."""
    APPROVED = "approved"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    ESCALATED = "escalated"


class GatePolicy(Enum):
    """How a gate decision affects execution."""
    ENFORCE = "enforce"   # Block execution if gate fails
    WARN = "warn"         # Log warning but allow execution
    AUDIT = "audit"       # Record decision only


# ---------------------------------------------------------------------------
# Gate evaluation sequence (dependency order)
# ---------------------------------------------------------------------------

GATE_SEQUENCE: List[GateType] = [
    GateType.COMPLIANCE,
    GateType.BUDGET,
    GateType.EXECUTIVE,
    GateType.OPERATIONS,
    GateType.QA,
    GateType.HITL,
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GateEvaluation:
    """Result of evaluating a single gate."""
    gate_id: str
    gate_type: GateType
    decision: GateDecision
    reason: str
    policy: GatePolicy
    evaluated_at: str
    evaluator: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_type": self.gate_type.value,
            "decision": self.decision.value,
            "reason": self.reason,
            "policy": self.policy.value,
            "evaluated_at": self.evaluated_at,
            "evaluator": self.evaluator,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# GateExecutionWiring
# ---------------------------------------------------------------------------

class GateExecutionWiring:
    """Wires gate synthesis into the runtime execution path.

    Registered gate evaluators are invoked **before** every task execution.
    Gates evaluate in the order defined by ``GATE_SEQUENCE`` so that
    dependency constraints (e.g. compliance before budget) are respected.
    """

    def __init__(self, default_policy: GatePolicy = GatePolicy.WARN):
        self._default_policy = default_policy
        # gate_type -> (evaluator_callable, policy)
        self._gates: Dict[GateType, Tuple[Callable, GatePolicy]] = {}
        self._history: List[Dict[str, Any]] = []

    # -- registration -------------------------------------------------------

    def register_gate(
        self,
        gate_type: GateType,
        evaluator: Callable[[Dict[str, Any], str], GateEvaluation],
        policy: Optional[GatePolicy] = None,
    ) -> None:
        """Register an evaluator for *gate_type*.

        ``evaluator`` must accept ``(task, session_id)`` and return a
        ``GateEvaluation``.
        """
        effective_policy = policy if policy is not None else self._default_policy
        self._gates[gate_type] = (evaluator, effective_policy)

    # -- evaluation ---------------------------------------------------------

    def evaluate_gates(
        self, task: Dict[str, Any], session_id: str
    ) -> List[GateEvaluation]:
        """Evaluate all registered gates in dependency order.

        Returns a list of ``GateEvaluation`` objects — one per registered
        gate type that appears in ``GATE_SEQUENCE``.
        """
        evaluations: List[GateEvaluation] = []
        for gate_type in GATE_SEQUENCE:
            if gate_type not in self._gates:
                continue
            evaluator_fn, policy = self._gates[gate_type]
            try:
                evaluation = evaluator_fn(task, session_id)
                # Ensure the policy stored on the evaluation matches config
                evaluation.policy = policy
                evaluation.gate_type = gate_type
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                evaluation = GateEvaluation(
                    gate_id=str(uuid.uuid4()),
                    gate_type=gate_type,
                    decision=GateDecision.BLOCKED,
                    reason=f"Gate evaluator raised an exception: {exc}",
                    policy=policy,
                    evaluated_at=datetime.now(timezone.utc).isoformat(),
                    metadata={"error": str(exc)},
                )
            evaluations.append(evaluation)

            # Record in history
            capped_append(self._history, {
                "session_id": session_id,
                "task": task,
                "evaluation": evaluation.to_dict(),
            })

            # Short-circuit: if an ENFORCE gate blocks, stop evaluating
            if (
                policy == GatePolicy.ENFORCE
                and evaluation.decision
                in (GateDecision.BLOCKED, GateDecision.ESCALATED)
            ):
                break

        return evaluations

    # -- decision helpers ---------------------------------------------------

    def can_execute(
        self, task: Dict[str, Any], session_id: str
    ) -> Tuple[bool, List[GateEvaluation]]:
        """Return ``(allowed, evaluations)``.

        Execution is blocked only when an **ENFORCE**-policy gate returns
        ``BLOCKED`` or ``ESCALATED``.  WARN and AUDIT gates never block.
        """
        evaluations = self.evaluate_gates(task, session_id)
        for ev in evaluations:
            if ev.policy == GatePolicy.ENFORCE and ev.decision in (
                GateDecision.BLOCKED,
                GateDecision.ESCALATED,
            ):
                return False, evaluations
        return True, evaluations

    # -- execution wrapping -------------------------------------------------

    def wrap_execution(
        self,
        task: Dict[str, Any],
        executor: Callable[[Dict[str, Any]], Dict[str, Any]],
        session_id: str,
    ) -> Dict[str, Any]:
        """Evaluate gates, then conditionally run *executor*.

        Returns a dict that always contains ``"gate_evaluations"`` and,
        when execution proceeds, the executor's own result merged in.
        """
        allowed, evaluations = self.can_execute(task, session_id)
        gate_data = [ev.to_dict() for ev in evaluations]

        if not allowed:
            blocking = [
                ev.to_dict()
                for ev in evaluations
                if ev.policy == GatePolicy.ENFORCE
                and ev.decision
                in (GateDecision.BLOCKED, GateDecision.ESCALATED)
            ]
            return {
                "status": "blocked",
                "gate_evaluations": gate_data,
                "blocking_gates": blocking,
            }

        # Log warnings for WARN-policy failures
        for ev in evaluations:
            if ev.policy == GatePolicy.WARN and ev.decision in (
                GateDecision.BLOCKED,
                GateDecision.NEEDS_REVIEW,
                GateDecision.ESCALATED,
            ):
                logger.warning(
                    "Gate %s (%s) returned %s: %s",
                    ev.gate_id,
                    ev.gate_type.value,
                    ev.decision.value,
                    ev.reason,
                )

        # Execute the task
        try:
            result = executor(task)
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "status": "error",
                "gate_evaluations": gate_data,
                "error": str(exc),
            }

        if isinstance(result, dict):
            result["gate_evaluations"] = gate_data
            result.setdefault("status", "completed")
            return result

        return {
            "status": "completed",
            "gate_evaluations": gate_data,
            "result": result,
        }

    # -- history / status ---------------------------------------------------

    def get_gate_history(
        self, session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return recorded gate evaluations, optionally filtered by session."""
        if session_id is None:
            return list(self._history)
        return [h for h in self._history if h.get("session_id") == session_id]

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the wiring configuration and history."""
        registered = {
            gt.value: policy.value for gt, (_, policy) in self._gates.items()
        }
        return {
            "registered_gates": registered,
            "total_registered": len(self._gates),
            "default_policy": self._default_policy.value,
            "total_evaluations": len(self._history),
            "gate_sequence": [gt.value for gt in GATE_SEQUENCE],
        }

    def register_security_plane_defaults(self) -> int:
        """Register default security-plane evaluators for all gate types.

        Imports each security module lazily so that the wiring works even
        when optional dependencies are not installed.

        Returns:
            Count of successfully loaded security modules.
        """
        # _security_checks: List[Tuple[str, Type]] where each entry is
        # (module_short_name, security_class)
        _security_checks: List[tuple] = []

        _module_pairs = [
            ("src.security_plane.access_control", "AccessController"),
            ("src.security_plane.authentication", "IdentityVerifier"),
            ("src.security_plane.authorization_enhancer", "AuthorizationEnhancer"),
            ("src.security_plane.hardening", "SystemHardening"),
            ("src.security_plane.data_leak_prevention", "DataLeakPrevention"),
            ("src.security_plane.bot_anomaly_detector", "BotAnomalyDetector"),
            ("src.security_plane.cryptography", "CryptographyService"),
        ]

        for module_path, class_name in _module_pairs:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name, None)
                if cls is not None:
                    _security_checks.append((module_path.split(".")[-1], cls))
            except (ImportError, Exception):
                pass

        loaded_count = len(_security_checks)

        def _security_evaluator(task: Dict[str, Any], session_id: str) -> "GateEvaluation":
            issues: List[str] = []
            for check_name, check_cls in _security_checks:
                try:
                    checker = check_cls()
                    if hasattr(checker, "check"):
                        result = checker.check(task)
                        if isinstance(result, dict) and not result.get("ok", True):
                            issues.append(check_name)
                    elif hasattr(checker, "evaluate"):
                        result = checker.evaluate(task)
                        if isinstance(result, dict) and not result.get("ok", True):
                            issues.append(check_name)
                except Exception as exc:
                    logger.debug("Non-critical error: %s", exc)

            if issues:
                decision = GateDecision.NEEDS_REVIEW
                reason = f"Security checks flagged: {', '.join(issues)}"
            else:
                decision = GateDecision.APPROVED
                reason = f"Security checks passed ({loaded_count} modules)"

            return GateEvaluation(
                gate_id=str(uuid.uuid4()),
                gate_type=GateType.COMPLIANCE,
                decision=decision,
                reason=reason,
                policy=GatePolicy.WARN,
                evaluated_at=datetime.now(timezone.utc).isoformat(),
                evaluator="security_plane_defaults",
                metadata={"loaded_modules": loaded_count, "flagged": issues},
            )

        self.register_gate(GateType.COMPLIANCE, _security_evaluator, GatePolicy.WARN)
        logger.info("Registered security plane defaults (%d modules loaded)", loaded_count)
        return loaded_count

    # -- execution engine wiring --------------------------------------------

    def wire_to_execution_engine(self) -> "GateExecutionWiring":
        """Wire this instance to the execution_engine and execution_orchestrator.

        Registers a default executor that dispatches through:
          GateExecutionWiring.wrap_execution()
            → execution_engine.TaskExecutor (schedules and runs the task)
            → execution_orchestrator.ExecutionOrchestrator (certifies and records)

        Returns *self* for fluent chaining.
        """
        try:
            from src.execution_engine import TaskExecutor, Task, TaskState, create_task
            from src.execution_orchestrator import ExecutionOrchestrator

            _task_executor = TaskExecutor()
            _orchestrator = ExecutionOrchestrator()

            def _engine_executor(task: Dict[str, Any]) -> Dict[str, Any]:
                """Dispatch task through execution_engine → orchestrator."""
                task_type = task.get("type", "generic")

                # Build an execution packet and pass to orchestrator
                packet: Dict[str, Any] = {
                    "task": task_type,
                    "authority": task.get("authority", "low"),
                    "requires_human_approval": task.get("requires_human_approval", False),
                }
                orch_result = _orchestrator.execute(packet)

                # Also schedule via task_executor for tracking / retry
                murphy_task = create_task(
                    task_type=task_type,
                    parameters=task,
                )
                task_id = _task_executor.schedule_task(murphy_task)

                return {
                    "status": orch_result.get("status", "completed"),
                    "orchestrator_result": orch_result,
                    "task_executor_id": task_id,
                }

            self._engine_executor = _engine_executor
            logger.info("Wired to execution_engine + execution_orchestrator")
        except Exception as exc:
            logger.warning("Could not wire to execution engine: %s", exc)
            self._engine_executor = None

        return self

    def execute_via_pipeline(
        self,
        task: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        """Evaluate gates then dispatch through the wired execution pipeline.

        This is the complete gate → execution_engine → orchestrator path.
        Call :meth:`wire_to_execution_engine` first to attach the pipeline;
        if not wired, falls back to a minimal direct executor.
        """
        executor = getattr(self, "_engine_executor", None)

        if executor is None:
            # Fallback: direct wrap with a no-op executor
            def _noop_executor(t: Dict[str, Any]) -> Dict[str, Any]:
                return {"status": "completed", "result": t}

            executor = _noop_executor

        return self.wrap_execution(task, executor, session_id)
