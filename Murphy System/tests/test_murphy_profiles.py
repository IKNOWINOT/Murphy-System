"""Tests for Murphy System grant profiles (Track A)."""

import pytest

from src.billing.grants.murphy_profiles import (
    get_murphy_profiles,
    murphy_sbir_profile,
    murphy_doe_profile,
    murphy_nsf_profile,
    murphy_manufacturing_profile,
)
from src.billing.grants.database import get_grant_by_id


REQUIRED_KEYS = [
    "company_name",
    "ein",
    "address",
    "naics_codes",
    "entity_type",
    "state",
    "verticals",
    "project_type",
    "annual_revenue",
    "employee_count",
    "project_cost",
    "is_rural",
    "has_ein",
    "has_sam_gov",
    "technical_description",
    "innovation_narrative",
    "commercial_potential",
    "team_description",
    "budget_template",
    "focus_grants",
]


class TestGetMurphyProfiles:
    def test_returns_dict(self):
        profiles = get_murphy_profiles()
        assert isinstance(profiles, dict)

    def test_all_four_profiles_present(self):
        profiles = get_murphy_profiles()
        assert "murphy_sbir_profile" in profiles
        assert "murphy_doe_profile" in profiles
        assert "murphy_nsf_profile" in profiles
        assert "murphy_manufacturing_profile" in profiles

    def test_profiles_are_dicts(self):
        profiles = get_murphy_profiles()
        for key, profile in profiles.items():
            assert isinstance(profile, dict), f"Profile {key} is not a dict"


class TestSbirProfile:
    profile = murphy_sbir_profile

    def test_has_required_keys(self):
        for key in REQUIRED_KEYS:
            assert key in self.profile, f"Missing key '{key}' in SBIR profile"

    def test_naics_codes_not_empty(self):
        assert len(self.profile["naics_codes"]) > 0

    def test_verticals_include_ai(self):
        assert "ai_ml" in self.profile["verticals"]

    def test_focus_grants_not_empty(self):
        assert len(self.profile["focus_grants"]) > 0

    def test_focus_grants_exist_in_catalog(self):
        for grant_id in self.profile["focus_grants"]:
            assert get_grant_by_id(grant_id) is not None, (
                f"Focus grant '{grant_id}' not found in catalog"
            )

    def test_budget_template_has_total(self):
        assert "total" in self.profile["budget_template"]
        assert self.profile["budget_template"]["total"] > 0

    def test_company_name_set(self):
        assert self.profile["company_name"]

    def test_ein_placeholder(self):
        assert "XX-XXXXXXX" in self.profile["ein"]

    def test_entity_type_is_small_business(self):
        assert self.profile["entity_type"] == "small_business"


class TestDoeProfile:
    profile = murphy_doe_profile

    def test_has_required_keys(self):
        for key in REQUIRED_KEYS:
            assert key in self.profile, f"Missing key '{key}' in DOE profile"

    def test_verticals_include_energy(self):
        assert "energy_management" in self.profile["verticals"]

    def test_focus_grants_exist_in_catalog(self):
        for grant_id in self.profile["focus_grants"]:
            assert get_grant_by_id(grant_id) is not None, (
                f"Focus grant '{grant_id}' not found in catalog"
            )

    def test_project_cost_reasonable(self):
        assert self.profile["project_cost"] >= 100_000


class TestNsfProfile:
    profile = murphy_nsf_profile

    def test_has_required_keys(self):
        for key in REQUIRED_KEYS:
            assert key in self.profile, f"Missing key '{key}' in NSF profile"

    def test_focus_grants_include_nsf(self):
        nsf_grants = [g for g in self.profile["focus_grants"] if "nsf" in g]
        assert len(nsf_grants) > 0

    def test_focus_grants_exist_in_catalog(self):
        for grant_id in self.profile["focus_grants"]:
            assert get_grant_by_id(grant_id) is not None, (
                f"Focus grant '{grant_id}' not found in catalog"
            )


class TestManufacturingProfile:
    profile = murphy_manufacturing_profile

    def test_has_required_keys(self):
        for key in REQUIRED_KEYS:
            assert key in self.profile, f"Missing key '{key}' in manufacturing profile"

    def test_verticals_include_manufacturing(self):
        assert "smart_manufacturing" in self.profile["verticals"]

    def test_focus_grants_exist_in_catalog(self):
        for grant_id in self.profile["focus_grants"]:
            assert get_grant_by_id(grant_id) is not None, (
                f"Focus grant '{grant_id}' not found in catalog"
            )

    def test_naics_codes_include_manufacturing(self):
        # NAICS 333xxx or 334xxx for manufacturing
        has_mfg = any(c.startswith("33") for c in self.profile["naics_codes"])
        assert has_mfg
