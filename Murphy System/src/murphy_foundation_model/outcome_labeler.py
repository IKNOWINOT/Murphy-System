# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Outcome Labeler
===============

Scores every :class:`ActionTrace` on five quality dimensions and assigns
an overall label category (*positive*, *partial*, or *negative*).  The
resulting :class:`OutcomeLabels` are consumed by the training-data
pipeline to weight and stratify training examples.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .action_trace_serializer import ActionTrace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OutcomeLabels:
    """Quality labels assigned to a single action trace."""

    success: bool
    efficiency: float           # 0.0 – 1.0
    safety_score: float         # 0.0 – 1.0
    confidence_calibration: float  # 0.0 – 1.0
    human_agreement: float      # 0.0 – 1.0
    overall_quality: float      # weighted average
    label_category: str         # "positive" | "partial" | "negative"


# ---------------------------------------------------------------------------
# Labeler
# ---------------------------------------------------------------------------

class OutcomeLabeler:
    """Labels action traces with quality scores.

    Parameters
    ----------
    efficiency_baseline:
        Mapping from *action_type* → expected execution time (ms).
        Used to compute relative efficiency.  Types without a baseline
        are assumed perfectly efficient.
    safety_keywords:
        Words whose presence in ``outcome_details`` triggers a safety
        penalty.
    """

    DEFAULT_SAFETY_KEYWORDS = frozenset({
        "safety_violation",
        "gate_blocked",
        "override_required",
        "escalation",
        "rollback",
    })

    def __init__(
        self,
        efficiency_baseline: Optional[Dict[str, float]] = None,
        safety_keywords: Optional[frozenset] = None,
    ) -> None:
        self.efficiency_baseline: Dict[str, float] = efficiency_baseline or {}
        self.safety_keywords: frozenset = (
            safety_keywords or self.DEFAULT_SAFETY_KEYWORDS
        )

    # -- public API ---------------------------------------------------------

    def label_trace(self, trace: ActionTrace) -> OutcomeLabels:
        """Compute quality labels for *trace*."""
        success = trace.outcome_success
        efficiency = self._compute_efficiency(trace)
        safety_score = self._compute_safety_score(trace)
        confidence_calibration = self._compute_confidence_calibration(trace)
        human_agreement = self._compute_human_agreement(trace)

        # Determine label category
        if success and not trace.human_correction:
            label_category = "positive"
        elif success and trace.human_correction:
            label_category = "partial"
        else:
            label_category = "negative"

        overall = (
            0.30 * float(success)
            + 0.20 * efficiency
            + 0.20 * safety_score
            + 0.15 * confidence_calibration
            + 0.15 * human_agreement
        )

        return OutcomeLabels(
            success=success,
            efficiency=efficiency,
            safety_score=safety_score,
            confidence_calibration=confidence_calibration,
            human_agreement=human_agreement,
            overall_quality=round(overall, 4),
            label_category=label_category,
        )

    def label_traces(self, traces: List[ActionTrace]) -> List[OutcomeLabels]:
        """Convenience: label a list of traces in one call."""
        return [self.label_trace(t) for t in traces]

    # -- internal scoring functions -----------------------------------------

    def _compute_efficiency(self, trace: ActionTrace) -> float:
        """Score efficiency based on execution time vs baseline.

        Returns 1.0 when at or below baseline, linearly decaying to 0.0
        when at 5× baseline.  Without a baseline → 0.75 (neutral).
        """
        if not trace.action_types or trace.execution_time_ms <= 0:
            return 0.75  # neutral default

        baselines = [
            self.efficiency_baseline.get(at)
            for at in trace.action_types
            if at in self.efficiency_baseline
        ]
        if not baselines:
            return 0.75

        expected_ms = sum(baselines)
        if expected_ms <= 0:
            return 0.75

        ratio = trace.execution_time_ms / expected_ms
        if ratio <= 1.0:
            return 1.0
        if ratio >= 5.0:
            return 0.0
        return max(0.0, 1.0 - (ratio - 1.0) / 4.0)

    def _compute_safety_score(self, trace: ActionTrace) -> float:
        """Return 1.0 unless safety-related keywords appear in outcome."""
        details_str = str(trace.outcome_details).lower()
        violations = sum(
            1 for kw in self.safety_keywords if kw in details_str
        )
        if violations == 0:
            return 1.0
        if violations == 1:
            return 0.5
        return 0.0

    def _compute_confidence_calibration(self, trace: ActionTrace) -> float:
        """How well predicted confidence matched actual outcome."""
        actual = 1.0 if trace.outcome_success else 0.0
        return 1.0 - abs(trace.confidence_at_decision - actual)

    @staticmethod
    def _compute_human_agreement(trace: ActionTrace) -> float:
        """1.0 when no human correction; 0.5 otherwise."""
        return 0.5 if trace.human_correction else 1.0
