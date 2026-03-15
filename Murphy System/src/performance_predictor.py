"""
Performance Predictor for Murphy System Learning Engine.

Design Label: LEARN-002 — Pattern-driven Confidence Prediction
Owner: Platform Engineering
Dependencies:
  - learning_engine.PatternRecognizer / LearnedPattern
  - EventBackbone (publishes PREDICTION_GENERATED, THRESHOLD_UPDATED)

Role in the closed learning loop::

    PatternRecognizer → PerformancePredictor → threshold / gate updates

Receives :class:`LearnedPattern` objects from the pattern recogniser and
produces :class:`PredictionResult` objects that encode recommended
confidence thresholds and gate sensitivity deltas.  The predictor
maintains an exponentially-weighted moving average of observed success
rates per task-type / gate-id so that each new prediction is grounded
in empirical data rather than fixed heuristics.

Safety invariants:
  - Thread-safe: all mutable state guarded by a single Lock.
  - Bounded: history deques have configurable max lengths (default 1000).
  - Conservative: threshold changes are bounded to ±MAX_DELTA per cycle.
  - Monotone drift tracking: records cumulative threshold drift per key.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_HISTORY = 1_000
_MAX_DELTA = 0.10          # Maximum threshold change per update cycle
_EWMA_ALPHA = 0.1          # Learning rate for exponential moving average
_MIN_THRESHOLD = 0.50      # Absolute minimum confidence threshold
_MAX_THRESHOLD = 0.99      # Absolute maximum confidence threshold
_MIN_SAMPLES = 5           # Minimum samples before adjusting a threshold


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    """Output of :class:`PerformancePredictor` for one key."""

    prediction_id: str
    key: str                        # task_type or gate_id
    predicted_success_rate: float   # [0, 1]
    recommended_threshold: float    # [0, 1] confidence threshold suggestion
    threshold_delta: float          # change from current stored threshold
    sample_count: int
    pattern_count: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "key": self.key,
            "predicted_success_rate": self.predicted_success_rate,
            "recommended_threshold": self.recommended_threshold,
            "threshold_delta": self.threshold_delta,
            "sample_count": self.sample_count,
            "pattern_count": self.pattern_count,
            "generated_at": self.generated_at,
        }


@dataclass
class OutcomeSample:
    """A single recorded outcome for success-rate tracking."""
    key: str
    success: bool
    confidence: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# PerformancePredictor
# ---------------------------------------------------------------------------

class PerformancePredictor:
    """Converts detected patterns into confidence threshold recommendations.

    Usage::

        predictor = PerformancePredictor(event_backbone=backbone)
        predictor.record_outcome("task_type:onboarding", success=True, confidence=0.87)
        results = predictor.predict_from_patterns(patterns)
        # results is List[PredictionResult]
    """

    def __init__(
        self,
        event_backbone=None,
        ewma_alpha: float = _EWMA_ALPHA,
        max_delta: float = _MAX_DELTA,
        min_threshold: float = _MIN_THRESHOLD,
        max_threshold: float = _MAX_THRESHOLD,
        min_samples: int = _MIN_SAMPLES,
    ) -> None:
        self._lock = threading.Lock()
        self._backbone = event_backbone
        self._ewma_alpha = ewma_alpha
        self._max_delta = max_delta
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        self._min_samples = min_samples

        # Per-key deques of OutcomeSamples
        self._samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY))
        # Per-key current threshold estimate (EWMA)
        self._thresholds: Dict[str, float] = {}
        # Cumulative drift per key
        self._drift: Dict[str, float] = defaultdict(float)
        # Prediction history
        self._predictions: deque = deque(maxlen=_MAX_HISTORY)

        # Metrics
        self._metrics: Dict[str, Any] = {
            "total_outcomes_recorded": 0,
            "total_predictions_generated": 0,
            "total_threshold_updates": 0,
            "keys_tracked": 0,
        }

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        key: str,
        success: bool,
        confidence: float,
    ) -> None:
        """Record a single task/gate outcome for the given *key*."""
        sample = OutcomeSample(key=key, success=success, confidence=confidence)
        with self._lock:
            self._samples[key].append(sample)
            self._metrics["total_outcomes_recorded"] += 1
            self._metrics["keys_tracked"] = len(self._samples)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_from_patterns(
        self,
        patterns: List[Any],
    ) -> List[PredictionResult]:
        """Produce threshold recommendations driven by *patterns*.

        *patterns* is expected to be a list of :class:`LearnedPattern`
        objects (from ``learning_engine.learning_engine``), but the
        predictor is duck-typed and only requires that each pattern has
        a ``pattern_type`` string and an ``affected_metrics`` list.

        For each unique key mentioned in the pattern metrics, the
        predictor computes the empirical success rate and produces a
        :class:`PredictionResult`.
        """
        results: List[PredictionResult] = []
        # Collect all keys referenced by these patterns
        keys_from_patterns: Dict[str, int] = defaultdict(int)  # key → pattern count
        for pat in patterns:
            for metric_name in getattr(pat, "affected_metrics", []):
                keys_from_patterns[metric_name] += 1

        # Also compute for all keys that have accumulated samples
        with self._lock:
            all_keys = set(keys_from_patterns) | set(self._samples.keys())

        for key in all_keys:
            result = self._compute_prediction(key, keys_from_patterns.get(key, 0))
            if result is not None:
                results.append(result)
                with self._lock:
                    self._predictions.append(result)
                    self._metrics["total_predictions_generated"] += 1

        # Publish prediction events
        for result in results:
            self._publish_prediction(result)

        return results

    def _compute_prediction(
        self, key: str, pattern_count: int
    ) -> Optional[PredictionResult]:
        """Compute a PredictionResult for *key*; returns None if too few samples."""
        with self._lock:
            samples = list(self._samples.get(key, []))
            current_threshold = self._thresholds.get(key, 0.85)

        if len(samples) < self._min_samples:
            return None

        success_count = sum(1 for s in samples if s.success)
        success_rate = success_count / len(samples)

        # Compute recommended threshold via EWMA of success rate
        # If success_rate is high → threshold can be tighter (higher);
        # if low → threshold should relax (lower) to avoid over-blocking.
        target = min(self._max_threshold,
                     max(self._min_threshold, success_rate))

        new_threshold = (
            (1.0 - self._ewma_alpha) * current_threshold
            + self._ewma_alpha * target
        )
        # Clamp delta
        delta = new_threshold - current_threshold
        delta = max(-self._max_delta, min(self._max_delta, delta))
        new_threshold = current_threshold + delta

        with self._lock:
            old_threshold = self._thresholds.get(key, 0.85)
            self._thresholds[key] = new_threshold
            self._drift[key] += delta
            if abs(delta) > 1e-6:
                self._metrics["total_threshold_updates"] += 1

        return PredictionResult(
            prediction_id=f"pred-{uuid.uuid4().hex[:8]}",
            key=key,
            predicted_success_rate=success_rate,
            recommended_threshold=new_threshold,
            threshold_delta=new_threshold - old_threshold,
            sample_count=len(samples),
            pattern_count=pattern_count,
        )

    # ------------------------------------------------------------------
    # Threshold access
    # ------------------------------------------------------------------

    def get_threshold(self, key: str, default: float = 0.85) -> float:
        """Return the current recommended threshold for *key*."""
        with self._lock:
            return self._thresholds.get(key, default)

    def get_all_thresholds(self) -> Dict[str, float]:
        """Return a snapshot of all current thresholds."""
        with self._lock:
            return dict(self._thresholds)

    def get_drift(self, key: str) -> float:
        """Return the cumulative threshold drift for *key*."""
        with self._lock:
            return self._drift.get(key, 0.0)

    # ------------------------------------------------------------------
    # Metrics / status
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._metrics)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "keys_tracked": len(self._samples),
                "total_outcomes_recorded": self._metrics["total_outcomes_recorded"],
                "total_predictions_generated": self._metrics["total_predictions_generated"],
                "total_threshold_updates": self._metrics["total_threshold_updates"],
                "thresholds": dict(self._thresholds),
                "drift": dict(self._drift),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_prediction(self, result: PredictionResult) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                EventType.PREDICTION_GENERATED,
                {
                    "source": "performance_predictor",
                    **result.to_dict(),
                },
            )
        except Exception as exc:
            logger.debug("PerformancePredictor: publish skipped: %s", exc)


__all__ = [
    "OutcomeSample",
    "PredictionResult",
    "PerformancePredictor",
]
