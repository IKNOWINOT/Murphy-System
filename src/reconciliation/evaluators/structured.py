"""
Evaluators for structured-payload deliverables (JSON payloads, deployment
results) that have dict-shaped content rather than text.

These evaluators inherit the standards-derived criteria from the catalog
(JSON-001, DEPLOY-001) but skip any text-only substance regex by
overriding :meth:`additional_criteria` to use a type-aware substance
check instead.
"""

from __future__ import annotations

from typing import Iterable

from ..models import (
    AcceptanceCriterion,
    CriterionKind,
    Deliverable,
    DeliverableType,
    IntentSpec,
)
from .base import DeterministicEvaluator, register_evaluator


class StructuredPayloadEvaluator(DeterministicEvaluator):
    """Evaluator for dict / list-shaped deliverables.

    Adds the same type-aware substance floor used by the text evaluator
    so empty payloads are reliably caught regardless of content type.
    """

    deliverable_types = (
        DeliverableType.JSON_PAYLOAD,
        DeliverableType.DEPLOYMENT_RESULT,
    )

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        yield AcceptanceCriterion(
            description="Deliverable payload is non-empty",
            kind=CriterionKind.STANDARD,
            weight=1.0,
            hard=True,
            check_spec={
                "kind": "callable",
                "fn": "src.reconciliation.evaluators.text:check_text_substance",
            },
        )


register_evaluator(DeliverableType.JSON_PAYLOAD, StructuredPayloadEvaluator())
register_evaluator(DeliverableType.DEPLOYMENT_RESULT, StructuredPayloadEvaluator())


__all__ = ["StructuredPayloadEvaluator"]
