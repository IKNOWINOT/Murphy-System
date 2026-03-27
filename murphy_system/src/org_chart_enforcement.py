"""
Org-Chart Execution Enforcement for Murphy System

This module implements organizational-hierarchy enforcement providing:
- Organizational hierarchy with reporting lines
- Role-bound permission checks
- Department-scoped memory isolation
- Escalation chains matching reporting lines
- Arbitration controls for cross-department workflows
- Immutable audit trail for every enforcement decision
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class EscalationLevel(int, Enum):
    """Ordered escalation levels within the organizational hierarchy."""
    TEAM_LEAD = 1
    DEPARTMENT_HEAD = 2
    VP = 3
    C_LEVEL = 4
    BOARD = 5


@dataclass
class OrgNode:
    """A single node in the organizational chart."""
    node_id: str
    role: str
    department: str
    reports_to: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    escalation_level: EscalationLevel = EscalationLevel.TEAM_LEAD


@dataclass
class EscalationRequest:
    """A request to escalate an action up the reporting chain."""
    request_id: str
    originator_id: str
    target_level: EscalationLevel
    reason: str
    status: str = "pending"
    resolved_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CrossDeptWorkflow:
    """A workflow that spans multiple departments and requires approvals."""
    workflow_id: str
    departments: List[str] = field(default_factory=list)
    initiator_id: str = ""
    status: str = "pending"
    approvals: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrgChartEnforcement:
    """Deterministic org-chart enforcement layer for the Murphy System.

    Maintains an organizational hierarchy and enforces role-bound
    permissions, department-scoped memory isolation, escalation chains,
    and cross-department workflow arbitration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, OrgNode] = {}
        self._escalation_requests: Dict[str, EscalationRequest] = {}
        self._cross_dept_workflows: Dict[str, CrossDeptWorkflow] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        role: str,
        department: str,
        reports_to: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        escalation_level: EscalationLevel = EscalationLevel.TEAM_LEAD,
    ) -> OrgNode:
        """Add a node to the organizational chart and return it."""
        node = OrgNode(
            node_id=node_id,
            role=role,
            department=department,
            reports_to=reports_to,
            permissions=permissions if permissions is not None else [],
            escalation_level=escalation_level,
        )
        with self._lock:
            self._nodes[node_id] = node
            self._emit_audit("add_node", node_id=node_id, detail=f"role={role} dept={department}")
        logger.info("Added org node %s (role=%s, dept=%s)", node_id, role, department)
        return node

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def check_permission(self, node_id: str, action: str) -> Tuple[bool, str]:
        """Check whether *node_id* is allowed to perform *action*.

        Returns (allowed, reason).  If the action is not in the node's
        own permissions the escalation chain is walked and the first
        ancestor whose permissions contain the action grants access.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                reason = f"node '{node_id}' not found in org chart"
                self._emit_audit("check_permission", node_id=node_id, detail=reason)
                return False, reason

            # Direct permission
            if action in node.permissions:
                reason = f"action '{action}' allowed by direct permission"
                self._emit_audit("check_permission", node_id=node_id, detail=reason)
                return True, reason

            # Walk the escalation chain
            current = node
            while current.reports_to is not None:
                parent = self._nodes.get(current.reports_to)
                if parent is None:
                    break
                if action in parent.permissions:
                    reason = (
                        f"action '{action}' allowed via escalation chain "
                        f"(inherited from '{parent.node_id}')"
                    )
                    self._emit_audit("check_permission", node_id=node_id, detail=reason)
                    return True, reason
                current = parent

            reason = f"action '{action}' denied; not in permissions or escalation chain"
            self._emit_audit("check_permission", node_id=node_id, detail=reason)
            return False, reason

    # ------------------------------------------------------------------
    # Escalation chain
    # ------------------------------------------------------------------

    def get_escalation_chain(self, node_id: str) -> List[OrgNode]:
        """Return the chain from *node_id* up to the top of the hierarchy."""
        with self._lock:
            chain: List[OrgNode] = []
            current = self._nodes.get(node_id)
            while current is not None:
                chain.append(current)
                if current.reports_to is None:
                    break
                current = self._nodes.get(current.reports_to)
            return chain

    # ------------------------------------------------------------------
    # Escalation requests
    # ------------------------------------------------------------------

    def escalate(
        self,
        originator_id: str,
        target_level: EscalationLevel,
        reason: str,
    ) -> EscalationRequest:
        """Create an escalation request targeting *target_level*."""
        request = EscalationRequest(
            request_id=uuid.uuid4().hex[:12],
            originator_id=originator_id,
            target_level=target_level,
            reason=reason,
        )
        with self._lock:
            self._escalation_requests[request.request_id] = request
            self._emit_audit(
                "escalate",
                node_id=originator_id,
                detail=f"target_level={target_level.name} reason={reason}",
            )
        logger.info(
            "Escalation %s created by %s targeting %s",
            request.request_id, originator_id, target_level.name,
        )
        return request

    def resolve_escalation(self, request_id: str, resolver_id: str) -> bool:
        """Resolve an escalation request.

        The resolver must exist in the org chart and have an escalation
        level at least as high as the request's target level.  Returns
        True on success.
        """
        with self._lock:
            request = self._escalation_requests.get(request_id)
            if request is None:
                self._emit_audit(
                    "resolve_escalation",
                    node_id=resolver_id,
                    detail=f"request '{request_id}' not found",
                )
                return False

            resolver = self._nodes.get(resolver_id)
            if resolver is None:
                self._emit_audit(
                    "resolve_escalation",
                    node_id=resolver_id,
                    detail=f"resolver '{resolver_id}' not found in org chart",
                )
                return False

            if resolver.escalation_level.value < request.target_level.value:
                self._emit_audit(
                    "resolve_escalation",
                    node_id=resolver_id,
                    detail=(
                        f"resolver level {resolver.escalation_level.name} "
                        f"insufficient for target {request.target_level.name}"
                    ),
                )
                return False

            request.status = "resolved"
            request.resolved_by = resolver_id
            self._emit_audit(
                "resolve_escalation",
                node_id=resolver_id,
                detail=f"request '{request_id}' resolved",
            )
        logger.info("Escalation %s resolved by %s", request_id, resolver_id)
        return True

    # ------------------------------------------------------------------
    # Cross-department workflows
    # ------------------------------------------------------------------

    def initiate_cross_dept_workflow(
        self,
        initiator_id: str,
        departments: List[str],
        reason: str = "",
    ) -> CrossDeptWorkflow:
        """Start a cross-department workflow requiring approval from each department."""
        workflow = CrossDeptWorkflow(
            workflow_id=uuid.uuid4().hex[:12],
            departments=list(departments),
            initiator_id=initiator_id,
            approvals={dept: False for dept in departments},
        )
        with self._lock:
            self._cross_dept_workflows[workflow.workflow_id] = workflow
            self._emit_audit(
                "initiate_cross_dept_workflow",
                node_id=initiator_id,
                detail=f"departments={departments} reason={reason}",
            )
        logger.info(
            "Cross-dept workflow %s initiated by %s for %s",
            workflow.workflow_id, initiator_id, departments,
        )
        return workflow

    def approve_cross_dept(
        self,
        workflow_id: str,
        approver_id: str,
    ) -> Tuple[bool, str]:
        """Approve a cross-department workflow on behalf of the approver's department.

        The approver must be at least DEPARTMENT_HEAD level.
        Returns (success, status_msg).
        """
        with self._lock:
            workflow = self._cross_dept_workflows.get(workflow_id)
            if workflow is None:
                msg = f"workflow '{workflow_id}' not found"
                self._emit_audit("approve_cross_dept", node_id=approver_id, detail=msg)
                return False, msg

            approver = self._nodes.get(approver_id)
            if approver is None:
                msg = f"approver '{approver_id}' not found in org chart"
                self._emit_audit("approve_cross_dept", node_id=approver_id, detail=msg)
                return False, msg

            if approver.escalation_level.value < EscalationLevel.DEPARTMENT_HEAD.value:
                msg = (
                    f"approver '{approver_id}' has insufficient level "
                    f"({approver.escalation_level.name}); "
                    f"DEPARTMENT_HEAD or above required"
                )
                self._emit_audit("approve_cross_dept", node_id=approver_id, detail=msg)
                return False, msg

            dept = approver.department
            if dept not in workflow.approvals:
                msg = f"department '{dept}' is not part of workflow '{workflow_id}'"
                self._emit_audit("approve_cross_dept", node_id=approver_id, detail=msg)
                return False, msg

            workflow.approvals[dept] = True

            if all(workflow.approvals.values()):
                workflow.status = "approved"
                msg = f"workflow '{workflow_id}' fully approved"
            else:
                pending = [d for d, v in workflow.approvals.items() if not v]
                msg = f"workflow '{workflow_id}' approval recorded; pending: {pending}"

            self._emit_audit("approve_cross_dept", node_id=approver_id, detail=msg)
        logger.info("Cross-dept approval: %s", msg)
        return True, msg

    # ------------------------------------------------------------------
    # Department-scoped memory isolation
    # ------------------------------------------------------------------

    def get_department_scope(self, node_id: str) -> Optional[str]:
        """Return the department that *node_id* belongs to.

        Used to enforce department-scoped memory isolation – callers
        should restrict data access to items tagged with the returned
        department identifier.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return None
            return node.department

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall org-chart enforcement status."""
        with self._lock:
            total_nodes = len(self._nodes)
            total_escalations = len(self._escalation_requests)
            pending_escalations = sum(
                1 for r in self._escalation_requests.values() if r.status == "pending"
            )
            total_workflows = len(self._cross_dept_workflows)
            pending_workflows = sum(
                1 for w in self._cross_dept_workflows.values() if w.status == "pending"
            )
            departments = sorted({n.department for n in self._nodes.values()})
            total_audit_entries = len(self._audit_log)

        return {
            "total_nodes": total_nodes,
            "departments": departments,
            "total_escalations": total_escalations,
            "pending_escalations": pending_escalations,
            "total_workflows": total_workflows,
            "pending_workflows": pending_workflows,
            "total_audit_entries": total_audit_entries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_audit(self, event: str, node_id: str = "", detail: str = "") -> None:
        """Append an audit entry. Must be called under lock."""
        capped_append(self._audit_log, {
            "event": event,
            "node_id": node_id,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
