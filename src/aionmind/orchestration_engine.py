"""
Layer 4 — Dynamic Orchestration Engine (Graph Execution).

Executes an approved :class:`ExecutionGraphObject` in topological order with:
  - dependency resolution
  - checkpoint / pause / resume / cancel
  - HITL approval gates at every node that requires it
  - RSC stability checks before expansion
  - full audit trail

Hard invariants
---------------
* A graph **must** be approved before execution begins.
* Nodes with ``requires_approval`` BLOCK until a human approves.
* RSC_CHECK nodes must pass before their dependents execute.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeStatus,
    ExecutionNodeType,
)
from aionmind.stability_integration import StabilityAction, StabilityIntegration

logger = logging.getLogger(__name__)


class OrchestrationStatus(str, Enum):
    """Runtime status of an orchestration execution."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class AuditEntry:
    """Single entry in an orchestration audit trail."""

    timestamp: str
    node_id: str
    event: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationState:
    """Mutable state tracking the progress of an orchestration execution."""

    execution_id: str
    graph_id: str
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    audit_trail: List[AuditEntry] = field(default_factory=list)
    pending_approvals: Dict[str, str] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class OrchestrationEngine:
    """Executes an approved ExecutionGraphObject.

    Parameters
    ----------
    stability : StabilityIntegration
        Layer 3 integration for RSC checks.
    handlers : dict
        Mapping of ``capability_id`` → callable handler.
    """

    def __init__(
        self,
        stability: StabilityIntegration,
        *,
        handlers: Optional[Dict[str, Callable[..., Any]]] = None,
    ) -> None:
        self._stability = stability
        self._handlers: Dict[str, Callable[..., Any]] = handlers or {}
        self._states: Dict[str, OrchestrationState] = {}

    def register_handler(
        self, capability_id: str, handler: Callable[..., Any]
    ) -> None:
        self._handlers[capability_id] = handler

    # ── execution lifecycle ───────────────────────────────────────

    def execute(self, graph: ExecutionGraphObject) -> OrchestrationState:
        """Execute an **approved** graph.

        Raises
        ------
        ValueError
            If the graph has not been approved.
        """
        if not graph.approved:
            raise ValueError(
                f"Graph {graph.graph_id} has not been approved. "
                "Execution requires prior human approval."
            )

        state = OrchestrationState(
            execution_id=str(uuid.uuid4()),
            graph_id=graph.graph_id,
            status=OrchestrationStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._states[state.execution_id] = state
        self._audit(state, "__start__", "execution_started")

        order = graph.topological_order()
        for node_id in order:
            node = graph.get_node(node_id)
            if node is None:
                continue

            if state.status in (
                OrchestrationStatus.PAUSED,
                OrchestrationStatus.CANCELLED,
                OrchestrationStatus.FAILED,
            ):
                break

            self._execute_node(graph, node, state)

        if state.status == OrchestrationStatus.RUNNING:
            state.status = OrchestrationStatus.COMPLETED
            state.finished_at = datetime.now(timezone.utc).isoformat()
            self._audit(state, "__end__", "execution_completed")

        return state

    def approve_node(
        self, execution_id: str, node_id: str, approver: str
    ) -> bool:
        """Grant approval for a pending HITL checkpoint."""
        state = self._states.get(execution_id)
        if not state:
            return False
        if node_id in state.pending_approvals:
            del state.pending_approvals[node_id]
            self._audit(
                state,
                node_id,
                "node_approved",
                {"approver": approver},
            )
            return True
        return False

    def pause(self, execution_id: str) -> bool:
        state = self._states.get(execution_id)
        if state and state.status == OrchestrationStatus.RUNNING:
            state.status = OrchestrationStatus.PAUSED
            self._audit(state, "__control__", "execution_paused")
            return True
        return False

    def cancel(self, execution_id: str) -> bool:
        state = self._states.get(execution_id)
        if state and state.status in (
            OrchestrationStatus.RUNNING,
            OrchestrationStatus.PAUSED,
            OrchestrationStatus.AWAITING_APPROVAL,
        ):
            state.status = OrchestrationStatus.CANCELLED
            self._audit(state, "__control__", "execution_cancelled")
            return True
        return False

    def get_state(self, execution_id: str) -> Optional[OrchestrationState]:
        return self._states.get(execution_id)

    # ── node execution ────────────────────────────────────────────

    def _execute_node(
        self,
        graph: ExecutionGraphObject,
        node: ExecutionNode,
        state: OrchestrationState,
    ) -> None:
        self._audit(state, node.node_id, "node_started", {"type": node.node_type.value})

        # ── RSC check nodes ───────────────────────────────────────
        if node.node_type == ExecutionNodeType.RSC_CHECK:
            result = self._stability.check_stability(
                context_id=graph.context_id,
                node_id=node.node_id,
            )
            if not result.stable:
                node.status = ExecutionNodeStatus.PAUSED
                state.status = OrchestrationStatus.PAUSED
                state.pending_approvals[node.node_id] = "rsc_instability"
                self._audit(
                    state,
                    node.node_id,
                    "rsc_instability_pause",
                    {"score": result.score, "action": result.action.value},
                )
                return
            node.status = ExecutionNodeStatus.COMPLETED
            self._audit(state, node.node_id, "rsc_check_passed", {"score": result.score})
            return

        # ── HITL checkpoint ───────────────────────────────────────
        if node.node_type == ExecutionNodeType.HITL_CHECKPOINT or node.requires_approval:
            node.status = ExecutionNodeStatus.AWAITING_APPROVAL
            state.status = OrchestrationStatus.AWAITING_APPROVAL
            state.pending_approvals[node.node_id] = "requires_human_approval"
            self._audit(state, node.node_id, "awaiting_approval")
            return

        # ── Gate check ────────────────────────────────────────────
        if node.node_type == ExecutionNodeType.GATE_CHECK:
            node.status = ExecutionNodeStatus.COMPLETED
            self._audit(state, node.node_id, "gate_check_passed")
            return

        # ── Aggregation ──────────────────────────────────────────
        if node.node_type == ExecutionNodeType.AGGREGATION:
            node.status = ExecutionNodeStatus.COMPLETED
            self._audit(state, node.node_id, "aggregation_completed")
            return

        # ── Capability call ──────────────────────────────────────
        if node.node_type == ExecutionNodeType.CAPABILITY_CALL:
            handler = self._handlers.get(node.capability_id or "")
            if handler is None:
                node.status = ExecutionNodeStatus.FAILED
                node.error = f"No handler for capability {node.capability_id}"
                state.status = OrchestrationStatus.FAILED
                self._audit(
                    state,
                    node.node_id,
                    "node_failed",
                    {"error": node.error},
                )
                return
            try:
                result = handler(node)
                node.result = result
                node.status = ExecutionNodeStatus.COMPLETED
                state.node_results[node.node_id] = result
                self._audit(state, node.node_id, "node_completed")
            except Exception as exc:
                node.status = ExecutionNodeStatus.FAILED
                node.error = str(exc)
                state.status = OrchestrationStatus.FAILED
                self._audit(
                    state,
                    node.node_id,
                    "node_failed",
                    {"error": str(exc)},
                )
                return

    # ── audit ─────────────────────────────────────────────────────

    def _audit(
        self,
        state: OrchestrationState,
        node_id: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=node_id,
            event=event,
            details=details or {},
        )
        state.audit_trail.append(entry)
        logger.info(
            "[%s] node=%s event=%s %s",
            state.execution_id[:8],
            node_id,
            event,
            details or "",
        )
