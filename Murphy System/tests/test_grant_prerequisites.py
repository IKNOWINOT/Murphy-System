"""Tests for the grant prerequisite chain."""

import pytest

from src.billing.grants import prerequisites
from src.billing.grants.models import PrereqStatus


@pytest.fixture(autouse=True)
def clear_prereq_status():
    """Clear session prereq status before each test."""
    prerequisites._SESSION_PREREQ_STATUS.clear()
    yield
    prerequisites._SESSION_PREREQ_STATUS.clear()


SESSION_ID = "test-prereq-session"


class TestGetPrerequisiteChain:
    def test_returns_list(self):
        chain = prerequisites.get_prerequisite_chain()
        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_has_expected_prereqs(self):
        chain = prerequisites.get_prerequisite_chain()
        ids = [p.prereq_id for p in chain]
        assert "ein" in ids
        assert "sam_gov" in ids
        assert "grants_gov" in ids
        assert "sbir_gov" in ids
        assert "research_gov" in ids
        assert "nist_mep" in ids

    def test_ein_is_first(self):
        chain = prerequisites.get_prerequisite_chain()
        assert chain[0].prereq_id == "ein"

    def test_order_maintained(self):
        chain = prerequisites.get_prerequisite_chain()
        ids = [p.prereq_id for p in chain]
        assert ids.index("ein") < ids.index("sam_gov")
        assert ids.index("sam_gov") < ids.index("grants_gov")

    def test_prereqs_have_verification_url(self):
        chain = prerequisites.get_prerequisite_chain()
        for p in chain:
            assert p.verification_url, f"Prereq {p.prereq_id} missing verification_url"

    def test_sam_gov_has_meaningful_blocks(self):
        chain = prerequisites.get_prerequisite_chain()
        sam = next(p for p in chain if p.prereq_id == "sam_gov")
        assert len(sam.blocks) > 0
        assert "sbir_phase1" in sam.blocks

    def test_sbir_gov_blocks_sbir(self):
        chain = prerequisites.get_prerequisite_chain()
        sbir_reg = next(p for p in chain if p.prereq_id == "sbir_gov")
        assert "sbir_phase1" in sbir_reg.blocks

    def test_estimated_days_positive(self):
        chain = prerequisites.get_prerequisite_chain()
        for p in chain:
            assert p.estimated_days >= 1


class TestCheckPrerequisiteStatus:
    def test_default_not_started(self):
        status = prerequisites.check_prerequisite_status(SESSION_ID, "ein")
        assert status == PrereqStatus.not_started

    def test_unknown_session_defaults_not_started(self):
        status = prerequisites.check_prerequisite_status("new-session", "sam_gov")
        assert status == PrereqStatus.not_started


class TestUpdatePrerequisiteStatus:
    def test_updates_status(self):
        prereq = prerequisites.update_prerequisite_status(SESSION_ID, "ein", PrereqStatus.completed)
        assert prereq.status == PrereqStatus.completed

    def test_persists_in_session(self):
        prerequisites.update_prerequisite_status(SESSION_ID, "ein", PrereqStatus.completed)
        status = prerequisites.check_prerequisite_status(SESSION_ID, "ein")
        assert status == PrereqStatus.completed

    def test_raises_for_unknown_prereq(self):
        with pytest.raises(ValueError, match="Unknown prerequisite"):
            prerequisites.update_prerequisite_status(SESSION_ID, "nonexistent_id", PrereqStatus.completed)

    def test_in_progress_status(self):
        prereq = prerequisites.update_prerequisite_status(SESSION_ID, "sam_gov", PrereqStatus.in_progress)
        assert prereq.status == PrereqStatus.in_progress

    def test_waiting_on_external(self):
        prereq = prerequisites.update_prerequisite_status(
            SESSION_ID, "grants_gov", PrereqStatus.waiting_on_external
        )
        assert prereq.status == PrereqStatus.waiting_on_external


class TestGetSessionPrereqSummary:
    def test_structure(self):
        summary = prerequisites.get_session_prereq_summary(SESSION_ID)
        assert "prerequisites" in summary
        assert "total" in summary
        assert "completed" in summary
        assert "completion_pct" in summary
        assert "ready_to_apply" in summary

    def test_zero_completed_initially(self):
        summary = prerequisites.get_session_prereq_summary(SESSION_ID)
        assert summary["completed"] == 0
        assert summary["completion_pct"] == 0.0

    def test_completion_percentage_updates(self):
        prerequisites.update_prerequisite_status(SESSION_ID, "ein", PrereqStatus.completed)
        summary = prerequisites.get_session_prereq_summary(SESSION_ID)
        assert summary["completed"] == 1
        assert summary["completion_pct"] > 0.0

    def test_all_prereqs_completed(self):
        chain = prerequisites.get_prerequisite_chain()
        for p in chain:
            prerequisites.update_prerequisite_status(SESSION_ID, p.prereq_id, PrereqStatus.completed)
        summary = prerequisites.get_session_prereq_summary(SESSION_ID)
        assert summary["completion_pct"] == 100.0

    def test_ready_to_apply_expands_with_completions(self):
        # Before any prereqs: fewer grants unlocked
        before = set(prerequisites.get_session_prereq_summary(SESSION_ID)["ready_to_apply"])

        # Complete SAM.gov
        prerequisites.update_prerequisite_status(SESSION_ID, "sam_gov", PrereqStatus.completed)
        after = set(prerequisites.get_session_prereq_summary(SESSION_ID)["ready_to_apply"])

        assert len(after) >= len(before)

    def test_prereq_list_count(self):
        summary = prerequisites.get_session_prereq_summary(SESSION_ID)
        assert summary["total"] == len(prerequisites.get_prerequisite_chain())
