"""
Application Service for the Murphy Matrix Bridge.

Implements the Matrix Application Service (AS) protocol.  The AS
registers with the Synapse homeserver via a YAML registration file and
then receives events via an HTTP push endpoint.  Network transport is
stubbed — ``matrix-nio``'s ``AppServiceProtocol`` will replace the stubs
in a later PR.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .auth_bridge import AuthBridge
from .command_dispatcher import CommandDispatcher
from .config import MatrixBridgeConfig
from .event_streamer import EventStreamer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AppserviceRegistration:
    """Represents the homeserver registration for this Application Service.

    Attributes:
        id: Unique identifier for this AS registration.
        url: Base URL where the homeserver sends events.
        as_token: Token the AS presents to the homeserver.
        hs_token: Token the homeserver presents to the AS.
        sender_localpart: Localpart of the AS bot user (e.g. ``"murphy"``).
        namespaces: Dict of regex lists for ``users``, ``aliases``,
            ``rooms`` claimed by this AS.
        rate_limited: Whether the homeserver rate-limits this AS.
        protocols: Optional third-party protocol identifiers.
    """

    id: str
    url: str
    as_token: str
    hs_token: str
    sender_localpart: str
    namespaces: dict
    rate_limited: bool = False
    protocols: list[str] = field(default_factory=list)


class AppServiceState(str, Enum):
    """Lifecycle state of the Application Service.

    Attributes:
        STOPPED: The AS is not running.
        STARTING: The AS is in the process of initialising.
        RUNNING: The AS is running and accepting events.
        ERROR: A non-recoverable error has occurred.
    """

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


# ---------------------------------------------------------------------------
# AppService
# ---------------------------------------------------------------------------


class AppService:
    """Matrix Application Service — registers with homeserver and processes events.

    This class wires together the :class:`~room_router.RoomRouter`,
    :class:`~command_dispatcher.CommandDispatcher`,
    :class:`~event_streamer.EventStreamer`, and :class:`~auth_bridge.AuthBridge`
    into a single unit that the homeserver communicates with.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
        room_router: Active room router.
        command_dispatcher: Active command dispatcher.
        event_streamer: Active event streamer.
        auth_bridge: Active authentication bridge.
    """

    def __init__(
        self,
        config: MatrixBridgeConfig,
        room_router: object,  # RoomRouter
        command_dispatcher: CommandDispatcher,
        event_streamer: EventStreamer,
        auth_bridge: AuthBridge,
    ) -> None:
        self._config = config
        self._room_router = room_router
        self._dispatcher = command_dispatcher
        self._streamer = event_streamer
        self._auth = auth_bridge
        self._state: AppServiceState = AppServiceState.STOPPED
        self._events_received: int = 0
        self._events_dispatched: int = 0
        self._errors: int = 0
        self._started_at: str | None = None
        logger.debug("AppService initialised")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def get_registration(self) -> AppserviceRegistration:
        """Build and return the :class:`AppserviceRegistration` for this AS.

        Returns:
            A fully-populated :class:`AppserviceRegistration`.
        """
        domain = self._config.domain
        return AppserviceRegistration(
            id=f"murphy-bridge-{domain}",
            url=f"http://localhost:{self._config.appservice_port}",
            as_token=self._config.appservice_token or "CHANGE_ME_AS_TOKEN",
            hs_token=self._config.homeserver_token or "CHANGE_ME_HS_TOKEN",
            sender_localpart="murphy",
            namespaces={
                "users": [
                    {
                        "exclusive": True,
                        "regex": f"@murphy.*:{domain}",
                    }
                ],
                "aliases": [
                    {
                        "exclusive": False,
                        "regex": f"#murphy-.*:{domain}",
                    }
                ],
                "rooms": [],
            },
            rate_limited=False,
            protocols=[],
        )

    def export_registration_yaml(self) -> str:
        """Export a Synapse-compatible registration YAML string.

        The output can be saved to a ``.yaml`` file and referenced in
        Synapse's ``app_service_config_files`` list.  This method uses
        only stdlib — no PyYAML dependency.

        Returns:
            A multi-line YAML string.
        """
        reg = self.get_registration()
        lines: list[str] = [
            f"id: {_yaml_scalar(reg.id)}",
            f"url: {_yaml_scalar(reg.url)}",
            f"as_token: {_yaml_scalar(reg.as_token)}",
            f"hs_token: {_yaml_scalar(reg.hs_token)}",
            f"sender_localpart: {_yaml_scalar(reg.sender_localpart)}",
            f"rate_limited: {str(reg.rate_limited).lower()}",
            "namespaces:",
        ]
        for ns_key in ("users", "aliases", "rooms"):
            items = reg.namespaces.get(ns_key, [])
            lines.append(f"  {ns_key}:")
            if not items:
                lines[-1] += " []"
            else:
                for item in items:
                    exclusive = str(item.get("exclusive", False)).lower()
                    regex = item.get("regex", "")
                    lines.append(f"  - exclusive: {exclusive}")
                    lines.append(f"    regex: {_yaml_scalar(regex)}")
        if reg.protocols:
            lines.append("protocols:")
            for p in reg.protocols:
                lines.append(f"  - {_yaml_scalar(p)}")
        else:
            lines.append("protocols: []")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Application Service.

        Starts the event streamer background thread and marks the AS as
        running.  The HTTP server that receives homeserver push events is
        **stubbed** — ``matrix-nio``'s ``AppServiceProtocol`` replaces it
        in a later PR.
        """
        if self._state == AppServiceState.RUNNING:
            logger.debug("AppService already running")
            return
        self._state = AppServiceState.STARTING
        logger.info("AppService starting on port %d …", self._config.appservice_port)

        try:
            self._streamer.start()
            self._state = AppServiceState.RUNNING
            self._started_at = datetime.now(timezone.utc).isoformat()
            logger.info("AppService running — HTTP listener stub (matrix-nio pending)")
        except Exception as exc:  # pylint: disable=broad-except
            self._state = AppServiceState.ERROR
            self._errors += 1
            logger.exception("AppService failed to start: %s", exc)

    def stop(self) -> None:
        """Stop the Application Service gracefully."""
        logger.info("AppService stopping …")
        self._streamer.stop()
        self._state = AppServiceState.STOPPED
        logger.info("AppService stopped")

    def get_state(self) -> AppServiceState:
        """Return the current :class:`AppServiceState`.

        Returns:
            Current lifecycle state.
        """
        return self._state

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_matrix_event(self, event: dict) -> None:
        """Route an incoming Matrix event pushed by the homeserver.

        Dispatches ``m.room.message`` events to :meth:`handle_room_message`
        and all other events to :meth:`handle_state_event`.

        Args:
            event: The raw Matrix event dict as received from Synapse.
        """
        self._events_received += 1
        event_type = event.get("type", "")
        logger.debug(
            "Received Matrix event type='%s' event_id='%s'",
            event_type,
            event.get("event_id", "?"),
        )

        try:
            if event_type == "m.room.message":
                self.handle_room_message(event)
            else:
                self.handle_state_event(event)
        except Exception as exc:  # pylint: disable=broad-except
            self._errors += 1
            logger.exception(
                "Error handling Matrix event %s: %s",
                event.get("event_id", "?"),
                exc,
            )

    def handle_room_message(self, event: dict) -> None:
        """Process an ``m.room.message`` event.

        If the message body starts with the configured command prefix, it
        is parsed and dispatched via :class:`~command_dispatcher.CommandDispatcher`.
        The response is then sent back to the originating room (stub — actual
        send requires matrix-nio).

        Args:
            event: Raw ``m.room.message`` Matrix event dict.
        """
        content = event.get("content", {})
        body: str = content.get("body", "")
        sender: str = event.get("sender", "")
        room_id: str = event.get("room_id", "")

        if not body.strip().startswith(self._config.command_prefix):
            return

        parsed = self._dispatcher.parse(body, sender, room_id)
        if parsed is None:
            return

        if not self._auth.can_execute_command(sender, parsed.command):
            response_body = (
                f"🚫 Access denied: you do not have permission to run "
                f"`{parsed.command}`."
            )
        else:
            response = self._dispatcher.dispatch(parsed)
            response_body = response.message
            self._events_dispatched += 1

        try:
            self._send_text_to_room(room_id, response_body)
        except RuntimeError:
            logger.debug(
                "Matrix send stubbed — would send to %s: %s",
                room_id,
                response_body[:80],
            )

    def handle_state_event(self, event: dict) -> None:
        """Process a Matrix state or non-message event.

        Currently logs the event for audit purposes.  Future versions will
        handle membership changes, room creation confirmations, etc.

        Args:
            event: Raw Matrix event dict.
        """
        logger.info(
            "State event: type=%s room=%s sender=%s",
            event.get("type"),
            event.get("room_id"),
            event.get("sender"),
        )

    # ------------------------------------------------------------------
    # Statistics & health
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return runtime statistics.

        Returns:
            Dictionary with event counters, state, and streamer stats.
        """
        return {
            "state": self._state.value,
            "started_at": self._started_at,
            "events_received": self._events_received,
            "events_dispatched": self._events_dispatched,
            "errors": self._errors,
            "streamer": self._streamer.get_stats(),
        }

    def health_check(self) -> dict:
        """Return a health-check summary suitable for a monitoring endpoint.

        Returns:
            Dictionary with ``healthy`` bool and component statuses.
        """
        streamer_stats = self._streamer.get_stats()
        healthy = self._state == AppServiceState.RUNNING
        return {
            "healthy": healthy,
            "state": self._state.value,
            "components": {
                "event_streamer": {
                    "running": streamer_stats.get("thread_alive", False),
                    "pending": streamer_stats.get("pending", 0),
                    "delivered": streamer_stats.get("delivered", 0),
                },
                "command_dispatcher": {
                    "commands_registered": len(self._dispatcher.list_commands()),
                },
                "auth_bridge": {
                    "mappings": len(self._auth._mappings),
                },
            },
        }

    # ------------------------------------------------------------------
    # Offline network helpers
    # ------------------------------------------------------------------

    def _send_text_to_room(self, room_id: str, body: str) -> None:
        """Send a text message to a Matrix room.

        .. note::
            **Stub** — requires ``matrix-nio`` SDK (pending PR).
            This method will become ``async`` once the SDK is wired.

        Args:
            room_id: Target Matrix room ID.
            body: Message body (Markdown supported by most clients).

        Raises:
            RuntimeError: Always, until matrix-nio is integrated.
        """
        raise RuntimeError(
            "Matrix text send requires matrix-nio SDK (pending PR)"
        )


# ---------------------------------------------------------------------------
# YAML helpers (stdlib only)
# ---------------------------------------------------------------------------


def _yaml_scalar(value: str) -> str:
    """Quote a string for safe YAML output if necessary.

    Args:
        value: The string to emit.

    Returns:
        A YAML-safe representation (quoted if the value contains special chars).
    """
    # Characters that require quoting in YAML scalar context
    needs_quoting = any(c in value for c in ':#{}[]|>&*!,\'"\\')
    if needs_quoting or not value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
