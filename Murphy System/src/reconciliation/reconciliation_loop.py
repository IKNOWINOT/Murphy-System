"""
Reconciliation loop controller.

State machine::

      ┌─────────────────────────┐
      ▼                         │
    extract_intent → generate → evaluate ──pass──▶ DONE
                                  │
                                  ├──no improvement / no patch──▶ DONE
                                  ▼
                            synthesize_patch ──── apply ──┐
                                                          │
                              (re-evaluate next iteration)│
                                                          ◀──┘

The loop is bounded by :class:`LoopBudget`.  It honours the feature
flags: when ``observe_only`` is set it scores once and returns without
patching.  When the request is too vague to satisfy automatically, it
emits :class:`ClarifyingQuestion` records instead of guessing forever.

Design label: RECON-LOOP-001
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Sequence

from .feature_flags import FeatureFlags, current_flags
from .models import (
    AmbiguityVector,
    ClarifyingQuestion,
    Deliverable,
    IntentSpec,
    LoopBudget,
    LoopIteration,
    LoopOutcome,
    LoopTerminationReason,
    Patch,
    PatchKind,
    ReconciliationScore,
    Request,
)
from .output_evaluator import OutputEvaluator
from .patch_synthesizer import PatchSynthesizer
from .request_intent import IntentExtractor

logger = logging.getLogger(__name__)


# Type aliases for the dependency-injected callables.
GeneratorFn = Callable[[Request, IntentSpec, Sequence[Patch]], Deliverable]
"""Produces a :class:`Deliverable` for *request* given the current
*intent* and any patches accumulated so far."""

OutcomeSink = Callable[[LoopOutcome], None]
"""Called once per loop run with the final :class:`LoopOutcome`.
Used by :mod:`learning_hooks` to feed the learning engine."""


class ReconciliationLoop:
    """Bounded controller for the reconciliation state machine."""

    # Soft-score gain below this is considered "no improvement".
    _IMPROVEMENT_EPSILON: float = 1e-3

    def __init__(
        self,
        intent_extractor: Optional[IntentExtractor] = None,
        output_evaluator: Optional[OutputEvaluator] = None,
        patch_synthesizer: Optional[PatchSynthesizer] = None,
        flags: Optional[FeatureFlags] = None,
        outcome_sink: Optional[OutcomeSink] = None,
    ) -> None:
        self._intent = intent_extractor or IntentExtractor()
        self._evaluator = output_evaluator or OutputEvaluator()
        self._patches = patch_synthesizer or PatchSynthesizer(flags=flags)
        self._flags = flags or current_flags()
        self._outcome_sink = outcome_sink

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        request: Request,
        generator: GeneratorFn,
        budget: Optional[LoopBudget] = None,
    ) -> LoopOutcome:
        """Execute the reconciliation loop for *request*.

        Args:
            request: The request being reconciled.
            generator: Callable that produces a deliverable given the
                request, the chosen intent spec, and the list of patches
                accumulated so far.  This is the integration seam with
                Murphy's existing generator pipeline.
            budget: Optional override for the default :class:`LoopBudget`.

        Returns:
            A :class:`LoopOutcome` describing the run, even when the
            subsystem is disabled by feature flag.
        """
        budget = budget or LoopBudget()
        deadline = time.monotonic() + budget.max_wallclock_seconds

        if not self._flags.enabled:
            return self._disabled_outcome(request, generator, budget)

        intents = self._intent.extract(request)
        if not intents:
            # Should never happen — extractor always returns >= 1.
            raise RuntimeError("IntentExtractor returned no candidates")

        # Pick the highest-confidence intent for the primary loop; the
        # remainder are tracked for the clarifying-question artifact.
        intents.sort(key=lambda s: s.confidence, reverse=True)
        primary = intents[0]
        alternatives = intents[1:]

        deliverable = generator(request, primary, ())
        score = self._evaluator.score(deliverable, primary)
        iterations: List[LoopIteration] = [
            LoopIteration(index=0, score=score, applied_patch=None, duration_seconds=0.0)
        ]

        # Observe-only mode: never patch, just record.
        if self._flags.observe_only or not self._flags.any_patching_allowed:
            outcome = self._finalise(
                request,
                primary,
                deliverable,
                iterations,
                LoopTerminationReason.PASSED if score.acceptable else LoopTerminationReason.DISABLED_BY_FEATURE_FLAG,
                clarifying_questions=self._maybe_clarify(primary, alternatives, score),
            )
            self._emit(outcome)
            return outcome

        # Active loop: try to converge on an acceptable score.
        best_score = score
        no_improvement = 0
        applied_patches: List[Patch] = []

        for index in range(1, budget.max_iterations + 1):
            if score.acceptable:
                break
            if time.monotonic() > deadline:
                outcome = self._finalise(
                    request,
                    primary,
                    deliverable,
                    iterations,
                    LoopTerminationReason.BUDGET_EXHAUSTED,
                )
                self._emit(outcome)
                return outcome

            patches = self._patches.synthesize(primary, score.diagnoses)
            patches = [p for p in patches if p.kind != PatchKind.NOOP]
            if not patches:
                outcome = self._finalise(
                    request,
                    primary,
                    deliverable,
                    iterations,
                    LoopTerminationReason.PATCH_SYNTHESIS_FAILED,
                    clarifying_questions=self._maybe_clarify(primary, alternatives, score),
                )
                self._emit(outcome)
                return outcome

            # Apply: feed accumulated patches to the generator.
            applied_patches.extend(patches)
            chosen_patch = patches[0]
            t0 = time.monotonic()
            deliverable = generator(request, primary, tuple(applied_patches))
            score = self._evaluator.score(deliverable, primary)
            iterations.append(
                LoopIteration(
                    index=index,
                    score=score,
                    applied_patch=chosen_patch,
                    duration_seconds=time.monotonic() - t0,
                )
            )

            if score.soft_score > best_score.soft_score + self._IMPROVEMENT_EPSILON:
                best_score = score
                no_improvement = 0
            else:
                no_improvement += 1
                if no_improvement >= budget.no_improvement_patience:
                    outcome = self._finalise(
                        request,
                        primary,
                        deliverable,
                        iterations,
                        LoopTerminationReason.NO_IMPROVEMENT,
                        clarifying_questions=self._maybe_clarify(primary, alternatives, score),
                    )
                    self._emit(outcome)
                    return outcome

        if score.acceptable:
            reason = LoopTerminationReason.PASSED
        else:
            reason = LoopTerminationReason.MAX_ITERATIONS

        outcome = self._finalise(
            request,
            primary,
            deliverable,
            iterations,
            reason,
            clarifying_questions=(
                self._maybe_clarify(primary, alternatives, score)
                if reason != LoopTerminationReason.PASSED
                else []
            ),
        )
        self._emit(outcome)
        return outcome

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _disabled_outcome(
        self,
        request: Request,
        generator: GeneratorFn,
        budget: LoopBudget,
    ) -> LoopOutcome:
        """Produce an outcome when the subsystem is disabled."""
        intents = self._intent.extract(request)
        primary = intents[0]
        deliverable = generator(request, primary, ())
        outcome = LoopOutcome(
            request_id=request.id,
            intent_id=primary.id,
            deliverable_id=deliverable.id,
            termination_reason=LoopTerminationReason.DISABLED_BY_FEATURE_FLAG,
            iterations=[],
            final_score=None,
            finished_at=datetime.now(timezone.utc),
        )
        self._emit(outcome)
        return outcome

    def _finalise(
        self,
        request: Request,
        intent: IntentSpec,
        deliverable: Deliverable,
        iterations: List[LoopIteration],
        reason: LoopTerminationReason,
        clarifying_questions: Optional[List[ClarifyingQuestion]] = None,
    ) -> LoopOutcome:
        final_score = iterations[-1].score if iterations else None
        return LoopOutcome(
            request_id=request.id,
            intent_id=intent.id,
            deliverable_id=deliverable.id,
            termination_reason=reason,
            iterations=iterations,
            final_score=final_score,
            clarifying_questions=clarifying_questions or [],
            finished_at=datetime.now(timezone.utc),
        )

    def _maybe_clarify(
        self,
        primary: IntentSpec,
        alternatives: Sequence[IntentSpec],
        score: ReconciliationScore,
    ) -> List[ClarifyingQuestion]:
        """Emit one targeted question per unresolved ambiguity dimension.

        Only emitted when the deliverable failed to clear the acceptance
        bar AND the primary intent still carries ambiguity.  Alternative
        intent summaries are surfaced as candidate answers so the user
        can disambiguate with a single click in the HITL UI.
        """
        if score.acceptable:
            return []
        ambiguity: AmbiguityVector = primary.ambiguity
        if not ambiguity.is_ambiguous:
            return []

        candidate_answers = [alt.summary for alt in alternatives if alt.summary]
        return [
            ClarifyingQuestion(
                question=f"Could you specify the intended {item}?",
                ambiguity_item=item,
                candidate_answers=candidate_answers,
            )
            for item in ambiguity.items
        ]

    def _emit(self, outcome: LoopOutcome) -> None:
        if self._outcome_sink is None:
            return
        try:
            self._outcome_sink(outcome)
        except Exception:  # pragma: no cover — sinks must never break the loop
            logger.exception("Outcome sink raised — ignoring")


__all__ = [
    "ReconciliationLoop",
    "GeneratorFn",
    "OutcomeSink",
]
