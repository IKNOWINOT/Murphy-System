# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class SbaPortalInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        business_name = application_data.get("business_name", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Go to SBA.gov and navigate to Loans & Grants.",
                url="https://www.sba.gov",
            ),
            SubmissionStep(
                step_number=2,
                instruction=f"Select the appropriate program for {business_name}.",
                data_to_enter={"business_name": business_name},
            ),
            SubmissionStep(
                step_number=3,
                instruction="Create or log into your SBA account.",
                url="https://account.sba.gov",
            ),
            SubmissionStep(
                step_number=4,
                instruction="Complete the online application form with your business information.",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Upload required financial documents (tax returns, bank statements).",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=6,
                instruction="Upload your business plan and other supporting documents.",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=7,
                instruction="Review and submit your application.",
            ),
        ]
