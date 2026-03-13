# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix HITL Bridge — polls for pending human-in-the-loop interventions and
relays them to a dedicated Matrix room, then listens for emoji reactions to
dispatch approval / rejection back to the Murphy API.
"""

"""HITL bridge — proactive polling and reaction-based approvals.

Polls /api/hitl/interventions/pending every N seconds and posts new
interventions to the configured HITL room.  Users can approve/reject by:
  - Sending `!murphy hitl respond <id> <approve|reject> [reason]`
  - Reacting with ✅ (approve) or ❌ (reject) on the posted message
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

try:
    from nio import AsyncClient, ReactionEvent
except ImportError:  # pragma: no cover
    AsyncClient = None
    ReactionEvent = None

from .matrix_config import MatrixConfig
from .matrix_bot import MurphyAPIClient
from .matrix_formatters import format_hitl_intervention, format_success, format_error

logger = logging.getLogger(__name__)

# Emoji sets for approve / reject reactions
_APPROVE_EMOJIS: Set[str] = {"✅", "✔️", "✔", "👍", "✓"}
_REJECT_EMOJIS: Set[str] = {"❌", "👎", "✗", "✕"}


class HITLBridge:
    """Polls pending HITL interventions and routes Matrix reactions to the API.

    Parameters
    ----------
    cfg:
        Shared :class:`MatrixConfig` instance.
    client:
        The :class:`~nio.AsyncClient` that is already logged in.
    api:
        Shared :class:`MurphyAPIClient` instance.
    """

    def __init__(
        self,
        cfg: MatrixConfig,
        client: Any,  # nio.AsyncClient (optional dep)
        api: MurphyAPIClient,
    ) -> None:
        self.cfg = cfg
        self._client = client
        self._api = api
        self._seen_ids: Set[str] = set()
        # Maps Matrix event_id → intervention_id so reactions can be resolved
        self._event_to_intervention: Dict[str, str] = {}
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the polling loop and register the reaction callback."""
        if AsyncClient is None:
            logger.warning("matrix-nio not installed; HITLBridge is disabled.")
            return

        self._running = True
        # Register reaction event callback
        self._client.add_event_callback(self._on_reaction, ReactionEvent)
        logger.info(
            "HITLBridge started — polling every %ds → room %s",
            self.cfg.hitl_poll_interval,
            self.cfg.hitl_room,
        )
        await self._poll_loop()

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
from typing import Optional, Set

from .matrix_config import MatrixBotConfig
from .matrix_formatters import format_hitl_intervention, skull_header, warn_msg, _code

logger = logging.getLogger(__name__)


class HITLBridge:
    """Polls for pending HITL interventions and posts them to a Matrix room."""

    def __init__(self, bot: "MurphyMatrixBot", config: MatrixBotConfig) -> None:  # type: ignore[name-defined]
        self.bot = bot
        self.config = config
        self._seen_ids: Set[str] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> asyncio.Task:
        """Start the polling loop as an asyncio background task."""
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
            except Exception:
                logger.exception("HITLBridge: error during pending check")
            await asyncio.sleep(self.cfg.hitl_poll_interval)

    async def _check_pending(self) -> None:
        result = await self._api.get("/api/hitl/interventions/pending")
        if not result["ok"]:
            logger.debug("HITLBridge: failed to fetch pending interventions: %s", result["error"])
            return

        data = result["data"]
        interventions: list = []
        if isinstance(data, list):
            interventions = data
        elif isinstance(data, dict):
            interventions = (
                data.get("interventions")
                or data.get("pending")
                or data.get("items")
                or data.get("data")
                or []
            )

        for intervention in interventions:
            iid = str(intervention.get("id", ""))
            if not iid or iid in self._seen_ids:
                continue

            self._seen_ids.add(iid)
            plain, html = format_hitl_intervention(intervention)
            event_id = await self._send(self.cfg.hitl_room, plain, html)

            # Track so reactions can look up the intervention id
            if event_id:
                self._event_to_intervention[event_id] = iid

            logger.info("HITLBridge: posted intervention %s to room %s", iid, self.cfg.hitl_room)

    async def _on_reaction(self, room: Any, event: Any) -> None:
        """Handle an m.reaction event from any room."""
        try:
            relates_to = event.source.get("content", {}).get("m.relates_to", {})
            target_event_id = relates_to.get("event_id", "")
            key = relates_to.get("key", "")

            intervention_id = self._event_to_intervention.get(target_event_id)
            if not intervention_id:
                return  # reaction not on a tracked intervention post

            if key in _APPROVE_EMOJIS:
                action = "approve"
            elif key in _REJECT_EMOJIS:
                action = "reject"
            else:
                return  # unrecognised emoji

            sender = getattr(event, "sender", "unknown")
            logger.info(
                "HITLBridge: %s reacted %s → %s intervention %s",
                sender, key, action, intervention_id,
            )
            await self._respond(intervention_id, action, sender, room.room_id)
        except Exception:
            logger.exception("HITLBridge: error processing reaction")

    async def _respond(
        self,
        intervention_id: str,
        action: str,
        sender: str,
        room_id: str,
    ) -> None:
        payload: Dict[str, Any] = {
            "action": action,
            "reason": f"Via Matrix reaction by {sender}",
        }
        result = await self._api.post(
            f"/api/hitl/interventions/{intervention_id}/respond",
            json=payload,
        )
        if result["ok"]:
            plain, html = format_success(
                f"Intervention {intervention_id} {action}d by {sender}"
            )
        else:
            plain, html = format_error(
                f"Failed to {action} intervention {intervention_id}: {result.get('error', '')}"
            )
        await self._send(room_id, plain, html)

        # Also post confirmation to HITL room if different
        if room_id != self.cfg.hitl_room:
            await self._send(self.cfg.hitl_room, plain, html)

    async def _send(
        self, room_id: str, plain: str, html: Optional[str] = None
    ) -> Optional[str]:
        """Send a message and return the event_id, or None on failure."""
        if self._client is None:
            return None
        content: Dict[str, Any] = {"msgtype": "m.text", "body": plain}
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html
        try:
            resp = await self._client.room_send(room_id, "m.room.message", content)
            return getattr(resp, "event_id", None)
        except Exception:
            logger.exception("HITLBridge: failed to send to room %s", room_id)
            return None


__all__ = ["HITLBridge"]
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
        self._seen_ids.add(str(intervention_id))
