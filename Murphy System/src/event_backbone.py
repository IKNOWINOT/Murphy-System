"""
Event Backbone for the Murphy System.
Provides durable, in-process event queues with publish/subscribe,
retry logic, circuit breakers, and dead letter queue support.
"""

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    """System event types for the Murphy event backbone."""
    TASK_SUBMITTED = "task_submitted"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    GATE_EVALUATED = "gate_evaluated"
    GATE_BLOCKED = "gate_blocked"
    DELIVERY_REQUESTED = "delivery_requested"
    DELIVERY_COMPLETED = "delivery_completed"
    AUDIT_LOGGED = "audit_logged"
    LEARNING_FEEDBACK = "learning_feedback"
    SWARM_SPAWNED = "swarm_spawned"
    HITL_REQUIRED = "hitl_required"
    HITL_RESOLVED = "hitl_resolved"
    PERSISTENCE_SNAPSHOT = "persistence_snapshot"
    SYSTEM_HEALTH = "system_health"
    RECALIBRATION_START = "recalibration_start"
    ROSETTA_UPDATED = "rosetta_updated"
    SELF_FIX_STARTED = "self_fix_started"
    SELF_FIX_PLAN_CREATED = "self_fix_plan_created"
    SELF_FIX_EXECUTED = "self_fix_executed"
    SELF_FIX_TESTED = "self_fix_tested"
    SELF_FIX_VERIFIED = "self_fix_verified"
    SELF_FIX_COMPLETED = "self_fix_completed"
    SELF_FIX_ROLLED_BACK = "self_fix_rolled_back"
    BOT_HEARTBEAT_OK = "bot_heartbeat_ok"
    BOT_HEARTBEAT_FAILED = "bot_heartbeat_failed"
    BOT_HEARTBEAT_MISSED = "bot_heartbeat_missed"
    BOT_HEARTBEAT_RECOVERY_STARTED = "bot_heartbeat_recovery_started"
    BOT_HEARTBEAT_RECOVERED = "bot_heartbeat_recovered"
    SUPERVISOR_CHILD_STARTED = "supervisor_child_started"
    SUPERVISOR_CHILD_STOPPED = "supervisor_child_stopped"
    SUPERVISOR_CHILD_RESTARTED = "supervisor_child_restarted"
    SUPERVISOR_CHILD_FAILED = "supervisor_child_failed"
    SUPERVISOR_CHILD_ESCALATED = "supervisor_child_escalated"
    SUPERVISOR_CRITICAL = "supervisor_critical"
    ALERT_FIRED = "alert_fired"
    ALERT_RESOLVED = "alert_resolved"
    METRIC_RECORDED = "metric_recorded"
    ANOMALY_DETECTED = "anomaly_detected"
    CHAOS_EXPERIMENT_STARTED = "chaos_experiment_started"
    CHAOS_EXPERIMENT_COMPLETED = "chaos_experiment_completed"
    CHAOS_SCORECARD_GENERATED = "chaos_scorecard_generated"
    CHAOS_GAPS_SUBMITTED = "chaos_gaps_submitted"
    FLEET_RECONCILIATION_STARTED = "fleet_reconciliation_started"
    FLEET_BOT_SPAWNED = "fleet_bot_spawned"
    FLEET_BOT_DESPAWNED = "fleet_bot_despawned"
    FLEET_BOT_UPDATED = "fleet_bot_updated"
    FLEET_RECONCILED = "fleet_reconciled"
    FLEET_DRIFT_DETECTED = "fleet_drift_detected"
    PREDICTION_GENERATED = "prediction_generated"
    PREDICTION_PREEMPTED = "prediction_preempted"
    PREDICTION_MATERIALIZED = "prediction_materialized"
    PREDICTION_FALSE_POSITIVE = "prediction_false_positive"
    IMMUNE_CYCLE_STARTED = "immune_cycle_started"
    IMMUNE_CYCLE_COMPLETED = "immune_cycle_completed"
    DRIFT_DETECTED = "drift_detected"
    FAILURE_PREDICTED = "failure_predicted"
    IMMUNITY_RECALLED = "immunity_recalled"
    CHAOS_VALIDATED = "chaos_validated"
    CASCADE_CHECKED = "cascade_checked"
    TEST_FAILED = "test_failed"
    DOC_DRIFT = "doc_drift"
    CODE_HEALER_STARTED = "code_healer_started"
    CODE_HEALER_COMPLETED = "code_healer_completed"
    CODE_HEALER_PROPOSAL_CREATED = "code_healer_proposal_created"
    CODE_HEALER_GAP_LOW_CONFIDENCE = "code_healer_gap_low_confidence"


@dataclass
class Event:
    """Represents a single event in the backbone."""
    event_id: str
    event_type: EventType
    payload: Dict[str, Any]
    timestamp: str
    session_id: Optional[str] = None
    source: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "source": self.source,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserialize from a dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            payload=data["payload"],
            timestamp=data["timestamp"],
            session_id=data.get("session_id"),
            source=data.get("source"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )


@dataclass
class _Subscription:
    """Internal record for an event subscription."""
    subscription_id: str
    event_type: EventType
    handler: Callable[[Event], None]


class _HandlerCircuitBreaker:
    """Per-handler circuit breaker tracking consecutive failures."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._consecutive_failures = 0
        self._last_failure_time: Optional[float] = None
        self._open = False

    @property
    def is_open(self) -> bool:
        """Return True if the breaker is tripped and not yet eligible for reset."""
        if not self._open:
            return False
        if self._last_failure_time is not None and \
                time.time() - self._last_failure_time >= self.recovery_timeout:
            # Allow a half-open probe
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        if self._consecutive_failures >= self.failure_threshold:
            self._open = True

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures


class EventBackbone:
    """
    In-process event backbone with durable queues, pub/sub,
    retry with exponential backoff, circuit breakers, idempotency,
    dead letter queue, and ordered processing.
    """

    def __init__(
        self,
        persistence_dir: Optional[str] = None,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ):
        self._lock = threading.Lock()
        self._persistence_dir = persistence_dir

        # Queues keyed by EventType
        self._queues: Dict[EventType, List[Event]] = defaultdict(list)
        # Subscriptions keyed by EventType
        self._subscriptions: Dict[EventType, List[_Subscription]] = defaultdict(list)
        # Quick lookup: subscription_id -> _Subscription
        self._subscription_index: Dict[str, _Subscription] = {}
        # Set of event_ids already seen (idempotency)
        self._seen_event_ids: set = set()
        # Dead letter queue (bounded)
        self._dlq: List[Event] = []
        self._max_dlq_size = 1000
        # Event history (completed / failed records, bounded)
        self._history: List[Dict[str, Any]] = []
        self._max_history_size = 10_000
        # Per-subscription circuit breakers
        self._circuit_breakers: Dict[str, _HandlerCircuitBreaker] = {}
        # Counters
        self._events_published = 0
        self._events_processed = 0
        self._events_failed = 0

        self._cb_threshold = circuit_breaker_threshold
        self._cb_timeout = circuit_breaker_timeout

        if self._persistence_dir:
            os.makedirs(self._persistence_dir, exist_ok=True)
            self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> str:
        """Publish an event onto the backbone. Returns the event_id."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        event = Event(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            session_id=session_id,
            source=source,
        )
        with self._lock:
            self._seen_event_ids.add(event_id)
            self._queues[event_type].append(event)
            self._events_published += 1
            logger.debug("Published event %s of type %s", event_id, event_type.value)
            self._persist_state()
        return event_id

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> str:
        """Subscribe a handler to an event type. Returns subscription_id."""
        subscription_id = str(uuid.uuid4())
        sub = _Subscription(
            subscription_id=subscription_id,
            event_type=event_type,
            handler=handler,
        )
        with self._lock:
            self._subscriptions[event_type].append(sub)
            self._subscription_index[subscription_id] = sub
            self._circuit_breakers[subscription_id] = _HandlerCircuitBreaker(
                failure_threshold=self._cb_threshold,
                recovery_timeout=self._cb_timeout,
            )
            logger.debug(
                "Subscription %s registered for %s", subscription_id, event_type.value
            )
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by its id."""
        with self._lock:
            sub = self._subscription_index.pop(subscription_id, None)
            if sub is None:
                return
            subs = self._subscriptions.get(sub.event_type, [])
            self._subscriptions[sub.event_type] = [
                s for s in subs if s.subscription_id != subscription_id
            ]
            self._circuit_breakers.pop(subscription_id, None)
            logger.debug("Unsubscribed %s", subscription_id)

    def process_pending(self) -> int:
        """
        Process all pending events across all queues in FIFO order.
        Returns the total number of events successfully dispatched.
        """
        processed = 0
        # Snapshot event types that have queued events
        with self._lock:
            event_types = [et for et in self._queues if self._queues[et]]

        for event_type in event_types:
            processed += self._process_queue(event_type)
        return processed

    def get_dead_letter_queue(self) -> List[Event]:
        """Return a copy of events in the dead letter queue."""
        with self._lock:
            return list(self._dlq)

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of the backbone."""
        with self._lock:
            pending_counts: Dict[str, int] = {}
            for et, events in self._queues.items():
                if events:
                    pending_counts[et.value] = len(events)

            subscriber_counts: Dict[str, int] = {}
            for et, subs in self._subscriptions.items():
                if subs:
                    subscriber_counts[et.value] = len(subs)

            breaker_states: Dict[str, Dict[str, Any]] = {}
            for sub_id, cb in self._circuit_breakers.items():
                if cb.failure_count > 0 or cb.is_open:
                    breaker_states[sub_id] = {
                        "open": cb.is_open,
                        "failures": cb.failure_count,
                    }

            return {
                "events_published": self._events_published,
                "events_processed": self._events_processed,
                "events_failed": self._events_failed,
                "pending_counts": pending_counts,
                "subscriber_counts": subscriber_counts,
                "dlq_size": len(self._dlq),
                "circuit_breakers": breaker_states,
            }

    def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query completed event history with optional filters."""
        with self._lock:
            results = self._history
            if event_type is not None:
                results = [r for r in results if r["event_type"] == event_type.value]
            if session_id is not None:
                results = [r for r in results if r.get("session_id") == session_id]
            return results[-limit:]

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_queue(self, event_type: EventType) -> int:
        """Process events for a single event type in FIFO order."""
        processed = 0
        while True:
            # Pop the next event while holding the lock
            with self._lock:
                queue = self._queues.get(event_type, [])
                if not queue:
                    break
                event = queue.pop(0)
                subs = list(self._subscriptions.get(event_type, []))

            if not subs:
                # No subscribers — record to history and move on
                self._record_history(event, "no_subscribers")
                processed += 1
                with self._lock:
                    self._events_processed += 1
                continue

            all_ok = True
            for sub in subs:
                ok = self._dispatch_to_handler(event, sub)
                if not ok:
                    all_ok = False

            if all_ok:
                self._record_history(event, "delivered")
                with self._lock:
                    self._events_processed += 1
                processed += 1
            else:
                # At least one handler failed — apply retry logic
                event.retry_count += 1
                if event.retry_count > event.max_retries:
                    self._send_to_dlq(event)
                    with self._lock:
                        self._events_failed += 1
                else:
                    # Re-enqueue at front so ordering is preserved for retries
                    with self._lock:
                        self._queues[event_type].insert(0, event)
                        self._persist_state()
                    # Stop processing this queue to respect ordering
                    break
        return processed

    def _dispatch_to_handler(self, event: Event, sub: _Subscription) -> bool:
        """Invoke a single handler, respecting circuit breaker."""
        cb = self._circuit_breakers.get(sub.subscription_id)
        if cb and cb.is_open:
            logger.warning(
                "Circuit breaker open for subscription %s — skipping",
                sub.subscription_id,
            )
            return False
        try:
            sub.handler(event)
            if cb:
                cb.record_success()
            return True
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            logger.exception(
                "Handler %s failed for event %s (retry %d/%d)",
                sub.subscription_id,
                event.event_id,
                event.retry_count,
                event.max_retries,
            )
            if cb:
                cb.record_failure()
            return False

    def _send_to_dlq(self, event: Event) -> None:
        """Move an event to the dead letter queue."""
        with self._lock:
            if len(self._dlq) >= self._max_dlq_size:
                self._dlq = self._dlq[self._max_dlq_size // 10:]
            self._dlq.append(event)
            self._persist_state()
        self._record_history(event, "dead_letter")
        logger.warning(
            "Event %s moved to DLQ after %d retries",
            event.event_id,
            event.retry_count,
        )

    def _record_history(self, event: Event, status: str) -> None:
        with self._lock:
            if len(self._history) >= self._max_history_size:
                self._history = self._history[self._max_history_size // 10:]
            self._history.append({
                **event.to_dict(),
                "status": status,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })

    # ------------------------------------------------------------------
    # Idempotent re-publish guard
    # ------------------------------------------------------------------

    def publish_event(self, event: Event) -> bool:
        """
        Publish a pre-built Event, enforcing idempotency.
        Returns False if the event_id was already seen.
        """
        with self._lock:
            if event.event_id in self._seen_event_ids:
                logger.debug("Duplicate event %s ignored", event.event_id)
                return False
            self._seen_event_ids.add(event.event_id)
            self._queues[event.event_type].append(event)
            self._events_published += 1
            self._persist_state()
        return True

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_state(self) -> None:
        """Persist queues and DLQ to disk (call while holding lock)."""
        if not self._persistence_dir:
            return
        state = {
            "queues": {
                et.value: [e.to_dict() for e in events]
                for et, events in self._queues.items()
                if events
            },
            "dlq": [e.to_dict() for e in self._dlq],
            "seen_event_ids": list(self._seen_event_ids),
        }
        path = os.path.join(self._persistence_dir, "event_backbone_state.json")
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding='utf-8') as f:
                json.dump(state, f)
            os.replace(tmp_path, path)
        except OSError:
            logger.exception("Failed to persist event backbone state")

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if not self._persistence_dir:
            return
        path = os.path.join(self._persistence_dir, "event_backbone_state.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding='utf-8') as f:
                state = json.load(f)
            for et_value, events in state.get("queues", {}).items():
                et = EventType(et_value)
                self._queues[et] = [Event.from_dict(e) for e in events]
            self._dlq = [Event.from_dict(e) for e in state.get("dlq", [])]
            self._seen_event_ids = set(state.get("seen_event_ids", []))
            logger.info(
                "Loaded event backbone state: %d queued, %d DLQ, %d seen",
                sum(len(v) for v in self._queues.values()),
                len(self._dlq),
                len(self._seen_event_ids),
            )
        except (OSError, json.JSONDecodeError, KeyError):
            logger.exception("Failed to load event backbone state")
