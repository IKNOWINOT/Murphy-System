"""Federal tax credits and rebate programs relevant to Murphy System."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

_MURPHY_VERTICALS = [
    "building_automation",
    "energy_management",
    "hvac_controls",
    "industrial_iot",
    "smart_manufacturing",
]


def get_federal_tax_credit_grants() -> List[Grant]:
    """Return fully populated Grant objects for federal tax credit programs."""
    return [
        Grant(
            id="tc_179d",
            name="§179D Commercial Buildings Energy Efficiency Tax Deduction",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "Tax deduction up to $5.00/sq ft for energy-efficient commercial "
                "buildings. Murphy System AI controls optimize HVAC, lighting, and "
                "envelope to qualify. Inflation Reduction Act enhanced the deduction "
                "and expanded eligibility to designers of government buildings."
            ),
            min_amount=10_000.0,
            max_amount=500_000.0,
            eligible_entity_types=["small_business", "corporation", "partnership", "nonprofit", "government"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.irs.gov/businesses/small-businesses-self-employed/deducting-business-expenses",
            deadline_pattern="Annual tax filing; no external deadline",
            longevity_years=10,
            requirements=[
                "Building must meet 50% energy cost savings threshold",
                "Qualified energy study by licensed engineer required",
                "Prevailing wage / apprenticeship requirements for full credit (post-2022)",
                "IRS Form 7205 required",
            ],
            tags=["ira", "energy_efficiency", "commercial_buildings", "hvac", "lighting"],
        ),
        Grant(
            id="tc_48_itc",
            name="§48/48E Investment Tax Credit (ITC) — Clean Energy",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "6–70% tax credit for investment in qualifying clean energy property "
                "including solar, storage, fuel cells, and grid-interactive systems. "
                "Murphy System controls qualify as integral part of qualifying property."
            ),
            min_amount=50_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=["small_business", "corporation", "partnership", "startup"],
            eligible_verticals=_MURPHY_VERTICALS + ["solar", "energy_storage", "microgrid"],
            eligible_states=[],
            application_url="https://www.irs.gov/credits-deductions/businesses/energy-investment-credit",
            deadline_pattern="Annual tax filing; credit percentage phases based on COD date",
            longevity_years=10,
            requirements=[
                "Qualifying clean energy property placed in service",
                "Prevailing wage and apprenticeship for >1MW projects",
                "Domestic content bonus available (+10%)",
                "Energy community bonus available (+10%)",
                "IRS Form 3468 required",
            ],
            tags=["ira", "itc", "solar", "storage", "clean_energy"],
        ),
        Grant(
            id="tc_48c",
            name="§48C Advanced Energy Project Credit",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / DOE",
            description=(
                "30% credit for advanced energy manufacturing and industrial "
                "decarbonization projects. Includes smart manufacturing facilities, "
                "grid-interactive industrial systems, and energy storage manufacturing. "
                "$10B allocated under IRA with at least $4B in energy communities."
            ),
            min_amount=100_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=["small_business", "corporation", "startup"],
            eligible_verticals=_MURPHY_VERTICALS + ["advanced_manufacturing", "cleantech"],
            eligible_states=[],
            application_url="https://www.energy.gov/oe/48c-program-guide",
            deadline_pattern="Competitive allocation rounds; check DOE for current round",
            longevity_years=10,
            requirements=[
                "Competitive application to DOE for allocation",
                "Project must re-equip, expand, or establish advanced energy manufacturing",
                "Prevailing wage and apprenticeship requirements",
                "IRS Form 3468 required after DOE allocation",
            ],
            tags=["ira", "advanced_manufacturing", "industrial_decarbonization", "competitive"],
        ),
        Grant(
            id="tc_25c",
            name="§25C Energy Efficient Home Improvement Credit",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "30% tax credit up to $3,200/year for homeowners installing qualifying "
                "energy-efficient improvements including heat pumps, smart thermostats, "
                "insulation, and windows. Murphy System smart thermostat integration qualifies."
            ),
            min_amount=300.0,
            max_amount=3_200.0,
            eligible_entity_types=["individual"],
            eligible_verticals=["hvac_controls", "building_automation", "energy_management"],
            eligible_states=[],
            application_url="https://www.irs.gov/credits-deductions/energy-efficient-home-improvement-credit",
            deadline_pattern="Annual tax filing; credit resets each year",
            longevity_years=10,
            requirements=[
                "Primary residence in the United States",
                "Qualifying products must meet efficiency standards",
                "Heat pump credit: up to $2,000; other items: up to $1,200",
                "IRS Form 5695 required",
            ],
            tags=["ira", "residential", "heat_pump", "smart_thermostat"],
        ),
        Grant(
            id="tc_25d",
            name="§25D Residential Clean Energy Credit",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "30% tax credit for residential solar, wind, geothermal, fuel cell, "
                "and battery storage installations. Murphy System residential energy "
                "management integrates with qualifying systems."
            ),
            min_amount=500.0,
            max_amount=50_000.0,
            eligible_entity_types=["individual"],
            eligible_verticals=["solar", "energy_storage", "energy_management"],
            eligible_states=[],
            application_url="https://www.irs.gov/credits-deductions/residential-clean-energy-credit",
            deadline_pattern="Annual tax filing; 30% through 2032, phases down after",
            longevity_years=10,
            requirements=[
                "Primary or secondary U.S. residence",
                "Qualifying clean energy equipment installed",
                "No maximum credit limit",
                "IRS Form 5695 required",
            ],
            tags=["ira", "residential", "solar", "battery_storage"],
        ),
        Grant(
            id="tc_45_ptc",
            name="§45/45Y Production Tax Credit (PTC) — Clean Energy",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "Per-kWh tax credit for electricity produced from qualifying clean "
                "energy facilities including wind, solar, geothermal, and other "
                "renewables. Murphy System grid-interactive controls enhance production "
                "optimization and monitoring."
            ),
            min_amount=10_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=["corporation", "partnership", "small_business"],
            eligible_verticals=_MURPHY_VERTICALS + ["solar", "wind", "grid_management"],
            eligible_states=[],
            application_url="https://www.irs.gov/credits-deductions/businesses/production-tax-credit",
            deadline_pattern="Annual tax filing; credit applies for 10 years post COD",
            longevity_years=10,
            requirements=[
                "Qualifying clean energy facility placed in service",
                "Prevailing wage and apprenticeship for >1MW",
                "Domestic content and energy community bonuses available",
                "IRS Form 8835 required",
            ],
            tags=["ira", "ptc", "wind", "solar", "production"],
        ),
        Grant(
            id="tc_41_rd",
            name="§41 R&D Tax Credit — Research and Experimentation",
            program_type=ProgramType.federal_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "6.5–20% tax credit for qualified research expenses including wages, "
                "supplies, and contract research. Murphy System AI development, "
                "algorithm improvements, and NL→DAG research qualify as QREs."
            ),
            min_amount=5_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=["small_business", "startup", "corporation"],
            eligible_verticals=_MURPHY_VERTICALS + ["ai_ml", "software", "robotics"],
            eligible_states=[],
            application_url="https://www.irs.gov/businesses/small-businesses-self-employed/research-and-development-credit",
            deadline_pattern="Annual tax filing; can be applied to payroll tax for startups",
            longevity_years=10,
            requirements=[
                "Qualified research activity under 4-part test",
                "Technology or process must be new to taxpayer",
                "Startup election available to offset payroll tax (up to $500K/yr)",
                "IRS Form 6765 required",
            ],
            tags=["r_and_d", "startup_friendly", "payroll_offset", "software_eligible"],
        ),
        Grant(
            id="rebate_heehra",
            name="HEEHRA — High-Efficiency Electric Home Rebate Act",
            program_type=ProgramType.federal_tax_credit,
            agency="DOE / State Energy Offices",
            description=(
                "Point-of-sale rebates for heat pumps, heat pump water heaters, "
                "and EV chargers. Income-qualified households receive higher rebates. "
                "Murphy System smart controls qualify for heat pump integration rebates."
            ),
            min_amount=840.0,
            max_amount=8_000.0,
            eligible_entity_types=["individual"],
            eligible_verticals=["hvac_controls", "building_automation"],
            eligible_states=[],
            application_url="https://www.energystar.gov/about/federal_tax_credits/high_efficiency_electric_home_rebate_act",
            deadline_pattern="Rolling; subject to state program launch dates",
            longevity_years=10,
            requirements=[
                "Income qualification: 80-150% area median income for partial rebate",
                "Primary U.S. residence",
                "Qualifying heat pump or appliance purchase",
                "Applied at point of sale through participating retailers",
            ],
            tags=["ira", "rebate", "residential", "heat_pump", "income_qualified"],
        ),
        Grant(
            id="rebate_homes",
            name="HOMES Rebate — Home Owner Managing Energy Savings",
            program_type=ProgramType.federal_tax_credit,
            agency="DOE / State Energy Offices",
            description=(
                "Rebates of up to $8,000 (or $4,000 standard) for whole-home energy "
                "efficiency improvements based on modeled or measured savings. Murphy "
                "System energy management and monitoring supports savings documentation."
            ),
            min_amount=2_000.0,
            max_amount=8_000.0,
            eligible_entity_types=["individual"],
            eligible_verticals=["energy_management", "building_automation", "hvac_controls"],
            eligible_states=[],
            application_url="https://www.energystar.gov/about/federal_tax_credits/home-efficiency-rebates",
            deadline_pattern="Rolling; subject to state program launch dates",
            longevity_years=10,
            requirements=[
                "Whole-home energy audit required",
                "20%+ modeled energy savings for standard rebate",
                "35%+ for enhanced rebate",
                "Income-qualified households receive 2x rebate",
                "State program must be active",
            ],
            tags=["ira", "rebate", "residential", "whole_home", "energy_audit"],
        ),
    ]
