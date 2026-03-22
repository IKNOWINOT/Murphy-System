"""
C-PACE Financing — Commercial Property Assessed Clean Energy (38+ states).

C-PACE is property-assessed financing for commercial building energy, water,
and resiliency improvements. It's tied to the property (not the owner) and
repaid through property tax assessments over 10–30 years.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from typing import Dict, List

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

# States with active C-PACE programs (as of 2024)
CPACE_STATES: List[str] = [
    "AL", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "IL",
    "IN", "KS", "KY", "LA", "MD", "ME", "MI", "MN", "MO", "MT",
    "NC", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR",
    "PA", "RI", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WY",
]

# States with R-PACE programs for residential
RPACE_STATES: List[str] = ["CA", "FL", "MO"]

CPACE_FINANCING = Grant(
    id="pace_financing",
    name="C-PACE Commercial Property Assessed Clean Energy Financing",
    category=GrantCategory.PACE_FINANCING,
    track=GrantTrack.TRACK_B,
    short_description="100% financing for commercial energy efficiency, solar, and resiliency projects. 10–30yr terms. No out-of-pocket.",
    long_description=(
        "C-PACE provides 100% financing (no down payment) for commercial building energy "
        "efficiency, renewable energy, water conservation, and resiliency improvements. "
        "The loan is secured by a property tax lien and repaid through property tax "
        "assessments — it stays with the property if sold. Terms: 10–30 years. Rates: "
        "typically 5–9% fixed (better than most bank loans). No personal guarantee required. "
        "Available in 38+ states and Washington DC through C-PACE administrators: "
        "Counterpointe, PACE Equity, Nuveen Green Capital, Twain Financial, and others. "
        "Eligible improvements: HVAC systems, building automation (BAS/BMS), energy "
        "management systems (EMS), LED lighting, solar/storage, building envelope, EV "
        "charging, resiliency upgrades. For Murphy customers, C-PACE is ideal for large "
        "BAS/SCADA deployments ($100K–$10M) where the energy savings pay the assessment "
        "over 10–20 years. The building owner shows improved cash flow from day one when "
        "savings exceed assessment payments."
    ),
    agency_or_provider="State C-PACE Programs (Counterpointe, PACE Equity, Nuveen, Twain, others)",
    program_url="https://www.pacenation.org/",
    application_url="https://www.pacenation.org/pace-programs/",
    min_amount_usd=100_000,
    max_amount_usd=50_000_000,
    value_description="100% financing; no down payment; 10-30yr terms; 5-9% fixed",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=[
        "bas_bms", "ems", "hvac_automation", "solar", "battery_storage",
        "lighting_controls", "building_envelope", "ev_charging", "smart_building",
        "scada", "grid_interactive",
    ],
    eligible_states=CPACE_STATES,
    requires_existing_building=True,
    requires_commercial=True,
    is_recurring=True,
    longevity_note="C-PACE programs expanding; 38+ states active; permanent property-based financing",
    stackable_with=[
        "sec_179d", "sec_48_itc", "utility_custom_incentive",
        "energy_trust_oregon", "nyserda", "green_bank_loan", "sba_504",
    ],
    tags=["cpace", "property_assessed", "100_percent_financing", "no_down_payment", "commercial", "track_b", "financing"],
    last_updated="2024-01",
)


def get_pace_financing() -> list:
    """Return all C-PACE financing program objects."""
    return [CPACE_FINANCING]


def is_cpace_available(state_code: str) -> bool:
    """Check if C-PACE is available in a given state (2-letter code)."""
    return state_code.upper() in CPACE_STATES


def get_cpace_info(state_code: str) -> Dict:
    """Get C-PACE availability and contact info for a state."""
    state = state_code.upper()
    if state not in CPACE_STATES:
        return {
            "available": False,
            "state": state,
            "message": f"C-PACE is not yet available in {state}. Check https://www.pacenation.org for updates.",
        }

    # State-specific C-PACE program info
    state_programs: Dict[str, Dict] = {
        "CA": {"administrator": "CSCDA PACE, Ygrene, HERO", "url": "https://www.cscda.org/"},
        "NY": {"administrator": "NYCIDA, Sustainable CUNY, NY Green Bank", "url": "https://nyc.gov/pace"},
        "TX": {"administrator": "Texas PACE Authority, Lone Star PACE", "url": "https://texaspaceinaction.com/"},
        "FL": {"administrator": "Florida PACE Funding Agency", "url": "https://www.floridagreefinance.com/"},
        "CO": {"administrator": "Colorado PACE", "url": "https://coloradopace.org/"},
        "OR": {"administrator": "Oregon C-PACE (OEFA)", "url": "https://oregonpace.org/"},
        "WA": {"administrator": "Washington PACE", "url": "https://www.pacenation.org/pace-programs/"},
        "CT": {"administrator": "CT Green Bank C-PACE", "url": "https://ctgreenbank.com/c-pace/"},
        "NJ": {"administrator": "NJ C-PACE", "url": "https://www.njeda.com/"},
        "MD": {"administrator": "MD PACE", "url": "https://energy.maryland.gov/Pages/Business/Pace.aspx"},
    }

    info = state_programs.get(state, {
        "administrator": "Contact PACE Nation for local administrator",
        "url": "https://www.pacenation.org/pace-programs/",
    })

    return {
        "available": True,
        "state": state,
        "administrator": info.get("administrator"),
        "program_url": info.get("url"),
        "national_registry": "https://www.pacenation.org/pace-programs/",
    }
