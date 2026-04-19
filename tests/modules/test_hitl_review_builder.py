"""Tests for HITL Review Builder module (PATCH-010)."""

import sys
import os
import pytest

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"),
)

from hitl_review_builder import (
    HITLReviewBuilder,
    HITLReviewPayload,
    ChangeCategory,
    ReviewPriority,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def builder():
    """Return a fresh HITLReviewBuilder with no external integrations."""
    return HITLReviewBuilder()


# ------------------------------------------------------------------
# Build review
# ------------------------------------------------------------------

class TestBuildReview:
    def test_build_basic_review(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.BUGFIX.value,
            problem_description="Fix null pointer in user auth flow",
            rationale_why="Users reported crashes on login",
            rationale_approach="Added null check before session lookup",
            priority=ReviewPriority.HIGH.value,
        )
        assert review.review_id.startswith("hitl-review-")
        assert review.change_category == "bugfix"
        assert review.priority == "high"
        assert review.status == "pending"
        assert review.problem_summary  # Should be non-empty
        assert review.rationale_why == "Users reported crashes on login"

    def test_review_anonymises_emails(self, builder):
        review = builder.build_review(
            problem_description="User alice@example.com reported a bug in acc-12345",
        )
        assert "alice@example.com" not in review.problem_summary
        assert "[REDACTED_EMAIL]" in review.problem_summary
        assert "acc-12345" not in review.problem_summary
        assert "[REDACTED_ACCOUNT]" in review.problem_summary

    def test_review_anonymises_uuids(self, builder):
        review = builder.build_review(
            problem_description="Error in transaction 550e8400-e29b-41d4-a716-446655440000",
        )
        assert "550e8400" not in review.problem_summary
        assert "[REDACTED_ID]" in review.problem_summary

    def test_review_has_edge_cases(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.SOURCE_CODE.value,
            problem_description="Refactor database queries",
        )
        assert len(review.edge_cases) > 0

    def test_review_has_failure_modes(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.SOURCE_CODE.value,
            problem_description="Refactor database queries",
            artifact_context={"change_category": "source_code"},
        )
        assert len(review.failure_modes) > 0
        assert any("Regression" in m for m in review.failure_modes)

    def test_review_has_best_practice_ordering(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.UPDATE.value,
            problem_description="Update dependency versions",
        )
        assert len(review.best_practice_ordering) > 0

    def test_review_has_mss_context(self, builder):
        review = builder.build_review(
            problem_description="Test MSS context",
        )
        assert review.mss_resolution_level == "RM3"
        assert review.mss_context

    def test_review_to_dict(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.CUSTOMER_DELIVERABLE.value,
            problem_description="Generate client report",
        )
        d = review.to_dict()
        assert "review_id" in d
        assert "problem_summary" in d
        assert "edge_cases" in d
        assert "failure_modes" in d
        assert "best_practice_ordering" in d
        assert isinstance(d["edge_cases"], list)

    def test_review_customer_deliverable_failure_modes(self, builder):
        review = builder.build_review(
            change_category=ChangeCategory.CUSTOMER_DELIVERABLE.value,
            problem_description="Deliver report",
            artifact_context={"change_category": "customer_deliverable"},
        )
        assert any("mismatch" in m.lower() or "leakage" in m.lower()
                    for m in review.failure_modes)


# ------------------------------------------------------------------
# List pending
# ------------------------------------------------------------------

class TestListPending:
    def test_list_pending_empty(self, builder):
        assert builder.list_pending() == []

    def test_list_pending_returns_only_pending(self, builder):
        r1 = builder.build_review(problem_description="Test 1")
        r2 = builder.build_review(problem_description="Test 2")
        builder.decide(r1.review_id, "approve", "admin1")
        pending = builder.list_pending()
        assert len(pending) == 1
        assert pending[0].review_id == r2.review_id


# ------------------------------------------------------------------
# Decide
# ------------------------------------------------------------------

class TestDecide:
    def test_approve_review(self, builder):
        review = builder.build_review(problem_description="Test approval")
        result = builder.decide(review.review_id, "approve", "founder1", "Looks good")
        assert result is not None
        assert result.status == "approved"
        assert result.decision == "approve"
        assert result.decided_by == "founder1"
        assert result.decision_reason == "Looks good"
        assert result.decided_at

    def test_reject_review(self, builder):
        review = builder.build_review(problem_description="Test rejection")
        result = builder.decide(review.review_id, "reject", "admin1", "Needs revision")
        assert result is not None
        assert result.status == "rejected"
        assert result.decision == "reject"

    def test_decide_nonexistent_review(self, builder):
        result = builder.decide("nonexistent", "approve", "admin1")
        assert result is None

    def test_cannot_decide_already_decided(self, builder):
        review = builder.build_review(problem_description="Test double decide")
        builder.decide(review.review_id, "approve", "admin1")
        result = builder.decide(review.review_id, "reject", "admin2")
        assert result is not None
        assert result.status == "approved"  # Still approved from first decision


# ------------------------------------------------------------------
# Get review
# ------------------------------------------------------------------

class TestGetReview:
    def test_get_review(self, builder):
        review = builder.build_review(problem_description="Test get")
        fetched = builder.get_review(review.review_id)
        assert fetched is not None
        assert fetched.review_id == review.review_id

    def test_get_nonexistent_review(self, builder):
        assert builder.get_review("nonexistent") is None


# ------------------------------------------------------------------
# Change categories coverage
# ------------------------------------------------------------------

class TestAllCategories:
    @pytest.mark.parametrize("category", [c.value for c in ChangeCategory])
    def test_build_review_for_each_category(self, builder, category):
        review = builder.build_review(
            change_category=category,
            problem_description=f"Test for {category}",
        )
        assert review.change_category == category
        assert review.status == "pending"
