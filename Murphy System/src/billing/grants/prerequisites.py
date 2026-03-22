"""Registration chain prerequisites for grant applications."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.billing.grants.models import Prerequisite, PrereqStatus

# Ordered prerequisite chain: EIN → SAM.gov → Grants.gov → SBIR.gov → Research.gov → NIST MEP
_PREREQUISITES: List[Prerequisite] = [
    Prerequisite(
        prereq_id="ein",
        name="EIN Registration",
        description=(
            "Obtain an Employer Identification Number (EIN) from the IRS. "
            "Required as the foundation for all other federal registrations. "
            "Apply online at IRS.gov in ~5 minutes."
        ),
        verification_url="https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
        status=PrereqStatus.not_started,
        blocks=[],  # EIN is required for everything but doesn't block in chain
        estimated_days=1,
    ),
    Prerequisite(
        prereq_id="sam_gov",
        name="SAM.gov Registration",
        description=(
            "Register in System for Award Management (SAM.gov). Required for "
            "all federal grants, contracts, and cooperative agreements. "
            "Takes 1-3 business days to activate; allow up to 10 business days. "
            "Requires EIN and DUNS/UEI number."
        ),
        verification_url="https://sam.gov/content/entity-registration",
        status=PrereqStatus.not_started,
        blocks=["sbir_phase1", "sbir_phase2", "sbir_breakthrough", "sttr",
                "doe_arpa_e", "doe_amo", "doe_bto", "cesmii", "nsf_convergence",
                "nsf_pfi", "eda_b2s", "nist_mep", "doe_grip", "usda_reap"],
        estimated_days=10,
    ),
    Prerequisite(
        prereq_id="grants_gov",
        name="Grants.gov Registration",
        description=(
            "Register at Grants.gov as an Authorized Organization Representative (AOR). "
            "Required to submit federal grant applications. Requires SAM.gov registration. "
            "Allows 3-5 business days for AOR authorization."
        ),
        verification_url="https://www.grants.gov/register.html",
        status=PrereqStatus.not_started,
        blocks=["doe_arpa_e", "doe_amo", "doe_bto", "nsf_convergence",
                "nsf_pfi", "eda_b2s", "doe_grip", "usda_reap"],
        estimated_days=5,
    ),
    Prerequisite(
        prereq_id="sbir_gov",
        name="SBIR.gov Registration",
        description=(
            "Register at SBIR.gov to access SBIR/STTR solicitations and submit "
            "applications to participating agencies (DOE, NSF, DOD, NIH, NASA, etc.). "
            "Requires SAM.gov UEI number."
        ),
        verification_url="https://www.sbir.gov/registration",
        status=PrereqStatus.not_started,
        blocks=["sbir_phase1", "sbir_phase2", "sbir_breakthrough", "sttr"],
        estimated_days=2,
    ),
    Prerequisite(
        prereq_id="research_gov",
        name="Research.gov Registration",
        description=(
            "Register at Research.gov for NSF grant submissions. Required to submit "
            "NSF SBIR, STTR, PFI, and Convergence Accelerator proposals. "
            "Organization registration requires a signing official."
        ),
        verification_url="https://www.research.gov/research-portal/appmanager/base/desktop?_nfpb=true&_pageLabel=research_home_page",
        status=PrereqStatus.not_started,
        blocks=["nsf_convergence", "nsf_pfi", "sttr"],
        estimated_days=3,
    ),
    Prerequisite(
        prereq_id="nist_mep",
        name="NIST MEP Network Engagement",
        description=(
            "Connect with your local NIST Manufacturing Extension Partnership (MEP) center. "
            "Required to access MEP-facilitated vouchers, technical assistance, and "
            "manufacturing grants. Contact local MEP center to initiate engagement."
        ),
        verification_url="https://www.nist.gov/mep/mep-national-network",
        status=PrereqStatus.not_started,
        blocks=["nist_mep"],
        estimated_days=5,
    ),
]

# Per-session prerequisite status override store
_SESSION_PREREQ_STATUS: Dict[str, Dict[str, PrereqStatus]] = {}


def get_prerequisite_chain() -> List[Prerequisite]:
    """Return the ordered prerequisite chain.

    Returns:
        List of Prerequisite objects in recommended completion order.
    """
    return list(_PREREQUISITES)


def check_prerequisite_status(session_id: str, prereq_id: str) -> PrereqStatus:
    """Check current status of a prerequisite for a session.

    Args:
        session_id: Session to check status for.
        prereq_id: ID of the prerequisite to check.

    Returns:
        PrereqStatus for this session/prereq combo, defaulting to not_started.
    """
    session_overrides = _SESSION_PREREQ_STATUS.get(session_id, {})
    return session_overrides.get(prereq_id, PrereqStatus.not_started)


def update_prerequisite_status(
    session_id: str, prereq_id: str, status: PrereqStatus
) -> Prerequisite:
    """Update prerequisite status for a session.

    Args:
        session_id: Session to update.
        prereq_id: ID of the prerequisite to update.
        status: New status to set.

    Returns:
        The prerequisite with the updated status reflected.

    Raises:
        ValueError: If prereq_id is not found in the prerequisite chain.
    """
    prereq = next((p for p in _PREREQUISITES if p.prereq_id == prereq_id), None)
    if prereq is None:
        raise ValueError(f"Unknown prerequisite ID: {prereq_id!r}")

    _SESSION_PREREQ_STATUS.setdefault(session_id, {})[prereq_id] = status

    # Return a copy with the session-specific status applied
    return prereq.model_copy(update={"status": status})


def get_session_prereq_summary(session_id: str) -> Dict[str, Any]:
    """Get a summary of all prerequisites status for a session.

    Args:
        session_id: Session to summarize.

    Returns:
        Dict with keys:
            - prerequisites: list of {prereq_id, name, status, estimated_days, blocks}
            - total: total count
            - completed: count of completed prereqs
            - completion_pct: float 0.0-100.0
            - ready_to_apply: list of grant IDs unblocked by completed prereqs
    """
    session_overrides = _SESSION_PREREQ_STATUS.get(session_id, {})
    summary_list = []
    completed_prereq_ids = set()

    for p in _PREREQUISITES:
        status = session_overrides.get(p.prereq_id, PrereqStatus.not_started)
        if status == PrereqStatus.completed:
            completed_prereq_ids.add(p.prereq_id)
        summary_list.append({
            "prereq_id": p.prereq_id,
            "name": p.name,
            "status": status.value,
            "estimated_days": p.estimated_days,
            "blocks": p.blocks,
            "verification_url": p.verification_url,
        })

    total = len(_PREREQUISITES)
    completed = len(completed_prereq_ids)
    completion_pct = (completed / total * 100.0) if total > 0 else 0.0

    # Determine which grants are unlocked (no longer blocked)
    all_blocking: Dict[str, List[str]] = {p.prereq_id: p.blocks for p in _PREREQUISITES}
    still_blocked: set = set()
    for prereq_id, blocks in all_blocking.items():
        if prereq_id not in completed_prereq_ids:
            still_blocked.update(blocks)

    return {
        "prerequisites": summary_list,
        "total": total,
        "completed": completed,
        "completion_pct": round(completion_pct, 1),
        "ready_to_apply": [g for g in _get_all_blocked_grants() if g not in still_blocked],
    }


def _get_all_blocked_grants() -> List[str]:
    """Return the union of all grant IDs that appear in any prerequisite's blocks list."""
    result: List[str] = []
    seen: set = set()
    for p in _PREREQUISITES:
        for g in p.blocks:
            if g not in seen:
                result.append(g)
                seen.add(g)
    return result
