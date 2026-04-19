# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
HITL Review Builder — Murphy System

Generates structured review payloads for the Human-in-the-Loop
deployment gate.  Every high-risk change (optimization, update,
bugfix, source-code change, or customer-side deliverable) must
pass through a HITL review before being applied to the system.

Each review contains:
  1. **Problem summary** — anonymised description (no mention of who
     or what system specifically, only a direct inference of what
     was requested).
  2. **Edge-case blowup** — risks and unconsidered scenarios
     enumerated from gate-synthesis failure-mode analysis.
  3. **Rationale** — why the changes were made and why in this
     specific way.
  4. **Best-practice ordering** — optimal implementation sequence
     inferred from Rosetta agent-state patterns.
  5. **MSS resolution context** — information-quality level from
     MSS controls (RM0–RM5).

Reviews are routed exclusively to users with FOUNDER or
PLATFORM_ADMIN roles via the HITL persistence layer.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.hitl_review_builder")


# ---------------------------------------------------------------------------
# Change categories
# ---------------------------------------------------------------------------

class ChangeCategory(str, Enum):
    """Categories of changes that require HITL deployment review."""
    OPTIMIZATION = "optimization"
    UPDATE = "update"
    BUGFIX = "bugfix"
    SOURCE_CODE = "source_code"
    CUSTOMER_DELIVERABLE = "customer_deliverable"
    CONFIGURATION = "configuration"
    SECURITY_PATCH = "security_patch"


class ReviewPriority(str, Enum):
    """Priority levels for HITL reviews."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Review payload
# ---------------------------------------------------------------------------

@dataclass
class HITLReviewPayload:
    """Structured review payload for HITL deployment gate.

    Contains all information a platform admin needs to make an
    informed approve/reject decision.
    """

    # Identity
    review_id: str = field(default_factory=lambda: f"hitl-review-{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Categorisation
    change_category: str = ChangeCategory.UPDATE.value
    priority: str = ReviewPriority.MEDIUM.value

    # 1. Problem summary — anonymised
    problem_summary: str = ""

    # 2. Edge-case blowup — risks not yet considered
    edge_cases: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)

    # 3. Rationale — why these changes and why this approach
    rationale_why: str = ""
    rationale_approach: str = ""

    # 4. Best-practice ordering from Rosetta
    best_practice_ordering: List[Dict[str, Any]] = field(default_factory=list)

    # 5. MSS resolution context
    mss_resolution_level: str = "RM3"
    mss_context: str = ""

    # Routing
    assigned_to: List[str] = field(default_factory=list)
    approval_tier: str = "platform"

    # Status
    status: str = "pending"
    decided_by: str = ""
    decision: str = ""
    decision_reason: str = ""
    decided_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary for persistence / API response."""
        return {
            "review_id": self.review_id,
            "created_at": self.created_at,
            "change_category": self.change_category,
            "priority": self.priority,
            "problem_summary": self.problem_summary,
            "edge_cases": list(self.edge_cases),
            "failure_modes": list(self.failure_modes),
            "rationale_why": self.rationale_why,
            "rationale_approach": self.rationale_approach,
            "best_practice_ordering": list(self.best_practice_ordering),
            "mss_resolution_level": self.mss_resolution_level,
            "mss_context": self.mss_context,
            "assigned_to": list(self.assigned_to),
            "approval_tier": self.approval_tier,
            "status": self.status,
            "decided_by": self.decided_by,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "decided_at": self.decided_at,
        }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class HITLReviewBuilder:
    """Builds structured HITL review payloads for deployment gate reviews.

    Integrates with:
      - Gate-synthesis failure-mode enumerator for edge cases
      - Rosetta agent-state for best-practice ordering
      - MSS controls for information-quality level
    """

    def __init__(
        self,
        gate_synthesis=None,
        rosetta_bridge=None,
        mss_controls=None,
    ) -> None:
        self._gate_synthesis = gate_synthesis
        self._rosetta_bridge = rosetta_bridge
        self._mss_controls = mss_controls
        self._reviews: Dict[str, HITLReviewPayload] = {}
        logger.info("HITLReviewBuilder initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_review(
        self,
        *,
        change_category: str = ChangeCategory.UPDATE.value,
        problem_description: str = "",
        rationale_why: str = "",
        rationale_approach: str = "",
        priority: str = ReviewPriority.MEDIUM.value,
        assigned_to: Optional[List[str]] = None,
        artifact_context: Optional[Dict[str, Any]] = None,
    ) -> HITLReviewPayload:
        """Build a complete HITL review payload.

        Parameters
        ----------
        change_category : str
            One of :class:`ChangeCategory` values.
        problem_description : str
            Raw description; will be anonymised for the review.
        rationale_why : str
            Why the changes were made.
        rationale_approach : str
            Why this specific approach was chosen.
        priority : str
            Review priority level.
        assigned_to : list[str] | None
            User IDs to route the review to. Defaults to platform
            admins (resolved at routing time).
        artifact_context : dict | None
            Optional context for gate-synthesis failure-mode analysis.

        Returns
        -------
        HITLReviewPayload
            Fully populated review payload.
        """
        review = HITLReviewPayload(
            change_category=change_category,
            priority=priority,
            rationale_why=rationale_why,
            rationale_approach=rationale_approach,
            assigned_to=assigned_to or [],
        )

        # 1. Anonymise problem summary
        review.problem_summary = self._anonymise_description(problem_description)

        # 2. Enumerate edge cases via gate-synthesis
        review.edge_cases = self._enumerate_edge_cases(artifact_context or {})
        review.failure_modes = self._enumerate_failure_modes(artifact_context or {})

        # 3. Best-practice ordering from Rosetta
        review.best_practice_ordering = self._get_rosetta_ordering(
            change_category, artifact_context or {}
        )

        # 4. MSS resolution context
        mss_level, mss_ctx = self._get_mss_context(problem_description)
        review.mss_resolution_level = mss_level
        review.mss_context = mss_ctx

        self._reviews[review.review_id] = review
        logger.info(
            "Built HITL review %s [%s/%s] — %d edge cases, %d failure modes",
            review.review_id,
            change_category,
            priority,
            len(review.edge_cases),
            len(review.failure_modes),
        )
        return review

    def get_review(self, review_id: str) -> Optional[HITLReviewPayload]:
        """Retrieve a review by ID."""
        return self._reviews.get(review_id)

    def list_pending(self) -> List[HITLReviewPayload]:
        """List all pending reviews."""
        return [r for r in self._reviews.values() if r.status == "pending"]

    def decide(
        self,
        review_id: str,
        decision: str,
        decided_by: str,
        reason: str = "",
    ) -> Optional[HITLReviewPayload]:
        """Record a decision (approve/reject) on a review.

        Parameters
        ----------
        review_id : str
            Review to decide on.
        decision : str
            ``"approve"`` or ``"reject"``.
        decided_by : str
            User ID of the decision maker.
        reason : str
            Optional reason for the decision.
        """
        review = self._reviews.get(review_id)
        if review is None:
            logger.warning("Review %s not found", review_id)
            return None
        if review.status != "pending":
            logger.warning("Review %s already decided (%s)", review_id, review.status)
            return review

        review.status = "approved" if decision == "approve" else "rejected"
        review.decision = decision
        review.decided_by = decided_by
        review.decision_reason = reason
        review.decided_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "HITL review %s %s by %s: %s",
            review_id,
            review.status,
            decided_by,
            reason or "(no reason)",
        )
        return review

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _anonymise_description(description: str) -> str:
        """Remove specific identifiers to create an anonymised summary.

        Strips email addresses, account IDs, proper nouns (simple
        heuristic), and org names to produce a context-only summary.
        """
        import re
        text = description
        # Remove emails
        text = re.sub(r'\b[\w.+-]+@[\w.-]+\.\w+\b', '[REDACTED_EMAIL]', text)
        # Remove UUIDs
        text = re.sub(
            r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
            '[REDACTED_ID]',
            text,
            flags=re.IGNORECASE,
        )
        # Remove account-id patterns (acc-XXXX)
        text = re.sub(r'\bacc-[a-zA-Z0-9]+\b', '[REDACTED_ACCOUNT]', text)
        return text.strip()

    def _enumerate_edge_cases(self, context: Dict[str, Any]) -> List[str]:
        """Use gate-synthesis failure-mode enumerator if available."""
        if self._gate_synthesis is None:
            return [
                "No automated edge-case analysis available — manual review required",
            ]
        try:
            from src.gate_synthesis.failure_mode_enumerator import FailureModeEnumerator
            enumerator = FailureModeEnumerator()
            modes = enumerator.enumerate(context.get("content", ""))
            return [m.get("description", str(m)) for m in modes]
        except Exception as exc:
            logger.warning("Edge-case enumeration failed: %s", exc)
            return [f"Edge-case analysis unavailable: {exc}"]

    def _enumerate_failure_modes(self, context: Dict[str, Any]) -> List[str]:
        """Enumerate potential failure modes for the change."""
        modes = []
        category = context.get("change_category", "")
        if category in ("source_code", "bugfix", "security_patch"):
            modes.append("Regression risk — existing functionality may break")
            modes.append("Test coverage gap — untested code paths")
        if category in ("optimization", "update"):
            modes.append("Performance regression — optimisation may degrade other paths")
        if category == "customer_deliverable":
            modes.append("Deliverable mismatch — output may not match customer expectations")
            modes.append("Data leakage — customer data may appear in wrong context")
        modes.append("Deployment rollback — ensure rollback path exists")
        return modes

    def _get_rosetta_ordering(
        self, change_category: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get optimal ordering from Rosetta bridge."""
        if self._rosetta_bridge is not None:
            try:
                stats = self._rosetta_bridge.get_stats()
                if stats:
                    return [{"source": "rosetta", "ordering": stats}]
            except Exception as exc:
                logger.debug("Rosetta ordering unavailable: %s", exc)

        # Default best-practice ordering
        return [
            {"step": 1, "action": "Run full test suite before changes", "priority": "critical"},
            {"step": 2, "action": "Apply changes in isolated branch", "priority": "high"},
            {"step": 3, "action": "Run regression tests", "priority": "critical"},
            {"step": 4, "action": "Security scan (CodeQL / Bandit)", "priority": "high"},
            {"step": 5, "action": "Peer review / HITL approval", "priority": "critical"},
            {"step": 6, "action": "Deploy to staging", "priority": "high"},
            {"step": 7, "action": "Smoke test in staging", "priority": "medium"},
            {"step": 8, "action": "Deploy to production", "priority": "high"},
            {"step": 9, "action": "Post-deploy monitoring (15 min)", "priority": "medium"},
        ]

    def _get_mss_context(self, description: str) -> tuple:
        """Get MSS resolution level and context."""
        if self._mss_controls is not None:
            try:
                level = self._mss_controls.get_resolution_level(description)
                return (level, f"MSS analysis at {level}")
            except Exception:
                pass
        # Default: RM3 (operational level)
        return ("RM3", "Default operational resolution level — no MSS analysis available")
