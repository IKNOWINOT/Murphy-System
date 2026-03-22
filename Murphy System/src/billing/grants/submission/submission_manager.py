# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.billing.grants.submission.models import (
    SubmissionFile,
    SubmissionPackage,
    SubmissionStep,
)
from src.billing.grants.submission.portal_instructions.generic_portal import GenericPortalInstructions

PORTAL_INSTRUCTIONS_MAP: Dict[str, type] = {}


def _get_portal_class(portal: str):
    """Lazy-load portal instruction classes to avoid circular imports."""
    if portal in PORTAL_INSTRUCTIONS_MAP:
        return PORTAL_INSTRUCTIONS_MAP[portal]

    from src.billing.grants.submission.portal_instructions.grants_gov import GrantsGovInstructions
    from src.billing.grants.submission.portal_instructions.sam_gov import SamGovInstructions
    from src.billing.grants.submission.portal_instructions.sbir_gov import SbirGovInstructions
    from src.billing.grants.submission.portal_instructions.research_gov import ResearchGovInstructions
    from src.billing.grants.submission.portal_instructions.sba_portal import SbaPortalInstructions
    from src.billing.grants.submission.portal_instructions.energy_trust import EnergyTrustInstructions

    registry = {
        "grants_gov": GrantsGovInstructions,
        "sam_gov": SamGovInstructions,
        "sbir_gov": SbirGovInstructions,
        "research_gov": ResearchGovInstructions,
        "sba_portal": SbaPortalInstructions,
        "energy_trust": EnergyTrustInstructions,
    }
    PORTAL_INSTRUCTIONS_MAP.update(registry)
    return PORTAL_INSTRUCTIONS_MAP.get(portal, GenericPortalInstructions)


# In-memory store: package_id -> SubmissionPackage
_packages: Dict[str, SubmissionPackage] = {}
# Index: (session_id, application_id) -> package_id
_package_index: Dict[tuple, str] = {}


class SubmissionManager:
    def generate_package(
        self,
        session_id: str,
        application_id: str,
        portal: str,
        application_data: Optional[Dict] = None,
    ) -> SubmissionPackage:
        if application_data is None:
            application_data = {}

        instructions_cls = _get_portal_class(portal)
        instructions_obj = instructions_cls()
        steps = instructions_obj.generate_steps(application_data)

        files = self._build_files(portal, application_data)

        package = SubmissionPackage(
            package_id=str(uuid.uuid4()),
            application_id=application_id,
            session_id=session_id,
            portal=portal,
            format=self._portal_format(portal),
            files=files,
            instructions=steps,
            status="generated",
            created_at=datetime.utcnow(),
        )

        _packages[package.package_id] = package
        _package_index[(session_id, application_id)] = package.package_id
        return package

    def get_package(self, session_id: str, application_id: str) -> Optional[SubmissionPackage]:
        pid = _package_index.get((session_id, application_id))
        if pid:
            return _packages.get(pid)
        return None

    def get_package_by_id(self, package_id: str) -> Optional[SubmissionPackage]:
        return _packages.get(package_id)

    def _portal_format(self, portal: str) -> str:
        formats = {
            "grants_gov": "xml",
            "sam_gov": "csv",
            "sbir_gov": "web_form",
            "research_gov": "web_form",
            "sba_portal": "web_form",
            "energy_trust": "web_form",
        }
        return formats.get(portal, "pdf")

    def _build_files(self, portal: str, application_data: dict) -> List[SubmissionFile]:
        files = []
        if portal == "grants_gov":
            files.append(SubmissionFile(
                file_id=str(uuid.uuid4()),
                filename="SF424_Application.xml",
                format="xml",
                content_type="application/xml",
                size_bytes=4096,
                description="SF-424 Application for Federal Assistance",
            ))
            files.append(SubmissionFile(
                file_id=str(uuid.uuid4()),
                filename="Project_Narrative.pdf",
                format="pdf",
                content_type="application/pdf",
                size_bytes=102400,
                description="Project Narrative",
            ))
            files.append(SubmissionFile(
                file_id=str(uuid.uuid4()),
                filename="Budget_Justification.pdf",
                format="pdf",
                content_type="application/pdf",
                size_bytes=51200,
                description="Budget Justification and Narrative",
            ))
        elif portal == "sam_gov":
            files.append(SubmissionFile(
                file_id=str(uuid.uuid4()),
                filename="SAM_Entity_Registration.csv",
                format="csv",
                content_type="text/csv",
                size_bytes=2048,
                description="SAM.gov Entity Registration Data",
            ))
        else:
            files.append(SubmissionFile(
                file_id=str(uuid.uuid4()),
                filename="Application_Package.pdf",
                format="pdf",
                content_type="application/pdf",
                size_bytes=81920,
                description="Application Package",
            ))
        return files
