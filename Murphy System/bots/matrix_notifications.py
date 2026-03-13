# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix Notification Relay — health monitoring, status alerts, sentinel relay,
and the live communication activity observatory for the Murphy Matrix bot.

Runs four concurrent polling loops:
- Health monitor  (mirrors MurphyHealth)
- Status monitor  (mirrors MurphyStatusBar)
- Sentinel relay
- Comms activity feed (the live communication observatory)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from .matrix_config import MatrixConfig
from .matrix_bot import MurphyAPIClient
from .matrix_formatters import (
    format_error,
    format_comms_activity_feed,
    format_overview,
)

logger = logging.getLogger(__name__)


class NotificationRelay:
    """Concurrent notification and monitoring relay.

    Parameters
    ----------
    cfg:
        Shared :class:`MatrixConfig` instance.
    client:
        The already-logged-in ``nio.AsyncClient``.
    api:
        Shared :class:`MurphyAPIClient` instance.
    """

    def __init__(self, cfg: MatrixConfig, client: Any, api: MurphyAPIClient) -> None:
        self.cfg = cfg
        self._client = client
        self._api = api
        self._running = False

        # Health state (mirrors MurphyHealth)
        self._api_online: Optional[bool] = None

        # Status state (mirrors MurphyStatusBar)
        self._prev_stuck: int = 0
        self._prev_waiting: int = 0

        # Sentinel: track seen alert IDs
        self._seen_sentinel_ids: Set[str] = set()

        # Comms activity: track seen activity IDs
        self._seen_comms_ids: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start all four concurrent monitoring loops."""
        self._running = True
        logger.info("NotificationRelay started.")
        await asyncio.gather(
            self._health_loop(),
            self._status_loop(),
            self._sentinel_loop(),
            self._comms_loop(),
            return_exceptions=True,
        )

    async def stop(self) -> None:
        """Signal all loops to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Health monitor (mirrors MurphyHealth)
    # ------------------------------------------------------------------

    async def _health_loop(self) -> None:
        while self._running:
            try:
                await self._check_health()
            except Exception:
                logger.exception("NotificationRelay: health loop error")
            await asyncio.sleep(self.cfg.health_poll_interval)

    async def _check_health(self) -> None:
        result = await self._api.get("/api/health")
        now_online = result["ok"] and result.get("status", 200) < 500

        if self._api_online is None:
            # First check — just record state, don't alert
            self._api_online = now_online
            return

        if self._api_online and not now_online:
            # Transition online → offline
            self._api_online = False
            await self._send(
                self.cfg.alerts_room,
                "⚠ MURPHY SYSTEM OFFLINE",
                '<p style="color:#c0392b;font-weight:bold;">⚠ MURPHY SYSTEM OFFLINE</p>',
            )
            logger.warning("NotificationRelay: Murphy API went offline")

        elif not self._api_online and now_online:
            # Transition offline → online
            self._api_online = True
            await self._send(
                self.cfg.alerts_room,
                "✓ MURPHY SYSTEM BACK ONLINE",
                '<p style="color:#27ae60;font-weight:bold;">✓ MURPHY SYSTEM BACK ONLINE</p>',
            )
            logger.info("NotificationRelay: Murphy API came back online")

    # ------------------------------------------------------------------
    # Status monitor (mirrors MurphyStatusBar)
    # ------------------------------------------------------------------

    async def _status_loop(self) -> None:
        while self._running:
            try:
                await self._check_status()
            except Exception:
                logger.exception("NotificationRelay: status loop error")
            await asyncio.sleep(self.cfg.status_poll_interval)

    async def _check_status(self) -> None:
        result = await self._api.get("/api/orchestrator/overview")
        if not result["ok"]:
            return

        data = result["data"] or {}
        if isinstance(data, dict):
            stuck = int(data.get("stuck", 0))
            waiting = int(data.get("hitl_waiting", data.get("waiting", 0)))
        else:
            return

        # Alert if stuck count increased
        if stuck > self._prev_stuck:
            delta = stuck - self._prev_stuck
            plain, html = format_overview(data)
            alert_plain = f"⚠ {delta} new stuck workflow(s)! Total stuck: {stuck}\n{plain}"
            alert_html = (
                f'<p style="color:#c0392b;font-weight:bold;">⚠ {delta} new stuck workflow(s)!</p>'
                + html
            )
            await self._send(self.cfg.alerts_room, alert_plain, alert_html)

        # Alert if HITL waiting count spiked (≥5 new)
        if waiting - self._prev_waiting >= 5:
            delta = waiting - self._prev_waiting
            await self._send(
                self.cfg.alerts_room,
                f"⚠ HITL backlog spike: {delta} new interventions waiting ({waiting} total)",
                f'<p style="color:#e67e22;font-weight:bold;">'
                f"⚠ HITL backlog spike: {delta} new ({waiting} total)</p>",
            )

        self._prev_stuck = stuck
        self._prev_waiting = waiting

    # ------------------------------------------------------------------
    # Sentinel relay
    # ------------------------------------------------------------------

    async def _sentinel_loop(self) -> None:
        while self._running:
            try:
                await self._check_sentinel()
            except Exception:
                logger.exception("NotificationRelay: sentinel loop error")
            await asyncio.sleep(60)

    async def _check_sentinel(self) -> None:
        result = await self._api.get("/api/sentinel/alerts")
        if not result["ok"]:
            return

        data = result["data"] or {}
        alerts: list = []
        if isinstance(data, list):
            alerts = data
        elif isinstance(data, dict):
            alerts = (
                data.get("alerts")
                or data.get("items")
                or data.get("data")
                or []
            )

        for alert in alerts:
            aid = str(alert.get("id", alert.get("alert_id", "")))
            if not aid or aid in self._seen_sentinel_ids:
                continue

            self._seen_sentinel_ids.add(aid)
            severity = str(alert.get("severity", "?")).upper()
            title = str(alert.get("title", alert.get("message", "Sentinel alert")))
            colour = {
                "CRITICAL": "#c0392b",
                "HIGH": "#e74c3c",
                "MEDIUM": "#e67e22",
                "LOW": "#f39c12",
                "INFO": "#2980b9",
            }.get(severity, "#888")

            plain = f"🔴 SENTINEL [{severity}] {title}"
            html = (
                f'<p><span style="color:{colour};font-weight:bold;">'
                f"🔴 SENTINEL [{severity}]</span> {title}</p>"
            )
            await self._send(self.cfg.alerts_room, plain, html)

    # ------------------------------------------------------------------
    # Comms activity feed (live communication observatory)
    # ------------------------------------------------------------------

    async def _comms_loop(self) -> None:
        while self._running:
            try:
                await self._check_comms()
            except Exception:
                logger.exception("NotificationRelay: comms loop error")
            await asyncio.sleep(self.cfg.comms_poll_interval)

    async def _check_comms(self) -> None:
        # Try /api/comms/activity first, fall back to /api/notifications/recent
        result = await self._api.get("/api/comms/activity")
        if not result["ok"]:
            result = await self._api.get("/api/notifications/recent")
        if not result["ok"]:
            return

        data = result["data"] or {}
        activities: list = []
        if isinstance(data, list):
            activities = data
        elif isinstance(data, dict):
            activities = (
                data.get("activities")
                or data.get("events")
                or data.get("items")
                or data.get("data")
                or []
            )

        new_activities = []
        for activity in activities:
            aid = str(
                activity.get("id")
                or activity.get("activity_id")
                or activity.get("event_id")
                or ""
            )
            if not aid:
                # No stable ID — derive a hash-based dedup key from available fields
                import hashlib as _hl
                raw = f"{activity.get('timestamp','')}\x00{activity.get('type','')}\x00{activity.get('subject','')}"
                aid = _hl.md5(raw.encode(), usedforsecurity=False).hexdigest()

            if aid in self._seen_comms_ids:
                continue

            self._seen_comms_ids.add(aid)
            new_activities.append(activity)

        if not new_activities:
            return

        # Post to comms room in batches of up to 10
        for i in range(0, len(new_activities), 10):
            batch = new_activities[i : i + 10]
            plain, html = format_comms_activity_feed(batch)
            await self._send(self.cfg.comms_room, plain, html)

        logger.info(
            "NotificationRelay: posted %d new comms activities to %s",
            len(new_activities),
            self.cfg.comms_room,
        )

    # ------------------------------------------------------------------
    # Internal send helper
    # ------------------------------------------------------------------

    async def _send(
        self, room_id: str, plain: str, html: Optional[str] = None
    ) -> None:
        if self._client is None:
            return
        content: Dict[str, Any] = {"msgtype": "m.text", "body": plain}
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html
        try:
            await self._client.room_send(room_id, "m.room.message", content)
        except Exception:
            logger.exception("NotificationRelay: failed to send to room %s", room_id)


__all__ = ["NotificationRelay"]
