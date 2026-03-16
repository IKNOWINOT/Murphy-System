"""
Unit tests for authority gate
"""

import pytest
from src.state_machine import State, QuestionType, Hypothesis, VerifiedFacts
from src.authority_gate import InvariantChecker, AuthorityGate, MurphyDefense


def test_invariant_checker_pass():
    """Test invariant checker with valid inputs"""
    checker = InvariantChecker(min_confidence=0.80)

    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.85,
        unknowns=[],
        intent="lookup",
        parameters={}
    )

    facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles"},
        sources=["db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01"
    )

    passed, violations = checker.check(hypothesis, facts)
    assert passed == True
    assert len(violations) == 0


def test_invariant_checker_fail_confidence():
    """Test invariant checker with low confidence"""
    checker = InvariantChecker(min_confidence=0.80)

    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.60,  # Below threshold
        unknowns=[],
        intent="lookup",
        parameters={}
    )

    facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles"},
        sources=["db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01"
    )

    passed, violations = checker.check(hypothesis, facts)
    assert passed == False
    assert any("Confidence" in v for v in violations)


def test_authority_gate_proceed():
    """Test authority gate proceeding"""
    gate = AuthorityGate(min_confidence=0.80)

    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.90,
        unknowns=[],
        intent="lookup",
        parameters={}
    )

    facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles"},
        sources=["db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01"
    )

    state, reasoning = gate.evaluate(hypothesis, facts)
    assert state.value == State.PROCEED.value


def test_authority_gate_clarify():
    """Test authority gate requesting clarification"""
    gate = AuthorityGate(min_confidence=0.80)

    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.60,  # Low confidence
        unknowns=["revision"],
        intent="lookup",
        parameters={}
    )

    facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles"},
        sources=["db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01"
    )

    state, reasoning = gate.evaluate(hypothesis, facts)
    assert state.value == State.CLARIFY.value


def test_murphy_defense_bound_uncertainty():
    """Test Murphy defense uncertainty bounding"""
    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.99,  # Very high
        unknowns=[],
        intent="lookup",
        parameters={}
    )

    bounded = MurphyDefense.bound_uncertainty(hypothesis)
    assert bounded.confidence <= 0.95


def test_murphy_defense_verify_before_action():
    """Test Murphy defense verification check"""
    valid_facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles"},
        sources=["db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01"
    )

    invalid_facts = VerifiedFacts(
        entity="ISO 26262",
        facts={},
        sources=[],
        verified=False,
        verification_method="none",
        timestamp="2024-01-01"
    )

    assert MurphyDefense.verify_before_action(valid_facts) == True
    assert MurphyDefense.verify_before_action(invalid_facts) == False
