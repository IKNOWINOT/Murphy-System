"""
Execution Orchestrator bridge module.
Provides ExecutionOrchestrator class for workflow execution with human approval support.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime


class ExecutionOrchestrator:
    """
    Orchestrates execution of task packets with safety enforcement
    and human approval support.
    """

    def __init__(self):
        self.executed_tasks = []
        self.pending_approvals = {}

    def execute(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task packet, routing to human approval if required."""
        task_name = packet.get("task", "unknown")
        requires_approval = packet.get("requires_human_approval", False)

        if requires_approval:
            request_id = f"apr_{uuid.uuid4().hex[:12]}"
            self.pending_approvals[request_id] = packet
            return {
                "accepted": True,
                "executed_automatically": False,
                "human_approval_required": True,
                "status": "pending_approval",
                "approval_request_id": request_id,
                "task": task_name,
            }

        self.executed_tasks.append(packet)
        return {
            "accepted": True,
            "executed_automatically": True,
            "human_approval_required": False,
            "status": "completed",
            "task": task_name,
        }

    def execute_after_approval(self, approval: Dict[str, Any]) -> Dict[str, Any]:
        """Continue execution after human approval is granted."""
        request_id = approval.get("approval_request_id", "")
        approved = approval.get("approved", False)

        packet = self.pending_approvals.pop(request_id, None)

        if not approved or packet is None:
            return {"executed": False, "reason": "not approved or unknown request"}

        self.executed_tasks.append(packet)
        return {
            "executed": True,
            "status": "completed",
            "task": packet.get("task", "unknown"),
            "approved_by": approval.get("approver", "unknown"),
        }

    def execute_packet(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a simple packet (used by simplified workflow tests)."""
        self.executed_tasks.append(packet)
        return {
            "success": True,
            "message": f"Executed: {packet.get('task_name', 'unknown')}",
            "status": "completed",
        }
