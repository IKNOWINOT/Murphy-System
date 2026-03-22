"""Energy Savings Performance Contract (ESPC) programs."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType


def get_espc_grants() -> List[Grant]:
    """Return fully populated Grant objects for ESPC financing programs."""
    return [
        Grant(
            id="espc_federal",
            name="Federal ESPC — Energy Savings Performance Contract",
            program_type=ProgramType.espc,
            agency="DOE / FEMP (Federal Energy Management Program)",
            description=(
                "Federal agencies can procure energy improvements with no upfront cost "
                "through ESPCs. An Energy Service Company (ESCO) finances and implements "
                "improvements, repaid through guaranteed energy savings over up to 25 years. "
                "Murphy System can serve as the technology provider or subcontractor to "
                "ESCOs pursuing federal contracts. Super-ESPCs via DOE available for all "
                "federal agencies."
            ),
            min_amount=100_000.0,
            max_amount=50_000_000.0,
            eligible_entity_types=["government"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
                "smart_manufacturing",
            ],
            eligible_states=[],
            application_url="https://www.energy.gov/femp/energy-savings-performance-contracts-federal-agencies",
            deadline_pattern="No deadline; task order against Super-ESPC IDIQ contracts",
            longevity_years=15,
            requirements=[
                "Federal agency facility",
                "ESCO must be on DOE Super-ESPC IDIQ vehicle",
                "Investment grade audit (IGA) required",
                "Guaranteed savings must exceed annual payments",
                "M&V plan required per IPMVP",
                "Contract term up to 25 years",
            ],
            tags=["espc", "federal", "esco", "performance_contract", "no_upfront"],
        ),
        Grant(
            id="espc_commercial",
            name="Commercial ESPC — Energy Performance Contracting",
            program_type=ProgramType.espc,
            agency="ESCO / Energy Service Company",
            description=(
                "Commercial ESPCs allow businesses to upgrade building systems and "
                "equipment with no upfront capital, repaid through energy savings. "
                "Murphy System is a qualifying technology for ESCO-delivered projects "
                "including HVAC controls, building automation, and monitoring."
            ),
            min_amount=50_000.0,
            max_amount=10_000_000.0,
            eligible_entity_types=["corporation", "small_business", "nonprofit", "government"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
                "industrial_iot",
            ],
            eligible_states=[],
            application_url="https://www.naesco.org/",
            deadline_pattern="Rolling; through participating ESCO",
            longevity_years=15,
            requirements=[
                "Commercial or institutional building",
                "Energy savings opportunity identified",
                "Creditworthiness sufficient for ESCO financing",
                "M&V plan required",
                "ESCO guarantees savings performance",
                "Minimum project size varies by ESCO ($50K-$500K typical)",
            ],
            tags=["espc", "commercial", "esco", "performance_contract", "no_upfront"],
        ),
    ]
