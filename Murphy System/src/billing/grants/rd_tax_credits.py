"""R&D tax credit programs — federal §41 and state-level credits."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

_MURPHY_VERTICALS = [
    "agentic",
    "ai_ml",
    "software",
    "building_automation",
    "energy_management",
    "industrial_iot",
    "smart_manufacturing",
]

_SB_TYPES = ["small_business", "startup", "corporation"]


def get_rd_tax_credit_grants() -> List[Grant]:
    """Return fully populated Grant objects for R&D tax credit programs."""
    return [
        Grant(
            id="federal_rd_41",
            name="Federal R&D Tax Credit — §41 Research and Experimentation",
            program_type=ProgramType.rd_tax_credit,
            agency="IRS / U.S. Treasury",
            description=(
                "6.5–20% federal tax credit for qualified research expenses. "
                "Murphy System AI development, NL→DAG research, confidence-gated "
                "execution algorithms, and HITL system research all qualify as QREs. "
                "Startups can offset payroll taxes up to $500K/year."
            ),
            min_amount=5_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=[],
            application_url="https://www.irs.gov/businesses/small-businesses-self-employed/research-and-development-credit",
            deadline_pattern="Annual tax filing; 3-year lookback allowed",
            longevity_years=10,
            requirements=[
                "Qualified research activity under 4-part test",
                "Technology or process must be new to taxpayer",
                "Payroll tax offset for startups (< 5 years revenue, < $5M gross receipts)",
                "IRS Form 6765 required",
                "Documentation: time tracking, project records, payroll",
            ],
            tags=["r_and_d", "federal", "startup_friendly", "payroll_offset"],
        ),
        Grant(
            id="state_rd_or",
            name="Oregon R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="Oregon Department of Revenue",
            description=(
                "Oregon offers a 5% state R&D credit on qualified research expenses "
                "exceeding the prior-year Oregon QRE base amount. Stackable with "
                "federal §41 credit for Oregon-based technology companies like Murphy System."
            ),
            min_amount=1_000.0,
            max_amount=500_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["OR"],
            application_url="https://www.oregon.gov/dor/programs/businesses/Pages/credits.aspx",
            deadline_pattern="Annual Oregon state tax filing",
            longevity_years=10,
            requirements=[
                "Oregon business income tax liability",
                "Qualifying research conducted in Oregon",
                "Oregon Form OR-ASC-CORP required",
            ],
            tags=["oregon", "state_rd", "stackable"],
        ),
        Grant(
            id="state_rd_ca",
            name="California R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="California Franchise Tax Board",
            description=(
                "California offers a 15% R&D credit (24% for basic research) on "
                "qualified research expenses above a base period. One of the most "
                "generous state R&D credits, stackable with federal §41."
            ),
            min_amount=2_000.0,
            max_amount=1_000_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["CA"],
            application_url="https://www.ftb.ca.gov/file/business/credits/research.html",
            deadline_pattern="Annual California state tax filing",
            longevity_years=10,
            requirements=[
                "California corporation franchise or income tax",
                "Qualified research conducted in California",
                "California Form 3523 required",
            ],
            tags=["california", "state_rd", "generous", "stackable"],
        ),
        Grant(
            id="state_rd_ny",
            name="New York R&D Tax Credit (QETC)",
            program_type=ProgramType.rd_tax_credit,
            agency="New York State Department of Taxation and Finance",
            description=(
                "New York Qualified Emerging Technology Company (QETC) credits "
                "include R&D credit up to 9% of eligible expenses for qualifying "
                "technology companies. Murphy System qualifies as a QETC."
            ),
            min_amount=1_000.0,
            max_amount=500_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["NY"],
            application_url="https://www.tax.ny.gov/bus/ct/qetccredits.htm",
            deadline_pattern="Annual New York state tax filing",
            longevity_years=10,
            requirements=[
                "New York State business",
                "QETC qualification (R&D in emerging tech, < $10M gross receipts)",
                "New York Form CT-44 required",
            ],
            tags=["new_york", "state_rd", "qetc", "emerging_tech"],
        ),
        Grant(
            id="state_rd_tx",
            name="Texas R&D Tax Credit / Franchise Tax Exemption",
            program_type=ProgramType.rd_tax_credit,
            agency="Texas Comptroller of Public Accounts",
            description=(
                "Texas franchise tax credit for qualified R&D expenses or exemption "
                "election. 5% credit on qualifying R&D expenditures for Texas-based "
                "technology companies with franchise tax liability."
            ),
            min_amount=1_000.0,
            max_amount=500_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["TX"],
            application_url="https://comptroller.texas.gov/taxes/franchise/research-development-credit.php",
            deadline_pattern="Annual Texas franchise tax filing (May 15)",
            longevity_years=10,
            requirements=[
                "Texas franchise tax liability",
                "Qualified research activity conducted in Texas",
                "Texas Form 05-178 required",
            ],
            tags=["texas", "state_rd", "franchise_tax"],
        ),
        Grant(
            id="state_rd_ma",
            name="Massachusetts R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="Massachusetts Department of Revenue",
            description=(
                "Massachusetts offers a 10% R&D credit on qualified research expenses "
                "above the prior-year base. Unused credit can be carried forward 15 years. "
                "Stackable with federal §41 for Massachusetts technology companies."
            ),
            min_amount=1_000.0,
            max_amount=500_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["MA"],
            application_url="https://www.mass.gov/info-details/research-credit-for-corporations",
            deadline_pattern="Annual Massachusetts state tax filing",
            longevity_years=10,
            requirements=[
                "Massachusetts business income or excise tax",
                "Qualified research conducted in Massachusetts",
                "Massachusetts Schedule RC required",
            ],
            tags=["massachusetts", "state_rd", "carryforward", "stackable"],
        ),
        Grant(
            id="state_rd_ct",
            name="Connecticut R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="Connecticut Department of Revenue Services",
            description=(
                "Connecticut offers R&D tax credits including a 6% credit on "
                "qualified research expenses and additional credits for research "
                "at Connecticut universities. Supports Connecticut-based innovation."
            ),
            min_amount=500.0,
            max_amount=250_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["CT"],
            application_url="https://portal.ct.gov/DRS/Businesses/New-Business-Portal/Research-and-Development-Tax-Credit",
            deadline_pattern="Annual Connecticut state tax filing",
            longevity_years=10,
            requirements=[
                "Connecticut corporation business tax",
                "Qualified research conducted in Connecticut",
                "Connecticut Schedule RC required",
            ],
            tags=["connecticut", "state_rd"],
        ),
        Grant(
            id="state_rd_nj",
            name="New Jersey R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="New Jersey Division of Taxation",
            description=(
                "New Jersey offers a 10% R&D tax credit on qualified research "
                "expenses above the prior-year base amount. Unused credits can be "
                "carried forward 7 years."
            ),
            min_amount=500.0,
            max_amount=250_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["NJ"],
            application_url="https://www.njconsumeraffairs.gov/",
            deadline_pattern="Annual New Jersey state tax filing",
            longevity_years=10,
            requirements=[
                "New Jersey corporation business tax",
                "Qualified research conducted in New Jersey",
                "NJ Form 308 required",
            ],
            tags=["new_jersey", "state_rd", "carryforward"],
        ),
        Grant(
            id="state_rd_pa",
            name="Pennsylvania R&D Tax Credit",
            program_type=ProgramType.rd_tax_credit,
            agency="Pennsylvania Department of Community & Economic Development",
            description=(
                "Pennsylvania offers up to 10% R&D tax credit on qualified research "
                "expenses (20% for small businesses). Credit applied through annual "
                "DCED application process, stackable with federal §41."
            ),
            min_amount=500.0,
            max_amount=250_000.0,
            eligible_entity_types=_SB_TYPES,
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["PA"],
            application_url="https://dced.pa.gov/business-assistance/r-d-tax-credit/",
            deadline_pattern="Annual DCED application; typically September 15",
            longevity_years=10,
            requirements=[
                "Pennsylvania corporate net income tax liability",
                "Qualified research conducted in Pennsylvania",
                "Annual DCED application required (not auto-applied)",
                "Small business rate: 20% (< 250 PA employees)",
            ],
            tags=["pennsylvania", "state_rd", "small_business_bonus"],
        ),
    ]
