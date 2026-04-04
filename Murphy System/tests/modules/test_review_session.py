"""
Tests for ReviewSessionManager.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
from src.billing.grants.form_filler.review_session import ReviewSessionManager, FilledField


@pytest.fixture
def manager():
    return ReviewSessionManager()


def make_filled_fields():
    return [
        FilledField(field_id="f1", value="hello", confidence=0.95, status="auto_filled", source="saved_form_data"),
        FilledField(field_id="f2", value="world", confidence=0.7, status="needs_review", source="murphy_profile"),
        FilledField(field_id="f3", value=None, confidence=0.0, status="blocked_human_required", source="llm_generated"),
    ]


def test_create_review_session(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    assert review.review_id is not None
    assert review.status == "draft"
    assert len(review.filled_fields) == 3


def test_start_review(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    started = manager.start_review(review.review_id, "reviewer1")
    assert started.status == "in_review"
    assert started.reviewer_id == "reviewer1"


def test_approve_review(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    manager.start_review(review.review_id, "reviewer1")
    approved = manager.approve_review(review.review_id, "reviewer1", "Looks good")
    assert approved.status == "approved"
    assert approved.approved_at is not None


def test_reject_review(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    manager.start_review(review.review_id, "reviewer1")
    rejected = manager.reject_review(review.review_id, "reviewer1", "Needs more detail")
    assert rejected.status == "draft"


def test_edit_field_marks_human_edited(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    manager.start_review(review.review_id, "reviewer1")
    edited = manager.edit_field(review.review_id, "f1", "updated value", "reviewer1")
    assert edited is not None
    assert edited.edited_by_human is True
    assert edited.value == "updated value"


def test_review_summary_counts(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    summary = manager.get_review_summary(review.review_id)
    assert "auto_filled" in summary
    assert "needs_review" in summary
    assert "blocked_human_required" in summary


def test_get_review_for_application(manager):
    review = manager.create_review("s1", "app1", "sbir_phase1", make_filled_fields())
    found = manager.get_review_for_application("app1")
    assert found is not None
    assert found.review_id == review.review_id
