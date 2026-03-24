"""
Grant Database — Unified catalog aggregating all grant programs.

All programs from federal_tax_credits, federal_grants, sba_financing,
usda_programs, state_incentives, utility_programs, pace_financing,
green_banks, espc, and rd_tax_credits.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.billing.grants.espc import get_espc_programs
from src.billing.grants.federal_grants import get_federal_grants
from src.billing.grants.federal_tax_credits import get_federal_tax_credits
from src.billing.grants.green_banks import get_green_banks
from src.billing.grants.models import Grant, GrantCategory, GrantTrack
from src.billing.grants.pace_financing import get_pace_financing
from src.billing.grants.rd_tax_credits import get_rd_tax_credits
from src.billing.grants.sba_financing import get_sba_financing
from src.billing.grants.state_incentives import get_state_incentives
from src.billing.grants.usda_programs import get_usda_programs
from src.billing.grants.utility_programs import get_utility_programs


def _build_catalog() -> Dict[str, Grant]:
    """Build the complete grant catalog, indexed by grant ID."""
    all_grants: List[Grant] = (
        get_federal_tax_credits()
        + get_federal_grants()
        + get_sba_financing()
        + get_usda_programs()
        + get_state_incentives()
        + get_utility_programs()
        + get_pace_financing()
        + get_green_banks()
        + get_espc_programs()
        + get_rd_tax_credits()
    )

    catalog: Dict[str, Grant] = {}
    for grant in all_grants:
        if grant.id in catalog:
            # Skip duplicates (e.g. rd_credit_sec41 appears in both modules)
            continue
        catalog[grant.id] = grant

    return catalog


# ---------------------------------------------------------------------------
# Module-level catalog (built once at import time)
# ---------------------------------------------------------------------------
GRANT_CATALOG: Dict[str, Grant] = _build_catalog()


def get_grant(grant_id: str) -> Optional[Grant]:
    """Return a grant by its ID, or None if not found."""
    return GRANT_CATALOG.get(grant_id)


def list_grants(
    category: Optional[GrantCategory] = None,
    track: Optional[GrantTrack] = None,
    state: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[Grant]:
    """
    List grants with optional filtering.

    Args:
        category: Filter by grant category.
        track: Filter by track (track_a, track_b, both).
        state: Filter by eligible state (2-letter code); pass None for all.
        tags: Filter to grants containing ALL specified tags.

    Returns:
        Filtered list of Grant objects.
    """
    grants = list(GRANT_CATALOG.values())

    if category is not None:
        grants = [g for g in grants if g.category == category]

    if track is not None:
        grants = [
            g for g in grants
            if g.track == track or g.track == GrantTrack.BOTH
        ]

    if state is not None:
        state_upper = state.upper()
        grants = [
            g for g in grants
            if not g.eligible_states or state_upper in g.eligible_states
        ]

    if tags:
        for tag in tags:
            grants = [g for g in grants if tag in g.tags]

    return grants


def get_catalog_stats() -> Dict:
    """Return summary statistics about the grant catalog."""
    catalog = GRANT_CATALOG
    by_category: Dict[str, int] = {}
    for grant in catalog.values():
        cat = grant.category.value
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total_programs": len(catalog),
        "by_category": by_category,
        "track_a_count": sum(1 for g in catalog.values() if g.track in (GrantTrack.TRACK_A, GrantTrack.BOTH)),
        "track_b_count": sum(1 for g in catalog.values() if g.track in (GrantTrack.TRACK_B, GrantTrack.BOTH)),
    }
