"""
Utility Programs — Demand response, custom incentives, on-bill financing.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

UTILITY_DEMAND_RESPONSE = Grant(
    id="utility_demand_response",
    name="Utility Demand Response Programs",
    category=GrantCategory.UTILITY_PROGRAM,
    track=GrantTrack.TRACK_B,
    short_description="$50–$200/kW/year for enrolled controllable load. Automated DR via Murphy's EMS/BAS integration.",
    long_description=(
        "Demand response (DR) programs pay commercial and industrial customers to reduce or "
        "shift electricity load during grid stress events. Murphy's BAS/BMS and EMS capabilities "
        "enable automated DR participation without manual intervention. Typical payments: "
        "$50–$200/kW/year for capacity commitment; additional energy payments during events. "
        "Major programs: PJM (Mid-Atlantic), CAISO (California), ERCOT (Texas), MISO (Midwest), "
        "SPP (Central), ISO-NE (New England). Local utilities often have their own DR programs "
        "with direct incentives. For Murphy customers, the ROI calculation: a 100 kW enrolled "
        "building generates $5,000–$20,000/year in DR revenue — often paying for the BAS "
        "automation investment in 2–3 years. Murphy's real-time control capabilities and "
        "protocol integrations (BACnet, Modbus, OpenADR) are key enablers for automated DR."
    ),
    agency_or_provider="Regional Grid Operators (PJM, CAISO, ERCOT, MISO, ISO-NE) + Local Utilities",
    program_url="https://www.ferc.gov/industries-data/electric/power-sales-and-markets/demand-response",
    application_url=None,
    min_amount_usd=500,
    max_amount_usd=None,
    value_description="$50–$200/kW/yr capacity payment + energy payments during events",
    eligible_entity_types=["small_business", "corporation", "industrial"],
    eligible_project_types=["bas_bms", "ems", "demand_response", "grid_interactive", "hvac_automation"],
    requires_commercial=True,
    is_recurring=True,
    longevity_note="Grid DR markets are permanent and expanding under FERC Order 2222",
    stackable_with=["sec_48_itc", "sec_45y_ptc", "utility_custom_incentive", "energy_trust_oregon"],
    tags=["demand_response", "grid", "utility", "openadr", "bacnet", "automated_dr", "track_b"],
    last_updated="2024-01",
)

UTILITY_CUSTOM_INCENTIVE = Grant(
    id="utility_custom_incentive",
    name="Utility Custom Energy Efficiency Incentives",
    category=GrantCategory.UTILITY_PROGRAM,
    track=GrantTrack.TRACK_B,
    short_description="$0.05–$0.25/kWh saved for custom energy efficiency projects with utility verification.",
    long_description=(
        "Most large U.S. utilities offer custom incentives for commercial and industrial "
        "energy efficiency projects that don't fit standard prescriptive programs. Custom "
        "incentives are paid per kWh of verified annual savings: typically $0.05–$0.25/kWh. "
        "A building automation project saving 100,000 kWh/year would generate $5,000–$25,000 "
        "in utility incentives. Process: (1) submit application with engineering estimate; "
        "(2) utility reviews and pre-approves incentive; (3) install and commission; "
        "(4) measurement & verification (M&V) of actual savings; (5) incentive payment. "
        "Murphy's built-in energy metering, M&V capabilities, and reporting make it easy to "
        "document savings for utility incentive applications. Key utilities with strong "
        "custom programs: PG&E (CA), ConEd (NY), ComEd (IL), Duke Energy, Xcel Energy, "
        "Puget Sound Energy (WA), PGE/Pacific Power (OR)."
    ),
    agency_or_provider="Varies by utility (PG&E, ConEd, ComEd, Duke, Xcel, PSE, PGE, Pacific Power, etc.)",
    program_url="https://www.energystar.gov/buildings/tools-and-resources/find-rebates",
    application_url=None,
    min_amount_usd=1_000,
    max_amount_usd=500_000,
    value_description="$0.05–$0.25/kWh saved; project-specific",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "industrial_iot", "demand_response"],
    requires_commercial=True,
    is_recurring=True,
    longevity_note="Utility efficiency programs mandated by state energy codes nationwide",
    stackable_with=["sec_179d", "sec_48_itc", "energy_trust_oregon", "nyserda", "pace_financing"],
    tags=["utility", "custom_incentive", "energy_efficiency", "measurement_verification", "track_b"],
    last_updated="2024-01",
)

UTILITY_ON_BILL_FINANCING = Grant(
    id="utility_on_bill_financing",
    name="Utility On-Bill Financing",
    category=GrantCategory.UTILITY_PROGRAM,
    track=GrantTrack.TRACK_B,
    short_description="0–3% interest financing for efficiency upgrades repaid through utility bill savings.",
    long_description=(
        "On-bill financing (OBF) allows commercial customers to install energy efficiency "
        "upgrades with 0–3% interest loans repaid through monthly utility bill savings. "
        "The key advantage: upgrades are cash-flow positive from day one (savings exceed "
        "loan payments). Loan amounts: $5K–$500K; terms 2–15 years. Available through "
        "utilities in many states: PSE&G NJ (up to $50K for small business), NYPA (NY), "
        "Puget Sound Energy (WA), Pacific Gas & Electric (CA), and many others. "
        "For Murphy customers, on-bill financing is ideal for BAS/BMS and EMS deployments "
        "with clear, measurable energy savings. Murphy's energy reporting can document "
        "projected savings for loan underwriting."
    ),
    agency_or_provider="Utility-specific programs (PSE&G, NYPA, PSE, PG&E, others)",
    program_url="https://www.aceee.org/topic/on-bill-financing",
    application_url=None,
    min_amount_usd=5_000,
    max_amount_usd=500_000,
    value_description="0–3% interest; cash-flow positive from day one",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "hvac_automation", "lighting_controls", "smart_building"],
    requires_commercial=False,
    is_recurring=True,
    longevity_note="On-bill programs expanding nationwide; permanent as utility programs",
    stackable_with=["utility_custom_incentive", "sec_179d", "sec_25c", "pace_financing"],
    tags=["on_bill_financing", "utility", "low_interest", "cash_flow_positive", "track_b", "financing"],
    last_updated="2024-01",
)


def get_utility_programs() -> list:
    """Return all utility program objects."""
    return [
        UTILITY_DEMAND_RESPONSE,
        UTILITY_CUSTOM_INCENTIVE,
        UTILITY_ON_BILL_FINANCING,
    ]
