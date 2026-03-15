# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Core Matrix bot for the Murphy System.

Provides :class:`MurphyMatrixBot` (AsyncClient-based command dispatcher) and
:class:`MurphyAPIBridge` (lightweight httpx wrapper for Murphy API calls).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

try:
    import nio
    from nio import AsyncClient, MatrixRoom, RoomMessageText
except ImportError:  # pragma: no cover — matrix-nio optional
    nio = None  # type: ignore
    AsyncClient = None  # type: ignore
    MatrixRoom = None  # type: ignore
    RoomMessageText = None  # type: ignore

from .matrix_config import MatrixBotConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Murphy API bridge (simple httpx wrapper per spec)
# ---------------------------------------------------------------------------


class MurphyAPIBridge:
    """Async HTTP client for Murphy System API."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        """Initialise the bridge with the given base URL and timeout."""
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def get(self, path: str, params: Optional[Dict] = None) -> dict:
        """Perform a GET request and return parsed JSON.

        Args:
            path: API path relative to base_url.
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RuntimeError: On network errors or non-2xx responses.
        """
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise RuntimeError(f"GET {path} failed: {exc}") from exc

    async def post(self, path: str, json: Optional[dict] = None) -> dict:
        """Perform a POST request and return parsed JSON.

        Args:
            path: API path relative to base_url.
            json: Optional request body as a dict.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RuntimeError: On network errors or non-2xx responses.
        """
        try:
            resp = await self._client.post(path, json=json)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise RuntimeError(f"POST {path} failed: {exc}") from exc

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Simple circuit breaker — CLOSED → OPEN → HALF_OPEN → CLOSED."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, threshold: int = 5, timeout: int = 60) -> None:
        self.threshold = threshold
        self.timeout = timeout
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: float = 0.0

    def record_success(self) -> None:
        """Reset the breaker to CLOSED after a successful request."""
        self._failures = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        """Increment failure count and open the breaker when threshold is hit."""
        self._failures += 1
        if self._failures >= self.threshold:
            self._state = self.OPEN
            self._opened_at = time.monotonic()

    def is_open(self) -> bool:
        """Return True if the breaker is OPEN (requests should not be allowed)."""
        if self._state == self.OPEN:
            if time.monotonic() - self._opened_at >= self.timeout:
                self._state = self.HALF_OPEN
                return False
            return True
        return False

    @property
    def state(self) -> str:
        """Current breaker state string."""
        return self._state


# ---------------------------------------------------------------------------
# Murphy API client (circuit-breaker-wrapped, config-based)
# ---------------------------------------------------------------------------


class MurphyAPIClient:
    """Async httpx client for the Murphy REST API with circuit breaker.

    This is the config-based client used internally by MurphyMatrixBot.
    For external use, prefer :class:`MurphyAPIBridge`.
    """

    def __init__(self, config: MatrixBotConfig) -> None:
        self.base_url = config.murphy_api_url.rstrip("/")
        self.timeout = config.api_timeout
        self.circuit = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            timeout=config.circuit_breaker_timeout,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get(self, path: str, **params: Any) -> Any:
        """Perform a GET request."""
        return await self._request("GET", path, params=params or None)

    async def post(self, path: str, body: Any = None) -> Any:
        """Perform a POST request."""
        return await self._request("POST", path, json=body)

    async def patch(self, path: str, body: Any = None) -> Any:
        """Perform a PATCH request."""
        return await self._request("PATCH", path, json=body)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self.circuit.is_open():
            raise RuntimeError(
                "Murphy API circuit breaker is OPEN (too many failures). Try again later."
            )
        url = f"{self.base_url}{path}"
        client = await self._get_client()
        try:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            self.circuit.record_success()
            try:
                return resp.json()
            except Exception:
                return resp.text
        except Exception as exc:
            self.circuit.record_failure()
            raise RuntimeError(f"API error [{method} {path}]: {exc}") from exc


# ---------------------------------------------------------------------------
# Command type alias
# ---------------------------------------------------------------------------

CommandHandler = Callable[..., Coroutine[Any, Any, str]]


# ---------------------------------------------------------------------------
# Core bot
# ---------------------------------------------------------------------------


class MurphyMatrixBot:
    """Core Matrix bot that connects to homeserver and routes commands.

    Commands are registered via :meth:`register_command` and dispatched
    when a message matching ``!murphy <command> [args...]`` is received.
    """

    COMMAND_PREFIX = "!murphy"

    def __init__(self, config: MatrixBotConfig) -> None:
        """Initialise the bot with the given configuration.

        Args:
            config: Validated :class:`MatrixBotConfig` instance.

        Raises:
            ImportError: If matrix-nio is not installed.
        """
        if nio is None:
            raise ImportError(
                "matrix-nio is required. Install with: pip install 'matrix-nio[e2e]>=0.24.0'"
            )
        self.config = config
        self.api = MurphyAPIClient(config)
        self.client = AsyncClient(config.homeserver, config.user_id)
        self._running = False
        self._hitl_event_map: Dict[str, str] = {}
        self._start_time: float = 0.0
        # Command registry: name → (handler, help_text)
        self._commands: Dict[str, tuple] = {}
        # Register built-in commands
        self.register_command("help", self._builtin_help, "Show this help message")
        self.register_command("ping", self._builtin_ping, "Check bot latency")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_command(
        self,
        name: str,
        handler: CommandHandler,
        help_text: str,
    ) -> None:
        """Register a command handler for ``!murphy <name>``.

        Args:
            name: Command name (without the ``!murphy`` prefix).
            handler: Async callable ``(room_id: str, args: list) -> str`` that
                returns an HTML string to send as the reply.
            help_text: Short description shown in ``!murphy help``.
        """
        self._commands[name.lower()] = (handler, help_text)

    async def start(self) -> None:
        """Login, join rooms, start listening for messages."""
        errors = self.config.validate()
        if errors:
            raise ValueError("Config errors: " + "; ".join(errors))

        if self.config.access_token:
            self.client.access_token = self.config.access_token
            self.client.user_id = self.config.user_id
        else:
            resp = await self.client.login(self.config.password)
            if hasattr(resp, "access_token"):
                logger.info("Logged in as %s", self.config.user_id)
            else:
                raise RuntimeError(f"Login failed: {resp}")

        self.client.add_event_callback(self.on_message, RoomMessageText)
        self._running = True
        self._start_time = time.monotonic()
        logger.info("Murphy Matrix bot started — prefix: %s", self.COMMAND_PREFIX)
        await self.client.sync_forever(timeout=30000, full_state=True)

    async def stop(self) -> None:
        """Stop the bot and close connections."""
        self._running = False
        await self.api.close()
        await self.client.close()

    async def send_message(
        self, room_id: str, body: str, html: Optional[str] = None
    ) -> None:
        """Send a message to a Matrix room (plain + optional HTML).

        Args:
            room_id: Target Matrix room ID.
            body: Plain-text fallback body.
            html: Optional HTML-formatted body.
        """
        content: Dict[str, Any] = {
            "msgtype": "m.text",
            "body": body,
        }
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html
        try:
            await self.client.room_send(room_id, "m.room.message", content)
        except Exception as exc:
            logger.error("Failed to send message to %s: %s", room_id, exc)

    async def send_notice(
        self, room_id: str, body: str, html: Optional[str] = None
    ) -> None:
        """Send a notice (non-highlighted) to a Matrix room.

        Args:
            room_id: Target Matrix room ID.
            body: Plain-text fallback body.
            html: Optional HTML-formatted body.
        """
        content: Dict[str, Any] = {
            "msgtype": "m.notice",
            "body": body,
        }
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html
        try:
            await self.client.room_send(room_id, "m.room.message", content)
        except Exception as exc:
            logger.error("Failed to send notice to %s: %s", room_id, exc)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_message(self, room: "MatrixRoom", event: "RoomMessageText") -> None:
        """Handle incoming messages. Route ``!murphy`` commands to handlers.

        Args:
            room: The Matrix room the message was received in.
            event: The incoming message event.
        """
        if event.sender == self.config.user_id:
            return
        body = (event.body or "").strip()
        if not body.lower().startswith(self.COMMAND_PREFIX.lower()):
            return
        args_str = body[len(self.COMMAND_PREFIX):].strip()
        args = args_str.split() if args_str else []
        command = args[0].lower() if args else ""
        cmd_args = args[1:] if len(args) > 1 else []
        try:
            await self._dispatch_command(room.room_id, event.sender, command, cmd_args)
        except Exception:
            logger.exception("Unhandled error processing command: %s", command)

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def _dispatch_command(
        self,
        room_id: str,
        sender: str,
        command: str,
        args: list,
    ) -> None:
        """Parse and dispatch to registered command handler.

        Args:
            room_id: Room to reply in.
            sender: Matrix user ID of the sender.
            command: The command name (without prefix).
            args: Remaining tokens after the command name.
        """
        logger.info(
            "Command from %s in %s: %s %s", sender, room_id, command, args
        )
        handler_entry = self._commands.get(command)
        if handler_entry is None:
            await self.send_message(
                room_id,
                f"Unknown command '{command}'. Try '!murphy help'.",
            )
            return
        handler, _ = handler_entry
        try:
            response = await handler(room_id, args)
            if response:
                plain = _strip_html(response)
                await self.send_message(room_id, plain, response)
        except Exception as exc:
            logger.exception("Error in command handler for '%s'", command)
            await self.send_message(room_id, f"Error: {exc}")

    # ------------------------------------------------------------------
    # Built-in commands
    # ------------------------------------------------------------------

    async def _builtin_help(self, room_id: str, args: list) -> str:
        """List all registered commands.

        Args:
            room_id: Room that triggered the help command.
            args: Optional args (unused).

        Returns:
            HTML string listing all registered commands.
        """
        lines = ["<b>Murphy System Bot Commands</b><br/>"]
        for name, (_, help_text) in sorted(self._commands.items()):
            lines.append(f"<code>!murphy {name}</code> — {help_text}")
        return "<br/>".join(lines)

    async def _builtin_ping(self, room_id: str, args: list) -> str:
        """Return bot latency and uptime.

        Args:
            room_id: Room that triggered the ping command.
            args: Optional args (unused).

        Returns:
            HTML string with uptime information.
        """
        elapsed = time.monotonic() - self._start_time if self._start_time else 0
        uptime_s = int(elapsed)
        h, remainder = divmod(uptime_s, 3600)
        m, s = divmod(remainder, 60)
        return (
            f"<b>🏓 Pong!</b><br/>"
            f"Uptime: {h}h {m}m {s}s"
        )

    # ------------------------------------------------------------------
    # HITL reaction registration (called by matrix_hitl.py)
    # ------------------------------------------------------------------

    def register_hitl_event(self, event_id: str, intervention_id: str) -> None:
        """Register an event_id → intervention_id mapping for reaction-based HITL.

        Args:
            event_id: Matrix event ID of the posted intervention message.
            intervention_id: Murphy HITL intervention ID.
        """
        self._hitl_event_map[event_id] = intervention_id

    # ------------------------------------------------------------------
    # Internal send helper (used by matrix_hitl.py and matrix_notifications.py)
    # ------------------------------------------------------------------

    async def _send(
        self, room_id: str, html: str, plain: Optional[str] = None
    ) -> Optional[str]:
        """Send an HTML message and return the event_id if available.

        Args:
            room_id: Target room ID.
            html: HTML-formatted message body.
            plain: Optional plain-text fallback. Auto-generated if not supplied.

        Returns:
            Matrix event_id string, or None on failure.
        """
        content = {
            "msgtype": "m.text",
            "body": plain or _strip_html(html),
            "format": "org.matrix.custom.html",
            "formatted_body": html,
        }
        try:
            resp = await self.client.room_send(room_id, "m.room.message", content)
            return getattr(resp, "event_id", None)
        except Exception as exc:
            logger.error("Failed to send message to %s: %s", room_id, exc)
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_html(html: str) -> str:
    """Convert a basic HTML string to plain text.

    Args:
        html: HTML string to strip.

    Returns:
        Plain-text string with tags removed and <br> replaced by newlines.
    """
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


__all__ = ["MurphyAPIBridge", "MurphyAPIClient", "MurphyMatrixBot"]
