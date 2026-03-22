"""Utility-sponsored demand response and incentive programs."""

from __future__ import annotations

from typing import List

from src.billing.grants.models import Grant, ProgramType


def get_utility_program_grants() -> List[Grant]:
    """Return fully populated Grant objects for utility-sponsored programs."""
    return [
        Grant(
            id="util_dr",
            name="Utility Demand Response Program",
            program_type=ProgramType.utility_program,
            agency="Local Utility / ISO/RTO",
            description=(
                "Revenue from reducing electricity demand during peak grid events. "
                "Murphy System AI controls can automatically curtail loads and "
                "dispatch storage to earn $50-$200/kW/year. Applicable across all "
                "major grid regions (PJM, CAISO, MISO, ISO-NE, ERCOT, NYISO)."
            ),
            min_amount=500.0,
            max_amount=200_000.0,
            eligible_entity_types=["small_business", "corporation", "industrial", "government"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
                "industrial_iot",
                "smart_manufacturing",
                "grid_management",
            ],
            eligible_states=[],
            application_url="https://www.ferc.gov/media/ferc-order-2222",
            deadline_pattern="Annual enrollment periods vary by utility/ISO",
            longevity_years=10,
            requirements=[
                "Controllable load or behind-the-meter storage",
                "Interval metering (15-min or hourly)",
                "Enrollment through utility or aggregator",
                "Minimum load reduction threshold (varies: 10-100 kW)",
                "Murphy System demand response module integration",
            ],
            tags=["demand_response", "grid_services", "curtailment", "revenue"],
        ),
        Grant(
            id="util_obf",
            name="Utility On-Bill Financing",
            program_type=ProgramType.utility_program,
            agency="Local Utility",
            description=(
                "Zero or low-interest financing repaid through utility bill savings. "
                "Customers financing Murphy System installation can structure repayment "
                "around measurable energy savings tracked by the system."
            ),
            min_amount=1_000.0,
            max_amount=100_000.0,
            eligible_entity_types=["small_business", "corporation", "nonprofit", "individual"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
            ],
            eligible_states=[],
            application_url="",
            deadline_pattern="Rolling; through participating utility",
            longevity_years=10,
            requirements=[
                "Active utility account in good standing",
                "Qualifying energy efficiency project",
                "Repayment through utility bill",
                "Available from select utilities — verify local availability",
            ],
            tags=["on_bill_financing", "low_interest", "utility", "accessible"],
        ),
        Grant(
            id="util_custom",
            name="Custom Utility Energy Efficiency Incentive",
            program_type=ProgramType.utility_program,
            agency="Local Utility",
            description=(
                "Custom performance-based incentives of $0.05-$0.25/kWh saved for "
                "large commercial and industrial customers. Murphy System energy "
                "management provides M&V documentation for incentive claims. "
                "Available through most major U.S. utility programs."
            ),
            min_amount=1_000.0,
            max_amount=500_000.0,
            eligible_entity_types=["small_business", "corporation", "industrial", "government"],
            eligible_verticals=[
                "building_automation",
                "energy_management",
                "hvac_controls",
                "industrial_iot",
                "smart_manufacturing",
            ],
            eligible_states=[],
            application_url="",
            deadline_pattern="Rolling; subject to annual utility program budget",
            longevity_years=10,
            requirements=[
                "Commercial or industrial utility customer",
                "Pre-approval before project start",
                "M&V (measurement & verification) plan required for large projects",
                "Energy savings must exceed minimum threshold",
                "Licensed contractor installation may be required",
            ],
            tags=["custom_incentive", "performance_based", "m_and_v", "commercial"],
        ),
    ]
