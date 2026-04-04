"""
Test: Grant Database Integrity

Tests that all grants load correctly and have required fields.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.database import GRANT_CATALOG, get_catalog_stats, list_grants, get_grant
from src.billing.grants.models import Grant, GrantCategory, GrantTrack


def test_catalog_loads():
    """Catalog should contain programs from all source files."""
    assert len(GRANT_CATALOG) > 30, f"Expected 30+ grants, got {len(GRANT_CATALOG)}"


def test_all_grants_have_required_fields():
    """Every grant must have id, name, category, description, program_url."""
    for grant_id, grant in GRANT_CATALOG.items():
        assert grant.id, f"Grant missing id: {grant_id}"
        assert grant.name, f"Grant {grant_id} missing name"
        assert grant.category, f"Grant {grant_id} missing category"
        assert grant.short_description, f"Grant {grant_id} missing short_description"
        assert grant.long_description, f"Grant {grant_id} missing long_description"
        assert grant.program_url, f"Grant {grant_id} missing program_url"
        assert grant.agency_or_provider, f"Grant {grant_id} missing agency_or_provider"


def test_all_grant_ids_unique():
    """Grant IDs must be unique."""
    ids = list(GRANT_CATALOG.keys())
    assert len(ids) == len(set(ids)), "Duplicate grant IDs found"


def test_grant_ids_match_catalog_keys():
    """Each grant's .id must match its catalog key."""
    for key, grant in GRANT_CATALOG.items():
        assert grant.id == key, f"Grant id {grant.id!r} != catalog key {key!r}"


def test_program_urls_are_strings():
    """All program URLs must be non-empty strings."""
    for grant_id, grant in GRANT_CATALOG.items():
        assert isinstance(grant.program_url, str), f"Grant {grant_id} program_url not a string"
        assert grant.program_url.startswith("http"), f"Grant {grant_id} program_url invalid: {grant.program_url}"


def test_amount_bounds_valid():
    """Where amounts are set, min <= max."""
    for grant_id, grant in GRANT_CATALOG.items():
        if grant.min_amount_usd is not None and grant.max_amount_usd is not None:
            assert grant.min_amount_usd <= grant.max_amount_usd, (
                f"Grant {grant_id}: min_amount_usd ({grant.min_amount_usd}) > max_amount_usd ({grant.max_amount_usd})"
            )


def test_stackable_with_references_valid_grants():
    """stackable_with IDs should reference known grants (or be empty)."""
    known_ids = set(GRANT_CATALOG.keys())
    for grant_id, grant in GRANT_CATALOG.items():
        for ref in grant.stackable_with:
            assert ref in known_ids, (
                f"Grant {grant_id} references unknown stackable grant: {ref!r}"
            )


def test_catalog_has_all_categories():
    """Catalog should cover all GrantCategory values."""
    covered = {grant.category for grant in GRANT_CATALOG.values()}
    for category in GrantCategory:
        assert category in covered, f"No grants found for category {category.value}"


def test_catalog_has_track_a_and_track_b():
    """Both Track A and Track B programs should be present."""
    has_a = any(
        g.track in (GrantTrack.TRACK_A, GrantTrack.BOTH)
        for g in GRANT_CATALOG.values()
    )
    has_b = any(
        g.track in (GrantTrack.TRACK_B, GrantTrack.BOTH)
        for g in GRANT_CATALOG.values()
    )
    assert has_a, "No Track A (Murphy/Inoni) programs found"
    assert has_b, "No Track B (customer-facing) programs found"


def test_list_grants_filter_category():
    """list_grants with category filter returns only matching programs."""
    federal_grants = list_grants(category=GrantCategory.FEDERAL_GRANT)
    assert len(federal_grants) > 0
    for g in federal_grants:
        assert g.category == GrantCategory.FEDERAL_GRANT


def test_list_grants_filter_state():
    """list_grants with state filter excludes state-restricted grants."""
    ny_grants = list_grants(state="NY")
    # Should include national programs and NY-specific programs
    # Should NOT include OR-only programs
    or_only = [g for g in ny_grants if g.eligible_states == ["OR"]]
    assert len(or_only) == 0, "OR-only grants should not appear in NY filter"


def test_list_grants_filter_track():
    """list_grants with track filter returns correct programs."""
    track_a_grants = list_grants(track=GrantTrack.TRACK_A)
    for g in track_a_grants:
        assert g.track in (GrantTrack.TRACK_A, GrantTrack.BOTH)


def test_get_grant_by_id():
    """get_grant() returns the correct grant."""
    grant = get_grant("sbir_phase1")
    assert grant is not None
    assert grant.id == "sbir_phase1"
    assert grant.name == "SBIR Phase I — Proof of Concept"


def test_get_grant_missing_returns_none():
    """get_grant() returns None for unknown IDs."""
    assert get_grant("nonexistent_grant_xyz") is None


def test_catalog_stats():
    """get_catalog_stats() returns meaningful statistics."""
    stats = get_catalog_stats()
    assert stats["total_programs"] > 0
    assert stats["track_a_count"] > 0
    assert stats["track_b_count"] > 0
    assert "by_category" in stats


def test_key_grants_present():
    """Specific important grants must be in the catalog."""
    required_grants = [
        "sbir_phase1", "sbir_phase2", "sttr", "arpa_e",
        "sec_179d", "sec_48_itc", "sec_25c", "sec_25d", "sec_45y_ptc",
        "rd_credit_sec41", "state_rd_credits",
        "sba_microloan", "sba_7a", "sba_504",
        "usda_reap",
        "energy_trust_oregon", "nyserda", "california_cec",
        "utility_demand_response", "utility_custom_incentive",
        "pace_financing",
        "ct_green_bank", "ny_green_bank",
        "espc_federal", "espc_commercial",
        "doe_bto", "doe_amo", "cesmii", "nist_mep",
        "nsf_convergence_accelerator",
    ]
    for grant_id in required_grants:
        assert grant_id in GRANT_CATALOG, f"Required grant {grant_id!r} not found in catalog"
