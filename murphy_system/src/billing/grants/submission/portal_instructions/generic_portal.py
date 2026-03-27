# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class GenericPortalInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        portal_url = application_data.get("portal_url", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Navigate to the grant portal.",
                url=portal_url if portal_url else None,
            ),
            SubmissionStep(
                step_number=2,
                instruction="Log in or create an account on the portal.",
            ),
            SubmissionStep(
                step_number=3,
                instruction="Complete all required application sections with the provided data.",
                data_to_enter=application_data,
            ),
            SubmissionStep(
                step_number=4,
                instruction="Upload any required supporting documents.",
                is_upload=True,
            ),
            SubmissionStep(
                step_number=5,
                instruction="Review your application and submit.",
            ),
        ]
