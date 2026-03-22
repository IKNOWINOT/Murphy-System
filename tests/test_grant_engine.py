"""Tests for the grant eligibility matching engine."""

import pytest

from src.billing.grants.engine import match_grants, match_for_murphy, match_for_customer
from src.billing.grants.models import EligibilityResult


_BASE_PROFILE = {
    "entity_type": "small_business",
    "state": "OR",
    "verticals": ["building_automation", "energy_management", "ai_ml"],
    "project_type": "research_and_development",
    "annual_revenue": 0.0,
    "employee_count": 5,
    "project_cost": 275_000.0,
    "has_ein": True,
    "has_sam_gov": False,
    "is_rural": False,
}


class TestMatchGrants:
    def test_returns_list(self):
        results = match_grants(_BASE_PROFILE)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_results_are_eligibility_result(self):
        results = match_grants(_BASE_PROFILE)
        for r in results:
            assert isinstance(r, EligibilityResult)

    def test_sorted_by_estimated_value_descending(self):
        results = match_grants(_BASE_PROFILE)
        values = [r.estimated_value for r in results]
        assert values == sorted(values, reverse=True)

    def test_eligible_results_have_positive_confidence(self):
        results = match_grants(_BASE_PROFILE)
        for r in results:
            if r.eligible:
                assert r.confidence > 0.0
            else:
                assert r.confidence <= 0.3

    def test_ineligible_results_have_zero_estimated_value(self):
        results = match_grants(_BASE_PROFILE)
        for r in results:
            if not r.eligible:
                assert r.estimated_value == 0.0

    def test_state_filtering_works(self):
        ca_profile = {**_BASE_PROFILE, "state": "CA"}
        results_ca = match_grants(ca_profile)
        results_by_id = {r.grant_id: r for r in results_ca}

        # CA-specific grants should be eligible for CA
        assert results_by_id.get("cec") is not None
        assert results_by_id["cec"].eligible is True

        # OR-specific grants should NOT be eligible for CA profile
        or_grant = results_by_id.get("etor")
        if or_grant:
            assert or_grant.eligible is False

    def test_or_state_specific_grants(self):
        or_profile = {**_BASE_PROFILE, "state": "OR"}
        results = match_grants(or_profile)
        by_id = {r.grant_id: r for r in results}

        # Oregon Energy Trust should be eligible
        assert by_id["etor"].eligible is True
        # New York NYSERDA should not be eligible
        assert by_id["nyserda"].eligible is False

    def test_entity_type_filtering(self):
        individual_profile = {**_BASE_PROFILE, "entity_type": "individual"}
        results = match_grants(individual_profile)
        by_id = {r.grant_id: r for r in results}

        # §25C/§25D are individual-only — should be eligible
        assert by_id.get("tc_25c") is not None
        assert by_id["tc_25c"].eligible is True

    def test_usda_reap_requires_rural(self):
        urban_profile = {**_BASE_PROFILE, "is_rural": False}
        results = match_grants(urban_profile)
        by_id = {r.grant_id: r for r in results}
        assert by_id["usda_reap"].eligible is False

        rural_profile = {**_BASE_PROFILE, "is_rural": True, "entity_type": "agricultural_producer"}
        results_rural = match_grants(rural_profile)
        by_id_rural = {r.grant_id: r for r in results_rural}
        assert by_id_rural["usda_reap"].eligible is True

    def test_sam_gov_action_item_for_federal(self):
        profile_no_sam = {**_BASE_PROFILE, "has_sam_gov": False}
        results = match_grants(profile_no_sam)
        by_id = {r.grant_id: r for r in results}
        sbir = by_id.get("sbir_phase1")
        assert sbir is not None
        sam_item = any("SAM.gov" in item for item in sbir.action_items)
        assert sam_item, "Expected SAM.gov action item for federal grant"

    def test_all_results_have_grant_id(self):
        results = match_grants(_BASE_PROFILE)
        for r in results:
            assert r.grant_id


class TestMatchForMurphy:
    def test_sbir_profile(self):
        results = match_for_murphy("sbir")
        assert len(results) > 0
        by_id = {r.grant_id: r for r in results}
        assert by_id["sbir_phase1"].eligible is True

    def test_doe_profile(self):
        results = match_for_murphy("doe")
        assert len(results) > 0

    def test_nsf_profile(self):
        results = match_for_murphy("nsf")
        assert len(results) > 0

    def test_manufacturing_profile(self):
        results = match_for_murphy("manufacturing")
        assert len(results) > 0

    def test_unknown_profile_falls_back_to_sbir(self):
        results = match_for_murphy("nonexistent_profile_xyz")
        assert len(results) > 0


class TestMatchForCustomer:
    def test_basic_customer_profile(self):
        customer = {
            "entity_type": "small_business",
            "state": "CA",
            "verticals": ["building_automation", "hvac_controls"],
            "project_cost": 150_000.0,
            "is_rural": False,
            "has_ein": True,
            "has_sam_gov": False,
        }
        results = match_for_customer(customer)
        assert len(results) > 0
        by_id = {r.grant_id: r for r in results}
        assert by_id["cec"].eligible is True
