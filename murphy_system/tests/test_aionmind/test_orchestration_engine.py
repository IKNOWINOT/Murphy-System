"""
Tests for Layer 4 — OrchestrationEngine.

Validates HITL enforcement, RSC gating, audit trail, and the invariant that
unapproved graphs cannot be executed.
"""

import pytest

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.models.context_object import ContextObject, RiskLevel
from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeStatus,
    ExecutionNodeType,
)
from aionmind.orchestration_engine import (
    OrchestrationEngine,
    OrchestrationStatus,
)
from aionmind.reasoning_engine import ReasoningEngine
from aionmind.stability_integration import StabilityIntegration


# ── fixtures ──────────────────────────────────────────────────────

def _build_approved_graph(
    *,
    require_approval: bool = False,
    risk_level: RiskLevel = RiskLevel.LOW,
) -> ExecutionGraphObject:
    """Build a simple approved execution graph."""
    reg = CapabilityRegistry()
    reg.register(Capability(
        capability_id="cap-a", name="analyser", provider="bot-a", tags=["test"],
    ))
    engine = ReasoningEngine(reg)
    ctx = ContextObject(source="test", intent="test", risk_level=risk_level)
    candidates = engine.generate_candidates(ctx, max_candidates=1)
    graph = candidates[0]
    # Force approval flags if needed
    if require_approval:
        for n in graph.nodes:
            if n.node_type == ExecutionNodeType.CAPABILITY_CALL:
                n.requires_approval = True
    graph.approved = True
    graph.approved_by = "test-operator"
    return graph


def _noop_handler(node):
    return {"handled": True}


# ── tests ─────────────────────────────────────────────────────────

class TestOrchestrationEngine:

    def test_unapproved_graph_raises(self):
        """Executing an unapproved graph must raise ValueError."""
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        graph = ExecutionGraphObject(context_id="ctx-1", approved=False)
        with pytest.raises(ValueError, match="not been approved"):
            oe.execute(graph)

    def test_approved_graph_with_handler_completes(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph()
        state = oe.execute(graph)
        assert state.status == OrchestrationStatus.COMPLETED
        assert len(state.audit_trail) > 0

    def test_hitl_node_pauses_execution(self):
        """Nodes requiring approval must pause the execution."""
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph(require_approval=True)
        state = oe.execute(graph)
        assert state.status == OrchestrationStatus.AWAITING_APPROVAL
        assert len(state.pending_approvals) > 0

    def test_rsc_instability_pauses_execution(self):
        """RSC instability must pause execution for human review."""

        class UnstableRSC:
            def get_status(self):
                return {"stability_score": 0.1}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=UnstableRSC())
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph()
        state = oe.execute(graph)
        # RSC check nodes appear before capability nodes — first one will pause
        assert state.status == OrchestrationStatus.PAUSED
        # Verify audit trail records the instability event
        rsc_events = [
            e for e in state.audit_trail if e.event == "rsc_instability_pause"
        ]
        assert len(rsc_events) > 0

    def test_missing_handler_fails_gracefully(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        # No handler registered for cap-a
        graph = _build_approved_graph()
        state = oe.execute(graph)
        assert state.status == OrchestrationStatus.FAILED
        failed_events = [
            e for e in state.audit_trail if e.event == "node_failed"
        ]
        assert len(failed_events) > 0

    def test_audit_trail_records_all_events(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph()
        state = oe.execute(graph)
        events = [e.event for e in state.audit_trail]
        assert "execution_started" in events
        assert "execution_completed" in events

    def test_cancel_execution(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph(require_approval=True)
        state = oe.execute(graph)
        assert oe.cancel(state.execution_id) is True
        assert oe.get_state(state.execution_id).status == OrchestrationStatus.CANCELLED

    def test_approve_node(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        oe.register_handler("cap-a", _noop_handler)
        graph = _build_approved_graph(require_approval=True)
        state = oe.execute(graph)
        pending = list(state.pending_approvals.keys())
        assert len(pending) > 0
        ok = oe.approve_node(state.execution_id, pending[0], "human-1")
        assert ok is True
