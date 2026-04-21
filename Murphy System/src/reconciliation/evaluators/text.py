"""Generic text-deliverable evaluator (default fallback)."""

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


class TextDeliverableEvaluator(DeterministicEvaluator):
    """Evaluator for free-form text deliverables.

    Adds a single deterministic criterion: the deliverable must contain
    at least one alphanumeric character — a minimum substance floor that
    catches accidentally-empty outputs.
    """

    deliverable_types = (
        DeliverableType.GENERIC_TEXT,
        DeliverableType.OTHER,
        DeliverableType.WORKFLOW,
    )

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        yield AcceptanceCriterion(
            description="Deliverable contains substantive content",
            kind=CriterionKind.STANDARD,
            weight=1.0,
            hard=True,
            check_spec={"kind": "regex", "pattern": r"[A-Za-z0-9]"},
        )


register_evaluator(DeliverableType.GENERIC_TEXT, TextDeliverableEvaluator())
register_evaluator(DeliverableType.OTHER, TextDeliverableEvaluator())
register_evaluator(DeliverableType.WORKFLOW, TextDeliverableEvaluator())


__all__ = ["TextDeliverableEvaluator"]
