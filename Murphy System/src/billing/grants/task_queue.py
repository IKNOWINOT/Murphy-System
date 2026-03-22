"""
HITL Task Queue — Human-in-the-loop task management for grant workflows.

Tasks flow through states: pending → auto_completed / needs_review /
blocked_human_required → completed.

Dependency chain logic: tasks with unresolved dependencies stay PENDING until
all dependency tasks reach COMPLETED state.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.billing.grants.models import (
    HitlTask,
    HitlTaskQueue,
    HitlTaskState,
)

logger = logging.getLogger(__name__)


class CircularDependencyError(Exception):
    """Raised when a dependency cycle is detected in the task graph."""


class TaskNotFoundError(KeyError):
    """Raised when a task_id is not found in the queue."""


class HitlTaskManager:
    """
    Manages HITL task queues for grant sessions.

    Each session has one task queue. Tasks can depend on other tasks;
    dependent tasks are blocked until all dependencies are COMPLETED.
    """

    def __init__(self) -> None:
        # session_id -> HitlTaskQueue
        self._queues: Dict[str, HitlTaskQueue] = {}

    # -----------------------------------------------------------------------
    # Queue management
    # -----------------------------------------------------------------------

    def get_or_create_queue(self, session_id: str) -> HitlTaskQueue:
        if session_id not in self._queues:
            self._queues[session_id] = HitlTaskQueue(session_id=session_id)
        return self._queues[session_id]

    def get_queue(self, session_id: str) -> HitlTaskQueue:
        if session_id not in self._queues:
            raise KeyError(f"No task queue found for session {session_id!r}")
        return self._queues[session_id]

    # -----------------------------------------------------------------------
    # Task CRUD
    # -----------------------------------------------------------------------

    def add_task(
        self,
        session_id: str,
        title: str,
        description: str,
        why_blocked: str = "",
        what_human_must_provide: str = "",
        external_link: str = "",
        dependencies: Optional[List[str]] = None,
        auto_filled_data: Optional[Dict] = None,
        confidence: float = 0.0,
        order: int = 0,
    ) -> HitlTask:
        """Add a new task to a session's queue."""
        queue = self.get_or_create_queue(session_id)
        deps = dependencies or []

        # Validate dependencies exist
        existing_ids = {t.task_id for t in queue.tasks}
        for dep_id in deps:
            if dep_id not in existing_ids:
                raise TaskNotFoundError(
                    f"Dependency task {dep_id!r} not found in session {session_id!r}"
                )

        # Detect circular dependency
        if deps:
            self._check_circular(queue, deps, set())

        task = HitlTask(
            session_id=session_id,
            title=title,
            description=description,
            why_blocked=why_blocked,
            what_human_must_provide=what_human_must_provide,
            external_link=external_link,
            dependencies=deps,
            auto_filled_data=auto_filled_data or {},
            confidence=confidence,
            order=order,
        )

        # Determine initial state based on dependencies
        task.state = self._compute_initial_state(queue, task)

        queue.tasks.append(task)
        queue.updated_at = datetime.utcnow()
        return task

    def update_task(
        self,
        session_id: str,
        task_id: str,
        new_state: Optional[HitlTaskState] = None,
        human_provided_data: Optional[Dict] = None,
        notes: Optional[str] = None,
    ) -> HitlTask:
        """Update a task's state and/or human-provided data."""
        task = self._find_task(session_id, task_id)
        queue = self.get_queue(session_id)

        if new_state is not None:
            # Validate state transition
            self._validate_transition(task.state, new_state)
            task.state = new_state
            if new_state == HitlTaskState.COMPLETED:
                task.completed_at = datetime.utcnow()
                # Unblock downstream tasks
                self._unblock_downstream(queue, task_id)

        if human_provided_data is not None:
            task.human_provided_data.update(human_provided_data)

        task.updated_at = datetime.utcnow()
        queue.updated_at = datetime.utcnow()
        return task

    def get_task(self, session_id: str, task_id: str) -> HitlTask:
        return self._find_task(session_id, task_id)

    def get_task_dependencies(self, session_id: str, task_id: str) -> List[HitlTask]:
        """Return the dependency tasks for a given task."""
        task = self._find_task(session_id, task_id)
        queue = self.get_queue(session_id)
        task_map = {t.task_id: t for t in queue.tasks}
        return [task_map[dep_id] for dep_id in task.dependencies if dep_id in task_map]

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _find_task(self, session_id: str, task_id: str) -> HitlTask:
        queue = self.get_or_create_queue(session_id)
        for task in queue.tasks:
            if task.task_id == task_id:
                return task
        raise TaskNotFoundError(f"Task {task_id!r} not found in session {session_id!r}")

    def _compute_initial_state(self, queue: HitlTaskQueue, task: HitlTask) -> HitlTaskState:
        """A task is PENDING until dependencies resolve; otherwise it starts as provided."""
        if task.dependencies:
            task_map = {t.task_id: t for t in queue.tasks}
            all_complete = all(
                task_map.get(dep_id, HitlTask(
                    task_id=dep_id,
                    session_id=task.session_id,
                    title="",
                    description="",
                    state=HitlTaskState.PENDING,
                )).state == HitlTaskState.COMPLETED
                for dep_id in task.dependencies
            )
            if not all_complete:
                return HitlTaskState.PENDING

        # If why_blocked is provided, start as blocked_human_required
        if task.why_blocked:
            return HitlTaskState.BLOCKED_HUMAN_REQUIRED
        # If confidence >= 0.8, auto-complete
        if task.confidence >= 0.8:
            return HitlTaskState.AUTO_COMPLETED
        # If confidence >= 0.5, needs review
        if task.confidence >= 0.5:
            return HitlTaskState.NEEDS_REVIEW
        return HitlTaskState.PENDING

    def _unblock_downstream(self, queue: HitlTaskQueue, completed_task_id: str) -> None:
        """After completing a task, re-evaluate downstream tasks that depended on it."""
        task_map = {t.task_id: t for t in queue.tasks}
        for task in queue.tasks:
            if completed_task_id not in task.dependencies:
                continue
            if task.state != HitlTaskState.PENDING:
                continue
            # Check if all dependencies are now complete
            all_deps_done = all(
                task_map.get(dep_id) is not None
                and task_map[dep_id].state == HitlTaskState.COMPLETED
                for dep_id in task.dependencies
            )
            if all_deps_done:
                # Transition to appropriate ready state (never back to PENDING)
                if task.why_blocked:
                    new_state = HitlTaskState.BLOCKED_HUMAN_REQUIRED
                elif task.confidence >= 0.8:
                    new_state = HitlTaskState.AUTO_COMPLETED
                elif task.confidence >= 0.5:
                    new_state = HitlTaskState.NEEDS_REVIEW
                else:
                    new_state = HitlTaskState.NEEDS_REVIEW
                task.state = new_state
                task.updated_at = datetime.utcnow()
                logger.info(
                    "Task %s unblocked → %s after dependency %s completed",
                    task.task_id, task.state, completed_task_id,
                )

    def _validate_transition(self, current: HitlTaskState, new: HitlTaskState) -> None:
        """Validate that a state transition is legal."""
        # Valid transitions (simplified — most transitions are allowed)
        invalid: Dict[HitlTaskState, set] = {
            HitlTaskState.COMPLETED: {
                HitlTaskState.PENDING,
                HitlTaskState.BLOCKED_HUMAN_REQUIRED,
            },
        }
        blocked_from = invalid.get(current, set())
        if new in blocked_from:
            raise ValueError(
                f"Cannot transition task from {current.value!r} to {new.value!r}"
            )

    def _check_circular(
        self,
        queue: HitlTaskQueue,
        dep_ids: List[str],
        visited: set,
    ) -> None:
        """DFS-based circular dependency detection."""
        task_map = {t.task_id: t for t in queue.tasks}
        for dep_id in dep_ids:
            if dep_id in visited:
                raise CircularDependencyError(
                    f"Circular dependency detected involving task {dep_id!r}"
                )
            task = task_map.get(dep_id)
            if task and task.dependencies:
                self._check_circular(queue, task.dependencies, visited | {dep_id})


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_task_manager: Optional[HitlTaskManager] = None


def get_task_manager() -> HitlTaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = HitlTaskManager()
    return _task_manager
