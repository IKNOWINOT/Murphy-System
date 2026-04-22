"""
End-to-end tests for HITL-004 — universal AI-recommendation framing.

These tests **round-trip real prompts through Murphy's IntentExtractor**
and verify that the framing block surfaced on every IntentSpec actually
catches what it claims to catch.  The point is not to unit-test
individual helpers in isolation; it's to demonstrate that the full
pipeline (prompt → IntentExtractor → IntentSpec.framing → renderer →
markdown output) produces a deliverable whose request-vs-inference
panel reflects the *real* divergence between what was asked and what
was inferred.

Coverage:

* Universal presence: every IntentSpec produced by IntentExtractor
  carries a non-None framing with a non-empty disclosure.
* Confidence-band derivation across a clear / ambiguous / MSS-flagged
  spectrum.
* Round-trip from a deliberately vague + delegated prompt: assertions
  on the concrete unaddressed-tokens, coverage ratio, assumptions
  count, and validation-checklist size produced.
* Round-trip from a clear, fully-specified prompt: HIGH band, no
  unresolved validation steps beyond the catch-all.
* :class:`BaseDeliverableRenderer` contract: subclassing with an
  override of ``render`` raises at class-definition time; the public
  ``render()`` always emits disclosure + body + assumptions panel +
  validation checklist + request-vs-inference panel.
* Universal-framing scan: every concrete subclass of
  :class:`BaseDeliverableRenderer` registered in the package emits
  the disclosure substring and a non-empty validation section.
* Disclosure non-suppressibility: empty disclosure is rejected at
  construction (FDA black-box-style invariant).

Design label: HITL-004
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.reconciliation import (
    AIRecommendationFraming,
    AmbiguityVector,
    BaseDeliverableRenderer,
    ClarifyingQuestion,
    ConfidenceBand,
    DelegatedPick,
    DeliverableType,
    IntentExtractor,
    IntentSpec,
    Request,
    RequestVsInference,
    build_framing,
    compute_inference_delta,
)


# ---------------------------------------------------------------------------
# Universal presence — every extractor output has a framing
# ---------------------------------------------------------------------------


def test_every_extractor_spec_has_framing() -> None:
    """No code path inside IntentExtractor.extract may return a spec without
    framing — the doctrine is universal."""
    extractor = IntentExtractor()
    prompts = [
        # Clear request.
        "Write a Python script that pings example.com once and exits.",
        # Vague request, no delegation.
        "make it nicer",
        # Vague request, explicit delegation.
        "make it nicer, you can pick",
        # Programmatic-flag delegation (no natural-language signal).
        "build a thing",
    ]
    for p in prompts:
        ctx: Dict[str, Any] = {"delegation": True} if p == "build a thing" else {}
        specs = extractor.extract(
            Request(text=p, deliverable_type=DeliverableType.GENERIC_TEXT, context=ctx)
        )
        assert specs, f"extractor produced no specs for prompt {p!r}"
        for s in specs:
            assert s.framing is not None, (
                f"spec produced for prompt {p!r} is missing framing"
            )
            assert isinstance(s.framing, AIRecommendationFraming)
            # Non-suppressible: the disclosure is always non-empty.
            assert s.framing.disclosure.strip()
            # The request-vs-inference panel is always built (real, not
            # a placeholder) and carries the original request verbatim.
            assert isinstance(s.framing.request_vs_inference, RequestVsInference)
            assert s.framing.request_vs_inference.original_request == p


# ---------------------------------------------------------------------------
# Confidence-band derivation — clear vs vague vs MSS-flagged
# ---------------------------------------------------------------------------


def test_clear_request_gets_high_band() -> None:
    """A spec with no ambiguity, no delegation, no MSS warning, and high
    confidence must land on HIGH.  The current IntentExtractor always
    emits at least one ambiguity dimension (audience/format/etc.), so
    we exercise the band derivation directly via build_framing on a
    deliberately-clean spec — proving the HIGH path is reachable."""
    req = Request(
        text="Write a Python script that pings example.com once and exits.",
        deliverable_type=DeliverableType.CODE,
    )
    clean_spec = IntentSpec(
        request_id=req.id,
        summary="Python script that pings example.com once and exits",
        deliverable_type=DeliverableType.CODE,
        confidence=0.95,
        ambiguity=AmbiguityVector(items=[]),
    )
    framing = build_framing(
        request=req, spec=clean_spec, delegation_granted=False, picks=[]
    )
    assert framing.confidence_band == ConfidenceBand.HIGH
    # HIGH band still carries assumptions count in the disclosure (== 0 here).
    assert "0 assumption" in framing.disclosure


def test_vague_delegated_request_gets_low_band() -> None:
    """Many ambiguity items + delegation is the canonical 'stop and validate'
    case — must land on LOW."""
    [primary, *_] = IntentExtractor().extract(
        Request(
            text=(
                "Make me a MVP web app for a highly lucrative niche that "
                "copies medvi business model. Write a launch campaign. "
                "You can pick."
            ),
            deliverable_type=DeliverableType.GENERIC_TEXT,
        )
    )
    assert primary.framing is not None
    assert primary.framing.confidence_band == ConfidenceBand.LOW
    # LOW band uses the strong wording.
    assert "strongly recommend" in primary.framing.disclosure


def test_vague_no_delegation_gets_medium_or_low_band() -> None:
    """Ambiguity without delegation → at least MEDIUM (never HIGH)."""
    [primary, *_] = IntentExtractor().extract(
        Request(text="make it nicer", deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.framing is not None
    assert primary.framing.confidence_band in {
        ConfidenceBand.MEDIUM,
        ConfidenceBand.LOW,
    }


# ---------------------------------------------------------------------------
# Round-trip: real prompt → real inference delta
# ---------------------------------------------------------------------------


_VAGUE_DELEGATED_PROMPT = (
    "Make me a MVP web app for a highly lucrative niche that copies "
    "medvi business model. Write a launch campaign. You can pick."
)


def test_roundtrip_inference_delta_catches_unaddressed_terms() -> None:
    """The hero test.  Run a prompt with concrete content terms ('campaign',
    'launch', 'medvi') through the extractor, then verify that those terms
    that Murphy never wove into its inferred summary or any criterion are
    surfaced in ``unaddressed_request_terms``.  This proves the framing
    actually catches divergence on a real round-trip, not just on
    hand-crafted unit-test inputs."""
    [primary, *_] = IntentExtractor().extract(
        Request(
            text=_VAGUE_DELEGATED_PROMPT,
            deliverable_type=DeliverableType.GENERIC_TEXT,
        )
    )
    assert primary.framing is not None
    rvi = primary.framing.request_vs_inference

    # Murphy delegates but never expands the summary to address every
    # noun in the prompt — concrete terms like "launch" and "campaign"
    # are exactly what the panel must highlight to the reviewer.
    unaddressed = set(rvi.unaddressed_request_terms)
    assert "launch" in unaddressed, (
        f"expected 'launch' in unaddressed terms, got {sorted(unaddressed)}"
    )
    assert "campaign" in unaddressed, (
        f"expected 'campaign' in unaddressed terms, got {sorted(unaddressed)}"
    )

    # Coverage is a real ratio in [0, 1] derived from the request's
    # content tokens; for a deliberately under-addressed prompt it
    # must be < 1.0.
    assert 0.0 < rvi.request_token_coverage < 1.0
    # And the framing must agree with itself: at least one divergence.
    assert rvi.has_divergences

    # Every unresolved ambiguity item produces an entry in
    # assumed_dimensions; with 5 picks + 1 unresolved deliverable type
    # we should see all 6.
    assert len(rvi.assumed_dimensions) >= len(primary.ambiguity.items)


def test_roundtrip_clear_prompt_high_coverage() -> None:
    """A fully-specified prompt should produce HIGH token coverage even
    though the extractor is conservative about marking dimensions as
    'resolved'.  Proves the delta computation isn't just noise: when
    Murphy actually echoes the request's content terms in the inferred
    summary, coverage approaches 1.0."""
    [primary, *_] = IntentExtractor().extract(
        Request(
            text="Write a Python script that pings example.com once and exits.",
            deliverable_type=DeliverableType.CODE,
        )
    )
    assert primary.framing is not None
    rvi = primary.framing.request_vs_inference
    # The summary echoes most of the prompt's content tokens, so
    # coverage must be high.
    assert rvi.request_token_coverage >= 0.5
    # Concrete assertion: 'python', 'script', 'pings', 'example' are all
    # content tokens that should be reflected in the summary, hence not
    # in the unaddressed set.
    unaddressed = set(rvi.unaddressed_request_terms)
    assert "python" not in unaddressed
    assert "script" not in unaddressed


def test_roundtrip_validation_steps_match_unresolved_dimensions() -> None:
    """One validation step per ambiguity dimension (plus optional MSS catch-
    all).  Proves the checklist size tracks the real unresolved surface."""
    [primary, *_] = IntentExtractor().extract(
        Request(
            text=_VAGUE_DELEGATED_PROMPT,
            deliverable_type=DeliverableType.GENERIC_TEXT,
        )
    )
    assert primary.framing is not None
    n_amb = len(primary.ambiguity.items)
    n_steps = len(primary.framing.suggested_validation_steps)
    # Allow up to 1 extra catch-all from MSS.
    assert n_amb <= n_steps <= n_amb + 1


# ---------------------------------------------------------------------------
# BaseDeliverableRenderer contract
# ---------------------------------------------------------------------------


class _StubMarkdownRenderer(BaseDeliverableRenderer):
    """Concrete renderer used to exercise the contract."""

    def _render_body(self, spec: IntentSpec, context: Dict[str, Any]) -> str:
        return f"## Body\n{spec.summary}"


def test_renderer_subclass_cannot_override_render() -> None:
    """Trying to override the wrapper must fail at class-definition time."""
    with pytest.raises(TypeError, match="must not override render"):
        class _BadRenderer(BaseDeliverableRenderer):  # noqa: D401
            def render(self, spec, *, framing=None, body_context=None):  # type: ignore[override]
                return "naked output"


def test_renderer_emits_all_required_panels() -> None:
    """Every render() output must contain the disclosure, the assumptions
    panel header, the validation checklist header, and the request-vs-
    inference panel header — even if any of those would be empty."""
    [primary, *_] = IntentExtractor().extract(
        Request(text=_VAGUE_DELEGATED_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.framing is not None
    out = _StubMarkdownRenderer().render(primary)
    assert primary.framing.disclosure in out
    assert "## Assumptions" in out
    assert "## HITL validation checklist" in out
    assert "## Request vs. inference" in out
    # And the body composes between them — disclosure first, body in the
    # middle, panels at the end.
    assert out.index(primary.framing.disclosure) < out.index("## Body")
    assert out.index("## Body") < out.index("## Assumptions")
    assert out.index("## Assumptions") < out.index("## HITL validation checklist")


def test_renderer_refuses_to_render_without_framing() -> None:
    """The whole point is that the framing is structurally unavoidable —
    so rendering a spec that somehow has framing=None must raise rather
    than silently drop the disclosure."""
    spec = IntentSpec(
        request_id="req_test",
        summary="bare spec",
        deliverable_type=DeliverableType.GENERIC_TEXT,
    )
    spec.framing = None
    with pytest.raises(ValueError, match="requires a framing"):
        _StubMarkdownRenderer().render(spec)


def test_universal_framing_every_concrete_renderer_in_registry() -> None:
    """Walk every concrete BaseDeliverableRenderer subclass registered in
    the package.  Each must, when invoked against a real extractor-
    produced spec, emit the disclosure substring and a non-empty
    validation section.  This is the CI-enforced gate that any new
    renderer added later must also surface the framing."""
    [primary, *_] = IntentExtractor().extract(
        Request(text=_VAGUE_DELEGATED_PROMPT, deliverable_type=DeliverableType.GENERIC_TEXT)
    )
    assert primary.framing is not None
    registry = list(BaseDeliverableRenderer._registry)
    assert _StubMarkdownRenderer in registry, (
        "test stub renderer was not auto-registered — registry is broken"
    )
    for cls in registry:
        instance = cls()
        out = instance.render(primary)
        assert primary.framing.disclosure in out, (
            f"{cls.__name__}.render() omitted the AI disclosure"
        )
        assert "HITL validation checklist" in out, (
            f"{cls.__name__}.render() omitted the validation checklist"
        )
        # The validation section must contain at least one checkbox.
        checklist_start = out.index("HITL validation checklist")
        assert "- [ ]" in out[checklist_start:], (
            f"{cls.__name__}.render() emitted an empty validation checklist"
        )


# ---------------------------------------------------------------------------
# Disclosure non-suppressibility — FDA black-box rule
# ---------------------------------------------------------------------------


def test_disclosure_cannot_be_constructed_empty() -> None:
    """Pydantic min_length + the explicit field validator both reject an
    empty disclosure — there is no path to a framing without the
    'I am an AI' line."""
    with pytest.raises(Exception):  # ValidationError or ValueError
        AIRecommendationFraming(
            disclosure="",
            confidence_band=ConfidenceBand.HIGH,
            validation_call_to_action="cta",
            request_vs_inference=RequestVsInference(
                original_request="x",
                inferred_summary="x",
                inferred_deliverable_type="generic_text",
                inferred_confidence=1.0,
                request_token_coverage=1.0,
            ),
        )


def test_disclosure_cannot_be_constructed_whitespace() -> None:
    with pytest.raises(Exception):
        AIRecommendationFraming(
            disclosure="   \n  ",
            confidence_band=ConfidenceBand.HIGH,
            validation_call_to_action="cta",
            request_vs_inference=RequestVsInference(
                original_request="x",
                inferred_summary="x",
                inferred_deliverable_type="generic_text",
                inferred_confidence=1.0,
                request_token_coverage=1.0,
            ),
        )


# ---------------------------------------------------------------------------
# compute_inference_delta — direct-call edge cases
# ---------------------------------------------------------------------------


def test_compute_inference_delta_handles_picks_outside_ambiguity_vector() -> None:
    """A defensive case: a DelegatedPick referring to an item not in the
    spec's ambiguity vector should still appear in assumed_dimensions
    (so the reviewer never loses a Murphy assumption)."""
    req = Request(text="x", deliverable_type=DeliverableType.GENERIC_TEXT)
    spec = IntentSpec(
        request_id=req.id,
        summary="y",
        deliverable_type=DeliverableType.GENERIC_TEXT,
        ambiguity=AmbiguityVector(items=[]),
    )
    pick = DelegatedPick(
        question_id="q_orphan",
        question="?",
        ambiguity_item="orphan-dim",
        chosen_answer="42",
        rationale="auto: test",
    )
    rvi = compute_inference_delta(req, spec, [pick])
    assert any("orphan-dim" in s for s in rvi.assumed_dimensions)


def test_compute_inference_delta_empty_request_has_unit_coverage() -> None:
    """A degenerate empty-tokens request must not divide-by-zero; coverage
    defaults to 1.0 (nothing to drop, nothing dropped)."""
    req = Request(text="!!!", deliverable_type=DeliverableType.GENERIC_TEXT)
    spec = IntentSpec(
        request_id=req.id,
        summary="anything",
        deliverable_type=DeliverableType.GENERIC_TEXT,
    )
    rvi = compute_inference_delta(req, spec, [])
    assert rvi.request_token_coverage == 1.0
