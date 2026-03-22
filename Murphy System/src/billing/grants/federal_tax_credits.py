"""
Federal Tax Credits — IRA §179D, §48/48E, §48C, §25C, §25D, §45/45Y, §41 R&D.

All credits carry 10+ year longevity (through 2032 or permanent).
IRA bonus multiplier metadata included for each applicable credit.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, GrantCategory, GrantIRABonus, GrantTrack

# ---------------------------------------------------------------------------
# §179D — Commercial Building Energy Efficiency Deduction
# ---------------------------------------------------------------------------
SEC_179D = Grant(
    id="sec_179d",
    name="§179D Commercial Building Energy Efficiency Tax Deduction",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.TRACK_B,
    short_description="Up to $5.00/sq ft deduction for energy-efficient commercial buildings.",
    long_description=(
        "IRC §179D provides a federal income tax deduction for commercial building owners "
        "and designers who install energy-efficient interior lighting, HVAC/hot water systems, "
        "or building envelope improvements. After the Inflation Reduction Act (IRA), the "
        "base deduction is $0.50/sq ft (25 % energy savings vs. ASHRAE 90.1) scaling to "
        "$1.00/sq ft (50 % savings). With prevailing-wage and apprenticeship requirements "
        "met, the deduction jumps to $2.50–$5.00/sq ft. Effective for property placed in "
        "service after Dec 31 2022; the IRA extended this credit indefinitely with no "
        "scheduled expiry. Building automation systems (BAS/BMS) and EMS upgrades that "
        "improve HVAC performance and lighting controls qualify."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/businesses/179d-commercial-buildings-energy-efficiency-tax-deduction",
    application_url="https://www.irs.gov/pub/irs-pdf/f7205.pdf",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="$0.50–$5.00 per sq ft; prevailing wage multiplier applies",
    eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "building_envelope"],
    requires_existing_building=True,
    requires_commercial=True,
    is_recurring=True,
    longevity_note="Permanent after IRA 2022 — no scheduled expiry",
    stackable_with=["sec_48_itc", "utility_custom_incentive"],
    ira_bonus=GrantIRABonus(
        prevailing_wage=True,
        direct_pay_eligible=False,
        transferable=False,
    ),
    tags=["ira", "tax_deduction", "commercial", "building_automation", "energy_efficiency"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §48 / §48E — Investment Tax Credit (ITC)
# ---------------------------------------------------------------------------
SEC_48_ITC = Grant(
    id="sec_48_itc",
    name="§48 / §48E Investment Tax Credit (ITC) for Clean Energy",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.BOTH,
    short_description="6–70% tax credit for clean energy installations including battery storage, solar, geothermal, fuel cells.",
    long_description=(
        "IRC §48 (technology-specific) and §48E (technology-neutral, effective 2025+) provide "
        "investment tax credits for qualified energy property. Base credit: 6 % (without prevailing "
        "wage/apprenticeship) or 30 % (with PW/A). Bonus adders available: +10 % energy community, "
        "+10 % domestic content, +10–20 % low-income community (§48E only). Maximum potential: 70 %. "
        "Grid-interactive building controls, smart inverters, battery energy storage systems (BESS), "
        "EV charging, and demand-response automation platforms that are part of qualifying energy "
        "systems are eligible. §48E transitions §48 for facilities that begin construction after "
        "Dec 31 2024 and is available through 2032 (with phase-down if clean electricity capacity "
        "goals are met). Direct pay available to tax-exempt entities."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/credits-deductions/businesses/investment-tax-credit",
    application_url="https://www.irs.gov/pub/irs-pdf/f3468.pdf",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="6–70% of eligible project cost",
    eligible_entity_types=["small_business", "corporation", "nonprofit", "individual", "government"],
    eligible_project_types=["ems", "battery_storage", "solar", "geothermal", "fuel_cell", "ev_charging", "demand_response", "grid_interactive"],
    requires_commercial=False,
    is_recurring=True,
    program_expiry_year=2032,
    longevity_note="§48E through 2032+ with phase-down tied to clean electricity capacity targets",
    stackable_with=["sec_179d", "sec_48c", "sec_45y_ptc", "pace_financing", "utility_custom_incentive"],
    ira_bonus=GrantIRABonus(
        prevailing_wage=True,
        energy_community=True,
        domestic_content=True,
        low_income=True,
        direct_pay_eligible=True,
        transferable=True,
    ),
    tags=["ira", "itc", "solar", "battery_storage", "clean_energy", "direct_pay"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §48C — Qualifying Advanced Energy Project Credit
# ---------------------------------------------------------------------------
SEC_48C = Grant(
    id="sec_48c",
    name="§48C Advanced Energy Project Credit",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.TRACK_A,
    short_description="Up to 30% credit for advanced energy manufacturing and industrial decarbonization projects.",
    long_description=(
        "IRC §48C provides a 30 % investment tax credit (or 6 % without prevailing wage) for "
        "qualifying advanced energy project facilities. The IRA allocated $10 B in new §48C "
        "credits ($4 B reserved for energy communities). Eligible projects include manufacturing "
        "or recycling facilities for clean energy equipment, industrial decarbonization, critical "
        "materials processing, and industrial efficiency equipment. For Murphy System / Inoni LLC, "
        "this credit applies to capital investments in manufacturing automation platforms, smart "
        "manufacturing infrastructure, and industrial IoT development facilities. Applications are "
        "submitted to IRS/DOE via a competitive allocation process."
    ),
    agency_or_provider="IRS / DOE",
    program_url="https://www.energy.gov/eere/iedo/section-48c-qualifying-advanced-energy-project-credit",
    application_url="https://www.irs.gov/credits-deductions/businesses/advanced-energy-project-credit-section-48c",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="6% (no PW) or 30% (with PW/apprenticeship) of qualified investment",
    eligible_entity_types=["small_business", "corporation"],
    eligible_project_types=["manufacturing_automation", "smart_manufacturing", "industrial_iot", "clean_energy_manufacturing"],
    requires_commercial=True,
    requires_rd_activity=False,
    is_recurring=True,
    longevity_note="Ongoing IRA allocation; competitive application process",
    stackable_with=["rd_credit_sec41", "state_rd_credits"],
    ira_bonus=GrantIRABonus(
        prevailing_wage=True,
        energy_community=True,
        domestic_content=False,
        direct_pay_eligible=False,
        transferable=True,
    ),
    tags=["ira", "manufacturing", "industrial_decarbonization", "competitive", "advanced_energy"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §25D — Residential Clean Energy Credit
# ---------------------------------------------------------------------------
SEC_25D = Grant(
    id="sec_25d",
    name="§25D Residential Clean Energy Credit",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.TRACK_B,
    short_description="30% tax credit for residential solar, battery storage, geothermal, and fuel cell installations through 2032.",
    long_description=(
        "IRC §25D provides a 30 % non-refundable credit for homeowners installing qualified clean "
        "energy property: solar electric, solar water heating, small wind, geothermal heat pumps, "
        "battery storage (≥3 kWh), and fuel cells. The IRA extended this credit at 30 % through "
        "2032, then phases down to 26 % (2033) and 22 % (2034). Home energy management systems "
        "(HEMS) and smart home automation that are directly integrated with qualifying clean energy "
        "equipment may qualify as part of the system cost. Murphy's residential smart energy "
        "management capabilities position it as an eligible system component."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/credits-deductions/residential-clean-energy-credit",
    application_url="https://www.irs.gov/pub/irs-pdf/f5695.pdf",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="30% of cost through 2032; 26% in 2033; 22% in 2034",
    eligible_entity_types=["individual"],
    eligible_project_types=["solar", "battery_storage", "geothermal", "fuel_cell", "small_wind", "home_energy_management"],
    requires_existing_building=False,
    requires_commercial=False,
    is_recurring=True,
    program_expiry_year=2034,
    longevity_note="IRA extended through 2032 at full 30%; phase-down 2033-2034",
    stackable_with=["sec_25c", "heehra_rebate", "utility_custom_incentive"],
    ira_bonus=GrantIRABonus(direct_pay_eligible=False),
    tags=["ira", "residential", "solar", "battery_storage", "homeowner"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §25C — Energy Efficient Home Improvement Credit
# ---------------------------------------------------------------------------
SEC_25C = Grant(
    id="sec_25c",
    name="§25C Energy Efficient Home Improvement Credit",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.TRACK_B,
    short_description="30% credit up to $3,200/yr for heat pumps, insulation, windows, and smart thermostats.",
    long_description=(
        "IRC §25C (as amended by the IRA) provides a 30 % annual credit capped at $3,200/year "
        "for residential energy efficiency improvements. Sub-limits: $2,000/yr for heat pumps "
        "and heat pump water heaters; $1,200/yr for insulation, windows, doors, and electrical "
        "upgrades (including smart panel upgrades, EV chargers). Smart thermostats and home "
        "energy management systems directly connected to qualifying HVAC equipment can qualify "
        "as part of the system cost. Applies to existing homes only. No lifetime cap (annual cap "
        "resets each year). Murphy's home automation BAS controls including thermostat integration "
        "and HVAC optimization qualify as part of a heat pump system."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/credits-deductions/energy-efficient-home-improvement-credit",
    application_url="https://www.irs.gov/pub/irs-pdf/f5695.pdf",
    min_amount_usd=None,
    max_amount_usd=3200,
    value_description="30% of costs; $3,200/yr cap ($2,000 for heat pumps; $1,200 for envelope/electrical)",
    eligible_entity_types=["individual"],
    eligible_project_types=["hvac_automation", "home_energy_management", "smart_thermostat", "heat_pump", "insulation"],
    requires_existing_building=True,
    requires_commercial=False,
    is_recurring=True,
    longevity_note="Annual credit; resets each tax year; no scheduled expiry in IRA",
    stackable_with=["sec_25d", "heehra_rebate", "utility_custom_incentive"],
    tags=["ira", "residential", "hvac", "smart_thermostat", "heat_pump", "home_improvement"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §45 / §45Y — Production Tax Credit (PTC)
# ---------------------------------------------------------------------------
SEC_45Y_PTC = Grant(
    id="sec_45y_ptc",
    name="§45 / §45Y Clean Electricity Production Tax Credit (PTC)",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.BOTH,
    short_description="Per-kWh production credit for wind, solar, and clean electricity generation through 2032+.",
    long_description=(
        "IRC §45 (technology-specific) and §45Y (technology-neutral, effective 2025+) provide a "
        "per-kilowatt-hour production tax credit for qualifying clean electricity facilities. "
        "Base rate: $0.003/kWh (without PW/A), or $0.015/kWh with prevailing wage and "
        "apprenticeship requirements. Energy community bonus: +10%. Domestic content: +10%. "
        "Low-income community: +10–20%. §45Y phases out when the U.S. achieves 75% clean "
        "electricity — estimated 2032+. Advanced metering, demand response systems, grid "
        "optimization software, and energy management platforms supporting qualifying generation "
        "facilities can be included in facility costs. Direct pay available for non-taxpayers."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/credits-deductions/businesses/clean-electricity-production-credit-45y",
    application_url="https://www.irs.gov/pub/irs-pdf/f8835.pdf",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="$0.003–$0.030/kWh depending on bonuses",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=["wind", "solar", "hydro", "geothermal", "demand_response", "grid_interactive", "ems"],
    is_recurring=True,
    program_expiry_year=2032,
    longevity_note="§45Y through 2032+ with capacity-based phase-down trigger",
    stackable_with=["sec_48_itc", "utility_custom_incentive"],
    ira_bonus=GrantIRABonus(
        prevailing_wage=True,
        energy_community=True,
        domestic_content=True,
        low_income=True,
        direct_pay_eligible=True,
        transferable=True,
    ),
    tags=["ira", "ptc", "production_credit", "wind", "solar", "clean_electricity"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# HEEHRA / HOMES Rebates
# ---------------------------------------------------------------------------
HEEHRA_REBATE = Grant(
    id="heehra_rebate",
    name="HEEHRA / HOMES State-Administered Electrification Rebates",
    category=GrantCategory.FEDERAL_TAX_CREDIT,
    track=GrantTrack.TRACK_B,
    short_description="Up to $8,000 for heat pump HVAC; up to $14,000 total for electrification upgrades. State-administered.",
    long_description=(
        "The High-Efficiency Electric Home Rebate Act (HEEHRA) and HOMES (Home Owner Managing "
        "Energy Savings) programs — part of the IRA — allocate $4.5 B and $4.3 B respectively "
        "for state-administered residential electrification rebates. HEEHRA: up to $8,000 for "
        "heat pump HVAC, $1,750 for heat pump water heater, $840 for electric range/dryer, "
        "$4,000 for electrical panel upgrade, $2,500 for electrical wiring, $1,600 for "
        "insulation/air sealing. HOMES: performance-based rebates scaled by energy savings "
        "(50%+ savings → $4,000–$8,000 per household). Income limits apply to rebate amounts. "
        "Smart controls and building automation that enable qualifying equipment to achieve "
        "modeled performance levels contribute to eligibility. Programs roll out state-by-state."
    ),
    agency_or_provider="State Energy Offices (funded by DOE)",
    program_url="https://www.energystar.gov/about/federal_tax_credits/2023-ira-rebates",
    application_url=None,
    min_amount_usd=840,
    max_amount_usd=14000,
    value_description="Up to $14,000 total; varies by income and equipment type",
    eligible_entity_types=["individual"],
    eligible_project_types=["hvac_automation", "heat_pump", "smart_thermostat", "electrical_upgrade", "home_energy_management"],
    requires_existing_building=False,
    requires_commercial=False,
    is_recurring=True,
    longevity_note="IRA-funded; state-administered rollout ongoing through 2031+",
    stackable_with=["sec_25c", "sec_25d", "utility_custom_incentive"],
    tags=["ira", "residential", "rebate", "heat_pump", "state_administered", "income_based"],
    last_updated="2024-01",
)

# ---------------------------------------------------------------------------
# §41 — R&D Tax Credit
# ---------------------------------------------------------------------------
RD_CREDIT_SEC41 = Grant(
    id="rd_credit_sec41",
    name="§41 Federal Research & Development Tax Credit",
    category=GrantCategory.RD_TAX_CREDIT,
    track=GrantTrack.TRACK_A,
    short_description="6.5–20% credit on qualifying R&D expenditures. Permanent credit. Key for Murphy/Inoni LLC.",
    long_description=(
        "IRC §41 provides a permanent federal tax credit for increasing qualified research "
        "expenditures (QREs). Two calculation methods: (1) Regular Credit = 20% of QREs above "
        "base amount; (2) Alternative Simplified Credit (ASC) = 14% of QREs above 50% of avg "
        "prior 3 years (6% if no prior-year QREs). QREs include wages, supplies, and 65% of "
        "contract research for activities meeting the 4-part test: (a) permitted purpose, "
        "(b) technological in nature, (c) elimination of technical uncertainty, (d) process of "
        "experimentation. Murphy System / Inoni LLC's development of multi-LLM routing, "
        "confidence-gated execution (G/D/H scoring), agentic AI orchestration, Causality "
        "Sandbox, Wingman Protocol, and self-improvement engine all qualify as QREs. "
        "The R&D credit can offset payroll taxes for qualified small businesses (up to $500K/yr), "
        "making it available even before profitability. Permanent — no expiry."
    ),
    agency_or_provider="IRS / U.S. Department of the Treasury",
    program_url="https://www.irs.gov/credits-deductions/businesses/research-credit",
    application_url="https://www.irs.gov/pub/irs-pdf/f6765.pdf",
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="6.5–20% of qualified research expenditures (QREs); up to $500K/yr payroll tax offset",
    eligible_entity_types=["small_business", "corporation", "startup"],
    eligible_project_types=["ai_platform", "software_rd", "automation_rd", "industrial_iot", "manufacturing_automation"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Permanent — codified in IRC; no scheduled expiry",
    stackable_with=["sbir_phase1", "sbir_phase2", "state_rd_credits", "sec_48c"],
    tags=["permanent", "rd", "payroll_tax_offset", "startup_friendly", "track_a"],
    last_updated="2024-01",
)


def get_federal_tax_credits() -> list:
    """Return all federal tax credit grant objects."""
    return [
        SEC_179D,
        SEC_48_ITC,
        SEC_48C,
        SEC_25D,
        SEC_25C,
        SEC_45Y_PTC,
        HEEHRA_REBATE,
        RD_CREDIT_SEC41,
    ]
