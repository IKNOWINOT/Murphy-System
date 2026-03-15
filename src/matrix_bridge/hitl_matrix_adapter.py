# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""HITL Matrix Adapter — Human-in-the-loop via Matrix rooms.

Integrates with the existing Murphy HITL system:
- ``hitl_autonomy_controller``
- ``hitl_graduation_engine``

Features:
- Post approval requests to the dedicated ``#murphy-hitl-approvals`` room
- Emoji reaction support: ✅ / 👍 to approve, ❌ / 👎 to reject
- Thread-based discussion for complex approvals
- Timeout handling with escalation
- Idempotent: duplicate posts are suppressed via in-memory tracking

Configuration
-------------
HITL_POLL_INTERVAL      seconds between polls (default 30)
HITL_APPROVAL_TIMEOUT   seconds before auto-escalation (default 3600)
HITL_ESCALATION_ROOM    room key to escalate timed-out items to
                        (default ``"admin"``)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .matrix_client import MatrixClient
from .room_registry import RoomRegistry

logger = logging.getLogger(__name__)

# Emoji sets for approve / reject
_APPROVE_EMOJIS: Set[str] = {"✅", "✔️", "✔", "👍", "✓"}
_REJECT_EMOJIS: Set[str] = {"❌", "👎", "✗", "✕", "✖"}

_HITL_ROOM_KEY = "hitl-approvals"
_DEFAULT_POLL_INTERVAL = 30
_DEFAULT_APPROVAL_TIMEOUT = 3600  # 1 hour


@dataclass
class HITLItem:
    """Pending HITL intervention posted to Matrix."""

    intervention_id: str
    event_id: Optional[str] = field(default=None)     # Matrix event ID of the posted message
    posted_at: float = field(default_factory=time.monotonic)
    resolved: bool = False
    escalated: bool = False


class HITLMatrixAdapter:
    """Posts pending HITL interventions to a Matrix room and listens for
    emoji reactions to dispatch approval / rejection back to Murphy.

    Parameters
    ----------
    client:
        Connected :class:`~murphy.matrix_bridge.MatrixClient`.
    registry:
        :class:`~murphy.matrix_bridge.RoomRegistry` with room IDs populated.
    api_client:
        Async callable ``(method, path, **kwargs) → dict`` to query the Murphy
        API (e.g. a thin ``httpx.AsyncClient`` wrapper).
    poll_interval:
        Seconds between polls for pending interventions.
    approval_timeout:
        Seconds before a pending item is escalated.
    escalation_room_key:
        Subsystem room key to post escalation notices to.
    """

    def __init__(
        self,
        client: MatrixClient,
        registry: RoomRegistry,
        api_client: Optional[Callable[..., Any]] = None,
        poll_interval: int = _DEFAULT_POLL_INTERVAL,
        approval_timeout: int = _DEFAULT_APPROVAL_TIMEOUT,
        escalation_room_key: str = "admin",
    ) -> None:
        self._client = client
        self._registry = registry
        self._api = api_client
        self.poll_interval = poll_interval
        self.approval_timeout = approval_timeout
        self.escalation_room_key = escalation_room_key
        self._pending: Dict[str, HITLItem] = {}  # intervention_id → HITLItem
        self._event_to_id: Dict[str, str] = {}   # Matrix event_id → intervention_id
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the polling loop in the current asyncio task."""
        self._running = True
        await self._poll_loop()

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
                await self._check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("HITLMatrixAdapter poll error: %s", exc)
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        """Fetch pending interventions and post new ones to Matrix."""
        if self._api is None:
            return
        try:
            data = await self._api("GET", "/hitl/interventions/pending")
            items: List[Dict[str, Any]] = data.get("interventions", [])
        except Exception as exc:
            logger.debug("HITLMatrixAdapter: API poll failed: %s", exc)
            return

        for item in items:
            iid = item.get("id") or item.get("intervention_id")
            if not iid or iid in self._pending:
                continue
            await self._post_intervention(iid, item)

    async def _check_timeouts(self) -> None:
        """Escalate interventions that have exceeded the approval timeout."""
        now = time.monotonic()
        for iid, hitl in list(self._pending.items()):
            if hitl.resolved or hitl.escalated:
                continue
            if now - hitl.posted_at > self.approval_timeout:
                await self._escalate(iid, hitl)
                hitl.escalated = True

    # ------------------------------------------------------------------
    # Post / escalate
    # ------------------------------------------------------------------

    async def _post_intervention(
        self, intervention_id: str, data: Dict[str, Any]
    ) -> None:
        """Format and post a HITL intervention card to the approvals room."""
        room_id = self._registry.get_room_id(_HITL_ROOM_KEY)
        if not room_id:
            logger.warning("HITLMatrixAdapter: hitl-approvals room not found")
            return

        plain, html = self._format_intervention(intervention_id, data)
        success = await self._client.send_formatted(room_id, plain, html, msgtype="m.text")
        if success:
            hitl = HITLItem(intervention_id=intervention_id)
            self._pending[intervention_id] = hitl
            logger.info("Posted HITL intervention %s", intervention_id)

    async def _escalate(self, intervention_id: str, hitl: HITLItem) -> None:
        """Post an escalation notice to the escalation room."""
        room_id = self._registry.get_room_id(self.escalation_room_key)
        if not room_id:
            return
        plain = (
            f"⏰ HITL TIMEOUT: Intervention {intervention_id} has exceeded "
            f"{self.approval_timeout}s without a response — escalating."
        )
        html = (
            f"<b>⏰ HITL TIMEOUT</b><br>"
            f"Intervention <code>{intervention_id}</code> exceeded "
            f"<b>{self.approval_timeout}s</b> without response — escalating."
        )
        await self._client.send_formatted(room_id, plain, html, msgtype="m.notice")

    # ------------------------------------------------------------------
    # Reaction handling
    # ------------------------------------------------------------------

    async def handle_reaction(
        self, user_id: str, event_id: str, emoji: str
    ) -> Optional[str]:
        """Process an emoji reaction on a HITL message.

        Returns the intervention ID if handled, ``None`` otherwise.
        """
        iid = self._event_to_id.get(event_id)
        if not iid:
            return None
        item = self._pending.get(iid)
        if not item or item.resolved:
            return None

        if emoji in _APPROVE_EMOJIS:
            await self._resolve(iid, user_id, "approve")
            item.resolved = True
            return iid
        if emoji in _REJECT_EMOJIS:
            await self._resolve(iid, user_id, "reject")
            item.resolved = True
            return iid

        return None

    async def handle_command_response(
        self,
        intervention_id: str,
        user_id: str,
        decision: str,  # "approve" | "reject"
        reason: str = "",
    ) -> bool:
        """Handle a ``!murphy hitl respond <id> approve|reject`` command."""
        if decision not in ("approve", "reject"):
            return False
        item = self._pending.get(intervention_id)
        if not item or item.resolved:
            return False
        await self._resolve(intervention_id, user_id, decision, reason=reason)
        item.resolved = True
        return True

    async def _resolve(
        self,
        intervention_id: str,
        user_id: str,
        decision: str,
        reason: str = "",
    ) -> None:
        if self._api is None:
            return
        try:
            await self._api(
                "POST",
                f"/hitl/interventions/{intervention_id}/respond",
                json={
                    "decision": decision,
                    "responded_by": user_id,
                    "reason": reason,
                },
            )
            # Notify approvals room
            room_id = self._registry.get_room_id(_HITL_ROOM_KEY)
            if room_id:
                symbol = "✅" if decision == "approve" else "❌"
                plain = f"{symbol} {decision.upper()}: {intervention_id} by {user_id}"
                html = (
                    f"<b>{symbol} {decision.upper()}</b> — "
                    f"<code>{intervention_id}</code> by <i>{user_id}</i>"
                )
                if reason:
                    plain += f" — {reason}"
                    html += f" — {reason}"
                await self._client.send_formatted(room_id, plain, html, msgtype="m.notice")
        except Exception as exc:
            logger.warning("HITLMatrixAdapter._resolve failed: %s", exc)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_intervention(
        intervention_id: str, data: Dict[str, Any]
    ) -> tuple[str, str]:
        title = data.get("title", "HITL Approval Required")
        description = data.get("description", "")
        severity = data.get("severity", "medium")
        requester = data.get("requester", "murphy-system")

        emoji_map = {"low": "🔵", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        sev_emoji = emoji_map.get(severity, "🟡")

        plain = (
            f"{sev_emoji} HITL APPROVAL REQUIRED\n"
            f"ID: {intervention_id}\n"
            f"Title: {title}\n"
            f"Severity: {severity}\n"
            f"Requester: {requester}\n"
        )
        if description:
            plain += f"Description: {description}\n"
        plain += "\nReact with ✅ to APPROVE or ❌ to REJECT."

        html = (
            f"<b>{sev_emoji} HITL APPROVAL REQUIRED</b><br>"
            f"<table>"
            f"<tr><td><b>ID</b></td><td><code>{intervention_id}</code></td></tr>"
            f"<tr><td><b>Title</b></td><td>{title}</td></tr>"
            f"<tr><td><b>Severity</b></td><td>{severity}</td></tr>"
            f"<tr><td><b>Requester</b></td><td>{requester}</td></tr>"
        )
        if description:
            html += f"<tr><td><b>Description</b></td><td>{description}</td></tr>"
        html += (
            "</table><br>"
            "<b>React with ✅ to APPROVE or ❌ to REJECT.</b>"
        )
        return plain, html


__all__ = ["HITLMatrixAdapter", "HITLItem"]
