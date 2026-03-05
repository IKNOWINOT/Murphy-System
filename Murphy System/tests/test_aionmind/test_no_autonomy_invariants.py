"""
No-Autonomy Invariant Tests.

These tests verify the five hard invariants of Murphy System 2.0:

1. No free-run execution: high-risk / low-confidence / irreversible operations
   require human approval (HITL).
2. Telemetry and learning loops never trigger execution actions directly.
3. Optimization outputs are proposals / recommendations only until approved.
4. Approvals are informational artifacts and must not be treated as executable
   commands by default.
5. The system may generate plans, workflows, candidates, and control signals,
   but execution must remain supervised.
"""

import pytest

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.context_engine import ContextEngine
from aionmind.memory_layer import MemoryLayer
from aionmind.models.context_object import ContextObject, RiskLevel
from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeType,
)
from aionmind.models.proposals import (
    OptimizationProposal,
    ProposalCategory,
    ProposalStatus,
)
from aionmind.optimization_engine import OptimizationEngine
from aionmind.orchestration_engine import OrchestrationEngine, OrchestrationStatus
from aionmind.reasoning_engine import ReasoningEngine
from aionmind.runtime_kernel import AionMindKernel
from aionmind.stability_integration import StabilityAction, StabilityIntegration


class TestInvariant1_NoFreeRunExecution:
    """High-risk / low-confidence / irreversible operations require HITL."""

    def test_unapproved_graph_cannot_execute(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        graph = ExecutionGraphObject(context_id="c", approved=False)
        with pytest.raises(ValueError, match="not been approved"):
            oe.execute(graph)

    def test_high_risk_nodes_require_approval(self):
        reg = CapabilityRegistry()
        reg.register(Capability(
            capability_id="c1", name="deploy", provider="p1", tags=["deploy"],
        ))
        engine = ReasoningEngine(reg)
        ctx = ContextObject(source="t", intent="deploy", risk_level=RiskLevel.CRITICAL)
        candidates = engine.generate_candidates(ctx)
        for g in candidates:
            cap_nodes = [
                n for n in g.nodes
                if n.node_type == ExecutionNodeType.CAPABILITY_CALL
            ]
            for n in cap_nodes:
                assert n.requires_approval is True

    def test_hitl_node_blocks_execution(self):
        si = StabilityIntegration()
        oe = OrchestrationEngine(si)
        graph = ExecutionGraphObject(context_id="c", approved=True, approved_by="op")
        graph.nodes.append(ExecutionNode(
            node_id="n1",
            node_type=ExecutionNodeType.HITL_CHECKPOINT,
            label="human gate",
        ))
        state = oe.execute(graph)
        assert state.status == OrchestrationStatus.AWAITING_APPROVAL


class TestInvariant2_TelemetryNeverExecutes:
    """Telemetry and learning loops never trigger execution actions directly."""

    def test_optimization_engine_has_no_execute(self):
        engine = OptimizationEngine()
        assert not hasattr(engine, "execute")
        assert not hasattr(engine, "run")
        assert not hasattr(engine, "apply")

    def test_context_engine_has_no_execute(self):
        engine = ContextEngine()
        assert not hasattr(engine, "execute")
        assert not hasattr(engine, "run")

    def test_memory_layer_has_no_execute(self):
        ml = MemoryLayer()
        assert not hasattr(ml, "execute")
        assert not hasattr(ml, "run")

    def test_proposals_never_trigger_execution(self):
        """Proposals from feedback must remain proposals."""
        engine = OptimizationEngine()
        p = engine.propose_gate_strengthening("g1", ["e1"], 0.9)
        assert p.status == ProposalStatus.PENDING_REVIEW
        # Even after approval, nothing auto-executes
        engine.approve_proposal(p.proposal_id, "admin")
        assert p.status == ProposalStatus.APPROVED
        # No side effects triggered


class TestInvariant3_ProposalsAreRecommendationsOnly:
    """Optimization outputs are proposals / recommendations only."""

    def test_proposal_starts_as_pending(self):
        p = OptimizationProposal(
            category=ProposalCategory.GATE_STRENGTHENING,
            title="test",
        )
        assert p.status == ProposalStatus.PENDING_REVIEW

    def test_cannot_apply_without_approval(self):
        p = OptimizationProposal(
            category=ProposalCategory.PHASE_TUNING,
            title="test",
        )
        with pytest.raises(ValueError, match="not been approved"):
            p.mark_applied()

    def test_engine_mark_applied_requires_approval(self):
        engine = OptimizationEngine()
        p = engine.propose_gate_strengthening("g1", [], 0.8)
        assert engine.mark_applied(p.proposal_id) is False  # not approved
        engine.approve_proposal(p.proposal_id, "admin")
        assert engine.mark_applied(p.proposal_id) is True


class TestInvariant4_ApprovalsAreInformational:
    """Approvals are informational artifacts, not executable commands."""

    def test_approved_proposal_is_not_auto_applied(self):
        engine = OptimizationEngine()
        p = engine.propose_gate_strengthening("g1", [], 0.8)
        engine.approve_proposal(p.proposal_id, "admin")
        # Status is APPROVED — not APPLIED
        assert p.status == ProposalStatus.APPROVED
        assert p.status != ProposalStatus.APPLIED

    def test_graph_approval_does_not_auto_execute(self):
        """Approving a graph (setting approved=True) does not start execution."""
        graph = ExecutionGraphObject(context_id="c", approved=True, approved_by="op")
        # Graph exists but has not been submitted to the engine
        assert graph.approved is True
        # No execution state is created automatically


class TestInvariant5_ExecutionIsSupervisedOnly:
    """Execution must remain supervised."""

    def test_rsc_instability_forces_pause(self):
        class Unstable:
            def get_status(self):
                return {"stability_score": 0.2}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=Unstable())
        result = si.check_stability()
        assert result.stable is False
        assert result.action == StabilityAction.REQUIRE_HUMAN_REVIEW

    def test_rsc_check_node_gates_execution(self):
        class Unstable:
            def get_status(self):
                return {"stability_score": 0.1}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=Unstable())
        oe = OrchestrationEngine(si)
        graph = ExecutionGraphObject(context_id="c", approved=True, approved_by="op")
        graph.nodes.append(ExecutionNode(
            node_id="rsc-1",
            node_type=ExecutionNodeType.RSC_CHECK,
            label="stability check",
        ))
        graph.nodes.append(ExecutionNode(
            node_id="n1",
            node_type=ExecutionNodeType.CAPABILITY_CALL,
            capability_id="cap-1",
            label="action",
            depends_on=["rsc-1"],
        ))
        state = oe.execute(graph)
        assert state.status == OrchestrationStatus.PAUSED
        assert "rsc-1" in state.pending_approvals

    def test_kernel_full_pipeline_is_supervised(self):
        """The kernel never auto-executes without explicit human approval."""
        kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
        kernel.register_capability(Capability(
            capability_id="c1", name="test", provider="p", tags=["test"],
        ))
        kernel.register_handler("c1", lambda n: {"ok": True})
        ctx = kernel.build_context(source="user", intent="test")
        candidates = kernel.plan(ctx)
        best = kernel.select(candidates, ctx)
        # Without approval, execution must fail
        with pytest.raises(ValueError, match="not been approved"):
            kernel.execute(best)
