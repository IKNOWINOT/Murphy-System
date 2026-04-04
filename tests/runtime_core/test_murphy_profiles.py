"""
Test: Murphy Grant Profiles — All Flavors

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.murphy_profiles import (
    get_all_profiles,
    get_mvp_modules,
    get_profile,
)
from src.billing.grants.models import GrantFlavor
from src.billing.grants.database import GRANT_CATALOG


def test_all_four_profiles_present():
    """All four grant profile flavors must be present."""
    profiles = get_all_profiles()
    flavors = {p.flavor for p in profiles}
    assert GrantFlavor.RD in flavors
    assert GrantFlavor.ENERGY in flavors
    assert GrantFlavor.MANUFACTURING in flavors
    assert GrantFlavor.GENERAL in flavors


def test_each_profile_has_required_fields():
    """Each profile must have positioning, innovation narrative, and tech highlights."""
    for profile in get_all_profiles():
        assert profile.positioning, f"{profile.flavor} missing positioning"
        assert profile.innovation_narrative, f"{profile.flavor} missing innovation_narrative"
        assert profile.job_creation_narrative, f"{profile.flavor} missing job_creation_narrative"
        assert len(profile.relevant_modules) > 0, f"{profile.flavor} has no relevant_modules"
        assert len(profile.target_grants) > 0, f"{profile.flavor} has no target_grants"
        assert len(profile.naics_codes) > 0, f"{profile.flavor} has no naics_codes"
        assert len(profile.keywords) > 0, f"{profile.flavor} has no keywords"


def test_profile_target_grants_exist_in_catalog():
    """Each profile's target_grants must reference valid catalog entries."""
    for profile in get_all_profiles():
        for grant_id in profile.target_grants:
            assert grant_id in GRANT_CATALOG, (
                f"Profile {profile.flavor.value} references unknown grant: {grant_id!r}"
            )


def test_get_profile_by_flavor():
    """get_profile() returns the correct profile for each flavor."""
    for flavor in GrantFlavor:
        profile = get_profile(flavor)
        assert profile is not None, f"Profile for {flavor.value} not found"
        assert profile.flavor == flavor


def test_rd_profile_targets_sbir_and_rd_credit():
    """R&D profile must target SBIR and §41 R&D credit."""
    rd = get_profile(GrantFlavor.RD)
    assert "sbir_phase1" in rd.target_grants
    assert "rd_credit_sec41" in rd.target_grants


def test_energy_profile_targets_bas_grants():
    """Energy profile must target BAS/EMS-relevant grants."""
    energy = get_profile(GrantFlavor.ENERGY)
    bas_grants = {"doe_bto", "energy_trust_oregon", "sec_179d", "utility_demand_response"}
    overlap = bas_grants & set(energy.target_grants)
    assert len(overlap) > 0, "Energy profile should target BAS/EMS grants"


def test_manufacturing_profile_targets_amo_and_cesmii():
    """Manufacturing profile must target DOE AMO and/or CESMII."""
    mfg = get_profile(GrantFlavor.MANUFACTURING)
    assert "doe_amo" in mfg.target_grants or "cesmii" in mfg.target_grants


def test_general_profile_targets_sba_and_eda():
    """General profile should target SBA and EDA programs."""
    gen = get_profile(GrantFlavor.GENERAL)
    gen_grants = set(gen.target_grants)
    sba_eda = {"sba_microloan", "sba_7a", "eda_build_to_scale", "eda_tech_hubs"}
    overlap = sba_eda & gen_grants
    assert len(overlap) > 0, "General profile should include SBA or EDA grants"


def test_core_positioning_in_all_profiles():
    """The core positioning statement must appear in all profiles."""
    CORE_SNIPPET = "universal automation platform"
    for profile in get_all_profiles():
        assert CORE_SNIPPET in profile.positioning.lower(), (
            f"Profile {profile.flavor.value} missing core positioning statement"
        )


def test_get_mvp_modules_rd():
    """get_mvp_modules('rd') returns R&D relevant modules."""
    modules = get_mvp_modules("rd")
    assert len(modules) > 0
    # Should include something about multi-LLM or confidence
    content = " ".join(modules).lower()
    assert "llm" in content or "confidence" in content or "agentic" in content.lower()


def test_get_mvp_modules_energy():
    """get_mvp_modules('energy') returns energy-relevant modules."""
    modules = get_mvp_modules("energy")
    assert len(modules) > 0
    content = " ".join(modules).lower()
    assert "bacnet" in content or "ems" in content or "demand" in content


def test_get_mvp_modules_manufacturing():
    """get_mvp_modules('manufacturing') returns manufacturing-relevant modules."""
    modules = get_mvp_modules("manufacturing")
    assert len(modules) > 0
    content = " ".join(modules).lower()
    assert "opc" in content or "scada" in content or "modbus" in content


def test_get_mvp_modules_unknown_defaults_to_general():
    """get_mvp_modules with unknown type defaults to general modules."""
    modules = get_mvp_modules("unknown_type_xyz")
    assert len(modules) > 0  # Should return general modules, not empty
