"""
Learning Engine Connector — closed-loop ML wiring hub.

Bridges the EventBackbone and the LearningEngine so every task result,
gate decision, and automation execution is automatically fed back into
the learning pipeline:

    EventBackbone  ──► LearningEngineConnector ──► LearningEngine
                                                        │
                                              pattern recognition
                                              insight generation
                                                        │
                                              AdaptiveDecisionEngine
                                              (threshold evolution)

Supported event types
─────────────────────
- TASK_COMPLETED  → records success metric + positive feedback
- TASK_FAILED     → records failure metric + negative feedback
- GATE_EVALUATED  → records gate confidence + gate feedback
- AUTOMATION_EXECUTED (TASK_SUBMITTED payload tag) → automation metrics

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports — all optional so the connector degrades gracefully
# ---------------------------------------------------------------------------

def _import_learning_engine():
    try:
        from src.learning_engine.learning_engine import LearningEngine  # type: ignore
        return LearningEngine
    except ImportError:
        return None


def _import_adaptive_decision_engine():
    try:
        from src.learning_engine.adaptive_decision_engine import AdaptiveDecisionEngine  # type: ignore
        return AdaptiveDecisionEngine
    except ImportError:
        return None


def _import_event_backbone():
    try:
        from src.event_backbone import EventBackbone, EventType  # type: ignore
        return EventBackbone, EventType
    except ImportError:
        return None, None


# ---------------------------------------------------------------------------
# LearningEngineConnector
# ---------------------------------------------------------------------------

class LearningEngineConnector:
    """Wires EventBackbone events into the closed-loop learning pipeline.

    Parameters
    ----------
    backbone : EventBackbone, optional
        Pre-created backbone instance.  When *None* a fresh one is
        instantiated if the module is available.
    learning_engine : LearningEngine, optional
        Pre-created learning engine.  When *None* a fresh one is created.
    analyze_interval_seconds : float
        How often (in real seconds) to run a full ``analyze_learning()``
        sweep and propagate insights back to the adaptive decision engine.
        Default 300 s (5 min).  Use a lower value in tests.
    """

    def __init__(
        self,
        backbone=None,
        learning_engine=None,
        analyze_interval_seconds: float = 300.0,
    ) -> None:
        self._analyze_interval = analyze_interval_seconds
        self._subscription_ids: List[str] = []
        self._last_analyze: float = time.monotonic()
        self._lock = threading.Lock()

        # Metrics counters (lightweight — no Prometheus dependency)
        self._events_received: int = 0
        self._insights_generated: int = 0
        self._is_started: bool = False

        # Backbone
        if backbone is not None:
            self._backbone = backbone
        else:
            EventBackbone, _ = _import_event_backbone()
            self._backbone = EventBackbone() if EventBackbone else None

        # Learning engine
        if learning_engine is not None:
            self._learning = learning_engine
        else:
            LearningEngine = _import_learning_engine()
            self._learning = LearningEngine() if LearningEngine else None

        # Adaptive decision engine (optional — used for threshold evolution)
        AdaptiveDecisionEngine = _import_adaptive_decision_engine()
        self._adaptive = AdaptiveDecisionEngine() if AdaptiveDecisionEngine else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Subscribe to all relevant EventBackbone event types.

        Returns True when subscriptions were successfully registered.
        """
        if self._is_started:
            return True

        if self._backbone is None or self._learning is None:
            logger.warning(
                "LearningEngineConnector: backbone or learning engine unavailable — "
                "closed-loop learning disabled"
            )
            return False

        _, EventType = _import_event_backbone()
        if EventType is None:
            return False

        _handlers = {
            EventType.TASK_COMPLETED: self._on_task_completed,
            EventType.TASK_FAILED: self._on_task_failed,
            EventType.GATE_EVALUATED: self._on_gate_evaluated,
        }

        # AUTOMATION_EXECUTED is represented as TASK_SUBMITTED with an
        # automation_type tag in the Murphy backbone schema.
        if hasattr(EventType, "AUTOMATION_EXECUTED"):
            _handlers[EventType.AUTOMATION_EXECUTED] = self._on_automation_executed

        for event_type, handler in _handlers.items():
            try:
                sid = self._backbone.subscribe(event_type, handler)
                self._subscription_ids.append(sid)
            except Exception as exc:
                logger.warning(
                    "LearningEngineConnector: failed to subscribe to %s — %s",
                    event_type.value, exc,
                )

        self._is_started = bool(self._subscription_ids)
        if self._is_started:
            logger.info(
                "LearningEngineConnector started — subscribed to %d event types",
                len(self._subscription_ids),
            )
        return self._is_started

    def stop(self) -> None:
        """Unsubscribe from all event types."""
        if not self._is_started or self._backbone is None:
            return
        for sid in self._subscription_ids:
            try:
                self._backbone.unsubscribe(sid)
            except Exception:
                pass
        self._subscription_ids.clear()
        self._is_started = False
        logger.info("LearningEngineConnector stopped")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_task_completed(self, event) -> None:
        """Handle TASK_COMPLETED — record success and positive feedback."""
        payload: Dict[str, Any] = getattr(event, "payload", {}) or {}
        self._events_received += 1

        task_id = payload.get("task_id", event.event_id)
        duration = float(payload.get("duration_seconds", 0.0))
        confidence = float(payload.get("confidence", 1.0))

        try:
            self._learning.record_performance(
                "task_success_rate", 1.0,
                context={"task_id": task_id, "event_type": "task_completed"},
            )
            if duration > 0:
                self._learning.record_performance(
                    "task_duration_seconds", duration,
                    context={"task_id": task_id},
                )
            self._learning.collect_feedback(
                feedback_type="task_execution",
                operation_id=task_id,
                success=True,
                confidence=confidence,
                feedback_data=payload,
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector._on_task_completed error: %s", exc)

        self._maybe_analyze()

    def _on_task_failed(self, event) -> None:
        """Handle TASK_FAILED — record failure and negative feedback."""
        payload: Dict[str, Any] = getattr(event, "payload", {}) or {}
        self._events_received += 1

        task_id = payload.get("task_id", event.event_id)
        confidence = float(payload.get("confidence", 0.0))

        try:
            self._learning.record_performance(
                "task_success_rate", 0.0,
                context={"task_id": task_id, "event_type": "task_failed"},
            )
            self._learning.collect_feedback(
                feedback_type="task_execution",
                operation_id=task_id,
                success=False,
                confidence=confidence,
                feedback_data=payload,
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector._on_task_failed error: %s", exc)

        self._maybe_analyze()

    def _on_gate_evaluated(self, event) -> None:
        """Handle GATE_EVALUATED — track gate confidence evolution."""
        payload: Dict[str, Any] = getattr(event, "payload", {}) or {}
        self._events_received += 1

        gate_id = payload.get("gate_id", event.event_id)
        confidence = float(payload.get("confidence", 0.5))
        passed = bool(payload.get("passed", False))

        try:
            self._learning.record_performance(
                f"gate.{gate_id}.confidence", confidence,
                context={"gate_id": gate_id, "passed": passed},
            )
            self._learning.collect_feedback(
                feedback_type="gate_evaluation",
                operation_id=gate_id,
                success=passed,
                confidence=confidence,
                feedback_data=payload,
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector._on_gate_evaluated error: %s", exc)

        self._maybe_analyze()

    def _on_automation_executed(self, event) -> None:
        """Handle AUTOMATION_EXECUTED — track automation performance."""
        payload: Dict[str, Any] = getattr(event, "payload", {}) or {}
        self._events_received += 1

        automation_id = payload.get("automation_id", event.event_id)
        success = bool(payload.get("success", True))
        confidence = float(payload.get("confidence", 0.8))

        try:
            self._learning.record_performance(
                "automation_success_rate", 1.0 if success else 0.0,
                context={"automation_id": automation_id},
            )
            self._learning.collect_feedback(
                feedback_type="automation_execution",
                operation_id=automation_id,
                success=success,
                confidence=confidence,
                feedback_data=payload,
            )
        except Exception as exc:
            logger.debug("LearningEngineConnector._on_automation_executed error: %s", exc)

        self._maybe_analyze()

    # ------------------------------------------------------------------
    # Periodic analysis
    # ------------------------------------------------------------------

    def _maybe_analyze(self) -> None:
        """Run ``analyze_learning()`` if the interval has elapsed."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_analyze < self._analyze_interval:
                return
            self._last_analyze = now

        try:
            insights = self._learning.analyze_learning()
            if insights:
                self._insights_generated += len(insights)
                logger.info(
                    "LearningEngineConnector: %d new insights generated "
                    "(total %d), %d events processed",
                    len(insights), self._insights_generated, self._events_received,
                )
                self._propagate_insights(insights)
        except Exception as exc:
            logger.warning("LearningEngineConnector.analyze_learning error: %s", exc)

    def force_analyze(self) -> List[Any]:
        """Immediately run analyze_learning and return insights.

        Useful for testing or manual triggering without waiting for the
        interval to elapse.
        """
        if self._learning is None:
            return []
        with self._lock:
            self._last_analyze = 0.0  # force next _maybe_analyze to run
        try:
            insights = self._learning.analyze_learning()
            self._insights_generated += len(insights)
            self._propagate_insights(insights)
            return insights
        except Exception as exc:
            logger.warning("LearningEngineConnector.force_analyze error: %s", exc)
            return []

    def _propagate_insights(self, insights: List[Any]) -> None:
        """Feed insights into the AdaptiveDecisionEngine for threshold evolution."""
        if self._adaptive is None or not insights:
            return
        for insight in insights:
            try:
                # Use adaptive engine's update_policy if available
                if hasattr(self._adaptive, "update_policy"):
                    self._adaptive.update_policy(
                        policy_key=getattr(insight, "insight_type", "default"),
                        confidence_delta=float(getattr(insight, "confidence", 0.0)),
                        importance=float(getattr(insight, "importance", 0.0)),
                    )
                elif hasattr(self._adaptive, "record_outcome"):
                    self._adaptive.record_outcome(
                        outcome={
                            "insight_id": getattr(insight, "insight_id", ""),
                            "recommendation": getattr(insight, "recommendation", ""),
                        }
                    )
            except Exception as exc:
                logger.debug(
                    "LearningEngineConnector._propagate_insights error for "
                    "insight %s: %s",
                    getattr(insight, "insight_id", "?"),
                    exc,
                )

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of connector health and counters."""
        return {
            "started": self._is_started,
            "subscriptions": len(self._subscription_ids),
            "events_received": self._events_received,
            "insights_generated": self._insights_generated,
            "backbone_available": self._backbone is not None,
            "learning_engine_available": self._learning is not None,
            "adaptive_engine_available": self._adaptive is not None,
        }


# ---------------------------------------------------------------------------
# Bootstrap helper — called from murphy_system_core.py startup
# ---------------------------------------------------------------------------

_connector_instance: Optional[LearningEngineConnector] = None


def bootstrap_learning_connector(
    backbone=None,
    learning_engine=None,
    analyze_interval_seconds: float = 300.0,
) -> LearningEngineConnector:
    """Create (or return the existing) global LearningEngineConnector and start it.

    Safe to call multiple times — subsequent calls return the already-started
    singleton without re-subscribing.

    Parameters
    ----------
    backbone, learning_engine
        Optional pre-built instances.  Useful in tests.
    analyze_interval_seconds
        Forwarded to LearningEngineConnector.__init__.
    """
    global _connector_instance

    if _connector_instance is not None and _connector_instance._is_started:
        return _connector_instance

    connector = LearningEngineConnector(
        backbone=backbone,
        learning_engine=learning_engine,
        analyze_interval_seconds=analyze_interval_seconds,
    )
    connector.start()
    _connector_instance = connector
    return connector


def get_connector() -> Optional[LearningEngineConnector]:
    """Return the running global connector instance (or None)."""
    return _connector_instance
