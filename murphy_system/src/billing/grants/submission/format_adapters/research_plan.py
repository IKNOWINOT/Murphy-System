# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import Dict, List


class ResearchPlanFormatter:
    """Formats research plan sections."""

    def build(self, application_data: Dict) -> Dict[str, str]:
        return {
            "project_summary": self._project_summary(application_data),
            "specific_aims": self._specific_aims(application_data),
            "research_strategy": self._research_strategy(application_data),
            "innovation": self._innovation(application_data),
            "approach": self._approach(application_data),
        }

    def _project_summary(self, data: Dict) -> str:
        title = data.get("project_title", "the proposed project")
        return f"Project Summary: {title}. This project aims to advance knowledge and practice in the target domain."

    def _specific_aims(self, data: Dict) -> str:
        aims = data.get("specific_aims", ["Aim 1: Establish baseline", "Aim 2: Conduct research", "Aim 3: Disseminate findings"])
        return "Specific Aims:\n" + "\n".join(f"  {a}" for a in aims)

    def _research_strategy(self, data: Dict) -> str:
        return "Research Strategy: The proposed research uses a rigorous, evidence-based methodology."

    def _innovation(self, data: Dict) -> str:
        return "Innovation: This project introduces novel approaches that advance the state of the art."

    def _approach(self, data: Dict) -> str:
        return "Approach: The research team will execute the project using established best practices and rigorous evaluation."
