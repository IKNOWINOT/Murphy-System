"""
Tests for Layer 6 — OptimizationEngine and Proposal models.

Key invariant: proposals NEVER trigger execution directly.
"""

import pytest

from aionmind.models.proposals import (
    OptimizationProposal,
    ProposalCategory,
    ProposalStatus,
)
from aionmind.optimization_engine import OptimizationEngine


class TestProposalModel:

    def test_default_status_is_pending(self):
        p = OptimizationProposal(
            category=ProposalCategory.GATE_STRENGTHENING,
            title="test",
        )
        assert p.status == ProposalStatus.PENDING_REVIEW

    def test_approve(self):
        p = OptimizationProposal(
            category=ProposalCategory.GATE_STRENGTHENING,
            title="test",
        )
        p.approve("admin")
        assert p.status == ProposalStatus.APPROVED
        assert p.approved_by == "admin"
        assert p.approved_at is not None

    def test_reject(self):
        p = OptimizationProposal(
            category=ProposalCategory.PHASE_TUNING,
            title="test",
        )
        p.reject("not needed")
        assert p.status == ProposalStatus.REJECTED
        assert p.rejection_reason == "not needed"

    def test_mark_applied_requires_approval(self):
        """Cannot mark as applied without prior approval."""
        p = OptimizationProposal(
            category=ProposalCategory.BOTTLENECK_REPORT,
            title="test",
        )
        with pytest.raises(ValueError, match="not been approved"):
            p.mark_applied()

    def test_mark_applied_after_approval(self):
        p = OptimizationProposal(
            category=ProposalCategory.BOTTLENECK_REPORT,
            title="test",
        )
        p.approve("admin")
        p.mark_applied()
        assert p.status == ProposalStatus.APPLIED

    def test_proposal_has_no_execute_method(self):
        """Proposals are informational — they must not carry execution logic."""
        p = OptimizationProposal(
            category=ProposalCategory.GATE_STRENGTHENING,
            title="test",
        )
        assert not hasattr(p, "execute")
        assert not hasattr(p, "run")
        assert not hasattr(p, "apply")  # apply != mark_applied


class TestOptimizationEngine:

    def test_propose_gate_strengthening(self):
        engine = OptimizationEngine()
        p = engine.propose_gate_strengthening(
            gate_id="gate-1",
            evidence=["metric-1"],
            suggested_threshold=0.9,
        )
        assert p.category == ProposalCategory.GATE_STRENGTHENING
        assert p.status == ProposalStatus.PENDING_REVIEW
        assert engine.get_proposal(p.proposal_id) is p

    def test_propose_phase_tuning(self):
        engine = OptimizationEngine()
        p = engine.propose_phase_tuning(
            phase="deploy",
            evidence=["log-1"],
            suggested_adjustment={"delay": 10},
        )
        assert p.category == ProposalCategory.PHASE_TUNING

    def test_propose_assumption_invalidation(self):
        engine = OptimizationEngine()
        p = engine.propose_assumption_invalidation(
            assumption="no downtime during deploy",
            evidence=["incident-1"],
        )
        assert p.category == ProposalCategory.ASSUMPTION_INVALIDATION

    def test_generate_bottleneck_report(self):
        engine = OptimizationEngine()
        p = engine.generate_bottleneck_report(
            bottleneck_details={"step": "build", "avg_time": 120},
            evidence=["telemetry-1"],
        )
        assert p.category == ProposalCategory.BOTTLENECK_REPORT
        assert p.priority == "high"

    def test_approve_and_reject_proposals(self):
        engine = OptimizationEngine()
        p1 = engine.propose_gate_strengthening("g1", ["e1"], 0.8)
        p2 = engine.propose_gate_strengthening("g2", ["e2"], 0.7)

        assert engine.approve_proposal(p1.proposal_id, "admin") is True
        assert engine.reject_proposal(p2.proposal_id, "not needed") is True

        assert engine.get_proposal(p1.proposal_id).status == ProposalStatus.APPROVED
        assert engine.get_proposal(p2.proposal_id).status == ProposalStatus.REJECTED

    def test_mark_applied_requires_prior_approval(self):
        engine = OptimizationEngine()
        p = engine.propose_gate_strengthening("g1", ["e1"], 0.8)
        assert engine.mark_applied(p.proposal_id) is False  # not yet approved
        engine.approve_proposal(p.proposal_id, "admin")
        assert engine.mark_applied(p.proposal_id) is True

    def test_list_proposals_by_status(self):
        engine = OptimizationEngine()
        engine.propose_gate_strengthening("g1", [], 0.8)
        engine.propose_phase_tuning("phase-1", [], {})
        pending = engine.list_proposals(status=ProposalStatus.PENDING_REVIEW)
        assert len(pending) == 2
        all_props = engine.list_proposals()
        assert len(all_props) == 2

    def test_telemetry_never_executes(self):
        """Optimization engine has no method to directly execute / apply changes."""
        engine = OptimizationEngine()
        assert not hasattr(engine, "execute")
        assert not hasattr(engine, "apply")
        assert not hasattr(engine, "run_action")
