# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class SbirGovInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        company_name = application_data.get("company_name", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Go to the SBIR.gov portal and log in.",
                url="https://www.sbir.gov",
            ),
            SubmissionStep(
                step_number=2,
                instruction=f"Navigate to Company Profile for {company_name} and verify it is current.",
                data_to_enter={"company_name": company_name},
            ),
            SubmissionStep(
                step_number=3,
                instruction="Search for the open SBIR/STTR solicitation matching your topic.",
                url="https://www.sbir.gov/solicitations",
            ),
            SubmissionStep(
                step_number=4,
                instruction="Click 'Apply' on the target solicitation and complete the online form.",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Upload your Technical Volume (research plan) as a PDF.",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=6,
                instruction="Upload your budget and budget justification documents.",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=7,
                instruction="Review the submission checklist and submit your proposal.",
            ),
        ]
