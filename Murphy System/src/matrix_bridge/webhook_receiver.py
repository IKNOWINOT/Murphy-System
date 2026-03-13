"""
Webhook Receiver for the Murphy Matrix Bridge.

Accepts inbound webhook payloads from Matrix and external systems
(GitHub, alert managers, deployment pipelines) and routes them to the
appropriate Matrix rooms via the event pipeline.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WebhookEventType(str, Enum):
    """Classifies the origin and purpose of an incoming webhook.

    Attributes:
        MATRIX_EVENT: An event pushed by the Matrix homeserver.
        EXTERNAL_TRIGGER: A generic external system trigger.
        GITHUB_EVENT: A GitHub Actions or repository event.
        ALERT_FIRING: An alert from Prometheus AlertManager or similar.
        DEPLOYMENT_EVENT: A CI/CD deployment notification.
    """

    MATRIX_EVENT = "matrix_event"
    EXTERNAL_TRIGGER = "external_trigger"
    GITHUB_EVENT = "github_event"
    ALERT_FIRING = "alert_firing"
    DEPLOYMENT_EVENT = "deployment_event"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WebhookEvent:
    """Represents a single inbound webhook payload.

    Attributes:
        webhook_id: Unique identifier for this webhook event record.
        event_type: :class:`WebhookEventType` describing the origin.
        source: Human-readable source identifier (e.g. ``"github"``).
        payload: Raw decoded payload dictionary.
        received_at: ISO-8601 UTC timestamp of receipt.
        processed: Whether this event has been fully processed.
        target_room: Matrix room alias to deliver the formatted message to.
    """

    webhook_id: str
    event_type: WebhookEventType
    source: str
    payload: dict
    received_at: str
    processed: bool = False
    target_room: str | None = None


# ---------------------------------------------------------------------------
# Source → room hint mapping
# ---------------------------------------------------------------------------

_SOURCE_ROOM_HINTS: dict[str, str] = {
    "github": "murphy-dev",
    "gitlab": "murphy-dev",
    "bitbucket": "murphy-dev",
    "alertmanager": "murphy-alerts",
    "prometheus": "murphy-alerts",
    "grafana": "murphy-alerts",
    "pagerduty": "murphy-alerts",
    "jenkins": "murphy-infra",
    "argocd": "murphy-infra",
    "kubernetes": "murphy-infra",
    "docker": "murphy-infra",
    "matrix": "murphy-core",
    "slack": "murphy-comms",
    "email": "murphy-comms",
}

# Mapping WebhookEventType → default room key
_EVENT_TYPE_ROOM_DEFAULTS: dict[WebhookEventType, str] = {
    WebhookEventType.MATRIX_EVENT: "murphy-core",
    WebhookEventType.EXTERNAL_TRIGGER: "murphy-integrations",
    WebhookEventType.GITHUB_EVENT: "murphy-dev",
    WebhookEventType.ALERT_FIRING: "murphy-alerts",
    WebhookEventType.DEPLOYMENT_EVENT: "murphy-infra",
}


# ---------------------------------------------------------------------------
# WebhookReceiver
# ---------------------------------------------------------------------------


class WebhookReceiver:
    """Receives, classifies, and routes inbound webhooks.

    Maintains an in-process queue of pending and processed events.
    Message delivery to Matrix rooms is stubbed — ``matrix-nio`` will
    be wired in a later PR.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
        room_router: Active :class:`~room_router.RoomRouter` instance.
    """

    def __init__(
        self,
        config: MatrixBridgeConfig,
        room_router: object,  # RoomRouter
    ) -> None:
        self._config = config
        self._room_router = room_router
        self._events: dict[str, WebhookEvent] = {}
        self._received_count: int = 0
        self._processed_count: int = 0
        logger.debug("WebhookReceiver initialised")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def receive(
        self, raw_payload: dict, source: str = "unknown"
    ) -> WebhookEvent:
        """Ingest a raw webhook payload and create a :class:`WebhookEvent`.

        The event is classified and a target room is determined, but no
        Matrix message is sent yet — call :meth:`process` to do that.

        Args:
            raw_payload: The decoded JSON body of the incoming request.
            source: Identifier for the sending system (e.g. ``"github"``).

        Returns:
            A new :class:`WebhookEvent` record.
        """
        event_type = _classify_event(raw_payload, source)
        evt = WebhookEvent(
            webhook_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source.lower(),
            payload=dict(raw_payload),
            received_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events[evt.webhook_id] = evt
        self._received_count += 1
        logger.debug(
            "WebhookReceiver: received event %s type=%s from=%s",
            evt.webhook_id,
            event_type.value,
            source,
        )
        return evt

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(self, event: WebhookEvent) -> dict:
        """Determine target room, format the message, and attempt delivery.

        Actual Matrix delivery is stubbed.

        Args:
            event: A :class:`WebhookEvent` previously created by
                :meth:`receive`.

        Returns:
            A result dict with ``webhook_id``, ``target_room``,
            ``formatted_message``, and ``delivered`` keys.
        """
        room_alias = self._resolve_room(event)
        event.target_room = room_alias
        formatted = self._format_webhook(event)

        delivered = False
        try:
            self._send_to_room(room_alias, formatted)
            delivered = True
        except NotImplementedError:
            logger.debug(
                "WebhookReceiver: send stubbed for webhook %s → %s",
                event.webhook_id,
                room_alias,
            )

        event.processed = True
        if delivered:
            self._processed_count += 1

        return {
            "webhook_id": event.webhook_id,
            "target_room": room_alias,
            "formatted_message": formatted,
            "delivered": delivered,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_pending(self) -> list[WebhookEvent]:
        """Return all events that have not yet been processed.

        Returns:
            List of unprocessed :class:`WebhookEvent` objects, oldest first.
        """
        return sorted(
            [e for e in self._events.values() if not e.processed],
            key=lambda e: e.received_at,
        )

    def get_stats(self) -> dict:
        """Return runtime statistics.

        Returns:
            Dictionary with ``received``, ``processed``, and ``pending``
            counters.
        """
        return {
            "received": self._received_count,
            "processed": self._processed_count,
            "pending": len(self.get_pending()),
            "total_stored": len(self._events),
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise all stored webhook events to a JSON-compatible dict.

        Returns:
            Dictionary keyed by ``webhook_id``.
        """
        return {
            wid: {
                **asdict(evt),
                "event_type": evt.event_type.value,
            }
            for wid, evt in self._events.items()
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_room(self, event: WebhookEvent) -> str:
        """Determine the best target room alias for *event*.

        Priority: source hint → event type default → murphy-integrations.
        """
        room_key = _SOURCE_ROOM_HINTS.get(event.source)
        if room_key is None:
            room_key = _EVENT_TYPE_ROOM_DEFAULTS.get(
                event.event_type, "murphy-integrations"
            )

        mapping = self._config.room_mappings.get(room_key)
        if mapping:
            return mapping.room_alias
        return f"#{room_key}:{self._config.domain}"

    def _format_webhook(self, event: WebhookEvent) -> str:
        """Format a :class:`WebhookEvent` as a Markdown Matrix message.

        Args:
            event: The event to format.

        Returns:
            Markdown string suitable for ``m.room.message`` body.
        """
        payload = event.payload
        source = event.source
        etype = event.event_type

        # GitHub-specific formatting
        if etype == WebhookEventType.GITHUB_EVENT:
            gh_event = payload.get("action") or payload.get("ref", "")
            repo = (payload.get("repository") or {}).get("full_name", "unknown")
            actor = (payload.get("sender") or {}).get("login", "unknown")
            return (
                f"🐙 **GitHub Event**\n"
                f"- Repository: `{repo}`\n"
                f"- Action: `{gh_event}`\n"
                f"- Actor: `{actor}`"
            )

        # Alert-specific formatting
        if etype == WebhookEventType.ALERT_FIRING:
            alerts = payload.get("alerts", [payload])
            if isinstance(alerts, list) and alerts:
                first = alerts[0]
                name = (first.get("labels") or {}).get("alertname", "unknown")
                severity = (first.get("labels") or {}).get("severity", "unknown")
                summary = (first.get("annotations") or {}).get("summary", "")
                return (
                    f"🔔 **Alert Firing** [{severity.upper()}]\n"
                    f"- Name: `{name}`\n"
                    f"- Summary: {summary}\n"
                    f"- Source: `{source}`"
                )

        # Deployment-specific formatting
        if etype == WebhookEventType.DEPLOYMENT_EVENT:
            env = payload.get("environment", "unknown")
            status = payload.get("status", "unknown")
            app = payload.get("application", payload.get("service", "unknown"))
            return (
                f"🚀 **Deployment Event**\n"
                f"- Application: `{app}`\n"
                f"- Environment: `{env}`\n"
                f"- Status: `{status}`\n"
                f"- Source: `{source}`"
            )

        # Generic fallback
        return (
            f"📡 **Webhook Event**\n"
            f"- Type: `{etype.value}`\n"
            f"- Source: `{source}`\n"
            f"- ID: `{event.webhook_id}`"
        )

    def _send_to_room(self, room_alias: str, message: str) -> None:
        """Send *message* to *room_alias* via Matrix.

        .. note::
            **Stub** — requires ``matrix-nio`` SDK (pending PR).
            This method will become ``async`` once the SDK is wired.

        Args:
            room_alias: The target Matrix room alias.
            message: Markdown message body.

        Raises:
            NotImplementedError: Always, until matrix-nio is integrated.
        """
        raise NotImplementedError(
            "Matrix send requires matrix-nio SDK (pending PR)"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_event(payload: dict, source: str) -> WebhookEventType:
    """Infer the :class:`WebhookEventType` from the payload and source.

    Args:
        payload: Raw webhook payload dict.
        source: Source system identifier string.

    Returns:
        The most appropriate :class:`WebhookEventType`.
    """
    src = source.lower()

    if src in ("github", "gitlab", "bitbucket"):
        return WebhookEventType.GITHUB_EVENT

    if src in ("alertmanager", "prometheus", "grafana", "pagerduty"):
        return WebhookEventType.ALERT_FIRING

    if src in ("jenkins", "argocd", "kubernetes", "docker", "ci"):
        return WebhookEventType.DEPLOYMENT_EVENT

    if src == "matrix":
        return WebhookEventType.MATRIX_EVENT

    # Heuristic payload inspection
    if "alerts" in payload or payload.get("status") == "firing":
        return WebhookEventType.ALERT_FIRING

    if "deployment" in payload or "environment" in payload:
        return WebhookEventType.DEPLOYMENT_EVENT

    if "repository" in payload or "commits" in payload:
        return WebhookEventType.GITHUB_EVENT

    return WebhookEventType.EXTERNAL_TRIGGER
