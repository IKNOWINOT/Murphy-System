# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from src.billing.grants.submission.submission_tracker import SubmissionTracker
from src.billing.grants.submission.models import SubmissionStatus, StatusChange


@pytest.fixture
def tracker():
    return SubmissionTracker()


def test_create_returns_submission_status(tracker):
    status = tracker.create("pkg-001", "grants_gov")
    assert isinstance(status, SubmissionStatus)


def test_initial_status_is_generated(tracker):
    status = tracker.create("pkg-002", "grants_gov")
    assert status.status == "generated"


def test_custom_initial_status(tracker):
    status = tracker.create("pkg-003", "grants_gov", initial_status="ready")
    assert status.status == "ready"


def test_get_returns_created_status(tracker):
    tracker.create("pkg-004", "grants_gov")
    status = tracker.get("pkg-004")
    assert status is not None
    assert status.submission_id == "pkg-004"


def test_update_status_changes_status(tracker):
    tracker.create("pkg-005", "grants_gov")
    updated = tracker.update_status("pkg-005", "submitted")
    assert updated.status == "submitted"


def test_update_status_adds_to_history(tracker):
    tracker.create("pkg-006", "grants_gov")
    tracker.update_status("pkg-006", "submitted")
    status = tracker.get("pkg-006")
    assert len(status.history) == 1
    assert status.history[0].old_status == "generated"
    assert status.history[0].new_status == "submitted"


def test_mark_submitted_sets_submitted_at(tracker):
    tracker.create("pkg-007", "grants_gov")
    status = tracker.mark_submitted("pkg-007", "CONF-12345")
    assert status.submitted_at is not None
    assert status.confirmation_number == "CONF-12345"


def test_mark_submitted_sets_status(tracker):
    tracker.create("pkg-008", "grants_gov")
    status = tracker.mark_submitted("pkg-008")
    assert status.status == "submitted"


def test_lifecycle_generated_to_confirmed(tracker):
    tracker.create("pkg-009", "grants_gov")
    tracker.update_status("pkg-009", "submitted")
    tracker.update_status("pkg-009", "confirmed", notes="Agency confirmed receipt")
    status = tracker.get("pkg-009")
    assert status.status == "confirmed"
    assert len(status.history) == 2


def test_get_nonexistent_returns_none(tracker):
    result = tracker.get("nonexistent-id")
    assert result is None
