"""
USDA Programs — REAP and rural development financing for automation projects.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

USDA_REAP = Grant(
    id="usda_reap",
    name="USDA REAP — Rural Energy for America Program",
    category=GrantCategory.USDA_PROGRAM,
    track=GrantTrack.TRACK_B,
    short_description="Up to 50% cost-share (25% grant + 25% loan guarantee) for renewable energy & energy efficiency in rural areas.",
    long_description=(
        "The Rural Energy for America Program (REAP) provides grants (up to 25% of eligible "
        "project costs, max $500K for energy efficiency) and loan guarantees (up to 75% of "
        "eligible project costs, max $25M) to agricultural producers and rural small businesses "
        "for renewable energy systems and energy efficiency improvements. IRA increased REAP "
        "funding to $2B+ and raised grant percentages. Eligible systems: solar, wind, biomass, "
        "geothermal, hydropower, ocean energy, hydrogen, energy efficiency upgrades. Building "
        "automation systems (BAS/BMS), energy management systems (EMS), HVAC controls, and "
        "lighting controls that demonstrably reduce energy use qualify as energy efficiency "
        "improvements. Must be located in rural area (population < 50,000). Murphy's BAS/EMS "
        "capabilities and demand response integrations are directly relevant for rural customers "
        "in agricultural, food processing, and rural manufacturing sectors."
    ),
    agency_or_provider="U.S. Department of Agriculture (USDA) Rural Development",
    program_url="https://www.rd.usda.gov/programs-services/energy-programs/rural-energy-america-program-renewable-energy-systems-energy-efficiency-improvement-guaranteed-loans-grants",
    application_url="https://www.rd.usda.gov/programs-services/energy-programs/rural-energy-america-program-renewable-energy-systems-energy-efficiency-improvement-guaranteed-loans-grants",
    min_amount_usd=2_500,
    max_amount_usd=500_000,
    value_description="Grant: up to 25% of project costs (max $500K); Loan guarantee: up to 75%",
    eligible_entity_types=["small_business", "agricultural_producer"],
    eligible_project_types=[
        "bas_bms", "ems", "hvac_automation", "solar", "wind", "biomass",
        "demand_response", "energy_efficiency", "lighting_controls",
    ],
    requires_commercial=True,
    is_recurring=True,
    longevity_note="IRA-expanded REAP funding through 2031+",
    stackable_with=["sec_48_itc", "sec_179d", "utility_custom_incentive", "sba_7a"],
    tags=["usda", "reap", "rural", "energy_efficiency", "agricultural", "grant_plus_loan", "track_b"],
    last_updated="2024-01",
)

USDA_RBEG = Grant(
    id="usda_rbeg",
    name="USDA Rural Business Enterprise Grant (RBEG) / RBDG",
    category=GrantCategory.USDA_PROGRAM,
    track=GrantTrack.TRACK_B,
    short_description="Grants to rural businesses and nonprofits for economic development, equipment, and technology.",
    long_description=(
        "USDA Rural Business Development Grants (RBDG, formerly RBEG) provide funding to "
        "rural nonprofit organizations, public bodies, and federally-recognized tribes to "
        "support small and emerging rural businesses. Funds can support: business incubators, "
        "technology-based economic development, feasibility studies, business plans, "
        "training programs, and equipment acquisition. For Murphy customers in rural areas, "
        "RBDG can fund the acquisition of automation technology (Murphy System licenses and "
        "hardware) when applied for by a local economic development organization on behalf "
        "of the rural business. Grants range from $10K to $500K. Rural areas: population "
        "under 50,000 for most programs."
    ),
    agency_or_provider="U.S. Department of Agriculture (USDA) Rural Development",
    program_url="https://www.rd.usda.gov/programs-services/business-programs/rural-business-development-grant-program",
    application_url="https://www.grants.gov/",
    min_amount_usd=10_000,
    max_amount_usd=500_000,
    value_description="$10K–$500K; through nonprofit/public body intermediary",
    eligible_entity_types=["nonprofit", "government", "small_business"],
    eligible_project_types=["general_business_automation", "manufacturing_automation", "agricultural_automation"],
    is_recurring=True,
    longevity_note="Permanent USDA program",
    stackable_with=["usda_reap", "sba_microloan"],
    tags=["usda", "rural", "business_development", "economic_development", "track_b"],
    last_updated="2024-01",
)


def get_usda_programs() -> list:
    """Return all USDA program objects."""
    return [USDA_REAP, USDA_RBEG]
