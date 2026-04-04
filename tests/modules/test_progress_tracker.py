# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for ProgressTracker and OnboardingProgress."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG
from src.platform_onboarding.progress_tracker import ProgressTracker, OnboardingProgress
from src.platform_onboarding.onboarding_session import OnboardingSession


TOTAL = len(TASK_CATALOG)


def make_session() -> OnboardingSession:
    return OnboardingSession.create_new("test-account")


def test_fresh_session_zero_complete():
    tracker = ProgressTracker()
    session = make_session()
    progress = tracker.compute_progress(session)
    assert progress.completed == 0


def test_fresh_session_total_correct():
    tracker = ProgressTracker()
    session = make_session()
    progress = tracker.compute_progress(session)
    assert progress.total_tasks == TOTAL


def test_fresh_session_zero_percent():
    tracker = ProgressTracker()
    session = make_session()
    progress = tracker.compute_progress(session)
    assert progress.completion_percentage == 0.0


def test_fresh_session_not_started_count():
    tracker = ProgressTracker()
    session = make_session()
    progress = tracker.compute_progress(session)
    # All tasks that have no dependencies should be not_started (not blocked)
    no_dep_tasks = [t for t in TASK_CATALOG if not t.depends_on]
    assert progress.not_started >= len(no_dep_tasks)


def test_complete_task_increments_counter():
    tracker = ProgressTracker()
    session = make_session()
    session.set_task_state("5.01", "completed")
    progress = tracker.compute_progress(session)
    assert progress.completed == 1


def test_completing_ein_unblocks_sam_gov():
    """After completing 1.02, 1.01 (SAM.gov) should appear in unblocked tasks."""
    tracker = ProgressTracker()
    session = make_session()
    session.set_task_state("1.02", "completed")
    unblocked = tracker.get_unblocked_tasks(session)
    unblocked_ids = {t.task_id for t in unblocked}
    assert "1.01" in unblocked_ids, "SAM.gov should be unblocked after EIN completion"


def test_completion_percentage_increases():
    tracker = ProgressTracker()
    session = make_session()
    session.set_task_state("5.01", "completed")
    session.set_task_state("5.02", "completed")
    progress = tracker.compute_progress(session)
    assert progress.completion_percentage > 0.0


def test_completion_percentage_100():
    tracker = ProgressTracker()
    session = make_session()
    for task in TASK_CATALOG:
        session.set_task_state(task.task_id, "completed")
    progress = tracker.compute_progress(session)
    assert progress.completion_percentage == 100.0


def test_waiting_external_counted_separately():
    tracker = ProgressTracker()
    session = make_session()
    session.set_task_state("1.01", "waiting_on_external")
    progress = tracker.compute_progress(session)
    assert progress.waiting_on_external == 1


def test_get_unblocked_tasks_initial():
    """Initially, all tasks with no dependencies should be unblocked."""
    tracker = ProgressTracker()
    session = make_session()
    unblocked = tracker.get_unblocked_tasks(session)
    unblocked_ids = {t.task_id for t in unblocked}
    # All section 4 (cloud credits) and section 5 (API keys) have no deps
    for t in TASK_CATALOG:
        if not t.depends_on:
            assert t.task_id in unblocked_ids, f"{t.task_id} should be unblocked initially"


def test_critical_path():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert "1.02" in path
    assert "1.01" in path
    assert "1.03" in path
    assert path.index("1.02") < path.index("1.01")


def test_parallel_groups_level_0():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_0 = set(groups.get(0, []))
    # EIN (1.02) has no deps → level 0
    assert "1.02" in level_0
    # Cloud credits have no deps → level 0
    for tid in ["4.01", "4.02", "4.03", "4.04", "4.05", "4.06", "4.07", "4.08"]:
        assert tid in level_0, f"{tid} should be level 0"


def test_parallel_groups_level_1():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_1 = set(groups.get(1, []))
    # 1.01 depends on 1.02 (level 0) → level 1
    assert "1.01" in level_1, "SAM.gov should be level 1"


def test_next_recommended_tasks_populated():
    tracker = ProgressTracker()
    session = make_session()
    progress = tracker.compute_progress(session)
    assert len(progress.next_recommended_tasks) <= 5
    assert len(progress.next_recommended_tasks) >= 1
