"""
Predictive Failure Anticipation Engine for the Murphy System.

Design Label: PRED-001 — Predictive Failure Anticipation Engine
Owner: Backend Team
Dependencies:
  - SelfFixLoop (ARCH-005)
  - SelfHealingCoordinator (OBS-004)
  - BugPatternDetector (DEV-004)
  - EventBackbone
  - PersistenceManager

Uses statistical analysis of historical telemetry, error patterns, and
confidence trajectories to predict failures before they happen and
pre-emptively trigger remediation.

Safety invariants:
  - Never blocks the main execution path (analysis is on-demand)
  - Bounded memory: sliding windows with configurable max size
  - Full audit trail via EventBackbone and PersistenceManager
  - Compatible with GovernanceKernel authority bands
  - Thread-safe: all shared state guarded by Lock

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_SIZE = 100          # max telemetry events per sliding window
_DEFAULT_ERROR_WINDOW = 50          # max error records per sliding window
_DEFAULT_MAX_PREDICTIONS = 1_000    # max stored prediction results
_LATENCY_BASELINE_RATIO = 2.0       # p95 / baseline threshold
_ERROR_ACCEL_WINDOWS = 3            # consecutive windows with rising error rate
_CONFIDENCE_DRIFT_THRESHOLD = 0.05  # drift magnitude (slope) to trigger a signal
_PATTERN_COOLDOWN_SEC = 3600        # 1 hour recurrence cooldown
_WEIGHT_MIN = 0.1
_WEIGHT_MAX = 2.0
_WEIGHT_INCREASE = 0.1
_WEIGHT_DECREASE = 0.15


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FailureSignal:
    """A weak signal that could indicate an upcoming failure."""

    signal_id: str
    signal_type: str          # latency_spike | error_rate_increase | confidence_drift
                              # resource_pressure | pattern_recurrence
    severity_score: float     # 0.0-1.0
    confidence: float         # 0.0-1.0
    source_component: str
    detected_at: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "severity_score": self.severity_score,
            "confidence": self.confidence,
            "source_component": self.source_component,
            "detected_at": self.detected_at,
            "context": self.context,
        }


@dataclass
class PredictionResult:
    """A structured prediction of an upcoming failure."""

    prediction_id: str
    predicted_failure_type: str
    probability: float        # 0.0-1.0
    estimated_time_to_failure_sec: float
    recommended_preemptive_action: str
    supporting_signals: List[FailureSignal] = field(default_factory=list)
    status: str = "predicted"   # predicted | preempted | false_positive | materialized
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "predicted_failure_type": self.predicted_failure_type,
            "probability": self.probability,
            "estimated_time_to_failure_sec": self.estimated_time_to_failure_sec,
            "recommended_preemptive_action": self.recommended_preemptive_action,
            "supporting_signals": [s.to_dict() for s in self.supporting_signals],
            "status": self.status,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# AdaptiveWeightManager
# ---------------------------------------------------------------------------

class AdaptiveWeightManager:
    """Learns from prediction accuracy per heuristic detector.

    Increases weights for heuristics that correctly predict failures.
    Decreases weights for heuristics that produce false positives.
    Weights are bounded within [_WEIGHT_MIN, _WEIGHT_MAX].
    """

    _HEURISTICS = (
        "latency_degradation",
        "error_rate_acceleration",
        "confidence_drift",
        "resource_exhaustion",
        "recurring_patterns",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._weights: Dict[str, float] = {h: 1.0 for h in self._HEURISTICS}
        self._hits: Dict[str, int] = {h: 0 for h in self._HEURISTICS}
        self._misses: Dict[str, int] = {h: 0 for h in self._HEURISTICS}

    def get_weight(self, heuristic: str) -> float:
        """Return the current weight for a heuristic (default 1.0)."""
        with self._lock:
            return self._weights.get(heuristic, 1.0)

    def record_hit(self, heuristic: str) -> None:
        """Record a true-positive prediction for a heuristic."""
        with self._lock:
            if heuristic not in self._weights:
                self._weights[heuristic] = 1.0
                self._hits[heuristic] = 0
                self._misses[heuristic] = 0
            self._hits[heuristic] += 1
            new_w = min(self._weights[heuristic] + _WEIGHT_INCREASE, _WEIGHT_MAX)
            self._weights[heuristic] = new_w

    def record_miss(self, heuristic: str) -> None:
        """Record a false-positive prediction for a heuristic."""
        with self._lock:
            if heuristic not in self._weights:
                self._weights[heuristic] = 1.0
                self._hits[heuristic] = 0
                self._misses[heuristic] = 0
            self._misses[heuristic] += 1
            new_w = max(self._weights[heuristic] - _WEIGHT_DECREASE, _WEIGHT_MIN)
            self._weights[heuristic] = new_w

    def get_accuracy(self, heuristic: str) -> float:
        """Return hit-rate accuracy for a heuristic (0.0 if no data)."""
        with self._lock:
            hits = self._hits.get(heuristic, 0)
            misses = self._misses.get(heuristic, 0)
            total = hits + misses
            return hits / total if total > 0 else 0.0

    def get_all_weights(self) -> Dict[str, float]:
        """Return a snapshot of all heuristic weights."""
        with self._lock:
            return dict(self._weights)


# ---------------------------------------------------------------------------
# PredictiveFailureEngine
# ---------------------------------------------------------------------------

class PredictiveFailureEngine:
    """Predicts failures before they happen using statistical heuristics.

    Design Label: PRED-001
    Owner: Backend Team

    Usage::

        engine = PredictiveFailureEngine(
            self_fix_loop=loop,
            healing_coordinator=coordinator,
            bug_detector=detector,
            event_backbone=backbone,
            persistence_manager=pm,
        )
        engine.ingest_telemetry({"component": "api-gw", "response_time_ms": 320})
        predictions = engine.analyze()
        for p in predictions:
            engine.preempt(p)
    """

    def __init__(
        self,
        self_fix_loop=None,
        healing_coordinator=None,
        bug_detector=None,
        event_backbone=None,
        persistence_manager=None,
        window_size: int = _DEFAULT_WINDOW_SIZE,
        error_window: int = _DEFAULT_ERROR_WINDOW,
        max_predictions: int = _DEFAULT_MAX_PREDICTIONS,
    ) -> None:
        self._fix_loop = self_fix_loop
        self._coordinator = healing_coordinator
        self._detector = bug_detector
        self._backbone = event_backbone
        self._pm = persistence_manager

        self._window_size = window_size
        self._error_window = error_window
        self._max_predictions = max_predictions

        self._lock = threading.Lock()

        # Sliding windows
        self._telemetry: Deque[Dict[str, Any]] = deque(maxlen=window_size)
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=error_window)

        # Predictions registry
        self._predictions: List[PredictionResult] = []

        # Baseline response time (computed lazily)
        self._baseline_response_time_ms: Optional[float] = None

        # Error rate per window snapshot (list of rates for derivative check)
        self._error_rate_history: List[float] = []

        # Confidence score history per component
        self._confidence_history: Dict[str, List[float]] = {}

        # Seen bug pattern fingerprints with timestamp for recurrence detection
        self._seen_patterns: Dict[str, float] = {}

        # Adaptive weight manager
        self._weights = AdaptiveWeightManager()

    # ------------------------------------------------------------------
    # Public API — Ingestion
    # ------------------------------------------------------------------

    def ingest_telemetry(self, event: Dict[str, Any]) -> None:
        """Feed a telemetry event into the engine's sliding window.

        Expected keys (all optional):
          - component (str)
          - response_time_ms (float)
          - confidence (float)
          - memory_mb (float)
          - cpu_percent (float)
          - registered_procedures (int)
          - runtime_config_size (int)
        """
        with self._lock:
            capped_append(self._telemetry, dict(event))
            # Track confidence history per component
            comp = event.get("component", "unknown")
            conf = event.get("confidence")
            if conf is not None:
                if comp not in self._confidence_history:
                    self._confidence_history[comp] = []
                capped_append(self._confidence_history[comp], float(conf))

    def ingest_error(self, error_record: Dict[str, Any]) -> None:
        """Feed an error record into the engine's sliding window.

        Expected keys (all optional):
          - message (str)
          - component (str)
          - error_type (str)
          - fingerprint (str)
          - timestamp (str)
        """
        with self._lock:
            capped_append(self._errors, dict(error_record))
            # Track error rate window
            self._error_rate_history.append(len(self._errors))
            # Bound history list to avoid unbounded growth
            if len(self._error_rate_history) > self._window_size:
                del self._error_rate_history[:self._window_size // 10]

    # ------------------------------------------------------------------
    # Public API — Analysis
    # ------------------------------------------------------------------

    def analyze(self) -> List[PredictionResult]:
        """Run all detection heuristics and return new PredictionResults."""
        signals: List[FailureSignal] = []

        with self._lock:
            signals += self._detect_latency_degradation()
            signals += self._detect_error_rate_acceleration()
            signals += self._detect_confidence_drift()
            signals += self._detect_resource_exhaustion()
            signals += self._detect_recurring_patterns()

        if not signals:
            return []

        # Group signals into predictions
        new_predictions: List[PredictionResult] = []
        for sig in signals:
            weight = self._weights.get_weight(_signal_type_to_heuristic(sig.signal_type))
            probability = min(sig.severity_score * sig.confidence * weight, 1.0)
            pred = PredictionResult(
                prediction_id=f"pred-{uuid.uuid4().hex[:8]}",
                predicted_failure_type=sig.signal_type,
                probability=probability,
                estimated_time_to_failure_sec=_estimate_ttf(sig),
                recommended_preemptive_action=_recommend_action(sig.signal_type),
                supporting_signals=[sig],
                status="predicted",
            )
            new_predictions.append(pred)

        with self._lock:
            for pred in new_predictions:
                capped_append(self._predictions, pred, max_size=self._max_predictions)

        for pred in new_predictions:
            self._publish(pred, "PREDICTION_GENERATED")
            self._persist(pred)

        return new_predictions

    # ------------------------------------------------------------------
    # Public API — Preemption
    # ------------------------------------------------------------------

    def preempt(self, prediction: PredictionResult) -> bool:
        """Trigger SelfFixLoop or SelfHealingCoordinator proactively.

        Returns True if a preemptive action was initiated, False otherwise.
        """
        if prediction.status != "predicted":
            return False

        initiated = False

        # Try SelfFixLoop first
        if self._fix_loop is not None:
            try:
                self._fix_loop.run_loop(max_iterations=1)
                initiated = True
            except Exception as exc:
                logger.warning("SelfFixLoop preemption failed: %s", exc)

        # Fall back to SelfHealingCoordinator
        if not initiated and self._coordinator is not None:
            try:
                self._coordinator.handle_failure(
                    category=prediction.predicted_failure_type,
                    context={"prediction_id": prediction.prediction_id},
                )
                initiated = True
            except Exception as exc:
                logger.warning("SelfHealingCoordinator preemption failed: %s", exc)

        with self._lock:
            prediction.status = "preempted" if initiated else prediction.status

        if initiated:
            self._publish(prediction, "PREDICTION_PREEMPTED")

        return initiated

    # ------------------------------------------------------------------
    # Public API — Outcome feedback
    # ------------------------------------------------------------------

    def record_outcome(self, prediction_id: str, actual_outcome: str) -> bool:
        """Record actual outcome of a prediction for adaptive learning.

        actual_outcome should be 'materialized' or 'false_positive'.
        Returns True if prediction was found and updated.
        """
        with self._lock:
            pred = self._find_prediction(prediction_id)
            if pred is None:
                return False
            pred.status = actual_outcome

        # Update heuristic weights based on outcome
        for sig in pred.supporting_signals:
            heuristic = _signal_type_to_heuristic(sig.signal_type)
            if actual_outcome == "materialized":
                self._weights.record_hit(heuristic)
            elif actual_outcome == "false_positive":
                self._weights.record_miss(heuristic)

        event_key = (
            "PREDICTION_MATERIALIZED"
            if actual_outcome == "materialized"
            else "PREDICTION_FALSE_POSITIVE"
        )
        self._publish(pred, event_key)
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_predictions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent predictions as dicts."""
        with self._lock:
            preds = list(self._predictions)
        return [p.to_dict() for p in preds[-limit:]]

    def get_weights(self) -> Dict[str, float]:
        """Return current heuristic weights."""
        return self._weights.get_all_weights()

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            telemetry_count = len(self._telemetry)
            error_count = len(self._errors)
            prediction_count = len(self._predictions)
        return {
            "telemetry_window_size": telemetry_count,
            "error_window_size": error_count,
            "total_predictions": prediction_count,
            "heuristic_weights": self._weights.get_all_weights(),
        }

    # ------------------------------------------------------------------
    # Heuristic detectors (called under lock)
    # ------------------------------------------------------------------

    def _detect_latency_degradation(self) -> List[FailureSignal]:
        """Sliding window over response times; signal if p95 > 2× baseline."""
        times = [
            t["response_time_ms"]
            for t in self._telemetry
            if "response_time_ms" in t
        ]
        if len(times) < 5:
            return []

        baseline = self._baseline_response_time_ms
        if baseline is None:
            # Use first half of window as baseline
            half = max(len(times) // 2, 1)
            baseline = sum(times[:half]) / (len(times[:half]) or 1)
            self._baseline_response_time_ms = baseline

        sorted_times = sorted(times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times) - 1)]

        if p95 < baseline * _LATENCY_BASELINE_RATIO:
            return []

        severity = min((p95 / (baseline or 1)) / (_LATENCY_BASELINE_RATIO * 2), 1.0)
        return [FailureSignal(
            signal_id=f"sig-{uuid.uuid4().hex[:8]}",
            signal_type="latency_spike",
            severity_score=severity,
            confidence=0.75,
            source_component="telemetry",
            detected_at=datetime.now(timezone.utc).isoformat(),
            context={"p95_ms": p95, "baseline_ms": baseline},
        )]

    def _detect_error_rate_acceleration(self) -> List[FailureSignal]:
        """Signal if the error rate derivative has been positive for N consecutive windows."""
        history = list(self._error_rate_history)
        if len(history) < _ERROR_ACCEL_WINDOWS + 1:
            return []

        recent = history[-(  _ERROR_ACCEL_WINDOWS + 1):]
        # Check if all consecutive differences are positive
        derivatives = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
        if not all(d > 0 for d in derivatives):
            return []

        rate_delta = recent[-1] - recent[0]
        severity = min(rate_delta / (recent[0] or 1), 1.0)
        return [FailureSignal(
            signal_id=f"sig-{uuid.uuid4().hex[:8]}",
            signal_type="error_rate_increase",
            severity_score=max(severity, 0.0),
            confidence=0.8,
            source_component="error_tracker",
            detected_at=datetime.now(timezone.utc).isoformat(),
            context={"recent_counts": recent, "derivatives": derivatives},
        )]

    def _detect_confidence_drift(self) -> List[FailureSignal]:
        """Signal if confidence scores trend downward across multiple components."""
        drifts: List[Tuple[str, float]] = []

        for comp, scores in self._confidence_history.items():
            if len(scores) < 3:
                continue
            trend = _linear_trend(scores)
            if trend < -_CONFIDENCE_DRIFT_THRESHOLD:
                drifts.append((comp, trend))

        if not drifts:
            return []

        worst_comp, worst_drift = min(drifts, key=lambda x: x[1])
        severity = min(abs(worst_drift), 1.0)
        return [FailureSignal(
            signal_id=f"sig-{uuid.uuid4().hex[:8]}",
            signal_type="confidence_drift",
            severity_score=severity,
            confidence=0.7,
            source_component=worst_comp,
            detected_at=datetime.now(timezone.utc).isoformat(),
            context={"drifting_components": [c for c, _ in drifts], "worst_drift": worst_drift},
        )]

    def _detect_resource_exhaustion(self) -> List[FailureSignal]:
        """Signal if resource metrics (memory, config store, procedures) are high."""
        signals: List[FailureSignal] = []
        recent = list(self._telemetry)
        if not recent:
            return []

        latest = recent[-1]

        # Check memory proxy
        memory_mb = latest.get("memory_mb")
        if memory_mb is not None and memory_mb > 0:
            # Signal if memory exceeds 90% of a 4 GB reference
            usage_ratio = memory_mb / 4096.0
            if usage_ratio > 0.9:
                signals.append(FailureSignal(
                    signal_id=f"sig-{uuid.uuid4().hex[:8]}",
                    signal_type="resource_pressure",
                    severity_score=min(usage_ratio, 1.0),
                    confidence=0.85,
                    source_component=latest.get("component", "runtime"),
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    context={"memory_mb": memory_mb, "usage_ratio": usage_ratio},
                ))

        # Check runtime config store size
        config_size = latest.get("runtime_config_size")
        if config_size is not None and config_size > 10_000:
            signals.append(FailureSignal(
                signal_id=f"sig-{uuid.uuid4().hex[:8]}",
                signal_type="resource_pressure",
                severity_score=min(config_size / 50_000, 1.0),
                confidence=0.65,
                source_component=latest.get("component", "runtime"),
                detected_at=datetime.now(timezone.utc).isoformat(),
                context={"runtime_config_size": config_size},
            ))

        # Check registered procedure count
        proc_count = latest.get("registered_procedures")
        if proc_count is not None and proc_count > 500:
            signals.append(FailureSignal(
                signal_id=f"sig-{uuid.uuid4().hex[:8]}",
                signal_type="resource_pressure",
                severity_score=min(proc_count / 5_000, 1.0),
                confidence=0.6,
                source_component=latest.get("component", "runtime"),
                detected_at=datetime.now(timezone.utc).isoformat(),
                context={"registered_procedures": proc_count},
            ))

        return signals

    def _detect_recurring_patterns(self) -> List[FailureSignal]:
        """Signal if a previously-fixed bug pattern reappears within cooldown window."""
        signals: List[FailureSignal] = []
        now = time.time()
        errors = list(self._errors)

        # Optionally pull patterns from BugPatternDetector
        known_fingerprints: Dict[str, str] = {}
        if self._detector is not None:
            try:
                for p in self._detector.get_patterns():
                    fp = p.get("fingerprint", "")
                    if fp:
                        known_fingerprints[fp] = p.get("representative_message", "")
            except Exception as exc:
                logger.debug("Could not fetch patterns from BugPatternDetector: %s", exc)

        for err in errors:
            fp = err.get("fingerprint", "")
            if not fp:
                continue
            last_seen = self._seen_patterns.get(fp)
            if last_seen is not None and (now - last_seen) < _PATTERN_COOLDOWN_SEC:
                # It appeared before and is recurring within cooldown
                elapsed = now - last_seen
                severity = 1.0 - (elapsed / _PATTERN_COOLDOWN_SEC)
                msg = known_fingerprints.get(fp, err.get("message", ""))
                signals.append(FailureSignal(
                    signal_id=f"sig-{uuid.uuid4().hex[:8]}",
                    signal_type="pattern_recurrence",
                    severity_score=max(severity, 0.1),
                    confidence=0.9,
                    source_component=err.get("component", "unknown"),
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    context={
                        "fingerprint": fp,
                        "seconds_since_last": elapsed,
                        "representative_message": msg[:200] if msg else "",
                    },
                ))
            # Record or refresh last-seen time
            self._seen_patterns[fp] = now

        return signals

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_prediction(self, prediction_id: str) -> Optional[PredictionResult]:
        """Find a prediction by ID (must be called under lock)."""
        for pred in self._predictions:
            if pred.prediction_id == prediction_id:
                return pred
        return None

    def _publish(self, prediction: PredictionResult, event_key: str) -> None:
        """Publish a prediction event to the EventBackbone."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            event_type = EventType[event_key]
            self._backbone.publish(
                event_type,
                payload=prediction.to_dict(),
                source="predictive_failure_engine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)

    def _persist(self, prediction: PredictionResult) -> None:
        """Persist a prediction record via PersistenceManager."""
        if self._pm is None:
            return
        try:
            self._pm.save_document(prediction.prediction_id, prediction.to_dict())
        except Exception as exc:
            logger.debug("PersistenceManager persist skipped: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _signal_type_to_heuristic(signal_type: str) -> str:
    """Map a signal_type string to its heuristic name."""
    mapping = {
        "latency_spike": "latency_degradation",
        "error_rate_increase": "error_rate_acceleration",
        "confidence_drift": "confidence_drift",
        "resource_pressure": "resource_exhaustion",
        "pattern_recurrence": "recurring_patterns",
    }
    return mapping.get(signal_type, signal_type)


def _estimate_ttf(signal: FailureSignal) -> float:
    """Estimate time-to-failure in seconds from a signal."""
    # Higher severity → shorter estimated time to failure
    base_sec = 3600.0
    return base_sec * (1.0 - signal.severity_score * 0.9)


def _recommend_action(signal_type: str) -> str:
    """Return a recommended preemptive action for a signal type."""
    actions = {
        "latency_spike": "Scale out affected service or trigger cache warm-up",
        "error_rate_increase": "Run SelfFixLoop diagnostics and inspect error logs",
        "confidence_drift": "Trigger recalibration cycle via SelfImprovementEngine",
        "resource_pressure": "Release idle resources or expand resource limits",
        "pattern_recurrence": "Re-apply previously successful fix via SelfHealingCoordinator",
    }
    return actions.get(signal_type, "Investigate and escalate to SelfFixLoop")


def _linear_trend(values: List[float]) -> float:
    """Return the slope of a simple linear regression over values.

    Positive slope → values rising; negative slope → values falling.
    """
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / (n or 1)
    mean_y = sum(values) / (n or 1)
    numerator = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator
