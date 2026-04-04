"""Tests for org_chart_enforcement module."""

import sys
import os
import threading

import pytest

# Ensure the src package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.org_chart_enforcement import (
    EscalationLevel,
    OrgNode,
    EscalationRequest,
    CrossDeptWorkflow,
    OrgChartEnforcement,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def enforcer() -> OrgChartEnforcement:
    """Return a fresh OrgChartEnforcement instance."""
    return OrgChartEnforcement()


@pytest.fixture
def populated(enforcer: OrgChartEnforcement) -> OrgChartEnforcement:
    """Build a small org chart for testing.

    Hierarchy (engineering):
        ceo (C_LEVEL)
          └── vp_eng (VP)
                └── head_eng (DEPARTMENT_HEAD)
                      └── lead_eng (TEAM_LEAD)

    Hierarchy (marketing):
        ceo (C_LEVEL)
          └── head_mkt (DEPARTMENT_HEAD)
                └── lead_mkt (TEAM_LEAD)
    """
    enforcer.add_node("ceo", "CEO", "executive",
                       permissions=["approve_budget", "hire", "fire", "deploy"],
                       escalation_level=EscalationLevel.C_LEVEL)
    enforcer.add_node("vp_eng", "VP Engineering", "engineering",
                       reports_to="ceo",
                       permissions=["deploy", "review_code"],
                       escalation_level=EscalationLevel.VP)
    enforcer.add_node("head_eng", "Head of Engineering", "engineering",
                       reports_to="vp_eng",
                       permissions=["review_code", "merge"],
                       escalation_level=EscalationLevel.DEPARTMENT_HEAD)
    enforcer.add_node("lead_eng", "Team Lead", "engineering",
                       reports_to="head_eng",
                       permissions=["write_code"],
                       escalation_level=EscalationLevel.TEAM_LEAD)
    enforcer.add_node("head_mkt", "Head of Marketing", "marketing",
                       reports_to="ceo",
                       permissions=["publish", "approve_campaign"],
                       escalation_level=EscalationLevel.DEPARTMENT_HEAD)
    enforcer.add_node("lead_mkt", "Team Lead Marketing", "marketing",
                       reports_to="head_mkt",
                       permissions=["draft_campaign"],
                       escalation_level=EscalationLevel.TEAM_LEAD)
    return enforcer


# ------------------------------------------------------------------
# Adding nodes and building hierarchy
# ------------------------------------------------------------------

class TestAddNode:
    def test_add_node_returns_org_node(self, enforcer: OrgChartEnforcement) -> None:
        node = enforcer.add_node("n1", "Dev", "engineering")
        assert isinstance(node, OrgNode)
        assert node.node_id == "n1"
        assert node.role == "Dev"
        assert node.department == "engineering"
        assert node.reports_to is None
        assert node.permissions == []
        assert node.escalation_level == EscalationLevel.TEAM_LEAD

    def test_add_node_with_all_fields(self, enforcer: OrgChartEnforcement) -> None:
        node = enforcer.add_node(
            "n2", "Manager", "sales",
            reports_to="n1",
            permissions=["sell", "discount"],
            escalation_level=EscalationLevel.DEPARTMENT_HEAD,
        )
        assert node.reports_to == "n1"
        assert node.permissions == ["sell", "discount"]
        assert node.escalation_level == EscalationLevel.DEPARTMENT_HEAD

    def test_nodes_appear_in_status(self, populated: OrgChartEnforcement) -> None:
        status = populated.get_status()
        assert status["total_nodes"] == 6


# ------------------------------------------------------------------
# Permission checking
# ------------------------------------------------------------------

class TestPermission:
    def test_direct_permission_allowed(self, populated: OrgChartEnforcement) -> None:
        allowed, reason = populated.check_permission("lead_eng", "write_code")
        assert allowed is True
        assert "direct permission" in reason

    def test_permission_denied(self, populated: OrgChartEnforcement) -> None:
        allowed, reason = populated.check_permission("lead_eng", "publish")
        assert allowed is False
        assert "denied" in reason

    def test_inherited_permission(self, populated: OrgChartEnforcement) -> None:
        # lead_eng doesn't have 'deploy' but vp_eng (ancestor) does
        allowed, reason = populated.check_permission("lead_eng", "deploy")
        assert allowed is True
        assert "inherited" in reason
        assert "vp_eng" in reason

    def test_unknown_node(self, populated: OrgChartEnforcement) -> None:
        allowed, reason = populated.check_permission("ghost", "anything")
        assert allowed is False
        assert "not found" in reason

    def test_root_node_direct(self, populated: OrgChartEnforcement) -> None:
        allowed, _ = populated.check_permission("ceo", "approve_budget")
        assert allowed is True

    def test_root_node_denied(self, populated: OrgChartEnforcement) -> None:
        allowed, _ = populated.check_permission("ceo", "nonexistent_action")
        assert allowed is False


# ------------------------------------------------------------------
# Escalation chain
# ------------------------------------------------------------------

class TestEscalationChain:
    def test_chain_from_leaf(self, populated: OrgChartEnforcement) -> None:
        chain = populated.get_escalation_chain("lead_eng")
        ids = [n.node_id for n in chain]
        assert ids == ["lead_eng", "head_eng", "vp_eng", "ceo"]

    def test_chain_from_root(self, populated: OrgChartEnforcement) -> None:
        chain = populated.get_escalation_chain("ceo")
        assert len(chain) == 1
        assert chain[0].node_id == "ceo"

    def test_chain_unknown_node(self, populated: OrgChartEnforcement) -> None:
        chain = populated.get_escalation_chain("ghost")
        assert chain == []


# ------------------------------------------------------------------
# Escalation request creation and resolution
# ------------------------------------------------------------------

class TestEscalationRequest:
    def test_create_request(self, populated: OrgChartEnforcement) -> None:
        req = populated.escalate("lead_eng", EscalationLevel.VP, "need deploy access")
        assert isinstance(req, EscalationRequest)
        assert req.originator_id == "lead_eng"
        assert req.target_level == EscalationLevel.VP
        assert req.status == "pending"
        assert req.resolved_by is None

    def test_resolve_by_sufficient_level(self, populated: OrgChartEnforcement) -> None:
        req = populated.escalate("lead_eng", EscalationLevel.VP, "deploy")
        ok = populated.resolve_escalation(req.request_id, "vp_eng")
        assert ok is True
        assert req.status == "resolved"
        assert req.resolved_by == "vp_eng"

    def test_resolve_by_higher_level(self, populated: OrgChartEnforcement) -> None:
        req = populated.escalate("lead_eng", EscalationLevel.VP, "deploy")
        ok = populated.resolve_escalation(req.request_id, "ceo")
        assert ok is True

    def test_resolve_by_insufficient_level(self, populated: OrgChartEnforcement) -> None:
        req = populated.escalate("lead_eng", EscalationLevel.VP, "deploy")
        ok = populated.resolve_escalation(req.request_id, "head_eng")
        assert ok is False
        assert req.status == "pending"

    def test_resolve_unknown_request(self, populated: OrgChartEnforcement) -> None:
        ok = populated.resolve_escalation("no_such_id", "ceo")
        assert ok is False

    def test_resolve_unknown_resolver(self, populated: OrgChartEnforcement) -> None:
        req = populated.escalate("lead_eng", EscalationLevel.VP, "deploy")
        ok = populated.resolve_escalation(req.request_id, "ghost")
        assert ok is False


# ------------------------------------------------------------------
# Cross-department workflow
# ------------------------------------------------------------------

class TestCrossDeptWorkflow:
    def test_initiate_workflow(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow(
            "lead_eng", ["engineering", "marketing"], "joint launch",
        )
        assert isinstance(wf, CrossDeptWorkflow)
        assert wf.status == "pending"
        assert set(wf.departments) == {"engineering", "marketing"}
        assert all(v is False for v in wf.approvals.values())

    def test_approve_single_department(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow(
            "lead_eng", ["engineering", "marketing"],
        )
        ok, msg = populated.approve_cross_dept(wf.workflow_id, "head_eng")
        assert ok is True
        assert "pending" in msg
        assert wf.status == "pending"

    def test_approve_all_departments(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow(
            "lead_eng", ["engineering", "marketing"],
        )
        populated.approve_cross_dept(wf.workflow_id, "head_eng")
        ok, msg = populated.approve_cross_dept(wf.workflow_id, "head_mkt")
        assert ok is True
        assert "fully approved" in msg
        assert wf.status == "approved"

    def test_approve_insufficient_level(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow(
            "lead_eng", ["engineering", "marketing"],
        )
        ok, msg = populated.approve_cross_dept(wf.workflow_id, "lead_eng")
        assert ok is False
        assert "insufficient" in msg

    def test_approve_wrong_department(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow(
            "lead_eng", ["engineering"],
        )
        ok, msg = populated.approve_cross_dept(wf.workflow_id, "head_mkt")
        assert ok is False
        assert "not part of workflow" in msg

    def test_approve_unknown_workflow(self, populated: OrgChartEnforcement) -> None:
        ok, msg = populated.approve_cross_dept("no_such_wf", "head_eng")
        assert ok is False
        assert "not found" in msg

    def test_approve_unknown_approver(self, populated: OrgChartEnforcement) -> None:
        wf = populated.initiate_cross_dept_workflow("lead_eng", ["engineering"])
        ok, msg = populated.approve_cross_dept(wf.workflow_id, "ghost")
        assert ok is False
        assert "not found" in msg


# ------------------------------------------------------------------
# Department scope isolation
# ------------------------------------------------------------------

class TestDepartmentScope:
    def test_returns_department(self, populated: OrgChartEnforcement) -> None:
        assert populated.get_department_scope("lead_eng") == "engineering"
        assert populated.get_department_scope("head_mkt") == "marketing"

    def test_unknown_node_returns_none(self, populated: OrgChartEnforcement) -> None:
        assert populated.get_department_scope("ghost") is None

    def test_departments_are_isolated(self, populated: OrgChartEnforcement) -> None:
        eng_scope = populated.get_department_scope("lead_eng")
        mkt_scope = populated.get_department_scope("lead_mkt")
        assert eng_scope != mkt_scope


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatus:
    def test_status_keys(self, populated: OrgChartEnforcement) -> None:
        status = populated.get_status()
        expected_keys = {
            "total_nodes", "departments", "total_escalations",
            "pending_escalations", "total_workflows",
            "pending_workflows", "total_audit_entries",
        }
        assert expected_keys.issubset(status.keys())

    def test_status_counts_escalations(self, populated: OrgChartEnforcement) -> None:
        populated.escalate("lead_eng", EscalationLevel.VP, "test")
        status = populated.get_status()
        assert status["total_escalations"] == 1
        assert status["pending_escalations"] == 1

    def test_status_counts_workflows(self, populated: OrgChartEnforcement) -> None:
        populated.initiate_cross_dept_workflow("lead_eng", ["engineering", "marketing"])
        status = populated.get_status()
        assert status["total_workflows"] == 1
        assert status["pending_workflows"] == 1

    def test_status_departments_sorted(self, populated: OrgChartEnforcement) -> None:
        depts = populated.get_status()["departments"]
        assert depts == sorted(depts)


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_add_nodes(self, enforcer: OrgChartEnforcement) -> None:
        errors: list = []

        def _add(idx: int) -> None:
            try:
                enforcer.add_node(f"node_{idx}", "role", "dept")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_add, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert enforcer.get_status()["total_nodes"] == 50

    def test_concurrent_permission_checks(self, populated: OrgChartEnforcement) -> None:
        results: list = []

        def _check() -> None:
            ok, _ = populated.check_permission("lead_eng", "write_code")
            results.append(ok)

        threads = [threading.Thread(target=_check) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
        assert len(results) == 50

    def test_concurrent_escalations(self, populated: OrgChartEnforcement) -> None:
        requests: list = []

        def _escalate(idx: int) -> None:
            req = populated.escalate(
                "lead_eng", EscalationLevel.VP, f"reason_{idx}",
            )
            requests.append(req)

        threads = [threading.Thread(target=_escalate, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(requests) == 30
        assert populated.get_status()["total_escalations"] == 30
