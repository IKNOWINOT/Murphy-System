"""HITL task queue for grant application assistance."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.billing.grants.models import HitlTask, TaskType

# In-memory store: session_id -> List[HitlTask]
_TASKS: Dict[str, List[HitlTask]] = {}


def create_task(
    session_id: str,
    task_type: TaskType,
    title: str,
    description: str,
    target_url: str = "",
    form_fields: Optional[Dict[str, Any]] = None,
    depends_on: Optional[List[str]] = None,
    priority: int = 50,
    estimated_minutes: int = 30,
) -> HitlTask:
    """Create a new HITL task for a session.

    Args:
        session_id: Session this task belongs to.
        task_type: Classification of the task.
        title: Short human-readable title.
        description: Detailed description of what the human needs to do.
        target_url: Optional URL to navigate to for this task.
        form_fields: Optional pre-populated form field values.
        depends_on: List of task_ids that must be completed before this task.
        priority: Lower value = higher priority (0 is highest).
        estimated_minutes: Estimated time to complete.

    Returns:
        Newly created HitlTask.
    """
    task = HitlTask(
        task_id=str(uuid.uuid4()),
        session_id=session_id,
        task_type=task_type,
        title=title,
        description=description,
        target_url=target_url,
        form_fields=form_fields or {},
        depends_on=depends_on or [],
        status="pending",
        priority=priority,
        estimated_minutes=estimated_minutes,
    )
    _TASKS.setdefault(session_id, []).append(task)
    return task


def _all_deps_completed(task: HitlTask, tasks: List[HitlTask]) -> bool:
    """Return True if all dependencies of *task* have status='completed'."""
    if not task.depends_on:
        return True
    completed_ids = {t.task_id for t in tasks if t.status == "completed"}
    return all(dep_id in completed_ids for dep_id in task.depends_on)


def get_next_tasks(session_id: str) -> List[HitlTask]:
    """Return unblocked pending tasks sorted by priority ascending (lower = higher priority).

    A task is unblocked when all tasks listed in its depends_on have
    status='completed'.

    Args:
        session_id: Session to query.

    Returns:
        List of unblocked pending HitlTask objects sorted by priority.
    """
    tasks = _TASKS.get(session_id, [])
    unblocked = [
        t for t in tasks
        if t.status == "pending" and _all_deps_completed(t, tasks)
    ]
    return sorted(unblocked, key=lambda t: t.priority)


def complete_task(
    session_id: str,
    task_id: str,
    result_data: Optional[Dict[str, Any]] = None,
) -> Optional[HitlTask]:
    """Mark a task as completed and store result data in form_fields.

    Args:
        session_id: Session the task belongs to.
        task_id: ID of the task to complete.
        result_data: Optional result data to merge into task.form_fields.

    Returns:
        Updated HitlTask or None if not found.
    """
    tasks = _TASKS.get(session_id, [])
    for task in tasks:
        if task.task_id == task_id:
            task.status = "completed"
            if result_data:
                task.form_fields.update(result_data)
            return task
    return None


def get_blocked_tasks(session_id: str) -> List[HitlTask]:
    """Return tasks blocked by incomplete dependencies.

    Args:
        session_id: Session to query.

    Returns:
        List of pending HitlTask objects that have unmet dependencies.
    """
    tasks = _TASKS.get(session_id, [])
    return [
        t for t in tasks
        if t.status == "pending" and not _all_deps_completed(t, tasks)
    ]


def get_waiting_tasks(session_id: str) -> List[HitlTask]:
    """Return tasks in waiting_on_external state.

    Args:
        session_id: Session to query.

    Returns:
        List of HitlTask objects with task_type=waiting_on_external.
    """
    tasks = _TASKS.get(session_id, [])
    return [t for t in tasks if t.task_type == TaskType.waiting_on_external]


def get_progress(session_id: str) -> Dict[str, Any]:
    """Return completion percentage and statistics for a session.

    Args:
        session_id: Session to query.

    Returns:
        Dict with keys: total, completed, pending, blocked, waiting,
        completion_pct (0.0-100.0).
    """
    tasks = _TASKS.get(session_id, [])
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    blocked = len(get_blocked_tasks(session_id))
    waiting = len(get_waiting_tasks(session_id))
    pending = sum(1 for t in tasks if t.status == "pending")
    completion_pct = (completed / total * 100.0) if total > 0 else 0.0
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "blocked": blocked,
        "waiting": waiting,
        "completion_pct": round(completion_pct, 1),
    }


def get_all_tasks(session_id: str) -> List[HitlTask]:
    """Return all tasks for a session in creation order.

    Args:
        session_id: Session to query.

    Returns:
        List of all HitlTask objects for the session.
    """
    return list(_TASKS.get(session_id, []))
