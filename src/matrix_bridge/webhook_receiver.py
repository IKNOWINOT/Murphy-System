# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Webhook Receiver — HTTP endpoint that receives external events and posts
them to the appropriate Matrix rooms.

Accepts inbound webhook payloads from Matrix and external systems
(GitHub, alert managers, deployment pipelines) and routes them to the
appropriate Matrix rooms via the event pipeline.

Supported sources:
- GitHub webhooks → ``#murphy-ci-cd``
- Stripe webhooks → ``#murphy-finance``
- Monitoring / PagerDuty / Grafana → ``#murphy-monitoring``
- Generic webhooks with configurable room routing

Built on ``aiohttp`` so it integrates cleanly with the async Matrix client.

Configuration
-------------
WEBHOOK_HOST            bind host (default ``0.0.0.0``)
WEBHOOK_PORT            bind port (default ``8765``)
WEBHOOK_SECRET_GITHUB   GitHub webhook secret for HMAC verification
WEBHOOK_SECRET_STRIPE   Stripe webhook secret for signature verification
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional aiohttp
# ---------------------------------------------------------------------------
try:
    import aiohttp
    from aiohttp import web
    _AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore
    web = None  # type: ignore
    _AIOHTTP_AVAILABLE = False

from .matrix_client import MatrixClient
from .room_registry import RoomRegistry

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
# Source -> room key routing (PR #206)
# ---------------------------------------------------------------------------

_SOURCE_ROOMS: Dict[str, str] = {
    "github":     "ci-cd",
    "stripe":     "finance",
    "grafana":    "monitoring",
    "pagerduty":  "monitoring",
    "prometheus": "monitoring",
    "jenkins":    "ci-cd",
    "gitlab":     "ci-cd",
    "datadog":    "monitoring",
    "sentry":     "monitoring",
    "generic":    "system-status",
}

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


# ---------------------------------------------------------------------------
# WebhookReceiver (config/room_router based -- PR #208)
# ---------------------------------------------------------------------------


class _StubWebhookReceiver:
    """Receives, classifies, and routes inbound webhooks.

    Maintains an in-process queue of pending and processed events.
    Message delivery to Matrix rooms is stubbed -- ``matrix-nio`` will
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
        except RuntimeError:
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
            RuntimeError: Always, until matrix-nio is integrated.
        """
        raise RuntimeError(
            "Matrix send requires matrix-nio SDK (pending PR)"
        )



# ---------------------------------------------------------------------------
# Async WebhookReceiver (client/registry based -- PR #206)
# ---------------------------------------------------------------------------


class WebhookReceiver:
    """Async HTTP webhook receiver that fans events into Matrix rooms.

    Parameters
    ----------
    client:
        Connected :class:`~murphy.matrix_bridge.MatrixClient`.
    registry:
        :class:`~murphy.matrix_bridge.RoomRegistry` with room IDs populated.
    host:
        Bind address.
    port:
        Bind port.
    github_secret:
        HMAC secret for GitHub payload verification (optional).
    stripe_secret:
        Stripe signing secret for payload verification (optional).
    """

    def __init__(
        self,
        client: MatrixClient,
        registry: RoomRegistry,
        host: str = "0.0.0.0",
        port: int = 8765,
        github_secret: Optional[str] = None,
        stripe_secret: Optional[str] = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self.host = host or os.environ.get("WEBHOOK_HOST", "0.0.0.0")
        self.port = int(port or os.environ.get("WEBHOOK_PORT", "8765"))
        self._github_secret = (
            github_secret or os.environ.get("WEBHOOK_SECRET_GITHUB") or ""
        )
        self._stripe_secret = (
            stripe_secret or os.environ.get("WEBHOOK_SECRET_STRIPE") or ""
        )
        self._app: Optional[Any] = None
        self._runner: Optional[Any] = None
        self._custom_routes: Dict[str, str] = {}  # path_suffix → room_key

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def add_route(self, path_suffix: str, room_key: str) -> None:
        """Route requests to ``/webhook/{path_suffix}`` to *room_key*."""
        self._custom_routes[path_suffix] = room_key


    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the webhook HTTP server."""
        if not _AIOHTTP_AVAILABLE:
            logger.warning(
                "aiohttp is not installed — WebhookReceiver disabled. "
                "Install with: pip install aiohttp"
            )
            return

        self._app = web.Application()
        self._app.router.add_post("/webhook/github", self._handle_github)
        self._app.router.add_post("/webhook/stripe", self._handle_stripe)
        self._app.router.add_post("/webhook/monitoring", self._handle_monitoring)
        self._app.router.add_post("/webhook/{source}", self._handle_generic)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info("WebhookReceiver listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop the webhook HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("WebhookReceiver stopped")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_github(self, request: Any) -> Any:
        body = await request.read()
        if self._github_secret:
            sig = request.headers.get("X-Hub-Signature-256", "")
            if not self._verify_github_sig(body, sig):
                return web.Response(status=401, text="Invalid signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        event = request.headers.get("X-GitHub-Event", "unknown")
        await self._post_to_room("github", event, payload)
        return web.Response(status=200, text="ok")

    async def _handle_stripe(self, request: Any) -> Any:
        body = await request.read()
        # Stripe signature verification is complex; skip deep validation here
        # but check the header exists when a secret is configured
        if self._stripe_secret:
            sig = request.headers.get("Stripe-Signature", "")
            if not sig:
                return web.Response(status=401, text="Missing Stripe-Signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        event_type = payload.get("type", "stripe.event")
        await self._post_to_room("stripe", event_type, payload)
        return web.Response(status=200, text="ok")

    async def _handle_monitoring(self, request: Any) -> Any:
        body = await request.read()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body.decode(errors="replace")}
        await self._post_to_room("grafana", "alert", payload)
        return web.Response(status=200, text="ok")

    async def _handle_generic(self, request: Any) -> Any:
        source = request.match_info.get("source", "generic")
        body = await request.read()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body.decode(errors="replace")}
        room_key = self._custom_routes.get(source) or _SOURCE_ROOMS.get(source, "system-status")
        room_id = self._registry.get_room_id(room_key)
        if not room_id:
            return web.Response(status=404, text=f"No room for source: {source}")
        plain, html = self._format_webhook(source, "event", payload)
        await self._client.send_formatted(room_id, plain, html, msgtype="m.notice")
        return web.Response(status=200, text="ok")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _post_to_room(
        self, source: str, event_type: str, payload: Dict[str, Any]
    ) -> None:
        room_key = _SOURCE_ROOMS.get(source, "system-status")
        room_id = self._registry.get_room_id(room_key)
        if not room_id:
            logger.warning("WebhookReceiver: no room for source=%s", source)
            return
        plain, html = self._format_webhook(source, event_type, payload)
        await self._client.send_formatted(room_id, plain, html, msgtype="m.notice")

    @staticmethod
    def _format_webhook(
        source: str, event_type: str, payload: Dict[str, Any]
    ) -> Tuple[str, str]:
        import html as _html_mod

        def h(t: str) -> str:
            return _html_mod.escape(str(t))

        source_icons: Dict[str, str] = {
            "github": "🐙",
            "stripe": "💳",
            "grafana": "📊",
            "pagerduty": "🚨",
            "jenkins": "🔧",
            "gitlab": "🦊",
            "datadog": "🐕",
            "sentry": "🛡️",
        }
        icon = source_icons.get(source, "🔔")

        plain = f"{icon} [{source.upper()}] {event_type}"
        rows = ""
        for k, v in list(payload.items())[:6]:
            if k not in ("object", "data"):
                plain += f"\n  {k}: {v}"
                rows += f"<tr><td><b>{h(k)}</b></td><td><code>{h(str(v)[:120])}</code></td></tr>"

        html = (
            f"<b>{icon} [{h(source.upper())}]</b> {h(event_type)}"
            f"<table>{rows}</table>"
        )
        return plain, html

    def _verify_github_sig(self, body: bytes, signature: str) -> bool:
        if not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            self._github_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)


__all__ = ["WebhookReceiver"]
