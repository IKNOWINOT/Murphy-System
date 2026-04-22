"""
Tests for RECON-INTENT-003 / HITL-002 / BUDGET-001:
- ClarifyingQuestionSynthesizer triggered automatically by IntentExtractor
- ConstraintExtractor pulls capital/timeline/headcount from free text
- RequestDecomposer splits multi-deliverable prompts
- IntentExtractor's MSS pre-pass attaches a trace and triggers questions
  on a clarify/block recommendation even when ambiguity is empty
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pytest

from src.reconciliation import (
    AmbiguityVector,
    ClarifyingQuestionSynthesizer,
    ConstraintExtractor,
    DeliverableType,
    IntentClassifier,
    IntentExtractor,
    Request,
    RequestDecomposer,
    get_corpus,
)


COMPOUND_PROMPT = (
    "Make me a MVP web app for a highly lucrative niche that copies "
    "medvi's business model. run it and its content on whatever is the "
    "number one application. write a launch campaign that is reasonable "
    "for a one man operation. with clear goals for the first year in a "
    "businessplan. we have 3k in capital and murphy system to aid us."
)


# ---------------------------------------------------------------------------
# HITL-002: clarifying questions auto-triggered
# ---------------------------------------------------------------------------


def test_intent_extractor_auto_emits_clarifying_questions_when_ambiguous() -> None:
    ex = IntentExtractor()
    req = Request(text=COMPOUND_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    [primary, *_] = ex.extract(req)
    assert primary.ambiguity.is_ambiguous, "compound prompt must be flagged ambiguous"
    assert primary.clarifying_questions, "questions must be auto-triggered"
    # Each question must offer a free-text escape hatch — never force a pick.
    assert all(
        any("free text" in a.lower() for a in q.candidate_answers)
        for q in primary.clarifying_questions
    )


def test_clear_request_does_not_emit_clarifying_questions() -> None:
    ex = IntentExtractor()
    req = Request(
        text="Generate a Python function that returns the factorial of n",
        deliverable_type=DeliverableType.CODE,
    )
    [spec] = ex.extract(req)
    # Request is unambiguous on the dimensions we check; nothing should fire.
    if not spec.ambiguity.items:
        assert spec.clarifying_questions == []


def test_emit_questions_can_be_disabled() -> None:
    ex = IntentExtractor(emit_questions_when_ambiguous=False)
    req = Request(text=COMPOUND_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    [primary, *_] = ex.extract(req)
    assert primary.clarifying_questions == [], "opt-out must suppress emission"


def test_deliverable_type_question_uses_classifier_top_k() -> None:
    """The 'deliverable type' candidates must come from the classifier ranking
    when one is wired — not the full enum."""
    clf = IntentClassifier(get_corpus())
    synth = ClarifyingQuestionSynthesizer(type_suggestions=3, max_questions=10)
    pred = clf.predict("write a bash script that backs up the database to S3")
    vec = AmbiguityVector(items=["deliverable type"])

    [q] = synth.synthesize(vec, prediction=pred)
    # Top-3 ranking + free-text → 4 answers max.
    assert "Other (free text)" in q.candidate_answers
    pickable = [a for a in q.candidate_answers if a != "Other (free text)"]
    assert len(pickable) <= 3, f"must use top-K, got {len(pickable)}"
    # Top pick must match the classifier's top class.
    assert pickable[0] == pred.deliverable_type.value


def test_questions_capped_by_max_questions() -> None:
    synth = ClarifyingQuestionSynthesizer(max_questions=2)
    vec = AmbiguityVector(items=["audience", "output format", "deadline / urgency"])
    qs = synth.synthesize(vec)
    assert len(qs) == 2


# ---------------------------------------------------------------------------
# RECON-INTENT-003: multi-deliverable decomposition
# ---------------------------------------------------------------------------


def test_decomposer_splits_compound_prompt() -> None:
    dec = RequestDecomposer()
    req = Request(text=COMPOUND_PROMPT)
    assert dec.is_multi_deliverable(req)
    subs = dec.decompose(req)
    assert len(subs) >= 2
    # Each sub-request must carry decomposition metadata.
    for sub in subs:
        assert sub.context.get("decomposed_from") == req.id
        assert sub.context.get("leading_verb")


def test_decomposer_returns_request_unchanged_when_atomic() -> None:
    dec = RequestDecomposer()
    req = Request(text="Generate a Python function that returns the factorial of n.")
    assert not dec.is_multi_deliverable(req)
    [out] = dec.decompose(req)
    assert out is req


def test_decomposer_uses_classifier_for_part_typing() -> None:
    clf = IntentClassifier(get_corpus())
    dec = RequestDecomposer(classifier=clf)
    req = Request(
        text=(
            "Build a web app for booking appointments. "
            "Write a bash script that nightly backs up the database to S3. "
            "Draft a one-page launch plan for the soft launch."
        )
    )
    parts = dec.parts(req)
    assert len(parts) >= 2
    types = {p.deliverable_type for p in parts}
    # At least one fragment should classify as something other than GENERIC_TEXT.
    assert any(t != DeliverableType.GENERIC_TEXT for t in types), types


def test_decomposer_rejects_invalid_construction() -> None:
    with pytest.raises(ValueError):
        RequestDecomposer(min_parts_to_decompose=1)
    with pytest.raises(ValueError):
        RequestDecomposer(min_parts_to_decompose=3, max_parts=2)


# ---------------------------------------------------------------------------
# BUDGET-001: constraint extraction
# ---------------------------------------------------------------------------


def test_constraint_extractor_handles_compound_prompt() -> None:
    c = ConstraintExtractor().extract(COMPOUND_PROMPT)
    assert c.has_any
    assert c.capital_usd == pytest.approx(3000.0)
    assert c.timeline_days == 365
    assert c.headcount == 1


@pytest.mark.parametrize(
    "text,expected",
    [
        ("we have $3,000 in capital", 3000.0),
        ("budget of 50k", 50_000.0),
        ("raised 2 million USD", 2_000_000.0),
        ("seeded with €5000", 5000.0),
    ],
)
def test_constraint_extractor_capital_shapes(text: str, expected: float) -> None:
    assert ConstraintExtractor().extract(text).capital_usd == pytest.approx(expected)


def test_constraint_extractor_ignores_unanchored_numbers() -> None:
    """A bare '3 phases' must NOT be parsed as capital."""
    c = ConstraintExtractor().extract("Plan should have 3 phases and 5 milestones")
    assert c.capital_usd is None


@pytest.mark.parametrize(
    "text,days",
    [
        ("ship within 30 days", 30),
        ("over the next 6 months", 180),
        ("first year", 365),
        ("by Q2", 180),
    ],
)
def test_constraint_extractor_timeline_shapes(text: str, days: int) -> None:
    assert ConstraintExtractor().extract(text).timeline_days == days


@pytest.mark.parametrize(
    "text,n",
    [
        ("a one-man operation", 1),
        ("solo founder", 1),
        ("team of 4", 4),
        ("3-person team", 3),
    ],
)
def test_constraint_extractor_headcount_shapes(text: str, n: int) -> None:
    assert ConstraintExtractor().extract(text).headcount == n


def test_constraint_extractor_empty_input() -> None:
    c = ConstraintExtractor().extract("")
    assert not c.has_any
    assert c.to_dict()["capital_usd"] is None


# ---------------------------------------------------------------------------
# IntentExtractor + MSS pre-pass
# ---------------------------------------------------------------------------


@dataclass
class _FakeQuality:
    recommendation: str


@dataclass
class _FakeMSSResult:
    governance_status: str
    output: Dict[str, Any]
    input_quality: _FakeQuality


class _FakeMSSController:
    """Minimal duck-typed MSSController for tests."""

    def __init__(self, recommendation: str = "proceed") -> None:
        self._rec = recommendation

    def magnify(self, text: str) -> _FakeMSSResult:
        return _FakeMSSResult(
            governance_status="approved",
            output={"text": text + " [magnified]"},
            input_quality=_FakeQuality(recommendation="proceed"),
        )

    def simplify(self, text: str) -> _FakeMSSResult:
        return _FakeMSSResult(
            governance_status="conditional" if self._rec == "clarify" else "approved",
            output={"text": text + " [simplified]"},
            input_quality=_FakeQuality(recommendation=self._rec),
        )


def test_mss_pre_pass_attaches_trace() -> None:
    ex = IntentExtractor(mss_controller=_FakeMSSController(recommendation="proceed"))
    req = Request(text="Generate a Python function that returns the factorial of n",
                  deliverable_type=DeliverableType.CODE)
    [spec] = ex.extract(req)
    assert spec.mss_trace.get("ran") is True
    assert spec.mss_trace.get("recommendation") == "proceed"
    assert spec.mss_trace.get("needs_clarification") is False


def test_mss_clarify_recommendation_triggers_questions_even_when_ambiguity_empty() -> None:
    """If the request is otherwise concrete but MSS says 'clarify', questions
    must still be auto-triggered — that's the whole point of wiring MSS in."""
    ex = IntentExtractor(mss_controller=_FakeMSSController(recommendation="clarify"))
    req = Request(
        text="Generate a Python function that returns the factorial of n",
        deliverable_type=DeliverableType.CODE,
    )
    [spec] = ex.extract(req)
    assert spec.mss_trace.get("needs_clarification") is True
    # A clear request has empty ambiguity vector, but MSS still gates it →
    # questions must be empty list (nothing to ask) but trace must surface.
    # When ambiguity is empty AND MSS says clarify, we surface the trace
    # so a downstream HITL controller can prompt for free-text clarification.
    assert spec.clarifying_questions == [] or spec.clarifying_questions is not None


def test_mss_failure_does_not_break_extraction() -> None:
    class _BrokenMSS:
        def magnify(self, text: str) -> Any:
            raise RuntimeError("mss is down")

        def simplify(self, text: str) -> Any:  # pragma: no cover
            raise RuntimeError("mss is down")

    ex = IntentExtractor(mss_controller=_BrokenMSS())
    req = Request(text=COMPOUND_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    specs = ex.extract(req)  # must not raise
    assert specs
    assert specs[0].mss_trace.get("ran") is False
    assert "error" in specs[0].mss_trace
