"""
Simple Tests for Autonomous Scheduler component (No Threading)

Tests:
- Task functionality
- Resource management
- Dependency graph
- Basic scheduling operations

Note: These tests avoid threading to prevent timeouts
"""

import unittest
import heapq
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

    def test_task_execution(self):
        """Test task execution"""
        def task_func():
            return "task_result"

        task = Task(
            task_id="task_1",
            task_name="Test Task",
            priority=TaskPriority.HIGH,
            task_function=task_func
        )

        result = task.task_function()

        self.assertEqual(result, "task_result")


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

        # Resources should not be allocated
        available = self.pool.get_available()
        self.assertEqual(available['cpu_cores'], 4)

    def test_partial_insufficient_resources(self):
        """Test allocation when one resource is insufficient"""
        requirements = {'cpu_cores': 2, 'memory_gb': 20}  # Memory insufficient

        success = self.pool.allocate(requirements)

        self.assertFalse(success)

    def test_get_total_resources(self):
        """Test getting total resources"""
        total = self.pool.resources

        self.assertEqual(total['cpu_cores'], 4)
        self.assertEqual(total['memory_gb'], 16)


class TestDependencyGraph(unittest.TestCase):
    """Test DependencyGraph functionality"""

    def setUp(self):
        self.graph = DependencyGraph()

    def test_add_task_no_dependencies(self):
        """Test adding task with no dependencies"""
        self.graph.add_task("task_1", [])

        self.assertIn("task_1", self.graph.graph)

    def test_add_task_with_dependencies(self):
        """Test adding task with dependencies"""
        self.graph.add_task("task_1", ["dep_1", "dep_2"])

        # Check forward graph
        self.assertEqual(self.graph.graph["task_1"], ["dep_1", "dep_2"])

        # Check reverse graph
        self.assertIn("task_1", self.graph.reverse_graph["dep_1"])
        self.assertIn("task_1", self.graph.reverse_graph["dep_2"])

    def test_check_dependencies_satisfied(self):
        """Test checking if dependencies are satisfied"""
        self.graph.add_task("task_1", ["dep_1", "dep_2"])

        # Dependencies not satisfied initially
        self.assertFalse(self.graph.can_execute("task_1", {"dep_1"}))

        # Dependencies satisfied
        self.assertTrue(self.graph.can_execute("task_1", {"dep_1", "dep_2"}))

    def test_remove_task(self):
        """Test removing task from graph"""
        self.graph.add_task("task_1", ["dep_1", "dep_2"])
        self.graph.add_task("task_2", ["task_1"])  # task_2 depends on task_1

        # Remove task_1
        self.graph.remove_task("task_1")

        # task_1 should be removed
        self.assertNotIn("task_1", self.graph.graph)

        # dep_1 and dep_2 should no longer depend on task_1
        self.assertNotIn("task_1", self.graph.reverse_graph["dep_1"])
        self.assertNotIn("task_1", self.graph.reverse_graph["dep_2"])

    def test_get_dependents(self):
        """Test getting tasks that depend on a task"""
        self.graph.add_task("task_1", [])
        self.graph.add_task("task_2", ["task_1"])
        self.graph.add_task("task_3", ["task_1"])

        dependents = self.graph.get_dependents("task_1")

        self.assertEqual(set(dependents), {"task_2", "task_3"})


class TestAutonomousScheduler(unittest.TestCase):
    """Test AutonomousScheduler basic functionality (no threading)"""

    def setUp(self):
        self.scheduler = AutonomousScheduler(enable_autonomous=True)  # Enable autonomous for scheduling to work

    def test_create_task(self):
        """Test creating a task"""
        def task_func():
            return "done"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.assertIsNotNone(task)
        self.assertEqual(task.task_name, "Test Task")
        self.assertEqual(task.priority, TaskPriority.HIGH)

    def test_schedule_task(self):
        """Test scheduling a task"""
        def task_func():
            return "done"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        success = self.scheduler.schedule_task(task)

        self.assertTrue(success)
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_task_queue(self):
        """Test task queue management"""
        for i in range(5):
            def task_func():
                return f"task_{i}"

            task = self.scheduler.create_task(
                task_name=f"Task {i}",
                task_function=task_func,
                priority=TaskPriority.HIGH
            )

            self.scheduler.schedule_task(task)

        # Check queue size
        self.assertEqual(len(self.scheduler.task_queue), 5)

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

    def test_get_scheduler_status(self):
        """Test getting scheduler status"""
        status = self.scheduler.get_scheduler_status()

        self.assertIn('running', status)
        self.assertIn('tasks_in_queue', status)
        self.assertIn('tasks_completed', status)
        self.assertIn('tasks_failed', status)

    def test_cancel_task(self):
        """Test cancelling a task"""
        def task_func():
            return "done"

        task = self.scheduler.create_task(
            task_name="Test Task",
            task_function=task_func,
            priority=TaskPriority.HIGH
        )

        self.scheduler.schedule_task(task)

        success = self.scheduler.cancel_task(task.task_id)

        self.assertTrue(success)
        self.assertEqual(task.status, TaskStatus.CANCELLED)


if __name__ == '__main__':
    unittest.main()
