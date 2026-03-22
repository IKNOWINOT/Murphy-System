"""C-PACE (Commercial Property Assessed Clean Energy) financing programs."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

#: States with active C-PACE programs as of 2024.
PACE_ELIGIBLE_STATES: List[str] = [
    "AL", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
    "IA", "ID", "IL", "IN", "KY", "LA", "MD", "ME", "MI", "MN",
    "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV",
    "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
    "UT", "VA", "VT", "WA", "WI", "WV", "WY",
]


def get_pace_financing_grants() -> List[Grant]:
    """Return fully populated Grant objects for C-PACE financing programs."""
    return [
        Grant(
            id="cpace",
            name="C-PACE — Commercial Property Assessed Clean Energy Financing",
            program_type=ProgramType.pace_financing,
            agency="State / Local PACE Administrator",
            description=(
                "Long-term (10-30 year) fixed-rate financing for commercial building "
                "energy efficiency, renewable energy, water conservation, and seismic "
                "improvements. Repaid as property tax assessment — keeps debt off "
                "balance sheet. Murphy System building automation and controls are a "
                "qualifying PACE measure in all active-state programs. "
                f"Available in {len(PACE_ELIGIBLE_STATES)} states and DC."
            ),
            min_amount=10_000.0,
            max_amount=10_000_000.0,
            eligible_entity_types=["corporation", "small_business", "nonprofit", "government"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
                "solar",
                "energy_storage",
            ],
            eligible_states=PACE_ELIGIBLE_STATES,
            application_url="https://pacenation.org/find-a-pace-program/",
            deadline_pattern="Rolling; through local PACE administrator or lender",
            longevity_years=10,
            requirements=[
                "Commercial property (not residential 1-4 unit)",
                "Property must be in PACE-enabled jurisdiction",
                "Mortgage holder consent may be required",
                "Qualifying energy efficiency or clean energy measure",
                "Property must have sufficient equity / LTV",
                "PACE lien takes senior position (check lender requirements)",
            ],
            tags=[
                "cpace",
                "off_balance_sheet",
                "long_term",
                "property_tax",
                "no_upfront_cost",
                "commercial",
            ],
        ),
    ]
