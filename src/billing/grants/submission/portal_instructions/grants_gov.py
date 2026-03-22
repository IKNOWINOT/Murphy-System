# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class GrantsGovInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        opportunity_number = application_data.get("opportunity_number", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Navigate to the Grants.gov Applicant Workspace.",
                url="https://www.grants.gov/applicants/workspace",
            ),
            SubmissionStep(
                step_number=2,
                instruction="Log in with your Grants.gov credentials.",
                screenshot_hint="Enter your username and password on the login screen.",
            ),
            SubmissionStep(
                step_number=3,
                instruction=f"Search for the opportunity number: {opportunity_number}.",
                data_to_enter={"opportunity_number": opportunity_number},
            ),
            SubmissionStep(
                step_number=4,
                instruction="Click 'Apply' to create your workspace for this opportunity.",
                screenshot_hint="The Apply button appears on the opportunity detail page.",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Upload your SF-424 XML application package.",
                is_upload=True,
                screenshot_hint="Click 'Upload' in the Mandatory Documents section.",
            ),
            SubmissionStep(
                step_number=6,
                instruction="Upload your Project Narrative PDF.",
                is_upload=True,
                screenshot_hint="Click 'Upload' in the Project Narrative section.",
            ),
            SubmissionStep(
                step_number=7,
                instruction="Upload your Budget Justification document.",
                is_upload=True,
                screenshot_hint="Click 'Upload' in the Budget section.",
            ),
            SubmissionStep(
                step_number=8,
                instruction="Review all sections to ensure they are complete and error-free.",
                screenshot_hint="A green checkmark will appear next to each completed section.",
            ),
            SubmissionStep(
                step_number=9,
                instruction="Click 'Sign and Submit' to submit your application.",
                screenshot_hint="The Sign and Submit button is at the bottom of the workspace.",
            ),
            SubmissionStep(
                step_number=10,
                instruction="Save your confirmation number for your records.",
                screenshot_hint="A confirmation page will show your application tracking number.",
            ),
        ]
