"""State-level incentive programs and DSIRE integration stub."""

from __future__ import annotations

import logging
from typing import List

from src.billing.grants.models import Grant, ProgramType

logger = logging.getLogger(__name__)

_MURPHY_VERTICALS = [
    "agentic",
    "building_automation",
    "energy_management",
    "hvac_controls",
    "industrial_iot",
    "smart_manufacturing",
]


def get_state_incentive_grants() -> List[Grant]:
    """Return fully populated Grant objects for state incentive programs."""
    return [
        Grant(
            id="etor",
            name="Energy Trust of Oregon — Commercial / Industrial Incentives",
            program_type=ProgramType.state_incentive,
            agency="Energy Trust of Oregon",
            description=(
                "Cash incentives for Oregon businesses reducing energy use through "
                "qualifying upgrades. Murphy System HVAC controls, building automation, "
                "and energy monitoring qualify for custom and prescriptive incentives."
            ),
            min_amount=500.0,
            max_amount=1_000_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["OR"],
            application_url="https://www.energytrust.org/incentives/business/",
            deadline_pattern="Rolling; subject to annual budget availability",
            longevity_years=10,
            requirements=[
                "Oregon utility customer (PGE, Pacific Power, NW Natural, Cascade Natural Gas)",
                "Pre-approval required before project start",
                "Qualifying energy efficiency measures",
                "M&V protocol may be required for custom projects",
            ],
            tags=["oregon", "utility_incentive", "commercial", "custom_incentive"],
        ),
        Grant(
            id="nyserda",
            name="NYSERDA — Clean Energy Programs for Businesses",
            program_type=ProgramType.state_incentive,
            agency="New York State Energy Research and Development Authority",
            description=(
                "Incentives, financing, and technical assistance for New York businesses "
                "adopting clean energy. Murphy System qualifies under FlexTech consulting, "
                "Clean Energy Fund commercial programs, and NY-Sun integration."
            ),
            min_amount=5_000.0,
            max_amount=2_000_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
            eligible_verticals=_MURPHY_VERTICALS + ["solar", "energy_storage"],
            eligible_states=["NY"],
            application_url="https://www.nyserda.ny.gov/businesses",
            deadline_pattern="Rolling; multiple program cycles per year",
            longevity_years=10,
            requirements=[
                "New York State location",
                "Qualifying clean energy or efficiency project",
                "FlexTech: independent technical study required",
                "PON or RFP response for larger projects",
            ],
            tags=["nyserda", "new_york", "flextech", "clean_energy_fund"],
        ),
        Grant(
            id="cec",
            name="California Energy Commission — Business Incentives",
            program_type=ProgramType.state_incentive,
            agency="California Energy Commission",
            description=(
                "CEC funding for clean energy technology deployment, R&D, and market "
                "transformation in California. Murphy System smart building and industrial "
                "IoT applications qualify under EPIC and GFO programs."
            ),
            min_amount=25_000.0,
            max_amount=5_000_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "university"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["CA"],
            application_url="https://www.energy.ca.gov/programs-and-topics/programs",
            deadline_pattern="GFO-specific; check CEC website for active funding opportunities",
            longevity_years=10,
            requirements=[
                "California nexus required",
                "Match funding typically required (50%+)",
                "Response to active GFO solicitation",
                "Reporting and deliverable requirements",
            ],
            tags=["california", "cec", "epic", "gfo", "clean_energy"],
        ),
        Grant(
            id="masscec",
            name="MassCEC / Mass Save — Commercial & Industrial Programs",
            program_type=ProgramType.state_incentive,
            agency="Massachusetts Clean Energy Center / Mass Save",
            description=(
                "Massachusetts incentives for businesses reducing energy use and adopting "
                "clean energy. Murphy System controls qualify under Mass Save custom "
                "incentive programs and MassCEC clean energy deployment programs."
            ),
            min_amount=1_000.0,
            max_amount=1_000_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["MA"],
            application_url="https://www.masssave.com/business/rebates-and-incentives",
            deadline_pattern="Rolling; program cycles vary by utility and program year",
            longevity_years=10,
            requirements=[
                "Massachusetts utility customer",
                "Pre-approval before project start",
                "Licensed contractor installation required for most measures",
                "Energy audit may be required",
            ],
            tags=["massachusetts", "mass_save", "masscec", "utility_incentive"],
        ),
        Grant(
            id="njce",
            name="NJ Clean Energy — Business Energy Incentive Program",
            program_type=ProgramType.state_incentive,
            agency="New Jersey Board of Public Utilities / NJ Clean Energy",
            description=(
                "New Jersey incentives for businesses investing in energy efficiency and "
                "clean energy. Murphy System smart controls, LED controls integration, "
                "and HVAC optimization qualify for Direct Install and custom incentives."
            ),
            min_amount=500.0,
            max_amount=500_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "government"],
            eligible_verticals=_MURPHY_VERTICALS,
            eligible_states=["NJ"],
            application_url="https://www.njcleanenergy.com/commercial-industrial/programs",
            deadline_pattern="Rolling; subject to annual program budget",
            longevity_years=10,
            requirements=[
                "New Jersey utility customer",
                "Qualifying energy efficiency measures",
                "Pre-approval required",
                "Direct Install program available for small businesses",
            ],
            tags=["new_jersey", "njce", "direct_install", "utility_incentive"],
        ),
    ]


def get_dsire_incentives(zip_code: str) -> List[Grant]:
    """Return state/local incentives from DSIRE database for a given ZIP code.

    Note: DSIRE API integration is pending. This stub returns an empty list
    and logs a warning. When implemented, this should call the DSIRE API at
    https://www.dsireusa.org/ to fetch jurisdiction-specific incentives.

    Args:
        zip_code: U.S. ZIP code to look up incentives for.

    Returns:
        Empty list until DSIRE API integration is implemented.
    """
    logger.warning(
        "DSIRE API integration pending; no incentives returned for ZIP %s. "
        "Implement DSIRE API call at https://api.dsireusa.org/ when available.",
        zip_code,
    )
    return []
