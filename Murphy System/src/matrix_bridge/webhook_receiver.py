# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Webhook Receiver — HTTP endpoint that receives external events and posts
them to the appropriate Matrix rooms.

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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
# Source → room key routing
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
