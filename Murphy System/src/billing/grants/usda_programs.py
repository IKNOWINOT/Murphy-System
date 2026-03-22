"""USDA rural energy and agricultural programs relevant to Murphy System."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType


def get_usda_grants() -> List[Grant]:
    """Return fully populated Grant objects for USDA programs."""
    return [
        Grant(
            id="usda_reap",
            name="USDA REAP — Rural Energy for America Program",
            program_type=ProgramType.usda_program,
            agency="U.S. Department of Agriculture — Rural Development",
            description=(
                "Grants and loan guarantees for agricultural producers and rural small "
                "businesses to purchase and install renewable energy systems and make "
                "energy efficiency improvements. Murphy System energy management and "
                "HVAC controls qualify as energy efficiency upgrades. Up to 50% cost-share "
                "for grants, up to 75% combined with loan guarantee."
            ),
            min_amount=2_500.0,
            max_amount=1_000_000.0,
            eligible_entity_types=["small_business", "agricultural_producer"],
            eligible_verticals=[
                "energy_management",
                "hvac_controls",
                "building_automation",
                "smart_manufacturing",
            ],
            eligible_states=[],
            application_url="https://www.rd.usda.gov/programs-services/energy-programs/rural-energy-america-program-renewable-energy-systems-energy-efficiency-improvement-guaranteed-loans",
            deadline_pattern="Annual; typically March/September for grants, rolling for loans",
            longevity_years=10,
            requirements=[
                "Rural location required (non-metro area)",
                "Agricultural producer or rural small business",
                "Energy audit required for efficiency projects > $80K",
                "Technical report required",
                "SAM.gov registration for grants",
                "Match funding encouraged",
            ],
            tags=["usda", "reap", "rural", "energy_efficiency", "cost_share", "renewable"],
        ),
    ]
