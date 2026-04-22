"""
Murphy reconciliation subsystem — closed-loop output↔request reconciliation.

Public surface:

* :class:`Request`, :class:`Deliverable`, :class:`IntentSpec`,
  :class:`ReconciliationScore`, :class:`Patch`, :class:`LoopOutcome`,
  :class:`LoopBudget`, :class:`DeliverableType`, :class:`PatchKind`,
  :class:`LoopTerminationReason`
* :class:`IntentExtractor` — request → intent specs (handles vagueness)
* :class:`OutputEvaluator` — multi-signal scoring across deliverable types
* :class:`PatchSynthesizer` — diagnoses → typed patch proposals
* :class:`ReconciliationLoop` — bounded controller / state machine
* :class:`LearningHook` / :func:`make_outcome_sink` — wire outcomes into
  Murphy's existing learning engine
* :class:`FeatureFlags` / :func:`current_flags` — env-driven phase rollout
* :class:`StandardsCatalog` / :func:`default_catalog` /
  :func:`register_standard` — extensible "above-average professional best
  practice" catalog covering all deliverable types, not just code

The subsystem honours the canonical-source rule: every file is authored
under ``Murphy System/src/reconciliation/`` and mirrored byte-identical
to ``src/reconciliation/`` at the repo root.

Phased rollout (controlled by env flags — see :mod:`feature_flags`):

* Phase 1: observe-only (default).  Scores deliverables; no patching.
* Phase 2: prompt/config patching.
* Phase 3: code-diff patches via PR.
* Phase 4: automatic retraining + A/B promotion.

Design label: RECON-PKG-001
"""

from __future__ import annotations

from .clarifying_questions import ClarifyingQuestionSynthesizer
from .constraints import ConstraintExtractor, Constraints
from .delegation import (
    BEST_EFFORT_PREAMBLE,
    auto_resolve_questions,
    detect_delegation,
)
from .feature_flags import FeatureFlags, current_flags
from .intent_classifier import (
    IntentClassifier,
    IntentClassifierError,
    IntentPrediction,
    evaluate_corpus,
)
from .intent_corpus import INTERNAL_REQUEST_CORPUS, get_corpus
from .learning_hooks import LearningHook, make_outcome_sink, outcome_to_feedback_payload
from .request_decomposer import DecompositionPart, RequestDecomposer
from .models import (
    AcceptanceCriterion,
    AmbiguityVector,
    ClarifyingQuestion,
    CriterionKind,
    CriterionResult,
    DelegatedPick,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
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
from .reconciliation_loop import GeneratorFn, OutcomeSink, ReconciliationLoop
from .request_intent import IntentExtractor
from .standards import (
    Standard,
    StandardsCatalog,
    default_catalog,
    register_standard,
)

# Importing the evaluators package as a side effect registers the
# built-in evaluators with the global registry.
from . import evaluators  # noqa: F401

__all__ = [
    # Models
    "AcceptanceCriterion",
    "AmbiguityVector",
    "ClarifyingQuestion",
    "CriterionKind",
    "CriterionResult",
    "DelegatedPick",
    "Deliverable",
    "DeliverableType",
    "Diagnosis",
    "DiagnosisSeverity",
    "IntentSpec",
    "LoopBudget",
    "LoopIteration",
    "LoopOutcome",
    "LoopTerminationReason",
    "Patch",
    "PatchKind",
    "ReconciliationScore",
    "Request",
    # Components
    "BEST_EFFORT_PREAMBLE",
    "ClarifyingQuestionSynthesizer",
    "ConstraintExtractor",
    "Constraints",
    "DecompositionPart",
    "auto_resolve_questions",
    "detect_delegation",
    "FeatureFlags",
    "current_flags",
    "IntentClassifier",
    "IntentClassifierError",
    "IntentPrediction",
    "INTERNAL_REQUEST_CORPUS",
    "get_corpus",
    "evaluate_corpus",
    "IntentExtractor",
    "RequestDecomposer",
    "LearningHook",
    "make_outcome_sink",
    "outcome_to_feedback_payload",
    "OutputEvaluator",
    "PatchSynthesizer",
    "ReconciliationLoop",
    "GeneratorFn",
    "OutcomeSink",
    # Standards
    "Standard",
    "StandardsCatalog",
    "default_catalog",
    "register_standard",
]
