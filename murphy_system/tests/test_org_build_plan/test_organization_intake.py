# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.organization_intake module."""
import os


import pytest
from src.org_build_plan.organization_intake import (
    DepartmentSpec,
    OrganizationIntake,
    OrganizationIntakeProfile,
    VALID_ORG_TYPES,
    VALID_LABOR_MODELS,
    VALID_IP_LEVELS,
    VALID_INDUSTRIES,
    VALID_REGULATORY_FRAMEWORKS,
)


def make_intake() -> OrganizationIntake:
    return OrganizationIntake()


def test_default_profile_creation():
    """OrganizationIntake creates a profile with sensible defaults."""
    intake = make_intake()
    profile = intake.get_profile()
    assert isinstance(profile, OrganizationIntakeProfile)
    assert profile.org_name == ""
    assert profile.industry == "other"
    assert profile.ip_protection_level == "standard"


def test_question_list_completeness():
    """get_questions returns at least 12 questions."""
    intake = make_intake()
    questions = intake.get_questions()
    assert len(questions) >= 12
    ids = [q["question_id"] for q in questions]
    required_ids = [
        "org_name", "industry", "org_type", "company_size", "labor_model",
        "regulatory_frameworks", "existing_systems", "connector_needs",
        "workflow_priorities", "ip_protection_level", "budget_tracking",
        "franchise_model",
    ]
    for qid in required_ids:
        assert qid in ids, f"Question '{qid}' missing from questionnaire"


def test_apply_answer_valid_org_name():
    """Applying a valid org_name updates the profile."""
    intake = make_intake()
    result = intake.apply_answer("org_name", "Acme Corp")
    assert result["applied"] is True
    assert intake.get_profile().org_name == "Acme Corp"


def test_apply_answer_valid_industry():
    """Applying a valid industry updates the profile."""
    intake = make_intake()
    result = intake.apply_answer("industry", "manufacturing")
    assert result["applied"] is True
    assert intake.get_profile().industry == "manufacturing"


def test_apply_answer_invalid_industry():
    """Applying an invalid industry returns an error."""
    intake = make_intake()
    result = intake.apply_answer("industry", "space_mining")
    assert result["applied"] is False
    assert "error" in result


def test_apply_answer_valid_ip_level():
    """patent_pending is a valid ip_protection_level."""
    intake = make_intake()
    result = intake.apply_answer("ip_protection_level", "patent_pending")
    assert result["applied"] is True
    assert intake.get_profile().ip_protection_level == "patent_pending"


def test_apply_answer_invalid_question_id():
    """Unknown question_id returns an error."""
    intake = make_intake()
    result = intake.apply_answer("does_not_exist", "value")
    assert result["applied"] is False


def test_apply_answer_budget_tracking_boolean():
    """budget_tracking=yes sets bool True."""
    intake = make_intake()
    intake.apply_answer("budget_tracking", "yes")
    assert intake.get_profile().budget_tracking is True


def test_apply_answer_franchise_model():
    """franchise_model=no sets bool False."""
    intake = make_intake()
    intake.apply_answer("franchise_model", "no")
    assert intake.get_profile().franchise_model is False


def test_apply_answer_regulatory_frameworks_list():
    """Regulatory frameworks can be provided as a list."""
    intake = make_intake()
    intake.apply_answer("org_name", "Mfg Co")
    result = intake.apply_answer("regulatory_frameworks", ["OSHA", "EPA"])
    assert result["applied"] is True
    assert "OSHA" in intake.get_profile().regulatory_frameworks
    assert "EPA" in intake.get_profile().regulatory_frameworks


def test_validate_profile_missing_org_name():
    """Validation fails when org_name is empty."""
    intake = make_intake()
    intake.apply_answer("industry", "manufacturing")
    v = intake.validate_profile()
    assert v["valid"] is False
    assert any("org_name" in issue for issue in v["issues"])


def test_validate_profile_invalid_industry():
    """Validation fails when industry is not in VALID_INDUSTRIES."""
    intake = make_intake()
    intake.apply_answer("org_name", "Test Org")
    intake._profile.industry = "alien_tech"
    v = intake.validate_profile()
    assert v["valid"] is False
    assert any("industry" in issue for issue in v["issues"])


def test_validate_profile_passes_when_complete():
    """Validation passes when all required fields are set correctly."""
    intake = make_intake()
    intake.apply_answer("org_name", "Valid Org")
    intake.apply_answer("industry", "manufacturing")
    intake.apply_answer("org_type", "corporation")
    intake.apply_answer("company_size", "medium")
    intake.apply_answer("labor_model", "union")
    intake.apply_answer("ip_protection_level", "standard")
    v = intake.validate_profile()
    assert v["valid"] is True, v["issues"]


def test_department_spec_creation():
    """DepartmentSpec can be created and serialised."""
    spec = DepartmentSpec(
        name="engineering",
        head_name="Jane Smith",
        head_email="jane@example.com",
        headcount=10,
        level="vp",
        responsibilities=["architecture"],
        automation_priorities=["system"],
    )
    d = spec.to_dict()
    assert d["name"] == "engineering"
    assert d["headcount"] == 10
    assert d["level"] == "vp"


def test_apply_preset_manufacturing():
    """apply_preset('manufacturing') fills in preset defaults."""
    intake = make_intake()
    intake.apply_answer("org_name", "Steel Works Inc")
    profile = intake.apply_preset("manufacturing")
    assert profile.industry == "manufacturing"
    assert profile.labor_model == "union"
    assert len(profile.departments) > 0


def test_apply_preset_unknown_raises():
    """apply_preset raises ValueError for an unknown preset."""
    intake = make_intake()
    with pytest.raises(ValueError):
        intake.apply_preset("unknown_preset_xyz")


def test_to_dict_serialisable():
    """to_dict produces a JSON-serialisable dict."""
    import json
    intake = make_intake()
    intake.apply_answer("org_name", "Serialise Co")
    intake.apply_answer("industry", "technology")
    d = intake.to_dict()
    assert "profile" in d
    json.dumps(d)
