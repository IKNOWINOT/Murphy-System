"""
Tests for Autonomous Scheduler component

Tests:
- Autonomous scheduler functionality
- Task scheduling and execution
- Resource management
- Dependency handling
- Priority-based scheduling
"""

import unittest
import time
import threading
from datetime import datetime, timedelta
from src.autonomous_systems import (
    AutonomousScheduler,
    Task,
    TaskPriority,
    TaskStatus,
    ResourcePool,
    DependencyGraph
)


class TestTask(unittest.TestCase):
    """Test Task dataclass"""

    def test_task_creation(self):
        """Test creating a task"""
        def task_func():
            return "done"

        task = Task(
            task_id="task_1",
            task_name="Test Task",
            priority=TaskPriority.HIGH,
            task_function=task_func
        )

        self.assertEqual(task.task_id, "task_1")
        self.assertEqual(task.task_name, "Test Task")
        self.assertEqual(task.priority, TaskPriority.HIGH)
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_task_comparison(self):
        """Test task comparison for heap ordering"""
        def task_func():
            return "done"

        task1 = Task(
            task_id="task_1",
            task_name="Task 1",
            priority=TaskPriority.HIGH,
            task_function=task_func
        )

        task2 = Task(
            task_id="task_2",
            task_name="Task 2",
            priority=TaskPriority.MEDIUM,
            task_function=task_func
        )

        # HIGH priority should come before MEDIUM
        self.assertTrue(task1 < task2)

    def test_task_deadline_comparison(self):
        """Test task comparison with deadlines"""
        def task_func():
            return "done"

        now = datetime.now()

        task1 = Task(
            task_id="task_1",
            task_name="Task 1",
            priority=TaskPriority.MEDIUM,
            task_function=task_func,
            deadline=now + timedelta(hours=1)
        )

        task2 = Task(
            task_id="task_2",
            task_name="Task 2",
            priority=TaskPriority.MEDIUM,
            task_function=task_func,
            deadline=now + timedelta(hours=2)
        )

        # Earlier deadline should come first
        self.assertTrue(task1 < task2)


class TestResourcePool(unittest.TestCase):
    """Test ResourcePool functionality"""

    def setUp(self):
        self.pool = ResourcePool()

    def test_initial_resources(self):
        """Test initial resource allocation"""
        available = self.pool.get_available()

        self.assertIn('cpu_cores', available)
        self.assertIn('memory_gb', available)
        self.assertEqual(available['cpu_cores'], 4)
        self.assertEqual(available['memory_gb'], 16)

    def test_resource_allocation(self):
        """Test allocating resources"""
        requirements = {'cpu_cores': 2, 'memory_gb': 4}

        success = self.pool.allocate(requirements)

        self.assertTrue(success)

        available = self.pool.get_available()
        self.assertEqual(available['cpu_cores'], 2)
        self.assertEqual(available['memory_gb'], 12)

    def test_resource_release(self):
        """Test releasing resources"""
        requirements = {'cpu_cores': 2, 'memory_gb': 4}

        self.pool.allocate(requirements)
        self.pool.release(requirements)

        available = self.pool.get_available()
        self.assertEqual(available['cpu_cores'], 4)
        self.assertEqual(available['memory_gb'], 16)

    def test_insufficient_resources(self):
        """Test allocation with insufficient resources"""
        requirements = {'cpu_cores': 10}  # More than available

        success = self.pool.allocate(requirements)

        self.assertFalse(success)

    def test_utilization_calculation(self):
        """Test resource utilization calculation"""
        requirements = {'cpu_cores': 2, 'memory_gb': 8}

        self.pool.allocate(requirements)
        utilization = self.pool.get_utilization()

        self.assertEqual(utilization['cpu_cores'], 0.5)  # 2/4
        self.assertEqual(utilization['memory_gb'], 0.5)  # 8/16


class TestDependencyGraph(unittest.TestCase):
    """Test DependencyGraph functionality"""

    def setUp(self):
        self.graph = DependencyGraph()

    def test_add_task_no_dependencies(self):
        """Test adding task without dependencies"""
        self.graph.add_task("task_1", [])

        # Task with no dependencies should be executable immediately
        self.assertTrue(self.graph.can_execute("task_1", set()))

    def test_add_task_with_dependencies(self):
        """Test adding task with dependencies"""
        self.graph.add_task("task_1", [])
        self.graph.add_task("task_2", ["task_1"])

        # Task 1 has no deps, can execute immediately
        self.assertTrue(self.graph.can_execute("task_1", set()))
        # Task 2 cannot execute until task 1 completes
        self.assertFalse(self.graph.can_execute("task_2", set()))

        # After task 1 completes, task 2 is ready
        self.assertTrue(self.graph.can_execute("task_2", {"task_1"}))

    def test_get_dependents(self):
        """Test getting dependent tasks"""
        self.graph.add_task("task_1", [])
        self.graph.add_task("task_2", ["task_1"])
        self.graph.add_task("task_3", ["task_1"])

        dependents = self.graph.get_dependents("task_1")

        self.assertEqual(len(dependents), 2)
        self.assertIn("task_2", dependents)
        self.assertIn("task_3", dependents)


class TestAutonomousScheduler(unittest.TestCase):
    """Test AutonomousScheduler functionality"""

    def setUp(self):
        self.scheduler = AutonomousScheduler(enable_autonomous=True)
        self.task_results = {}

    def tearDown(self):
        self.scheduler.stop()

    def test_create_task(self):
        """Test creating a task"""
        def task_func():
            return "result"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.task_name, "Test Task")
        self.assertEqual(task.priority, TaskPriority.HIGH)
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_schedule_task(self):
        """Test scheduling a task"""
        def task_func():
            self.task_results['task_1'] = "done"
            return "done"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        success = self.scheduler.schedule_task(task)

        self.assertTrue(success)
        self.assertEqual(len(self.scheduler.task_queue), 1)

    def test_autonomous_disabled(self):
        """Test behavior when autonomous is disabled"""
        scheduler = AutonomousScheduler(enable_autonomous=False)

        def task_func():
            return "done"

        task = scheduler.create_task(
            task_name="Test Task",
            task_function=task_func
        )

        success = scheduler.schedule_task(task)

        self.assertFalse(success)

    def test_scheduler_start_stop(self):
        """Test starting and stopping scheduler"""
        self.assertFalse(self.scheduler.running)

        self.scheduler.start()
        self.assertTrue(self.scheduler.running)

        self.scheduler.stop()
        self.assertFalse(self.scheduler.running)

    def test_task_execution(self):
        """Test that tasks execute correctly"""
        execution_result = []

        def task_func():
            execution_result.append("executed")
            return "result"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.scheduler.schedule_task(task)
        self.scheduler.start()

        # Wait for task to complete
        time.sleep(0.5)

        self.assertEqual(len(execution_result), 1)
        self.assertEqual(execution_result[0], "executed")

    def test_task_priority_ordering(self):
        """Test that tasks are executed in priority order"""
        execution_order = []

        def create_task_func(name):
            def task_func():
                execution_order.append(name)
                return name
            return task_func

        # Create tasks with different priorities
        low_task = self.scheduler.create_task(
            task_name="low",
            task_function=create_task_func("low"),
            priority=TaskPriority.LOW
        )

        high_task = self.scheduler.create_task(
            task_name="high",
            task_function=create_task_func("high"),
            priority=TaskPriority.HIGH
        )

        medium_task = self.scheduler.create_task(
            task_name="medium",
            task_function=create_task_func("medium"),
            priority=TaskPriority.MEDIUM
        )

        # Schedule tasks
        self.scheduler.schedule_task(low_task)
        self.scheduler.schedule_task(high_task)
        self.scheduler.schedule_task(medium_task)

        # Start scheduler
        self.scheduler.start()

        # Wait for tasks to complete
        time.sleep(1.0)

        # High priority should execute first
        self.assertEqual(execution_order[0], "high")

    def test_task_dependencies(self):
        """Test task dependency handling"""
        execution_order = []

        def create_task_func(name):
            def task_func():
                execution_order.append(name)
                return name
            return task_func

        # Create tasks with dependencies
        task1 = self.scheduler.create_task(
            task_name="task1",
            task_function=create_task_func("task1"),
            priority=TaskPriority.HIGH
        )

        task2 = self.scheduler.create_task(
            task_name="task2",
            task_function=create_task_func("task2"),
            priority=TaskPriority.HIGH,
            dependencies=[task1.task_id]
        )

        # Schedule tasks
        self.scheduler.schedule_task(task1)
        self.scheduler.schedule_task(task2)

        # Start scheduler
        self.scheduler.start()

        # Wait for tasks to complete
        time.sleep(1.0)

        # Task 1 should execute before task 2
        self.assertEqual(execution_order[0], "task1")
        self.assertEqual(execution_order[1], "task2")

    def test_task_retry_on_failure(self):
        """Test that failed tasks are retried"""
        execution_count = [0]

        def failing_task():
            execution_count[0] += 1
            if execution_count[0] < 2:
                raise Exception("Temporary failure")
            return "success"

        task = self.scheduler.create_task(
            task_name="Failing Task",
            task_function=failing_task,
            priority=TaskPriority.HIGH
        )
        task.max_retries = 3

        self.scheduler.schedule_task(task)
        self.scheduler.start()

        # Wait for task to complete (including retries)
        time.sleep(2.0)

        # Should have executed twice (initial + 1 retry)
        self.assertGreaterEqual(execution_count[0], 2)

    def test_scheduler_status(self):
        """Test getting scheduler status"""
        status = self.scheduler.get_scheduler_status()

        self.assertIn('running', status)
        self.assertIn('tasks_in_queue', status)
        self.assertIn('tasks_running', status)
        self.assertIn('tasks_completed', status)
        self.assertIn('resource_utilization', status)

    def test_cancel_task(self):
        """Test cancelling a task"""
        def task_func():
            time.sleep(10)  # Long-running task
            return "done"

        task = self.scheduler.create_task(
            task_name="Long Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.scheduler.schedule_task(task)

        # Cancel before execution
        success = self.scheduler.cancel_task(task.task_id)

        self.assertTrue(success)

    def test_get_task_status(self):
        """Test getting task status"""
        def task_func():
            return "done"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.scheduler.schedule_task(task)

        status = self.scheduler.get_task_status(task.task_id)

        self.assertIsNotNone(status)
        self.assertEqual(status['task_id'], task.task_id)
        self.assertEqual(status['task_name'], "Test Task")
        self.assertEqual(status['priority'], "HIGH")

    def test_get_queue_snapshot(self):
        """Test getting queue snapshot"""
        for i in range(5):
            def task_func():
                return f"task_{i}"

            task = self.scheduler.create_task(
                task_name=f"Task {i}",
                task_function=task_func,
                priority=TaskPriority.HIGH
            )

            self.scheduler.schedule_task(task)

        snapshot = self.scheduler.get_queue_snapshot()

        self.assertEqual(len(snapshot), 5)


class TestAutonomousSchedulerIntegration(unittest.TestCase):
    """Integration tests for autonomous scheduler"""

    def test_full_scheduling_cycle(self):
        """Test complete scheduling cycle"""
        scheduler = AutonomousScheduler(enable_autonomous=True)

        results = {}

        def create_task_func(name, duration):
            def task_func():
                time.sleep(duration)
                results[name] = f"{name}_completed"
                return results[name]
            return task_func

        # Create multiple tasks
        tasks = []
        for i in range(10):
            task = scheduler.create_task(
                task_name=f"Task {i}",
                task_function=create_task_func(f"task_{i}", 0.05),
                priority=TaskPriority.HIGH if i < 3 else TaskPriority.MEDIUM
            )
            tasks.append(task)
            scheduler.schedule_task(task)

        # Start scheduler
        scheduler.start()

        # Wait for all tasks to complete
        time.sleep(2.0)

        # Stop scheduler
        scheduler.stop()

        # Verify results
        status = scheduler.get_scheduler_status()

        self.assertGreaterEqual(len(results), 1)
        self.assertGreater(status['tasks_completed'], 0)


if __name__ == '__main__':
    unittest.main()
