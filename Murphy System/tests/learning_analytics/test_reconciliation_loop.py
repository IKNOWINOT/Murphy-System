"""
Tests for the patch synthesizer, the reconciliation loop controller,
and the learning-engine outcome sink.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from src.reconciliation import (
    AmbiguityVector,
    Deliverable,
    DeliverableType,
    Diagnosis,
    DiagnosisSeverity,
    FeatureFlags,
    IntentExtractor,
    IntentSpec,
    LearningHook,
    LoopBudget,
    LoopOutcome,
    LoopTerminationReason,
    Patch,
    PatchKind,
    PatchSynthesizer,
    ReconciliationLoop,
    Request,
    make_outcome_sink,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FLAGS_OBSERVE = FeatureFlags(
    enabled=True,
    observe_only=True,
    patch_prompts=False,
    patch_code=False,
    auto_retrain=False,
    llm_judge=False,
)

_FLAGS_PATCH_PROMPTS = FeatureFlags(
    enabled=True,
    observe_only=False,
    patch_prompts=True,
    patch_code=False,
    auto_retrain=False,
    llm_judge=False,
)

_FLAGS_DISABLED = FeatureFlags(
    enabled=False,
    observe_only=True,
    patch_prompts=False,
    patch_code=False,
    auto_retrain=False,
    llm_judge=False,
)


def _diag(
    severity: DiagnosisSeverity = DiagnosisSeverity.MAJOR,
    kind: PatchKind = PatchKind.PROMPT_REWRITE,
) -> Diagnosis:
    return Diagnosis(severity=severity, summary="x", suggested_patch_kind=kind)


# ---------------------------------------------------------------------------
# PatchSynthesizer
# ---------------------------------------------------------------------------


def test_patch_synthesizer_emits_nothing_in_observe_only() -> None:
    syn = PatchSynthesizer(flags=_FLAGS_OBSERVE)
    intent = IntentExtractor().extract(Request(text="x"))[0]
    patches = syn.synthesize(intent, [_diag()])
    assert patches == []


def test_patch_synthesizer_emits_prompt_rewrite_when_enabled() -> None:
    syn = PatchSynthesizer(flags=_FLAGS_PATCH_PROMPTS)
    intent = IntentExtractor().extract(Request(text="x"))[0]
    patches = syn.synthesize(intent, [_diag(kind=PatchKind.PROMPT_REWRITE)])
    assert len(patches) == 1
    assert patches[0].kind == PatchKind.PROMPT_REWRITE
    assert "additional_clause" in patches[0].payload
    assert not patches[0].requires_human_review


def test_patch_synthesizer_skips_info_severity() -> None:
    syn = PatchSynthesizer(flags=_FLAGS_PATCH_PROMPTS)
    intent = IntentExtractor().extract(Request(text="x"))[0]
    assert syn.synthesize(intent, [_diag(severity=DiagnosisSeverity.INFO)]) == []


def test_patch_synthesizer_suppresses_code_diff_without_flag() -> None:
    syn = PatchSynthesizer(flags=_FLAGS_PATCH_PROMPTS)  # patch_code is False
    intent = IntentExtractor().extract(Request(text="x"))[0]
    assert syn.synthesize(intent, [_diag(kind=PatchKind.CODE_DIFF)]) == []


def test_patch_synthesizer_marks_code_diff_for_human_review() -> None:
    flags = FeatureFlags(
        enabled=True, observe_only=False, patch_prompts=False,
        patch_code=True, auto_retrain=False, llm_judge=False,
    )
    syn = PatchSynthesizer(flags=flags)
    intent = IntentExtractor().extract(Request(text="x"))[0]
    patches = syn.synthesize(intent, [_diag(kind=PatchKind.CODE_DIFF)])
    assert len(patches) == 1
    assert patches[0].requires_human_review


# ---------------------------------------------------------------------------
# ReconciliationLoop — observe-only path
# ---------------------------------------------------------------------------


def _generator_factory(contents: List):
    """Build a generator that returns a queued sequence of contents."""
    queue = list(contents)

    def gen(req: Request, intent: IntentSpec, patches: Sequence[Patch]) -> Deliverable:
        c = queue.pop(0) if queue else queue and queue[-1]
        return Deliverable(
            request_id=req.id,
            deliverable_type=req.deliverable_type,
            content=c,
        )

    return gen, queue


def test_loop_observe_only_runs_one_iteration_and_does_not_patch() -> None:
    gen, queue = _generator_factory(
        ["#!/usr/bin/env bash\nset -euo pipefail\necho hi\n"]
    )
    loop = ReconciliationLoop(flags=_FLAGS_OBSERVE)
    req = Request(text="write a script", deliverable_type=DeliverableType.SHELL_SCRIPT)
    outcome = loop.run(req, gen)
    assert len(outcome.iterations) == 1
    assert outcome.final_score is not None
    assert outcome.termination_reason in (
        LoopTerminationReason.PASSED,
        LoopTerminationReason.DISABLED_BY_FEATURE_FLAG,
    )


def test_loop_disabled_short_circuits_with_no_score() -> None:
    gen, _ = _generator_factory([{"accounts": []}])
    loop = ReconciliationLoop(flags=_FLAGS_DISABLED)
    req = Request(text="x", deliverable_type=DeliverableType.MAILBOX_PROVISIONING)
    outcome = loop.run(req, gen)
    assert outcome.termination_reason == LoopTerminationReason.DISABLED_BY_FEATURE_FLAG
    assert outcome.final_score is None


# ---------------------------------------------------------------------------
# ReconciliationLoop — patching path
# ---------------------------------------------------------------------------


def test_loop_iterates_until_passed_with_patches() -> None:
    """Generator returns failing then passing scripts; loop must converge."""

    sequence = [
        "echo broken\n",  # missing shebang → hard fail
        "#!/usr/bin/env bash\nset -euo pipefail\necho fixed\n",  # passes
    ]
    gen, _ = _generator_factory(sequence)
    loop = ReconciliationLoop(flags=_FLAGS_PATCH_PROMPTS)
    outcome = loop.run(
        Request(text="write a script", deliverable_type=DeliverableType.SHELL_SCRIPT),
        gen,
        budget=LoopBudget(max_iterations=3, no_improvement_patience=3),
    )
    assert outcome.termination_reason == LoopTerminationReason.PASSED
    assert outcome.accepted
    assert len(outcome.iterations) >= 2


def test_loop_terminates_when_no_improvement() -> None:
    """Generator returns the same failing output; loop must give up."""

    bad = "echo no shebang\n"
    gen, _ = _generator_factory([bad, bad, bad, bad, bad])
    loop = ReconciliationLoop(flags=_FLAGS_PATCH_PROMPTS)
    outcome = loop.run(
        Request(text="write a script", deliverable_type=DeliverableType.SHELL_SCRIPT),
        gen,
        budget=LoopBudget(max_iterations=4, no_improvement_patience=2),
    )
    assert outcome.termination_reason in (
        LoopTerminationReason.NO_IMPROVEMENT,
        LoopTerminationReason.MAX_ITERATIONS,
        LoopTerminationReason.PATCH_SYNTHESIS_FAILED,
    )
    assert not outcome.accepted


def test_loop_emits_clarifying_questions_for_vague_failed_request() -> None:
    """Vague request that fails to converge must surface clarifying questions."""

    # Empty content fails the substance floor → loop never converges.
    gen, _ = _generator_factory(["", "", "", ""])
    loop = ReconciliationLoop(flags=_FLAGS_PATCH_PROMPTS)
    outcome = loop.run(
        Request(text="make it nicer"),
        gen,
        budget=LoopBudget(max_iterations=2, no_improvement_patience=1),
    )
    assert not outcome.accepted
    assert outcome.clarifying_questions, "must emit clarifying questions"
    # One question per ambiguity vector item.
    assert all(q.ambiguity_item for q in outcome.clarifying_questions)


def test_loop_outcome_sink_receives_outcome() -> None:
    received: List[LoopOutcome] = []
    sink = received.append
    gen, _ = _generator_factory(["hello world content"])
    loop = ReconciliationLoop(flags=_FLAGS_OBSERVE, outcome_sink=sink)
    loop.run(Request(text="write a sentence"), gen)
    assert len(received) == 1


def test_loop_sink_exception_does_not_break_loop() -> None:
    def boom(_outcome: LoopOutcome) -> None:
        raise RuntimeError("explode")

    gen, _ = _generator_factory(["hello world content"])
    loop = ReconciliationLoop(flags=_FLAGS_OBSERVE, outcome_sink=boom)
    outcome = loop.run(Request(text="write a sentence"), gen)
    assert outcome is not None  # loop completed despite sink raising


# ---------------------------------------------------------------------------
# LearningHook
# ---------------------------------------------------------------------------


class _StubEngine:
    def __init__(self) -> None:
        self.collected: List[dict] = []
        self.retrained: List[dict] = []

    def collect_feedback(self, payload: dict) -> None:
        self.collected.append(payload)

    def trigger_retraining(self, payload: dict) -> None:
        self.retrained.append(payload)


class _StubStore:
    def __init__(self) -> None:
        self.captured: List[dict] = []

    def capture(self, payload: dict) -> None:
        self.captured.append(payload)


def test_learning_hook_records_outcome_into_engine_and_store() -> None:
    engine = _StubEngine()
    store = _StubStore()
    hook = LearningHook(flags=_FLAGS_OBSERVE, engine=engine, store=store)

    gen, _ = _generator_factory(["hello world content"])
    loop = ReconciliationLoop(flags=_FLAGS_OBSERVE, outcome_sink=hook)
    loop.run(Request(text="write a sentence"), gen)

    assert len(hook.calls) == 1
    assert len(engine.collected) == 1
    assert engine.collected[0]["kind"] == "reconciliation_outcome"
    assert len(store.captured) == 1
    # Auto-retrain disabled: must not have triggered.
    assert engine.retrained == []


def test_learning_hook_triggers_retrain_when_enabled() -> None:
    flags = FeatureFlags(
        enabled=True, observe_only=True, patch_prompts=False,
        patch_code=False, auto_retrain=True, llm_judge=False,
    )
    engine = _StubEngine()
    hook = LearningHook(flags=flags, engine=engine, store=None)

    gen, _ = _generator_factory(["hello world content"])
    loop = ReconciliationLoop(flags=flags, outcome_sink=hook)
    loop.run(Request(text="write a sentence"), gen)

    assert len(engine.retrained) == 1


def test_make_outcome_sink_returns_callable() -> None:
    sink = make_outcome_sink(flags=_FLAGS_OBSERVE)
    assert callable(sink)
