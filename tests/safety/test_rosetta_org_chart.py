"""Tests for ROSETTA-ORG-001..004 — Murphy-platform org chart.

Test profile (designed to cover the full range of conditions named in
the module docstrings):

ROSETTA-ORG-001 (platform_org_seed)
    * empty manager → 4 roles seeded with correct reports_to
    * idempotent re-seed → no duplicates, no overwrites
    * tree validator catches multi-root, cycle, dangling parent
    * None manager raises ValueError (no silent skip)

ROSETTA-ORG-003 (org_chart.build_org_chart)
    * happy seeded path → single rooted tree, 4 roles, deterministic order
    * empty manager → available=False, reason=empty
    * None manager → available=False, reason=no_manager
    * cycle detection → available=False, reason=cycle, cycle path returned
    * orphan parent → role promoted to root, warning emitted, never silent

ROSETTA-ORG-004 (lookup_role_for_operator + PSM endpoint integration)
    * known operator → owner_role + approver_chain populated
    * unknown operator → owner_lookup="unknown_operator" (loud, not silent)
    * None manager → owner_lookup="no_manager"
    * PSM /launch endpoint with seeded manager + known op-cto:
        - 202, owner_role="cto" in response and APPROVED+LAUNCHED ledger entries
    * PSM /launch with unknown operator: 202 still, owner_lookup recorded
    * PSM /launch when get_rosetta_manager not provided: backwards-compatible
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform_self_modification import (
    OPERATOR_HEADER,
    OPERATOR_TOKEN_ENV,
    build_router,
)
from src.platform_self_modification.ledger import SelfEditLedger
from src.recursive_stability_controller.lyapunov_monitor import LyapunovMonitor
from src.rosetta import (
    PLATFORM_ORG_ID,
    RosettaManager,
    build_org_chart,
    get_platform_roster,
    lookup_role_for_operator,
    seed_platform_org,
)
from src.rosetta.platform_org_seed import _agent_id_for, _validate_tree
from src.rosetta.rosetta_models import (
    AgentType,
    EmployeeContract,
    Identity,
    ManagementLayer,
    RosettaAgentState,
)


TOKEN = "test-operator-token-rosetta-org-tests"


# ---------------------------------------------------------------------------
# ROSETTA-ORG-001 — seed
# ---------------------------------------------------------------------------

def test_seed_creates_four_roles(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    ids = seed_platform_org(m)
    assert sorted(ids) == sorted([
        f"{PLATFORM_ORG_ID}.ceo",
        f"{PLATFORM_ORG_ID}.cto",
        f"{PLATFORM_ORG_ID}.compliance",
        f"{PLATFORM_ORG_ID}.sre",
    ])
    # Every state has the contract in extras.
    for aid in ids:
        s = m.load_state(aid)
        assert s is not None
        assert s.metadata.extras.get("platform_seed") is True
        contract = s.metadata.extras.get("employee_contract")
        assert contract is not None
        assert contract["role_title"] == aid.split(".", 1)[1]


def test_seed_is_idempotent(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    ids1 = seed_platform_org(m)
    # Reseed: must not duplicate or overwrite.
    ids2 = seed_platform_org(m)
    assert ids1 == ids2
    assert len(m.list_agents()) == 4


def test_seed_backfills_missing_contract(tmp_path):
    """If a platform-named state exists without a contract, seed self-heals."""
    m = RosettaManager(persistence_dir=str(tmp_path))
    bare = RosettaAgentState(identity=Identity(
        agent_id=_agent_id_for("cto"), name="bare", role="cto",
        organization=PLATFORM_ORG_ID,
    ))
    # Note: extras intentionally empty.
    m.save_state(bare)
    seed_platform_org(m)
    s = m.load_state(_agent_id_for("cto"))
    assert s.metadata.extras.get("employee_contract") is not None
    assert s.metadata.extras["employee_contract"]["role_title"] == "cto"


def test_seed_rejects_none_manager():
    with pytest.raises(ValueError, match="non-None"):
        seed_platform_org(None)


def test_validate_tree_rejects_multiple_roots():
    bad = [
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="a",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to=None),
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="b",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to=None),
    ]
    with pytest.raises(ValueError, match="exactly one root"):
        _validate_tree(bad)


def test_validate_tree_rejects_cycle():
    bad = [
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="a",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to="b"),
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="b",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to="a"),
    ]
    with pytest.raises(ValueError, match="(Cycle|exactly one root)"):
        _validate_tree(bad)


def test_validate_tree_rejects_unknown_parent():
    bad = [
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="a",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to=None),
        EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="b",
                         management_layer=ManagementLayer.EXECUTIVE,
                         organisation_id="x", reports_to="ghost"),
    ]
    with pytest.raises(ValueError, match="unknown role"):
        _validate_tree(bad)


def test_canonical_roster_validates():
    # The shipped roster must always be a valid tree.
    _validate_tree(get_platform_roster())


# ---------------------------------------------------------------------------
# ROSETTA-ORG-003 — build_org_chart
# ---------------------------------------------------------------------------

def test_org_chart_happy_path(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m)
    chart = build_org_chart(m)
    assert chart["available"] is True
    assert chart["role_count"] == 4
    assert chart["organisation_id"] == PLATFORM_ORG_ID
    assert chart["tree"]["role"] == "ceo"
    children = sorted(c["role"] for c in chart["tree"]["reports"])
    assert children == ["compliance", "cto", "sre"]
    assert chart["warnings"] == []


def test_org_chart_empty_manager(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    chart = build_org_chart(m)
    assert chart["available"] is False
    assert chart["reason"] == "empty"


def test_org_chart_none_manager():
    chart = build_org_chart(None)
    assert chart["available"] is False
    assert chart["reason"] == "no_manager"


def test_org_chart_detects_cycle(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    # Hand-craft two states that form a cycle in their contracts.
    for role, parent in [("alpha", "beta"), ("beta", "alpha")]:
        contract = EmployeeContract(
            agent_type=AgentType.AUTOMATION,
            role_title=role,
            management_layer=ManagementLayer.MIDDLE_MANAGEMENT,
            organisation_id="cyc-org",
            reports_to=parent,
        )
        s = RosettaAgentState(identity=Identity(
            agent_id=f"cyc.{role}", name=role, role=role,
            organization="cyc-org",
        ))
        s.metadata.extras["employee_contract"] = contract.model_dump(mode="json")
        m.save_state(s)
    chart = build_org_chart(m)
    assert chart["available"] is False
    assert chart["reason"] == "cycle"
    assert "alpha" in chart["cycle"] and "beta" in chart["cycle"]


def test_org_chart_orphan_parent_is_loud(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    contract = EmployeeContract(
        agent_type=AgentType.AUTOMATION,
        role_title="loner",
        management_layer=ManagementLayer.INDIVIDUAL,
        organisation_id="orph",
        reports_to="missing-boss",
    )
    s = RosettaAgentState(identity=Identity(
        agent_id="orph.loner", name="loner", role="loner",
        organization="orph",
    ))
    s.metadata.extras["employee_contract"] = contract.model_dump(mode="json")
    m.save_state(s)
    chart = build_org_chart(m)
    # Single role total → still tree-shaped, but warning explicit.
    assert chart["available"] is True
    assert any(w.startswith("orphan_role:loner") for w in chart["warnings"])


def test_org_chart_skips_agents_without_contract_loudly(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m)
    # Add an agent with no contract — it must be reported, never silently dropped.
    s = RosettaAgentState(identity=Identity(
        agent_id="random.agent", name="r", role="r", organization="x",
    ))
    m.save_state(s)
    chart = build_org_chart(m)
    assert chart["available"] is True
    assert any(w.startswith("no_contract:random.agent") for w in chart["warnings"])


# ---------------------------------------------------------------------------
# ROSETTA-ORG-004 — operator → role lookup
# ---------------------------------------------------------------------------

def test_lookup_known_operator(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m)
    info = lookup_role_for_operator(m, "op-cto")
    assert info["owner_lookup"] == "ok"
    assert info["owner_role"] == "cto"
    assert info["approver_chain"] == ["ceo"]


def test_lookup_unknown_operator_is_explicit(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m)
    info = lookup_role_for_operator(m, "op-nobody")
    assert info["owner_lookup"] == "unknown_operator"
    assert info["owner_role"] is None


def test_lookup_no_manager():
    info = lookup_role_for_operator(None, "op-cto")
    assert info["owner_lookup"] == "no_manager"
    assert info["owner_role"] is None


def test_lookup_root_operator_has_empty_chain(tmp_path):
    m = RosettaManager(persistence_dir=str(tmp_path))
    seed_platform_org(m)
    info = lookup_role_for_operator(m, "op-ceo")
    assert info["owner_role"] == "ceo"
    assert info["approver_chain"] == []  # root has no approvers above it


# ---------------------------------------------------------------------------
# ROSETTA-ORG-004 — PSM router integration
# ---------------------------------------------------------------------------

class _StubOrchestrator:
    def __init__(self):
        self.calls = []

    def start_cycle(self, gap_analysis=None):
        self.calls.append(gap_analysis)

        class _Cycle:
            cycle_id = "cycle-stub-org-001"

        return _Cycle()


def _stable_monitor() -> LyapunovMonitor:
    m = LyapunovMonitor()
    m.update(recursion_energy=1.0, timestamp=1.0, cycle_id=1)
    m.update(recursion_energy=0.5, timestamp=2.0, cycle_id=2)
    return m


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setenv(OPERATOR_TOKEN_ENV, TOKEN)
    yield


def _build_app(orchestrator, lyap, ledger_path, manager):
    app = FastAPI()
    app.include_router(build_router(
        get_orchestrator=lambda: orchestrator,
        get_lyapunov_source=lambda: lyap,
        ledger_path=str(ledger_path),
        get_rosetta_manager=lambda: manager,
    ))
    return app


def _good_body(operator_id):
    return {
        "proposal_id": f"prop-{operator_id}",
        "operator_id": operator_id,
        "justification": "rosetta-org integration test",
    }


def test_psm_launch_attaches_owner_role_for_known_operator(tmp_path):
    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm)
    orch = _StubOrchestrator()
    ledger_path = tmp_path / "ledger.jsonl"
    app = _build_app(orch, _stable_monitor(), ledger_path, rm)

    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-cto"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["owner_role"] == "cto"
    assert body["owner_lookup"] == "ok"

    # Orchestrator received owner attribution in gap_analysis.
    assert len(orch.calls) == 1
    ga = orch.calls[0]
    assert ga["owner_role"] == "cto"
    assert ga["approver_chain"] == ["ceo"]
    assert ga["owner_lookup"] == "ok"

    # APPROVED + LAUNCHED ledger entries carry it forward.
    ledger = SelfEditLedger(ledger_path)
    entries = ledger.read_all()
    # Ledger entries' .kind may be enum or str depending on read path;
    # normalise so the test isn't coupled to that detail.
    def _kind(e):
        k = e.kind
        return k.value if hasattr(k, "value") else k
    kinds = [_kind(e) for e in entries]
    assert "APPROVED" in kinds and "LAUNCHED" in kinds
    for e in entries:
        if _kind(e) in ("APPROVED", "LAUNCHED"):
            assert e.payload.get("owner_role") == "cto"
            assert e.payload.get("owner_lookup") == "ok"


def test_psm_launch_unknown_operator_is_explicit_not_silent(tmp_path):
    rm = RosettaManager(persistence_dir=str(tmp_path / "ros"))
    seed_platform_org(rm)
    orch = _StubOrchestrator()
    app = _build_app(orch, _stable_monitor(), tmp_path / "led.jsonl", rm)

    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-ghost"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["owner_role"] is None
    assert body["owner_lookup"] == "unknown_operator"
    assert orch.calls[0]["owner_lookup"] == "unknown_operator"


def test_psm_launch_without_rosetta_callable_is_backward_compatible(tmp_path):
    """Omitting get_rosetta_manager keeps PSM-003 behavior unchanged."""
    orch = _StubOrchestrator()
    ledger_path = tmp_path / "led.jsonl"
    app = FastAPI()
    app.include_router(build_router(
        get_orchestrator=lambda: orch,
        get_lyapunov_source=lambda: _stable_monitor(),
        ledger_path=str(ledger_path),
        # NOTE: get_rosetta_manager omitted on purpose
    ))
    r = TestClient(app).post(
        "/api/platform/self-modification/launch",
        json=_good_body("op-anyone"),
        headers={OPERATOR_HEADER: TOKEN},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["owner_lookup"] == "rosetta_not_wired"
    assert body["owner_role"] is None
