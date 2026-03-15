"""
Event Streamer for the Murphy Matrix Bridge.

Subscribes to Murphy's ``event_backbone`` and routes formatted events
to the appropriate Matrix rooms.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Markdown templates for each Murphy event type
# ---------------------------------------------------------------------------

EVENT_FORMAT_TEMPLATES: dict[str, str] = {
    "task_submitted": (
        "📥 **Task Submitted**\n"
        "- ID: `{task_id}`\n"
        "- Module: `{source_module}`\n"
        "- Description: {description}"
    ),
    "task_completed": (
        "✅ **Task Completed**\n"
        "- ID: `{task_id}`\n"
        "- Module: `{source_module}`\n"
        "- Duration: {duration_ms}ms"
    ),
    "task_failed": (
        "❌ **Task Failed**\n"
        "- ID: `{task_id}`\n"
        "- Module: `{source_module}`\n"
        "- Reason: {reason}"
    ),
    "gate_evaluated": (
        "🔍 **Gate Evaluated**\n"
        "- Gate: `{gate_name}`\n"
        "- Result: {result}\n"
        "- Score: {score}"
    ),
    "gate_blocked": (
        "🚫 **Gate Blocked**\n"
        "- Gate: `{gate_name}`\n"
        "- Reason: {reason}"
    ),
    "delivery_requested": (
        "📤 **Delivery Requested**\n"
        "- ID: `{delivery_id}`\n"
        "- Target: {target}"
    ),
    "delivery_completed": (
        "📦 **Delivery Completed**\n"
        "- ID: `{delivery_id}`\n"
        "- Target: {target}"
    ),
    "hitl_required": (
        "🙋 **Human Review Required**\n"
        "- Task: `{task_id}`\n"
        "- Reason: {reason}\n"
        "- Requested by: `{source_module}`"
    ),
    "hitl_resolved": (
        "✔️ **HITL Resolved**\n"
        "- Task: `{task_id}`\n"
        "- Decision: {decision}\n"
        "- Reviewer: {reviewer}"
    ),
    "system_health": (
        "💚 **System Health Update**\n"
        "- Status: {status}\n"
        "- Module: `{source_module}`"
    ),
    "health_alert": (
        "🚨 **Health Alert**\n"
        "- Severity: {severity}\n"
        "- Module: `{source_module}`\n"
        "- Message: {message}"
    ),
    "alert_fired": (
        "🔔 **Alert Fired**\n"
        "- Rule: `{rule_name}`\n"
        "- Severity: {severity}\n"
        "- Message: {message}"
    ),
    "alert_resolved": (
        "🔕 **Alert Resolved**\n"
        "- Rule: `{rule_name}`"
    ),
    "swarm_spawned": (
        "🐝 **Swarm Spawned**\n"
        "- Swarm ID: `{swarm_id}`\n"
        "- Agents: {agent_count}\n"
        "- Task: {task_description}"
    ),
    "self_fix_started": (
        "🔧 **Self-Fix Started**\n"
        "- Module: `{source_module}`\n"
        "- Issue: {issue_description}"
    ),
    "self_fix_completed": (
        "✅ **Self-Fix Completed**\n"
        "- Module: `{source_module}`\n"
        "- Fix applied: {fix_summary}"
    ),
    "self_fix_rolled_back": (
        "↩️ **Self-Fix Rolled Back**\n"
        "- Module: `{source_module}`\n"
        "- Reason: {reason}"
    ),
    "audit_logged": (
        "📋 **Audit Entry**\n"
        "- Actor: `{actor}`\n"
        "- Action: {action}\n"
        "- Target: {target}"
    ),
    "learning_feedback": (
        "🧠 **Learning Feedback**\n"
        "- Source: `{source_module}`\n"
        "- Type: {feedback_type}\n"
        "- Score: {score}"
    ),
    "anomaly_detected": (
        "⚠️ **Anomaly Detected**\n"
        "- Detector: `{source_module}`\n"
        "- Metric: {metric}\n"
        "- Value: {value} (threshold: {threshold})"
    ),
    "fleet_bot_spawned": (
        "🤖 **Bot Spawned**\n"
        "- Bot ID: `{bot_id}`\n"
        "- Type: {bot_type}"
    ),
    "fleet_bot_despawned": (
        "👋 **Bot Despawned**\n"
        "- Bot ID: `{bot_id}`\n"
        "- Reason: {reason}"
    ),
    "chaos_experiment_started": (
        "🌩️ **Chaos Experiment Started**\n"
        "- Experiment: `{experiment_name}`\n"
        "- Target: {target}"
    ),
    "chaos_experiment_completed": (
        "🌤️ **Chaos Experiment Completed**\n"
        "- Experiment: `{experiment_name}`\n"
        "- Score: {score}"
    ),
    "prediction_generated": (
        "🔮 **Prediction Generated**\n"
        "- Model: `{model_name}`\n"
        "- Confidence: {confidence:.1%}"
    ),
    "supervisor_child_failed": (
        "💥 **Supervisor: Child Failed**\n"
        "- Component: `{child_name}`\n"
        "- Error: {error}"
    ),
    "supervisor_critical": (
        "🚨 **Supervisor Critical Event**\n"
        "- Message: {message}"
    ),
    "metric_recorded": (
        "📊 **Metric Recorded**\n"
        "- Metric: `{metric_name}`\n"
        "- Value: {value}"
    ),
    "_default": (
        "📡 **Murphy Event**\n"
        "- Type: `{event_type}`\n"
        "- Source: `{source_module}`"
    ),
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StreamedEvent:
    """A Murphy event that has been routed toward a Matrix room.

    Attributes:
        event_id: Unique identifier for this streamed event record.
        murphy_event_type: The string value of the Murphy ``EventType``.
        source_module: Murphy module that produced the event.
        payload: Raw event payload dict.
        target_room: Matrix room alias (e.g. ``#murphy-health:example.com``).
        formatted_message: Markdown-ready string for the Matrix message body.
        timestamp: ISO-8601 UTC creation timestamp.
        delivered: Whether the event has been sent to Matrix.
        retry_count: Number of delivery attempts made so far.
    """

    event_id: str
    murphy_event_type: str
    source_module: str
    payload: dict
    target_room: str
    formatted_message: str
    timestamp: str
    delivered: bool = False
    retry_count: int = 0


# ---------------------------------------------------------------------------
# EventStreamer
# ---------------------------------------------------------------------------


class EventStreamer:
    """Routes Murphy backbone events to Matrix rooms.

    Maintains an internal queue and a background delivery thread.
    Actual Matrix network calls are stubbed; they will be wired to
    ``matrix-nio`` in a later PR.

    Args:
        config: Active :class:`~config.MatrixBridgeConfig`.
        room_router: Active :class:`~room_router.RoomRouter` instance.
    """

    def __init__(
        self,
        config: MatrixBridgeConfig,
        room_router: object,  # RoomRouter — avoid circular import at class level
    ) -> None:
        self._config = config
        self._room_router = room_router
        self._queue: queue.Queue[StreamedEvent] = queue.Queue(
            maxsize=config.max_event_queue_size
        )
        self._pending: dict[str, StreamedEvent] = {}
        self._delivered_count: int = 0
        self._dropped_count: int = 0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        logger.debug("EventStreamer initialised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background delivery thread.

        Safe to call multiple times; subsequent calls are no-ops if already
        running.
        """
        if self._thread and self._thread.is_alive():
            logger.debug("EventStreamer already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._delivery_loop,
            name="matrix-bridge-event-streamer",
            daemon=True,
        )
        self._thread.start()
        logger.info("EventStreamer delivery thread started")

    def stop(self) -> None:
        """Signal the delivery thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("EventStreamer stopped")

    # ------------------------------------------------------------------
    # Event production
    # ------------------------------------------------------------------

    def format_event(self, event_type: str, payload: dict) -> str:
        """Format a Murphy event payload as a Markdown string for Matrix.

        Args:
            event_type: Murphy event type string (e.g. ``"task_completed"``).
            payload: The raw event payload.

        Returns:
            Markdown-formatted string ready for use as a Matrix message body.
        """
        template = EVENT_FORMAT_TEMPLATES.get(
            event_type, EVENT_FORMAT_TEMPLATES["_default"]
        )
        context: dict[str, Any] = dict(payload)
        context.setdefault("event_type", event_type)
        context.setdefault("source_module", payload.get("source", "unknown"))
        try:
            return template.format_map(_SafeDict(context))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to format event '%s': %s", event_type, exc)
            return (
                f"📡 **Murphy Event** — `{event_type}`\n"
                f"*(formatting error: {exc})*"
            )

    def route_event(
        self, event_type: str, source_module: str, payload: dict
    ) -> StreamedEvent | None:
        """Determine target room, format the event, and enqueue it.

        Args:
            event_type: Murphy event type string.
            source_module: Murphy module that emitted the event.
            payload: Raw event payload.

        Returns:
            The created :class:`StreamedEvent`, or ``None`` if the queue
            is full or no target room is found.
        """
        room_alias = _resolve_room(self._room_router, event_type, source_module)
        if room_alias is None:
            logger.debug(
                "No target room for event_type='%s' source='%s' — dropping",
                event_type,
                source_module,
            )
            self._dropped_count += 1
            return None

        formatted = self.format_event(event_type, payload)
        evt = StreamedEvent(
            event_id=str(uuid.uuid4()),
            murphy_event_type=event_type,
            source_module=source_module,
            payload=dict(payload),
            target_room=room_alias,
            formatted_message=formatted,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self._pending[evt.event_id] = evt
        try:
            self._queue.put_nowait(evt)
        except queue.Full:
            logger.warning(
                "Event queue full — dropping event %s (%s)", evt.event_id, event_type
            )
            del self._pending[evt.event_id]
            self._dropped_count += 1
            return None

        logger.debug(
            "Routed event %s (%s) → %s", evt.event_id, event_type, room_alias
        )
        return evt

    # ------------------------------------------------------------------
    # Delivery tracking
    # ------------------------------------------------------------------

    def get_pending_events(self) -> list[StreamedEvent]:
        """Return all events that have not yet been marked as delivered.

        Returns:
            List of undelivered :class:`StreamedEvent` objects.
        """
        return [e for e in self._pending.values() if not e.delivered]

    def mark_delivered(self, event_id: str) -> None:
        """Mark an event as successfully delivered to Matrix.

        Args:
            event_id: The :attr:`StreamedEvent.event_id` to mark.
        """
        evt = self._pending.get(event_id)
        if evt is None:
            logger.warning("mark_delivered: unknown event_id '%s'", event_id)
            return
        evt.delivered = True
        self._delivered_count += 1
        del self._pending[event_id]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return runtime statistics for monitoring.

        Returns:
            Dictionary with ``queue_size``, ``pending``, ``delivered``, and
            ``dropped`` counters.
        """
        return {
            "queue_size": self._queue.qsize(),
            "pending": len(self._pending),
            "delivered": self._delivered_count,
            "dropped": self._dropped_count,
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }

    # ------------------------------------------------------------------
    # Background delivery loop (stub — matrix-nio pending)
    # ------------------------------------------------------------------

    def _delivery_loop(self) -> None:
        """Background thread: dequeue and attempt Matrix delivery."""
        logger.debug("EventStreamer delivery loop running")
        while not self._stop_event.is_set():
            try:
                evt = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._send_matrix_event(evt)
                self.mark_delivered(evt.event_id)
            except RuntimeError:
                # Expected until matrix-nio is wired — silently re-queue
                evt.retry_count += 1
                if evt.retry_count <= self._config.retry_attempts:
                    try:
                        self._queue.put_nowait(evt)
                    except queue.Full:
                        self._dropped_count += 1
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(
                    "Unexpected error delivering event %s: %s", evt.event_id, exc
                )
        logger.debug("EventStreamer delivery loop exited")

    def _send_matrix_event(self, evt: StreamedEvent) -> None:
        """Send a formatted event to a Matrix room.

        .. note::
            This is a **stub**. Real network delivery via ``matrix-nio``
            will replace this method in a later PR.  The method will
            become ``async`` at that point.

        Args:
            evt: The :class:`StreamedEvent` to deliver.

        Raises:
            RuntimeError: Always, until matrix-nio is integrated.
        """
        raise RuntimeError(
            "Matrix event delivery requires matrix-nio SDK (pending PR)"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_room(room_router: object, event_type: str, source_module: str) -> str | None:
    """Try event type first, then module name for room resolution."""
    alias = getattr(room_router, "get_room_for_event_type", lambda _: None)(event_type)
    if alias:
        return alias
    return getattr(room_router, "get_room_for_module", lambda _: None)(source_module)


class _SafeDict(dict):
    """A dict subclass that returns ``{key}`` for missing keys in format_map."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
