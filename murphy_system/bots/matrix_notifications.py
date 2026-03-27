# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Health monitor and notification broadcaster.

Polls ``/api/health`` every N seconds (default 15 s) and posts
offline/online transitions plus stuck-workflow warnings to the
configured alerts room.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .matrix_config import MatrixBotConfig
from .matrix_formatters import (
    skull_header,
    error_msg,
    success_msg,
    warn_msg,
    status_badge,
    format_health,
    format_json,
)

logger = logging.getLogger(__name__)

# Workflows processing longer than this many seconds are flagged as stuck.
STUCK_WORKFLOW_THRESHOLD_SECONDS = 3600


class HealthMonitor:
    """Polls ``/api/health`` and broadcasts status changes to the alerts room.

    Works in conjunction with :class:`~bots.matrix_bot.MurphyMatrixBot`
    to broadcast health-change notifications without user interaction.
    """

    def __init__(self, bot: "MurphyMatrixBot", config: MatrixBotConfig) -> None:  # type: ignore[name-defined]
        """Initialise the health monitor.

        Args:
            bot: Running :class:`MurphyMatrixBot` instance.
            config: Validated :class:`MatrixBotConfig` instance.
        """
        self.bot = bot
        self.config = config
        self._last_status: Optional[str] = None  # "healthy" | "unhealthy" | "offline" | None
        self._consecutive_failures = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> asyncio.Task:
        """Start the polling loop as an asyncio background task.

        Returns:
            The asyncio :class:`~asyncio.Task` running the poll loop.
        """
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="health-monitor")
        logger.info(
            "Health monitor started — polling every %ds → room %s",
            self.config.health_poll_interval,
            self.config.alerts_room or "(not configured)",
        )
        return self._task

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Health poll error: %s", exc)
            await asyncio.sleep(self.config.health_poll_interval)

    async def _check_health(self) -> None:
        try:
            data = await self.bot.api.get("/health")
            self._consecutive_failures = 0
            status = (
                str(data.get("status", "unknown")).lower()
                if isinstance(data, dict)
                else "unknown"
            )
            await self._handle_status(status, data)
        except RuntimeError as exc:
            self._consecutive_failures += 1
            logger.debug(
                "Health check failed (%d): %s", self._consecutive_failures, exc
            )
            if self._consecutive_failures == 3:
                # Only alert once when it first goes down
                await self._broadcast(
                    error_msg(
                        f"⚠ Murphy API appears to be offline "
                        f"(failed {self._consecutive_failures} consecutive health checks)"
                    )
                )
                self._last_status = "offline"

    async def _handle_status(self, status: str, data: dict) -> None:
        is_healthy = status in ("healthy", "ok", "running")
        current = "healthy" if is_healthy else "unhealthy"

        if self._last_status == "offline" and current == "healthy":
            await self._broadcast(
                success_msg("✓ Murphy API is back online.")
                + "<br/>"
                + (format_health(data) if isinstance(data, dict) else "")
            )
        elif self._last_status == "healthy" and current == "unhealthy":
            await self._broadcast(
                warn_msg(f"Murphy API status degraded: {status_badge(status)}")
                + "<br/>"
                + (format_health(data) if isinstance(data, dict) else "")
            )
        elif self._last_status is None:
            # First check — log but don't spam the room
            logger.info("Initial health status: %s", current)

        self._last_status = current
        await self._check_stuck_workflows()

    async def _check_stuck_workflows(self) -> None:
        """Warn if any workflows appear stuck (processing for too long)."""
        try:
            data = await self.bot.api.get("/flows/processing")
        except RuntimeError:
            return

        items = data if isinstance(data, list) else data.get("flows", data.get("items", []))
        if not isinstance(items, list):
            return

        stuck: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # Flag items that have been processing for > STUCK_WORKFLOW_THRESHOLD_SECONDS
            duration = item.get("duration_seconds", item.get("elapsed", 0))
            try:
                if float(duration) > STUCK_WORKFLOW_THRESHOLD_SECONDS:
                    stuck.append(str(item.get("id", "unknown")))
            except (TypeError, ValueError):
                pass

        if stuck:
            ids = ", ".join(f"<code>{wid}</code>" for wid in stuck[:10])
            await self._broadcast(
                warn_msg(f"Potentially stuck workflows detected: {ids}")
            )

    async def _broadcast(self, html: str) -> None:
        """Send an HTML message to the alerts room.

        Args:
            html: HTML-formatted message to broadcast.
        """
        if not self.config.alerts_room:
            logger.debug("Alerts room not configured — suppressing: %s", html[:80])
            return
        await self.bot._send(self.config.alerts_room, html)


__all__ = ["HealthMonitor"]
