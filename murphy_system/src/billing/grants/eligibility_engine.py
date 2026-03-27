"""
Eligibility Engine — Checks grant program eligibility for project parameters.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.billing.grants.grant_database import GRANT_PROGRAMS, get_program


@dataclass
class EligibilityResult:
    program_id: str
    eligible: bool
    score: float
    missing_requirements: List[str]
    met_requirements: List[str]
    recommendations: List[str]


class EligibilityEngine:
    def check_eligibility(self, program_id: str, project_params: Dict[str, Any]) -> EligibilityResult:
        program = get_program(program_id)
        if program is None:
            return EligibilityResult(
                program_id=program_id,
                eligible=False,
                score=0.0,
                missing_requirements=["Unknown program"],
                met_requirements=[],
                recommendations=["Verify program ID is correct"],
            )

        met: List[str] = []
        missing: List[str] = []
        recommendations: List[str] = []

        company_type = project_params.get("company_type", "")
        employee_count = int(project_params.get("employee_count", 0))
        annual_revenue = float(project_params.get("annual_revenue_usd", 0.0))
        naics_codes = project_params.get("naics_codes", [])
        us_based = bool(project_params.get("us_based", False))
        has_uei = bool(project_params.get("has_uei", False))
        has_cage = bool(project_params.get("has_cage", False))
        grants_gov_account = bool(project_params.get("grants_gov_account", False))
        research_focus = project_params.get("research_focus", "")

        is_sbir_sttr = program_id in ("sbir_phase1", "sbir_phase2", "sttr_phase1", "doe_sbir")
        is_nsf = program_id == "nsf_sbir"
        is_flexible = program_id in ("sba_microloan", "energy_trust_oregon")

        if is_sbir_sttr:
            if company_type == "small_business":
                met.append("Small business entity type")
            else:
                missing.append("Must be a small business")
                recommendations.append("Ensure company is registered as a small business")

            if employee_count < 500:
                met.append("Employee count < 500")
            else:
                missing.append("Employee count must be < 500")

            if us_based:
                met.append("US-based company")
            else:
                missing.append("Company must be US-based")
                recommendations.append("Company must be incorporated in the United States")

            if has_uei:
                met.append("UEI obtained")
            else:
                missing.append("UEI required")
                recommendations.append("Register at SAM.gov to obtain your UEI")

            if has_cage:
                met.append("CAGE code obtained")
            else:
                missing.append("CAGE code required")
                recommendations.append("CAGE code assigned after SAM.gov registration")

            if program_id == "sbir_phase2":
                sbir1_done = project_params.get("has_sbir_phase1", False)
                if sbir1_done:
                    met.append("SBIR Phase I completed")
                else:
                    missing.append("Must have completed SBIR Phase I")
                    recommendations.append("Apply for and complete SBIR Phase I first")

        elif is_nsf:
            if company_type == "small_business":
                met.append("Small business entity type")
            else:
                missing.append("Must be a small business")

            if us_based:
                met.append("US-based company")
            else:
                missing.append("Company must be US-based")

            if has_uei:
                met.append("UEI obtained")
            else:
                missing.append("UEI required")
                recommendations.append("Register at SAM.gov to obtain your UEI")

            if grants_gov_account:
                met.append("Grants.gov account active")
            else:
                missing.append("Grants.gov account required")
                recommendations.append("Create a free account at grants.gov")

        elif is_flexible:
            if us_based:
                met.append("US-based company")
            else:
                missing.append("Company must be US-based")

            met.append("Open eligibility program")
            if annual_revenue > 0:
                met.append("Revenue information provided")
            else:
                recommendations.append("Provide annual revenue information")

        else:
            if company_type == "small_business":
                met.append("Small business entity type")
            if us_based:
                met.append("US-based company")
            if has_uei:
                met.append("UEI obtained")

        # NAICS match bonus
        if program.naics_codes and naics_codes:
            overlap = set(naics_codes) & set(program.naics_codes)
            if overlap:
                met.append(f"NAICS code match: {', '.join(overlap)}")
            else:
                recommendations.append(f"Consider aligning NAICS codes with program codes: {', '.join(program.naics_codes[:3])}")

        total_checks = len(met) + len(missing)
        score = (len(met) / total_checks) if total_checks > 0 else 0.0
        score = min(1.0, score)

        eligible = score >= 0.6

        return EligibilityResult(
            program_id=program_id,
            eligible=eligible,
            score=round(score, 4),
            missing_requirements=missing,
            met_requirements=met,
            recommendations=recommendations,
        )

    def check_multiple(self, program_ids: List[str], project_params: Dict[str, Any]) -> List[EligibilityResult]:
        return [self.check_eligibility(pid, project_params) for pid in program_ids]

    def recommend_programs(self, project_params: Dict[str, Any]) -> List[EligibilityResult]:
        results = [self.check_eligibility(pid, project_params) for pid in GRANT_PROGRAMS]
        return sorted(results, key=lambda r: r.score, reverse=True)
