"""Document deliverable evaluator (Markdown / prose)."""

from __future__ import annotations

import re
from typing import Iterable

from ..models import (
    AcceptanceCriterion,
    CriterionKind,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    PatchKind,
)
from .base import DeterministicEvaluator, EvaluationContext, register_evaluator


_HEADING = re.compile(r"^(#{1,6})\s", re.MULTILINE)


class DocumentDeliverableEvaluator(DeterministicEvaluator):
    """Evaluator for documents (Markdown and similar prose)."""

    deliverable_types = (
        DeliverableType.DOCUMENT,
        DeliverableType.PLAN,
        DeliverableType.DASHBOARD,
    )

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        # Documents must have actual prose, not just whitespace.
        yield AcceptanceCriterion(
            description="Document is non-trivial",
            kind=CriterionKind.STANDARD,
            weight=1.0,
            hard=True,
            check_spec={"kind": "min_length", "value": 1},
        )

    def additional_diagnoses(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: EvaluationContext,
    ) -> Iterable[Diagnosis]:
        content = deliverable.content
        if not isinstance(content, str):
            return ()

        diagnoses = []
        headings = _HEADING.findall(content)

        # Heading-depth jumps (H1 -> H3 with no H2) are an above-average
        # writing red flag.
        levels = [len(h) for h in headings]
        for i in range(1, len(levels)):
            if levels[i] > levels[i - 1] + 1:
                diagnoses.append(
                    Diagnosis(
                        severity=DiagnosisSeverity.MINOR,
                        summary=(
                            f"Heading depth jumps from H{levels[i - 1]} to H{levels[i]} — "
                            "skip a level."
                        ),
                        suggested_patch_kind=PatchKind.CONTENT_EDIT,
                        suggested_action="Insert intermediate heading levels",
                        evidence={"levels": levels},
                    )
                )
                break

        # Multiple consecutive blank lines indicate sloppy formatting.
        if "\n\n\n\n" in content:
            diagnoses.append(
                Diagnosis(
                    severity=DiagnosisSeverity.INFO,
                    summary="Document contains 4+ consecutive blank lines",
                    suggested_patch_kind=PatchKind.CONTENT_EDIT,
                    suggested_action="Collapse repeated blank lines",
                    evidence={},
                )
            )

        return diagnoses


register_evaluator(DeliverableType.DOCUMENT, DocumentDeliverableEvaluator())
register_evaluator(DeliverableType.PLAN, DocumentDeliverableEvaluator())
register_evaluator(DeliverableType.DASHBOARD, DocumentDeliverableEvaluator())


__all__ = ["DocumentDeliverableEvaluator"]
