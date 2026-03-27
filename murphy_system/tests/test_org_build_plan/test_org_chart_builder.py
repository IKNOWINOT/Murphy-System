# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.org_chart_builder module."""
import os


import pytest
from src.org_build_plan.organization_intake import DepartmentSpec, OrganizationIntakeProfile
from src.org_build_plan.org_chart_builder import (
    OrgChartBuilder,
    OrgChartResult,
    DEPARTMENT_MAP,
    LEVEL_MAP,
)


def make_dept(**kwargs) -> DepartmentSpec:
    defaults = {
        "name": "engineering",
        "head_name": "Alice",
        "head_email": "alice@example.com",
        "headcount": 1,
        "level": "vp",
        "responsibilities": ["design"],
        "automation_priorities": ["system"],
    }
    defaults.update(kwargs)
    return DepartmentSpec(**defaults)


def make_profile(departments=None) -> OrganizationIntakeProfile:
    return OrganizationIntakeProfile(
        org_name="Build Test Corp",
        industry="manufacturing",
        org_type="corporation",
        labor_model="w2",
        company_size="medium",
        departments=departments or [],
    )


def test_build_from_single_department():
    """Building from one department creates at least 2 positions (CEO + head)."""
    builder = OrgChartBuilder()
    profile = make_profile(departments=[make_dept()])
    result = builder.build_from_intake(profile)
    assert isinstance(result, OrgChartResult)
    assert result.positions_created >= 2  # CEO + dept head


def test_build_from_multi_department():
    """Multiple departments produce the expected number of positions."""
    builder = OrgChartBuilder()
    depts = [
        make_dept(name="engineering", headcount=1),
        make_dept(name="finance", level="c_suite", headcount=1),
        make_dept(name="sales", level="vp", headcount=1),
    ]
    result = builder.build_from_intake(make_profile(departments=depts))
    # CEO + 3 heads
    assert result.positions_created >= 4


def test_ic_positions_for_headcount_gt_1():
    """Departments with headcount > 1 get IC positions."""
    builder = OrgChartBuilder()
    dept = make_dept(name="operations", headcount=5, level="director")
    result = builder.build_from_intake(make_profile(departments=[dept]))
    # CEO + head + (min(5-1, 3) = 3 ICs) = 5
    assert result.positions_created >= 5


def test_reporting_chains_created():
    """Each department head gets a reporting chain to CEO."""
    builder = OrgChartBuilder()
    depts = [make_dept(name="engineering"), make_dept(name="sales")]
    result = builder.build_from_intake(make_profile(departments=depts))
    assert result.reporting_chains >= 2


def test_departments_mapped():
    """departments_mapped contains the dept names processed."""
    builder = OrgChartBuilder()
    depts = [make_dept(name="engineering"), make_dept(name="finance")]
    result = builder.build_from_intake(make_profile(departments=depts))
    assert "engineering" in result.departments_mapped
    assert "finance" in result.departments_mapped


def test_org_chart_dict_populated():
    """org_chart dict has position entries."""
    builder = OrgChartBuilder()
    result = builder.build_from_intake(make_profile(departments=[make_dept()]))
    assert isinstance(result.org_chart, dict)
    assert len(result.org_chart) > 0


def test_department_type_mapping():
    """DEPARTMENT_MAP covers all standard department names."""
    for key in ["engineering", "operations", "sales", "marketing",
                "finance", "hr", "legal", "product", "executive",
                "it", "research", "customer_success"]:
        assert key in DEPARTMENT_MAP


def test_level_map_completeness():
    """LEVEL_MAP covers all PositionLevel values."""
    for key in ["c_suite", "vp", "director", "manager", "lead",
                "individual_contributor", "intern"]:
        assert key in LEVEL_MAP


def test_build_enforcement_nodes():
    """build_enforcement creates at least CEO + dept nodes."""
    builder = OrgChartBuilder()
    depts = [make_dept(name="engineering"), make_dept(name="sales")]
    profile = make_profile(departments=depts)
    enforcement = builder.build_enforcement(profile)
    # Should have at least ceo + 2 dept nodes
    assert len(enforcement._nodes) >= 3


def test_result_to_dict():
    """OrgChartResult.to_dict is JSON-serialisable."""
    import json
    builder = OrgChartBuilder()
    result = builder.build_from_intake(make_profile(departments=[make_dept()]))
    d = result.to_dict()
    assert "positions_created" in d
    json.dumps(d)
