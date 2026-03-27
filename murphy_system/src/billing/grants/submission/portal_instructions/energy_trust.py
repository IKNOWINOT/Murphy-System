# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class EnergyTrustInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        project_name = application_data.get("project_name", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Go to the Energy Trust of Oregon online application portal.",
                url="https://www.energytrust.org/about/for-contractors/",
            ),
            SubmissionStep(
                step_number=2,
                instruction=f"Start a new application for project: {project_name}.",
                data_to_enter={"project_name": project_name},
            ),
            SubmissionStep(
                step_number=3,
                instruction="Enter your utility account information and service address.",
            ),
            SubmissionStep(
                step_number=4,
                instruction="Describe the proposed energy efficiency measures.",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Upload project specifications and contractor quotes.",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=6,
                instruction="Submit the application for Energy Trust review.",
            ),
        ]
