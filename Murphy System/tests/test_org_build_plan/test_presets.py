# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.presets package."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from src.org_build_plan.presets import (
    IndustryPreset,
    INDUSTRY_PRESETS,
    get_preset,
    list_presets,
)
from src.org_build_plan.compliance_profiler import FRAMEWORK_MAP


EXPECTED_PRESET_IDS = [
    "manufacturing",
    "financial_services",
    "logistics_fleet",
    "nonprofit_advocacy",
    "energy_utilities",
    "retail_ecommerce",
    "saas_agency",
]

KNOWN_SETUP_WIZARD_PRESETS = [
    "solo_operator",
    "personal_assistant",
    "org_onboarding",
    "startup_growth",
    "enterprise_compliance",
    "agency_automation",
]


def test_all_seven_presets_exist():
    """All 7 preset IDs must be registered."""
    for pid in EXPECTED_PRESET_IDS:
        assert pid in INDUSTRY_PRESETS, f"Preset '{pid}' not found"


def test_each_preset_is_industry_preset_instance():
    """Every registry value must be an IndustryPreset instance."""
    for pid, preset in INDUSTRY_PRESETS.items():
        assert isinstance(preset, IndustryPreset), f"Preset '{pid}' is not an IndustryPreset"


def test_each_preset_required_fields():
    """Each preset must have non-empty required string fields."""
    required = ["preset_id", "name", "description", "industry",
                "default_org_type", "default_labor_model", "default_company_size"]
    for pid, preset in INDUSTRY_PRESETS.items():
        for attr in required:
            val = getattr(preset, attr, None)
            assert val, f"Preset '{pid}' missing required field '{attr}'"


def test_preset_connector_ids_are_strings():
    """All recommended_connectors must be non-empty strings."""
    for pid, preset in INDUSTRY_PRESETS.items():
        for connector in preset.recommended_connectors:
            assert isinstance(connector, str) and connector, \
                f"Preset '{pid}' has invalid connector: {connector!r}"


def test_preset_frameworks_in_framework_map():
    """All recommended_frameworks must be keys in FRAMEWORK_MAP."""
    for pid, preset in INDUSTRY_PRESETS.items():
        for fw in preset.recommended_frameworks:
            assert fw in FRAMEWORK_MAP, \
                f"Preset '{pid}' framework '{fw}' not in FRAMEWORK_MAP"


def test_preset_setup_wizard_preset_is_known():
    """Each preset's setup_wizard_preset must reference a known wizard preset."""
    for pid, preset in INDUSTRY_PRESETS.items():
        assert preset.setup_wizard_preset in KNOWN_SETUP_WIZARD_PRESETS, \
            f"Preset '{pid}' has unknown setup_wizard_preset '{preset.setup_wizard_preset}'"


def test_preset_has_default_departments():
    """Each preset must have at least one default department."""
    for pid, preset in INDUSTRY_PRESETS.items():
        assert preset.default_departments, \
            f"Preset '{pid}' has no default_departments"


def test_preset_has_workflow_templates():
    """Each preset must have at least one workflow template."""
    for pid, preset in INDUSTRY_PRESETS.items():
        assert preset.workflow_templates, \
            f"Preset '{pid}' has no workflow_templates"


def test_get_preset_returns_correct_object():
    """get_preset should return the right IndustryPreset."""
    for pid in EXPECTED_PRESET_IDS:
        p = get_preset(pid)
        assert p is not None
        assert p.preset_id == pid


def test_get_preset_unknown_returns_none():
    """get_preset returns None for an unknown ID."""
    assert get_preset("does_not_exist") is None


def test_list_presets_structure():
    """list_presets returns one summary dict per preset with required keys."""
    summaries = list_presets()
    assert len(summaries) == len(EXPECTED_PRESET_IDS)
    for summary in summaries:
        assert "preset_id" in summary
        assert "name" in summary
        assert "description" in summary
        assert "industry" in summary


def test_preset_to_dict_serialisable():
    """to_dict must return a JSON-compatible dict for each preset."""
    import json
    for pid, preset in INDUSTRY_PRESETS.items():
        d = preset.to_dict()
        assert isinstance(d, dict)
        # Must be JSON-serialisable (no non-serialisable objects)
        json.dumps(d)


def test_manufacturing_preset_details():
    """Spot-check manufacturing preset values."""
    p = get_preset("manufacturing")
    assert p.industry == "manufacturing"
    assert p.default_labor_model == "union"
    assert "OSHA" in p.recommended_frameworks
    assert "scada_modbus" in p.recommended_connectors


def test_energy_preset_details():
    """Spot-check energy_utilities preset values."""
    p = get_preset("energy_utilities")
    assert p.industry == "energy"
    assert p.default_company_size == "enterprise"
    assert "NERC" in p.recommended_frameworks
    assert "scada_opcua" in p.recommended_connectors
