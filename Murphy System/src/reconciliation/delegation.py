"""
Best-recommendations mode — opt-in on explicit user delegation.

By default (HITL-002) Murphy refuses to auto-answer its own
:class:`ClarifyingQuestion`s — answering is the principal's job.  But
real users frequently say things like "you can pick", "your call", or
"use your best judgment".  When the principal *explicitly* delegates,
the right move is to:

1. Auto-resolve each clarifying question with Murphy's best pick
   (top-ranked candidate; classifier ranking when one is wired).
2. Record every pick with provenance — what we chose and why — so
   the principal can audit and override any individual assumption.
3. Mark the resulting deliverable as a "best-effort working version"
   and surface the assumptions panel.

CITL / HITL boundary
====================

* **HITL act** — saying "you can pick".  Murphy never assumes
  delegation; the principal must opt in with an explicit phrase or
  by setting ``Request.context['delegation'] = True``.
* **CITL OK** — once delegation is granted, picking the top-ranked
  candidate is fully automated, *provided every pick is recorded
  with provenance*.  No silent guessing.
* **Still HITL** — delegation does NOT extend to side-effect
  operations (capital allocation, external messages, prod changes).
  Those remain HITL even when delegation is granted on phrasing /
  format / scope dimensions.

Design label: HITL-003
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .intent_classifier import IntentPrediction
from .models import ClarifyingQuestion, DelegatedPick


# ---------------------------------------------------------------------------
# Delegation detection
# ---------------------------------------------------------------------------

# Phrases that explicitly transfer pick authority to Murphy.  Kept
# conservative on purpose: false positives here would silently disable
# the HITL-002 protection.
_DELEGATION_PHRASES = (
    r"you\s+can\s+pick",
    r"you\s+pick",
    r"you\s+choose",
    r"you\s+decide",
    r"your\s+call",
    r"your\s+choice",
    r"use\s+your\s+best\s+judgment",
    r"use\s+your\s+best\s+judgement",
    r"best\s+recommendations?",
    r"best[-\s]?effort\s+(?:version|pick|guess)",
    r"surprise\s+me",
    r"make\s+the\s+call",
    r"go\s+with\s+(?:whatever|your)\s+(?:you\s+think|best|recommendation)",
    r"\bwhatever\s+you\s+(?:think|recommend|pick)",
    r"i\s+trust\s+you",
    r"pick\s+for\s+me",
)
_DELEGATION_RE = re.compile(
    r"(?:" + "|".join(_DELEGATION_PHRASES) + r")",
    re.IGNORECASE,
)

# Negation guard — phrases that look like delegation but explicitly
# revoke it ("don't pick for me", "I'll decide").
_NEGATION_RE = re.compile(
    r"(?:don'?t|do\s+not|never)\s+(?:pick|choose|decide|guess)",
    re.IGNORECASE,
)
_RESERVATION_RE = re.compile(
    r"\bi(?:'ll|\s+will)?\s+(?:pick|choose|decide)",
    re.IGNORECASE,
)


def detect_delegation(text: str) -> bool:
    """Return True iff *text* explicitly delegates picks to Murphy.

    The detector is **conservative**: any of the negation / reservation
    patterns wins over a delegation phrase.  When in doubt, return
    False — the HITL-002 default applies and the principal is asked.
    """
    if not text:
        return False
    if _NEGATION_RE.search(text) or _RESERVATION_RE.search(text):
        return False
    return bool(_DELEGATION_RE.search(text))


# ---------------------------------------------------------------------------
# Auto-resolver
# ---------------------------------------------------------------------------

# Standard rationale strings — surfaced in the dashboard / audit log.
_RATIONALE_CLASSIFIER = "auto: top classifier rank"
_RATIONALE_DEFAULT_FIRST = "auto: first non-free-text candidate"
_RATIONALE_FALLBACK = "auto: free-text fallback (no concrete options)"

# A short, principal-facing preamble we recommend prepending to any
# deliverable produced under delegation.  Generators are free to
# render it however they like; the canonical text lives here so the
# dashboard, the export, and the LLM rubric all agree on the framing.
BEST_EFFORT_PREAMBLE = (
    "Working version — best-effort recommendations.\n"
    "I'd normally ask the questions below before committing; you "
    "delegated the picks to me, so each is my best guess given the "
    "request. Override any of them and I'll regenerate."
)


def auto_resolve_questions(
    questions: Sequence[ClarifyingQuestion],
    prediction: Optional[IntentPrediction] = None,
) -> List[DelegatedPick]:
    """Pick a best-effort answer for each clarifying question.

    The selection rules, in order:

    1. For the "deliverable type" question, pick the classifier's
       top-ranked deliverable type (when a prediction is supplied
       and has nonzero token coverage).
    2. Otherwise, pick the first candidate that is not the free-text
       escape hatch.
    3. If the only candidate is the free-text option, record a
       fallback pick with that text — the dashboard renders it as
       "(no concrete options — please specify)".

    Each pick carries the question, the chosen answer, and a short
    rationale string so the principal can audit every assumption.
    """
    picks: List[DelegatedPick] = []
    for q in questions:
        candidates = list(q.candidate_answers)
        chosen: Optional[str] = None
        rationale = _RATIONALE_DEFAULT_FIRST

        if (
            q.ambiguity_item == "deliverable type"
            and prediction is not None
            and prediction.token_count > 0
            and prediction.ranking
        ):
            top = prediction.ranking[0][0].value
            if top in candidates:
                chosen = top
                rationale = _RATIONALE_CLASSIFIER

        if chosen is None:
            non_free = [c for c in candidates if "free text" not in c.lower()]
            if non_free:
                chosen = non_free[0]
                rationale = _RATIONALE_DEFAULT_FIRST
            elif candidates:
                chosen = candidates[0]
                rationale = _RATIONALE_FALLBACK
            else:
                # Defensive — synthesizer always emits at least one option.
                chosen = ""
                rationale = _RATIONALE_FALLBACK

        picks.append(
            DelegatedPick(
                question_id=q.id,
                question=q.question,
                ambiguity_item=q.ambiguity_item,
                chosen_answer=chosen,
                rationale=rationale,
            )
        )
    return picks


__all__ = [
    "BEST_EFFORT_PREAMBLE",
    "auto_resolve_questions",
    "detect_delegation",
]
