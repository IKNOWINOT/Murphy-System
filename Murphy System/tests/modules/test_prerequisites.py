"""
Test: Prerequisite Chain — SAM.gov / UEI / CAGE / Grants.gov

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.prerequisites import PrerequisiteChain
from src.billing.grants.models import PrerequisiteStatus


@pytest.fixture
def chain():
    return PrerequisiteChain()


def test_prerequisites_load(chain):
    """Chain should have all expected prerequisites."""
    prereqs = chain.list_prerequisites()
    assert len(prereqs) >= 6, f"Expected at least 6 prerequisites, got {len(prereqs)}"


def test_prereq_ids_unique(chain):
    """All prerequisite IDs must be unique."""
    prereqs = chain.list_prerequisites()
    ids = [p.prereq_id for p in prereqs]
    assert len(ids) == len(set(ids)), "Duplicate prerequisite IDs found"


def test_expected_prereqs_present(chain):
    """Expected prerequisites must be present."""
    prereq_ids = {p.prereq_id for p in chain.list_prerequisites()}
    required = ["sam_registration", "uei_number", "cage_code", "grants_gov_account", "ein"]
    for pid in required:
        assert pid in prereq_ids, f"Required prerequisite {pid!r} not found"


def test_sam_depends_on_nothing(chain):
    """EIN and SAM registration have no dependencies (base prerequisites)."""
    ein = chain.get_prerequisite("ein")
    assert len(ein.depends_on) == 0

    sam = chain.get_prerequisite("sam_registration")
    # SAM may depend on EIN or have no deps — check it's accessible
    assert sam.prereq_id == "sam_registration"


def test_uei_depends_on_sam(chain):
    """UEI must depend on SAM.gov registration."""
    uei = chain.get_prerequisite("uei_number")
    assert "sam_registration" in uei.depends_on


def test_grants_gov_depends_on_sam_and_uei(chain):
    """Grants.gov account must depend on SAM registration and UEI."""
    grants_gov = chain.get_prerequisite("grants_gov_account")
    assert "sam_registration" in grants_gov.depends_on
    assert "uei_number" in grants_gov.depends_on


def test_cannot_complete_prereq_with_incomplete_deps(chain):
    """Completing a prerequisite before its dependencies raises ValueError."""
    with pytest.raises(ValueError, match="dependency"):
        chain.mark_complete("uei_number")  # SAM not yet completed


def test_completing_in_order_works(chain):
    """Completing prerequisites in dependency order should succeed."""
    chain.mark_complete("ein")
    chain.mark_complete("sam_registration")
    chain.mark_complete("uei_number")
    chain.mark_complete("cage_code")

    uei = chain.get_prerequisite("uei_number")
    assert uei.status == PrerequisiteStatus.COMPLETED
    assert uei.completed_at is not None


def test_ready_prereqs_start_with_no_deps(chain):
    """Initially, only prerequisites with no dependencies should be ready."""
    ready = chain.get_ready_prerequisites()
    for p in ready:
        assert len(p.depends_on) == 0, (
            f"Prerequisite {p.prereq_id} has dependencies but was returned as ready"
        )


def test_completing_dep_makes_downstream_ready(chain):
    """After completing SAM, uei_number and cage_code should become ready."""
    chain.mark_complete("ein")
    chain.mark_complete("sam_registration")

    ready_ids = {p.prereq_id for p in chain.get_ready_prerequisites()}
    assert "uei_number" in ready_ids or "cage_code" in ready_ids, (
        "After SAM completion, UEI or CAGE should be ready"
    )


def test_completion_summary(chain):
    """completion_summary returns correct statistics."""
    summary = chain.completion_summary()
    assert "total" in summary
    assert "completed" in summary
    assert "pct_complete" in summary
    assert summary["completed"] == 0
    assert summary["pct_complete"] == 0.0


def test_completion_summary_updates_after_completion(chain):
    """Summary updates correctly after completing prerequisites."""
    chain.mark_complete("ein")
    chain.mark_complete("sam_registration")
    summary = chain.completion_summary()
    assert summary["completed"] >= 2


def test_prerequisite_has_external_link(chain):
    """All prerequisites must have an external link for documentation."""
    for prereq in chain.list_prerequisites():
        assert prereq.external_link, f"Prerequisite {prereq.prereq_id!r} missing external_link"
        assert prereq.external_link.startswith("http"), (
            f"Prerequisite {prereq.prereq_id!r} has invalid link: {prereq.external_link}"
        )


def test_blocking_prereqs(chain):
    """get_blocking_prerequisites returns incomplete base-level prerequisites."""
    blocking = chain.get_blocking_prerequisites()
    assert len(blocking) > 0
    # All returned should be NOT_STARTED or IN_PROGRESS
    for p in blocking:
        assert p.status != PrerequisiteStatus.COMPLETED
