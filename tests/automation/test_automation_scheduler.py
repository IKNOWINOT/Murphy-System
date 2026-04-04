"""Tests for the Automation Scheduler module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import threading
import pytest
from src.automation_scheduler import (
    AutomationScheduler,
    ProjectSchedule,
    ScheduledExecution,
    SchedulePriority,
)
from src.automation_scheduler import ScheduledExecution as SE


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def scheduler():
    return AutomationScheduler()


def _make_schedule(
    project_id="proj-1",
    task_description="Run tests",
    task_type="test",
    priority=SchedulePriority.MEDIUM,
    cron_expression=None,
    max_concurrent=1,
    parameters=None,
):
    return ProjectSchedule(
        project_id=project_id,
        task_description=task_description,
        task_type=task_type,
        priority=priority,
        cron_expression=cron_expression,
        max_concurrent=max_concurrent,
        parameters=parameters or {},
    )


# ------------------------------------------------------------------
# Adding / removing projects
# ------------------------------------------------------------------

class TestProjectManagement:
    def test_add_project(self, scheduler):
        pid = scheduler.add_project(_make_schedule(project_id="p1"))
        assert pid == "p1"
        status = scheduler.get_status()
        assert status["total_projects"] == 1
        assert status["total_executions"] == 1

    def test_add_multiple_projects(self, scheduler):
        for i in range(3):
            scheduler.add_project(_make_schedule(project_id=f"p-{i}"))
        assert scheduler.get_status()["total_projects"] == 3
        assert scheduler.get_status()["total_executions"] == 3

    def test_remove_project(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        assert scheduler.remove_project("p1") is True
        assert scheduler.get_status()["total_projects"] == 0

    def test_remove_nonexistent_project(self, scheduler):
        assert scheduler.remove_project("nonexistent") is False

    def test_remove_keeps_running_executions(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        scheduler.start_execution(batch[0].execution_id)
        scheduler.remove_project("p1")
        # Running execution should still exist
        assert scheduler.get_status()["running_executions"] == 1


# ------------------------------------------------------------------
# Getting next batch with priority ordering
# ------------------------------------------------------------------

class TestGetNextBatch:
    def test_empty_queue(self, scheduler):
        assert scheduler.get_next_batch() == []

    def test_single_pending(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        assert len(batch) == 1
        assert batch[0].project_id == "p1"
        assert batch[0].status == "pending"

    def test_priority_ordering(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="low", priority=SchedulePriority.LOW))
        scheduler.add_project(_make_schedule(project_id="crit", priority=SchedulePriority.CRITICAL))
        scheduler.add_project(_make_schedule(project_id="high", priority=SchedulePriority.HIGH))
        batch = scheduler.get_next_batch(max_slots=3)
        project_ids = [e.project_id for e in batch]
        assert project_ids == ["crit", "high", "low"]

    def test_max_slots_limit(self, scheduler):
        for i in range(10):
            scheduler.add_project(_make_schedule(project_id=f"p-{i}"))
        batch = scheduler.get_next_batch(max_slots=3)
        assert len(batch) == 3

    def test_batch_excludes_running(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        scheduler.start_execution(batch[0].execution_id)
        second_batch = scheduler.get_next_batch()
        assert len(second_batch) == 0


# ------------------------------------------------------------------
# Execution lifecycle (start -> complete)
# ------------------------------------------------------------------

class TestExecutionLifecycle:
    def test_start_execution(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        assert scheduler.start_execution(eid) is True
        assert scheduler.get_status()["running_executions"] == 1

    def test_start_nonexistent_execution(self, scheduler):
        assert scheduler.start_execution("fake-id") is False

    def test_complete_execution_success(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        scheduler.start_execution(eid)
        assert scheduler.complete_execution(eid, success=True, result={"output": "ok"}) is True
        assert scheduler.get_status()["completed_executions"] == 1

    def test_complete_execution_failure(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        scheduler.start_execution(eid)
        assert scheduler.complete_execution(eid, success=False) is True
        assert scheduler.get_status()["failed_executions"] == 1

    def test_cannot_complete_pending(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        assert scheduler.complete_execution(eid, success=True) is False

    def test_cannot_start_already_running(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        scheduler.start_execution(eid)
        assert scheduler.start_execution(eid) is False

    def test_recurring_task_requeues(self, scheduler):
        scheduler.add_project(
            _make_schedule(project_id="cron-p", cron_expression="*/5 * * * *")
        )
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        scheduler.start_execution(eid)
        scheduler.complete_execution(eid, success=True)
        # A new pending execution should exist
        assert scheduler.get_status()["pending_executions"] == 1
        assert scheduler.get_status()["total_executions"] == 2

    def test_scheduled_execution_default_timestamp(self):
        exe = ScheduledExecution(execution_id="e1", project_id="p1")
        assert exe.scheduled_at is not None


# ------------------------------------------------------------------
# Load balancing (max_concurrent enforcement)
# ------------------------------------------------------------------

class TestLoadBalancing:
    def test_max_concurrent_one(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1", max_concurrent=1))
        batch = scheduler.get_next_batch()
        scheduler.start_execution(batch[0].execution_id)
        # Add another execution manually for the same project
        with scheduler._lock:
            exe = SE(execution_id="extra-1", project_id="p1")
            scheduler._executions[exe.execution_id] = exe
            scheduler._project_executions["p1"].append(exe.execution_id)
        second_batch = scheduler.get_next_batch()
        assert len(second_batch) == 0

    def test_max_concurrent_two(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1", max_concurrent=2))
        # Add a second pending execution
        with scheduler._lock:
            exe = SE(execution_id="extra-1", project_id="p1")
            scheduler._executions[exe.execution_id] = exe
            scheduler._project_executions["p1"].append(exe.execution_id)
        batch = scheduler.get_next_batch(max_slots=5)
        assert len(batch) == 2

    def test_mixed_projects_load_balance(self, scheduler):
        scheduler.add_project(
            _make_schedule(project_id="fast", max_concurrent=2, priority=SchedulePriority.HIGH)
        )
        scheduler.add_project(
            _make_schedule(project_id="slow", max_concurrent=1, priority=SchedulePriority.LOW)
        )
        # Add extra pending for "fast"
        with scheduler._lock:
            exe = SE(execution_id="fast-extra", project_id="fast")
            scheduler._executions[exe.execution_id] = exe
            scheduler._project_executions["fast"].append(exe.execution_id)
        batch = scheduler.get_next_batch(max_slots=5)
        fast_count = sum(1 for e in batch if e.project_id == "fast")
        slow_count = sum(1 for e in batch if e.project_id == "slow")
        assert fast_count == 2
        assert slow_count == 1


# ------------------------------------------------------------------
# Queue status reporting
# ------------------------------------------------------------------

class TestStatusReporting:
    def test_empty_status(self, scheduler):
        status = scheduler.get_status()
        assert status["total_projects"] == 0
        assert status["total_executions"] == 0

    def test_queue_status(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        scheduler.add_project(_make_schedule(project_id="p2"))
        qs = scheduler.get_queue_status()
        assert qs["total_projects"] == 2
        assert qs["total_executions"] == 2
        assert qs["pending"] == 2

    def test_project_status_found(self, scheduler):
        scheduler.add_project(
            _make_schedule(project_id="p1", task_type="deploy", priority=SchedulePriority.HIGH)
        )
        ps = scheduler.get_project_status("p1")
        assert ps["found"] is True
        assert ps["task_type"] == "deploy"
        assert ps["priority"] == "high"
        assert ps["status_counts"]["pending"] == 1

    def test_project_status_not_found(self, scheduler):
        ps = scheduler.get_project_status("nonexistent")
        assert ps["found"] is False

    def test_status_after_lifecycle(self, scheduler):
        scheduler.add_project(_make_schedule(project_id="p1"))
        batch = scheduler.get_next_batch()
        eid = batch[0].execution_id
        scheduler.start_execution(eid)
        status = scheduler.get_status()
        assert status["running_executions"] == 1
        assert status["pending_executions"] == 0
        scheduler.complete_execution(eid, success=True)
        status = scheduler.get_status()
        assert status["completed_executions"] == 1
        assert status["running_executions"] == 0


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_add_projects(self, scheduler):
        errors = []

        def add_project(idx):
            try:
                scheduler.add_project(_make_schedule(project_id=f"tp-{idx}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_project, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert scheduler.get_status()["total_projects"] == 20

    def test_concurrent_start_and_complete(self, scheduler):
        for i in range(10):
            scheduler.add_project(_make_schedule(project_id=f"cp-{i}"))

        batch = scheduler.get_next_batch(max_slots=10)
        errors = []

        def run_execution(exe):
            try:
                scheduler.start_execution(exe.execution_id)
                scheduler.complete_execution(exe.execution_id, success=True)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run_execution, args=(e,)) for e in batch]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        status = scheduler.get_status()
        assert status["completed_executions"] == 10
        assert status["running_executions"] == 0

    def test_concurrent_batch_retrieval(self, scheduler):
        for i in range(5):
            scheduler.add_project(_make_schedule(project_id=f"bp-{i}"))

        results = []

        def get_batch():
            results.append(scheduler.get_next_batch(max_slots=5))

        threads = [threading.Thread(target=get_batch) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        for batch in results:
            assert len(batch) == 5
