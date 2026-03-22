"""SBA loan programs relevant to Murphy System and its customers."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

_MURPHY_VERTICALS = [
    "agentic",
    "building_automation",
    "energy_management",
    "hvac_controls",
    "industrial_iot",
    "smart_manufacturing",
]


def get_sba_financing_grants() -> List[Grant]:
    """Return fully populated Grant objects for SBA loan programs."""
    return [
        Grant(
            id="sba_microloan",
            name="SBA Microloan Program",
            program_type=ProgramType.sba_loan,
            agency="U.S. Small Business Administration",
            description=(
                "Low-interest microloans up to $50,000 for small businesses and "
                "certain nonprofit childcare centers. Ideal for Murphy System early "
                "customers needing small capital for technology adoption and hardware."
            ),
            min_amount=500.0,
            max_amount=50_000.0,
            eligible_entity_types=["small_business", "startup", "nonprofit"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sba.gov/funding-programs/loans/microloans",
            deadline_pattern="Rolling; through SBA-approved microlender",
            longevity_years=10,
            requirements=[
                "Must work through SBA-approved intermediary lender",
                "Cannot be used to pay existing debts",
                "Maximum term: 6 years",
                "Average interest rate: 8-13%",
                "May require business plan and collateral",
            ],
            tags=["sba", "microloan", "small_capital", "startup_friendly"],
        ),
        Grant(
            id="sba_7a",
            name="SBA 7(a) Loan Program",
            program_type=ProgramType.sba_loan,
            agency="U.S. Small Business Administration",
            description=(
                "SBA's primary loan program for working capital, equipment, real estate, "
                "and business expansion. Murphy System customers can use 7(a) loans to "
                "finance Murphy installation, hardware, and integration costs."
            ),
            min_amount=5_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=["small_business", "startup"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sba.gov/funding-programs/loans/7a-loans",
            deadline_pattern="Rolling; through SBA-approved lender",
            longevity_years=10,
            requirements=[
                "For-profit U.S. small business",
                "Operate in eligible industry",
                "Owner equity investment required",
                "Cannot get credit elsewhere on reasonable terms",
                "SBA Form 1919 and lender forms required",
            ],
            tags=["sba", "7a", "general_purpose", "equipment", "working_capital"],
        ),
        Grant(
            id="sba_504",
            name="SBA 504 Loan — Fixed Assets & Energy Efficiency",
            program_type=ProgramType.sba_loan,
            agency="U.S. Small Business Administration / CDC",
            description=(
                "Long-term, fixed-rate financing for major fixed assets like real estate "
                "and equipment. Energy efficiency projects qualify for special 504 terms. "
                "Ideal for Murphy System building automation infrastructure deployments."
            ),
            min_amount=25_000.0,
            max_amount=5_500_000.0,
            eligible_entity_types=["small_business"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.sba.gov/funding-programs/loans/504-loans",
            deadline_pattern="Rolling; through SBA-approved Certified Development Company",
            longevity_years=10,
            requirements=[
                "Net worth less than $15M; average net income < $5M",
                "Project must create or retain jobs or meet public policy goal",
                "Energy efficiency projects can qualify for higher limits",
                "Borrower contributes 10% equity minimum",
                "CDC covers 40%, bank covers 50% of project",
            ],
            tags=["sba", "504", "fixed_assets", "energy_efficiency", "long_term"],
        ),
    ]
