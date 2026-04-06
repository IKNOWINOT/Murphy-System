"""
Learning Engine ↔ Event Backbone Feedback Loop Wiring
=====================================================

Closes the feedback loop by:
1. Subscribing to TASK_COMPLETED / TASK_FAILED events from the EventBackbone
2. Feeding outcomes into LearningEngine.collect_feedback()
3. Triggering training pipeline retraining after a configurable threshold
4. Wiring A/B test promotion logic

This module is imported during application startup (e.g. in app.py or
MurphySystemCore) and calls ``wire_feedback_loop()`` to activate.

Design label: LEARN-LOOP-001

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_RETRAIN_THRESHOLD: int = 100  # outcomes before triggering retraining
_AB_PROMOTION_MIN_SAMPLES: int = 50  # minimum samples per variant


# ---------------------------------------------------------------------------
# Singleton wiring state
# ---------------------------------------------------------------------------

_engine: Optional[Any] = None
_outcome_count: int = 0
_lock = threading.Lock()
_wired: bool = False


def wire_feedback_loop(
    learning_engine: Any = None,
    backbone: Any = None,
    retrain_threshold: int = _RETRAIN_THRESHOLD,
) -> bool:
    """Wire EventBackbone task events into the LearningEngine.

    Subscribes to ``task_completed`` and ``task_failed`` events from the
    backbone.  Each event is routed to the learning engine's feedback
    collector.  After *retrain_threshold* outcomes, the training pipeline
    is triggered.

    Args:
        learning_engine: An instance of :class:`LearningEngine`.  If
            ``None``, one is lazily created.
        backbone: EventBackbone instance.  If ``None``, uses the global
            backbone from :mod:`event_backbone_client`.
        retrain_threshold: Number of outcomes before auto-retraining.

    Returns:
        ``True`` if wiring succeeded, ``False`` otherwise.
    """
    global _engine, _wired, _RETRAIN_THRESHOLD

    if _wired:
        logger.debug("Feedback loop already wired — skipping duplicate call")
        return True

    _RETRAIN_THRESHOLD = retrain_threshold

    # Resolve learning engine
    if learning_engine is None:
        try:
            from src.learning_engine.learning_engine import LearningEngine
            learning_engine = LearningEngine(enable_learning=True)
        except ImportError as exc:
            logger.warning("Cannot import LearningEngine: %s", exc)
            return False

    _engine = learning_engine

    # Resolve backbone
    if backbone is None:
        try:
            from src.event_backbone_client import get_backbone
            backbone = get_backbone()
        except ImportError as exc:
            logger.warning("Cannot import event_backbone_client: %s", exc)
            return False

    if backbone is None:
        logger.info("No backbone available — feedback loop not wired")
        return False

    # Subscribe to task events
    try:
        if hasattr(backbone, "subscribe"):
            backbone.subscribe("task_completed", _on_task_completed)
            backbone.subscribe("task_failed", _on_task_failed)
            logger.info(
                "Feedback loop wired: task_completed/task_failed → LearningEngine"
            )
        elif hasattr(backbone, "on"):
            backbone.on("task_completed", _on_task_completed)
            backbone.on("task_failed", _on_task_failed)
            logger.info(
                "Feedback loop wired (on-style): task events → LearningEngine"
            )
        else:
            logger.warning("Backbone has no subscribe/on method — cannot wire")
            return False
    except Exception as exc:
        logger.warning("Failed to subscribe to backbone events: %s", exc)
        return False

    _wired = True
    return True


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _on_task_completed(payload: Dict[str, Any]) -> None:
    """Handle a TASK_COMPLETED event from the backbone."""
    _record_outcome(
        feedback_type="task_execution",
        operation_id=payload.get("task_id", "unknown"),
        success=True,
        confidence=payload.get("confidence", 1.0),
        data=payload,
    )


def _on_task_failed(payload: Dict[str, Any]) -> None:
    """Handle a TASK_FAILED event from the backbone."""
    _record_outcome(
        feedback_type="task_execution",
        operation_id=payload.get("task_id", "unknown"),
        success=False,
        confidence=payload.get("confidence", 0.0),
        data=payload,
    )


def _record_outcome(
    feedback_type: str,
    operation_id: str,
    success: bool,
    confidence: float,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Route an outcome into the learning engine and check retraining threshold."""
    global _outcome_count

    if _engine is None:
        return

    try:
        _engine.collect_feedback(
            feedback_type=feedback_type,
            operation_id=operation_id,
            success=success,
            confidence=confidence,
            feedback_data=data,
        )
    except Exception as exc:
        logger.debug("LearningEngine.collect_feedback failed: %s", exc)
        return

    with _lock:
        _outcome_count += 1
        count = _outcome_count

    # Performance metric
    try:
        _engine.record_performance(
            metric_name=f"{feedback_type}_latency",
            value=data.get("latency_ms", 0.0) if data else 0.0,
            context={"operation_id": operation_id, "success": success},
        )
    except Exception as exc:
        logger.debug("record_performance failed: %s", exc)

    # Check retraining threshold
    if count > 0 and count % _RETRAIN_THRESHOLD == 0:
        _trigger_retraining(count)

    # Check A/B test promotion
    if count > 0 and count % _AB_PROMOTION_MIN_SAMPLES == 0:
        _check_ab_promotion()


# ---------------------------------------------------------------------------
# Training pipeline trigger
# ---------------------------------------------------------------------------


def _trigger_retraining(outcome_count: int) -> None:
    """Trigger the training pipeline when enough outcomes are collected."""
    try:
        from src.learning_engine.training_pipeline import ModelTrainingPipeline
        logger.info(
            "Retraining triggered: %d outcomes accumulated", outcome_count
        )
        # The pipeline is stateless — instantiate and run
        pipeline = ModelTrainingPipeline()
        if hasattr(pipeline, "start_training"):
            pipeline.start_training()
        elif hasattr(pipeline, "train"):
            pipeline.train()
        else:
            logger.debug("TrainingPipeline has no start_training/train method")
    except ImportError as exc:
        logger.debug("TrainingPipeline import failed: %s", exc)
    except Exception as exc:
        logger.warning("Retraining failed: %s", exc)


# ---------------------------------------------------------------------------
# A/B test promotion
# ---------------------------------------------------------------------------


def _check_ab_promotion() -> None:
    """Check if any A/B test variant should be promoted to production."""
    try:
        from src.learning_engine.ab_testing import ABTestingEngine
        ab = ABTestingEngine()
        experiments = ab.get_active_experiments() if hasattr(ab, "get_active_experiments") else []
        for exp in experiments:
            if hasattr(ab, "evaluate_experiment"):
                result = ab.evaluate_experiment(exp)
                if result and getattr(result, "is_significant", False):
                    winner = getattr(result, "winner", None)
                    if winner:
                        logger.info(
                            "A/B test '%s' winner: variant=%s — promoting",
                            getattr(exp, "name", "?"), winner,
                        )
                        if hasattr(ab, "promote_variant"):
                            ab.promote_variant(exp, winner)
    except ImportError:
        logger.debug("ABTestingEngine not available — skipping promotion check")
    except Exception as exc:
        logger.debug("A/B promotion check failed: %s", exc)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def get_feedback_loop_status() -> Dict[str, Any]:
    """Return current feedback loop status."""
    return {
        "wired": _wired,
        "outcome_count": _outcome_count,
        "retrain_threshold": _RETRAIN_THRESHOLD,
        "next_retrain_at": (
            (_outcome_count // _RETRAIN_THRESHOLD + 1) * _RETRAIN_THRESHOLD
            if _wired else None
        ),
        "engine_available": _engine is not None,
    }
