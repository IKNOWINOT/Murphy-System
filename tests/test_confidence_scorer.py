"""
Tests for ConfidenceScorer.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
from src.billing.grants.form_filler.confidence_scorer import ConfidenceScorer, TIER_AUTO, TIER_REVIEW, TIER_BLOCKED
from src.billing.grants.form_filler.review_session import FormField, FormDefinition, FormSection


@pytest.fixture
def scorer():
    return ConfidenceScorer()


def make_field(field_id="test_field", label="Test Field", field_type="text", legal_cert=False, data_source_hint="company_info"):
    return FormField(field_id=field_id, label=label, field_type=field_type, legal_certification=legal_cert, data_source_hint=data_source_hint, section_id="default")


def test_saved_form_data_high_confidence(scorer):
    field = make_field()
    conf, status = scorer.score_field(field, "Acme Corp", "saved_form_data", 0.95)
    assert conf >= 0.9
    assert status == TIER_AUTO


def test_llm_generated_medium_confidence(scorer):
    field = make_field(field_type="textarea")
    conf, status = scorer.score_field(field, "Some generated text", "llm_generated", 0.6)
    assert conf < 0.9
    assert status in [TIER_REVIEW, TIER_BLOCKED]


def test_legal_cert_always_blocked(scorer):
    field = make_field(legal_cert=True)
    conf, status = scorer.score_field(field, "Anything", "saved_form_data", 1.0)
    assert status == TIER_BLOCKED
    assert conf == 0.0


def test_empty_value_blocked(scorer):
    field = make_field()
    conf, status = scorer.score_field(field, None, "saved_form_data", 0.95)
    assert status == TIER_BLOCKED
    conf2, status2 = scorer.score_field(field, "", "saved_form_data", 0.95)
    assert status2 == TIER_BLOCKED


def test_murphy_profile_review_tier(scorer):
    field = make_field()
    conf, status = scorer.score_field(field, "Profile Value", "murphy_profile", 0.75)
    assert status in [TIER_REVIEW, TIER_AUTO]


def test_score_all_fields(scorer):
    fields = [
        FormField(field_id="f1", label="F1", field_type="text", section_id="d"),
        FormField(field_id="f2", label="F2", field_type="text", legal_certification=True, section_id="d"),
    ]
    form = FormDefinition(
        form_id="t", form_name="T", grant_program_id="t",
        fields=fields,
        sections=[FormSection(section_id="d", title="D")]
    )
    mapped = {"f1": {"value": "hello", "source": "saved_form_data", "confidence": 0.95}}
    result = scorer.score_all_fields(form, mapped)
    assert len(result) == 2
    f2 = next(r for r in result if r.field_id == "f2")
    assert f2.status == TIER_BLOCKED


def test_confidence_caps_at_1(scorer):
    field = make_field()
    conf, _ = scorer.score_field(field, "value", "user_input", 1.0)
    assert conf <= 1.0
