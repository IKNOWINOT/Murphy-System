# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import csv
import io
from typing import Dict


class SamGovFormatter:
    """Builds SAM.gov entity registration CSV/JSON format."""

    def build_csv(self, application_data: Dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Field", "Value"])
        writer.writerow(["Legal Business Name", application_data.get("entity_name", "")])
        writer.writerow(["UEI", application_data.get("uei", "")])
        writer.writerow(["EIN", application_data.get("ein", "")])
        writer.writerow(["CAGE Code", application_data.get("cage_code", "")])
        writer.writerow(["NAICS Primary", application_data.get("primary_naics", "")])
        writer.writerow(["Physical Address", application_data.get("address", "")])
        writer.writerow(["City", application_data.get("city", "")])
        writer.writerow(["State", application_data.get("state", "")])
        writer.writerow(["ZIP", application_data.get("zip", "")])
        writer.writerow(["Country", application_data.get("country", "USA")])
        return output.getvalue()

    def build_json(self, application_data: Dict) -> Dict:
        return {
            "legalBusinessName": application_data.get("entity_name", ""),
            "uei": application_data.get("uei", ""),
            "ein": application_data.get("ein", ""),
            "cageCode": application_data.get("cage_code", ""),
            "primaryNaics": application_data.get("primary_naics", ""),
            "physicalAddress": {
                "addressLine1": application_data.get("address", ""),
                "city": application_data.get("city", ""),
                "stateOrProvinceCode": application_data.get("state", ""),
                "zipCode": application_data.get("zip", ""),
                "countryCode": application_data.get("country", "USA"),
            },
        }
