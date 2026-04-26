"""
Autonomous Scheduler for Murphy System Runtime

This module provides autonomous task scheduling capabilities:
- Self-scheduling without human intervention
- Priority-based task queueing
- Resource-aware scheduling
- Deadline management
"""

import heapq
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("autonomous_systems.autonomous_scheduler")


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1  # Highest priority
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    DEFERRED = 5  # Lowest priority


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class Task:
    """Represents a schedulable task"""
    task_id: str
    task_name: str
    priority: TaskPriority
    task_function: Callable
    task_args: tuple = field(default_factory=tuple)
    task_kwargs: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    deadline: Optional[datetime] = None
    estimated_duration: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        """For heap ordering (lower priority number = higher priority)"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # If same priority, use deadline
        if self.deadline and other.deadline:
            return self.deadline < other.deadline
        elif self.deadline:
            return True
        elif other.deadline:
            return False
        # If no deadline, use creation time
        return self.created_at < other.created_at


@dataclass
class ScheduleSlot:
    """Represents a time slot in the schedule"""
    slot_id: str
    start_time: datetime
    end_time: datetime
    task_id: Optional[str] = None
    resource_allocation: Dict[str, Any] = field(default_factory=dict)
    status: str = "available"  # available, occupied, blocked


class ResourcePool:
    """Manages available resources for scheduling"""

    def __init__(self):
        self.resources: Dict[str, int] = {
            'cpu_cores': 4,
            'memory_gb': 16,
            'gpu_count': 0,
            'network_bandwidth_mbps': 1000
        }
        self.available: Dict[str, int] = self.resources.copy()
        self.lock = threading.Lock()

    def allocate(self, requirements: Dict[str, int]) -> bool:
        """Attempt to allocate resources"""
        with self.lock:
            # Check if resources are available
            for resource, amount in requirements.items():
                if self.available.get(resource, 0) < amount:
                    return False

            # Allocate resources
            for resource, amount in requirements.items():
                self.available[resource] -= amount

            return True

    def release(self, allocation: Dict[str, int]) -> None:
        """Release allocated resources"""
        with self.lock:
            for resource, amount in allocation.items():
                self.available[resource] = min(
                    self.available[resource] + amount,
                    self.resources.get(resource, 0)
                )

    def get_available(self) -> Dict[str, int]:
        """Get available resources"""
        with self.lock:
            return self.available.copy()

    def get_utilization(self) -> Dict[str, float]:
        """Get resource utilization percentages"""
        with self.lock:
            utilization = {}
            for resource, total in self.resources.items():
                available = self.available.get(resource, 0)
                utilization[resource] = (total - available) / total if total > 0 else 0.0
            return utilization


class DependencyGraph:
    """Manages task dependencies"""

    def __init__(self):
        self.graph: Dict[str, List[str]] = {}  # task_id -> dependencies
        self.reverse_graph: Dict[str, List[str]] = {}  # task_id -> dependents
        self.lock = threading.Lock()

    def add_task(self, task_id: str, dependencies: List[str]) -> None:
        """Add a task with its dependencies"""
        with self.lock:
            self.graph[task_id] = dependencies

            # Build reverse graph
            for dep in dependencies:
                if dep not in self.reverse_graph:
                    self.reverse_graph[dep] = []
                self.reverse_graph[dep].append(task_id)

    def can_execute(self, task_id: str, completed_tasks: set) -> bool:
        """Check if a task's dependencies are satisfied"""
        with self.lock:
            dependencies = self.graph.get(task_id, [])
            return all(dep in completed_tasks for dep in dependencies)

    def get_ready_tasks(self, all_tasks: set, completed_tasks: set) -> set:
        """Get tasks that are ready to execute"""
        with self.lock:
            ready_tasks = set()
            for task_id in all_tasks:
                if task_id not in completed_tasks:
                    if self.can_execute(task_id, completed_tasks):
                        ready_tasks.add(task_id)
            return ready_tasks

    def get_dependents(self, task_id: str) -> List[str]:
        """Get tasks that depend on this task"""
        with self.lock:
            return self.reverse_graph.get(task_id, []).copy()

    def remove_task(self, task_id: str) -> None:
        """Remove a task and clean up its dependency references"""
        with self.lock:
            # Remove from forward graph and clean up reverse references
            if task_id in self.graph:
                for dep in self.graph[task_id]:
                    if dep in self.reverse_graph and task_id in self.reverse_graph[dep]:
                        self.reverse_graph[dep].remove(task_id)
                del self.graph[task_id]

            # Remove from reverse graph (dependents of this task)
            if task_id in self.reverse_graph:
                del self.reverse_graph[task_id]


class AutonomousScheduler:
    """
    Autonomous scheduler that manages task execution without human intervention

    The scheduler:
    - Schedules tasks based on priority and dependencies
    - Manages resource allocation
    - Handles task retries and failures
    - Adapts scheduling based on feedback
    """

    def __init__(self, enable_autonomous: bool = True):
        self.enable_autonomous = enable_autonomous
        self.task_queue: List[Task] = []
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        self.dependency_graph = DependencyGraph()
        self.resource_pool = ResourcePool()
        self.lock = threading.Lock()
        self.scheduler_thread: Optional[threading.Thread] = None
        self.running = False

        # Performance metrics
        self.tasks_scheduled = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_execution_time = 0.0
        self.average_execution_time = 0.0

        # Configuration
        self.max_concurrent_tasks = 4
        self.scheduling_interval = 5.0  # seconds — PATCH-103h: was 0.1 (CPU hog), throttled to 5s

    def schedule_task(self, task: Task) -> bool:
        """Schedule a task for execution"""
        if not self.enable_autonomous:
            return False

        with self.lock:
            # Add to dependency graph
            self.dependency_graph.add_task(task.task_id, task.dependencies)

            # Add to queue
            heapq.heappush(self.task_queue, task)
            task.status = TaskStatus.PENDING

            return True

    def create_task(self, task_name: str, task_function: Callable,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   task_args: tuple = (), task_kwargs: dict = None,
                   dependencies: List[str] = None,
                   deadline: Optional[datetime] = None,
                   estimated_duration: Optional[float] = None,
                   metadata: Dict[str, Any] = None) -> Task:
        """Create a new task"""
        task = Task(
            task_id=str(uuid.uuid4()),
            task_name=task_name,
            priority=priority,
            task_function=task_function,
            task_args=task_args,
            task_kwargs=task_kwargs or {},
            dependencies=dependencies or [],
            deadline=deadline,
            estimated_duration=estimated_duration,
            metadata=metadata or {}
        )
        return task

    def start(self) -> None:
        """Start the autonomous scheduler"""
        if not self.enable_autonomous:
            return

        with self.lock:
            if self.running:
                return

            self.running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

    def stop(self) -> None:
        """Stop the autonomous scheduler"""
        with self.lock:
            self.running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5.0)

    def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self.running:
            try:
                self._schedule_next_task()
                self._check_task_status()
                time.sleep(self.scheduling_interval)
            except Exception as exc:
                # Log error but continue
                logger.info(f"Scheduler error: {exc}")

    def _schedule_next_task(self) -> None:
        """Schedule the next available task"""
        with self.lock:
            # Check if we can run more tasks
            if len(self.running_tasks) >= self.max_concurrent_tasks:
                return

            # Get completed task IDs
            completed_ids = set(self.completed_tasks.keys())

            # Get ready tasks from queue
            ready_tasks = []
            temp_queue = []

            while self.task_queue:
                task = heapq.heappop(self.task_queue)
                if task.status == TaskStatus.PENDING:
                    if self.dependency_graph.can_execute(task.task_id, completed_ids):
                        ready_tasks.append(task)
                    else:
                        # Dependencies not satisfied, put back in queue
                        temp_queue.append(task)
                else:
                    temp_queue.append(task)

            # Put remaining tasks back in queue
            for task in temp_queue:
                heapq.heappush(self.task_queue, task)

            # Schedule the highest priority ready task
            if ready_tasks:
                task = ready_tasks[0]  # Already sorted by priority

                # Check resources
                resource_requirements = task.metadata.get('resource_requirements', {})
                if self.resource_pool.allocate(resource_requirements):
                    self._start_task(task)

    def _start_task(self, task: Task) -> None:
        """Start executing a task"""
        task.status = TaskStatus.SCHEDULED
        task.scheduled_at = datetime.now(timezone.utc)

        # Move to running tasks
        self.running_tasks[task.task_id] = task

        # Start task in thread
        task_thread = threading.Thread(
            target=self._execute_task,
            args=(task,),
            daemon=True
        )
        task_thread.start()

    def _execute_task(self, task: Task) -> None:
        """Execute a task"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        try:
            # Execute task function
            result = task.task_function(*task.task_args, **task.task_kwargs)

            # Record success
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = result

            # Update metrics
            execution_time = (task.completed_at - task.started_at).total_seconds()
            with self.lock:
                self.tasks_completed += 1
                self.total_execution_time += execution_time
                self.average_execution_time = (
                    self.total_execution_time / self.tasks_completed
                )

            # Move to completed tasks
            with self.lock:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task

            # Release resources
            resource_requirements = task.metadata.get('resource_requirements', {})
            self.resource_pool.release(resource_requirements)

        except Exception as exc:
            # Record failure
            logger.debug("Caught exception: %s", exc)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.error = str(exc)

            # Update metrics
            with self.lock:
                self.tasks_failed += 1
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                self.failed_tasks[task.task_id] = task

            # Release resources
            resource_requirements = task.metadata.get('resource_requirements', {})
            self.resource_pool.release(resource_requirements)

            # Retry if possible
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                task.error = None
                heapq.heappush(self.task_queue, task)

    def _check_task_status(self) -> None:
        """Check status of running tasks and handle timeouts"""
        now = datetime.now(timezone.utc)

        with self.lock:
            # Check for tasks that have exceeded their deadline
            for task_id, task in list(self.running_tasks.items()):
                if task.deadline and now > task.deadline:
                    # Task has exceeded deadline
                    # Cancel task and mark as failed
                    task.status = TaskStatus.FAILED
                    task.error = "Task exceeded deadline"
                    self.tasks_failed += 1
                    del self.running_tasks[task_id]
                    self.failed_tasks[task_id] = task

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task"""
        with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
            elif task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
            elif task_id in self.failed_tasks:
                task = self.failed_tasks[task_id]
            else:
                # Check in queue
                for task in self.task_queue:
                    if task.task_id == task_id:
                        break
                else:
                    return None

            return {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'status': task.status.value,
                'priority': task.priority.name,
                'retry_count': task.retry_count,
                'created_at': task.created_at.isoformat(),
                'scheduled_at': task.scheduled_at.isoformat() if task.scheduled_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'result': task.result,
                'error': task.error
            }

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get overall scheduler status"""
        with self.lock:
            return {
                'running': self.running,
                'tasks_in_queue': len(self.task_queue),
                'tasks_running': len(self.running_tasks),
                'tasks_completed': self.tasks_completed,
                'tasks_failed': self.tasks_failed,
                'total_execution_time': self.total_execution_time,
                'average_execution_time': self.average_execution_time,
                'resource_utilization': self.resource_pool.get_utilization(),
                'available_resources': self.resource_pool.get_available()
            }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        with self.lock:
            # Check running tasks
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = TaskStatus.CANCELLED
                del self.running_tasks[task_id]
                return True

            # Check in queue
            for i, task in enumerate(self.task_queue):
                if task.task_id == task_id:
                    task.status = TaskStatus.CANCELLED
                    del self.task_queue[i]
                    heapq.heapify(self.task_queue)
                    return True

            return False

    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of task queue"""
        with self.lock:
            return [
                {
                    'task_id': task.task_id,
                    'task_name': task.task_name,
                    'priority': task.priority.name,
                    'status': task.status.value,
                    'deadline': task.deadline.isoformat() if task.deadline else None
                }
                for task in sorted(self.task_queue)[:100]  # Limit to 100
            ]

    def reset_scheduler(self) -> None:
        """Reset the scheduler"""
        with self.lock:
            self.task_queue = []
            self.running_tasks = {}
            self.completed_tasks = {}
            self.failed_tasks = {}
            self.dependency_graph = DependencyGraph()
            self.resource_pool = ResourcePool()
            self.tasks_scheduled = 0
            self.tasks_completed = 0
            self.tasks_failed = 0
            self.total_execution_time = 0.0
            self.average_execution_time = 0.0
