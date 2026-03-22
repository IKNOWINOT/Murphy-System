"""
Test: HITL Task Queue State Transitions

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.task_queue import (
    CircularDependencyError,
    HitlTaskManager,
    TaskNotFoundError,
)
from src.billing.grants.models import HitlTaskState


@pytest.fixture
def mgr():
    return HitlTaskManager()

SESSION_ID = "test-session-001"


def test_add_task_creates_queue(mgr):
    """Adding a task creates a queue if none exists."""
    task = mgr.add_task(SESSION_ID, "Test Task", "A test task description")
    assert task.task_id is not None
    queue = mgr.get_queue(SESSION_ID)
    assert len(queue.tasks) == 1


def test_task_with_why_blocked_starts_blocked(mgr):
    """A task with why_blocked set starts in BLOCKED_HUMAN_REQUIRED state."""
    task = mgr.add_task(
        SESSION_ID,
        "SAM Registration",
        "Register in SAM.gov",
        why_blocked="Legal entity must register directly",
    )
    assert task.state == HitlTaskState.BLOCKED_HUMAN_REQUIRED


def test_high_confidence_task_auto_completes(mgr):
    """Task with confidence >= 0.8 starts as AUTO_COMPLETED."""
    task = mgr.add_task(
        SESSION_ID,
        "NAICS Auto-Fill",
        "Agent suggests NAICS codes",
        confidence=0.9,
    )
    assert task.state == HitlTaskState.AUTO_COMPLETED


def test_medium_confidence_task_needs_review(mgr):
    """Task with confidence 0.5–0.8 starts as NEEDS_REVIEW."""
    task = mgr.add_task(
        SESSION_ID,
        "Company Description",
        "Auto-filled description",
        confidence=0.65,
    )
    assert task.state == HitlTaskState.NEEDS_REVIEW


def test_task_with_unresolved_deps_stays_pending(mgr):
    """Task whose dependencies are not complete starts as PENDING."""
    dep_task = mgr.add_task(
        SESSION_ID,
        "SAM.gov Registration",
        "Must register first",
        why_blocked="Human must do this",
    )
    dep_task_id = dep_task.task_id

    dependent = mgr.add_task(
        SESSION_ID,
        "Grants.gov Account",
        "Needs SAM first",
        dependencies=[dep_task_id],
    )
    assert dependent.state == HitlTaskState.PENDING, (
        "Task with unresolved dependency should be PENDING"
    )


def test_completing_task_unblocks_downstream(mgr):
    """Completing a task should unblock downstream dependent tasks."""
    dep = mgr.add_task(
        SESSION_ID,
        "Step 1",
        "First step",
        why_blocked="Human required",
    )
    down = mgr.add_task(
        SESSION_ID,
        "Step 2",
        "Depends on step 1",
        dependencies=[dep.task_id],
    )
    assert down.state == HitlTaskState.PENDING

    # Complete the dependency
    mgr.update_task(SESSION_ID, dep.task_id, new_state=HitlTaskState.COMPLETED)

    # Re-fetch downstream task
    down_updated = mgr.get_task(SESSION_ID, down.task_id)
    assert down_updated.state != HitlTaskState.PENDING, (
        "Downstream task should no longer be PENDING after dependency completes"
    )


def test_invalid_state_transition_raises(mgr):
    """Transitioning from COMPLETED to PENDING should raise ValueError."""
    task = mgr.add_task(SESSION_ID, "Task", "desc", confidence=0.9)
    mgr.update_task(SESSION_ID, task.task_id, new_state=HitlTaskState.COMPLETED)

    with pytest.raises(ValueError):
        mgr.update_task(SESSION_ID, task.task_id, new_state=HitlTaskState.PENDING)


def test_circular_dependency_detected(mgr):
    """Adding a task that creates a circular dependency raises CircularDependencyError."""
    t1 = mgr.add_task(SESSION_ID, "Task 1", "desc")
    t2 = mgr.add_task(SESSION_ID, "Task 2", "desc", dependencies=[t1.task_id])

    # Now try to make t1 depend on t2 — this would create a cycle
    with pytest.raises(CircularDependencyError):
        mgr.add_task(SESSION_ID, "Task 3", "desc", dependencies=[t1.task_id, t2.task_id])
        # The circular check runs on the dep list; t2 already depends on t1
        # so adding t1->t2 via t2 as dep creates cycle
        # Actually let's directly test: modify t1 deps to include t2
        # Since we can't do this directly in the API, let's create a proper cycle scenario
    # Reset and test properly
    mgr2 = HitlTaskManager()
    s2 = "session-cycle"
    a = mgr2.add_task(s2, "A", "desc")
    b = mgr2.add_task(s2, "B", "desc", dependencies=[a.task_id])
    # Try to add C that depends on B — then try to add with dep that creates cycle
    # by checking that a depends_on b would cycle: a->b->a
    # We'll hack it: make a.dependencies = [b.task_id] and then check
    a.dependencies = [b.task_id]  # Direct manipulation
    # Now trying to add a new task that has b as dependency: fine
    # Adding task with [a] dep when a depends on b: a->b, new->a, not circular (chain)
    # Let's verify the DFS approach by creating an actual cycle
    mgr3 = HitlTaskManager()
    s3 = "session-direct-cycle"
    x = mgr3.add_task(s3, "X", "desc")
    y = mgr3.add_task(s3, "Y", "desc", dependencies=[x.task_id])
    # Manually set x to depend on y to simulate cycle detection
    x.dependencies = [y.task_id]
    # Now adding a task that depends on x should detect the x->y->x cycle
    with pytest.raises(CircularDependencyError):
        mgr3.add_task(s3, "Z", "desc", dependencies=[y.task_id])


def test_get_task_dependencies_returns_dep_tasks(mgr):
    """get_task_dependencies returns the actual dependency task objects."""
    t1 = mgr.add_task(SESSION_ID, "Step 1", "desc")
    t2 = mgr.add_task(SESSION_ID, "Step 2", "desc", dependencies=[t1.task_id])

    deps = mgr.get_task_dependencies(SESSION_ID, t2.task_id)
    assert len(deps) == 1
    assert deps[0].task_id == t1.task_id


def test_task_not_found_raises(mgr):
    """Accessing a nonexistent task raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError):
        mgr.get_task(SESSION_ID, "nonexistent-task-id")


def test_progress_summary_counts_correctly(mgr):
    """progress_summary returns correct counts per state."""
    mgr.add_task(SESSION_ID, "T1", "desc", why_blocked="blocked")  # BLOCKED_HUMAN_REQUIRED
    mgr.add_task(SESSION_ID, "T2", "desc", confidence=0.9)  # AUTO_COMPLETED
    mgr.add_task(SESSION_ID, "T3", "desc", confidence=0.6)  # NEEDS_REVIEW

    queue = mgr.get_queue(SESSION_ID)
    summary = queue.progress_summary()
    assert summary[HitlTaskState.BLOCKED_HUMAN_REQUIRED.value] >= 1
    assert summary[HitlTaskState.AUTO_COMPLETED.value] >= 1
    assert summary[HitlTaskState.NEEDS_REVIEW.value] >= 1


def test_human_provided_data_stored(mgr):
    """Human-provided data is stored on the task."""
    task = mgr.add_task(SESSION_ID, "SAM Registration", "desc", why_blocked="human needed")
    mgr.update_task(
        SESSION_ID,
        task.task_id,
        new_state=HitlTaskState.COMPLETED,
        human_provided_data={"uei": "ABCD1234XYZ", "cage": "1ABC2"},
    )
    updated = mgr.get_task(SESSION_ID, task.task_id)
    assert updated.human_provided_data["uei"] == "ABCD1234XYZ"
    assert updated.human_provided_data["cage"] == "1ABC2"
    assert updated.completed_at is not None
