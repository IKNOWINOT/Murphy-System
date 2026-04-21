"""
Evaluator base class, protocol, and registry.

Each concrete evaluator is registered against one or more
:class:`DeliverableType` values.  The base
:class:`DeterministicEvaluator` is the default — it just walks the
deliverable's standards-derived criteria — and individual subclasses
override hooks to add type-specific deterministic and behavioural
checks.

Design label: RECON-EVAL-BASE-001
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from ..models import (
    AcceptanceCriterion,
    CriterionKind,
    CriterionResult,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    IntentSpec,
    PatchKind,
)
from ..standards import evaluate_check

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context passed to every evaluator
# ---------------------------------------------------------------------------


@dataclass
class EvaluationContext:
    """Optional knobs an evaluator may consult."""

    llm_judge: Optional[Callable[[str, Any], Tuple[float, str]]] = None
    """Callable ``(rubric, content) -> (score, detail)``.  Optional."""

    semantic_similarity: Optional[Callable[[str, str], float]] = None
    """Callable ``(a, b) -> similarity in [0, 1]``.  Optional."""

    behavioural_runner: Optional[Callable[[Deliverable], Tuple[bool, str]]] = None
    """Optional sandbox runner that executes the deliverable."""

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol + base
# ---------------------------------------------------------------------------


class Evaluator(Protocol):
    """A typed evaluator for a single :class:`DeliverableType`."""

    def evaluate(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: Optional[EvaluationContext] = None,
    ) -> Tuple[List[CriterionResult], List[Diagnosis]]:
        """Score *deliverable* against *intent*.

        Returns the per-criterion results and any diagnoses that
        capture failures in machine-readable form.
        """
        ...


class DeterministicEvaluator:
    """Default base implementation that walks every criterion in the intent.

    Subclasses typically override :meth:`additional_criteria` and/or
    :meth:`additional_diagnoses` to inject type-specific deterministic
    checks beyond what the standards catalog already supplied.
    """

    deliverable_types: Tuple[DeliverableType, ...] = ()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: Optional[EvaluationContext] = None,
    ) -> Tuple[List[CriterionResult], List[Diagnosis]]:
        ctx = context or EvaluationContext()
        results: List[CriterionResult] = []
        diagnoses: List[Diagnosis] = []

        for criterion in self._all_criteria(deliverable, intent):
            result = self._evaluate_criterion(criterion, deliverable, intent, ctx)
            results.append(result)
            if not result.passed:
                diagnoses.append(self._diagnose(criterion, result))

        diagnoses.extend(self.additional_diagnoses(deliverable, intent, ctx))
        return results, diagnoses

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    def additional_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> Iterable[AcceptanceCriterion]:
        """Subclass hook — yield extra criteria to evaluate."""
        return ()

    def additional_diagnoses(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: EvaluationContext,
    ) -> Iterable[Diagnosis]:
        """Subclass hook — yield extra diagnoses (independent of criteria)."""
        return ()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _all_criteria(
        self,
        deliverable: Deliverable,
        intent: IntentSpec,
    ) -> List[AcceptanceCriterion]:
        seen_ids = set()
        out: List[AcceptanceCriterion] = []
        for c in list(intent.acceptance_criteria) + list(self.additional_criteria(deliverable, intent)):
            if c.id in seen_ids:
                continue
            seen_ids.add(c.id)
            out.append(c)
        return out

    def _evaluate_criterion(
        self,
        criterion: AcceptanceCriterion,
        deliverable: Deliverable,
        intent: IntentSpec,
        context: EvaluationContext,
    ) -> CriterionResult:
        evidence: Dict[str, Any] = {}
        if criterion.kind in (CriterionKind.STANDARD, CriterionKind.DETERMINISTIC):
            passed, score, detail = evaluate_check(criterion.check_spec, deliverable.content)
        elif criterion.kind == CriterionKind.LLM_RUBRIC:
            if context.llm_judge is None:
                # Without a judge, treat unknown rubric criteria as a soft pass
                # so the absence of a configured judge cannot mask real failures
                # found by deterministic checks.
                passed, score, detail = True, 1.0, "no LLM judge configured — skipped"
            else:
                try:
                    score, detail = context.llm_judge(criterion.rubric or "", deliverable.content)
                except Exception as exc:  # pragma: no cover — defensive
                    score, detail = 0.0, f"judge raised {type(exc).__name__}: {exc}"
                score = max(0.0, min(1.0, float(score)))
                passed = score >= 0.85
        elif criterion.kind == CriterionKind.SEMANTIC:
            exemplar = criterion.check_spec.get("exemplar", "")
            if context.semantic_similarity is None or not exemplar:
                passed, score, detail = True, 1.0, "no semantic backend configured — skipped"
            else:
                try:
                    sim = float(context.semantic_similarity(str(deliverable.content), str(exemplar)))
                except Exception as exc:  # pragma: no cover — defensive
                    sim = 0.0
                    detail = f"semantic backend raised {type(exc).__name__}: {exc}"
                else:
                    detail = f"similarity={sim:.3f}"
                score = max(0.0, min(1.0, sim))
                passed = score >= 0.75
        elif criterion.kind == CriterionKind.BEHAVIOURAL:
            if context.behavioural_runner is None:
                passed, score, detail = True, 1.0, "no behavioural runner configured — skipped"
            else:
                try:
                    ok, info = context.behavioural_runner(deliverable)
                except Exception as exc:  # pragma: no cover — defensive
                    ok, info = False, f"runner raised {type(exc).__name__}: {exc}"
                passed, score, detail = ok, 1.0 if ok else 0.0, info
        else:  # pragma: no cover — exhaustiveness guard
            passed, score, detail = True, 1.0, f"unknown criterion kind {criterion.kind}"

        if criterion.check_spec.get("standard_id"):
            evidence["standard_id"] = criterion.check_spec["standard_id"]

        return CriterionResult(
            criterion_id=criterion.id,
            description=criterion.description,
            kind=criterion.kind,
            score=score,
            passed=passed,
            weight=criterion.weight,
            hard=criterion.hard,
            detail=detail,
            evidence=evidence,
        )

    @staticmethod
    def _diagnose(criterion: AcceptanceCriterion, result: CriterionResult) -> Diagnosis:
        severity = (
            DiagnosisSeverity.BLOCKER
            if criterion.hard
            else DiagnosisSeverity.MAJOR
            if result.score < 0.5
            else DiagnosisSeverity.MINOR
        )
        suggested_kind = (
            PatchKind.PROMPT_REWRITE
            if criterion.kind in {CriterionKind.LLM_RUBRIC, CriterionKind.SEMANTIC}
            else PatchKind.CONTENT_EDIT
        )
        return Diagnosis(
            criterion_id=criterion.id,
            severity=severity,
            summary=f"Criterion failed: {criterion.description} — {result.detail}",
            suggested_patch_kind=suggested_kind,
            suggested_action=(
                "Refine the prompt to explicitly require: " + criterion.description
                if suggested_kind == PatchKind.PROMPT_REWRITE
                else "Edit the deliverable to satisfy: " + criterion.description
            ),
            evidence={"criterion_kind": criterion.kind.value, "detail": result.detail},
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_REGISTRY: Dict[DeliverableType, Evaluator] = {}
_REGISTRY_LOCK = threading.RLock()


def register_evaluator(deliverable_type: DeliverableType, evaluator: Evaluator) -> None:
    """Register *evaluator* for *deliverable_type*.

    The most recent registration wins; this is intentional so deployments
    can override a built-in with a tenant-specific implementation.
    """
    with _REGISTRY_LOCK:
        _REGISTRY[deliverable_type] = evaluator


def get_evaluator(deliverable_type: DeliverableType) -> Evaluator:
    """Look up the evaluator for *deliverable_type*.

    Falls back to the generic-text evaluator for any unregistered type
    so the subsystem never refuses to score a deliverable just because
    its type catalog has not been extended.
    """
    with _REGISTRY_LOCK:
        evaluator = _REGISTRY.get(deliverable_type)
        if evaluator is not None:
            return evaluator
        fallback = _REGISTRY.get(DeliverableType.GENERIC_TEXT)
        if fallback is not None:
            return fallback
    # Last-ditch fallback — ensures get_evaluator is total even before
    # the package's __init__ has registered anything.
    return DeterministicEvaluator()


def list_evaluators() -> Dict[DeliverableType, Evaluator]:
    """Return a snapshot of the current registry."""
    with _REGISTRY_LOCK:
        return dict(_REGISTRY)


__all__ = [
    "Evaluator",
    "DeterministicEvaluator",
    "EvaluationContext",
    "register_evaluator",
    "get_evaluator",
    "list_evaluators",
]
