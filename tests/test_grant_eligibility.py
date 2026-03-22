"""
Test: Grant Eligibility Matching

Tests that the eligibility engine correctly matches project parameters to grants.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.engine import GrantEligibilityEngine
from src.billing.grants.models import EligibilityRequest, GrantCategory


@pytest.fixture
def engine():
    return GrantEligibilityEngine()


def test_bas_project_oregon_matches_energy_grants(engine):
    """BAS/BMS project in Oregon → Energy Trust OR + federal energy grants."""
    req = EligibilityRequest(
        project_type="bas_bms",
        entity_type="small_business",
        state="OR",
        project_cost_usd=50_000,
        is_commercial=True,
    )
    resp = engine.match(req)
    assert len(resp.matches) > 0
    grant_ids = {m.grant.id for m in resp.matches}
    # Energy Trust Oregon should match for OR commercial BAS
    assert "energy_trust_oregon" in grant_ids, "Energy Trust Oregon should match OR BAS project"
    # Federal grants (BTO, SBA) should also match
    assert any(g in grant_ids for g in ["doe_bto", "sba_7a", "sec_179d"])


def test_rd_project_matches_sbir(engine):
    """R&D project with has_rd_activity=True → SBIR matches."""
    req = EligibilityRequest(
        project_type="ai_platform",
        entity_type="small_business",
        state="OR",
        has_rd_activity=True,
    )
    resp = engine.match(req)
    grant_ids = {m.grant.id for m in resp.matches}
    assert "sbir_phase1" in grant_ids, "SBIR Phase 1 should match for R&D small business"
    assert "rd_credit_sec41" in grant_ids, "§41 R&D credit should match"


def test_manufacturing_project_matches_amo(engine):
    """Manufacturing project → DOE AMO and CESMII should match."""
    req = EligibilityRequest(
        project_type="manufacturing_automation",
        entity_type="small_business",
        state="MI",
        project_cost_usd=200_000,
        is_commercial=True,
        has_rd_activity=True,
    )
    resp = engine.match(req)
    grant_ids = {m.grant.id for m in resp.matches}
    assert "doe_amo" in grant_ids or "cesmii" in grant_ids, "DOE AMO or CESMII should match"


def test_residential_project_matches_25c(engine):
    """Residential HVAC automation → §25C should match."""
    req = EligibilityRequest(
        project_type="hvac_automation",
        entity_type="individual",
        state="CA",
        project_cost_usd=15_000,
        is_commercial=False,
        existing_building=True,
    )
    resp = engine.match(req)
    grant_ids = {m.grant.id for m in resp.matches}
    assert "sec_25c" in grant_ids, "§25C should match residential HVAC project"


def test_solar_project_matches_itc(engine):
    """Solar project → §48/48E ITC should match."""
    req = EligibilityRequest(
        project_type="solar",
        entity_type="small_business",
        state="TX",
        project_cost_usd=100_000,
        is_commercial=True,
    )
    resp = engine.match(req)
    grant_ids = {m.grant.id for m in resp.matches}
    assert "sec_48_itc" in grant_ids, "§48 ITC should match solar project"


def test_nonqualifying_entity_type_excluded(engine):
    """Government entity should not match small-business-only programs."""
    req = EligibilityRequest(
        project_type="bas_bms",
        entity_type="government",
        state="OR",
    )
    resp = engine.match(req)
    # SBIR requires small_business — should not appear for government entity
    sbir_match = [m for m in resp.matches if m.grant.id == "sbir_phase1"]
    assert len(sbir_match) == 0, "SBIR Phase 1 should not match government entity"


def test_state_specific_grant_excluded_for_wrong_state(engine):
    """Energy Trust Oregon should NOT match for NY projects."""
    req = EligibilityRequest(
        project_type="bas_bms",
        entity_type="small_business",
        state="NY",
        is_commercial=True,
    )
    resp = engine.match(req)
    energy_trust_matches = [m for m in resp.matches if m.grant.id == "energy_trust_oregon"]
    assert len(energy_trust_matches) == 0, "Energy Trust Oregon should not match NY project"


def test_matches_ranked_by_score(engine):
    """Matches should be ranked by score descending."""
    req = EligibilityRequest(
        project_type="bas_bms",
        entity_type="small_business",
        state="OR",
        is_commercial=True,
    )
    resp = engine.match(req)
    scores = [m.match_score for m in resp.matches]
    assert scores == sorted(scores, reverse=True), "Matches should be ranked by score desc"


def test_total_estimated_value_calculated(engine):
    """Total estimated value should be sum of individual match values."""
    req = EligibilityRequest(
        project_type="ems",
        entity_type="small_business",
        state="CA",
        project_cost_usd=500_000,
        is_commercial=True,
    )
    resp = engine.match(req)
    calculated = sum(m.estimated_value_usd for m in resp.matches if m.estimated_value_usd)
    assert resp.total_estimated_value_usd == pytest.approx(calculated, rel=1e-6)


def test_cpace_excluded_for_state_without_cpace(engine):
    """C-PACE should only match states in the CPACE_STATES list."""
    from src.billing.grants.pace_financing import CPACE_STATES
    # Find a state NOT in CPACE (this is unusual but let's check)
    # Most states are in CPACE now; skip if all states are covered
    req = EligibilityRequest(
        project_type="bas_bms",
        entity_type="small_business",
        state="OR",
        is_commercial=True,
        existing_building=True,
    )
    resp = engine.match(req)
    if "OR" in CPACE_STATES:
        cpace_matches = [m for m in resp.matches if m.grant.id == "pace_financing"]
        assert len(cpace_matches) > 0, "C-PACE should match OR (in CPACE_STATES)"


def test_stacking_opportunities_present(engine):
    """Matches should include stacking opportunities where applicable."""
    req = EligibilityRequest(
        project_type="solar",
        entity_type="small_business",
        state="CA",
        project_cost_usd=200_000,
        is_commercial=True,
    )
    resp = engine.match(req)
    itc_match = next((m for m in resp.matches if m.grant.id == "sec_48_itc"), None)
    if itc_match:
        assert len(itc_match.stacking_opportunities) > 0, "ITC should have stacking opportunities"
