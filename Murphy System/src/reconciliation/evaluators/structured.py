"""
Evaluators for structured-payload deliverables (JSON payloads, deployment
results) that have dict-shaped content rather than text.

These evaluators inherit the standards-derived criteria from the catalog
(JSON-001, DEPLOY-001) but skip any text-only substance regex by
overriding :meth:`additional_criteria` to use a type-aware substance
check instead.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Tuple

from ..models import (
    AcceptanceCriterion,
    CriterionKind,
    Deliverable,
    DeliverableType,
    IntentSpec,
)
from ..standards import _CALLABLE_REGISTRY  # type: ignore[attr-defined]
from .base import DeterministicEvaluator, register_evaluator
from .text import check_text_substance


def check_structured_payload_substance(content: Any) -> Tuple[bool, float, str]:
    """Substance floor for JSON / deployment-style payloads.

    Strings that parse as JSON are evaluated against the *parsed*
    structure (so ``"[1,2,3]"`` counts as a 3-element list, not a
    9-character string).  Anything else falls through to the generic
    type-aware substance check.
    """
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except (ValueError, TypeError):
            # Not JSON — fall back to text substance.
            return check_text_substance(content)
        # Empty containers (``[]``, ``{}``) are not substantive payloads.
        if isinstance(parsed, (list, dict, tuple, set)) and not parsed:
            return (False, 0.0, f"parsed JSON is empty {type(parsed).__name__}")
        if parsed is None:
            return (False, 0.0, "parsed JSON is null")
        return (True, 1.0, f"parsed JSON: {type(parsed).__name__}")
    return check_text_substance(content)


_CALLABLE_REGISTRY[
    "src.reconciliation.evaluators.structured:check_structured_payload_substance"
] = check_structured_payload_substance


class StructuredPayloadEvaluator(DeterministicEvaluator):
    """Evaluator for dict / list-shaped deliverables.

    Adds a JSON-aware substance floor so empty payloads are reliably
    caught, regardless of whether they arrive as Python objects or
    serialised strings.
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
                "fn": "src.reconciliation.evaluators.structured:check_structured_payload_substance",
            },
        )


register_evaluator(DeliverableType.JSON_PAYLOAD, StructuredPayloadEvaluator())
register_evaluator(DeliverableType.DEPLOYMENT_RESULT, StructuredPayloadEvaluator())


__all__ = ["StructuredPayloadEvaluator", "check_structured_payload_substance"]
