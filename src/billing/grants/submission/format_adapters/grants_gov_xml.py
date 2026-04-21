# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

# PROD-HARD-SEC-001 (audit G18): this module constructs XML documents
# (ET.Element/SubElement/tostring) and never parses untrusted input —
# no ET.fromstring / ET.parse / ET.iterparse / XMLParser call sites.
# Serialization has no XXE surface, so defusedxml is not required here.
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict


class GrantsGovXMLBuilder:
    """Builds complete SF-424 XML package with proper XML namespaces for Grants.gov."""

    NS = "http://apply.grants.gov/system/ApplicantCommonElements-V1.1"
    SF424_NS = "http://apply.grants.gov/forms/SF424-V2.1"
    RR_BUDGET_NS = "http://apply.grants.gov/forms/RR_Budget-V1.1"
    SF424A_NS = "http://apply.grants.gov/forms/SF424A-V1.0"

    def build_sf424_xml(self, application_data: Dict) -> str:
        root = ET.Element("GrantApplication", attrib={
            "xmlns": self.NS,
            "xmlns:SF424": self.SF424_NS,
            "xmlns:RRBudget": self.RR_BUDGET_NS,
        })

        sf424 = ET.SubElement(root, "SF424:SF424")
        ET.SubElement(sf424, "SF424:FederalAwardIdentifier").text = application_data.get("federal_award_identifier", "")
        ET.SubElement(sf424, "SF424:ApplicantOrganizationName").text = application_data.get("organization_name", "")
        ET.SubElement(sf424, "SF424:ApplicantUEI").text = application_data.get("uei", "")
        ET.SubElement(sf424, "SF424:ApplicantEIN").text = application_data.get("ein", "")
        ET.SubElement(sf424, "SF424:ProjectTitle").text = application_data.get("project_title", "")
        ET.SubElement(sf424, "SF424:ProjectStartDate").text = application_data.get("start_date", "")
        ET.SubElement(sf424, "SF424:ProjectEndDate").text = application_data.get("end_date", "")
        ET.SubElement(sf424, "SF424:FederalFundsRequested").text = str(application_data.get("federal_amount", 0))
        ET.SubElement(sf424, "SF424:NonFederalMatch").text = str(application_data.get("match_amount", 0))

        ar = ET.SubElement(sf424, "SF424:AuthorizedRepresentative")
        ET.SubElement(ar, "SF424:Name").text = application_data.get("ar_name", "")
        ET.SubElement(ar, "SF424:Title").text = application_data.get("ar_title", "")
        ET.SubElement(ar, "SF424:Email").text = application_data.get("ar_email", "")
        ET.SubElement(ar, "SF424:Phone").text = application_data.get("ar_phone", "")

        rr_budget = ET.SubElement(root, "RRBudget:RRBudget")
        ET.SubElement(rr_budget, "RRBudget:FederalAmount").text = str(application_data.get("federal_amount", 0))
        ET.SubElement(rr_budget, "RRBudget:TotalCost").text = str(
            application_data.get("federal_amount", 0) + application_data.get("match_amount", 0)
        )

        ET.indent(root, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    def build_full_package(self, application_data: Dict) -> Dict[str, str]:
        return {
            "sf424.xml": self.build_sf424_xml(application_data),
        }
