"""Green bank financing programs for clean energy projects."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType

_MURPHY_VERTICALS = [
    "building_automation",
    "energy_management",
    "hvac_controls",
    "industrial_iot",
    "smart_manufacturing",
    "solar",
    "energy_storage",
]


def get_green_bank_grants() -> List[Grant]:
    """Return fully populated Grant objects for green bank financing programs."""
    return [
        Grant(
            id="ct_green_bank",
            name="CT Green Bank — Commercial Clean Energy Financing",
            program_type=ProgramType.green_bank,
            agency="Connecticut Green Bank",
            description=(
                "Connecticut's green bank provides low-cost financing and incentives for "
                "commercial clean energy and efficiency projects. C-PACE, Smart-E Loans, "
                "and commercial PACE programs cover Murphy System building automation, "
                "solar, storage, and HVAC controls for CT businesses."
            ),
            min_amount=5_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["CT"],
            application_url="https://ctgreenbank.com/",
            deadline_pattern="Rolling; multiple programs with ongoing enrollment",
            longevity_years=10,
            requirements=[
                "Connecticut location",
                "Qualifying clean energy or efficiency project",
                "Property assessment for C-PACE financing",
                "Creditworthiness review for Smart-E loans",
            ],
            tags=["connecticut", "green_bank", "cpace", "smart_e_loan"],
        ),
        Grant(
            id="ny_green_bank",
            name="NY Green Bank — Commercial & Industrial Financing",
            program_type=ProgramType.green_bank,
            agency="New York Green Bank (NYGB)",
            description=(
                "NY Green Bank provides wholesale financing to accelerate clean energy "
                "deployment in New York. Works through financial intermediaries to fund "
                "commercial building efficiency, distributed generation, and storage "
                "projects including Murphy System deployments."
            ),
            min_amount=1_000_000.0,
            max_amount=50_000_000.0,
            eligible_entity_types=["corporation", "small_business", "financial_institution"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["NY"],
            application_url="https://greenbank.ny.gov/",
            deadline_pattern="Rolling; through participating financial intermediaries",
            longevity_years=10,
            requirements=[
                "New York State project location",
                "Minimum transaction size $1M",
                "Clean energy or efficiency project",
                "Work through NYGB-approved financial partner",
                "Project financing plan required",
            ],
            tags=["new_york", "green_bank", "wholesale_financing", "large_projects"],
        ),
        Grant(
            id="nj_green_bank",
            name="NJ Infrastructure Bank — Clean Energy Financing",
            program_type=ProgramType.green_bank,
            agency="New Jersey Infrastructure Bank / NJ Clean Energy",
            description=(
                "New Jersey clean energy financing through NJ Infrastructure Bank and "
                "NJ Clean Energy programs. Covers commercial efficiency upgrades, "
                "solar, and combined heat & power. Murphy System controls integration "
                "qualifies as part of comprehensive energy projects."
            ),
            min_amount=10_000.0,
            max_amount=10_000_000.0,
            eligible_entity_types=["small_business", "corporation", "government", "nonprofit"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["NJ"],
            application_url="https://www.njib.gov/",
            deadline_pattern="Rolling; through NJ Infrastructure Bank loan programs",
            longevity_years=10,
            requirements=[
                "New Jersey location",
                "Qualifying clean energy infrastructure project",
                "Municipality or nonprofit applicants for some programs",
                "Creditworthiness review required",
            ],
            tags=["new_jersey", "infrastructure_bank", "clean_energy", "financing"],
        ),
        Grant(
            id="ca_green_finance",
            name="California Infrastructure & Economic Development Bank (IBank)",
            program_type=ProgramType.green_bank,
            agency="California IBank / CPCFA",
            description=(
                "California's IBank provides financing for infrastructure and economic "
                "development including clean energy projects. CPCFA (California Pollution "
                "Control Financing Authority) offers low-cost financing for qualifying "
                "environmental and clean energy projects including Murphy System deployments."
            ),
            min_amount=25_000.0,
            max_amount=20_000_000.0,
            eligible_entity_types=["small_business", "corporation", "government", "nonprofit"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["CA"],
            application_url="https://ibank.ca.gov/",
            deadline_pattern="Rolling; through IBank loan programs",
            longevity_years=10,
            requirements=[
                "California location",
                "Qualifying environmental or economic development project",
                "Small business program available for qualifying businesses",
                "Revenue bond financing available for larger projects",
            ],
            tags=["california", "ibank", "cpcfa", "infrastructure_financing"],
        ),
    ]
