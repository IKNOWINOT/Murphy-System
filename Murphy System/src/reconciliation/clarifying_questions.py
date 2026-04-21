"""
Auto-emit :class:`ClarifyingQuestion`s from an :class:`AmbiguityVector`.

The :class:`IntentExtractor` already enumerates which dimensions of a
request are under-specified (output format, scope, deadline, ...),
but historically nothing turned that vector into actual questions
back to the principal — Murphy would proceed on a tautological
acceptance criterion ("Deliverable satisfies the literal request").
That is exactly the silent-failure mode we forbid.

Question synthesis is **triggered automatically** by
:meth:`IntentExtractor.extract` whenever the ambiguity vector is
non-empty; callers do not have to know to invoke it.

Candidate answers are drawn from the classifier's top-K ranked
deliverable types when relevant, so the user picks from a short,
on-topic list rather than the full 11-class enum.

CITL / HITL boundary
====================

* **CITL OK** — generating the questions, the candidate answers, the
  free-text fallback option.  Question text is just an artifact for
  display.
* **HITL required** — *answering* the questions.  Selecting one of
  the candidate answers is, by definition, the principal resolving
  ambiguity.  Murphy MUST NOT auto-pick a candidate answer to "make
  progress" — that is the regression we are guarding against.

Design label: HITL-002
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .intent_classifier import IntentPrediction
from .models import AmbiguityVector, ClarifyingQuestion, DeliverableType


# Question template + (default) candidate answers per ambiguity-vector
# item label.  The "deliverable type" candidates are overridden at call
# time using the classifier's top-K ranking when available.
_TEMPLATES: Dict[str, Tuple[str, Sequence[str]]] = {
    "audience": (
        "Who is this for?",
        ("Internal team", "End users / customers", "Investors / stakeholders", "General public"),
    ),
    "output format": (
        "What output format do you want?",
        ("Markdown document", "Plain text", "JSON", "PDF", "Slide deck"),
    ),
    "scope / boundaries": (
        "What's in scope and what's explicitly out of scope?",
        ("Minimum viable scope only", "Include all stated items", "Include items + reasonable extensions"),
    ),
    "acceptance criteria": (
        "How will we know this is done?",
        ("I'll review and confirm manually", "Pass automated tests", "Match a specific exemplar I'll provide"),
    ),
    "deadline / urgency": (
        "When do you need this by?",
        ("Today", "This week", "This month", "No fixed deadline"),
    ),
    "environment / target": (
        "Which environment is this targeting?",
        ("Local / dev", "Staging", "Production", "Not yet decided"),
    ),
    "deliverable type": (
        "What kind of deliverable do you want?",
        # Overridden at call time from classifier ranking when available.
        tuple(t.value for t in DeliverableType if t != DeliverableType.OTHER),
    ),
}

# Generic fallback for items we don't have a template for.
_GENERIC_TEMPLATE = (
    "Can you clarify '{item}'?",
    ("Provide more detail", "Use a sensible default", "Skip this dimension"),
)

# Always offered as a free-text escape hatch on every question so the
# principal isn't forced into a multiple-choice strait-jacket.
_FREE_TEXT_OPTION = "Other (free text)"


class ClarifyingQuestionSynthesizer:
    """Turn an :class:`AmbiguityVector` into actionable questions.

    Args:
        max_questions: Cap on the number of questions emitted in a
            single batch — keeps the HITL prompt short.
        type_suggestions: Number of classifier-ranked deliverable
            types to surface as picks for the "deliverable type"
            question (default 4).
    """

    def __init__(
        self,
        max_questions: int = 5,
        type_suggestions: int = 4,
    ) -> None:
        if max_questions < 1:
            raise ValueError("max_questions must be >= 1")
        if type_suggestions < 1:
            raise ValueError("type_suggestions must be >= 1")
        self._max = max_questions
        self._type_suggestions = type_suggestions

    def synthesize(
        self,
        vector: AmbiguityVector,
        prediction: Optional[IntentPrediction] = None,
    ) -> List[ClarifyingQuestion]:
        """Return one :class:`ClarifyingQuestion` per ambiguity item.

        Args:
            vector: The ambiguity vector from :meth:`IntentExtractor.ambiguity_vector`.
            prediction: Optional classifier prediction.  When supplied,
                the "deliverable type" question's candidate answers are
                drawn from ``prediction.ranking[:type_suggestions]``
                rather than the full enum — relevant picks instead of
                the whole catalog.
        """
        out: List[ClarifyingQuestion] = []
        for item in vector.items[: self._max]:
            template, candidates = _TEMPLATES.get(item, _GENERIC_TEMPLATE)
            question = template.format(item=item)

            if (
                item == "deliverable type"
                and prediction is not None
                and prediction.token_count > 0
                and prediction.ranking
            ):
                ranked = [
                    cls.value
                    for cls, _ in prediction.ranking[: self._type_suggestions]
                    if cls != DeliverableType.OTHER
                ]
                if ranked:
                    candidates = tuple(ranked)

            answers = list(candidates)
            if _FREE_TEXT_OPTION not in answers:
                answers.append(_FREE_TEXT_OPTION)

            out.append(
                ClarifyingQuestion(
                    question=question,
                    ambiguity_item=item,
                    candidate_answers=answers,
                )
            )
        return out


__all__ = ["ClarifyingQuestionSynthesizer"]

