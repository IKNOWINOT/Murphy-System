# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""HITL bridge — proactive polling and reaction-based approvals.

Polls ``/api/hitl/interventions/pending`` every N seconds and posts new
interventions to the configured HITL room.  Users can approve/reject by:

  - Sending ``!murphy hitl respond <id> <approve|reject> [reason]``
  - Reacting with ✅ (approve) or ❌ (reject) on the posted message
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Set

from .matrix_config import MatrixBotConfig
from .matrix_formatters import format_hitl_intervention, skull_header, warn_msg, _code

logger = logging.getLogger(__name__)


class HITLBridge:
    """Polls for pending HITL interventions and posts them to a Matrix room.

    Works in conjunction with :class:`~bots.matrix_bot.MurphyMatrixBot`
    to post new interventions and register their event IDs so that emoji
    reactions can be used for approval or rejection.
    """

    def __init__(self, bot: "MurphyMatrixBot", config: MatrixBotConfig) -> None:  # type: ignore[name-defined]
        """Initialise the HITL bridge.

        Args:
            bot: Running :class:`MurphyMatrixBot` instance used for API calls
                and message sending.
            config: Validated :class:`MatrixBotConfig` instance.
        """
        self.bot = bot
        self.config = config
        self._seen_ids: Set[str] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> asyncio.Task:
        """Start the polling loop as an asyncio background task.

        Returns:
            The asyncio :class:`~asyncio.Task` running the poll loop.
        """
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="hitl-bridge")
        logger.info(
            "HITL bridge started — polling every %ds → room %s",
            self.config.hitl_poll_interval,
            self.config.hitl_room or "(not configured)",
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
                await self._check_pending()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("HITL poll error: %s", exc)
            await asyncio.sleep(self.config.hitl_poll_interval)

    async def _check_pending(self) -> None:
        if not self.config.hitl_room:
            return  # no room configured — skip silently

        try:
            data = await self.bot.api.get("/hitl/interventions/pending")
        except RuntimeError as exc:
            logger.debug("HITL API unavailable: %s", exc)
            return

        items = data if isinstance(data, list) else data.get("interventions", [])
        if not isinstance(items, list):
            return

        for item in items:
            intervention_id = str(item.get("id", ""))
            if not intervention_id or intervention_id in self._seen_ids:
                continue
            self._seen_ids.add(intervention_id)
            await self._post_intervention(item)

    async def _post_intervention(self, item: dict) -> None:
        html = (
            f"{skull_header('⚠ New HITL Intervention')}<br/>"
            + format_hitl_intervention(item)
        )
        event_id = await self.bot._send(self.config.hitl_room, html)
        if event_id:
            self.bot.register_hitl_event(event_id, str(item.get("id", "")))
            logger.info(
                "Posted HITL intervention %s → event %s",
                item.get("id"),
                event_id,
            )

    # ------------------------------------------------------------------
    # Allow the bridge to mark an intervention as handled so it doesn't
    # re-post after an approve/reject.
    # ------------------------------------------------------------------

    def mark_handled(self, intervention_id: str) -> None:
        """Mark an intervention as handled so it is not re-posted.

        Args:
            intervention_id: ID of the intervention to mark as handled.
        """
        self._seen_ids.add(str(intervention_id))


__all__ = ["HITLBridge"]
