"""
Tests for FieldMapper.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
from src.billing.grants.form_filler.field_mapper import FieldMapper
from src.billing.grants.form_filler.review_session import FormField, FormDefinition, FormSection


@pytest.fixture
def mapper():
    return FieldMapper()


def make_form(fields):
    return FormDefinition(
        form_id="test", form_name="Test Form", grant_program_id="test",
        fields=fields,
        sections=[FormSection(section_id="default", title="Default")]
    )


def test_maps_exact_field_id_match(mapper):
    fields = [FormField(field_id="company_name", label="Company Name", field_type="text", section_id="default")]
    form = make_form(fields)
    result = mapper.map_fields(form, {"company_name": "Acme"}, {})
    assert "company_name" in result
    assert result["company_name"]["value"] == "Acme"


def test_maps_by_data_source_hint(mapper):
    fields = [FormField(field_id="org_name", label="Organization Name", field_type="text", data_source_hint="company_info", section_id="default")]
    form = make_form(fields)
    result = mapper.map_fields(form, {"company_name": "Acme"}, {})
    assert "org_name" in result


def test_maps_company_info_fields(mapper):
    fields = [
        FormField(field_id="ein_field", label="EIN", field_type="text", data_source_hint="company_info", section_id="default"),
        FormField(field_id="uei_field", label="UEI", field_type="text", data_source_hint="company_info", section_id="default"),
    ]
    form = make_form(fields)
    result = mapper.map_fields(form, {"ein": "12-3456789", "uei": "ABC123"}, {})
    assert result.get("ein_field", {}).get("value") is not None or result.get("uei_field", {}).get("value") is not None


def test_blocks_legal_certification_fields(mapper):
    fields = [FormField(field_id="cert", label="Certification", field_type="checkbox", legal_certification=True, data_source_hint="legal_certification", section_id="default")]
    form = make_form(fields)
    result = mapper.map_fields(form, {"cert": True, "anything": "value"}, {})
    if "cert" in result:
        assert result["cert"]["value"] is None or result["cert"].get("source") != "saved_form_data"


def test_maps_project_info_fields(mapper):
    fields = [FormField(field_id="proj_title", label="Project Title", field_type="text", data_source_hint="project_info", section_id="default")]
    form = make_form(fields)
    result = mapper.map_fields(form, {"project_title": "AI Innovation"}, {})
    assert "proj_title" in result
    assert result["proj_title"]["value"] == "AI Innovation"


def test_builds_field_context(mapper):
    field = FormField(field_id="company_name", label="Company Name", field_type="text", section_id="default")
    ctx = mapper.build_field_context(field, {"company_name": "Acme", "ein": "12-3456789"})
    assert "Company Name" in ctx
    assert "company_name" in ctx
