"""
Tests for HITL-003 (delegation / best-recommendations mode).

Verifies that:
  * detect_delegation recognises common opt-in phrasings and rejects negations
  * IntentExtractor remains HITL-by-default (no auto-picks)
  * Explicit delegation in the request text triggers auto-resolution and
    records every pick with provenance + a [best-effort] summary tag
  * Setting Request.context['delegation'] = True is an equivalent opt-in
  * The "deliverable type" question's auto-pick uses the classifier's top
    rank when wired
  * Free-text-only candidate sets fall back gracefully
"""
from __future__ import annotations

import pytest

from src.reconciliation import (
    BEST_EFFORT_PREAMBLE,
    AmbiguityVector,
    ClarifyingQuestion,
    ClarifyingQuestionSynthesizer,
    DelegatedPick,
    DeliverableType,
    IntentClassifier,
    IntentExtractor,
    Request,
    auto_resolve_questions,
    detect_delegation,
    get_corpus,
)


# ---------------------------------------------------------------------------
# detect_delegation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "you can pick honestly",
        "your call, use your best judgment",
        "go with whatever you think is best",
        "I trust you, surprise me",
        "give me your best recommendations into a working version",
        "you choose the format",
        "make the call on the deadline",
        "pick for me",
    ],
)
def test_detect_delegation_positive(text: str) -> None:
    assert detect_delegation(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "here are some options",
        "Build me a web app for booking appointments.",
        "don't pick for me",
        "do not decide yet",
        "I'll pick the format myself",
        "I will choose the deadline",
        "never guess on production",
    ],
)
def test_detect_delegation_negative(text: str) -> None:
    assert detect_delegation(text) is False


def test_detect_delegation_negation_overrides_positive() -> None:
    """If both signals are present, negation wins (conservative bias)."""
    assert detect_delegation(
        "you can pick the format but I'll decide the deadline"
    ) is False


# ---------------------------------------------------------------------------
# auto_resolve_questions
# ---------------------------------------------------------------------------


def test_auto_resolve_skips_free_text_option() -> None:
    qs = [
        ClarifyingQuestion(
            question="Audience?",
            ambiguity_item="audience",
            candidate_answers=["Internal team", "End users", "Other (free text)"],
        )
    ]
    [pick] = auto_resolve_questions(qs)
    assert pick.chosen_answer == "Internal team"
    assert "first non-free-text" in pick.rationale


def test_auto_resolve_falls_back_when_only_free_text() -> None:
    qs = [
        ClarifyingQuestion(
            question="Anything else?",
            ambiguity_item="custom dim",
            candidate_answers=["Other (free text)"],
        )
    ]
    [pick] = auto_resolve_questions(qs)
    assert pick.chosen_answer == "Other (free text)"
    assert "fallback" in pick.rationale


def test_auto_resolve_uses_classifier_top_for_deliverable_type() -> None:
    clf = IntentClassifier(get_corpus())
    pred = clf.predict("write a bash script that backs up the db nightly")
    synth = ClarifyingQuestionSynthesizer(type_suggestions=4, max_questions=5)
    [type_q] = synth.synthesize(
        AmbiguityVector(items=["deliverable type"]), prediction=pred
    )

    [pick] = auto_resolve_questions([type_q], prediction=pred)
    assert pick.chosen_answer == pred.deliverable_type.value
    assert "classifier" in pick.rationale


# ---------------------------------------------------------------------------
# IntentExtractor end-to-end — HITL by default, CITL on delegation
# ---------------------------------------------------------------------------


_VAGUE_PROMPT = (
    "Make me a MVP web app for a highly lucrative niche that copies "
    "medvi's business model. write a launch campaign."
)


def test_intent_extractor_does_not_auto_pick_by_default() -> None:
    """Without any delegation phrase, HITL-002 protection holds."""
    [primary, *_] = IntentExtractor().extract(
        Request(text=_VAGUE_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.delegation_granted is False
    assert primary.delegated_picks == []
    assert primary.clarifying_questions, "questions still get asked"
    assert "[best-effort]" not in primary.summary


def test_intent_extractor_auto_picks_on_explicit_delegation_phrase() -> None:
    text = _VAGUE_PROMPT + " honestly you can pick — give me your best recommendations."
    [primary, *_] = IntentExtractor().extract(
        Request(text=text, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.delegation_granted is True
    assert primary.delegated_picks
    assert len(primary.delegated_picks) == len(primary.clarifying_questions)
    assert primary.summary.startswith("[best-effort]")
    # Every pick must carry provenance.
    for p in primary.delegated_picks:
        assert isinstance(p, DelegatedPick)
        assert p.rationale.startswith("auto:")
        assert p.chosen_answer  # non-empty


def test_intent_extractor_delegation_via_context_flag() -> None:
    """Setting Request.context['delegation'] = True is an equivalent opt-in."""
    req = Request(
        text=_VAGUE_PROMPT,
        deliverable_type=DeliverableType.GENERIC_TEXT,
        context={"delegation": True},
    )
    [primary, *_] = IntentExtractor().extract(req)
    assert primary.delegation_granted is True
    assert primary.delegated_picks


def test_intent_extractor_delegation_propagates_to_alternative_specs() -> None:
    # A vague request yields multiple candidate specs; delegation must
    # apply to every one of them, not just the primary.
    text = "make it nicer, you can pick"
    specs = IntentExtractor().extract(
        Request(text=text, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert len(specs) >= 2  # vague → primary + alternatives
    for s in specs:
        assert s.delegation_granted is True
        assert s.delegated_picks


def test_intent_extractor_negated_delegation_stays_hitl() -> None:
    text = _VAGUE_PROMPT + " I'll decide the format myself"
    [primary, *_] = IntentExtractor().extract(
        Request(text=text, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.delegation_granted is False
    assert primary.delegated_picks == []


def test_best_effort_preamble_is_a_non_empty_string() -> None:
    """Smoke check that the canonical preamble exists for downstream renderers."""
    assert isinstance(BEST_EFFORT_PREAMBLE, str)
    assert "Working version" in BEST_EFFORT_PREAMBLE
    assert "override" in BEST_EFFORT_PREAMBLE.lower()
