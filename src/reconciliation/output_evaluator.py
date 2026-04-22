"""
Top-level multi-signal output evaluator.

Aggregates the per-criterion results from the appropriate
:mod:`evaluators` plug-in into a single :class:`ReconciliationScore`.

Score aggregation follows a *strict* model: any ``hard`` criterion that
fails sets ``hard_pass = False``.  The soft score is the weighted mean
of every criterion's per-criterion score.

Design label: RECON-EVAL-TOP-001
"""

from __future__ import annotations

import logging
from typing import Optional

from .evaluators import (
    EvaluationContext,
    get_evaluator,
)
from .models import (
    Deliverable,
    IntentSpec,
    ReconciliationScore,
)

logger = logging.getLogger(__name__)


class OutputEvaluator:
    """Top-level evaluator that fans out to per-type evaluators."""

    def __init__(self, context: Optional[EvaluationContext] = None) -> None:
        self._context = context or EvaluationContext()

    def score(self, deliverable: Deliverable, intent: IntentSpec) -> ReconciliationScore:
        """Score *deliverable* against *intent*."""
        evaluator = get_evaluator(deliverable.deliverable_type)
        results, diagnoses = evaluator.evaluate(deliverable, intent, self._context)

        hard_pass = all(r.passed for r in results if r.hard)

        total_weight = sum(r.weight for r in results) or 1.0
        soft_score = sum(r.score * r.weight for r in results) / total_weight
        soft_score = max(0.0, min(1.0, soft_score))

        score = ReconciliationScore(
            deliverable_id=deliverable.id,
            intent_id=intent.id,
            soft_score=round(soft_score, 6),
            hard_pass=hard_pass,
            per_criterion=results,
            diagnoses=diagnoses,
        )

        logger.debug(
            "Reconciliation score deliverable=%s intent=%s soft=%.3f hard_pass=%s diagnoses=%d",
            deliverable.id,
            intent.id,
            soft_score,
            hard_pass,
            len(diagnoses),
        )
        return score


__all__ = ["OutputEvaluator"]
