"""
Tests for the AionMindKernel runtime façade.
"""

import pytest

from aionmind.capability_registry import Capability
from aionmind.models.context_object import ContextObject
from aionmind.models.execution_graph import ExecutionGraphObject
from aionmind.models.proposals import ProposalStatus
from aionmind.orchestration_engine import OrchestrationStatus
from aionmind.runtime_kernel import AionMindKernel


def _setup_kernel() -> AionMindKernel:
    kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
    kernel.register_capability(
        Capability(
            capability_id="cap-a",
            name="analyser",
            provider="bot-a",
            tags=["analysis"],
        )
    )
    kernel.register_capability(
        Capability(
            capability_id="cap-b",
            name="generator",
            provider="bot-b",
            tags=["generation"],
        )
    )
    kernel.register_handler("cap-a", lambda node: {"ok": True})
    kernel.register_handler("cap-b", lambda node: {"ok": True})
    return kernel


class TestAionMindKernel:

    def test_build_context(self):
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="user", raw_input="hello")
        assert isinstance(ctx, ContextObject)
        assert ctx.source == "user"
        # Context should be stored in STM
        stm = kernel.memory.retrieve_context(f"ctx:{ctx.context_id}")
        assert stm is not None

    def test_plan_generates_candidates(self):
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="test", intent="analysis generation")
        candidates = kernel.plan(ctx, max_candidates=3)
        assert len(candidates) >= 1
        for g in candidates:
            assert isinstance(g, ExecutionGraphObject)
            assert g.approved is False

    def test_select_returns_best(self):
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="test", intent="analysis")
        candidates = kernel.plan(ctx)
        best = kernel.select(candidates, ctx)
        assert best is not None
        assert best.score > 0

    def test_execute_unapproved_raises(self):
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="test", intent="analysis")
        candidates = kernel.plan(ctx)
        best = kernel.select(candidates, ctx)
        with pytest.raises(ValueError, match="not been approved"):
            kernel.execute(best)

    def test_full_workflow(self):
        """End-to-end: build context → plan → select → approve → execute."""
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="user", intent="analysis")
        candidates = kernel.plan(ctx, max_candidates=3)
        best = kernel.select(candidates, ctx)
        # Human approves
        best.approved = True
        best.approved_by = "operator"
        state = kernel.execute(best)
        # Execution completes or awaits approval (depending on node flags)
        assert state.status in (
            OrchestrationStatus.COMPLETED,
            OrchestrationStatus.AWAITING_APPROVAL,
        )

    def test_archive_execution(self):
        kernel = _setup_kernel()
        ctx = kernel.build_context(source="test", intent="analysis")
        candidates = kernel.plan(ctx, max_candidates=1)
        graph = candidates[0]
        graph.approved = True
        graph.approved_by = "op"
        state = kernel.execute(graph)
        kernel.archive_execution(state.execution_id)
        # Should now be in LTM, not STM
        assert kernel.memory.retrieve_context(f"exec:{state.execution_id}") is None
        assert kernel.memory.retrieve_archived(f"exec:{state.execution_id}") is not None

    def test_status_summary(self):
        kernel = _setup_kernel()
        status = kernel.status()
        assert "capabilities_registered" in status
        assert "memory" in status
        assert "pending_proposals" in status
        assert status["capabilities_registered"] == 2

    def test_proposal_workflow(self):
        kernel = _setup_kernel()
        p = kernel.optimization.propose_gate_strengthening("g1", ["e1"], 0.9)
        assert len(kernel.list_proposals(status=ProposalStatus.PENDING_REVIEW)) == 1
        kernel.approve_proposal(p.proposal_id, "admin")
        assert kernel.optimization.get_proposal(p.proposal_id).status == ProposalStatus.APPROVED
