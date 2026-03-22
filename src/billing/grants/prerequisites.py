"""
Prerequisites System — SAM.gov, UEI, CAGE, Grants.gov registration chain.

Models the federal grant prerequisite chain as HITL tasks.
Each prerequisite is a step in a DAG with dependency chain logic.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional

from src.billing.grants.models import Prerequisite, PrerequisiteStatus


# ---------------------------------------------------------------------------
# Prerequisite definitions (federal grant chain)
# ---------------------------------------------------------------------------

def _make_prerequisites() -> List[Prerequisite]:
    """Build the ordered federal grant prerequisite chain."""
    return [
        Prerequisite(
            prereq_id="sam_registration",
            name="SAM.gov Entity Registration",
            description=(
                "Register your organization in SAM.gov (System for Award Management). "
                "SAM.gov is the official U.S. government database for entities doing "
                "business with the federal government. Required for ALL federal grants "
                "and contracts, including SBIR, STTR, ARPA-E, DOE, NSF, and EDA awards."
            ),
            why_needed=(
                "Every federal agency requires a valid, active SAM.gov registration before "
                "awarding a grant. Without SAM.gov registration, your organization cannot "
                "receive federal award funds. Registration is free and must be renewed annually."
            ),
            external_link="https://sam.gov/content/entity-registration",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=[],
            is_recurring=True,
            renewal_period_days=365,
            order=1,
        ),
        Prerequisite(
            prereq_id="uei_number",
            name="UEI — Unique Entity Identifier",
            description=(
                "Obtain your organization's Unique Entity Identifier (UEI) from SAM.gov. "
                "The UEI replaced the DUNS number in April 2022. It is a 12-character "
                "alphanumeric identifier assigned by SAM.gov during entity registration. "
                "The UEI is required on all federal grant applications."
            ),
            why_needed=(
                "The UEI is how federal agencies identify your organization across all "
                "grants, contracts, and assistance programs. It is automatically assigned "
                "during SAM.gov registration — no separate application needed."
            ),
            external_link="https://sam.gov/content/unique-entity-id",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["sam_registration"],
            is_recurring=False,
            order=2,
            notes=(
                "Inoni LLC UEI: "
                + os.environ.get(
                    "INONI_SAM_UEI",
                    "[Not yet obtained — complete SAM.gov registration]",
                )
            ),
        ),
        Prerequisite(
            prereq_id="cage_code",
            name="CAGE Code — Commercial and Government Entity Code",
            description=(
                "Obtain a CAGE (Commercial and Government Entity) code. CAGE codes are "
                "5-character alphanumeric identifiers assigned by the Defense Logistics "
                "Agency (DLA). They are automatically assigned to U.S. entities during "
                "SAM.gov registration. CAGE codes are required for DoD contracts and "
                "some DOE/NASA programs."
            ),
            why_needed=(
                "CAGE codes are required for DoD SBIR/STTR applications and contracts. "
                "They are automatically assigned during SAM.gov registration — no "
                "separate application needed for U.S. entities."
            ),
            external_link="https://sam.gov/content/cage-codes",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["sam_registration"],
            is_recurring=False,
            order=3,
            notes=(
                f"Inoni LLC CAGE: {os.environ.get('INONI_CAGE_CODE', '[Auto-assigned during SAM.gov registration]')}"
            ),
        ),
        Prerequisite(
            prereq_id="naics_selection",
            name="NAICS Code Selection",
            description=(
                "Select appropriate NAICS (North American Industry Classification System) "
                "codes for your organization in SAM.gov. NAICS codes classify your "
                "business activity and determine small business size standards. "
                "For Inoni LLC / Murphy System, the primary codes are: "
                "541715 (R&D in computer science), 541512 (Computer Systems Design), "
                "238220 (Plumbing, Heating, A/C Contractors for BAS)."
            ),
            why_needed=(
                "Agencies use NAICS codes to verify size standard eligibility for SBIR/STTR "
                "and other small business programs. Selecting the right codes ensures Murphy "
                "qualifies as a 'small business' under the applicable size standards. "
                "Multiple NAICS codes can be listed."
            ),
            external_link="https://www.census.gov/naics/",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["sam_registration"],
            is_recurring=False,
            order=4,
            notes=(
                "Suggested NAICS codes for Inoni LLC:\n"
                "  541715 - R&D in Phys/Eng/Life Sciences (computer)\n"
                "  541512 - Computer Systems Design Services\n"
                "  541511 - Custom Computer Programming Services\n"
                "  519290 - Web Search Portals, Libraries, Archives (platform)\n"
                "Agent will suggest based on Murphy's verticals; human must confirm."
            ),
        ),
        Prerequisite(
            prereq_id="ein",
            name="Employer Identification Number (EIN)",
            description=(
                "Obtain a federal Employer Identification Number (EIN) from the IRS. "
                "The EIN is required for corporate tax filing, payroll, and federal grants. "
                "For LLCs, an EIN is required when the entity has employees or files "
                "for certain grants. Free to obtain at IRS.gov."
            ),
            why_needed=(
                "Federal grants require EIN for tax reporting (1099-G). Many grant "
                "applications and SAM.gov registration require EIN. Required before "
                "R&D tax credit filing."
            ),
            external_link="https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=[],
            is_recurring=False,
            order=0,
            notes=(
                f"Inoni LLC EIN: {os.environ.get('INONI_EIN', '[Not configured — set INONI_EIN in .env]')}"
            ),
        ),
        Prerequisite(
            prereq_id="grants_gov_account",
            name="Grants.gov Account Registration",
            description=(
                "Create a Grants.gov account for your organization. Grants.gov is the "
                "official portal for finding and applying for U.S. federal grants. "
                "Required for DOE, NSF, EDA, USDA, and most non-SBIR federal grants. "
                "Organization must be registered in SAM.gov first."
            ),
            why_needed=(
                "Most federal agencies require Grants.gov submission for non-SBIR grants "
                "(DOE BTO, ARPA-E OPEN, EDA B2S, USDA REAP). SBIR/STTR uses sbir.gov separately. "
                "Creating a Grants.gov account requires SAM.gov registration to be active."
            ),
            external_link="https://www.grants.gov/applicants/registration",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["sam_registration", "uei_number"],
            is_recurring=False,
            order=5,
            notes=(
                f"Inoni LLC Grants.gov: {os.environ.get('INONI_GRANTS_GOV_USERNAME', '[Not configured]')}"
            ),
        ),
        Prerequisite(
            prereq_id="sam_annual_renewal",
            name="SAM.gov Annual Renewal",
            description=(
                "Renew your SAM.gov registration annually to maintain active status. "
                "SAM.gov registrations expire after 365 days. An expired registration "
                "blocks all federal grant awards and disbursements."
            ),
            why_needed=(
                "Federal regulations require active SAM.gov registration to receive award "
                "funds. Awards are paused for entities with expired registrations. "
                "Set a calendar reminder 60 days before expiry."
            ),
            external_link="https://sam.gov/content/entity-registration",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["sam_registration"],
            is_recurring=True,
            renewal_period_days=365,
            order=6,
        ),
        Prerequisite(
            prereq_id="sbir_gov_account",
            name="SBIR.gov / STTR Applicant Registration",
            description=(
                "Register on SBIR.gov for Small Business Innovation Research and STTR "
                "applications. SBIR.gov is separate from Grants.gov. Required for "
                "DOE, NSF, DoD, NIH, and NASA SBIR/STTR applications."
            ),
            why_needed=(
                "SBIR/STTR applications are submitted through agency-specific portals "
                "linked from SBIR.gov, not through Grants.gov. Registration is free "
                "and requires SAM.gov UEI."
            ),
            external_link="https://www.sbir.gov/registration",
            status=PrerequisiteStatus.NOT_STARTED,
            depends_on=["uei_number"],
            is_recurring=False,
            order=7,
        ),
    ]


class PrerequisiteChain:
    """
    Manages the federal grant prerequisite chain.

    Provides status tracking, dependency resolution, and completion logic.
    """

    def __init__(self) -> None:
        prereqs = _make_prerequisites()
        self._prereqs: Dict[str, Prerequisite] = {p.prereq_id: p for p in prereqs}

    def list_prerequisites(self) -> List[Prerequisite]:
        """Return all prerequisites in dependency order."""
        return sorted(self._prereqs.values(), key=lambda p: p.order)

    def get_prerequisite(self, prereq_id: str) -> Prerequisite:
        """Get a specific prerequisite by ID."""
        if prereq_id not in self._prereqs:
            raise KeyError(f"Prerequisite {prereq_id!r} not found")
        return self._prereqs[prereq_id]

    def mark_complete(
        self,
        prereq_id: str,
        notes: Optional[str] = None,
    ) -> Prerequisite:
        """Mark a prerequisite as completed and unblock dependents."""
        prereq = self.get_prerequisite(prereq_id)

        # Check all dependencies are complete
        for dep_id in prereq.depends_on:
            dep = self._prereqs.get(dep_id)
            if dep and dep.status != PrerequisiteStatus.COMPLETED:
                raise ValueError(
                    f"Cannot complete {prereq_id!r}: dependency {dep_id!r} is not yet completed "
                    f"(current status: {dep.status.value})"
                )

        prereq.status = PrerequisiteStatus.COMPLETED
        prereq.completed_at = datetime.utcnow()
        if notes:
            prereq.notes = notes

        return prereq

    def update_status(
        self,
        prereq_id: str,
        status: PrerequisiteStatus,
        notes: Optional[str] = None,
    ) -> Prerequisite:
        """Update the status of a prerequisite."""
        prereq = self.get_prerequisite(prereq_id)
        prereq.status = status
        if notes:
            prereq.notes = notes
        if status == PrerequisiteStatus.COMPLETED:
            prereq.completed_at = datetime.utcnow()
        return prereq

    def get_blocking_prerequisites(self) -> List[Prerequisite]:
        """Return prerequisites that are not yet completed and are blocking dependents."""
        completed_ids = {
            p.prereq_id for p in self._prereqs.values()
            if p.status == PrerequisiteStatus.COMPLETED
        }
        blocking = []
        for prereq in self._prereqs.values():
            if prereq.status == PrerequisiteStatus.COMPLETED:
                continue
            # Check if anything depends on this
            is_depended_on = any(
                prereq.prereq_id in other.depends_on
                for other in self._prereqs.values()
                if other.prereq_id != prereq.prereq_id
            )
            if is_depended_on or not prereq.depends_on:
                blocking.append(prereq)
        return sorted(blocking, key=lambda p: p.order)

    def get_ready_prerequisites(self) -> List[Prerequisite]:
        """Return prerequisites whose dependencies are all complete but they are not yet started."""
        result = []
        for prereq in self._prereqs.values():
            if prereq.status != PrerequisiteStatus.NOT_STARTED:
                continue
            deps_complete = all(
                self._prereqs.get(dep_id, None) is not None
                and self._prereqs[dep_id].status == PrerequisiteStatus.COMPLETED
                for dep_id in prereq.depends_on
            )
            if deps_complete:
                result.append(prereq)
        return sorted(result, key=lambda p: p.order)

    def completion_summary(self) -> Dict:
        """Return a summary of prerequisite completion status."""
        total = len(self._prereqs)
        by_status: Dict[str, int] = {}
        for prereq in self._prereqs.values():
            key = prereq.status.value
            by_status[key] = by_status.get(key, 0) + 1

        completed = by_status.get("completed", 0)
        return {
            "total": total,
            "completed": completed,
            "pct_complete": round(completed / total * 100, 1) if total > 0 else 0.0,
            "by_status": by_status,
            "ready_to_start": [p.prereq_id for p in self.get_ready_prerequisites()],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_prereq_chain: Optional[PrerequisiteChain] = None


def get_prereq_chain() -> PrerequisiteChain:
    global _prereq_chain
    if _prereq_chain is None:
        _prereq_chain = PrerequisiteChain()
    return _prereq_chain
