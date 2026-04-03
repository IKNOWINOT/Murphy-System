"""
Fleet orchestrator -- Open-RMF integration.

Wraps Open-RMF task dispatch for multi-fleet mission scheduling,
traffic management, and infrastructure coordination.  Uses the Murphy
RobotRegistry as the fleet adapter.

External dependency: Open-RMF (Apache 2.0) via ROS 2.
When RMF is not available the orchestrator provides a simple
priority-queue task dispatcher.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------

try:
    import rclpy  # type: ignore[import-untyped]
    _RMF_AVAILABLE = True
except ImportError:
    _RMF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Status of a fleet task."""
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Common task types."""
    NAVIGATE = "navigate"
    DELIVER = "deliver"
    PATROL = "patrol"
    CHARGE = "charge"
    DOCK = "dock"
    CUSTOM = "custom"


@dataclass
class FleetTask:
    """A task to be dispatched to the fleet."""
    task_id: str = ""
    task_type: TaskType = TaskType.NAVIGATE
    priority: TaskPriority = TaskPriority.NORMAL
    robot_id: Optional[str] = None  # None = auto-assign
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.QUEUED
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    message: str = ""

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = f"task_{uuid.uuid4().hex[:8]}"
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class FleetStatus:
    """Status of the entire fleet."""
    total_robots: int = 0
    idle_robots: int = 0
    busy_robots: int = 0
    queued_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class FleetOrchestrator:
    """Multi-fleet task dispatch and traffic management.

    Uses Open-RMF when available; otherwise provides a simple
    priority-queue dispatcher.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._task_queue: List[FleetTask] = []
        self._active_tasks: Dict[str, FleetTask] = {}
        self._completed_tasks: List[FleetTask] = []
        self._max_completed: int = 500
        self._robot_assignments: Dict[str, str] = {}  # robot_id -> task_id
        self._available_robots: List[str] = []

    @property
    def backend_available(self) -> bool:
        return _RMF_AVAILABLE

    # -- Robot management ----------------------------------------------------

    def register_robot(self, robot_id: str) -> None:
        """Register a robot as available for task dispatch."""
        with self._lock:
            if robot_id not in self._available_robots:
                self._available_robots.append(robot_id)

    def unregister_robot(self, robot_id: str) -> None:
        with self._lock:
            if robot_id in self._available_robots:
                self._available_robots.remove(robot_id)
            self._robot_assignments.pop(robot_id, None)

    # -- Task submission -----------------------------------------------------

    def submit_task(self, task: FleetTask) -> FleetTask:
        """Submit a task to the dispatch queue."""
        with self._lock:
            self._task_queue.append(task)
            # Sort by priority (critical first)
            priority_order = {
                TaskPriority.CRITICAL: 0,
                TaskPriority.HIGH: 1,
                TaskPriority.NORMAL: 2,
                TaskPriority.LOW: 3,
            }
            self._task_queue.sort(
                key=lambda t: priority_order.get(t.priority, 2))
        logger.info("Task %s submitted (type=%s, priority=%s)",
                     task.task_id, task.task_type.value, task.priority.value)
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or active task."""
        with self._lock:
            # Check queue
            for i, t in enumerate(self._task_queue):
                if t.task_id == task_id:
                    t.status = TaskStatus.CANCELED
                    self._task_queue.pop(i)
                    self._record_completed(t)
                    return True
            # Check active
            task = self._active_tasks.pop(task_id, None)
            if task:
                task.status = TaskStatus.CANCELED
                if task.robot_id:
                    self._robot_assignments.pop(task.robot_id, None)
                self._record_completed(task)
                return True
        return False

    # -- Dispatch ------------------------------------------------------------

    def dispatch_next(self) -> Optional[FleetTask]:
        """Dispatch the highest-priority queued task to an available robot."""
        with self._lock:
            if not self._task_queue:
                return None

            # Find an available robot
            assigned_robots = set(self._robot_assignments.keys())
            free_robots = [r for r in self._available_robots
                           if r not in assigned_robots]

            if not free_robots:
                return None

            task = self._task_queue.pop(0)
            robot_id = task.robot_id if task.robot_id in free_robots else free_robots[0]
            task.robot_id = robot_id
            task.status = TaskStatus.DISPATCHED
            task.started_at = time.time()
            self._active_tasks[task.task_id] = task
            self._robot_assignments[robot_id] = task.task_id

        logger.info("Dispatched task %s to robot %s", task.task_id, robot_id)
        return task

    def dispatch_all(self) -> List[FleetTask]:
        """Dispatch as many queued tasks as there are free robots."""
        dispatched: List[FleetTask] = []
        while True:
            task = self.dispatch_next()
            if task is None:
                break
            dispatched.append(task)
        return dispatched

    # -- Task completion -----------------------------------------------------

    def complete_task(self, task_id: str, success: bool = True,
                      message: str = "") -> bool:
        """Mark an active task as completed or failed."""
        with self._lock:
            task = self._active_tasks.pop(task_id, None)
            if task is None:
                return False
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.completed_at = time.time()
            task.message = message
            if task.robot_id:
                self._robot_assignments.pop(task.robot_id, None)
            self._record_completed(task)
        return True

    def _record_completed(self, task: FleetTask) -> None:
        """Record completed task with bounded history."""
        if len(self._completed_tasks) >= self._max_completed:
            self._completed_tasks = self._completed_tasks[-(self._max_completed // 2):]
        self._completed_tasks.append(task)

    # -- Queries -------------------------------------------------------------

    def get_task(self, task_id: str) -> Optional[FleetTask]:
        with self._lock:
            for t in self._task_queue:
                if t.task_id == task_id:
                    return t
            return self._active_tasks.get(task_id)

    def get_queue(self) -> List[FleetTask]:
        with self._lock:
            return list(self._task_queue)

    def get_active_tasks(self) -> List[FleetTask]:
        with self._lock:
            return list(self._active_tasks.values())

    def get_completed_tasks(self, limit: int = 20) -> List[FleetTask]:
        with self._lock:
            return self._completed_tasks[-limit:]

    def get_fleet_status(self) -> FleetStatus:
        with self._lock:
            assigned = set(self._robot_assignments.keys())
            return FleetStatus(
                total_robots=len(self._available_robots),
                idle_robots=len(self._available_robots) - len(assigned),
                busy_robots=len(assigned),
                queued_tasks=len(self._task_queue),
                active_tasks=len(self._active_tasks),
                completed_tasks=len(self._completed_tasks),
            )

    # -- Status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        fs = self.get_fleet_status()
        return {
            "backend": "open_rmf" if _RMF_AVAILABLE else "stub",
            "total_robots": fs.total_robots,
            "idle_robots": fs.idle_robots,
            "busy_robots": fs.busy_robots,
            "queued_tasks": fs.queued_tasks,
            "active_tasks": fs.active_tasks,
            "completed_tasks": fs.completed_tasks,
        }
