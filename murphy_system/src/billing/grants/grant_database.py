"""
Grant Database — Catalog of grant programs for the Murphy HITL system.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GrantProgram:
    program_id: str
    name: str
    agency: str
    description: str
    max_award_usd: float
    eligibility_requirements: List[str]
    naics_codes: List[str]
    form_ids: List[str]
    prerequisites: List[str]
    url: str
    active: bool = True


GRANT_PROGRAMS: Dict[str, GrantProgram] = {
    "sbir_phase1": GrantProgram(
        program_id="sbir_phase1",
        name="SBIR Phase I",
        agency="DOD/SBA",
        description="Small Business Innovation Research Phase I award for feasibility study.",
        max_award_usd=275000,
        eligibility_requirements=[
            "Small business (< 500 employees)",
            "US-based company",
            "Principal Investigator employed at least 51% by applicant",
            "UEI required",
            "CAGE code required",
        ],
        naics_codes=["541715", "541714", "517410"],
        form_ids=["sbir_phase1"],
        prerequisites=["sam_gov_uei", "cage_code"],
        url="https://www.sbir.gov",
    ),
    "sbir_phase2": GrantProgram(
        program_id="sbir_phase2",
        name="SBIR Phase II",
        agency="DOD/SBA",
        description="Small Business Innovation Research Phase II award for R&D.",
        max_award_usd=1837500,
        eligibility_requirements=[
            "Successful SBIR Phase I recipient",
            "Small business (< 500 employees)",
            "US-based company",
            "UEI required",
            "CAGE code required",
        ],
        naics_codes=["541715", "541714"],
        form_ids=["sbir_phase2"],
        prerequisites=["sam_gov_uei", "cage_code", "sbir_phase1"],
        url="https://www.sbir.gov",
    ),
    "sttr_phase1": GrantProgram(
        program_id="sttr_phase1",
        name="STTR Phase I",
        agency="DOD/NSF",
        description="Small Business Technology Transfer Phase I award.",
        max_award_usd=275000,
        eligibility_requirements=[
            "Small business (< 500 employees)",
            "US-based company",
            "Research institution partner required",
            "UEI required",
            "CAGE code required",
        ],
        naics_codes=["541715", "541714"],
        form_ids=["sttr_phase1"],
        prerequisites=["sam_gov_uei", "cage_code"],
        url="https://www.sbir.gov/sttr",
    ),
    "nsf_sbir": GrantProgram(
        program_id="nsf_sbir",
        name="NSF SBIR",
        agency="NSF",
        description="National Science Foundation SBIR grant for deep tech innovation.",
        max_award_usd=275000,
        eligibility_requirements=[
            "Small business (< 500 employees)",
            "US-based company",
            "UEI required",
            "Grants.gov account required",
        ],
        naics_codes=["541715", "541714", "517410"],
        form_ids=["nsf_sbir"],
        prerequisites=["sam_gov_uei", "grants_gov_account"],
        url="https://seedfund.nsf.gov",
    ),
    "doe_sbir": GrantProgram(
        program_id="doe_sbir",
        name="DOE SBIR",
        agency="DOE",
        description="Department of Energy SBIR grant for energy technology.",
        max_award_usd=200000,
        eligibility_requirements=[
            "Small business (< 500 employees)",
            "US-based company",
            "UEI required",
            "CAGE code required",
        ],
        naics_codes=["541715", "221118", "333611"],
        form_ids=["nsf_sbir"],
        prerequisites=["sam_gov_uei", "cage_code"],
        url="https://science.osti.gov/sbir",
    ),
    "sba_microloan": GrantProgram(
        program_id="sba_microloan",
        name="SBA Microloan",
        agency="SBA",
        description="SBA microloan program for small businesses and nonprofits.",
        max_award_usd=50000,
        eligibility_requirements=[
            "For-profit small business",
            "US-based",
            "Unable to obtain credit elsewhere",
        ],
        naics_codes=[],
        form_ids=["sba_microloan"],
        prerequisites=[],
        url="https://www.sba.gov/funding-programs/loans/microloans",
    ),
    "energy_trust_oregon": GrantProgram(
        program_id="energy_trust_oregon",
        name="Energy Trust of Oregon",
        agency="Energy Trust of Oregon",
        description="Cash incentives for energy efficiency and renewable energy projects.",
        max_award_usd=300000,
        eligibility_requirements=[
            "Oregon-based business",
            "Pacific Power or PGE utility customer",
        ],
        naics_codes=[],
        form_ids=["energy_trust"],
        prerequisites=[],
        url="https://www.energytrust.org/commercial/cash-incentives/",
    ),
}


def get_program(program_id: str) -> Optional[GrantProgram]:
    return GRANT_PROGRAMS.get(program_id)


def list_programs() -> List[GrantProgram]:
    return list(GRANT_PROGRAMS.values())
