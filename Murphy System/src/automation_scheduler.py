"""
Automation Scheduler for Murphy System Runtime

This module implements a multi-project automation scheduler that provides:
- Priority-based scheduling of automation tasks across projects
- Load balancing across configurable execution slots
- Project execution state tracking (pending/running/completed/failed)
- Cron-like scheduling for recurring tasks
- Thread-safe queue management with concurrent access support
- Execution lifecycle management with result tracking
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SchedulePriority(str, Enum):
    """Priority levels for scheduled automation tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


PRIORITY_ORDER = {
    SchedulePriority.CRITICAL: 0,
    SchedulePriority.HIGH: 1,
    SchedulePriority.MEDIUM: 2,
    SchedulePriority.LOW: 3,
}


@dataclass
class ProjectSchedule:
    """Configuration for a scheduled project automation task."""
    project_id: str
    task_description: str
    task_type: str
    priority: SchedulePriority = SchedulePriority.MEDIUM
    cron_expression: Optional[str] = None
    max_concurrent: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduledExecution:
    """Tracks a single scheduled execution instance."""
    execution_id: str
    project_id: str
    status: str = "pending"
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.scheduled_at is None:
            self.scheduled_at = datetime.now(timezone.utc).isoformat()


class AutomationScheduler:
    """Multi-project automation scheduler with priority queuing and load balancing.

    Manages project schedules, dispatches execution batches respecting priority
    and concurrency limits, and tracks execution lifecycle state.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._projects: Dict[str, ProjectSchedule] = {}
        self._executions: Dict[str, ScheduledExecution] = {}
        self._project_executions: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def add_project(self, schedule: ProjectSchedule) -> str:
        """Register a project for scheduling and create its first pending execution."""
        with self._lock:
            self._projects[schedule.project_id] = schedule
            execution = ScheduledExecution(
                execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                project_id=schedule.project_id,
            )
            self._executions[execution.execution_id] = execution
            self._project_executions.setdefault(schedule.project_id, []).append(
                execution.execution_id
            )
        logger.info(
            "Added project %s with priority %s",
            schedule.project_id,
            schedule.priority.value,
        )
        return schedule.project_id

    def remove_project(self, project_id: str) -> bool:
        """Remove a project and all its pending executions."""
        with self._lock:
            if project_id not in self._projects:
                logger.warning("Project %s not found", project_id)
                return False
            del self._projects[project_id]
            exec_ids = self._project_executions.pop(project_id, [])
            for eid in exec_ids:
                exe = self._executions.get(eid)
                if exe and exe.status == "pending":
                    del self._executions[eid]
        logger.info("Removed project %s", project_id)
        return True

    # ------------------------------------------------------------------
    # Batch scheduling with load balancing
    # ------------------------------------------------------------------

    def get_next_batch(self, max_slots: int = 5) -> List[ScheduledExecution]:
        """Return the next batch of executions to run, ordered by priority.

        Respects per-project ``max_concurrent`` limits and the global
        ``max_slots`` cap to provide fair load balancing.
        """
        with self._lock:
            # Count currently running executions per project
            running_counts: Dict[str, int] = {}
            for exe in self._executions.values():
                if exe.status == "running":
                    running_counts[exe.project_id] = (
                        running_counts.get(exe.project_id, 0) + 1
                    )

            # Gather eligible pending executions
            pending: List[ScheduledExecution] = []
            for exe in self._executions.values():
                if exe.status != "pending":
                    continue
                schedule = self._projects.get(exe.project_id)
                if schedule is None:
                    continue
                current_running = running_counts.get(exe.project_id, 0)
                if current_running >= schedule.max_concurrent:
                    continue
                pending.append(exe)

            # Sort by priority (project's schedule priority)
            pending.sort(
                key=lambda e: PRIORITY_ORDER.get(
                    self._projects[e.project_id].priority, 99
                )
            )

            batch: List[ScheduledExecution] = []
            batch_running: Dict[str, int] = dict(running_counts)
            for exe in pending:
                if len(batch) >= max_slots:
                    break
                schedule = self._projects[exe.project_id]
                current = batch_running.get(exe.project_id, 0)
                if current >= schedule.max_concurrent:
                    continue
                batch.append(exe)
                batch_running[exe.project_id] = current + 1

        logger.info("Next batch contains %d executions", len(batch))
        return batch

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------

    def start_execution(self, execution_id: str) -> bool:
        """Mark an execution as running."""
        with self._lock:
            exe = self._executions.get(execution_id)
            if exe is None or exe.status != "pending":
                logger.warning("Cannot start execution %s", execution_id)
                return False
            exe.status = "running"
            exe.started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Started execution %s", execution_id)
        return True

    def complete_execution(
        self,
        execution_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark an execution as completed or failed and optionally re-queue recurring tasks."""
        with self._lock:
            exe = self._executions.get(execution_id)
            if exe is None or exe.status != "running":
                logger.warning("Cannot complete execution %s", execution_id)
                return False
            exe.status = "completed" if success else "failed"
            exe.completed_at = datetime.now(timezone.utc).isoformat()
            exe.result = result

            # Re-queue for recurring (cron) tasks
            schedule = self._projects.get(exe.project_id)
            if schedule is not None and schedule.cron_expression is not None:
                new_exe = ScheduledExecution(
                    execution_id=f"exec-{uuid.uuid4().hex[:12]}",
                    project_id=exe.project_id,
                )
                self._executions[new_exe.execution_id] = new_exe
                self._project_executions.setdefault(exe.project_id, []).append(
                    new_exe.execution_id
                )
                logger.info(
                    "Re-queued recurring task for project %s as %s",
                    exe.project_id,
                    new_exe.execution_id,
                )

        logger.info(
            "Completed execution %s: %s",
            execution_id,
            "success" if success else "failed",
        )
        return True

    # ------------------------------------------------------------------
    # Status / reporting
    # ------------------------------------------------------------------

    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Return status summary for a specific project."""
        with self._lock:
            schedule = self._projects.get(project_id)
            if schedule is None:
                return {"project_id": project_id, "found": False}

            exec_ids = self._project_executions.get(project_id, [])
            execs = [self._executions[eid] for eid in exec_ids if eid in self._executions]

            counts: Dict[str, int] = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
            for exe in execs:
                counts[exe.status] = counts.get(exe.status, 0) + 1

        return {
            "project_id": project_id,
            "found": True,
            "task_type": schedule.task_type,
            "priority": schedule.priority.value,
            "max_concurrent": schedule.max_concurrent,
            "cron_expression": schedule.cron_expression,
            "total_executions": len(execs),
            "status_counts": counts,
        }

    def get_queue_status(self) -> Dict[str, Any]:
        """Return overall queue status across all projects."""
        with self._lock:
            total = len(self._executions)
            counts: Dict[str, int] = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
            for exe in self._executions.values():
                counts[exe.status] = counts.get(exe.status, 0) + 1
            project_count = len(self._projects)

        return {
            "total_projects": project_count,
            "total_executions": total,
            "status_counts": counts,
            "pending": counts["pending"],
            "running": counts["running"],
            "completed": counts["completed"],
            "failed": counts["failed"],
        }

    def get_status(self) -> Dict[str, Any]:
        """Return current scheduler status."""
        with self._lock:
            total_projects = len(self._projects)
            total_executions = len(self._executions)
            pending = sum(1 for e in self._executions.values() if e.status == "pending")
            running = sum(1 for e in self._executions.values() if e.status == "running")
            completed = sum(1 for e in self._executions.values() if e.status == "completed")
            failed = sum(1 for e in self._executions.values() if e.status == "failed")

        return {
            "total_projects": total_projects,
            "total_executions": total_executions,
            "pending_executions": pending,
            "running_executions": running,
            "completed_executions": completed,
            "failed_executions": failed,
        }
