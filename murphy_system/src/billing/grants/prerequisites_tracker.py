"""
Prerequisites Tracker — Tracks SAM.gov, UEI, CAGE, and other grant prerequisites.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.billing.grants.grant_database import get_program


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Prerequisite:
    prereq_id: str
    name: str
    description: str
    instructions: str
    url: str
    estimated_days: int
    completed: bool = False
    completed_at: Optional[datetime] = None
    depends_on: List[str] = field(default_factory=list)


_BASE_PREREQUISITES: Dict[str, Prerequisite] = {
    "sam_gov_registration": Prerequisite(
        prereq_id="sam_gov_registration",
        name="SAM.gov Entity Registration",
        description="Register your entity in the System for Award Management.",
        instructions=(
            "Visit https://sam.gov and click 'Register New Entity'. You will need your "
            "EIN/TIN, banking information, and legal business name. The process takes "
            "approximately 10 business days."
        ),
        url="https://sam.gov",
        estimated_days=10,
        depends_on=[],
    ),
    "sam_gov_uei": Prerequisite(
        prereq_id="sam_gov_uei",
        name="Unique Entity Identifier (UEI)",
        description="Obtain your Unique Entity Identifier from SAM.gov.",
        instructions=(
            "Your UEI is automatically assigned during SAM.gov registration. If you need "
            "a standalone UEI, visit https://sam.gov/content/entity-registration and "
            "request a UEI. This is required for all federal grants."
        ),
        url="https://sam.gov/content/entity-registration",
        estimated_days=3,
        depends_on=["sam_gov_registration"],
    ),
    "cage_code": Prerequisite(
        prereq_id="cage_code",
        name="CAGE Code",
        description="Obtain your Commercial and Government Entity Code.",
        instructions=(
            "CAGE codes are assigned by the Defense Logistics Agency. After SAM.gov "
            "registration, your CAGE code is typically assigned within 7 business days. "
            "Check your SAM.gov registration status at https://sam.gov."
        ),
        url="https://cage.dla.mil",
        estimated_days=7,
        depends_on=["sam_gov_uei"],
    ),
    "grants_gov_account": Prerequisite(
        prereq_id="grants_gov_account",
        name="Grants.gov Account",
        description="Create an account on Grants.gov for federal grant applications.",
        instructions=(
            "Create a free account at https://www.grants.gov/web/grants/register.html. "
            "You will need your UEI number. Account activation is usually immediate."
        ),
        url="https://www.grants.gov/web/grants/register.html",
        estimated_days=1,
        depends_on=["sam_gov_uei"],
    ),
    "duns_number": Prerequisite(
        prereq_id="duns_number",
        name="DUNS Number (Legacy)",
        description="Legacy D-U-N-S Number (now superseded by UEI for most programs).",
        instructions=(
            "DUNS numbers have been replaced by UEI for most federal grants. If still "
            "required, visit https://www.dnb.com/duns-number.html. Most programs now "
            "use UEI instead."
        ),
        url="https://www.dnb.com/duns-number.html",
        estimated_days=5,
        depends_on=[],
    ),
}


class PrerequisitesTracker:
    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Prerequisite]] = {}

    def initialize_for_session(self, session_id: str) -> Dict[str, Prerequisite]:
        prereqs = {k: copy.deepcopy(v) for k, v in _BASE_PREREQUISITES.items()}
        self._sessions[session_id] = prereqs
        return prereqs

    def get_prerequisites(self, session_id: str) -> Dict[str, Prerequisite]:
        if session_id not in self._sessions:
            return self.initialize_for_session(session_id)
        return self._sessions[session_id]

    def mark_complete(
        self,
        session_id: str,
        prereq_id: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Prerequisite]:
        prereqs = self.get_prerequisites(session_id)
        prereq = prereqs.get(prereq_id)
        if prereq is None:
            return None
        prereq.completed = True
        prereq.completed_at = completed_at or _now()
        return prereq

    def get_blocking_prerequisites(
        self,
        session_id: str,
        required_prereqs: List[str],
    ) -> List[Prerequisite]:
        prereqs = self.get_prerequisites(session_id)
        return [
            prereqs[pid]
            for pid in required_prereqs
            if pid in prereqs and not prereqs[pid].completed
        ]

    def is_application_ready(
        self,
        session_id: str,
        program_id: str,
    ) -> Tuple[bool, List[Prerequisite]]:
        program = get_program(program_id)
        if program is None:
            return False, []
        blocking = self.get_blocking_prerequisites(session_id, program.prerequisites)
        return len(blocking) == 0, blocking
