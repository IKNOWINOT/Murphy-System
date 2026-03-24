# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import Dict


class BudgetNarrativeBuilder:
    """Generates budget narrative/justification text."""

    def build(self, application_data: Dict) -> str:
        org = application_data.get("organization_name", "the applicant organization")
        project = application_data.get("project_title", "the proposed project")
        federal_amount = application_data.get("federal_amount", 0)
        match_amount = application_data.get("match_amount", 0)
        total = federal_amount + match_amount

        personnel = application_data.get("personnel_costs", federal_amount * 0.6)
        fringe = application_data.get("fringe_benefits", personnel * 0.25)
        indirect = application_data.get("indirect_costs", federal_amount * 0.1)
        direct_other = federal_amount - personnel - fringe - indirect

        lines = [
            "BUDGET NARRATIVE AND JUSTIFICATION",
            f"Organization: {org}",
            f"Project: {project}",
            "",
            "A. PERSONNEL",
            f"Personnel costs total ${personnel:,.2f}, covering the salary and effort of key project staff.",
            "",
            "B. FRINGE BENEFITS",
            f"Fringe benefits are calculated at the organization's approved rate totaling ${fringe:,.2f}.",
            "",
            "C. TRAVEL",
            "Travel costs are included for project-related site visits and conference participation.",
            "",
            "D. SUPPLIES",
            "Supplies necessary for project activities are included in direct costs.",
            "",
            "E. OTHER DIRECT COSTS",
            f"Other direct costs total ${max(direct_other, 0):,.2f}.",
            "",
            "F. INDIRECT COSTS",
            f"Indirect costs total ${indirect:,.2f} based on the organization's negotiated rate.",
            "",
            f"TOTAL FEDERAL REQUEST: ${federal_amount:,.2f}",
            f"NON-FEDERAL MATCH: ${match_amount:,.2f}",
            f"TOTAL PROJECT COST: ${total:,.2f}",
        ]
        return "\n".join(lines)
