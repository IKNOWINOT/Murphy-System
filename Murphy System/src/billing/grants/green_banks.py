"""
State Green Bank Programs — CT Green Bank, NY Green Bank, NJ IBank, CA IBank, and others.

Green banks use public funds to attract private investment in clean energy projects,
filling the gap where traditional financing falls short.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from src.billing.grants.models import Grant, GrantCategory, GrantTrack

CT_GREEN_BANK = Grant(
    id="ct_green_bank",
    name="Connecticut Green Bank",
    category=GrantCategory.GREEN_BANK,
    track=GrantTrack.TRACK_B,
    short_description="Connecticut's state green bank: C-PACE, solar financing, clean energy loans for commercial and residential.",
    long_description=(
        "The Connecticut Green Bank (CGB) is the nation's first state green bank, created "
        "in 2011. Programs: (1) Commercial C-PACE (CT PACE): 100% financing for commercial "
        "energy efficiency and clean energy; (2) Residential Solar Loan program; "
        "(3) Smart-E Loan: 0–3.49% loans for residential efficiency and clean energy "
        "($5K–$40K, up to 12 years); (4) Green Liberty Bonds: bonds financing clean energy "
        "projects. CT Green Bank has deployed $2.6B+ in clean energy investment. For Murphy "
        "customers in Connecticut, CT PACE is the primary path for commercial BAS/BMS and "
        "EMS deployments. CGB also co-invests with private lenders for larger projects."
    ),
    agency_or_provider="Connecticut Green Bank",
    program_url="https://ctgreenbank.com/",
    application_url="https://ctgreenbank.com/programs/",
    min_amount_usd=5_000,
    max_amount_usd=10_000_000,
    value_description="C-PACE: 100% financing; Smart-E: $5K–$40K at 0–3.49%",
    eligible_entity_types=["small_business", "corporation", "individual", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "solar", "heat_pump", "battery_storage", "smart_building", "hvac_automation"],
    eligible_states=["CT"],
    is_recurring=True,
    longevity_note="Permanent state institution; nation's first green bank",
    stackable_with=["sec_179d", "sec_48_itc", "sec_25c", "pace_financing"],
    tags=["connecticut", "green_bank", "cpace", "low_interest", "commercial", "residential"],
    last_updated="2024-01",
)

NY_GREEN_BANK = Grant(
    id="ny_green_bank",
    name="NY Green Bank (NYSERDA)",
    category=GrantCategory.GREEN_BANK,
    track=GrantTrack.TRACK_B,
    short_description="New York's $1B+ green bank: wholesale financing for clean energy project developers and lenders.",
    long_description=(
        "NY Green Bank, a division of NYSERDA, is a $1B+ state-capitalized, specialized "
        "financial entity that accelerates private investment in clean energy. NY Green Bank "
        "provides wholesale financing (not direct to end-users): senior debt, subordinated "
        "debt, letters of credit, and equity co-investments to clean energy project developers, "
        "contractors, and lenders. For Murphy customers, NY Green Bank finances are accessed "
        "through participating lenders and clean energy developers who use NY Green Bank "
        "wholesale facilities to offer competitive retail clean energy financing. NY Green "
        "Bank has deployed $4B+ in financing. NY Comptroller's office oversees operations."
    ),
    agency_or_provider="NY Green Bank (NYSERDA division)",
    program_url="https://greenbank.ny.gov/",
    application_url="https://greenbank.ny.gov/Working-With-Us/How-to-Work-With-Us",
    min_amount_usd=1_000_000,
    max_amount_usd=100_000_000,
    value_description="Wholesale financing; accessed through participating lenders",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "solar", "battery_storage", "grid_interactive", "smart_building"],
    eligible_states=["NY"],
    is_recurring=True,
    longevity_note="Permanent state institution under NYSERDA; CLCPA funded",
    stackable_with=["sec_48_itc", "nyserda", "pace_financing"],
    tags=["new_york", "green_bank", "wholesale_financing", "large_projects"],
    last_updated="2024-01",
)

NJ_IBANK = Grant(
    id="nj_ibank",
    name="New Jersey Infrastructure Bank (NJIB) Clean Energy Financing",
    category=GrantCategory.GREEN_BANK,
    track=GrantTrack.TRACK_B,
    short_description="NJ state financing for clean energy infrastructure; low-cost loans for commercial and municipal projects.",
    long_description=(
        "The New Jersey Infrastructure Bank (NJIB) provides low-cost financing for NJ "
        "infrastructure projects including clean energy. Programs include: Clean Energy "
        "Loan Program (sub-market rates for qualifying commercial projects), environmental "
        "infrastructure loans, and the NJ Clean Energy Fund financing programs. NJ also "
        "operates a C-PACE program through NJEDA. For Murphy customers in NJ, NJIB provides "
        "a bridge between grant incentives (NJCEP) and commercial financing at favorable rates. "
        "Combined with NJCEP Direct Install and federal tax credits, NJ offers one of the "
        "nation's most comprehensive clean energy financing stacks."
    ),
    agency_or_provider="New Jersey Infrastructure Bank (NJIB) / NJEDA",
    program_url="https://www.njib.gov/",
    application_url="https://www.njib.gov/programs",
    min_amount_usd=100_000,
    max_amount_usd=50_000_000,
    value_description="Sub-market rates; project-specific",
    eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
    eligible_project_types=["bas_bms", "ems", "solar", "battery_storage", "smart_building"],
    eligible_states=["NJ"],
    is_recurring=True,
    longevity_note="Permanent state institution",
    stackable_with=["nj_clean_energy", "sec_48_itc", "pace_financing"],
    tags=["new_jersey", "green_bank", "infrastructure", "low_interest"],
    last_updated="2024-01",
)

CA_IBANK = Grant(
    id="ca_ibank",
    name="California Infrastructure and Economic Development Bank (IBank) Clean Energy",
    category=GrantCategory.GREEN_BANK,
    track=GrantTrack.TRACK_B,
    short_description="California IBank: small business loan guarantees and clean energy project financing.",
    long_description=(
        "California's IBank provides financing for infrastructure and economic development "
        "projects, including clean energy. Key programs: (1) Small Business Loan Guarantee "
        "Program: guarantees up to 80% of loans from $50K to $2.5M for small businesses; "
        "(2) Infrastructure State Revolving Fund (ISRF): low-cost loans for public agencies "
        "and nonprofits; (3) Climate Catalyst Fund: clean energy and climate resilience. "
        "For Murphy customers in California, IBank's small business loan guarantee reduces "
        "the risk for lenders offering automation financing, enabling access to capital for "
        "businesses that might not qualify for conventional loans. Combined with SGIP, CPUC "
        "programs, and federal IRA credits, California offers exceptional clean energy "
        "financing stacking."
    ),
    agency_or_provider="California Infrastructure and Economic Development Bank (IBank)",
    program_url="https://www.ibank.ca.gov/",
    application_url="https://www.ibank.ca.gov/small-business/",
    min_amount_usd=50_000,
    max_amount_usd=2_500_000,
    value_description="Loan guarantee: up to 80% of $50K–$2.5M; ISRF: sub-market rates",
    eligible_entity_types=["small_business", "corporation", "nonprofit"],
    eligible_project_types=["bas_bms", "ems", "solar", "battery_storage", "smart_building", "manufacturing_automation"],
    eligible_states=["CA"],
    is_recurring=True,
    longevity_note="Permanent state institution; California clean energy mandates through 2045",
    stackable_with=["sec_48_itc", "california_cec", "pace_financing"],
    tags=["california", "ibank", "green_bank", "loan_guarantee", "small_business"],
    last_updated="2024-01",
)


def get_green_banks() -> list:
    """Return all state green bank program objects."""
    return [CT_GREEN_BANK, NY_GREEN_BANK, NJ_IBANK, CA_IBANK]
