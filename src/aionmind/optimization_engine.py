"""
Layer 6 — Optimization & Feedback (Conservative Learning).

Integrates corrections, telemetry, workflow performance, and gate outcomes to
produce :class:`OptimizationProposal` objects.

Hard invariant: **No direct execution from feedback.  Ever.**

All outputs are proposals that require human approval before they can affect
system behaviour.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aionmind.models.proposals import (
    OptimizationProposal,
    ProposalCategory,
    ProposalStatus,
)

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """Generates improvement proposals from operational data.

    This engine **never** modifies gates, schedules, or system behaviour
    directly.  It only produces :class:`OptimizationProposal` artifacts that
    must be reviewed and approved by a human operator.
    """

    def __init__(self) -> None:
        self._proposals: Dict[str, OptimizationProposal] = {}

    # ── proposal generation ───────────────────────────────────────

    def propose_gate_strengthening(
        self,
        gate_id: str,
        evidence: List[str],
        suggested_threshold: float,
        *,
        description: str = "",
    ) -> OptimizationProposal:
        """Suggest tightening a safety gate threshold."""
        proposal = OptimizationProposal(
            category=ProposalCategory.GATE_STRENGTHENING,
            title=f"Strengthen gate {gate_id}",
            description=description
            or f"Evidence suggests gate {gate_id} threshold should increase to {suggested_threshold}.",
            source_evidence=evidence,
            suggested_action={
                "gate_id": gate_id,
                "new_threshold": suggested_threshold,
            },
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info("Generated proposal %s: %s", proposal.proposal_id, proposal.title)
        return proposal

    def propose_phase_tuning(
        self,
        phase: str,
        evidence: List[str],
        suggested_adjustment: Dict[str, Any],
        *,
        description: str = "",
    ) -> OptimizationProposal:
        """Suggest adjusting phase scheduling parameters."""
        proposal = OptimizationProposal(
            category=ProposalCategory.PHASE_TUNING,
            title=f"Tune phase '{phase}'",
            description=description or f"Adjustments suggested for phase '{phase}'.",
            source_evidence=evidence,
            suggested_action={"phase": phase, **suggested_adjustment},
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info("Generated proposal %s: %s", proposal.proposal_id, proposal.title)
        return proposal

    def propose_assumption_invalidation(
        self,
        assumption: str,
        evidence: List[str],
        *,
        description: str = "",
    ) -> OptimizationProposal:
        """Flag an assumption that evidence suggests is no longer valid."""
        proposal = OptimizationProposal(
            category=ProposalCategory.ASSUMPTION_INVALIDATION,
            title=f"Invalidate assumption: {assumption[:80]}",
            description=description or f"Evidence contradicts assumption: {assumption}",
            source_evidence=evidence,
            suggested_action={"assumption": assumption, "action": "invalidate"},
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info("Generated proposal %s: %s", proposal.proposal_id, proposal.title)
        return proposal

    def generate_bottleneck_report(
        self,
        bottleneck_details: Dict[str, Any],
        evidence: List[str],
        *,
        description: str = "",
    ) -> OptimizationProposal:
        """Report a detected bottleneck in workflow execution."""
        proposal = OptimizationProposal(
            category=ProposalCategory.BOTTLENECK_REPORT,
            title="Bottleneck report",
            description=description or "Bottleneck detected in workflow execution.",
            source_evidence=evidence,
            suggested_action=bottleneck_details,
            priority="high",
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info("Generated proposal %s: %s", proposal.proposal_id, proposal.title)
        return proposal

    # ── proposal lifecycle ────────────────────────────────────────

    def approve_proposal(self, proposal_id: str, approver: str) -> bool:
        """Mark a proposal as approved.  Does NOT apply it."""
        proposal = self._proposals.get(proposal_id)
        if proposal and proposal.status == ProposalStatus.PENDING_REVIEW:
            proposal.approve(approver)
            logger.info("Proposal %s approved by %s", proposal_id, approver)
            return True
        return False

    def reject_proposal(self, proposal_id: str, reason: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal and proposal.status == ProposalStatus.PENDING_REVIEW:
            proposal.reject(reason)
            logger.info("Proposal %s rejected: %s", proposal_id, reason)
            return True
        return False

    def mark_applied(self, proposal_id: str) -> bool:
        """Mark a previously-approved proposal as applied."""
        proposal = self._proposals.get(proposal_id)
        if proposal and proposal.status == ProposalStatus.APPROVED:
            proposal.mark_applied()
            logger.info("Proposal %s marked as applied", proposal_id)
            return True
        return False

    def get_proposal(self, proposal_id: str) -> Optional[OptimizationProposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self, *, status: Optional[ProposalStatus] = None
    ) -> List[OptimizationProposal]:
        if status is None:
            return list(self._proposals.values())
        return [p for p in self._proposals.values() if p.status == status]
