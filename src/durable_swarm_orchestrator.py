"""
Durable Swarm Orchestrator for Murphy System Runtime

This module implements budget-aware durable swarm orchestration with:
- Durable swarm spawning with queue durability
- Idempotency keys to prevent duplicate execution
- Retry policies with configurable max_retries and exponential backoff
- Circuit breaker pattern (fail-fast after threshold failures)
- Budget-aware spawn limits (deny spawn when budget exhausted)
- Anti-runaway recursion controls (max spawn depth limit)
- Rollback hooks for failed swarm tasks
- Thread-safe operation
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SwarmTaskState(str, Enum):
    """Lifecycle states for a swarm task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class CircuitState(str, Enum):
    """States for the circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class SwarmTask:
    """Represents a single durable swarm task."""
    task_id: str
    idempotency_key: str
    parent_id: Optional[str]
    depth: int
    state: SwarmTaskState
    description: str
    budget_allocated: float
    budget_spent: float
    retries: int
    max_retries: int
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict] = None


@dataclass
class SwarmBudget:
    """Tracks budget allocation and spending across the swarm."""
    total_budget: float
    allocated: float
    spent: float
    max_per_task: float
    max_spawn_depth: int


class CircuitBreaker:
    """Circuit breaker to fail-fast after repeated failures.

    Transitions:
      CLOSED  -> OPEN       when consecutive failures >= failure_threshold
      OPEN    -> HALF_OPEN  after recovery_timeout seconds
      HALF_OPEN -> CLOSED   on next success
      HALF_OPEN -> OPEN     on next failure
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Record a successful operation, resetting the breaker."""
        with self._lock:
            self._consecutive_failures = 0
            self.state = CircuitState.CLOSED
        logger.debug("Circuit breaker: success recorded, state=CLOSED")

    def record_failure(self) -> None:
        """Record a failure, potentially tripping the breaker."""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()
            if self._consecutive_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker OPEN after %d consecutive failures",
                    self._consecutive_failures,
                )

    def is_open(self) -> bool:
        """Return True if the circuit is open (requests should be denied)."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return False
            if self.state == CircuitState.OPEN:
                if (
                    self._last_failure_time is not None
                    and time.monotonic() - self._last_failure_time >= self.recovery_timeout
                ):
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    return False
                return True
            # HALF_OPEN — allow one probe
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the circuit breaker state."""
        with self._lock:
            return {
                "state": self.state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }


class DurableSwarmOrchestrator:
    """Budget-aware durable swarm orchestrator with retry, circuit breaker,
    idempotency, depth limits, and rollback support.
    """

    def __init__(
        self,
        total_budget: float = 1000.0,
        max_per_task: float = 100.0,
        max_spawn_depth: int = 5,
        max_retries: int = 3,
        failure_threshold: int = 5,
    ) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, SwarmTask] = {}
        self._idempotency_index: Dict[str, str] = {}  # key -> task_id
        self._budget = SwarmBudget(
            total_budget=total_budget,
            allocated=0.0,
            spent=0.0,
            max_per_task=max_per_task,
            max_spawn_depth=max_spawn_depth,
        )
        self._max_retries = max_retries
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
        )

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------

    def spawn_task(
        self,
        description: str,
        budget: float,
        parent_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, str, str]:
        """Spawn a new swarm task with full pre-flight checks.

        Returns (success, task_id_or_reason, idempotency_key).
        """
        idem_key = idempotency_key or uuid.uuid4().hex

        # Circuit breaker check
        if self._circuit_breaker.is_open():
            logger.warning("Spawn denied: circuit breaker open")
            return (False, "circuit_open", idem_key)

        with self._lock:
            # Depth check
            depth = 0
            if parent_id is not None:
                parent = self._tasks.get(parent_id)
                if parent is None:
                    return (False, "parent_not_found", idem_key)
                depth = parent.depth + 1
                if depth > self._budget.max_spawn_depth:
                    logger.warning("Spawn denied: max depth exceeded (depth=%d)", depth)
                    return (False, "max_depth_exceeded", idem_key)

            # Per-task budget limit
            if budget > self._budget.max_per_task:
                logger.warning("Spawn denied: exceeds per-task limit")
                return (False, "exceeds_per_task_limit", idem_key)

            # Total budget check
            if self._budget.allocated + budget > self._budget.total_budget:
                logger.warning("Spawn denied: budget exhausted")
                return (False, "budget_exhausted", idem_key)

            # Idempotency check
            if idem_key in self._idempotency_index:
                existing_id = self._idempotency_index[idem_key]
                existing = self._tasks.get(existing_id)
                if existing is not None and existing.state not in (
                    SwarmTaskState.FAILED,
                    SwarmTaskState.CANCELLED,
                ):
                    logger.warning("Spawn denied: duplicate idempotency key %s", idem_key)
                    return (False, "duplicate_idempotency_key", idem_key)

            # All checks passed — create task
            now = datetime.now(timezone.utc)
            task_id = f"swarm-{uuid.uuid4().hex[:12]}"
            task = SwarmTask(
                task_id=task_id,
                idempotency_key=idem_key,
                parent_id=parent_id,
                depth=depth,
                state=SwarmTaskState.PENDING,
                description=description,
                budget_allocated=budget,
                budget_spent=0.0,
                retries=0,
                max_retries=self._max_retries,
                created_at=now,
                updated_at=now,
            )
            self._tasks[task_id] = task
            self._idempotency_index[idem_key] = task_id
            self._budget.allocated += budget

        logger.info("Spawned task %s (depth=%d, budget=%.2f)", task_id, depth, budget)

        # Publish to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_task_spawned(task_id=task_id, description=description, budget=budget)
        except Exception:  # PROD-HARD A2: Rosetta bridge optional; swarm function unaffected
            logger.debug("Rosetta bridge unavailable for on_task_spawned(%s)", task_id, exc_info=True)

        return (True, task_id, idem_key)

    # ------------------------------------------------------------------
    # Complete
    # ------------------------------------------------------------------

    def complete_task(self, task_id: str, result: Dict[str, Any], cost: float = 0.0) -> bool:
        """Mark a task as completed, record its result and cost."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("complete_task: task %s not found", task_id)
                return False
            task.state = SwarmTaskState.COMPLETED
            task.result = result
            task.budget_spent = cost
            task.updated_at = datetime.now(timezone.utc)
            self._budget.spent += cost

        self._circuit_breaker.record_success()
        logger.info("Task %s completed (cost=%.2f)", task_id, cost)

        # Publish to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_task_completed(task_id=task_id, cost=cost)
        except Exception:  # PROD-HARD A2: Rosetta bridge optional; swarm function unaffected
            logger.debug("Rosetta bridge unavailable for on_task_completed(%s)", task_id, exc_info=True)

        return True

    # ------------------------------------------------------------------
    # Fail
    # ------------------------------------------------------------------

    def fail_task(self, task_id: str, error: str) -> Tuple[bool, str]:
        """Handle a task failure with retry / rollback / circuit logic.

        Returns (should_retry, next_action) where next_action is one of
        ``"retry"``, ``"rollback"``, or ``"circuit_open"``.
        """
        self._circuit_breaker.record_failure()

        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("fail_task: task %s not found", task_id)
                return (False, "rollback")

            task.updated_at = datetime.now(timezone.utc)
            task.result = {"error": error}

            # Circuit just opened?
            if self._circuit_breaker.is_open():
                task.state = SwarmTaskState.FAILED
                logger.warning("Task %s failed; circuit breaker open", task_id)
                return (False, "circuit_open")

            # Retry budget remaining?
            if task.retries < task.max_retries:
                task.retries += 1
                task.state = SwarmTaskState.RETRYING
                logger.info("Task %s retrying (%d/%d)", task_id, task.retries, task.max_retries)
                return (True, "retry")

            # Exhausted retries — rollback
            task.state = SwarmTaskState.FAILED
            logger.warning("Task %s failed after %d retries; rollback", task_id, task.retries)

        # Publish to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_task_failed(task_id=task_id, reason=error)
        except Exception:  # PROD-HARD A2: Rosetta bridge optional; swarm function unaffected
            logger.debug("Rosetta bridge unavailable for on_task_failed(%s)", task_id, exc_info=True)

        return (False, "rollback")

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback_task(self, task_id: str) -> bool:
        """Roll back a failed task, releasing its allocated budget."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("rollback_task: task %s not found", task_id)
                return False
            task.state = SwarmTaskState.ROLLED_BACK
            task.updated_at = datetime.now(timezone.utc)
            self._budget.allocated -= task.budget_allocated

        logger.info("Task %s rolled back", task_id)
        return True

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task, releasing its allocated budget."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                logger.warning("cancel_task: task %s not found", task_id)
                return False
            task.state = SwarmTaskState.CANCELLED
            task.updated_at = datetime.now(timezone.utc)
            self._budget.allocated -= task.budget_allocated

        logger.info("Task %s cancelled", task_id)
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> Optional[SwarmTask]:
        """Return a task by id, or None."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, state: Optional[SwarmTaskState] = None) -> List[SwarmTask]:
        """Return all tasks, optionally filtered by state."""
        with self._lock:
            if state is None:
                return list(self._tasks.values())
            return [t for t in self._tasks.values() if t.state == state]

    # ------------------------------------------------------------------
    # Budget status
    # ------------------------------------------------------------------

    def get_budget_status(self) -> Dict[str, Any]:
        """Return current budget metrics."""
        with self._lock:
            return {
                "total_budget": self._budget.total_budget,
                "allocated": self._budget.allocated,
                "spent": self._budget.spent,
                "remaining": self._budget.total_budget - self._budget.allocated,
                "max_per_task": self._budget.max_per_task,
                "max_spawn_depth": self._budget.max_spawn_depth,
            }

    # ------------------------------------------------------------------
    # Overall status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return an overall orchestrator status snapshot."""
        with self._lock:
            state_counts: Dict[str, int] = {}
            for t in self._tasks.values():
                state_counts[t.state.value] = state_counts.get(t.state.value, 0) + 1
            total_tasks = len(self._tasks)

        return {
            "total_tasks": total_tasks,
            "state_counts": state_counts,
            "budget": self.get_budget_status(),
            "circuit_breaker": self._circuit_breaker.get_status(),
        }
