# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class ResearchGovInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        pi_name = application_data.get("pi_name", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Go to NSF Research.gov and sign in with your NSF account.",
                url="https://www.research.gov",
            ),
            SubmissionStep(
                step_number=2,
                instruction=f"Verify Principal Investigator (PI) profile for {pi_name} is complete.",
                data_to_enter={"pi_name": pi_name},
            ),
            SubmissionStep(
                step_number=3,
                instruction="Navigate to 'Prepare & Submit Proposals' and select 'Proposal Preparation'.",
            ),
            SubmissionStep(
                step_number=4,
                instruction="Create a new proposal and enter funding opportunity details.",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Upload the Project Summary (one page max).",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=6,
                instruction="Upload the Project Description (15 pages max for standard proposals).",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=7,
                instruction="Enter budget details in the NSF budget module.",
            ),
            SubmissionStep(
                step_number=8,
                instruction="Have Authorized Organizational Representative (AOR) submit the proposal.",
            ),
        ]
