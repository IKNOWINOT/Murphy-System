# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from src.billing.grants.submission.format_adapters.sf424_builder import SF424Builder
from src.billing.grants.submission.format_adapters.sam_gov_format import SamGovFormatter
from src.billing.grants.submission.format_adapters.budget_narrative import BudgetNarrativeBuilder
from src.billing.grants.submission.format_adapters.research_plan import ResearchPlanFormatter


@pytest.fixture
def sample_data():
    return {
        "organization_name": "Test Org",
        "project_title": "Amazing Project",
        "uei": "ABC123",
        "ein": "99-1234567",
        "federal_amount": 200000,
        "match_amount": 50000,
        "start_date": "2024-06-01",
        "end_date": "2025-05-31",
        "ar_name": "John Smith",
        "ar_title": "CEO",
        "ar_email": "john@testorg.com",
        "ar_phone": "503-555-0200",
        "entity_name": "Test Org LLC",
        "cage_code": "1ABC2",
        "primary_naics": "541715",
        "address": "123 Main St",
        "city": "Portland",
        "state": "OR",
        "zip": "97201",
    }


def test_sf424_builder_returns_dict(sample_data):
    result = SF424Builder().build(sample_data)
    assert isinstance(result, dict)


def test_sf424_has_organization_name(sample_data):
    result = SF424Builder().build(sample_data)
    assert result["applicant_organization_name"] == "Test Org"


def test_sf424_has_project_title(sample_data):
    result = SF424Builder().build(sample_data)
    assert result["project_title"] == "Amazing Project"


def test_sf424_has_federal_funds(sample_data):
    result = SF424Builder().build(sample_data)
    assert result["federal_funds_requested"] == 200000


def test_sam_gov_csv_has_header(sample_data):
    csv_str = SamGovFormatter().build_csv(sample_data)
    assert "Field" in csv_str
    assert "Value" in csv_str


def test_sam_gov_csv_has_entity_name(sample_data):
    csv_str = SamGovFormatter().build_csv(sample_data)
    assert "Test Org LLC" in csv_str


def test_sam_gov_json_has_uei(sample_data):
    result = SamGovFormatter().build_json(sample_data)
    assert result["uei"] == "ABC123"


def test_sam_gov_json_has_address(sample_data):
    result = SamGovFormatter().build_json(sample_data)
    assert result["physicalAddress"]["city"] == "Portland"


def test_budget_narrative_contains_totals(sample_data):
    narrative = BudgetNarrativeBuilder().build(sample_data)
    assert "200,000" in narrative or "200000" in narrative


def test_budget_narrative_contains_sections(sample_data):
    narrative = BudgetNarrativeBuilder().build(sample_data)
    assert "PERSONNEL" in narrative
    assert "INDIRECT" in narrative


def test_research_plan_has_all_sections(sample_data):
    plan = ResearchPlanFormatter().build(sample_data)
    assert "project_summary" in plan
    assert "specific_aims" in plan
    assert "research_strategy" in plan
    assert "approach" in plan


def test_research_plan_project_summary_has_title(sample_data):
    plan = ResearchPlanFormatter().build(sample_data)
    assert "Amazing Project" in plan["project_summary"]
