"""
Wire reconciliation outcomes into Murphy's existing learning engine.

Each :class:`LoopOutcome` is converted to a payload accepted by
``learning_engine.feedback_loop_wiring`` and to a
``CorrectionCaptureRequest`` for the correction store.  Both bindings
are best-effort: missing dependencies degrade to no-ops with a single
log line so the reconciliation subsystem stays usable in standalone /
CI contexts.

Design label: RECON-LEARN-001
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

from .feature_flags import FeatureFlags, current_flags
from .models import LoopOutcome, LoopTerminationReason

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal handles, resolved lazily so a missing import never breaks the
# reconciliation loop itself.
# ---------------------------------------------------------------------------

_engine_singleton: Any = None


def _resolve_engine() -> Any:
    """Lazily import and instantiate the LearningEngine.  May return None."""
    global _engine_singleton
    if _engine_singleton is not None:
        return _engine_singleton
    try:
        from src.learning_engine.learning_engine import LearningEngine  # type: ignore
        _engine_singleton = LearningEngine(enable_learning=True)
        return _engine_singleton
    except Exception as exc:
        logger.debug("LearningEngine unavailable to reconciliation hooks: %s", exc)
        return None


def _resolve_correction_store() -> Any:
    try:
        from src.learning_engine.correction_storage import CorrectionStorageSystem  # type: ignore
        return CorrectionStorageSystem()
    except Exception as exc:
        logger.debug("CorrectionStorageSystem unavailable to reconciliation hooks: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Outcome → learning-engine payload
# ---------------------------------------------------------------------------


def outcome_to_feedback_payload(outcome: LoopOutcome) -> dict:
    """Serialise a :class:`LoopOutcome` into a learning-engine feedback dict.

    The payload is shaped to drop straight into
    ``LearningEngine.collect_feedback`` (a free-form dict consumer).
    """
    final = outcome.final_score
    return {
        "kind": "reconciliation_outcome",
        "request_id": outcome.request_id,
        "intent_id": outcome.intent_id,
        "deliverable_id": outcome.deliverable_id,
        "termination_reason": outcome.termination_reason.value,
        "accepted": outcome.accepted,
        "iterations": len(outcome.iterations),
        "soft_score": final.soft_score if final else None,
        "hard_pass": final.hard_pass if final else None,
        "diagnoses": [d.summary for d in (final.diagnoses if final else [])],
        "clarifying_questions": [q.question for q in outcome.clarifying_questions],
        "started_at": outcome.started_at.isoformat(),
        "finished_at": outcome.finished_at.isoformat() if outcome.finished_at else None,
    }


# ---------------------------------------------------------------------------
# The sink callable — designed to be passed to ReconciliationLoop(...,
# outcome_sink=record_outcome).
# ---------------------------------------------------------------------------


class LearningHook:
    """Callable that funnels :class:`LoopOutcome` records into the learning loop.

    Args:
        flags: Feature flag snapshot.  When ``auto_retrain`` is False
            (default), outcomes are still *recorded* into the correction
            store and learning engine but no retraining is triggered.
        engine: Optional pre-resolved learning engine, to bypass lazy
            import (useful in tests).
        store: Optional pre-resolved correction store.
    """

    def __init__(
        self,
        flags: Optional[FeatureFlags] = None,
        engine: Any = None,
        store: Any = None,
    ) -> None:
        self._flags = flags or current_flags()
        self._engine = engine
        self._store = store
        self.calls: List[LoopOutcome] = []

    def __call__(self, outcome: LoopOutcome) -> None:
        self.calls.append(outcome)
        engine = self._engine if self._engine is not None else _resolve_engine()
        store = self._store if self._store is not None else _resolve_correction_store()

        payload = outcome_to_feedback_payload(outcome)

        if engine is not None:
            collect = getattr(engine, "collect_feedback", None)
            if callable(collect):
                try:
                    collect(payload)
                except Exception:  # pragma: no cover — best effort
                    logger.exception("LearningEngine.collect_feedback raised")

        if store is not None:
            self._record_correction(store, outcome, payload)

        if self._flags.auto_retrain and outcome.termination_reason in (
            LoopTerminationReason.PASSED,
            LoopTerminationReason.MAX_ITERATIONS,
            LoopTerminationReason.NO_IMPROVEMENT,
        ):
            self._maybe_trigger_retrain(engine, payload)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _record_correction(store: Any, outcome: LoopOutcome, payload: dict) -> None:
        capture = getattr(store, "capture", None) or getattr(store, "add_correction", None)
        if not callable(capture):
            return
        try:
            capture(
                {
                    "task_id": outcome.request_id,
                    "operation": "reconciliation_loop",
                    "original_output": outcome.deliverable_id,
                    "corrected_output": payload,
                    "reasoning": outcome.termination_reason.value,
                }
            )
        except Exception:  # pragma: no cover — best effort
            logger.exception("Correction store capture raised")

    @staticmethod
    def _maybe_trigger_retrain(engine: Any, payload: dict) -> None:
        if engine is None:
            return
        trigger = getattr(engine, "trigger_retraining", None)
        if not callable(trigger):
            return
        try:
            trigger({"source": "reconciliation_loop", "payload": payload})
        except Exception:  # pragma: no cover
            logger.exception("LearningEngine.trigger_retraining raised")


def make_outcome_sink(
    flags: Optional[FeatureFlags] = None,
    engine: Any = None,
    store: Any = None,
) -> Callable[[LoopOutcome], None]:
    """Convenience constructor that returns a fresh :class:`LearningHook`."""
    return LearningHook(flags=flags, engine=engine, store=store)


__all__ = [
    "LearningHook",
    "make_outcome_sink",
    "outcome_to_feedback_payload",
]
