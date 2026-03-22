"""
SBA Financing Programs — Microloans, 7(a), and 504 loan programs.

These are debt-based (not grants) but are key financing options for small
businesses purchasing or building automation systems in the $5K–$5M range.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

SBA_MICROLOAN = Grant(
    id="sba_microloan",
    name="SBA Microloan Program",
    category=GrantCategory.SBA_FINANCING,
    track=GrantTrack.TRACK_B,
    short_description="Up to $50K for small businesses and startups. Flexible underwriting. Avg loan: $13K.",
    long_description=(
        "The SBA Microloan Program provides small loans through SBA-approved nonprofit "
        "intermediaries. Maximum loan: $50,000; average: $13,000. Terms up to 6 years. "
        "Interest rates: 8–13%. No SBA guarantee fee. Lenders often provide business training "
        "and technical assistance. Best for: startups, micro-businesses, businesses that "
        "can't qualify for traditional bank loans. For Murphy customers in the $5K–$50K "
        "automation range, microloans cover a full deployment with reasonable monthly payments. "
        "Oregon intermediaries: Mercy Corps NW, Craft3, Oregon CDC. Murphy's BAS/BMS, EMS, "
        "or small-scale SCADA deployments fit the microloan sweet spot."
    ),
    agency_or_provider="U.S. Small Business Administration (SBA)",
    program_url="https://www.sba.gov/funding-programs/loans/microloans",
    application_url="https://www.sba.gov/funding-programs/loans/microloans#section-header-1",
    min_amount_usd=500,
    max_amount_usd=50_000,
    value_description="Up to $50K; avg $13K; 6-year terms; 8-13% interest",
    eligible_entity_types=["small_business", "nonprofit", "startup"],
    eligible_project_types=[
        "bas_bms", "ems", "general_business_automation", "manufacturing_automation",
        "smart_building", "scada",
    ],
    is_recurring=True,
    longevity_note="Permanent SBA program",
    stackable_with=["rd_credit_sec41", "sec_179d", "utility_custom_incentive"],
    tags=["sba", "loan", "microloan", "startup_friendly", "track_b", "financing"],
    last_updated="2024-01",
)

SBA_7A = Grant(
    id="sba_7a",
    name="SBA 7(a) Loan Program",
    category=GrantCategory.SBA_FINANCING,
    track=GrantTrack.TRACK_B,
    short_description="Up to $5M SBA-guaranteed loans for working capital, equipment, and business expansion.",
    long_description=(
        "The SBA 7(a) loan program is the SBA's primary lending program. Loans up to $5M "
        "with SBA guaranteeing up to 85% ($150K and under) or 75% (over $150K). Terms: up to "
        "10 years for working capital/equipment; up to 25 years for real estate. Interest rates: "
        "Prime + 2.25–4.75% (negotiated with lender). Use of proceeds: working capital, "
        "machinery/equipment, furniture, leasehold improvements, business acquisition, refinancing. "
        "SBA Express: up to $500K with 36-hour turnaround. For Murphy customers, 7(a) covers "
        "larger automation deployments ($50K–$500K) including full BAS/SCADA system builds, "
        "manufacturing automation integrations, and multi-site EMS deployments. The 'green' "
        "SBA 7(a) for energy improvements offers enhanced terms."
    ),
    agency_or_provider="U.S. Small Business Administration (SBA)",
    program_url="https://www.sba.gov/funding-programs/loans/7a-loans",
    application_url="https://www.sba.gov/funding-programs/loans/7a-loans#section-header-1",
    min_amount_usd=5_000,
    max_amount_usd=5_000_000,
    value_description="Up to $5M; 75-85% SBA guaranteed; 10-25 year terms",
    eligible_entity_types=["small_business"],
    eligible_project_types=[
        "bas_bms", "ems", "scada", "manufacturing_automation", "general_business_automation",
        "industrial_iot", "smart_building",
    ],
    is_recurring=True,
    longevity_note="Permanent SBA program",
    stackable_with=["sec_179d", "sec_48_itc", "utility_custom_incentive", "pace_financing"],
    tags=["sba", "loan", "7a", "equipment", "working_capital", "track_b", "financing"],
    last_updated="2024-01",
)

SBA_504 = Grant(
    id="sba_504",
    name="SBA 504 Loan Program (CDC/504)",
    category=GrantCategory.SBA_FINANCING,
    track=GrantTrack.TRACK_B,
    short_description="Up to $5.5M ($5M for most; up to $5.5M for manufacturing/energy) for fixed assets at below-market rates.",
    long_description=(
        "SBA 504 loans finance major fixed assets (real estate, heavy equipment, major "
        "machinery) at long-term, below-market interest rates. Structure: 50% from bank, "
        "40% from Certified Development Company (CDC) backed by SBA debenture, 10% from "
        "borrower. Standard limit: $5M; manufacturing projects or energy-efficient projects: "
        "$5.5M. Terms: 10, 20, or 25 years for real estate; 10 years for equipment. "
        "Interest: near Treasury rate (typically 3–6%). Green 504 (energy efficiency/renewables) "
        "allows multiple 504 loans up to $16.5M for qualifying projects. For Murphy customers "
        "deploying large-scale building automation, SCADA, or manufacturing automation, "
        "504 loans provide the lowest-cost long-term financing. Energy projects using Murphy's "
        "EMS for documented energy savings qualify for the Green 504 program."
    ),
    agency_or_provider="U.S. Small Business Administration (SBA) / Certified Development Companies",
    program_url="https://www.sba.gov/funding-programs/loans/504-loans",
    application_url="https://www.sba.gov/funding-programs/loans/504-loans#section-header-1",
    min_amount_usd=125_000,
    max_amount_usd=5_500_000,
    value_description="Up to $5.5M; 10% down; 10-25 year terms; near-Treasury rates",
    eligible_entity_types=["small_business"],
    eligible_project_types=[
        "bas_bms", "ems", "scada", "manufacturing_automation", "smart_building",
        "industrial_iot", "grid_interactive",
    ],
    requires_existing_building=True,
    is_recurring=True,
    longevity_note="Permanent SBA program; Green 504 for energy efficiency",
    stackable_with=["sec_179d", "sec_48_itc", "pace_financing", "ct_green_bank"],
    tags=["sba", "loan", "504", "green_504", "fixed_assets", "below_market_rate", "track_b", "financing"],
    last_updated="2024-01",
)


def get_sba_financing() -> list:
    """Return all SBA financing program objects."""
    return [SBA_MICROLOAN, SBA_7A, SBA_504]
