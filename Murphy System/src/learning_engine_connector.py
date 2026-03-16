"""
Learning Engine Connector for Murphy System.

Design Label: LEARN-001 — Closed Learning Loop (EventBackbone wiring)
Owner: Platform Engineering
Dependencies:
  - EventBackbone (TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED,
                   AUTOMATION_EXECUTED, THRESHOLD_UPDATED, GATE_EVOLVED)
  - FeedbackIntegrator  (feedback_integrator.py)
  - PatternRecognizer   (learning_engine/learning_engine.py)
  - FeedbackCollector   (learning_engine/learning_engine.py)
  - PerformancePredictor (performance_predictor.py)
  - DomainGateGenerator  (domain_gate_generator.py)

Completes the closed ML loop described in the Storyline (Ch. 16–17)::

    EventBackbone events
         │
         ▼
    FeedbackIntegrator ── FeedbackSignal → TypedStateVector adjustments
         │
         ▼  (outcome records)
    FeedbackCollector / PatternRecognizer  (learning_engine)
         │
         ▼  (LearnedPattern list)
    PerformancePredictor  → PredictionResult (threshold recommendations)
         │
         ▼  (recommended_threshold per key)
    Gate evolution: DomainGate.confidence_threshold auto-adjusted
         │
         ▼  (publish THRESHOLD_UPDATED / GATE_EVOLVED events)
    EventBackbone

Safety invariants:
  - Thread-safe: all mutable shared state protected by a Lock.
  - Bounded: all history lists capped via capped_append.
  - Conservative: threshold changes bounded by PerformancePredictor.
  - Fail-safe: every external call is wrapped; errors are logged, not raised.

Metrics tracked:
  - learning_rate_ema           : exponentially-weighted moving average of
                                  the proportion of events that produced a
                                  pattern or threshold update.
  - pattern_count               : total patterns detected since startup.
  - prediction_accuracy_ema     : EWMA of |predicted_success_rate −
                                  actual_success_rate| (lower is better).
  - threshold_drift_total       : sum of |delta| across all threshold
                                  updates.
  - gate_evolution_count        : total gate confidence_threshold updates.
  - events_processed_total      : total events consumed.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import deque
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

_MAX_HISTORY = 500
_EMA_ALPHA = 0.1          # Learning rate for EMA metrics


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class LearningCycleResult:
    """Summary of one run of :meth:`LearningEngineConnector.run_cycle`."""

    cycle_id: str
    events_drained: int
    outcomes_fed: int
    patterns_detected: int
    predictions_generated: int
    thresholds_updated: int
    gates_evolved: int
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "events_drained": self.events_drained,
            "outcomes_fed": self.outcomes_fed,
            "patterns_detected": self.patterns_detected,
            "predictions_generated": self.predictions_generated,
            "thresholds_updated": self.thresholds_updated,
            "gates_evolved": self.gates_evolved,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# LearningEngineConnector
# ---------------------------------------------------------------------------

class LearningEngineConnector:
    """Wires EventBackbone events through the full learning pipeline.

    Typical usage::

        connector = LearningEngineConnector(
            event_backbone=backbone,
            feedback_integrator=integrator,
            pattern_recognizer=recognizer,
            feedback_collector=collector,
            performance_predictor=predictor,
            gate_registry={"gate-1": domain_gate_obj, ...},
            confidence_calculator=calc,
            gate_generator=generator,
        )
        # Events are queued automatically via subscriptions.
        # Call run_cycle() to drain the queue and execute the full loop.
        result = connector.run_cycle()

    *gate_registry* is an optional ``dict[gate_id, DomainGate]`` —
    gates whose ``confidence_threshold`` will be auto-adjusted when the
    predictor recommends a new threshold for the corresponding key.

    *confidence_calculator* is an optional :class:`ConfidenceCalculator`
    whose adaptive thresholds (bootstrap floor, sparse threshold) are
    updated when the predictor recommends a global threshold change.

    *gate_generator* is an optional :class:`DomainGateGenerator` whose
    ``default_confidence_threshold`` is updated so that all newly
    generated gates inherit the learned threshold.

    All constructor arguments are optional; missing components cause the
    relevant pipeline stage to be skipped gracefully.
    """

    def __init__(
        self,
        event_backbone=None,
        feedback_integrator=None,
        pattern_recognizer=None,
        feedback_collector=None,
        performance_predictor=None,
        gate_registry: Optional[Dict[str, Any]] = None,
        state_vector=None,
        confidence_calculator=None,
        gate_generator=None,
    ) -> None:
        self._lock = threading.Lock()
        self._backbone = event_backbone
        self._feedback_integrator = feedback_integrator
        self._pattern_recognizer = pattern_recognizer
        self._feedback_collector = feedback_collector
        self._predictor = performance_predictor
        self._gate_registry: Dict[str, Any] = gate_registry or {}
        self._state_vector = state_vector
        self._confidence_calculator = confidence_calculator
        self._gate_generator = gate_generator

        # Incoming event queue (drained during run_cycle)
        self._pending_events: List[Dict[str, Any]] = []

        # Cycle history
        self._cycle_history: deque = deque(maxlen=100)

        # Metrics
        self._metrics: Dict[str, Any] = {
            "learning_rate_ema": 0.0,
            "pattern_count": 0,
            "prediction_accuracy_ema": 0.0,
            "threshold_drift_total": 0.0,
            "gate_evolution_count": 0,
            "events_processed_total": 0,
            "confidence_calculator_updates": 0,
            "gate_generator_updates": 0,
        }

        if self._backbone is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Gate registry management
    # ------------------------------------------------------------------

    def register_gate(self, gate_id: str, gate: Any) -> None:
        """Register a :class:`DomainGate` for threshold evolution."""
        with self._lock:
            self._gate_registry[gate_id] = gate

    def unregister_gate(self, gate_id: str) -> None:
        """Remove a gate from evolution tracking."""
        with self._lock:
            self._gate_registry.pop(gate_id, None)

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to all relevant event types on the EventBackbone."""
        try:
            from event_backbone import EventType

            def _on_task_completed(event) -> None:
                self._enqueue_event("task_completed", event)

            def _on_task_failed(event) -> None:
                self._enqueue_event("task_failed", event)

            def _on_gate_evaluated(event) -> None:
                self._enqueue_event("gate_evaluated", event)

            def _on_automation_executed(event) -> None:
                self._enqueue_event("automation_executed", event)

            self._backbone.subscribe(EventType.TASK_COMPLETED, _on_task_completed)
            self._backbone.subscribe(EventType.TASK_FAILED, _on_task_failed)
            self._backbone.subscribe(EventType.GATE_EVALUATED, _on_gate_evaluated)
            self._backbone.subscribe(EventType.AUTOMATION_EXECUTED, _on_automation_executed)

            logger.info("LearningEngineConnector subscribed to EventBackbone")
        except Exception as exc:
            logger.warning("LearningEngineConnector: failed to subscribe: %s", exc)

    def _enqueue_event(self, event_type: str, event: Any) -> None:
        """Normalise an event and add it to the pending queue."""
        payload = event.payload if hasattr(event, "payload") else {}
        if event_type == "task_completed":
            success = True
        elif event_type == "task_failed":
            success = False
        elif event_type == "automation_executed":
            success = payload.get("passed", True)
        else:
            success = payload.get("passed", True)
        record = {
            "event_type": event_type,
            "task_id": payload.get("task_id", f"evt-{uuid.uuid4().hex[:8]}"),
            "gate_id": payload.get("gate_id", ""),
            "gate_name": payload.get("gate_name", ""),
            "success": success,
            "confidence": float(payload.get("confidence", 0.85)),
            "outcome": "success" if event_type in ("task_completed",)
                       else ("failure" if event_type == "task_failed" else "gate"),
            "metrics": payload.get("metrics", {}),
            "source": payload.get("source", event_type),
            "payload": payload,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._pending_events, record, max_size=_MAX_HISTORY)

    # ------------------------------------------------------------------
    # Core learning cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> LearningCycleResult:
        """Execute one full learning cycle.

        Steps:
        1. Drain the pending event queue.
        2. Feed outcomes into FeedbackIntegrator and FeedbackCollector.
        3. Run PatternRecognizer over any recorded metrics.
        4. Feed detected patterns to PerformancePredictor.
        5. Apply threshold recommendations to registered DomainGates.
        6. Update connector-level metrics.
        7. Publish THRESHOLD_UPDATED / GATE_EVOLVED events.
        8. Return a :class:`LearningCycleResult` summary.
        """
        cycle_id = f"learn-{uuid.uuid4().hex[:8]}"
        events_drained = 0
        outcomes_fed = 0
        patterns_detected = 0
        predictions_generated = 0
        thresholds_updated = 0
        gates_evolved = 0

        # 1 — Drain pending events
        with self._lock:
            pending = list(self._pending_events)
            self._pending_events.clear()
        events_drained = len(pending)

        # 2 — Feed into FeedbackIntegrator and FeedbackCollector
        for record in pending:
            # 2a — FeedbackIntegrator (TypedStateVector adjustment)
            if self._feedback_integrator is not None and self._state_vector is not None:
                try:
                    from feedback_integrator import FeedbackSignal
                    signal = FeedbackSignal(
                        signal_type=(
                            "correction" if record["event_type"] == "task_completed"
                            else "feedback"
                        ),
                        source_task_id=record["task_id"],
                        original_confidence=record["confidence"],
                        corrected_confidence=(
                            record["confidence"] if record["success"] else None
                        ),
                        affected_state_variables=self._state_variables_for(record),
                    )
                    self._feedback_integrator.integrate(signal, self._state_vector)
                except Exception as exc:
                    logger.warning(
                        "LearningEngineConnector: FeedbackIntegrator step failed: %s", exc
                    )

            # 2b — FeedbackCollector (empirical success-rate tracking)
            if self._feedback_collector is not None:
                try:
                    self._feedback_collector.collect_feedback(
                        feedback_type=record["event_type"],
                        operation_id=record["task_id"],
                        success=record["success"],
                        confidence=record["confidence"],
                        feedback_data=record.get("metrics", {}),
                    )
                    outcomes_fed += 1
                except Exception as exc:
                    logger.warning(
                        "LearningEngineConnector: FeedbackCollector step failed: %s", exc
                    )

            # 2c — PerformancePredictor outcome recording
            if self._predictor is not None:
                try:
                    key = self._outcome_key(record)
                    self._predictor.record_outcome(
                        key=key,
                        success=record["success"],
                        confidence=record["confidence"],
                    )
                except Exception as exc:
                    logger.warning(
                        "LearningEngineConnector: predictor.record_outcome failed: %s", exc
                    )

        # 3 — PatternRecognizer
        patterns: List[Any] = []
        if self._pattern_recognizer is not None and events_drained > 0:
            try:
                # Build a minimal PerformanceMetric list from pending events so
                # the recognizer has something to analyse.
                from learning_engine.learning_engine import PerformanceMetric
                metrics_list = [
                    PerformanceMetric(
                        metric_name=self._outcome_key(r),
                        value=r["confidence"],
                        timestamp=datetime.now(timezone.utc),
                        context=r.get("metrics", {}),
                    )
                    for r in pending
                ]
                if metrics_list:
                    patterns = self._pattern_recognizer.analyze_metrics(metrics_list)
                    patterns_detected = len(patterns)
                    with self._lock:
                        self._metrics["pattern_count"] += patterns_detected
            except Exception as exc:
                logger.warning(
                    "LearningEngineConnector: PatternRecognizer step failed: %s", exc
                )

        # 4 — PerformancePredictor
        prediction_results: List[Any] = []
        if self._predictor is not None:
            try:
                prediction_results = self._predictor.predict_from_patterns(patterns)
                predictions_generated = len(prediction_results)
            except Exception as exc:
                logger.warning(
                    "LearningEngineConnector: PerformancePredictor step failed: %s", exc
                )

        # 5 — Gate evolution: apply threshold recommendations
        # Compute global (average) recommended threshold across all predictions
        # for updating ConfidenceCalculator and DomainGateGenerator.
        global_threshold_sum = 0.0
        global_threshold_count = 0

        for pred in prediction_results:
            key = pred.key
            new_threshold = pred.recommended_threshold
            delta = pred.threshold_delta

            # Update gates whose gate_id or name matches the prediction key
            for gate_id, gate in list(self._gate_registry.items()):
                if gate_id == key or getattr(gate, "name", None) == key:
                    try:
                        old_threshold = getattr(gate, "confidence_threshold", 0.85)
                        gate.confidence_threshold = new_threshold
                        gates_evolved += 1
                        with self._lock:
                            self._metrics["gate_evolution_count"] += 1
                            self._metrics["threshold_drift_total"] += abs(delta)
                        self._publish_gate_evolved(
                            gate_id=gate_id,
                            gate_name=getattr(gate, "name", gate_id),
                            old_threshold=old_threshold,
                            new_threshold=new_threshold,
                            delta=delta,
                        )
                        logger.debug(
                            "Gate %s threshold evolved: %.4f → %.4f (delta=%.4f)",
                            gate_id, old_threshold, new_threshold, delta,
                        )
                    except Exception as exc:
                        logger.warning(
                            "LearningEngineConnector: gate evolution failed for %s: %s",
                            gate_id, exc,
                        )

            # Publish a THRESHOLD_UPDATED event and count one update per key
            if abs(delta) > 1e-6:
                thresholds_updated += 1
                self._publish_threshold_updated(key, new_threshold, delta)

            global_threshold_sum += new_threshold
            global_threshold_count += 1

        # 5b — Update ConfidenceCalculator and DomainGateGenerator with the
        #      global (averaged) threshold from all predictions this cycle.
        if global_threshold_count > 0:
            global_avg = global_threshold_sum / global_threshold_count
            if self._confidence_calculator is not None:
                try:
                    self._confidence_calculator.update_thresholds(
                        bootstrap_floor=global_avg * 0.6,  # floor = 60 % of threshold
                    )
                    with self._lock:
                        self._metrics["confidence_calculator_updates"] += 1
                    logger.debug(
                        "ConfidenceCalculator bootstrap_floor updated to %.4f",
                        global_avg * 0.6,
                    )
                except Exception as exc:
                    logger.warning(
                        "LearningEngineConnector: ConfidenceCalculator update failed: %s",
                        exc,
                    )
            if self._gate_generator is not None:
                try:
                    self._gate_generator.update_default_threshold(global_avg)
                    with self._lock:
                        self._metrics["gate_generator_updates"] += 1
                    logger.debug(
                        "DomainGateGenerator default threshold updated to %.4f",
                        global_avg,
                    )
                except Exception as exc:
                    logger.warning(
                        "LearningEngineConnector: DomainGateGenerator update failed: %s",
                        exc,
                    )

        # 6 — Update connector-level metrics
        self._update_ema_metrics(events_drained, patterns_detected)

        # 7 — Build and store cycle result
        result = LearningCycleResult(
            cycle_id=cycle_id,
            events_drained=events_drained,
            outcomes_fed=outcomes_fed,
            patterns_detected=patterns_detected,
            predictions_generated=predictions_generated,
            thresholds_updated=thresholds_updated,
            gates_evolved=gates_evolved,
        )
        with self._lock:
            self._cycle_history.append(result)
            self._metrics["events_processed_total"] += events_drained

        logger.info(
            "LearningEngineConnector cycle %s: events=%d outcomes=%d "
            "patterns=%d predictions=%d thresholds=%d gates=%d",
            cycle_id, events_drained, outcomes_fed, patterns_detected,
            predictions_generated, thresholds_updated, gates_evolved,
        )
        return result

    # ------------------------------------------------------------------
    # Status / metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Return a snapshot of learning metrics."""
        with self._lock:
            return dict(self._metrics)

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of the connector."""
        with self._lock:
            return {
                "pending_events": len(self._pending_events),
                "cycles_completed": len(self._cycle_history),
                "gates_registered": len(self._gate_registry),
                "backbone_attached": self._backbone is not None,
                "feedback_integrator_attached": self._feedback_integrator is not None,
                "pattern_recognizer_attached": self._pattern_recognizer is not None,
                "feedback_collector_attached": self._feedback_collector is not None,
                "predictor_attached": self._predictor is not None,
                "confidence_calculator_attached": self._confidence_calculator is not None,
                "gate_generator_attached": self._gate_generator is not None,
                "metrics": dict(self._metrics),
            }

    def get_cycle_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent cycle summaries."""
        with self._lock:
            recent = list(self._cycle_history)[-limit:]
        return [r.to_dict() for r in recent]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _outcome_key(record: Dict[str, Any]) -> str:
        """Derive a stable string key from an event record."""
        source = record.get("source", "")
        gate_id = record.get("gate_id", "")
        if gate_id:
            return f"gate:{gate_id}"
        event_type = record.get("event_type", "unknown")
        return f"task:{source}" if source else f"event:{event_type}"

    @staticmethod
    def _state_variables_for(record: Dict[str, Any]) -> List[str]:
        """Derive state variable names that should be updated for this event."""
        variables = []
        if record.get("event_type") in ("task_completed", "task_failed"):
            variables.append("task_confidence")
        if record.get("gate_id"):
            variables.append(f"gate_{record['gate_id']}_confidence")
        if not variables:
            variables.append("system_confidence")
        return variables

    def _update_ema_metrics(self, events_drained: int, patterns_detected: int) -> None:
        """Update exponentially-weighted moving average metrics."""
        if events_drained == 0:
            return
        learning_rate = patterns_detected / events_drained
        with self._lock:
            self._metrics["learning_rate_ema"] = (
                (1.0 - _EMA_ALPHA) * self._metrics["learning_rate_ema"]
                + _EMA_ALPHA * learning_rate
            )

    def _publish_threshold_updated(
        self, key: str, new_threshold: float, delta: float
    ) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                EventType.THRESHOLD_UPDATED,
                {
                    "source": "learning_engine_connector",
                    "key": key,
                    "new_threshold": new_threshold,
                    "delta": delta,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector: threshold publish skipped: %s", exc)

    def _publish_gate_evolved(
        self,
        gate_id: str,
        gate_name: str,
        old_threshold: float,
        new_threshold: float,
        delta: float,
    ) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                EventType.GATE_EVOLVED,
                {
                    "source": "learning_engine_connector",
                    "gate_id": gate_id,
                    "gate_name": gate_name,
                    "old_threshold": old_threshold,
                    "new_threshold": new_threshold,
                    "delta": delta,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector: gate_evolved publish skipped: %s", exc)


__all__ = [
    "LearningCycleResult",
    "LearningEngineConnector",
]
