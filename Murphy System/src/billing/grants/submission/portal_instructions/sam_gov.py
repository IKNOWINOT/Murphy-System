# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import List

from src.billing.grants.submission.models import SubmissionStep
from src.billing.grants.submission.portal_instructions.base import BasePortalInstructions


class SamGovInstructions(BasePortalInstructions):
    def generate_steps(self, application_data: dict) -> List[SubmissionStep]:
        entity_name = application_data.get("entity_name", "")
        return [
            SubmissionStep(
                step_number=1,
                instruction="Navigate to SAM.gov and sign in or create an account.",
                url="https://sam.gov",
            ),
            SubmissionStep(
                step_number=2,
                instruction="Go to 'Entity Registrations' and click 'Register/Update Entity'.",
                screenshot_hint="Entity management is under the top navigation menu.",
            ),
            SubmissionStep(
                step_number=3,
                instruction=f"Enter your entity legal name: {entity_name}.",
                data_to_enter={"entity_name": entity_name},
            ),
            SubmissionStep(
                step_number=4,
                instruction="Enter your UEI (Unique Entity Identifier) or obtain a new one.",
                url="https://sam.gov/content/duns-uei",
            ),
            SubmissionStep(
                step_number=5,
                instruction="Complete all required entity information fields including NAICS codes.",
            ),
            SubmissionStep(
                step_number=6,
                instruction="Submit the registration and note your SAM.gov registration number.",
            ),
        ]
