"""Tests for ROSETTA-ORG-005..008 — CEOBranch↔PSM end-to-end wiring.

Covers the four design labels introduced in the extension:

ROSETTA-ORG-005 — Unify CEOBranch VPs into the org chart
    * ``seed_platform_org(include_vps=True)`` seeds all 11 canonical
      platform roles (4 core + 7 VPs), tree remains valid.
    * ``CEOBranch`` activation writes state via ``seed_platform_org``
      (single writer), and every VPRole's ``agent_id`` matches the
      canonical ``murphy-inc.<role-title>`` form.
    * ``/api/rosetta/org-chart`` (via ``build_org_chart``) reports
      ``role_count >= 10`` with no orphaned VPs.

ROSETTA-ORG-006 — Operator → VP routing
    * Each of the 7 new operators resolves to the correct owner_role
      and a non-empty approver_chain.
    * A known operator whose role is not in the seeded chart surfaces
      ``owner_lookup="role_not_in_chart"`` (not silent "ok").

ROSETTA-ORG-007 — Wire ExecutivePlanningEngine + OperationsCycleEngine
    * When both engines are wired, ``gap_analysis`` includes
      ``executive_initiatives`` + ``operations_cycles`` + ``ok`` status.
    * Missing engines surface as ``not_wired`` in gap_analysis and in
      the LAUNCHED ledger payload.
    * Engine exceptions surface as ``exception`` with the error
      message — never silent.

ROSETTA-ORG-008 — Bidirectional CEOBranch directive routing through PSM
    * ``CEOBranch(psm_launch_hook=...).dispatch_directive_to_psm(
         "VP Engineering", ...)`` produces REQUESTED+APPROVED+LAUNCHED
      ledger entries with ``owner_role="vp-eng"`` and
      ``directive_id`` in ``gap_analysis``.
    * Missing hook → ``hook_not_wired``; unknown label → ``unknown_role``;
      hook exception → ``hook_exception`` (all named, never silent).

License: BSL 1.1 — Inoni LLC — Creator: Corey Post
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Match the rest of the suite's sys.path convention.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT, _REPO_ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.platform_self_modification import (  # noqa: E402
    OPERATOR_HEADER,
    OPERATOR_TOKEN_ENV,
    build_router,
)
from src.platform_self_modification.ledger import SelfEditLedger  # noqa: E402
from src.recursive_stability_controller.lyapunov_monitor import (  # noqa: E402
    LyapunovMonitor,
)
from src.rosetta import (  # noqa: E402
    PLATFORM_ORG_ID,
    RosettaManager,
    build_org_chart,
    lookup_role_for_operator,
    seed_platform_org,
)
from src.rosetta.platform_org_seed import (  # noqa: E402
    CEO_BRANCH_LABEL_TO_ROLE_TITLE,
    PLATFORM_OPERATOR_TO_ROLE,
    _agent_id_for,
)

TOKEN = "test-operator-token-rosetta-org-005-008"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setenv(OPERATOR_TOKEN_ENV, TOKEN)
    yield


def _stable_monitor() -> LyapunovMonitor:
    m = LyapunovMonitor()
    m.update(recursion_energy=1.0, timestamp=1.0, cycle_id=1)
    m.update(recursion_energy=0.5, timestamp=2.0, cycle_id=2)
    return m


class _StubOrchestrator:
    """Captures the gap_analysis passed into ``start_cycle`` for assertions."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def start_cycle(self, gap_analysis=None):
        self.calls.append(gap_analysis)

        class _Cycle:
            cycle_id = "cycle-stub-vp-001"

        return _Cycle()


def _kind(entry):
    k = entry.kind
    return k.value if hasattr(k, "value") else k


# ===========================================================================
# ROSETTA-ORG-005 — VP roster + seed_platform_org(include_vps=True)
# ===========================================================================


def test_seed_platform_org_include_vps_creates_eleven_roles(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    ids = seed_platform_org(m, include_vps=True)
    role_titles = {i.split(".", 1)[1] for i in ids}
    # 4 core + 7 VPs = 11 canonical roles, no duplicates.
    assert len(ids) == 11
    assert len(role_titles) == 11
    assert role_titles == {
        "ceo", "cto", "compliance", "sre",  # core
        "cso", "vp-sales", "vp-ops", "vp-eng",
        "vp-cs", "vp-finance", "vp-marketing",  # VPs
    }


def test_seed_platform_org_include_vps_default_is_backcompat(tmp_path):
    """Without ``include_vps=True``, the roster stays at 4 core roles."""
    m = RosettaManager(persistence_dir=str(tmp_path))
    ids = seed_platform_org(m)  # default include_vps=False
    assert len(ids) == 4
    assert {i.split(".", 1)[1] for i in ids} == {"ceo", "cto", "compliance", "sre"}


def test_seed_with_vps_is_idempotent(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    ids1 = seed_platform_org(m, include_vps=True)
    ids2 = seed_platform_org(m, include_vps=True)
    assert ids1 == ids2
    assert len(m.list_agents()) == 11


def test_seed_with_vps_state_has_canonical_identity(tmp_path):
    """Every seeded VP state has canonical identity.role + organization + phase."""
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m, include_vps=True)
    for vp_title in ("vp-sales", "vp-eng", "cso"):
        s = m.load_state(_agent_id_for(vp_title))
        assert s is not None, f"Missing platform state for {vp_title}"
        assert s.identity.role == vp_title
        assert s.identity.organization == PLATFORM_ORG_ID
        assert s.system_state.status == "idle"
        assert s.agent_state.current_phase == "onboarding"


def test_org_chart_with_vps_reports_eleven_roles(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m, include_vps=True)
    chart = build_org_chart(m)
    assert chart["available"] is True
    assert chart["role_count"] == 11
    assert chart["warnings"] == []
    # agent_count (== role_count here) means no orphaned VPs without contracts.
    assert chart["organisation_id"] == PLATFORM_ORG_ID
    # Spot-check hierarchy: VP Engineering reports to CTO; all others to CEO.
    all_roles: Dict[str, Dict[str, Any]] = {}

    def _flatten(node):
        all_roles[node["role"]] = node
        for child in node.get("reports", []):
            _flatten(child)

    _flatten(chart["tree"])
    assert all_roles["vp-eng"]["reports_to"] == "cto"
    assert all_roles["cso"]["reports_to"] == "ceo"
    assert all_roles["vp-sales"]["reports_to"] == "ceo"


def test_ceo_branch_uses_canonical_agent_ids(tmp_path):
    """CEOBranch-owned VPRoles carry the canonical ``murphy-inc.*`` agent_id."""
    # Import here — ceo_branch_activation lives at src/ root.
    from ceo_branch_activation import CEOBranch  # noqa: E402

    m = RosettaManager(persistence_dir=str(tmp_path))
    branch = CEOBranch(rosetta_manager=m)
    try:
        vp_eng = branch._org_chart.get_role("VP Engineering")
        assert vp_eng is not None
        assert vp_eng.agent_id == _agent_id_for("vp-eng")
        ceo = branch._org_chart.get_role("CEO")
        assert ceo is not None
        assert ceo.agent_id == _agent_id_for("ceo")
    finally:
        # No background threads started without activate(); nothing to clean.
        pass


# ===========================================================================
# ROSETTA-ORG-006 — Operator → VP routing
# ===========================================================================


@pytest.mark.parametrize(
    "operator_id, expected_role, expected_chain",
    [
        ("op-vp-sales", "vp-sales", ["ceo"]),
        ("op-vp-ops", "vp-ops", ["ceo"]),
        ("op-vp-marketing", "vp-marketing", ["ceo"]),
        ("op-vp-eng", "vp-eng", ["cto", "ceo"]),  # eng reports to cto, cto to ceo
        ("op-vp-finance", "vp-finance", ["ceo"]),
        ("op-vp-cs", "vp-cs", ["ceo"]),
        ("op-cso", "cso", ["ceo"]),
    ],
)
def test_vp_operator_resolves_to_correct_role(
    tmp_path, operator_id, expected_role, expected_chain,
):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m, include_vps=True)
    info = lookup_role_for_operator(m, operator_id)
    assert info["owner_lookup"] == "ok", (operator_id, info)
    assert info["owner_role"] == expected_role
    assert info["approver_chain"] == expected_chain


def test_known_vp_operator_without_seeded_vps_is_explicit(tmp_path):
    """If only the 4 core roles are seeded, a known VP operator must not silently report ``ok``."""
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m, include_vps=False)  # VPs absent
    info = lookup_role_for_operator(m, "op-vp-eng")
    assert info["owner_role"] == "vp-eng"
    assert info["owner_lookup"] == "role_not_in_chart"
    assert info["approver_chain"] == []


def test_operator_to_role_map_covers_all_vps():
    """Every VP in CEO_BRANCH_LABEL_TO_ROLE_TITLE has a matching operator row."""
    vp_role_titles = {rt for rt in CEO_BRANCH_LABEL_TO_ROLE_TITLE.values()}
    mapped_roles = set(PLATFORM_OPERATOR_TO_ROLE.values())
    missing = vp_role_titles - mapped_roles
    assert not missing, f"Roles without an operator in PLATFORM_OPERATOR_TO_ROLE: {missing}"


# ===========================================================================
# ROSETTA-ORG-007 — Executive + Operations context in gap_analysis
# ===========================================================================


class _StubPlanner:
    """Duck-typed ExecutiveStrategyPlanner for tests."""

    def __init__(self, initiatives: Optional[List[Dict[str, Any]]] = None,
                 raise_on_rank: bool = False) -> None:
        self._initiatives = initiatives or []
        self._raise = raise_on_rank

    def rank_initiatives(self) -> List[Dict[str, Any]]:
        if self._raise:
            raise RuntimeError("simulated planner failure")
        return list(self._initiatives)


class _StubOpsEngine:
    def __init__(self, status: Optional[Dict[str, Any]] = None,
                 raise_on_status: bool = False) -> None:
        self._status = status or {"active_traction_cycles": 1, "active_rd_cycles": 0}
        self._raise = raise_on_status

    def get_status(self) -> Dict[str, Any]:
        if self._raise:
            raise RuntimeError("simulated ops failure")
        return dict(self._status)


def _build_app(
    *, orchestrator, lyap, ledger_path, manager=None,
    planner_cb=None, ops_cb=None,
):
    app = FastAPI()
    app.include_router(build_router(
        get_orchestrator=lambda: orchestrator,
        get_lyapunov_source=lambda: lyap,
        ledger_path=str(ledger_path),
        get_rosetta_manager=(lambda: manager) if manager is not None else None,
        get_executive_planner=planner_cb,
        get_operations_cycle_engine=ops_cb,
    ))
    return app


def _good_body(operator_id, **extras):
    body = {
        "proposal_id": f"prop-{operator_id}",
        "operator_id": operator_id,
        "justification": "rosetta-org 007/008 test",
    }
    body.update(extras)
    return body


def test_gap_analysis_includes_executive_and_ops_context_when_wired(tmp_path):
    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm, include_vps=True)
    orch = _StubOrchestrator()
    planner = _StubPlanner(initiatives=[
        {"initiative_id": "init-1", "name": "Upsell", "status": "proposed"},
        {"initiative_id": "init-2", "name": "Done", "status": "completed"},  # filtered
        {"initiative_id": "init-3", "name": "Active", "status": "active"},
    ])
    ops = _StubOpsEngine(status={"active_traction_cycles": 2, "active_rd_cycles": 1})
    ledger_path = tmp_path / "led.jsonl"
    app = _build_app(
        orchestrator=orch, lyap=_stable_monitor(), ledger_path=ledger_path,
        manager=rm, planner_cb=lambda: planner, ops_cb=lambda: ops,
    )

    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-vp-eng"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["executive_status"] == "ok"
    assert body["ops_status"] == "ok"
    assert body["owner_role"] == "vp-eng"

    ga = orch.calls[0]
    assert ga["executive_status"] == "ok"
    assert ga["ops_status"] == "ok"
    init_ids = [i["initiative_id"] for i in ga["executive_initiatives"]]
    assert "init-1" in init_ids and "init-3" in init_ids
    assert "init-2" not in init_ids  # completed filtered out
    assert ga["operations_cycles"]["active_traction_cycles"] == 2

    # LAUNCHED ledger payload carries status strings too (queryable audit).
    ledger = SelfEditLedger(ledger_path)
    launched = [e for e in ledger.read_all() if _kind(e) == "LAUNCHED"]
    assert len(launched) == 1
    assert launched[0].payload.get("executive_status") == "ok"
    assert launched[0].payload.get("ops_status") == "ok"


def test_gap_analysis_marks_engines_not_wired_when_callables_missing(tmp_path):
    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm, include_vps=True)
    orch = _StubOrchestrator()
    app = _build_app(
        orchestrator=orch, lyap=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl", manager=rm,
        planner_cb=None, ops_cb=None,
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-vp-sales"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["executive_status"] == "not_wired"
    assert body["ops_status"] == "not_wired"
    ga = orch.calls[0]
    assert ga["executive_initiatives"] == []
    assert ga["operations_cycles"] == {}


def test_gap_analysis_names_engine_exception_loudly(tmp_path):
    """A raising planner must surface as ``exception`` — never silent."""
    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm, include_vps=True)
    orch = _StubOrchestrator()
    planner = _StubPlanner(raise_on_rank=True)
    ops = _StubOpsEngine(raise_on_status=True)
    app = _build_app(
        orchestrator=orch, lyap=_stable_monitor(),
        ledger_path=tmp_path / "led.jsonl", manager=rm,
        planner_cb=lambda: planner, ops_cb=lambda: ops,
    )
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-vp-finance"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202
    ga = orch.calls[0]
    assert ga["executive_status"] == "exception"
    assert ga["ops_status"] == "exception"
    # Launch itself still succeeds — the engines are context, not gates.
    assert ga["executive_initiatives"] == []
    assert ga["operations_cycles"] == {}


# ===========================================================================
# ROSETTA-ORG-008 — CEOBranch → PSM directive bridge
# ===========================================================================


def _make_psm_hook(app_client: TestClient):
    """Build a psm_launch_hook that posts to the TestClient and returns JSON."""
    def hook(body: Dict[str, Any]) -> Dict[str, Any]:
        resp = app_client.post(
            "/api/platform/self-modification/launch",
            json=body,
            headers={OPERATOR_HEADER: TOKEN},
        )
        return resp.json()
    return hook


def test_ceo_directive_routes_through_psm_end_to_end(tmp_path):
    """CEOBranch.dispatch_directive_to_psm → PSM ledger + gap_analysis directive_id."""
    from ceo_branch_activation import CEOBranch  # noqa: E402

    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm, include_vps=True)
    orch = _StubOrchestrator()
    ledger_path = tmp_path / "led.jsonl"
    app = _build_app(
        orchestrator=orch, lyap=_stable_monitor(),
        ledger_path=ledger_path, manager=rm,
    )
    client = TestClient(app)

    branch = CEOBranch(rosetta_manager=rm, psm_launch_hook=_make_psm_hook(client))
    result = branch.dispatch_directive_to_psm(
        "VP Engineering",
        "Ship the caching layer by EOQ",
    )

    assert result["ok"] is True, result
    assert result["reason"] == "ok"
    assert result["operator_id"] == "op-vp-eng"
    assert result["directive_id"]  # non-empty
    directive_id = result["directive_id"]

    # PSM response carries directive_id + owner_role.
    psm_resp = result["psm_response"]
    assert psm_resp["owner_role"] == "vp-eng"
    assert psm_resp["directive_id"] == directive_id

    # Orchestrator gap_analysis references the directive.
    ga = orch.calls[0]
    assert ga["directive_id"] == directive_id
    assert ga["owner_role"] == "vp-eng"

    # Ledger has REQUESTED + APPROVED + LAUNCHED with owner_role=vp-eng.
    ledger = SelfEditLedger(ledger_path)
    kinds_by_proposal: Dict[str, List[str]] = {}
    for e in ledger.read_all():
        kinds_by_proposal.setdefault(e.proposal_id, []).append(_kind(e))
    pid = result["proposal_id"]
    assert "REQUESTED" in kinds_by_proposal[pid]
    assert "APPROVED" in kinds_by_proposal[pid]
    assert "LAUNCHED" in kinds_by_proposal[pid]

    launched = [e for e in ledger.read_all()
                if e.proposal_id == pid and _kind(e) == "LAUNCHED"]
    assert len(launched) == 1
    assert launched[0].payload.get("owner_role") == "vp-eng"
    assert launched[0].payload.get("directive_id") == directive_id


def test_dispatch_without_hook_is_explicit_not_silent():
    from ceo_branch_activation import CEOBranch  # noqa: E402

    branch = CEOBranch()  # no psm_launch_hook
    result = branch.dispatch_directive_to_psm("VP Engineering", "anything")
    assert result["ok"] is False
    assert result["reason"] == "hook_not_wired"
    assert result["directive_id"]  # still provided for correlation
    assert result["operator_id"] is None


def test_dispatch_unknown_role_label_is_explicit():
    from ceo_branch_activation import CEOBranch  # noqa: E402

    calls = []

    def hook(body):
        calls.append(body)
        return {"ok": True}

    branch = CEOBranch(psm_launch_hook=hook)
    result = branch.dispatch_directive_to_psm("Nobody In Particular", "anything")
    assert result["ok"] is False
    assert result["reason"] == "unknown_role"
    assert calls == []  # hook must NOT be invoked when label is unknown


def test_dispatch_hook_exception_is_explicit():
    from ceo_branch_activation import CEOBranch  # noqa: E402

    def broken_hook(body):
        raise RuntimeError("network down")

    branch = CEOBranch(psm_launch_hook=broken_hook)
    result = branch.dispatch_directive_to_psm("VP Sales", "do the thing")
    assert result["ok"] is False
    assert result["reason"] == "hook_exception"
    assert "network down" in result["error"]
    assert result["operator_id"] == "op-vp-sales"  # resolved before the crash
