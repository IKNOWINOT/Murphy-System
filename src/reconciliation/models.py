"""
Reconciliation subsystem — typed data models.

Defines the immutable contract between the intent extractor, evaluators,
patch synthesizer, controller, and learning hooks.

All models are :class:`pydantic.BaseModel` subclasses so they serialize
cleanly into the existing correction store, the event backbone, and the
HITL dashboard.

Design label: RECON-MODELS-001
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeliverableType(str, Enum):
    """The kind of artifact Murphy produced for a request.

    The reconciliation subsystem dispatches evaluators and patch
    synthesizers based on this value.  Treat the catalog as
    open — new types may be added; evaluators that do not recognise a
    type fall through to :class:`DeliverableType.GENERIC_TEXT`.
    """

    CODE = "code"
    CONFIG_FILE = "config_file"
    SHELL_SCRIPT = "shell_script"
    DOCUMENT = "document"
    GENERIC_TEXT = "generic_text"
    JSON_PAYLOAD = "json_payload"
    MAILBOX_PROVISIONING = "mailbox_provisioning"
    DEPLOYMENT_RESULT = "deployment_result"
    DASHBOARD = "dashboard"
    PLAN = "plan"
    WORKFLOW = "workflow"
    OTHER = "other"


class CriterionKind(str, Enum):
    """How an :class:`AcceptanceCriterion` is evaluated."""

    DETERMINISTIC = "deterministic"   # schema, regex, exit-code, file-exists
    SEMANTIC = "semantic"              # embedding similarity to exemplar
    LLM_RUBRIC = "llm_rubric"          # LLM-as-judge against a rubric
    BEHAVIOURAL = "behavioural"        # sandboxed execution side-effects
    STANDARD = "standard"              # professional best-practice standard


class DiagnosisSeverity(str, Enum):
    """Severity of a single failed criterion."""

    BLOCKER = "blocker"     # criterion is hard-required and failed
    MAJOR = "major"         # noticeably degrades the deliverable
    MINOR = "minor"         # quality nit
    INFO = "info"           # informational observation only


class PatchKind(str, Enum):
    """The kind of patch the synthesizer can propose."""

    PROMPT_REWRITE = "prompt_rewrite"
    CONFIG_TWEAK = "config_tweak"
    PARAMETER_RETRY = "parameter_retry"
    CODE_DIFF = "code_diff"
    CONTENT_EDIT = "content_edit"
    NOOP = "noop"


class LoopTerminationReason(str, Enum):
    """Why the reconciliation loop stopped iterating."""

    PASSED = "passed"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_IMPROVEMENT = "no_improvement"
    AMBIGUITY_REQUIRES_CLARIFICATION = "ambiguity_requires_clarification"
    PATCH_SYNTHESIS_FAILED = "patch_synthesis_failed"
    DISABLED_BY_FEATURE_FLAG = "disabled_by_feature_flag"


# ---------------------------------------------------------------------------
# Base config — every model is immutable + extra-forbid for safety
# ---------------------------------------------------------------------------


class _ReconBase(BaseModel):
    """Shared pydantic config for all reconciliation models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,           # mutability is required for incremental builds
        validate_assignment=True,
        str_strip_whitespace=True,
    )


# ---------------------------------------------------------------------------
# Request + Deliverable
# ---------------------------------------------------------------------------


class Request(_ReconBase):
    """A request submitted to Murphy that ultimately produces a deliverable."""

    id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:16]}")
    text: str = Field(..., min_length=1, description="Free-form request text")
    deliverable_type: DeliverableType = DeliverableType.GENERIC_TEXT
    requester_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Deliverable(_ReconBase):
    """The artifact Murphy produced in response to a :class:`Request`."""

    id: str = Field(default_factory=lambda: f"dlv_{uuid.uuid4().hex[:16]}")
    request_id: str
    deliverable_type: DeliverableType
    content: Any = Field(
        ...,
        description=(
            "The raw deliverable.  May be a string (text, code, document), a "
            "dict (JSON payload, provisioning result), or a path-like reference"
        ),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    produced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Intent + Ambiguity
# ---------------------------------------------------------------------------


class AcceptanceCriterion(_ReconBase):
    """A single, individually-evaluable success condition for a deliverable."""

    id: str = Field(default_factory=lambda: f"crit_{uuid.uuid4().hex[:8]}")
    description: str = Field(..., min_length=1)
    kind: CriterionKind
    weight: float = Field(1.0, ge=0.0, le=10.0)
    hard: bool = Field(
        False,
        description="If true, failing this criterion blocks acceptance regardless of soft score.",
    )
    rubric: Optional[str] = Field(
        None,
        description="LLM-judge rubric text (only required when kind == LLM_RUBRIC).",
    )
    check_spec: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form spec consumed by the matching evaluator: e.g. "
            "{'regex': '...'} for DETERMINISTIC, {'exemplar': '...'} for SEMANTIC, "
            "{'standard_id': 'PEP8'} for STANDARD."
        ),
    )

    @field_validator("rubric")
    @classmethod
    def _rubric_required_for_llm(cls, v: Optional[str], info: Any) -> Optional[str]:
        kind = info.data.get("kind") if info and info.data else None
        if kind == CriterionKind.LLM_RUBRIC and not v:
            raise ValueError("rubric must be provided when kind == LLM_RUBRIC")
        return v


class AmbiguityVector(_ReconBase):
    """An enumeration of what is *under-specified* in a vague request."""

    items: List[str] = Field(
        default_factory=list,
        description="One short phrase per unresolved dimension of the request.",
    )

    @property
    def is_ambiguous(self) -> bool:
        return len(self.items) > 0


class IntentSpec(_ReconBase):
    """A structured interpretation of a free-form :class:`Request`.

    Vague requests typically yield a *distribution* of intent specs;
    callers of :class:`request_intent.IntentExtractor` will receive a
    list of these with :attr:`confidence` summing approximately to 1.
    """

    id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:12]}")
    request_id: str
    summary: str = Field(..., min_length=1)
    deliverable_type: DeliverableType
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    soft_preferences: List[str] = Field(default_factory=list)
    success_exemplars: List[str] = Field(default_factory=list)
    failure_exemplars: List[str] = Field(default_factory=list)
    ambiguity: AmbiguityVector = Field(default_factory=AmbiguityVector)
    clarifying_questions: List["ClarifyingQuestion"] = Field(
        default_factory=list,
        description=(
            "Auto-emitted by IntentExtractor when the request is ambiguous; "
            "answering them is HITL-only — Murphy must NOT auto-pick a "
            "candidate answer unless delegation_granted is True."
        ),
    )
    delegation_granted: bool = Field(
        False,
        description=(
            "True iff the principal explicitly delegated picks to Murphy "
            "(HITL-003 — phrases like 'you can pick' / 'your call' / "
            "Request.context['delegation'] = True). When False, Murphy "
            "must NOT auto-answer any clarifying question."
        ),
    )
    delegated_picks: List["DelegatedPick"] = Field(
        default_factory=list,
        description=(
            "Best-effort answers Murphy auto-selected because delegation "
            "was granted. Each carries a rationale so every assumption is "
            "auditable and individually overridable."
        ),
    )
    mss_trace: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional Magnify→Simplify→Solidify trace: governance_status, "
            "input/output quality scores, and recommendation. Populated when "
            "an MSSController is wired into the extractor."
        ),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Scoring + Diagnoses
# ---------------------------------------------------------------------------


class CriterionResult(_ReconBase):
    """Per-criterion evaluation result feeding the aggregate score."""

    criterion_id: str
    description: str
    kind: CriterionKind
    score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    weight: float = Field(1.0, ge=0.0)
    hard: bool = False
    detail: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class Diagnosis(_ReconBase):
    """A targeted, machine-readable description of *what is wrong*.

    Each diagnosis is consumed by :mod:`patch_synthesizer` to propose a
    single corrective patch.
    """

    id: str = Field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    criterion_id: Optional[str] = None
    severity: DiagnosisSeverity
    summary: str = Field(..., min_length=1)
    suggested_patch_kind: PatchKind = PatchKind.PROMPT_REWRITE
    suggested_action: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ReconciliationScore(_ReconBase):
    """Aggregate score returned by :class:`output_evaluator.OutputEvaluator`."""

    deliverable_id: str
    intent_id: str
    soft_score: float = Field(..., ge=0.0, le=1.0)
    hard_pass: bool
    per_criterion: List[CriterionResult] = Field(default_factory=list)
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    judged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def acceptable(self) -> bool:
        """Hard-pass and soft-score crosses the recommended 0.85 bar."""
        return self.hard_pass and self.soft_score >= 0.85


# ---------------------------------------------------------------------------
# Patches + Loop
# ---------------------------------------------------------------------------


class Patch(_ReconBase):
    """A typed proposal to improve the next-iteration deliverable."""

    id: str = Field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:10]}")
    kind: PatchKind
    target: str = Field(
        ...,
        description="What the patch targets: a prompt id, a config key, a file path, etc.",
    )
    payload: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    addresses_diagnoses: List[str] = Field(default_factory=list)
    requires_human_review: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoopBudget(_ReconBase):
    """Hard caps on a single reconciliation loop run."""

    max_iterations: int = Field(3, ge=1, le=20)
    max_wallclock_seconds: float = Field(60.0, gt=0.0)
    max_llm_calls: int = Field(8, ge=0)
    no_improvement_patience: int = Field(
        2,
        ge=1,
        description="Stop if soft_score does not strictly improve for N iterations.",
    )


class LoopIteration(_ReconBase):
    """Snapshot of a single loop iteration."""

    index: int = Field(..., ge=0)
    score: ReconciliationScore
    applied_patch: Optional[Patch] = None
    duration_seconds: float = 0.0


class ClarifyingQuestion(_ReconBase):
    """A question emitted when a vague request cannot be resolved automatically."""

    id: str = Field(default_factory=lambda: f"q_{uuid.uuid4().hex[:8]}")
    question: str = Field(..., min_length=1)
    ambiguity_item: str
    candidate_answers: List[str] = Field(default_factory=list)


class DelegatedPick(_ReconBase):
    """A best-effort answer Murphy auto-selected after explicit user delegation.

    HITL-003: when the principal says "you can pick" (or sets
    ``Request.context['delegation'] = True``), Murphy auto-resolves
    each :class:`ClarifyingQuestion` and records the choice + rationale
    here so the principal can audit and override every assumption.
    """

    question_id: str
    question: str = Field(..., min_length=1)
    ambiguity_item: str
    chosen_answer: str
    rationale: str = Field(
        ...,
        min_length=1,
        description=(
            "Short, machine-friendly tag explaining why this answer was "
            "picked, e.g. 'auto: top classifier rank'."
        ),
    )


class LoopOutcome(_ReconBase):
    """Final result of a reconciliation loop run."""

    request_id: str
    intent_id: str
    deliverable_id: str
    termination_reason: LoopTerminationReason
    iterations: List[LoopIteration] = Field(default_factory=list)
    final_score: Optional[ReconciliationScore] = None
    clarifying_questions: List[ClarifyingQuestion] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    @property
    def accepted(self) -> bool:
        return (
            self.termination_reason == LoopTerminationReason.PASSED
            and self.final_score is not None
            and self.final_score.acceptable
        )


__all__ = [
    "DeliverableType",
    "CriterionKind",
    "DiagnosisSeverity",
    "PatchKind",
    "LoopTerminationReason",
    "Request",
    "Deliverable",
    "AcceptanceCriterion",
    "AmbiguityVector",
    "IntentSpec",
    "CriterionResult",
    "Diagnosis",
    "ReconciliationScore",
    "Patch",
    "LoopBudget",
    "LoopIteration",
    "ClarifyingQuestion",
    "DelegatedPick",
    "LoopOutcome",
]


# Resolve the forward reference IntentSpec → ClarifyingQuestion (declared
# after IntentSpec for grouping reasons).  Without this, pydantic v2 raises
# PydanticUndefinedAnnotation on first use.
IntentSpec.model_rebuild()
