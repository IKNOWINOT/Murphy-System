"""
Energy Savings Performance Contracts (ESPC) — Federal and commercial models.

ESPC allows energy efficiency upgrades with zero upfront cost; the contractor
guarantees savings will cover all costs over the contract term.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

ESPC_FEDERAL = Grant(
    id="espc_federal",
    name="Energy Savings Performance Contracts (ESPC) — Federal Facilities",
    category=GrantCategory.ESPC,
    track=GrantTrack.TRACK_B,
    short_description="Zero-upfront-cost energy upgrades for federal facilities. ESCO guarantees savings cover all costs.",
    long_description=(
        "Federal ESPC (authorized by the Energy Policy Act of 1992) allows federal agencies "
        "to procure energy upgrades with no upfront appropriation. An Energy Service Company "
        "(ESCO) designs, finances, and installs improvements and guarantees that energy savings "
        "will cover all costs over the contract term (up to 25 years). FEMP (Federal Energy "
        "Management Program) administers the DOE-ESPC IDIQ contract — agencies can order "
        "directly from pre-qualified ESCOs without a new competitive procurement. Annual "
        "federal ESPC awards: $1–2B. For Murphy, this program creates a market: federal "
        "agencies using Murphy's BAS/BMS and EMS as components of ESPC projects. Murphy "
        "should partner with ESPC prime contractors (Ameresco, Johnson Controls, Honeywell, "
        "Schneider Electric, Siemens) as a technology subcontractor."
    ),
    agency_or_provider="DOE Federal Energy Management Program (FEMP)",
    program_url="https://www.energy.gov/femp/energy-savings-performance-contracts",
    application_url="https://www.energy.gov/femp/espc-resources-federal-agencies",
    min_amount_usd=500_000,
    max_amount_usd=50_000_000,
    value_description="Zero upfront cost; 10-25 year contracts; savings guaranteed by ESCO",
    eligible_entity_types=["government"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "solar", "demand_response"],
    requires_commercial=True,
    is_recurring=True,
    longevity_note="Federal law since 1992; permanent program",
    stackable_with=["sec_179d", "utility_custom_incentive"],
    tags=["espc", "federal", "esco", "zero_upfront", "government", "femp"],
    last_updated="2024-01",
)

ESPC_COMMERCIAL = Grant(
    id="espc_commercial",
    name="Commercial ESPC / Energy-as-a-Service (EaaS)",
    category=GrantCategory.ESPC,
    track=GrantTrack.TRACK_B,
    short_description="Performance-based financing for commercial buildings: ESCO pays for upgrades, recovers cost from verified savings.",
    long_description=(
        "Commercial ESPC and Energy-as-a-Service (EaaS) models provide zero-upfront energy "
        "upgrades for commercial buildings. The ESCO or EaaS provider finances and installs "
        "all improvements; the building owner pays a monthly fee from energy savings over "
        "7–20 years. After the contract, all savings accrue to the building owner. "
        "For commercial buildings with high energy bills ($100K+/year), ESPC/EaaS is "
        "often the best path for comprehensive building automation upgrades. Key providers: "
        "Ameresco, Johnson Controls, Honeywell, Siemens, Schneider Electric, Metrus Energy "
        "(EaaS), Transcend Equity (EaaS). Murphy's BAS/BMS and EMS capabilities make it "
        "ideal as the control layer in ESPC projects. Murphy can position itself as a "
        "preferred BAS subcontractor for ESPC prime contractors."
    ),
    agency_or_provider="ESCOs: Ameresco, Johnson Controls, Honeywell, Siemens, Schneider, Metrus",
    program_url="https://www.naesco.org/",
    application_url=None,
    min_amount_usd=100_000,
    max_amount_usd=20_000_000,
    value_description="Zero upfront cost; monthly savings-based payment; 7-20 year terms",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "smart_building"],
    requires_commercial=True,
    is_recurring=True,
    longevity_note="Growing EaaS market; permanent financing model",
    stackable_with=["utility_custom_incentive", "sec_179d", "pace_financing"],
    tags=["espc", "eaas", "commercial", "esco", "zero_upfront", "performance_based", "track_b"],
    last_updated="2024-01",
)


def get_espc_programs() -> list:
    """Return all ESPC program objects."""
    return [ESPC_FEDERAL, ESPC_COMMERCIAL]
