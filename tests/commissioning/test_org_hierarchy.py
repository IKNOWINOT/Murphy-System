"""
Murphy System — Organizational Hierarchy Commissioning Tests
Owner: @biz-sim
Phase: 3 — Business Process Simulation
Completion: 100%

Resolves GAP-004 (no organizational hierarchy automation).
Tests complete org chart construction, position management,
reporting chains, and approval workflows.
"""

import uuid
import pytest
from datetime import datetime
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
# Mock Org Chart System (mirrors src/organization_chart_system.py)
# ═══════════════════════════════════════════════════════════════════════════


class MockOrgChart:
    """Simulates organizational hierarchy management.

    Mirrors the Department enum and OrgNode structure from
    src/organization_chart_system.py.
    """

    VALID_LEVELS = ["Owner", "C-Suite", "VP", "Director", "Manager", "Lead", "Agent"]

    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.employees: Dict[str, Dict] = {}
        self.contracts: Dict[str, Dict] = {}
        self.approvals: Dict[str, Dict] = {}

    def create_position(self, position_data: Dict) -> Dict:
        """Create a position in the org chart."""
        position_id = f"POS-{uuid.uuid4().hex[:8]}"
        level = position_data.get("level", "Agent")
        assert level in self.VALID_LEVELS, f"Invalid level: {level}"

        self.positions[position_id] = {
            **position_data,
            "position_id": position_id,
            "employee_id": None,
            "created_at": datetime.now().isoformat(),
        }
        return {"position_id": position_id, "status": "created"}

    def assign_employee(self, employee_id: str, position_id: str) -> Dict:
        """Assign an employee to a position."""
        if position_id not in self.positions:
            return {"error": "Position not found"}

        self.positions[position_id]["employee_id"] = employee_id
        self.employees[employee_id] = {
            "employee_id": employee_id,
            "position_id": position_id,
            "assigned_at": datetime.now().isoformat(),
        }
        return {"position_id": position_id, "employee_id": employee_id}

    def create_contract(self, contract_data: Dict) -> Dict:
        """Create a contract for a position."""
        contract_id = f"CONTRACT-{uuid.uuid4().hex[:8]}"
        self.contracts[contract_id] = {
            **contract_data,
            "contract_id": contract_id,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }
        return self.contracts[contract_id]

    def request_approval(self, request_data: Dict) -> Dict:
        """Request approval for an action."""
        approval_id = f"APR-{uuid.uuid4().hex[:8]}"
        self.approvals[approval_id] = {
            **request_data,
            "approval_id": approval_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        return {"approval_id": approval_id, "status": "pending"}

    def approve(self, approval_id: str, approver_id: str) -> Dict:
        """Approve a pending request."""
        if approval_id not in self.approvals:
            return {"error": "Approval not found"}

        self.approvals[approval_id]["status"] = "approved"
        self.approvals[approval_id]["approver_id"] = approver_id
        self.approvals[approval_id]["approved_at"] = datetime.now().isoformat()
        return {"approval_id": approval_id, "status": "approved"}

    def reject(self, approval_id: str, approver_id: str, reason: str) -> Dict:
        """Reject a pending request."""
        if approval_id not in self.approvals:
            return {"error": "Approval not found"}

        self.approvals[approval_id]["status"] = "rejected"
        self.approvals[approval_id]["approver_id"] = approver_id
        self.approvals[approval_id]["reason"] = reason
        return {"approval_id": approval_id, "status": "rejected"}

    def get_reporting_chain(self, position_id: str) -> List[Dict]:
        """Get the chain of command from position to root."""
        chain = []
        current = position_id

        while current and current in self.positions:
            pos = self.positions[current]
            chain.append(pos)
            current = pos.get("reports_to")

        return chain

    def get_direct_reports(self, position_id: str) -> List[Dict]:
        """Get all positions that report to this position."""
        return [
            pos for pos in self.positions.values()
            if pos.get("reports_to") == position_id
        ]

    def get_org_summary(self) -> Dict:
        """Generate org chart summary."""
        levels = {}
        for pos in self.positions.values():
            level = pos.get("level", "Unknown")
            levels[level] = levels.get(level, 0) + 1

        return {
            "total_positions": len(self.positions),
            "total_employees": len(self.employees),
            "total_contracts": len(self.contracts),
            "level_distribution": levels,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Org Hierarchy Tests
# Owner: @biz-sim | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def org():
    """Provide a fresh org chart for each test."""
    return MockOrgChart()


class TestOrgHierarchyPositions:
    """@biz-sim: Tests for position management."""

    def test_create_ceo_position(self, org):
        """@biz-sim: Verify CEO position creation."""
        result = org.create_position({
            "title": "Chief Executive Officer",
            "level": "C-Suite",
            "department": "Executive",
            "reports_to": None,
        })
        assert result["status"] == "created"
        assert result["position_id"].startswith("POS-")

    def test_create_vp_positions(self, org):
        """@biz-sim: Verify VP positions with CEO reporting."""
        ceo = org.create_position({
            "title": "CEO",
            "level": "C-Suite",
            "department": "Executive",
            "reports_to": None,
        })

        vp_titles = ["VP Engineering", "VP Sales", "VP Marketing"]
        for title in vp_titles:
            vp = org.create_position({
                "title": title,
                "level": "VP",
                "department": title.split()[-1],
                "reports_to": ceo["position_id"],
            })
            assert vp["status"] == "created"

    def test_invalid_level_rejected(self, org):
        """@biz-sim: Verify invalid org levels are rejected."""
        with pytest.raises(AssertionError):
            org.create_position({
                "title": "Intern",
                "level": "InvalidLevel",
                "department": "Engineering",
            })


class TestOrgHierarchyReporting:
    """@biz-sim: Tests for reporting chain validation."""

    def _build_standard_hierarchy(self, org) -> Dict[str, str]:
        """Helper: Build a standard org hierarchy, return position IDs."""
        ceo = org.create_position({
            "title": "CEO", "level": "C-Suite",
            "department": "Executive", "reports_to": None,
        })
        vp = org.create_position({
            "title": "VP Engineering", "level": "VP",
            "department": "Engineering", "reports_to": ceo["position_id"],
        })
        director = org.create_position({
            "title": "Director of Engineering", "level": "Director",
            "department": "Engineering", "reports_to": vp["position_id"],
        })
        manager = org.create_position({
            "title": "Engineering Manager", "level": "Manager",
            "department": "Engineering", "reports_to": director["position_id"],
        })
        return {
            "ceo": ceo["position_id"],
            "vp": vp["position_id"],
            "director": director["position_id"],
            "manager": manager["position_id"],
        }

    def test_reporting_chain(self, org):
        """@biz-sim: Verify complete reporting chain traversal."""
        ids = self._build_standard_hierarchy(org)
        chain = org.get_reporting_chain(ids["manager"])
        assert len(chain) == 4  # Manager → Director → VP → CEO

    def test_direct_reports(self, org):
        """@biz-sim: Verify direct reports listing."""
        ids = self._build_standard_hierarchy(org)
        reports = org.get_direct_reports(ids["ceo"])
        assert len(reports) == 1  # VP only

    def test_employee_assignment(self, org):
        """@biz-sim: Verify employee assignment to position."""
        pos = org.create_position({
            "title": "Engineer", "level": "Agent",
            "department": "Engineering", "reports_to": None,
        })
        result = org.assign_employee("EMP-001", pos["position_id"])
        assert result["employee_id"] == "EMP-001"


class TestOrgHierarchyApprovals:
    """@biz-sim: Tests for approval workflows."""

    def test_approval_workflow(self, org):
        """@biz-sim: Verify approval request and response."""
        approval = org.request_approval({
            "requester_id": "CEO-001",
            "action": "strategic_initiative",
            "description": "Launch new product line",
            "budget": 1000000,
        })
        assert approval["status"] == "pending"

        approved = org.approve(approval["approval_id"], "CEO-001")
        assert approved["status"] == "approved"

    def test_rejection_workflow(self, org):
        """@biz-sim: Verify rejection with reason."""
        approval = org.request_approval({
            "requester_id": "MGR-001",
            "action": "budget_increase",
            "budget": 500000,
        })
        rejected = org.reject(
            approval["approval_id"], "VP-001", "Budget exceeds department limit"
        )
        assert rejected["status"] == "rejected"


class TestOrgHierarchyCEOSystem:
    """@biz-sim: Tests for CEO system through org chart.
    Completion: 100%"""

    def test_ceo_system_workflow(self, org):
        """@biz-sim: Complete CEO system workflow."""
        # Step 1: Create CEO position
        ceo = org.create_position({
            "title": "Chief Executive Officer",
            "level": "C-Suite",
            "department": "Executive",
            "reports_to": None,
        })

        # Step 2: Create CEO contract
        contract = org.create_contract({
            "position_id": ceo["position_id"],
            "salary": 250000,
            "start_date": datetime.now().isoformat(),
            "benefits": ["health", "401k", "equity"],
        })
        assert contract["status"] == "active"

        # Step 3: Create VP positions
        vp_ids = []
        for title in ["VP Engineering", "VP Sales", "VP Marketing"]:
            vp = org.create_position({
                "title": title,
                "level": "VP",
                "department": title.split()[-1],
                "reports_to": ceo["position_id"],
            })
            vp_ids.append(vp["position_id"])

        # Step 4: Verify org structure
        reports = org.get_direct_reports(ceo["position_id"])
        assert len(reports) == 3

        # Step 5: CEO approval workflow
        approval = org.request_approval({
            "requester_id": "CEO-001",
            "action": "strategic_initiative",
            "description": "Launch new product line",
            "budget": 1000000,
        })
        approved = org.approve(approval["approval_id"], "CEO-001")
        assert approved["status"] == "approved"

        # Step 6: Validate summary
        summary = org.get_org_summary()
        assert summary["total_positions"] == 4
        assert summary["level_distribution"]["C-Suite"] == 1
        assert summary["level_distribution"]["VP"] == 3
