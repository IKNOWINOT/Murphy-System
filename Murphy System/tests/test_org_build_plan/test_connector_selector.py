# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.connector_selector module."""
import os


import pytest
from src.org_build_plan.organization_intake import OrganizationIntakeProfile
from src.org_build_plan.connector_selector import (
    ConnectorSelectionResult,
    ConnectorSelector,
)


def make_profile(**kwargs) -> OrganizationIntakeProfile:
    defaults = {
        "org_name": "Connector Test",
        "industry": "manufacturing",
        "company_size": "medium",
    }
    defaults.update(kwargs)
    return OrganizationIntakeProfile(**defaults)


def test_select_connectors_manufacturing():
    """Manufacturing preset connectors are included in the result."""
    cs = ConnectorSelector()
    profile = make_profile(industry="manufacturing")
    result = cs.select_connectors(profile)
    assert "scada_modbus" in result.selected_connectors
    assert "quickbooks" in result.selected_connectors


def test_select_connectors_energy():
    """Energy preset connectors are included."""
    cs = ConnectorSelector()
    profile = make_profile(industry="energy")
    result = cs.select_connectors(profile)
    assert "scada_opcua" in result.selected_connectors
    assert "power_bi" in result.selected_connectors


def test_select_connectors_finance():
    """Finance preset connectors are included."""
    cs = ConnectorSelector()
    profile = make_profile(industry="finance")
    result = cs.select_connectors(profile)
    assert "stripe" in result.selected_connectors
    assert "salesforce" in result.selected_connectors


def test_select_connectors_technology():
    """Technology/SaaS preset connectors are included."""
    cs = ConnectorSelector()
    profile = make_profile(industry="technology")
    result = cs.select_connectors(profile)
    assert "github" in result.selected_connectors
    assert "jira" in result.selected_connectors


def test_deduplication():
    """Connectors appearing in multiple sources are only included once."""
    cs = ConnectorSelector()
    profile = make_profile(
        industry="manufacturing",
        existing_systems=["quickbooks"],  # also in manufacturing preset
        connector_needs=["quickbooks"],
    )
    result = cs.select_connectors(profile)
    assert result.selected_connectors.count("quickbooks") == 1


def test_existing_systems_included():
    """Connectors from existing_systems appear in the result."""
    cs = ConnectorSelector()
    profile = make_profile(
        industry="other",
        existing_systems=["slack", "jira"],
    )
    result = cs.select_connectors(profile)
    assert "slack" in result.selected_connectors
    assert "jira" in result.selected_connectors
    assert "slack" in result.from_existing
    assert "jira" in result.from_existing


def test_connector_needs_included():
    """Connectors from connector_needs appear in the result."""
    cs = ConnectorSelector()
    profile = make_profile(
        industry="other",
        connector_needs=["github", "confluence"],
    )
    result = cs.select_connectors(profile)
    assert "github" in result.selected_connectors
    assert "github" in result.from_needs


def test_categories_populated():
    """categories dict must be populated when connectors are selected."""
    cs = ConnectorSelector()
    profile = make_profile(industry="manufacturing")
    result = cs.select_connectors(profile)
    assert isinstance(result.categories, dict)
    assert len(result.categories) > 0


def test_empty_intake_returns_empty():
    """An intake with no preset match and no connectors returns empty lists."""
    cs = ConnectorSelector()
    profile = make_profile(industry="other")
    result = cs.select_connectors(profile)
    # other industry has no preset — lists should all be empty
    assert result.selected_connectors == []
    assert result.from_preset == []


def test_get_available_connectors():
    """get_available_connectors returns a non-empty sorted list."""
    cs = ConnectorSelector()
    connectors = cs.get_available_connectors()
    assert len(connectors) > 0
    assert connectors == sorted(connectors)


def test_result_to_dict():
    """ConnectorSelectionResult.to_dict is JSON-serialisable."""
    import json
    cs = ConnectorSelector()
    result = cs.select_connectors(make_profile(industry="finance"))
    d = result.to_dict()
    assert "selected_connectors" in d
    json.dumps(d)
