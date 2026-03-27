# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Event Bridge — subscribes to Murphy's event_backbone and routes events to
the appropriate Matrix rooms as formatted notifications.

Bridged event types (from :class:`~murphy.event_backbone.EventType`):
- Gate results, HITL approvals/rejections, execution results
- Health alerts, confidence scores, compliance events
- Security events (routed to encrypted room)
- Self-fix lifecycle events
- Monitoring alerts

Events are formatted with severity / priority indicators and posted via
:class:`~murphy.matrix_bridge.MatrixClient`.
"""

from __future__ import annotations

import asyncio
import html as _html_mod
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .matrix_client import MatrixClient
from .room_registry import RoomRegistry

logger = logging.getLogger(__name__)


def _h(text: str) -> str:
    return _html_mod.escape(str(text))


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

class Severity(Enum):
    """Severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_SEVERITY_EMOJI: Dict[str, str] = {
    "info":     "ℹ️",
    "warning":  "⚠️",
    "error":    "❌",
    "critical": "🚨",
}

_SEVERITY_COLOR: Dict[str, str] = {
    "info":     "#2980b9",
    "warning":  "#e67e22",
    "error":    "#c0392b",
    "critical": "#8e44ad",
}


# ---------------------------------------------------------------------------
# Routing table: event_type prefix → subsystem room key
# ---------------------------------------------------------------------------

_EVENT_ROOM_MAP: Dict[str, str] = {
    # Gate events
    "gate_evaluated":               "gate-synthesis",
    "gate_blocked":                 "gate-synthesis",
    # HITL events
    "hitl_required":                "hitl-approvals",
    "hitl_resolved":                "hitl-approvals",
    # Execution events
    "task_submitted":               "execution-engine",
    "task_completed":               "execution-engine",
    "task_failed":                  "execution-engine",
    # Delivery events
    "delivery_requested":           "execution-orchestrator",
    "delivery_completed":           "execution-orchestrator",
    # Learning
    "learning_feedback":            "learning-engine",
    # Recalibration
    "recalibration_start":          "confidence-engine",
    # Audit
    "audit_logged":                 "security-audit-scanner",
    # Rosetta
    "rosetta_updated":              "rosetta",
    # Swarm
    "swarm_spawned":                "advanced-swarm-system",
    # Persistence
    "persistence_snapshot":         "persistence-manager",
    # Health
    "system_health":                "health-monitor",
    # Self-fix lifecycle
    "self_fix_started":             "self-fix-loop",
    "self_fix_plan_created":        "self-fix-loop",
    "self_fix_executed":            "self-fix-loop",
    "self_fix_tested":              "self-fix-loop",
    "self_fix_verified":            "self-fix-loop",
    "self_fix_completed":           "self-fix-loop",
    "self_fix_rolled_back":         "self-fix-loop",
    # Bot heartbeat
    "bot_heartbeat_ok":             "heartbeat-liveness-protocol",
    "bot_heartbeat_failed":         "heartbeat-liveness-protocol",
    "bot_heartbeat_missed":         "heartbeat-liveness-protocol",
    "bot_heartbeat_recovery_started": "heartbeat-liveness-protocol",
    "bot_heartbeat_recovered":      "heartbeat-liveness-protocol",
    # Supervisor
    "supervisor_child_started":     "supervisor-system",
    "supervisor_child_stopped":     "supervisor-system",
    "supervisor_child_restarted":   "supervisor-system",
    "supervisor_child_failed":      "supervisor-system",
    "supervisor_child_escalated":   "supervisor-system",
    "supervisor_critical":          "supervisor-system",
    # Alerts
    "alert_fired":                  "alert-rules-engine",
    "alert_resolved":               "alert-rules-engine",
    # Metrics
    "metric_recorded":              "prometheus-metrics-exporter",
}

# Events that should additionally go to the security-alerts room
_SECURITY_EVENT_TYPES = frozenset({
    "gate_blocked",
    "audit_logged",
    "supervisor_critical",
    "alert_fired",
    "self_fix_rolled_back",
    "bot_heartbeat_failed",
})

# Events that should additionally go to system-status
_STATUS_EVENT_TYPES = frozenset({
    "system_health",
    "bot_heartbeat_ok",
    "bot_heartbeat_failed",
    "supervisor_critical",
    "alert_fired",
    "alert_resolved",
})


@dataclass
class BridgedEvent:
    """Normalised event consumed by the EventBridge."""

    event_type: str
    source: str
    payload: Dict[str, Any]
    severity: str = "info"
    correlation_id: Optional[str] = None
    timestamp: Optional[str] = None


class EventBridge:
    """Subscribes to Murphy events and fans them out to Matrix rooms.

    Parameters
    ----------
    client:
        Connected :class:`~murphy.matrix_bridge.MatrixClient`.
    registry:
        :class:`~murphy.matrix_bridge.RoomRegistry` with room IDs populated.
    event_backbone:
        Optional Murphy :class:`~murphy.event_backbone.EventBackbone` to
        subscribe to.  When ``None`` the bridge must be driven externally via
        :meth:`dispatch`.
    """

    def __init__(
        self,
        client: MatrixClient,
        registry: RoomRegistry,
        event_backbone: Optional[Any] = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self._backbone = event_backbone
        self._running = False
        self._custom_routers: List[Callable[[BridgedEvent], Optional[str]]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Attach to the event backbone (if provided)."""
        if self._backbone is None:
            logger.info("EventBridge: no event_backbone provided — use dispatch() manually")
            return
        try:
            self._backbone.subscribe("*", self._on_backbone_event)
            self._running = True
            logger.info("EventBridge subscribed to event_backbone")
        except Exception as exc:
            logger.warning("EventBridge: failed to subscribe to event_backbone: %s", exc)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Custom routing
    # ------------------------------------------------------------------

    def add_router(self, router: Callable[[BridgedEvent], Optional[str]]) -> None:
        """Add a custom router ``(event) → subsystem_key | None``."""
        capped_append(self._custom_routers, router)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, event: BridgedEvent) -> None:
        """Route *event* to the correct Matrix room(s)."""
        rooms = self._resolve_rooms(event)
        if not rooms:
            logger.debug("EventBridge: no room for event_type=%s", event.event_type)
            return

        plain, html = self._format(event)
        for room_key in rooms:
            room_id = self._registry.get_room_id(room_key)
            if room_id:
                await self._client.send_formatted(room_id, plain, html, msgtype="m.notice")

    def _on_backbone_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Called synchronously by the event_backbone; schedules async dispatch."""
        severity = payload.get("severity", "info")
        event = BridgedEvent(
            event_type=event_type,
            source=payload.get("source", "unknown"),
            payload=payload,
            severity=severity if severity in _SEVERITY_EMOJI else "info",
            correlation_id=payload.get("correlation_id"),
            timestamp=payload.get("timestamp"),
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.dispatch(event))
            else:
                loop.run_until_complete(self.dispatch(event))
        except RuntimeError as exc:
            logger.debug("Non-critical error: %s", exc)

    # ------------------------------------------------------------------
    # Room resolution
    # ------------------------------------------------------------------

    def _resolve_rooms(self, event: BridgedEvent) -> List[str]:
        rooms: List[str] = []

        # Custom routers first
        for router in self._custom_routers:
            result = router(event)
            if result and result not in rooms:
                rooms.append(result)

        # Default routing table
        primary = _EVENT_ROOM_MAP.get(event.event_type)
        if primary and primary not in rooms:
            rooms.append(primary)

        # Additional fan-out
        if event.event_type in _SECURITY_EVENT_TYPES and "security-alerts" not in rooms:
            rooms.append("security-alerts")
        if event.event_type in _STATUS_EVENT_TYPES and "system-status" not in rooms:
            rooms.append("system-status")

        return rooms

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format(self, event: BridgedEvent) -> tuple[str, str]:
        sev = event.severity
        emoji = _SEVERITY_EMOJI.get(sev, "ℹ️")
        color = _SEVERITY_COLOR.get(sev, "#2980b9")
        ts = event.timestamp or ""

        plain_lines = [
            f"{emoji} [{sev.upper()}] {event.event_type} from {event.source}",
        ]
        if ts:
            plain_lines.append(f"  Time: {ts}")
        if event.correlation_id:
            plain_lines.append(f"  Correlation: {event.correlation_id}")

        # Include a selection of payload fields
        skip_keys = {"severity", "source", "timestamp", "correlation_id"}
        for k, v in list(event.payload.items())[:8]:
            if k not in skip_keys:
                plain_lines.append(f"  {k}: {v}")

        plain = "\n".join(plain_lines)

        # HTML
        header_color = color
        rows = ""
        for k, v in list(event.payload.items())[:8]:
            if k not in skip_keys:
                rows += f"<tr><td><b>{_h(k)}</b></td><td><code>{_h(str(v))}</code></td></tr>"

        html = (
            f'<span style="color:{header_color};font-weight:bold;">'
            f"{emoji} [{_h(sev.upper())}] {_h(event.event_type)}</span>"
            f" — <i>{_h(event.source)}</i>"
        )
        if ts:
            html += f" <small>({_h(ts)})</small>"
        if rows:
            html += f"<table>{rows}</table>"

        return plain, html


__all__ = ["EventBridge", "BridgedEvent", "Severity"]
