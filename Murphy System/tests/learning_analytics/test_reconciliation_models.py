"""
Tests for the reconciliation models — basic shape, validation, and
property-driven invariants.
"""

from __future__ import annotations

import pytest

from src.reconciliation import (
    AcceptanceCriterion,
    AmbiguityVector,
    CriterionKind,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    LoopBudget,
    LoopOutcome,
    LoopTerminationReason,
    Patch,
    PatchKind,
    ReconciliationScore,
    Request,
)


def test_request_requires_non_empty_text() -> None:
    with pytest.raises(Exception):
        Request(text="")


def test_acceptance_criterion_requires_rubric_for_llm_judge() -> None:
    with pytest.raises(Exception):
        AcceptanceCriterion(
            description="needs rubric",
            kind=CriterionKind.LLM_RUBRIC,
            rubric=None,
        )


def test_acceptance_criterion_standard_kind_no_rubric_required() -> None:
    crit = AcceptanceCriterion(
        description="standard",
        kind=CriterionKind.STANDARD,
        check_spec={"kind": "regex", "pattern": "x"},
    )
    assert crit.rubric is None


def test_ambiguity_vector_is_ambiguous_property() -> None:
    assert not AmbiguityVector(items=[]).is_ambiguous
    assert AmbiguityVector(items=["scope"]).is_ambiguous


def test_reconciliation_score_acceptable_requires_hard_pass_and_threshold() -> None:
    score = ReconciliationScore(
        deliverable_id="d", intent_id="i", soft_score=0.9, hard_pass=True
    )
    assert score.acceptable
    assert not ReconciliationScore(
        deliverable_id="d", intent_id="i", soft_score=0.95, hard_pass=False
    ).acceptable
    assert not ReconciliationScore(
        deliverable_id="d", intent_id="i", soft_score=0.84, hard_pass=True
    ).acceptable


def test_loop_budget_validates_bounds() -> None:
    with pytest.raises(Exception):
        LoopBudget(max_iterations=0)
    with pytest.raises(Exception):
        LoopBudget(max_wallclock_seconds=0)


def test_loop_outcome_accepted_property() -> None:
    score = ReconciliationScore(
        deliverable_id="d", intent_id="i", soft_score=0.9, hard_pass=True
    )
    outcome = LoopOutcome(
        request_id="r",
        intent_id="i",
        deliverable_id="d",
        termination_reason=LoopTerminationReason.PASSED,
        final_score=score,
    )
    assert outcome.accepted

    outcome.termination_reason = LoopTerminationReason.MAX_ITERATIONS
    assert not outcome.accepted


def test_patch_defaults_are_safe() -> None:
    p = Patch(kind=PatchKind.PROMPT_REWRITE, target="x")
    assert not p.requires_human_review
    assert p.payload == {}


def test_diagnosis_severity_enum_round_trip() -> None:
    d = Diagnosis(severity=DiagnosisSeverity.BLOCKER, summary="x")
    assert d.severity == DiagnosisSeverity.BLOCKER


def test_request_default_deliverable_type() -> None:
    r = Request(text="hello world")
    assert r.deliverable_type == DeliverableType.GENERIC_TEXT


def test_intent_spec_round_trip_via_dict() -> None:
    spec = IntentSpec(
        request_id="r",
        summary="s",
        deliverable_type=DeliverableType.DOCUMENT,
        confidence=0.7,
    )
    data = spec.model_dump()
    rebuilt = IntentSpec(**data)
    assert rebuilt == spec


def test_deliverable_accepts_dict_content() -> None:
    d = Deliverable(
        request_id="r",
        deliverable_type=DeliverableType.MAILBOX_PROVISIONING,
        content={"accounts": []},
    )
    assert isinstance(d.content, dict)
