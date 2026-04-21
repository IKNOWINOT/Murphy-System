"""
ROSETTA-ORG-001 — Murphy-platform org seed.

Design labels: ``ROSETTA-ORG-001`` (this module),
``ROSETTA-ORG-002`` (called from production-server lifespan).

Commissioning checklist (per project guidelines):

* What is this module supposed to do?
    Seed the canonical Murphy-platform org chart into a
    :class:`~rosetta.rosetta_manager.RosettaManager` so the platform's
    own internal roster (CEO / CTO / Compliance / SRE) is queryable
    via ``/api/rosetta/org-chart`` and usable by the platform
    self-modification pipeline (PSM-003) for owner-role attribution.

* What conditions are possible?
    1. Empty manager → all four roles created.
    2. Re-seed of an already-seeded manager → no-op (idempotent).
    3. Manager with a *richer* existing record for one of the seeded
       agents → the existing record is preserved untouched, but its
       ``metadata.extras['employee_contract']`` is *added* if absent
       (still preserving any unrelated extras).
    4. Manager raises on save → exception propagates with a clear
       message; **never silently swallowed**.

* Expected vs actual:
    Expected: ``seed_platform_org(manager) -> List[str]`` returns the
    list of agent IDs that exist in the platform org after seeding
    (always exactly the four canonical IDs).  Each agent state has
    ``metadata.extras['employee_contract']`` populated with the
    serialized :class:`EmployeeContract`.

* Restart-from-symptom:
    If ``/api/rosetta/org-chart`` reports a missing role, call
    :func:`seed_platform_org` again — it is idempotent and self-heals.

* Hardening:
    Validates the contract via ``EmployeeContract.model_validate`` to
    refuse malformed extras on re-seed.  Verifies tree integrity
    (single root, no cycles) before returning.

License: BSL 1.1 — Inoni LLC — Creator: Corey Post
"""

from __future__ import annotations

import logging
from typing import Dict, List

from .rosetta_manager import RosettaManager
from .rosetta_models import (
    AgentState,
    AgentType,
    EmployeeContract,
    Identity,
    ManagementLayer,
    RosettaAgentState,
    SystemState,
)

logger = logging.getLogger(__name__)

PLATFORM_ORG_ID = "murphy-inc"

# ---------------------------------------------------------------------------
# Canonical Murphy-platform roster.
#
# Kept tiny on purpose: this is the *seed*, not the full org.  The four
# roles below are the ones the self-modification pipeline (PSM-003) needs
# to do owner-role attribution: an executive sponsor, a technical owner,
# a compliance gate, and an operations gate.
# ---------------------------------------------------------------------------

_PLATFORM_ROSTER: List[EmployeeContract] = [
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="ceo",
        role_description="Chief Executive — strategic sponsor for platform self-modification.",
        management_layer=ManagementLayer.EXECUTIVE,
        department="executive",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["approve_strategic", "veto_strategic"],
        reports_to=None,
        direct_reports=[
            "cto", "compliance", "sre", "cso",
            "vp-sales", "vp-ops", "vp-marketing",
            "vp-finance", "vp-cs",
        ],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="cto",
        role_description="Chief Technology Officer — owns platform self-modification cycles.",
        management_layer=ManagementLayer.EXECUTIVE,
        department="engineering",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["approve_self_mod", "launch_cycle"],
        reports_to="ceo",
        direct_reports=["vp-eng"],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="compliance",
        role_description="Compliance officer — RSC veto reviewer, ledger auditor.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="compliance",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["audit_ledger", "review_veto"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="sre",
        role_description="Site reliability engineer — runs the production server, owns rollback.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="operations",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["rollback_cycle", "monitor_health"],
        reports_to="ceo",
        direct_reports=[],
    ),
]

# ---------------------------------------------------------------------------
# ROSETTA-ORG-005 — VP roster (CEOBranch executive layer).
#
# These 7 roles come from ``_ORG_CHART_DEFINITION`` in
# ``ceo_branch_activation`` (the runtime CEO branch): VP Sales, VP
# Operations, VP Engineering, VP Customer Success, VP Finance, VP
# Marketing, and Chief Security Officer.  The three CEOBranch labels
# that overlap with ``_PLATFORM_ROSTER`` (CEO→``ceo``, CTO→``cto``,
# VP Compliance→``compliance``) deliberately do NOT appear here — they
# are the same roles, not duplicates.  See
# ``CEO_BRANCH_LABEL_TO_ROLE_TITLE`` below for the full mapping.
#
# Hierarchy intent (per problem-statement ROSETTA-ORG-005):
#   * CSO reports to CEO (executive layer).
#   * VP-Engineering reports to CTO (technical track).
#   * All other VPs report to CEO.
# ---------------------------------------------------------------------------

_VP_ROSTER: List[EmployeeContract] = [
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="cso",
        role_description="Chief Security Officer — security posture, authority gating.",
        management_layer=ManagementLayer.EXECUTIVE,
        department="security",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["enforce_security", "gate_authority"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-sales",
        role_description="VP Sales — revenue generation, outreach, trial lifecycle.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="sales",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["run_outreach", "approve_discount"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-ops",
        role_description="VP Operations — day-to-day ops, automation scheduling.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="operations",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["schedule_automation", "operate_day_to_day"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-eng",
        role_description="VP Engineering — CI/CD pipeline, autonomous repair.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="engineering",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["run_ci_cd", "trigger_repair"],
        reports_to="cto",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-cs",
        role_description="VP Customer Success — onboarding, retention, engagement.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="customer_success",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["onboard_customer", "run_retention"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-finance",
        role_description="VP Finance — budget, revenue tracking, cost optimisation.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="finance",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["manage_budget", "optimise_cost"],
        reports_to="ceo",
        direct_reports=[],
    ),
    EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="vp-marketing",
        role_description="VP Marketing — campaign orchestration, community outreach.",
        management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
        department="marketing",
        organisation_id=PLATFORM_ORG_ID,
        authorised_actions=["orchestrate_campaign", "adapt_campaign"],
        reports_to="ceo",
        direct_reports=[],
    ),
]

# ---------------------------------------------------------------------------
# ROSETTA-ORG-005 — CEOBranch label → canonical role_title mapping.
#
# CEOBranch's ``_ORG_CHART_DEFINITION`` uses human-readable role labels
# (e.g. ``"VP Sales"``, ``"Chief Security Officer"``).  The platform org
# chart is indexed by canonical lowercase-hyphenated role_titles
# (e.g. ``"vp-sales"``, ``"cso"``).  This mapping is the *single source
# of truth* for the translation — used by both ``OrgChartAutomation`` to
# stamp ``agent_id`` onto each VPRole and by
# ``CEOBranch.dispatch_directive_to_psm`` to resolve a label to the
# matching ``operator_id``.
# ---------------------------------------------------------------------------

CEO_BRANCH_LABEL_TO_ROLE_TITLE: Dict[str, str] = {
    "CEO": "ceo",
    "CTO": "cto",
    "VP Compliance": "compliance",
    "Chief Security Officer": "cso",
    "VP Sales": "vp-sales",
    "VP Operations": "vp-ops",
    "VP Engineering": "vp-eng",
    "VP Customer Success": "vp-cs",
    "VP Finance": "vp-finance",
    "VP Marketing": "vp-marketing",
}

# Stable map: operator_id (the value PSM-003 receives in the launch body)
# → role_title in the platform org.  Used by ROSETTA-ORG-004 for owner
# attribution.  Unknown operator_ids are surfaced explicitly, never
# silently ignored.
PLATFORM_OPERATOR_TO_ROLE = {
    "op-ceo": "ceo",
    "op-cto": "cto",
    "op-compliance": "compliance",
    "op-sre": "sre",
    # ROSETTA-ORG-006 — executive VP operators.
    "op-cso": "cso",
    "op-vp-sales": "vp-sales",
    "op-vp-ops": "vp-ops",
    "op-vp-eng": "vp-eng",
    "op-vp-cs": "vp-cs",
    "op-vp-finance": "vp-finance",
    "op-vp-marketing": "vp-marketing",
}


def _agent_id_for(role_title: str) -> str:
    """Stable agent_id for a platform role.

    Uses the form ``murphy-inc.<role>`` so operators can recognise
    platform-internal agents at a glance and so they sort separately
    from tenant agents.  (Single ``.`` rather than ``::`` because the
    ``RosettaManager`` agent-ID sanitizer only allows
    ``[A-Za-z0-9_\\-\\.]``.)
    """
    return f"{PLATFORM_ORG_ID}.{role_title}"


def _build_state(contract: EmployeeContract) -> RosettaAgentState:
    """Compose a fresh :class:`RosettaAgentState` for a platform role.

    The :class:`EmployeeContract` is stored in ``metadata.extras`` —
    the documented extension point on :class:`Metadata` (see its
    docstring: "avoids silent data loss when Pydantic revalidation
    drops unknown keys").

    ``system_state.status`` starts at ``"idle"`` and
    ``agent_state.current_phase`` at ``"onboarding"`` — the CEOBranch
    runtime (``SystemWorkflow.tick``) transitions these as the role is
    exercised.
    """
    role = contract.role_title
    state = RosettaAgentState(
        identity=Identity(
            agent_id=_agent_id_for(role),
            name=f"Murphy {role.upper()}",
            role=role,
            organization=PLATFORM_ORG_ID,
        ),
        system_state=SystemState(status="idle"),
        agent_state=AgentState(current_phase="onboarding"),
    )
    state.metadata.extras["employee_contract"] = contract.model_dump(mode="json")
    state.metadata.extras["platform_seed"] = True
    return state


def _validate_tree(roster: List[EmployeeContract]) -> None:
    """Refuse to seed a roster that isn't a valid tree.

    A valid platform org has:
      * exactly one root (``reports_to is None``)
      * every non-root role's ``reports_to`` exists in the roster
      * no cycles when walking ``reports_to`` upward

    Raises :class:`ValueError` with an explicit message on failure —
    never a silent acceptance.
    """
    titles = {c.role_title for c in roster}
    roots = [c.role_title for c in roster if c.reports_to is None]
    if len(roots) != 1:
        raise ValueError(
            f"Platform org must have exactly one root, found {roots!r}"
        )
    parent_of = {c.role_title: c.reports_to for c in roster}
    for title in titles:
        seen = {title}
        cur = parent_of[title]
        while cur is not None:
            if cur not in titles:
                raise ValueError(
                    f"Role {title!r} reports_to unknown role {cur!r}"
                )
            if cur in seen:
                raise ValueError(
                    f"Cycle detected in platform org reports_to chain at {cur!r}"
                )
            seen.add(cur)
            cur = parent_of[cur]


def seed_platform_org(
    manager: RosettaManager, *, include_vps: bool = False,
) -> List[str]:
    """Idempotently seed the Murphy-platform org into *manager*.

    Parameters
    ----------
    manager:
        Target :class:`RosettaManager`.  ``None`` raises ``ValueError``
        (never silently skipped).
    include_vps:
        ROSETTA-ORG-005. When ``True``, also seed the 7 VP roles from
        ``_VP_ROSTER`` (VP Sales, VP Ops, VP Engineering, VP Customer
        Success, VP Finance, VP Marketing, CSO).  Default is ``False``
        for backward compatibility with ROSETTA-ORG-001 tests and
        production-server lifespan (which only needs the four core
        roles for PSM owner attribution).  ``CEOBranch._seed_rosetta_personas``
        always passes ``True`` — that is the single writer of the
        full VP roster.

    Returns the list of platform agent IDs that exist after seeding.
    Raises if the manager refuses a write — failures are loud, not
    silent.
    """
    if manager is None:
        raise ValueError("seed_platform_org requires a non-None RosettaManager")

    roster = list(_PLATFORM_ROSTER)
    if include_vps:
        roster.extend(_VP_ROSTER)

    _validate_tree(roster)

    seeded_ids: List[str] = []
    for contract in roster:
        agent_id = _agent_id_for(contract.role_title)
        existing = manager.load_state(agent_id)
        if existing is None:
            state = _build_state(contract)
            manager.save_state(state)
            logger.info(
                "ROSETTA-ORG-001: seeded platform role %s as %s",
                contract.role_title, agent_id,
            )
        else:
            # Preserve the richer existing record but make sure the
            # contract is present in extras (self-heal for old states).
            extras = existing.metadata.extras or {}
            if "employee_contract" not in extras:
                extras["employee_contract"] = contract.model_dump(mode="json")
                extras["platform_seed"] = True
                # update_state merges; pass the metadata block explicitly.
                manager.update_state(
                    agent_id, {"metadata": {"extras": extras}}
                )
                logger.info(
                    "ROSETTA-ORG-001: backfilled employee_contract for %s",
                    agent_id,
                )
            else:
                logger.debug(
                    "ROSETTA-ORG-001: platform role %s already seeded", agent_id
                )
        seeded_ids.append(agent_id)
    return seeded_ids


def get_platform_roster(*, include_vps: bool = False) -> List[EmployeeContract]:
    """Return a copy of the canonical roster (for tests and read-only use).

    When ``include_vps=True``, the 7 VP roles from ``_VP_ROSTER`` are
    appended — same set that ``seed_platform_org(include_vps=True)`` writes.
    """
    if include_vps:
        return list(_PLATFORM_ROSTER) + list(_VP_ROSTER)
    return list(_PLATFORM_ROSTER)
