"""Tests for the HITL task queue."""

import pytest

from src.billing.grants import task_queue
from src.billing.grants.models import TaskType


@pytest.fixture(autouse=True)
def clear_tasks():
    """Clear task store before each test."""
    task_queue._TASKS.clear()
    yield
    task_queue._TASKS.clear()


SESSION_ID = "test-session-tasks"


class TestCreateTask:
    def test_creates_task(self):
        task = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "Review EIN", "Check EIN is correct"
        )
        assert task.task_id
        assert task.session_id == SESSION_ID
        assert task.task_type == TaskType.needs_review
        assert task.title == "Review EIN"
        assert task.status == "pending"

    def test_task_stored(self):
        task = task_queue.create_task(
            SESSION_ID, TaskType.auto_filled, "Auto Task", "desc"
        )
        all_tasks = task_queue.get_all_tasks(SESSION_ID)
        assert any(t.task_id == task.task_id for t in all_tasks)

    def test_default_priority(self):
        task = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "T", "desc"
        )
        assert task.priority == 50

    def test_custom_priority(self):
        task = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "T", "desc", priority=10
        )
        assert task.priority == 10

    def test_depends_on(self):
        task = task_queue.create_task(
            SESSION_ID, TaskType.blocked_human_required, "Blocked", "desc",
            depends_on=["fake-dep-id"]
        )
        assert "fake-dep-id" in task.depends_on


class TestGetNextTasks:
    def test_returns_unblocked_tasks(self):
        t1 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T1", "d")
        tasks = task_queue.get_next_tasks(SESSION_ID)
        assert any(t.task_id == t1.task_id for t in tasks)

    def test_blocked_task_not_in_next(self):
        t1 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T1", "d")
        t2 = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "T2", "d", depends_on=[t1.task_id]
        )
        next_tasks = task_queue.get_next_tasks(SESSION_ID)
        ids = {t.task_id for t in next_tasks}
        assert t1.task_id in ids
        assert t2.task_id not in ids

    def test_sorted_by_priority(self):
        task_queue.create_task(SESSION_ID, TaskType.needs_review, "Low", "d", priority=90)
        task_queue.create_task(SESSION_ID, TaskType.needs_review, "High", "d", priority=5)
        next_tasks = task_queue.get_next_tasks(SESSION_ID)
        assert next_tasks[0].priority <= next_tasks[-1].priority

    def test_unblocked_after_dep_completed(self):
        t1 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T1", "d")
        t2 = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "T2", "d", depends_on=[t1.task_id]
        )
        # Before completing t1, t2 is blocked
        next_before = {t.task_id for t in task_queue.get_next_tasks(SESSION_ID)}
        assert t2.task_id not in next_before

        task_queue.complete_task(SESSION_ID, t1.task_id)

        # After completing t1, t2 should be in next
        next_after = {t.task_id for t in task_queue.get_next_tasks(SESSION_ID)}
        assert t2.task_id in next_after


class TestCompleteTask:
    def test_marks_completed(self):
        task = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T", "d")
        completed = task_queue.complete_task(SESSION_ID, task.task_id)
        assert completed is not None
        assert completed.status == "completed"

    def test_stores_result_data(self):
        task = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T", "d")
        task_queue.complete_task(SESSION_ID, task.task_id, result_data={"key": "value"})
        tasks = task_queue.get_all_tasks(SESSION_ID)
        done = next(t for t in tasks if t.task_id == task.task_id)
        assert done.form_fields.get("key") == "value"

    def test_returns_none_for_unknown_task(self):
        result = task_queue.complete_task(SESSION_ID, "nonexistent-task")
        assert result is None


class TestGetBlockedTasks:
    def test_blocked_task_appears(self):
        t1 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T1", "d")
        t2 = task_queue.create_task(
            SESSION_ID, TaskType.needs_review, "T2", "d", depends_on=[t1.task_id]
        )
        blocked = task_queue.get_blocked_tasks(SESSION_ID)
        blocked_ids = {t.task_id for t in blocked}
        assert t2.task_id in blocked_ids
        assert t1.task_id not in blocked_ids

    def test_no_blocked_when_no_deps(self):
        task_queue.create_task(SESSION_ID, TaskType.needs_review, "T", "d")
        assert task_queue.get_blocked_tasks(SESSION_ID) == []


class TestGetWaitingTasks:
    def test_waiting_on_external_tasks(self):
        t = task_queue.create_task(
            SESSION_ID, TaskType.waiting_on_external, "SAM.gov pending", "Waiting"
        )
        waiting = task_queue.get_waiting_tasks(SESSION_ID)
        assert any(w.task_id == t.task_id for w in waiting)

    def test_non_waiting_tasks_excluded(self):
        task_queue.create_task(SESSION_ID, TaskType.needs_review, "Review", "d")
        waiting = task_queue.get_waiting_tasks(SESSION_ID)
        assert waiting == []


class TestGetProgress:
    def test_empty_session(self):
        progress = task_queue.get_progress("empty-session-xyz")
        assert progress["total"] == 0
        assert progress["completion_pct"] == 0.0

    def test_progress_tracking(self):
        t1 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T1", "d")
        t2 = task_queue.create_task(SESSION_ID, TaskType.needs_review, "T2", "d")
        task_queue.create_task(SESSION_ID, TaskType.needs_review, "T3", "d")

        progress = task_queue.get_progress(SESSION_ID)
        assert progress["total"] == 3
        assert progress["completed"] == 0

        task_queue.complete_task(SESSION_ID, t1.task_id)
        task_queue.complete_task(SESSION_ID, t2.task_id)

        progress = task_queue.get_progress(SESSION_ID)
        assert progress["completed"] == 2
        assert progress["completion_pct"] == pytest.approx(66.7, abs=0.1)

    def test_completion_100_percent(self):
        t = task_queue.create_task(SESSION_ID, TaskType.auto_filled, "T", "d")
        task_queue.complete_task(SESSION_ID, t.task_id)
        progress = task_queue.get_progress(SESSION_ID)
        assert progress["completion_pct"] == 100.0
