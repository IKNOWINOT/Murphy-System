# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Startup script for the Murphy System Matrix integration layer.

Connects to the Matrix homeserver, creates all spaces and rooms from the
registry, registers all command handlers, starts the event bridge, and
reports ready status to ``#murphy-system-status``.

Usage::

    import asyncio
    from murphy.matrix_bridge.startup import startup

    asyncio.run(startup())

or::

    python -m murphy.matrix_bridge.startup
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from .bot_personas import BotPersonas
from .command_router import PERM_ADMIN, PERM_OPERATOR, CommandDef, CommandRouter
from .event_bridge import BridgedEvent, EventBridge
from .hitl_matrix_adapter import HITLMatrixAdapter
from .matrix_client import MatrixClient
from .room_registry import RoomRegistry
from .space_manager import SpaceManager
from .webhook_receiver import WebhookReceiver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ready banner
# ---------------------------------------------------------------------------
_READY_PLAIN = (
    "☠ Murphy System Matrix integration ONLINE\n"
    "All subsystem rooms initialised.\n"
    "Type !murphy help for command reference."
)
_READY_HTML = (
    "<b>☠ Murphy System Matrix Integration — ONLINE</b><br>"
    "All subsystem rooms initialised. ✅<br>"
    "Type <code>!murphy help</code> for the command reference."
)


# ---------------------------------------------------------------------------
# Main startup coroutine
# ---------------------------------------------------------------------------

async def startup(
    event_backbone: object = None,
    murphy_api_url: str = "",
) -> dict:
    """Connect to Matrix, create rooms/spaces, start services.

    Parameters
    ----------
    event_backbone:
        Optional Murphy event backbone instance to subscribe the EventBridge
        to.  When ``None`` the bridge can be driven manually via
        ``bridge.dispatch()``.
    murphy_api_url:
        Murphy API base URL for HITL polling.  Defaults to
        ``MURPHY_API_URL`` env var.

    Returns
    -------
    dict
        ``{"client": …, "registry": …, "router": …, "bridge": …, …}``
    """
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        stream=sys.stdout,
    )

    # ------------------------------------------------------------------
    # 1. Matrix client
    # ------------------------------------------------------------------
    client = MatrixClient()
    logger.info("Connecting to Matrix homeserver: %s", client.homeserver)
    connected = await client.connect()
    if not connected:
        logger.warning(
            "MatrixClient could not connect — rooms will be created lazily "
            "when the connection becomes available."
        )

    # ------------------------------------------------------------------
    # 2. Room registry — create all rooms
    # ------------------------------------------------------------------
    registry = RoomRegistry(client=client)
    logger.info("Ensuring all %d subsystem rooms exist…", len(registry.all_subsystems()))
    await registry.ensure_all_rooms()

    # ------------------------------------------------------------------
    # 3. Matrix Spaces hierarchy
    # ------------------------------------------------------------------
    space_mgr = SpaceManager(client=client, registry=registry)
    logger.info("Creating Matrix Spaces hierarchy…")
    await space_mgr.create_all_spaces()

    # ------------------------------------------------------------------
    # 4. Command router
    # ------------------------------------------------------------------
    router = CommandRouter(prefix="!murphy")

    # Register a generic subsystem handler
    async def _subsystem_handler(subsystem: str, command: str, args: list) -> tuple:
        plain = f"Murphy subsystem: {subsystem}  command: {command}  args: {args}"
        html = (
            f"<b>Murphy subsystem:</b> <code>{subsystem}</code> "
            f"— <b>command:</b> <code>{command}</code>"
        )
        return plain, html

    router.set_subsystem_handler(_subsystem_handler)

    # Attach router to client event stream
    async def _message_handler(room: object, event: object) -> None:
        try:
            body: str = getattr(event, "body", "") or ""
            sender: str = getattr(event, "sender", "") or ""
            room_id: str = getattr(room, "room_id", "") or ""
            result = await router.dispatch(sender, room_id, body)
            if result is not None:
                plain, html_msg = result
                if html_msg:
                    await client.send_formatted(room_id, plain, html_msg)
                else:
                    await client.send_text(room_id, plain)
        except Exception as exc:
            logger.warning("Message handler error: %s", exc)

    client.add_event_callback(_message_handler)

    # ------------------------------------------------------------------
    # 5. Event bridge
    # ------------------------------------------------------------------
    bridge = EventBridge(
        client=client,
        registry=registry,
        event_backbone=event_backbone,
    )
    bridge.start()

    # ------------------------------------------------------------------
    # 6. Bot personas (meta-registry, not actively dispatching here)
    # ------------------------------------------------------------------
    personas = BotPersonas()
    logger.info("Loaded %d bot personas: %s", len(personas.all()), personas.names())

    # ------------------------------------------------------------------
    # 7. HITL adapter
    # ------------------------------------------------------------------
    api_url = (murphy_api_url or os.environ.get("MURPHY_API_URL", "")).rstrip("/")
    hitl_adapter = HITLMatrixAdapter(
        client=client,
        registry=registry,
        api_client=None,  # wire up a real httpx client in production
    )

    # ------------------------------------------------------------------
    # 8. Webhook receiver
    # ------------------------------------------------------------------
    webhook = WebhookReceiver(client=client, registry=registry)
    try:
        await webhook.start()
    except Exception as exc:
        logger.warning("WebhookReceiver failed to start: %s", exc)

    # ------------------------------------------------------------------
    # 9. Ready notification
    # ------------------------------------------------------------------
    status_room_id = registry.get_room_id("system-status")
    if status_room_id and client.is_connected():
        await client.send_formatted(
            status_room_id, _READY_PLAIN, _READY_HTML, msgtype="m.notice"
        )
    logger.info("Murphy Matrix integration is READY ✅")

    return {
        "client": client,
        "registry": registry,
        "router": router,
        "bridge": bridge,
        "space_manager": space_mgr,
        "personas": personas,
        "hitl_adapter": hitl_adapter,
        "webhook_receiver": webhook,
    }


async def run_forever(event_backbone: object = None) -> None:
    """Startup then run the Matrix sync loop forever."""
    components = await startup(event_backbone=event_backbone)
    client: MatrixClient = components["client"]
    await client.sync_forever()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_forever())
