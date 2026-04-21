# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for WaitStateHandler."""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.wait_state_handler import WaitStateHandler
from src.platform_onboarding.onboarding_session import OnboardingSession


def make_session() -> OnboardingSession:
    return OnboardingSession.create_new("test-account")


def test_mark_waiting_sets_state():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.01", session)
    assert session.get_task_state("1.01") == "waiting_on_external"


def test_mark_waiting_returns_expected_date_for_sam_gov():
    """SAM.gov has external_wait_days=10."""
    handler = WaitStateHandler()
    session = make_session()
    expected = handler.mark_waiting("1.01", session)
    delta = expected - datetime.now(timezone.utc).replace(tzinfo=None)
    assert 9 <= delta.days <= 10, f"Expected ~10 days, got {delta.days}"


def test_mark_waiting_stores_in_wait_states():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.01", session)
    assert "1.01" in session.wait_states


def test_get_waiting_tasks_returns_waiting():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.01", session)
    waiting = handler.get_waiting_tasks(session)
    assert any(w["task_id"] == "1.01" for w in waiting)


def test_get_waiting_tasks_empty_initially():
    handler = WaitStateHandler()
    session = make_session()
    waiting = handler.get_waiting_tasks(session)
    assert waiting == []


def test_check_completion_false_for_10day_wait():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.01", session)
    # Immediately after marking, not complete yet
    assert not handler.check_completion("1.01", session)


def test_check_completion_true_for_overdue():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.01", session)
    # Manually set expected to the past
    session.wait_states["1.01"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    assert handler.check_completion("1.01", session)


def test_advance_to_unblocked_marks_completed():
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.02", session)
    # Manually complete
    handler.advance_to_unblocked("1.02", session)
    assert session.get_task_state("1.02") == "completed"


def test_advance_to_unblocked_returns_unlocked_tasks():
    """Completing 1.02 (EIN) should unlock 1.01 (SAM.gov) if all other deps satisfied."""
    handler = WaitStateHandler()
    session = make_session()
    handler.mark_waiting("1.02", session)
    newly_unblocked = handler.advance_to_unblocked("1.02", session)
    # 1.01 depends only on 1.02, so it should now be unblocked
    assert "1.01" in newly_unblocked


def test_cascade_unlock_direct_dependents():
    handler = WaitStateHandler()
    session = make_session()
    session.set_task_state("1.02", "completed")
    unlocked = handler.cascade_unlock("1.02", session)
    assert "1.01" in unlocked


def test_cascade_unlock_does_not_return_already_started():
    handler = WaitStateHandler()
    session = make_session()
    session.set_task_state("1.02", "completed")
    session.set_task_state("1.01", "in_progress")
    unlocked = handler.cascade_unlock("1.02", session)
    assert "1.01" not in unlocked


def test_wait_days_for_no_wait_task():
    """API key tasks have no external wait."""
    handler = WaitStateHandler()
    session = make_session()
    expected = handler.mark_waiting("5.01", session)
    delta = expected - datetime.now(timezone.utc).replace(tzinfo=None)
    # No wait days → expected is essentially now (within 1 second)
    assert abs(delta.total_seconds()) < 1
