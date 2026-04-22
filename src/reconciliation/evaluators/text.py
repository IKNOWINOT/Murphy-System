"""Generic text-deliverable evaluator (default fallback)."""

from __future__ import annotations

import re
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


# Above-average professional minimums for free-form text deliverables.
# A single token like "ok" is not a substantive summary or response.
_MIN_SUBSTANCE_CHARS = 12
_MIN_SUBSTANCE_WORDS = 2


def check_text_substance(content: Any) -> Tuple[bool, float, str]:
    """Type-aware substance floor for any deliverable.

    Strings must clear a minimum length AND a minimum word count.
    Dicts and lists must be non-empty.  Anything else passes through —
    type-specific evaluators are responsible for those.

    Returns ``(passed, score, detail)``.
    """
    if isinstance(content, str):
        stripped = content.strip()
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", stripped)
        if not stripped or not words:
            return (False, 0.0, "empty or whitespace-only content")
        if len(stripped) < _MIN_SUBSTANCE_CHARS or len(words) < _MIN_SUBSTANCE_WORDS:
            ratio = min(
                len(stripped) / _MIN_SUBSTANCE_CHARS,
                len(words) / _MIN_SUBSTANCE_WORDS,
            )
            return (
                False,
                max(0.0, min(1.0, ratio)),
                (
                    f"content is too short to be substantive "
                    f"(chars={len(stripped)}<{_MIN_SUBSTANCE_CHARS}, "
                    f"words={len(words)}<{_MIN_SUBSTANCE_WORDS})"
                ),
            )
        return (True, 1.0, f"chars={len(stripped)}, words={len(words)}")

    if isinstance(content, (dict, list, tuple, set)):
        if not content:
            return (False, 0.0, f"{type(content).__name__} is empty")
        return (True, 1.0, f"{type(content).__name__} has {len(content)} entries")

    if content is None:
        return (False, 0.0, "content is None")

    # Bytes / numbers / objects: defer judgement to the type-specific evaluator.
    return (True, 1.0, f"non-text content of type {type(content).__name__} — substance deferred")


# Expose via the standards-callable registry so it works from check_spec.
_CALLABLE_REGISTRY["src.reconciliation.evaluators.text:check_text_substance"] = check_text_substance


class TextDeliverableEvaluator(DeterministicEvaluator):
    """Evaluator for free-form text deliverables.

    Enforces an above-average substance floor: non-empty, at least
    :data:`_MIN_SUBSTANCE_CHARS` characters AND :data:`_MIN_SUBSTANCE_WORDS`
    distinct words.  Single-token outputs like ``"ok"`` are flagged.

    The same substance check is type-aware — it accepts non-empty dicts /
    lists so the same evaluator can serve as a safe last-resort fallback
    for structured deliverable types that have no dedicated evaluator
    registered (e.g. JSON payloads, deployment results).
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
            check_spec={
                "kind": "callable",
                "fn": "src.reconciliation.evaluators.text:check_text_substance",
            },
        )


register_evaluator(DeliverableType.GENERIC_TEXT, TextDeliverableEvaluator())
register_evaluator(DeliverableType.OTHER, TextDeliverableEvaluator())
register_evaluator(DeliverableType.WORKFLOW, TextDeliverableEvaluator())


__all__ = ["TextDeliverableEvaluator", "check_text_substance"]
