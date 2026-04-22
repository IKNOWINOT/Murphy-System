"""
Universal AI-recommendation framing for every Murphy deliverable.

Doctrine — *AI-first draft, HITL-validated commit*
==================================================

No deliverable Murphy emits is ever final.  Every deliverable is a
**professional starting point** — completely done from the AI's
perspective, with dramatically less work left for the human reviewer
(validation + selection rather than authorship), but explicitly
labelled as such with the HITL boundary named.

This module defines:

* :class:`RequestVsInference` — a real, computed delta between the
  principal's literal request text and Murphy's structured
  :class:`IntentSpec`.  Enumerates dimensions Murphy *assumed*,
  request fragments Murphy *did not address*, and added criteria /
  preferences that came from Murphy rather than the request itself.
  Computed deterministically; never a placeholder.

* :class:`AIRecommendationFraming` — the value object every renderer
  must surface.  Carries the always-present, never-suppressible AI
  disclosure, the confidence band (high / medium / low), the
  validation call-to-action, the assumptions panel
  (:class:`DelegatedPick` list), the unresolved
  :class:`ClarifyingQuestion`s, the suggested validation steps (one
  per still-unresolved ambiguity dimension), and the
  :class:`RequestVsInference` panel.

* :func:`build_framing` — the deterministic builder called from
  :class:`IntentExtractor.extract`.  Inputs:
  ``(request, spec, delegation_granted, picks, mss_trace)``.
  Output: a fully-populated :class:`AIRecommendationFraming` whose
  :attr:`disclosure` is non-empty regardless of inputs.

* :class:`BaseDeliverableRenderer` — the contract every concrete
  generator (markdown writer, code writer, plan writer, dashboard
  payload) must extend.  Subclasses override :meth:`_render_body`
  only; the public :meth:`render` is final and composes
  ``disclosure + body + assumptions panel + validation steps +
  request-vs-inference panel`` so the framing is structurally
  impossible to omit.

CITL / HITL boundary for the framing itself
-------------------------------------------

* The framing is **CITL** — Murphy generates it deterministically
  from ``(ambiguity_vector, mss_trace, delegation_granted,
  delegated_picks, request_text, spec)``.
* The *validation* it requests is **HITL**.  Removing the framing
  requires changing source code (audit trail on review), not a
  runtime flag.
* Like the FDA black-box-warning rule, individual fields can be
  *reworded* by callers passing custom :class:`AIRecommendationFraming`
  configs, but the disclosure cannot be empty — pydantic enforces
  ``min_length=1`` and the builder always supplies a non-empty value.

Design label: HITL-004
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import Field, field_validator

from .delegation import BEST_EFFORT_PREAMBLE
from .models import (
    AmbiguityVector,
    ClarifyingQuestion,
    DelegatedPick,
    IntentSpec,
    Request,
    _ReconBase,
)


# ---------------------------------------------------------------------------
# Confidence band
# ---------------------------------------------------------------------------


class ConfidenceBand(str, Enum):
    """Three-tier framing intensity, derived from ambiguity + MSS + delegation.

    The tier selects the *wording* of the disclosure / call-to-action,
    never the *presence* of the framing (which is mandatory).
    """

    HIGH = "high"      # low ambiguity, no MSS clarify, no delegation
    MEDIUM = "medium"  # some ambiguity remained, or delegation on minor dims
    LOW = "low"        # MSS recommended clarify/block, or delegation on
                       # high-stakes dims, or many unresolved questions


# Disclosure templates — terse, principal-facing, never empty.  The
# {n} placeholder is filled with the count of assumptions / open
# questions so the reviewer immediately knows the surface area.
_DISCLOSURE_HIGH = (
    "Recommendation. I'm an AI — please validate the {n} assumption(s) "
    "below before acting."
)
_DISCLOSURE_MEDIUM = BEST_EFFORT_PREAMBLE  # canonical phrasing
_DISCLOSURE_LOW = (
    "Working draft. I am an AI and I strongly recommend a HITL "
    "validation pass here to reduce variables — see the per-dimension "
    "checklist below."
)

# Call-to-action templates — tells the reviewer where to focus first.
_CTA_HIGH = "Validate the assumptions panel; sign-off otherwise."
_CTA_MEDIUM = (
    "Review every assumption I auto-resolved; override any that don't "
    "match your intent and I'll regenerate."
)
_CTA_LOW = (
    "Do not act on this draft until the validation checklist is "
    "answered. Several dimensions are unresolved or high-stakes."
)


# ---------------------------------------------------------------------------
# Request ↔ inference delta — the actual, computed comparison
# ---------------------------------------------------------------------------


# Stopwords kept short on purpose — we only need to filter the
# obvious filler so the request-token coverage diff stays meaningful.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on",
    "for", "with", "from", "by", "at", "as", "is", "are", "was", "were",
    "be", "been", "being", "it", "this", "that", "these", "those", "i",
    "you", "your", "we", "us", "our", "they", "them", "their", "me",
    "my", "mine", "do", "does", "did", "doing", "have", "has", "had",
    "having", "will", "would", "should", "could", "can", "may", "might",
    "must", "shall", "not", "no", "yes", "so", "than", "then", "into",
    "out", "up", "down", "over", "under", "again", "further", "just",
    "also", "any", "all", "some", "few", "more", "most", "other",
    "such", "only", "own", "same", "very", "too", "now",
    # delegation noise — the framing already records delegation explicitly,
    # so these tokens shouldn't show up as "unaddressed request content".
    "pick", "picks", "choose", "decide", "call", "judgment", "judgement",
    "best", "honestly", "trust", "surprise", "whatever", "recommendations",
    "recommendation",
})

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")


def _content_tokens(text: str) -> List[str]:
    """Lowercased content words from *text* with stopwords removed."""
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if t.lower() not in _STOPWORDS
    ]


class RequestVsInference(_ReconBase):
    """A real, computed delta between the literal request and the inference.

    All fields are derived deterministically from the inputs; nothing
    here is a placeholder.  The reviewer can use this panel to spot
    exactly where Murphy's interpretation diverged from what was
    written, before validating anything else.
    """

    original_request: str = Field(..., min_length=1)
    inferred_summary: str = Field(..., min_length=1)
    inferred_deliverable_type: str = Field(..., min_length=1)
    inferred_confidence: float = Field(..., ge=0.0, le=1.0)

    # Dimensions Murphy filled in that the request did not specify.
    # Each entry: ``"<ambiguity dimension> := <chosen answer> (<rationale>)"``
    # for resolved picks, or ``"<dimension> := <unresolved>"`` for items
    # that remain open questions.
    assumed_dimensions: List[str] = Field(default_factory=list)

    # Content tokens present in the original request that do NOT appear
    # in the inferred summary or any acceptance criterion / preference.
    # These are the literal asks Murphy may have failed to address.
    unaddressed_request_terms: List[str] = Field(default_factory=list)

    # Acceptance criteria / soft preferences that come from Murphy
    # (catalog defaults, standards) rather than from the request text.
    # Lets the reviewer see which constraints they didn't ask for.
    added_by_inference: List[str] = Field(default_factory=list)

    # Best-practice standards (by id) Murphy attached on its own.
    standards_attached: List[str] = Field(default_factory=list)

    # Numeric coverage: fraction of request content tokens that were
    # mirrored into the inferred summary or a criterion.  1.0 means
    # nothing was dropped; values < ~0.5 are a strong "review me" signal.
    request_token_coverage: float = Field(..., ge=0.0, le=1.0)

    @property
    def has_divergences(self) -> bool:
        """True iff the reviewer should pay extra attention to this panel."""
        return bool(
            self.assumed_dimensions
            or self.unaddressed_request_terms
            or self.added_by_inference
        )


def compute_inference_delta(
    request: Request,
    spec: IntentSpec,
    picks: Sequence[DelegatedPick],
) -> RequestVsInference:
    """Compute the request-vs-inference delta.

    The computation is intentionally simple but **not a placeholder**:

    * ``assumed_dimensions`` is built from the spec's ambiguity vector,
      pairing each ambiguity item with its delegated pick (when one
      exists) or marking it ``<unresolved>``.
    * ``added_by_inference`` lists every acceptance-criterion
      description and soft preference whose lower-cased content tokens
      do not all appear in the request.
    * ``standards_attached`` extracts ``standard_id`` values from any
      criterion's :attr:`check_spec`.
    * ``unaddressed_request_terms`` is the set difference between the
      request's content tokens and the union of (summary + criterion
      descriptions + preferences) tokens.
    * ``request_token_coverage`` is ``|covered| / |request_tokens|``,
      defaulting to 1.0 for the degenerate empty-request case.
    """
    request_tokens = _content_tokens(request.text)
    request_token_set = set(request_tokens)

    # -------- assumed_dimensions ------------------------------------
    pick_by_item: Dict[str, DelegatedPick] = {p.ambiguity_item: p for p in picks}
    assumed: List[str] = []
    for item in spec.ambiguity.items:
        p = pick_by_item.get(item)
        if p is not None:
            assumed.append(
                f"{item} := {p.chosen_answer} ({p.rationale})"
            )
        else:
            assumed.append(f"{item} := <unresolved — HITL required>")

    # Handle picks for items NOT in the ambiguity vector (defensive).
    seen_items = {p.ambiguity_item for p in picks if p.ambiguity_item in spec.ambiguity.items}
    for p in picks:
        if p.ambiguity_item in seen_items:
            continue
        assumed.append(f"{p.ambiguity_item} := {p.chosen_answer} ({p.rationale})")

    # -------- inferred-content vs request-content ------------------
    inferred_strings: List[str] = [spec.summary]
    inferred_strings.extend(c.description for c in spec.acceptance_criteria)
    inferred_strings.extend(spec.soft_preferences)
    inferred_token_set = {
        t for s in inferred_strings for t in _content_tokens(s)
    }

    # -------- added_by_inference -----------------------------------
    added: List[str] = []
    for crit in spec.acceptance_criteria:
        crit_tokens = set(_content_tokens(crit.description))
        # If at least half the criterion's content tokens are absent
        # from the request, mark it as Murphy-added rather than
        # echoing the user.  Keeps the panel focused on real
        # additions instead of trivial overlaps.
        if crit_tokens and len(crit_tokens - request_token_set) >= max(
            1, len(crit_tokens) // 2
        ):
            added.append(f"criterion: {crit.description}")
    for pref in spec.soft_preferences:
        pref_tokens = set(_content_tokens(pref))
        if pref_tokens and len(pref_tokens - request_token_set) >= max(
            1, len(pref_tokens) // 2
        ):
            added.append(f"preference: {pref}")

    # -------- standards_attached -----------------------------------
    standards: List[str] = []
    seen_standards = set()
    for crit in spec.acceptance_criteria:
        sid = crit.check_spec.get("standard_id") if isinstance(crit.check_spec, dict) else None
        if sid and sid not in seen_standards:
            seen_standards.add(sid)
            standards.append(sid)

    # -------- unaddressed_request_terms ----------------------------
    # Preserve original ordering / dedupe.
    seen_terms: set = set()
    unaddressed: List[str] = []
    for tok in request_tokens:
        if tok in inferred_token_set or tok in seen_terms:
            continue
        seen_terms.add(tok)
        unaddressed.append(tok)

    # -------- coverage ratio ---------------------------------------
    if not request_token_set:
        coverage = 1.0
    else:
        covered = len(request_token_set & inferred_token_set)
        coverage = covered / len(request_token_set)

    return RequestVsInference(
        original_request=request.text,
        inferred_summary=spec.summary,
        inferred_deliverable_type=spec.deliverable_type.value,
        inferred_confidence=spec.confidence,
        assumed_dimensions=assumed,
        unaddressed_request_terms=unaddressed,
        added_by_inference=added,
        standards_attached=standards,
        request_token_coverage=round(coverage, 4),
    )


# ---------------------------------------------------------------------------
# AIRecommendationFraming value object
# ---------------------------------------------------------------------------


class AIRecommendationFraming(_ReconBase):
    """The framing block every Murphy deliverable must surface.

    Treat the disclosure as a black-box warning: callers may *reword*
    it by constructing a custom instance, but the field is constrained
    ``min_length=1`` so it can never be silently empty.  The builder
    :func:`build_framing` always populates a non-empty disclosure
    appropriate to the confidence band.
    """

    disclosure: str = Field(..., min_length=1)
    confidence_band: ConfidenceBand
    validation_call_to_action: str = Field(..., min_length=1)
    assumptions: List[DelegatedPick] = Field(default_factory=list)
    open_questions: List[ClarifyingQuestion] = Field(default_factory=list)
    suggested_validation_steps: List[str] = Field(default_factory=list)
    request_vs_inference: RequestVsInference

    @field_validator("disclosure")
    @classmethod
    def _disclosure_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "AIRecommendationFraming.disclosure is mandatory and "
                "cannot be empty (FDA-style black-box rule)."
            )
        return v

    # ------------------------------------------------------------------
    # Renderer helpers — pure formatting, no side effects.
    # ------------------------------------------------------------------

    def render_assumptions_panel(self) -> str:
        """Markdown-friendly list of every Murphy-made assumption.

        Returns the canonical "(none — request was fully specified)"
        when there are no picks; this is intentional, so renderers
        always emit *some* assumptions section rather than silently
        dropping it.
        """
        if not self.assumptions:
            return (
                "## Assumptions\n"
                "_(none — request was fully specified, or no delegation "
                "was granted)_"
            )
        lines = ["## Assumptions"]
        for p in self.assumptions:
            lines.append(
                f"- **{p.ambiguity_item}** → {p.chosen_answer}  \n"
                f"  _why: {p.rationale}_"
            )
        return "\n".join(lines)

    def render_validation_steps(self) -> str:
        """Markdown checklist of HITL validation steps.

        Always non-empty: when no per-dimension steps were generated
        (e.g. high-confidence path) we still emit the catch-all
        "Confirm the inferred deliverable matches your intent" step
        so the section is structurally never blank.
        """
        steps = list(self.suggested_validation_steps) or [
            "Confirm the inferred deliverable matches your intent.",
        ]
        lines = ["## HITL validation checklist"]
        for s in steps:
            lines.append(f"- [ ] {s}")
        return "\n".join(lines)

    def render_request_vs_inference(self) -> str:
        """Markdown-friendly request ↔ inference delta panel.

        Always emitted, even when ``has_divergences`` is False — in
        that case the panel reads "no divergences" so the reviewer
        knows the check ran.
        """
        rvi = self.request_vs_inference
        lines = [
            "## Request vs. inference",
            f"- **You asked:** {rvi.original_request}",
            f"- **I inferred:** {rvi.inferred_summary} "
            f"_(as {rvi.inferred_deliverable_type}, "
            f"confidence={rvi.inferred_confidence:.2f})_",
            f"- **Request token coverage:** "
            f"{rvi.request_token_coverage:.0%}",
        ]
        if rvi.assumed_dimensions:
            lines.append("- **Dimensions I assumed:**")
            for a in rvi.assumed_dimensions:
                lines.append(f"  - {a}")
        if rvi.unaddressed_request_terms:
            lines.append(
                "- **Request terms I did NOT address:** "
                + ", ".join(f"`{t}`" for t in rvi.unaddressed_request_terms)
            )
        if rvi.added_by_inference:
            lines.append("- **Constraints I added on my own:**")
            for a in rvi.added_by_inference:
                lines.append(f"  - {a}")
        if rvi.standards_attached:
            lines.append(
                "- **Best-practice standards attached:** "
                + ", ".join(rvi.standards_attached)
            )
        if not rvi.has_divergences:
            lines.append(
                "- _No structural divergences detected — your request "
                "matches my inference closely._"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Confidence-band derivation
# ---------------------------------------------------------------------------

# Beyond this many ambiguity items the band drops to LOW even if the
# rest of the signals look fine; many unresolved dimensions are by
# themselves a strong "stop and validate" signal.
_AMBIGUITY_LOW_THRESHOLD = 3


def _derive_band(
    spec: IntentSpec,
    delegation_granted: bool,
    mss_trace: Dict[str, Any],
) -> ConfidenceBand:
    """Map the structured signals to a three-tier confidence band.

    Rules (first match wins):

    * **LOW** — MSS recommended ``clarify``/``block``, OR more than
      :data:`_AMBIGUITY_LOW_THRESHOLD` ambiguity items, OR the spec's
      own confidence is below 0.4.
    * **MEDIUM** — any unresolved ambiguity remains, OR delegation
      was granted, OR the spec's confidence is below 0.8.
    * **HIGH** — none of the above (low ambiguity, no delegation, no
      MSS warning, high confidence).

    The thresholds match the existing extractor's behaviour: a clear
    request gets ``confidence >= 0.9`` and an empty ambiguity vector,
    so it lands cleanly on HIGH.
    """
    recommendation = (mss_trace or {}).get("recommendation")
    n_ambiguity = len(spec.ambiguity.items)

    if (
        recommendation in {"clarify", "block"}
        or n_ambiguity > _AMBIGUITY_LOW_THRESHOLD
        or spec.confidence < 0.4
    ):
        return ConfidenceBand.LOW
    if n_ambiguity > 0 or delegation_granted or spec.confidence < 0.8:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.HIGH


def _disclosure_for(band: ConfidenceBand, n_assumptions: int) -> str:
    if band == ConfidenceBand.HIGH:
        return _DISCLOSURE_HIGH.format(n=n_assumptions)
    if band == ConfidenceBand.MEDIUM:
        return _DISCLOSURE_MEDIUM
    return _DISCLOSURE_LOW


def _cta_for(band: ConfidenceBand) -> str:
    if band == ConfidenceBand.HIGH:
        return _CTA_HIGH
    if band == ConfidenceBand.MEDIUM:
        return _CTA_MEDIUM
    return _CTA_LOW


def _validation_steps_for(
    spec: IntentSpec,
    picks: Sequence[DelegatedPick],
    delegation_granted: bool,
    mss_trace: Dict[str, Any],
) -> List[str]:
    """Build one validation step per still-unresolved ambiguity dimension.

    "Still-unresolved" means: present in the ambiguity vector AND
    either (a) delegation was not granted (so no pick exists), or
    (b) a pick exists but the rationale is the free-text fallback.
    """
    pick_by_item: Dict[str, DelegatedPick] = {p.ambiguity_item: p for p in picks}
    steps: List[str] = []
    for item in spec.ambiguity.items:
        p = pick_by_item.get(item)
        if p is None:
            if delegation_granted:
                steps.append(
                    f"Resolve **{item}** — delegation was granted but no "
                    "concrete question was synthesized for this dimension; "
                    "confirm what you want."
                )
            else:
                steps.append(
                    f"Resolve **{item}** — Murphy did not pick (no delegation)."
                )
        elif "fallback" in p.rationale.lower():
            steps.append(
                f"Confirm **{item}**: Murphy fell back to "
                f"`{p.chosen_answer}` because no concrete options were "
                "available."
            )
        else:
            steps.append(
                f"Validate **{item}** — Murphy chose `{p.chosen_answer}` "
                f"({p.rationale}); override if wrong."
            )
    # MSS-driven catch-all step.
    if (mss_trace or {}).get("recommendation") in {"clarify", "block"}:
        steps.append(
            "MSS pre-pass flagged the request as needing clarification; "
            "double-check the inferred summary before acting."
        )
    return steps


def build_framing(
    request: Request,
    spec: IntentSpec,
    delegation_granted: bool,
    picks: Sequence[DelegatedPick],
    mss_trace: Optional[Dict[str, Any]] = None,
) -> AIRecommendationFraming:
    """Deterministic builder called from :class:`IntentExtractor.extract`.

    Always returns a fully-populated framing.  The disclosure is
    selected from the appropriate confidence-band template; the
    request-vs-inference panel is computed via
    :func:`compute_inference_delta`.
    """
    mss = mss_trace or {}
    band = _derive_band(spec, delegation_granted, mss)
    rvi = compute_inference_delta(request, spec, picks)
    return AIRecommendationFraming(
        disclosure=_disclosure_for(band, len(picks)),
        confidence_band=band,
        validation_call_to_action=_cta_for(band),
        assumptions=list(picks),
        open_questions=list(spec.clarifying_questions),
        suggested_validation_steps=_validation_steps_for(
            spec, picks, delegation_granted, mss
        ),
        request_vs_inference=rvi,
    )


# ---------------------------------------------------------------------------
# BaseDeliverableRenderer — the contract every generator must extend
# ---------------------------------------------------------------------------


class BaseDeliverableRenderer:
    """Final-template wrapper that makes the framing structurally unavoidable.

    Subclasses override :meth:`_render_body` only.  The public
    :meth:`render` is **final** — it composes::

        disclosure
        + call-to-action
        + body          (subclass-supplied)
        + assumptions panel
        + validation checklist
        + request-vs-inference panel

    Subclasses that try to override :meth:`render` will trigger a
    ``TypeError`` at class-definition time via
    :meth:`__init_subclass__`, mirroring how the pydantic models
    forbid extra fields.

    A renderer is invoked as::

        out = MyRenderer().render(spec)        # framing taken from spec
        out = MyRenderer().render(spec, framing=custom)  # explicit override
    """

    #: Set by :meth:`__init_subclass__`; used by the universal-framing
    #: test to walk every concrete renderer in the package.
    _registry: List[type] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Forbid override of the wrapper.
        if "render" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must not override render(); override "
                "_render_body() instead."
            )
        # Track every concrete subclass so the universal-framing test
        # can iterate them.  Abstract intermediate classes can opt out
        # by setting ``_abstract = True`` in their body.
        if not cls.__dict__.get("_abstract", False):
            BaseDeliverableRenderer._registry.append(cls)

    # ------------------------------------------------------------------
    # Public — final
    # ------------------------------------------------------------------

    def render(
        self,
        spec: IntentSpec,
        *,
        framing: Optional[AIRecommendationFraming] = None,
        body_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compose disclosure + body + assumptions + validation + delta.

        :param spec: the :class:`IntentSpec` whose framing is rendered.
        :param framing: explicit framing override; defaults to
            ``spec.framing``.  Raises :class:`ValueError` if neither is
            available — refusing to render rather than silently dropping
            the disclosure is the whole point.
        :param body_context: free-form dict passed through to
            :meth:`_render_body` for subclass use.
        """
        chosen = framing or getattr(spec, "framing", None)
        if chosen is None:
            raise ValueError(
                "BaseDeliverableRenderer.render requires a framing — "
                "either pass framing=... or use a spec produced by "
                "IntentExtractor (which auto-attaches one)."
            )
        body = self._render_body(spec, body_context or {})
        return "\n\n".join(
            [
                chosen.disclosure,
                f"_{chosen.validation_call_to_action}_",
                body,
                chosen.render_assumptions_panel(),
                chosen.render_validation_steps(),
                chosen.render_request_vs_inference(),
            ]
        )

    # ------------------------------------------------------------------
    # Subclass hook
    # ------------------------------------------------------------------

    def _render_body(
        self, spec: IntentSpec, context: Dict[str, Any]
    ) -> str:
        """Override in subclasses to render the deliverable-specific body.

        The default implementation returns the spec's summary so that
        a bare :class:`BaseDeliverableRenderer` instance is still
        useful in tests / smoke checks.
        """
        return f"## Deliverable\n{spec.summary}"


__all__ = [
    "AIRecommendationFraming",
    "BaseDeliverableRenderer",
    "ConfidenceBand",
    "RequestVsInference",
    "build_framing",
    "compute_inference_delta",
]
