"""
State Incentive Programs — NYSERDA, CEC, MassCEC, NJ Clean Energy, Energy Trust of Oregon,
plus a DSIRE integration stub for ZIP-code-based state/utility incentive lookup.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

# ---------------------------------------------------------------------------
# Energy Trust of Oregon
# ---------------------------------------------------------------------------
ENERGY_TRUST_OREGON = Grant(
    id="energy_trust_oregon",
    name="Energy Trust of Oregon — Cash Incentives",
    category=GrantCategory.STATE_INCENTIVE,
    track=GrantTrack.TRACK_B,
    short_description="Cash incentives for Oregon commercial and residential energy efficiency, solar, and controls upgrades.",
    long_description=(
        "Energy Trust of Oregon is an independent nonprofit funded by Oregon utility customers "
        "(PGE, Pacific Power, NW Natural, Cascade Natural Gas). Programs: (1) Commercial: cash "
        "incentives for HVAC, lighting, building controls, refrigeration, custom equipment "
        "upgrades ($0.10–$0.30/kWh saved for custom projects); (2) Industrial: custom process "
        "improvement incentives; (3) Solar: cash incentives for solar installations; "
        "(4) New Buildings: design assistance and incentives for high-performance buildings. "
        "For Murphy customers in Oregon: BAS/BMS upgrades, EMS deployment, demand response "
        "controls, and custom automation that reduces energy use qualify for cash incentives. "
        "Murphy's BAS integration with BACnet/OPC UA and its energy optimization capabilities "
        "are directly aligned with Energy Trust's custom commercial program."
    ),
    agency_or_provider="Energy Trust of Oregon",
    program_url="https://www.energytrust.org/",
    application_url="https://www.energytrust.org/work-with-us/contractors/",
    min_amount_usd=500,
    max_amount_usd=500_000,
    value_description="$0.10–$0.30/kWh saved; custom incentives up to $500K for large projects",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "solar", "industrial_iot"],
    eligible_states=["OR"],
    requires_commercial=False,
    is_recurring=True,
    longevity_note="Ongoing program funded by Oregon utility ratepayers; 20+ year history",
    stackable_with=["sec_179d", "sec_48_itc", "sec_25c", "utility_custom_incentive", "pace_financing"],
    tags=["oregon", "utility", "cash_incentive", "energy_efficiency", "bas_bms", "commercial"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# NYSERDA — New York State Energy Research and Development Authority
# ---------------------------------------------------------------------------
NYSERDA = Grant(
    id="nyserda",
    name="NYSERDA — NY State Clean Energy Programs",
    category=GrantCategory.STATE_INCENTIVE,
    track=GrantTrack.TRACK_B,
    short_description="New York State clean energy incentives: solar, storage, efficiency, EV, and building performance.",
    long_description=(
        "NYSERDA administers New York State's clean energy programs under NY's Climate Leadership "
        "and Community Protection Act (CLCPA) — the nation's most aggressive clean energy law. "
        "Programs: (1) NY-Sun: solar incentives for commercial and residential; (2) Clean "
        "Buildings: performance-based incentives for large commercial buildings (50K+ sq ft); "
        "(3) FlexTech: 50% cost-share for energy studies (up to $250K); (4) Clean Heating & "
        "Cooling: heat pump incentives; (5) ConEdison/PSEG/National Grid DR programs; "
        "(6) REV Demonstration projects for distributed energy. For Murphy customers in NY, "
        "BAS/BMS upgrades, demand response automation, and smart building controls all have "
        "available incentive pathways. NYSERDA also co-invests in clean energy companies "
        "through its NY Green Bank and Entrepreneurs Network."
    ),
    agency_or_provider="NYSERDA — New York State Energy Research and Development Authority",
    program_url="https://www.nyserda.ny.gov/",
    application_url="https://www.nyserda.ny.gov/All-Programs",
    min_amount_usd=1_000,
    max_amount_usd=250_000,
    value_description="Varies by program; FlexTech up to $250K; Clean Buildings performance-based",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "solar", "demand_response", "heat_pump", "smart_building"],
    eligible_states=["NY"],
    is_recurring=True,
    longevity_note="NY CLCPA mandates programs through 2050",
    stackable_with=["sec_179d", "sec_48_itc", "green_bank_loan", "pace_financing"],
    tags=["new_york", "nyserda", "clcpa", "clean_energy", "commercial", "demand_response"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# California Energy Commission (CEC)
# ---------------------------------------------------------------------------
CALIFORNIA_CEC = Grant(
    id="california_cec",
    name="California Energy Commission (CEC) — Clean Energy R&D and Deployment",
    category=GrantCategory.STATE_INCENTIVE,
    track=GrantTrack.BOTH,
    short_description="CEC grants for clean energy R&D, demonstration, and deployment. EPIC program: $130M+/yr.",
    long_description=(
        "The California Energy Commission's Electric Program Investment Charge (EPIC) program "
        "funds clean energy research, development, and demonstration with $130M+ annually. "
        "Key programs: (1) R&D grants for energy technology innovation ($500K–$5M); "
        "(2) Demonstration projects for advanced grid technologies; (3) Building Energy "
        "Efficiency Standards (Title 24) compliance programs; (4) CALCERTS and third-party "
        "verification programs. For Murphy System (Track A), CEC's grid-interactive building "
        "and AI-driven energy management R&D programs are strong matches. For California "
        "customers (Track B), CEC-funded utility programs, NEM solar incentives, "
        "Self-Generation Incentive Program (SGIP) for battery storage ($0.25/Wh), and "
        "demand response programs through CA utilities (PG&E, SCE, SDG&E) all apply. "
        "California's AB 32, SB 100, and Executive Order N-79-20 mandate clean energy "
        "programs through 2045."
    ),
    agency_or_provider="California Energy Commission (CEC)",
    program_url="https://www.energy.ca.gov/",
    application_url="https://efiling.energy.ca.gov/",
    min_amount_usd=500_000,
    max_amount_usd=5_000_000,
    value_description="R&D: $500K–$5M; SGIP: $0.25/Wh for battery storage",
    eligible_entity_types=["small_business", "corporation", "university", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "battery_storage", "solar", "grid_interactive", "demand_response", "ai_platform"],
    eligible_states=["CA"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="California clean energy mandates through 2045",
    stackable_with=["sec_48_itc", "sec_48c", "rd_credit_sec41", "pace_financing"],
    tags=["california", "cec", "epic", "sgip", "clean_energy", "rd", "track_a"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# MassCEC — Massachusetts Clean Energy Center
# ---------------------------------------------------------------------------
MASSCEC = Grant(
    id="masscec",
    name="MassCEC — Massachusetts Clean Energy Center",
    category=GrantCategory.STATE_INCENTIVE,
    track=GrantTrack.BOTH,
    short_description="Massachusetts clean energy incentives: solar, storage, offshore wind, and building efficiency.",
    long_description=(
        "MassCEC supports Massachusetts' clean energy industry through grants, incentives, "
        "and workforce programs. Key programs: (1) Offshore Wind Supply Chain Grant (up to "
        "$1M for manufacturers); (2) Clean Energy Internship Program; (3) Equitable "
        "Electrification Initiative; (4) Mass Save (utility-administered energy efficiency "
        "programs — one of the nation's best); (5) SMART Program for solar. Mass Save "
        "provides significant commercial incentives: HVAC upgrades, building controls, "
        "lighting, insulation. Custom incentives available for large commercial projects. "
        "For Murphy customers in Massachusetts, Mass Save's custom track for building "
        "automation and EMS upgrades offers substantial incentives."
    ),
    agency_or_provider="Massachusetts Clean Energy Center (MassCEC)",
    program_url="https://www.masscec.com/",
    application_url="https://www.masscec.com/programs",
    min_amount_usd=1_000,
    max_amount_usd=1_000_000,
    value_description="Varies; Mass Save up to $500K for custom commercial; offshore wind up to $1M",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "solar", "battery_storage", "smart_building"],
    eligible_states=["MA"],
    is_recurring=True,
    longevity_note="Massachusetts GWSA mandates clean energy programs through 2050",
    stackable_with=["sec_179d", "sec_48_itc", "green_bank_loan", "pace_financing"],
    tags=["massachusetts", "masscec", "mass_save", "clean_energy", "building_efficiency"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# New Jersey Clean Energy Program
# ---------------------------------------------------------------------------
NJ_CLEAN_ENERGY = Grant(
    id="nj_clean_energy",
    name="New Jersey Clean Energy Program (NJCEP)",
    category=GrantCategory.STATE_INCENTIVE,
    track=GrantTrack.TRACK_B,
    short_description="New Jersey utility-funded programs for solar, energy efficiency, and EV charging.",
    long_description=(
        "NJ's Clean Energy Program (NJCEP), administered by the NJ Board of Public Utilities, "
        "provides incentives for energy efficiency and renewable energy through utilities "
        "(PSE&G, JCP&L, Atlantic City Electric, Rockland Electric). Key programs: "
        "(1) Commercial & Industrial Direct Install: no-cost energy efficiency upgrades for "
        "small businesses (up to $100K in improvements); (2) Pay for Performance: incentives "
        "based on measured energy savings (large commercial/industrial); (3) Net Metering and "
        "TRECs for solar; (4) Transition Incentive Program (solar); (5) EV Fleet incentives. "
        "For Murphy customers in NJ, Direct Install covers lighting and HVAC controls; "
        "Pay for Performance covers BAS/EMS upgrades with measured savings verification. "
        "NJ's goal: 100% clean energy by 2035."
    ),
    agency_or_provider="NJ Board of Public Utilities / NJ Clean Energy Program",
    program_url="https://www.njcleanenergy.com/",
    application_url="https://www.njcleanenergy.com/commercial-industrial",
    min_amount_usd=0,
    max_amount_usd=100_000,
    value_description="Direct Install: up to $100K no-cost; Pay for Performance: based on savings",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "solar"],
    eligible_states=["NJ"],
    is_recurring=True,
    longevity_note="NJ 100% clean energy by 2035 mandate ensures long-term programs",
    stackable_with=["sec_179d", "sec_25c", "pace_financing"],
    tags=["new_jersey", "njcep", "direct_install", "utility", "energy_efficiency"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# DSIRE Integration Stub
# ---------------------------------------------------------------------------

def lookup_dsire_incentives(
    zip_code: str,
    project_types: Optional[List[str]] = None,
    entity_type: Optional[str] = None,
) -> Dict:
    """
    Stub for DSIRE (Database of State Incentives for Renewables & Efficiency) API lookup.

    DSIRE (dsireusa.org) is the nation's comprehensive database of state, utility,
    and local incentives. This stub will be replaced with live API integration
    once GRANT_DSIRE_API_KEY is configured.

    Args:
        zip_code: 5-digit US ZIP code
        project_types: List of project type strings (e.g., ['solar', 'ems'])
        entity_type: Entity type string (e.g., 'small_business')

    Returns:
        Dict with available programs or stub response if API key not configured.
    """
    import os
    api_key = os.environ.get("GRANT_DSIRE_API_KEY", "")
    if not api_key:
        return {
            "status": "stub",
            "message": (
                "DSIRE API key not configured. Set GRANT_DSIRE_API_KEY in .env "
                "to enable live ZIP-code-based incentive lookup. "
                "Manual lookup available at https://www.dsireusa.org/"
            ),
            "zip_code": zip_code,
            "dsire_url": f"https://www.dsireusa.org/resources/detailed-summary-maps/?zip={zip_code}",
            "programs": [],
        }

    # TODO: Implement live DSIRE API call when key is available
    # DSIRE API endpoint: https://programs.dsireusa.org/system/program
    # Parameters: zipCode, technology, sector
    return {
        "status": "not_implemented",
        "message": "Live DSIRE API integration pending implementation.",
        "zip_code": zip_code,
    }


# ---------------------------------------------------------------------------
# State incentive catalog
# ---------------------------------------------------------------------------
_STATE_INCENTIVES = [
    ENERGY_TRUST_OREGON,
    NYSERDA,
    CALIFORNIA_CEC,
    MASSCEC,
    NJ_CLEAN_ENERGY,
]


def get_state_incentives() -> list:
    """Return all state incentive program objects."""
    return list(_STATE_INCENTIVES)


def get_state_incentives_for_state(state_code: str) -> list:
    """Return state incentive programs applicable to a specific state (2-letter code)."""
    state_upper = state_code.upper()
    return [
        g for g in _STATE_INCENTIVES
        if not g.eligible_states or state_upper in g.eligible_states
    ]
