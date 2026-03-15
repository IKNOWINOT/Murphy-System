"""
Layer 6 — Proposal models: optimisation outputs that are **recommendations only**.

Hard invariant: proposals NEVER trigger execution directly.  They must be
reviewed, approved, and then applied through a supervised pathway.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProposalStatus(str, Enum):
    """Lifecycle of a proposal."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"


class ProposalCategory(str, Enum):
    """What the proposal aims to improve."""

    GATE_STRENGTHENING = "gate_strengthening"
    PHASE_TUNING = "phase_tuning"
    ASSUMPTION_INVALIDATION = "assumption_invalidation"
    BOTTLENECK_REPORT = "bottleneck_report"
    WORKFLOW_TEMPLATE = "workflow_template"
    CONFIDENCE_CALIBRATION = "confidence_calibration"


class OptimizationProposal(BaseModel):
    """A recommendation produced by the Optimization & Feedback layer.

    Invariants
    ----------
    * ``status`` starts as DRAFT or PENDING_REVIEW — never APPLIED.
    * Transition to APPLIED requires ``approved_by`` to be set.
    * The proposal itself carries **no execution authority**.
    """

    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: ProposalCategory
    title: str
    description: str = ""
    source_evidence: List[str] = Field(
        default_factory=list,
        description="References to telemetry / workflow data that motivated this.",
    )
    suggested_action: Dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable action payload (applied only after approval).",
    )
    priority: str = "medium"
    status: ProposalStatus = ProposalStatus.PENDING_REVIEW
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def approve(self, approver: str) -> None:
        """Mark the proposal as approved.  Does NOT execute anything."""
        self.status = ProposalStatus.APPROVED
        self.approved_by = approver
        self.approved_at = datetime.now(timezone.utc)

    def reject(self, reason: str) -> None:
        self.status = ProposalStatus.REJECTED
        self.rejection_reason = reason

    def mark_applied(self) -> None:
        """Only callable after approval."""
        if self.status != ProposalStatus.APPROVED:
            raise ValueError(
                "Cannot apply a proposal that has not been approved."
            )
        self.status = ProposalStatus.APPLIED
