"""Tests for the grant catalog database."""

import pytest

from src.billing.grants.database import get_all_grants, get_grant_by_id
from src.billing.grants.models import Grant


class TestCatalogCompleteness:
    def setup_method(self):
        self.grants = get_all_grants()

    def test_catalog_not_empty(self):
        assert len(self.grants) > 0

    def test_minimum_grant_count(self):
        # Should have at least 45 grants across all categories
        assert len(self.grants) >= 45

    def test_all_ids_unique(self):
        ids = [g.id for g in self.grants]
        assert len(ids) == len(set(ids)), "Duplicate grant IDs found"

    def test_all_grants_have_name(self):
        for g in self.grants:
            assert g.name, f"Grant {g.id} has empty name"

    def test_all_grants_have_description(self):
        for g in self.grants:
            assert g.description, f"Grant {g.id} has empty description"

    def test_all_grants_have_agency(self):
        for g in self.grants:
            assert g.agency, f"Grant {g.id} has empty agency"

    def test_all_grants_have_valid_amounts(self):
        for g in self.grants:
            assert g.min_amount >= 0, f"Grant {g.id} has negative min_amount"
            assert g.max_amount > 0, f"Grant {g.id} has zero or negative max_amount"
            assert g.max_amount >= g.min_amount, (
                f"Grant {g.id} max_amount < min_amount"
            )

    def test_all_grants_have_requirements(self):
        for g in self.grants:
            assert len(g.requirements) > 0, f"Grant {g.id} has no requirements"

    def test_all_grants_have_tags(self):
        for g in self.grants:
            assert len(g.tags) > 0, f"Grant {g.id} has no tags"

    def test_expected_grant_ids_present(self):
        expected = [
            "tc_179d", "tc_48_itc", "tc_48c", "tc_25c", "tc_25d",
            "tc_45_ptc", "tc_41_rd", "rebate_heehra", "rebate_homes",
            "sbir_phase1", "sbir_phase2", "sbir_breakthrough", "sttr",
            "doe_arpa_e", "doe_amo", "doe_bto", "cesmii",
            "nsf_convergence", "nsf_pfi", "eda_b2s", "nist_mep", "doe_grip",
            "sba_microloan", "sba_7a", "sba_504",
            "usda_reap",
            "etor", "nyserda", "cec", "masscec", "njce",
            "util_dr", "util_obf", "util_custom",
            "cpace",
            "ct_green_bank", "ny_green_bank", "nj_green_bank", "ca_green_finance",
            "espc_federal", "espc_commercial",
            "federal_rd_41", "state_rd_or", "state_rd_ca", "state_rd_ny",
            "state_rd_tx", "state_rd_ma", "state_rd_ct", "state_rd_nj", "state_rd_pa",
        ]
        grant_ids = {g.id for g in self.grants}
        for expected_id in expected:
            assert expected_id in grant_ids, f"Expected grant ID '{expected_id}' not in catalog"

    def test_state_specific_grants_have_states(self):
        state_grants = {
            "etor": ["OR"],
            "nyserda": ["NY"],
            "cec": ["CA"],
            "masscec": ["MA"],
            "njce": ["NJ"],
            "ct_green_bank": ["CT"],
            "ny_green_bank": ["NY"],
            "nj_green_bank": ["NJ"],
            "ca_green_finance": ["CA"],
            "state_rd_or": ["OR"],
            "state_rd_ca": ["CA"],
        }
        by_id = {g.id: g for g in self.grants}
        for grant_id, expected_states in state_grants.items():
            grant = by_id.get(grant_id)
            assert grant is not None
            for state in expected_states:
                assert state in grant.eligible_states, (
                    f"Grant {grant_id} should have {state} in eligible_states"
                )

    def test_national_grants_have_empty_state_list(self):
        national_ids = ["sbir_phase1", "tc_41_rd", "doe_arpa_e"]
        by_id = {g.id: g for g in self.grants}
        for grant_id in national_ids:
            g = by_id[grant_id]
            assert g.eligible_states == [], f"Grant {grant_id} should have empty eligible_states"


class TestGetGrantById:
    def test_known_grant(self):
        grant = get_grant_by_id("sbir_phase1")
        assert grant is not None
        assert grant.id == "sbir_phase1"

    def test_unknown_grant(self):
        assert get_grant_by_id("nonexistent_grant_xyz") is None

    def test_returns_grant_instance(self):
        grant = get_grant_by_id("tc_179d")
        assert isinstance(grant, Grant)

    def test_multiple_lookups_consistent(self):
        g1 = get_grant_by_id("sbir_phase2")
        g2 = get_grant_by_id("sbir_phase2")
        assert g1 == g2
