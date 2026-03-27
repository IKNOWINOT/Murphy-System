# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from typing import Dict


class SF424Builder:
    """Builds Standard Form 424 data structure from application data."""

    def build(self, application_data: Dict) -> Dict:
        return {
            "federal_award_identifier": application_data.get("federal_award_identifier", ""),
            "applicant_organization_name": application_data.get("organization_name", ""),
            "applicant_uei": application_data.get("uei", ""),
            "applicant_ein": application_data.get("ein", ""),
            "project_title": application_data.get("project_title", ""),
            "project_start_date": application_data.get("start_date", ""),
            "project_end_date": application_data.get("end_date", ""),
            "federal_funds_requested": application_data.get("federal_amount", 0),
            "non_federal_match": application_data.get("match_amount", 0),
            "congressional_district": application_data.get("congressional_district", ""),
            "state_application_identifier": application_data.get("state_id", ""),
            "authorized_representative_name": application_data.get("ar_name", ""),
            "authorized_representative_title": application_data.get("ar_title", ""),
            "authorized_representative_email": application_data.get("ar_email", ""),
            "authorized_representative_phone": application_data.get("ar_phone", ""),
        }
