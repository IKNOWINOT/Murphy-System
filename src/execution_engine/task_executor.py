"""
Task Execution Engine - Core task scheduling and execution
"""

import logging
import os

# Import thread-safe utilities
import sys
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from thread_safe_operations import CircuitBreaker, ThreadSafeCounter, ThreadSafeDict
except ImportError:
    import threading as _fb_threading
    class CircuitBreaker:
        """Minimal fallback CircuitBreaker (pass-through, no tripping)."""
        def __init__(self, *args, **kwargs):
            pass
        def call(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)
        @property
        def state(self):
            return "closed"
        def reset(self) -> None:
            pass
    class ThreadSafeCounter:
        """Minimal fallback ThreadSafeCounter."""
        def __init__(self, initial_value: int = 0):
            self._value = initial_value
            self._lock = _fb_threading.Lock()
        def increment(self, delta: int = 1) -> int:
            with self._lock:
                self._value += delta
                return self._value
        def decrement(self, delta: int = 1) -> int:
            with self._lock:
                self._value -= delta
                return self._value
        def get(self) -> int:
            with self._lock:
                return self._value
        def reset(self) -> int:
            with self._lock:
                self._value = 0
                return self._value
    class ThreadSafeDict:
        """Minimal fallback ThreadSafeDict."""
        def __init__(self):
            self._dict: dict = {}
            self._lock = _fb_threading.RLock()
        def get(self, key, default=None):
            with self._lock:
                return self._dict.get(key, default)
        def set(self, key, value) -> None:
            with self._lock:
                self._dict[key] = value
        def delete(self, key) -> bool:
            with self._lock:
                if key in self._dict:
                    del self._dict[key]
                    return True
                return False
        def keys(self):
            with self._lock:
                return list(self._dict.keys())
        def values(self):
            with self._lock:
                return list(self._dict.values())
        def items(self):
            with self._lock:
                return list(self._dict.items())
        def update(self, other: dict) -> None:
            with self._lock:
                self._dict.update(other)
        def clear(self) -> None:
            with self._lock:
                self._dict.clear()
        def get_dict(self) -> dict:
            with self._lock:
                return dict(self._dict)
        def __len__(self) -> int:
            with self._lock:
                return len(self._dict)
        def __contains__(self, key) -> bool:
            with self._lock:
                return key in self._dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskState(Enum):
    """Task execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


class Task:
    """Task definition and state"""

    def __init__(
        self,
        task_id: Optional[str] = None,
        task_type: str = "generic",
        action: Optional[Callable] = None,
        parameters: Optional[Dict] = None,
        dependencies: Optional[List[str]] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        metadata: Optional[Dict] = None
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.task_type = task_type
        self.action = action
        self.parameters = parameters or {}
        self.dependencies = dependencies or []
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.metadata = metadata or {}

        # Execution state
        self.state = TaskState.PENDING
        self.retry_count = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.execution_time: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert task to dictionary"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'parameters': self.parameters,
            'dependencies': self.dependencies,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'state': self.state.value,
            'retry_count': self.retry_count,
            'result': self.result,
            'error': str(self.error) if self.error else None,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time
        }


class TaskScheduler:
    """Schedule tasks based on dependencies and priorities"""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.tasks: ThreadSafeDict = ThreadSafeDict()
        self.task_queue = []
        self._lock = threading.Lock()
        self.form_executor = ThreadPoolExecutor(max_workers=max_workers)

    def schedule_task(self, task: Task) -> str:
        """Schedule a task for execution"""
        with self._lock:
            self.tasks.set(task.task_id, task)
            self.task_queue.append(task.task_id)
            return task.task_id

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute"""
        ready_tasks = []
        with self._lock:
            for task_id in self.task_queue:
                task = self.tasks.get(task_id)
                if task and task.state == TaskState.PENDING:
                    # Check dependencies
                    dependencies_met = self._check_dependencies(task)
                    if dependencies_met:
                        ready_tasks.append(task)
        return ready_tasks

    def _check_dependencies(self, task: Task) -> bool:
        """Check if task dependencies are met"""
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.state != TaskState.COMPLETED:
                return False
        return True

    def update_task_state(self, task_id: str, new_state: TaskState) -> None:
        """Update task state"""
        task = self.tasks.get(task_id)
        if task:
            task.state = new_state
            self.tasks.set(task_id, task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        return list(self.tasks.values())

    def clear(self) -> None:
        """Clear all tasks"""
        with self._lock:
            self.tasks.clear()
            self.task_queue.clear()


class TaskExecutor:
    """Core task execution engine with retry and timeout"""

    def __init__(self, max_workers: int = 10):
        self.scheduler = TaskScheduler(max_workers=max_workers)
        self.task_history: ThreadSafeDict = ThreadSafeDict()
        self.active_tasks = ThreadSafeCounter()
        self._lock = threading.Lock()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            expected_exception=Exception
        )
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def schedule_task(self, task: Task) -> str:
        """Schedule a task for execution"""
        task_id = self.scheduler.schedule_task(task)
        logger.info(f"Task scheduled: {task_id} (type: {task.task_type})")
        return task_id

    def start(self) -> None:
        """Start the task executor"""
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(target=self._run_executor, daemon=True)
            self._worker_thread.start()
            logger.info("Task executor started")

    def stop(self) -> None:
        """Stop the task executor"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        logger.info("Task executor stopped")

    def _run_executor(self) -> None:
        """Main executor loop"""
        while self._running:
            try:
                # Get ready tasks
                ready_tasks = self.scheduler.get_ready_tasks()

                # Execute ready tasks
                for task in ready_tasks:
                    if not self._running:
                        break

                    # Submit task to thread pool
                    future = self.scheduler.form_executor.submit(self._execute_task, task)

                    # Update task state
                    self.scheduler.update_task_state(task.task_id, TaskState.RUNNING)
                    self.active_tasks.increment()

                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)

            except Exception as exc:
                logger.error(f"Error in executor loop: {exc}")

    def _execute_task(self, task: Task) -> None:
        """Execute a single task"""
        task.started_at = datetime.now(timezone.utc)
        self.scheduler.update_task_state(task.task_id, TaskState.RUNNING)

        try:
            # Use circuit breaker to prevent cascading failures
            result = self.circuit_breaker.call(
                self._execute_with_retry, task
            )

            # Task completed successfully
            task.result = result
            task.state = TaskState.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.execution_time = (task.completed_at - task.started_at).total_seconds()

            logger.info(f"Task completed: {task.task_id} in {task.execution_time:.2f}s")

        except Exception as exc:
            # Task failed
            task.error = exc
            task.state = TaskState.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.execution_time = (task.completed_at - task.started_at).total_seconds()

            logger.error(f"Task failed: {task.task_id} - {exc}")

        finally:
            # Update scheduler and decrement active count
            self.scheduler.update_task_state(task.task_id, task.state)
            self.task_history.set(task.task_id, task.to_dict())
            self.active_tasks.decrement()

    def _execute_with_retry(self, task: Task) -> Any:
        """Execute task with retry logic"""
        last_error = None

        for attempt in range(task.max_retries + 1):
            try:
                # Check timeout
                if task.started_at and (datetime.now(timezone.utc) - task.started_at).total_seconds() > task.timeout:
                    raise TimeoutError(f"Task timeout after {task.timeout}s")

                # Execute the task action
                if task.action:
                    result = task.action(**task.parameters)
                else:
                    result = self._default_action(task)

                return result

            except Exception as exc:
                last_error = exc
                task.retry_count = attempt + 1

                if attempt < task.max_retries:
                    # Retry with exponential backoff
                    delay = task.retry_delay * (2 ** attempt)
                    logger.warning(f"Task {task.task_id} failed (attempt {attempt + 1}), retrying in {delay}s")
                    task.state = TaskState.RETRYING
                    time.sleep(delay)
                else:
                    # Max retries reached
                    logger.error(f"Task {task.task_id} failed after {task.max_retries} retries")
                    raise

        # Should not reach here
        raise last_error or Exception("Task execution failed")

    def _default_action(self, task: Task) -> Any:
        """Default action when no action is provided"""
        return {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'parameters': task.parameters,
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        task = self.scheduler.get_task(task_id)
        if task and task.state in [TaskState.PENDING, TaskState.RETRYING]:
            task.state = TaskState.CANCELLED
            self.scheduler.update_task_state(task_id, TaskState.CANCELLED)
            logger.info(f"Task cancelled: {task_id}")
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status"""
        task = self.scheduler.get_task(task_id)
        if task:
            return task.to_dict()
        return None

    def get_all_task_statuses(self) -> List[Dict]:
        """Get all task statuses"""
        tasks = self.scheduler.get_all_tasks()
        return [task.to_dict() for task in tasks]

    def get_active_task_count(self) -> int:
        """Get number of active tasks"""
        return self.active_tasks.get()

    def get_task_history(self, task_id: str) -> Optional[Dict]:
        """Get task execution history"""
        return self.task_history.get(task_id)

    def get_statistics(self) -> Dict:
        """Get executor statistics"""
        tasks = self.scheduler.get_all_tasks()

        stats = {
            'total_tasks': len(tasks),
            'active_tasks': self.active_tasks.get(),
            'completed_tasks': len([t for t in tasks if t.state == TaskState.COMPLETED]),
            'failed_tasks': len([t for t in tasks if t.state == TaskState.FAILED]),
            'pending_tasks': len([t for t in tasks if t.state == TaskState.PENDING]),
            'cancelled_tasks': len([t for t in tasks if t.state == TaskState.CANCELLED]),
            'retrying_tasks': len([t for t in tasks if t.state == TaskState.RETRYING]),
            'average_execution_time': self._calculate_average_execution_time(tasks)
        }

        return stats

    def _calculate_average_execution_time(self, tasks: List[Task]) -> float:
        """Calculate average execution time for completed tasks"""
        completed_tasks = [t for t in tasks if t.execution_time is not None]
        if not completed_tasks:
            return 0.0
        return sum(t.execution_time for t in completed_tasks) / len(completed_tasks)


# Convenience functions

def create_task(
    task_type: str,
    action: Optional[Callable] = None,
    parameters: Optional[Dict] = None,
    **kwargs
) -> Task:
    """Create a task"""
    return Task(
        task_type=task_type,
        action=action,
        parameters=parameters,
        **kwargs
    )


def execute_task(
    action: Callable,
    parameters: Optional[Dict] = None,
    **kwargs
) -> Any:
    """Execute a single task immediately"""
    task = create_task(
        task_type="immediate",
        action=action,
        parameters=parameters,
        **kwargs
    )

    executor = TaskExecutor(max_workers=1)
    executor.start()
    task_id = executor.schedule_task(task)

    # Wait for task completion
    while executor.get_task_status(task_id)['state'] == 'running':
        time.sleep(0.1)

    task_status = executor.get_task_status(task_id)
    executor.stop()

    if task_status['state'] == 'completed':
        return task_status['result']
    else:
        raise Exception(f"Task failed: {task_status.get('error')}")
