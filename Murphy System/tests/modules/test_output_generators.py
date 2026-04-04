"""
Tests for output generators.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import json
import pytest
import xml.etree.ElementTree as ET
from src.billing.grants.form_filler.output_generators.pdf_generator import PDFGenerator
from src.billing.grants.form_filler.output_generators.xml_generator import XMLGenerator
from src.billing.grants.form_filler.output_generators.json_export import JSONExporter
from src.billing.grants.form_filler.review_session import FormDefinition, FormField, FilledField, FormSection


@pytest.fixture
def sample_form():
    return FormDefinition(
        form_id="test_form", form_name="Test Form", grant_program_id="test",
        fields=[
            FormField(field_id="org_name", label="Organization Name", field_type="text", section_id="s1"),
            FormField(field_id="project_title", label="Project Title", field_type="text", section_id="s1"),
        ],
        sections=[FormSection(section_id="s1", title="Main Section")]
    )


@pytest.fixture
def sample_filled_fields():
    return [
        FilledField(field_id="org_name", value="Acme Corp", confidence=0.95, status="auto_filled", source="saved_form_data"),
        FilledField(field_id="project_title", value="AI Project", confidence=0.7, status="needs_review", source="murphy_profile"),
    ]


def test_json_export_produces_valid_json(sample_form, sample_filled_fields):
    exporter = JSONExporter()
    result = exporter.generate(sample_form, sample_filled_fields, {"export_time": "2024-01-01"})
    assert isinstance(result, bytes)
    data = json.loads(result)
    assert data is not None


def test_xml_export_produces_valid_xml(sample_form, sample_filled_fields):
    generator = XMLGenerator()
    result = generator.generate(sample_form, sample_filled_fields, {})
    assert isinstance(result, bytes)
    root = ET.fromstring(result)
    assert root is not None


def test_pdf_generator_produces_bytes(sample_form, sample_filled_fields):
    generator = PDFGenerator()
    result = generator.generate(sample_form, sample_filled_fields, {})
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_pdf_falls_back_gracefully(sample_form, sample_filled_fields):
    generator = PDFGenerator()
    generator._has_reportlab = False
    result = generator.generate(sample_form, sample_filled_fields, {})
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_json_includes_all_fields(sample_form, sample_filled_fields):
    exporter = JSONExporter()
    result = json.loads(exporter.generate(sample_form, sample_filled_fields, {}))
    field_ids = [f["field_id"] for f in result.get("fields", [])]
    assert "org_name" in field_ids
    assert "project_title" in field_ids


def test_xml_has_root_element(sample_form, sample_filled_fields):
    generator = XMLGenerator()
    result = generator.generate(sample_form, sample_filled_fields, {})
    root = ET.fromstring(result)
    assert root.tag == "GrantApplication"
