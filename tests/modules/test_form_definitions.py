"""
Tests for form definitions.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
from src.billing.grants.form_filler.form_definitions import FORM_REGISTRY, get_form, list_forms
from src.billing.grants.form_filler.form_definitions.sbir_phase1 import SBIRPhase1Form


def test_all_forms_load_without_error():
    for form_id, form_obj in FORM_REGISTRY.items():
        defn = form_obj.get_definition()
        assert defn is not None
        assert defn.form_id


def test_sbir_has_required_fields():
    form = SBIRPhase1Form().get_definition()
    field_ids = [f.field_id for f in form.fields]
    assert "company_legal_name" in field_ids
    assert "ein" in field_ids
    assert "uei" in field_ids
    assert "project_title" in field_ids
    assert "total_budget_request" in field_ids


def test_sbir_has_certification_fields_blocked():
    form = SBIRPhase1Form().get_definition()
    cert_fields = [f for f in form.fields if f.legal_certification]
    assert len(cert_fields) >= 4


def test_all_forms_have_at_least_one_certification_field():
    for form_id, form_obj in FORM_REGISTRY.items():
        defn = form_obj.get_definition()
        cert_fields = [f for f in defn.fields if f.legal_certification]
        assert len(cert_fields) >= 1, f"Form {form_id} has no certification fields"


def test_form_registry_complete():
    expected_forms = ["sbir_phase1", "sttr_phase1", "nsf_sbir", "sam_gov", "grants_gov", "sba_microloan", "energy_trust", "generic_grant"]
    for form_id in expected_forms:
        assert form_id in FORM_REGISTRY, f"Form {form_id} missing from registry"


def test_form_definitions_valid():
    from src.billing.grants.form_filler.review_session import FormDefinition
    for form_id, form_obj in FORM_REGISTRY.items():
        defn = form_obj.get_definition()
        assert isinstance(defn, FormDefinition)
        assert len(defn.fields) > 0
