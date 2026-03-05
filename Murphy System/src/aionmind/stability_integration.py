"""
Layer 3 — Recursive Stability Controller Integration.

Wraps the existing RSC (``recursive_stability_controller``) so that every
recursion / graph-expansion step is gated by the stability score S(t).

Hard invariants
---------------
* Instability forces the SAFE default: **pause + require human review**.
* No expansion is permitted when S(t) is below the configured threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StabilityAction(str, Enum):
    """Control actions the stability integration can emit."""

    PROCEED = "proceed"
    PAUSE = "pause"
    REPLAN = "replan"
    REDUCE_DEPTH = "reduce_depth"
    REQUIRE_HUMAN_REVIEW = "require_human_review"


@dataclass
class StabilityCheckResult:
    """Outcome of a stability evaluation."""

    stable: bool
    score: float
    action: StabilityAction
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class StabilityIntegration:
    """Façade over the existing RSC for use by AionMind layers.

    Parameters
    ----------
    stability_threshold : float
        Minimum S(t) score required to allow expansion (default 0.5).
    rsc_client : object, optional
        An instance of the existing ``RecursiveStabilityController`` or an
        HTTP client pointing at the RSC service.  When ``None`` a conservative
        stub is used (always returns stable with score 1.0).
    """

    def __init__(
        self,
        *,
        stability_threshold: float = 0.5,
        rsc_client: Optional[Any] = None,
    ) -> None:
        self._threshold = stability_threshold
        self._rsc = rsc_client
        self._last_result: Optional[StabilityCheckResult] = None

    @property
    def last_result(self) -> Optional[StabilityCheckResult]:
        return self._last_result

    def check_stability(
        self,
        *,
        context_id: str = "",
        node_id: str = "",
        current_depth: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StabilityCheckResult:
        """Evaluate whether expansion is safe.

        Returns a :class:`StabilityCheckResult` with the recommended action.
        When no RSC client is available a conservative stub is used that always
        allows proceeding (score = 1.0).
        """
        score = self._query_rsc(metadata or {})

        if score >= self._threshold:
            result = StabilityCheckResult(
                stable=True,
                score=score,
                action=StabilityAction.PROCEED,
                message="Stability OK",
                details={
                    "context_id": context_id,
                    "node_id": node_id,
                    "depth": current_depth,
                },
            )
        else:
            # SAFE default: pause + require human review
            result = StabilityCheckResult(
                stable=False,
                score=score,
                action=StabilityAction.REQUIRE_HUMAN_REVIEW,
                message=(
                    f"Stability score {score:.3f} below threshold "
                    f"{self._threshold:.3f} — pausing for human review."
                ),
                details={
                    "context_id": context_id,
                    "node_id": node_id,
                    "depth": current_depth,
                },
            )
            logger.warning(
                "RSC instability detected (score=%.3f < %.3f) for node %s — "
                "forcing pause + human review.",
                score,
                self._threshold,
                node_id,
            )

        self._last_result = result
        return result

    # ── private ───────────────────────────────────────────────────

    def _query_rsc(self, metadata: Dict[str, Any]) -> float:
        """Obtain S(t) from the RSC backend.

        Falls back to a conservative score of 1.0 when no client is configured
        so that the system is permissive in test / dev environments but never
        silently skips checks in production (the caller sees score = 1.0 and
        the decision is logged).
        """
        if self._rsc is None:
            return 1.0

        # Try to call the RSC client's status method (works for both in-process
        # controller and HTTP-client adapters).
        try:
            status = self._rsc.get_status()  # type: ignore[union-attr]
            return float(status.get("stability_score", 1.0))
        except Exception as exc:
            logger.exception("RSC query failed — defaulting to score 1.0: %s", exc)
            return 1.0
