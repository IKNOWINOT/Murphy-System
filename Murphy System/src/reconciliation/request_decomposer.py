"""
Request → multiple :class:`Request` decomposition.

When a single prompt asks for *several* deliverables (for example,
"build an MVP web app, write a launch campaign, and draft a one-year
business plan"), the rest of the reconciliation pipeline collapses
that into one degenerate ``GENERIC_TEXT`` spec.  The
:class:`RequestDecomposer` splits such prompts into one sub-request
per detected deliverable so :class:`IntentExtractor` can extract a
spec for each.

CITL / HITL boundary
====================

* **CITL OK** — splitting the text, classifying each fragment,
  emitting sub-:class:`Request`s.  The output is a list of
  candidate interpretations; nothing is executed.
* **HITL required** — choosing *which* sub-request to actually
  execute, especially when fragments imply mutually exclusive
  business decisions ("the number one platform" must be resolved
  by the principal, not guessed).

Design label: RECON-INTENT-003
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .intent_classifier import IntentClassifier
from .models import DeliverableType, Request

logger = logging.getLogger(__name__)


# Strong verb cues that typically open a new deliverable clause.
_DELIVERABLE_VERBS = (
    "build", "make", "create", "design", "develop", "scaffold",
    "write", "draft", "compose", "author",
    "plan", "outline", "propose",
    "deploy", "ship", "launch", "release",
    "set up", "set-up", "configure", "provision",
    "generate", "produce",
)

# Sentence-ish boundary: period, semicolon, newline, " and " between
# verb-led clauses.  We split conservatively, keep order.
_SPLIT_RE = re.compile(r"(?<=[.;\n])\s+|(?:^|\s)(?:also|then|plus)\s+", re.IGNORECASE)
_VERB_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _DELIVERABLE_VERBS) + r")\b",
    re.IGNORECASE,
)

# Minimum length (chars) of a fragment to be considered its own
# deliverable — anything shorter is treated as a continuation.
_MIN_FRAGMENT_LEN = 18


@dataclass(frozen=True)
class DecompositionPart:
    """One fragment of a decomposed request."""

    text: str
    deliverable_type: DeliverableType
    confidence: float
    leading_verb: Optional[str]


class RequestDecomposer:
    """Split a free-form :class:`Request` into one or more sub-requests.

    The decomposer is *advisory* in the same sense as
    :class:`IntentClassifier`: it returns hints, never side-effects.

    Args:
        classifier: Optional :class:`IntentClassifier`.  When provided,
            each fragment is classified to assign its deliverable
            type; otherwise every fragment defaults to
            :attr:`DeliverableType.GENERIC_TEXT`.
        min_parts_to_decompose: A request is only treated as multi-
            deliverable when at least this many distinct verb-led
            fragments are detected (default 2).
        max_parts: Hard cap on the number of sub-requests returned.
    """

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        min_parts_to_decompose: int = 2,
        max_parts: int = 6,
    ) -> None:
        if min_parts_to_decompose < 2:
            raise ValueError("min_parts_to_decompose must be >= 2")
        if max_parts < min_parts_to_decompose:
            raise ValueError("max_parts must be >= min_parts_to_decompose")
        self._classifier = classifier
        self._min_parts = min_parts_to_decompose
        self._max_parts = max_parts

    # ------------------------------------------------------------------

    def is_multi_deliverable(self, request: Request) -> bool:
        """Return True when *request* contains multiple verb-led clauses."""
        return len(self._segment(request.text)) >= self._min_parts

    def parts(self, request: Request) -> List[DecompositionPart]:
        """Return the typed parts the request decomposes into.

        For non-multi-deliverable requests this returns a single part
        wrapping the whole request — callers can therefore use the
        same code path for both cases.
        """
        fragments = self._segment(request.text)
        if not fragments:
            fragments = [request.text.strip()]
        out: List[DecompositionPart] = []
        for frag, verb in fragments[: self._max_parts]:
            dtype, conf = self._type_for(frag)
            out.append(
                DecompositionPart(
                    text=frag,
                    deliverable_type=dtype,
                    confidence=conf,
                    leading_verb=verb,
                )
            )
        return out

    def decompose(self, request: Request) -> List[Request]:
        """Return one :class:`Request` per detected deliverable.

        If the request does not look multi-deliverable, returns
        ``[request]`` unchanged so call sites can use this method
        unconditionally.
        """
        if not self.is_multi_deliverable(request):
            return [request]

        parts = self.parts(request)
        sub_requests: List[Request] = []
        for idx, part in enumerate(parts):
            sub_requests.append(
                Request(
                    text=part.text,
                    deliverable_type=part.deliverable_type,
                    requester_id=request.requester_id,
                    context={
                        **request.context,
                        "decomposed_from": request.id,
                        "decomposition_index": idx,
                        "decomposition_total": len(parts),
                        "leading_verb": part.leading_verb or "",
                        "decomposer_confidence": part.confidence,
                    },
                )
            )
        return sub_requests

    # ------------------------------------------------------------------

    def _segment(self, text: str) -> List[Tuple[str, Optional[str]]]:
        """Return ``[(fragment, leading_verb), ...]`` in source order."""
        if not text or not text.strip():
            return []

        raw = [seg.strip() for seg in _SPLIT_RE.split(text) if seg and seg.strip()]
        if not raw:
            raw = [text.strip()]

        # For each segment, further split on " and " between two verb-led
        # clauses ("build X and write Y") — only when both halves contain
        # a deliverable verb.
        expanded: List[str] = []
        for seg in raw:
            expanded.extend(self._split_on_inner_and(seg))

        # Keep only segments that look like a deliverable clause: must
        # contain a deliverable verb AND clear the length floor.
        out: List[Tuple[str, Optional[str]]] = []
        for seg in expanded:
            if len(seg) < _MIN_FRAGMENT_LEN:
                continue
            m = _VERB_RE.search(seg)
            if not m:
                continue
            out.append((seg, m.group(1).lower()))
        return out

    @staticmethod
    def _split_on_inner_and(segment: str) -> List[str]:
        """Split ``segment`` on " and " only when *both* halves are verb-led."""
        # Find candidate split points (lower-cased ' and ' boundaries).
        parts: List[str] = []
        cursor = 0
        lowered = segment.lower()
        for match in re.finditer(r"\band\b", lowered):
            left = segment[cursor : match.start()].strip()
            right = segment[match.end():].strip()
            if (
                len(left) >= _MIN_FRAGMENT_LEN
                and len(right) >= _MIN_FRAGMENT_LEN
                and _VERB_RE.search(left)
                and _VERB_RE.search(right)
            ):
                parts.append(left)
                cursor = match.end()
        tail = segment[cursor:].strip()
        if tail:
            parts.append(tail)
        return parts or [segment]

    def _type_for(self, fragment: str) -> Tuple[DeliverableType, float]:
        """Classify a fragment, falling back to GENERIC_TEXT on no signal."""
        if self._classifier is None:
            return DeliverableType.GENERIC_TEXT, 0.5
        try:
            pred = self._classifier.predict(fragment)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "RequestDecomposer classifier raised %s; defaulting fragment "
                "to GENERIC_TEXT", exc,
            )
            return DeliverableType.GENERIC_TEXT, 0.0
        if pred.token_count == 0:
            return DeliverableType.GENERIC_TEXT, 0.0
        return pred.deliverable_type, pred.confidence


__all__ = ["DecompositionPart", "RequestDecomposer"]
