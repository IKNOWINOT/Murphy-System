"""
Unit tests for state machine components
"""

import pytest
from src.state_machine import State, QuestionType, Hypothesis, VerifiedFacts


def test_hypothesis_confidence():
    """Test hypothesis confidence checking"""
    hypothesis = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.85,
        unknowns=[],
        intent="lookup standard",
        parameters={}
    )

    assert hypothesis.is_confident(0.80) == True
    assert hypothesis.is_confident(0.90) == False


def test_hypothesis_unknowns():
    """Test hypothesis unknowns checking"""
    hypothesis_with_unknowns = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.85,
        unknowns=["latest revision"],
        intent="lookup standard",
        parameters={}
    )

    hypothesis_without_unknowns = Hypothesis(
        question_type=QuestionType.FACTUAL_LOOKUP,
        entities=["ISO 26262"],
        confidence=0.85,
        unknowns=[],
        intent="lookup standard",
        parameters={}
    )

    assert hypothesis_with_unknowns.has_unknowns() == True
    assert hypothesis_without_unknowns.has_unknowns() == False


def test_verified_facts_validity():
    """Test verified facts validation"""
    valid_facts = VerifiedFacts(
        entity="ISO 26262",
        facts={"title": "Road vehicles", "revision": "2018"},
        sources=["standards_db"],
        verified=True,
        verification_method="lookup",
        timestamp="2024-01-01T00:00:00"
    )

    invalid_facts = VerifiedFacts(
        entity="ISO 26262",
        facts={},
        sources=[],
        verified=False,
        verification_method="none",
        timestamp="2024-01-01T00:00:00"
    )

    assert valid_facts.is_valid() == True
    assert invalid_facts.is_valid() == False


def test_state_enum():
    """Test state enum values"""
    assert State.HALT.value == 0
    assert State.CLARIFY.value == 1
    assert State.PROCEED.value == 2


def test_question_type_enum():
    """Test question type enum"""
    assert QuestionType.FACTUAL_LOOKUP.value == "factual_lookup"
    assert QuestionType.CALCULATION.value == "calculation"
