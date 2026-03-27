# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.build_orchestrator module."""
import os


import pytest
from src.org_build_plan.organization_intake import DepartmentSpec, OrganizationIntakeProfile
from src.org_build_plan.build_orchestrator import (
    BuildPhase,
    BuildResult,
    OrganizationBuildOrchestrator,
)


def make_profile(**kwargs) -> OrganizationIntakeProfile:
    defaults = {
        "org_name": "Orchestrator Test Corp",
        "industry": "manufacturing",
        "org_type": "corporation",
        "labor_model": "union",
        "company_size": "medium",
        "ip_protection_level": "standard",
        "regulatory_frameworks": ["OSHA"],
        "departments": [
            DepartmentSpec(
                name="engineering",
                head_name="VP Eng",
                head_email="eng@test.com",
                headcount=5,
                level="vp",
                responsibilities=["design"],
                automation_priorities=["system"],
            )
        ],
    }
    defaults.update(kwargs)
    return OrganizationIntakeProfile(**defaults)


def test_full_build_from_manufacturing_preset():
    """Happy path: build_from_preset succeeds for manufacturing."""
    obo = OrganizationBuildOrchestrator()
    result = obo.build_from_preset("manufacturing", "Steel Works Inc")
    assert result.phase == BuildPhase.COMPLETED
    assert result.tenant_id is not None
    assert result.provision_result is not None
    assert result.org_chart_result is not None
    assert result.connector_result is not None
    assert result.compliance_result is not None
    assert result.workflow_result is not None
    assert result.errors == []


def test_full_build_from_finance_preset():
    """Happy path: build_from_preset succeeds for financial_services."""
    obo = OrganizationBuildOrchestrator()
    result = obo.build_from_preset("financial_services", "Capital Group")
    assert result.phase == BuildPhase.COMPLETED
    assert result.errors == []


def test_build_with_invalid_intake_stops_at_intake():
    """Build with an invalid profile (empty org_name) fails at INTAKE phase."""
    obo = OrganizationBuildOrchestrator()
    bad_profile = make_profile(org_name="")
    result = obo.build_organization(bad_profile)
    assert result.phase == BuildPhase.FAILED
    assert any("org_name" in e for e in result.errors)
    # Downstream steps must not run — no tenant provisioned
    assert result.tenant_id is None


def test_get_build_by_id():
    """get_build returns the correct result after a successful build."""
    obo = OrganizationBuildOrchestrator()
    result = obo.build_organization(make_profile())
    retrieved = obo.get_build(result.build_id)
    assert retrieved is not None
    assert retrieved.build_id == result.build_id


def test_get_build_unknown_returns_none():
    """get_build returns None for an unknown build_id."""
    obo = OrganizationBuildOrchestrator()
    assert obo.get_build("does_not_exist") is None


def test_list_builds():
    """list_builds returns all completed builds."""
    obo = OrganizationBuildOrchestrator()
    r1 = obo.build_organization(make_profile(org_name="Corp A"))
    r2 = obo.build_organization(make_profile(org_name="Corp B"))
    builds = obo.list_builds()
    ids = [b["build_id"] for b in builds]
    assert r1.build_id in ids
    assert r2.build_id in ids


def test_available_presets_listing():
    """get_available_presets returns all 7 presets."""
    obo = OrganizationBuildOrchestrator()
    presets = obo.get_available_presets()
    ids = [p["preset_id"] for p in presets]
    assert len(ids) == 7
    assert "manufacturing" in ids
    assert "saas_agency" in ids


def test_build_from_preset_with_custom_departments():
    """build_from_preset allows overriding departments."""
    obo = OrganizationBuildOrchestrator()
    custom_depts = [
        DepartmentSpec(
            name="finance",
            head_name="Jane CFO",
            head_email="cfo@test.com",
            headcount=3,
            level="c_suite",
            responsibilities=["budgeting"],
            automation_priorities=["data"],
        )
    ]
    result = obo.build_from_preset("manufacturing", "Custom Mfg", departments=custom_depts)
    assert result.phase == BuildPhase.COMPLETED
    assert "finance" in result.org_chart_result["departments_mapped"]


def test_build_from_unknown_preset_fails():
    """build_from_preset with an unknown preset_id returns FAILED."""
    obo = OrganizationBuildOrchestrator()
    result = obo.build_from_preset("nonexistent_preset", "Org X")
    assert result.phase == BuildPhase.FAILED
    assert any("nonexistent_preset" in e for e in result.errors)


def test_build_result_has_completed_at():
    """Successful build sets completed_at timestamp."""
    obo = OrganizationBuildOrchestrator()
    result = obo.build_organization(make_profile())
    assert result.completed_at is not None


def test_build_result_to_dict():
    """BuildResult.to_dict is JSON-serialisable."""
    import json
    obo = OrganizationBuildOrchestrator()
    result = obo.build_organization(make_profile())
    d = result.to_dict()
    assert "build_id" in d
    assert "phase" in d
    json.dumps(d)
