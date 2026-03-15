"""
Command Dispatcher for the Murphy Matrix Bridge.

Parses ``!murphy <command> [args...]`` messages from Matrix rooms and
dispatches them to registered handler callables.
"""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ParsedCommand:
    """Represents a fully-parsed Murphy bot command.

    Attributes:
        prefix: The command prefix, e.g. ``"!murphy"``.
        command: Primary command token, e.g. ``"health"``.
        subcommand: Optional second token, e.g. ``"check"``.
        args: Positional arguments following the (sub)command.
        kwargs: Key/value pairs parsed from ``--key=value`` tokens.
        raw: The original raw message string.
        sender: Matrix user ID of the message author.
        room_id: Matrix room ID where the message was received.
        timestamp: ISO-8601 UTC timestamp of the message.
    """

    prefix: str
    command: str
    subcommand: str | None
    args: list[str]
    kwargs: dict[str, str]
    raw: str
    sender: str
    room_id: str
    timestamp: str


@dataclass
class CommandResponse:
    """Encapsulates the result of dispatching a :class:`ParsedCommand`.

    Attributes:
        success: Whether the command completed without errors.
        message: Human-readable result text (Markdown supported).
        data: Optional structured data payload.
        room_id: Target room for the reply (defaults to the originating room).
        format: Content type hint — ``"text"``, ``"markdown"``, or ``"code"``.
    """

    success: bool
    message: str
    data: dict | None = None
    room_id: str | None = None
    format: str = "text"


# ---------------------------------------------------------------------------
# Internal handler record
# ---------------------------------------------------------------------------


@dataclass
class _HandlerEntry:
    command: str
    handler: Callable[["CommandDispatcher", ParsedCommand], CommandResponse]
    description: str


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class CommandDispatcher:
    """Parses and dispatches ``!murphy`` commands from Matrix rooms.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
        room_router: The active room router (imported inline to avoid cycles).
    """

    def __init__(
        self,
        config: MatrixBridgeConfig,
        room_router: object,  # RoomRouter – avoid circular import at runtime
    ) -> None:
        self._config = config
        self._room_router = room_router
        self._handlers: dict[str, _HandlerEntry] = {}
        self._register_builtins()
        logger.debug("CommandDispatcher initialised with %d built-in handlers", len(self._handlers))

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(
        self, raw_message: str, sender: str, room_id: str
    ) -> ParsedCommand | None:
        """Parse a raw Matrix message into a :class:`ParsedCommand`.

        Returns ``None`` if the message does not start with the configured
        command prefix or cannot be tokenised.

        Args:
            raw_message: The full body text of the Matrix ``m.text`` event.
            sender: Matrix user ID (e.g. ``"@alice:example.com"``).
            room_id: Matrix room ID.

        Returns:
            A :class:`ParsedCommand` or ``None``.
        """
        stripped = raw_message.strip()
        if not stripped.lower().startswith(self._config.command_prefix.lower()):
            return None

        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            logger.warning("Failed to tokenise command from %s: %s", sender, exc)
            return None

        if len(tokens) < 2:
            # Bare prefix with no command → show help
            tokens.append("help")

        prefix = tokens[0]
        command = tokens[1].lower()
        remaining = tokens[2:]

        subcommand: str | None = None
        args: list[str] = []
        kwargs: dict[str, str] = {}

        for tok in remaining:
            if tok.startswith("--"):
                if "=" in tok:
                    key, _, val = tok[2:].partition("=")
                    kwargs[key] = val
                else:
                    kwargs[tok[2:]] = "true"
            elif subcommand is None and not tok.startswith("-"):
                subcommand = tok.lower()
            else:
                args.append(tok)

        return ParsedCommand(
            prefix=prefix,
            command=command,
            subcommand=subcommand,
            args=args,
            kwargs=kwargs,
            raw=raw_message,
            sender=sender,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, cmd: ParsedCommand) -> CommandResponse:
        """Dispatch a :class:`ParsedCommand` to its registered handler.

        Falls back to the ``help`` command if no handler is found.

        Args:
            cmd: A parsed command to execute.

        Returns:
            A :class:`CommandResponse` with the result.
        """
        entry = self._handlers.get(cmd.command)
        if entry is None:
            logger.info(
                "Unknown command '%s' from %s — returning help", cmd.command, cmd.sender
            )
            return CommandResponse(
                success=False,
                message=f"Unknown command `{cmd.command}`. Try `!murphy help`.",
                format="markdown",
            )

        try:
            response = entry.handler(self, cmd)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Handler for '%s' raised: %s", cmd.command, exc)
            response = CommandResponse(
                success=False,
                message=f"⚠️ Internal error executing `{cmd.command}`: {exc}",
                format="markdown",
            )

        if response.room_id is None:
            response.room_id = cmd.room_id
        return response

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_handler(
        self,
        command: str,
        handler: Callable[["CommandDispatcher", ParsedCommand], CommandResponse],
        description: str = "",
    ) -> None:
        """Register a handler callable for a command token.

        Args:
            command: The command token (without prefix), e.g. ``"deploy"``.
            handler: A callable ``(dispatcher, cmd) → CommandResponse``.
            description: Short description shown in ``!murphy help``.
        """
        self._handlers[command.lower()] = _HandlerEntry(
            command=command.lower(),
            handler=handler,
            description=description,
        )
        logger.debug("Registered handler for command '%s'", command)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_commands(self) -> list[dict]:
        """Return a list of registered commands with descriptions.

        Returns:
            List of ``{"command": str, "description": str}`` dicts.
        """
        return [
            {"command": e.command, "description": e.description}
            for e in sorted(self._handlers.values(), key=lambda x: x.command)
        ]

    def get_help(self, command: str | None = None) -> str:
        """Return a Markdown help string.

        Args:
            command: If provided, show help for a single command; otherwise
                show the full command list.

        Returns:
            A Markdown-formatted help string.
        """
        if command and command in self._handlers:
            entry = self._handlers[command]
            return f"**`!murphy {entry.command}`** — {entry.description}"

        lines = ["## Murphy Bot Commands\n"]
        for entry in sorted(self._handlers.values(), key=lambda x: x.command):
            lines.append(f"- **`!murphy {entry.command}`** — {entry.description}")
        lines.append("\nUse `!murphy help <command>` for more detail.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Built-in handlers
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register all built-in command handlers."""
        self.register_handler("help", _handle_help, "Show available commands")
        self.register_handler("status", _handle_status, "Show bridge status summary")
        self.register_handler("health", _handle_health, "Check Murphy system health")
        self.register_handler("version", _handle_version, "Show Murphy version information")
        self.register_handler("list-modules", _handle_list_modules, "List all registered Murphy modules")
        self.register_handler("list-rooms", _handle_list_rooms, "List all Matrix rooms in the bridge")
        # Management Systems commands — delegate to management_commands handlers
        self.register_handler("board", _handle_board, "Board management (list, create, view, kanban)")
        self.register_handler("status-label", _handle_status_label, "Status label management")
        self.register_handler("timeline", _handle_timeline, "Timeline/Gantt engine (view, add, milestones)")
        self.register_handler("workspace", _handle_workspace, "Workspace management")
        self.register_handler("recipe", _handle_recipe, "Automation recipes (list, create, run)")
        self.register_handler("dashboard", _handle_dashboard, "Dashboard generator (standup, weekly)")
        self.register_handler("sync", _handle_sync, "Integration bridge sync")
        self.register_handler("form", _handle_form, "Form builder (list, start, submit)")
        self.register_handler("doc", _handle_doc, "Document manager (list, create, view, search)")
        self.register_handler("onboard", _handle_onboard, "Onboarding flow (init, start, questions, answer, assign, complete)")
        self.register_handler("gate", _handle_gate, "Business gate management (create, list, evaluate, status)")
        self.register_handler("setpoint", _handle_setpoint, "Control loop setpoints (show, set, ranges)")
        self.register_handler("schedule", _handle_schedule, "Business loop scheduling (loops, configure, status)")
        self.register_handler("skm", _handle_skm, "Sense-Know-Model loop (status, sense, know, model, cycle)")
        self.register_handler("automation", _handle_automation, "Unified automation view and control (list, summary, types, mode, hub, rbac, readiness, scale, loop, scheduler, marketplace, native, self, onboard-engine, building, manufacturing, sales, compliance-bridge, full, deploy)")


# ---------------------------------------------------------------------------
# Built-in handler implementations
# ---------------------------------------------------------------------------


def _handle_help(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy help [command]``."""
    target = cmd.subcommand or (cmd.args[0] if cmd.args else None)
    text = dispatcher.get_help(target)
    return CommandResponse(success=True, message=text, format="markdown")


def _handle_status(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy status``."""
    cfg = dispatcher._config
    msg = (
        "## Murphy Bridge Status\n\n"
        f"- **Homeserver:** `{cfg.homeserver_url}`\n"
        f"- **Bot user:** `{cfg.bot_user_id}`\n"
        f"- **Domain:** `{cfg.domain}`\n"
        f"- **Rooms configured:** {len(cfg.room_mappings)}\n"
        f"- **E2EE:** {'enabled' if cfg.enable_e2ee else 'disabled'}\n"
    )
    return CommandResponse(success=True, message=msg, format="markdown")


def _handle_health(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy health [check]``."""
    msg = (
        "## Murphy Health Check\n\n"
        "✅ Bridge process: **running**\n"
        "✅ Config: **loaded**\n"
        "⚠️ Matrix SDK: **not connected** *(network calls stubbed — matrix-nio pending)*\n"
        "\nUse `!murphy health check` for a deep subsystem scan."
    )
    return CommandResponse(success=True, message=msg, format="markdown")


def _handle_version(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy version``."""
    from . import __codename__, __version__  # type: ignore[attr-defined]

    msg = (
        f"## Murphy Matrix Bridge\n\n"
        f"**Version:** `{__version__}` — *{__codename__}*\n"
        "**Python:** 3.10+\n"
    )
    return CommandResponse(success=True, message=msg, format="markdown")


def _handle_list_modules(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy list-modules``."""
    from .room_router import MODULE_TO_ROOM  # local import avoids cycle at class level

    lines = ["## Murphy Modules\n"]
    grouped: dict[str, list[str]] = {}
    for mod, room in sorted(MODULE_TO_ROOM.items()):
        grouped.setdefault(room, []).append(mod)
    for room, mods in sorted(grouped.items()):
        lines.append(f"**{room}** ({len(mods)} modules)")
        lines.append(", ".join(f"`{m}`" for m in sorted(mods)))
        lines.append("")
    return CommandResponse(
        success=True, message="\n".join(lines), format="markdown"
    )


def _handle_list_rooms(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy list-rooms``."""
    rooms = dispatcher._config.room_mappings
    lines = ["## Murphy Matrix Rooms\n"]
    for key, rm in sorted(rooms.items()):
        enc = "🔒" if rm.encrypted else "🔓"
        lines.append(f"- {enc} **{rm.display_name}** — `{rm.room_alias}`")
    return CommandResponse(success=True, message="\n".join(lines), format="markdown")


def _handle_board(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy board`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_board
    return handle_board(dispatcher, cmd)


def _handle_status_label(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy status-label`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_status
    return handle_status(dispatcher, cmd)


def _handle_timeline(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy timeline`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_timeline
    return handle_timeline(dispatcher, cmd)


def _handle_workspace(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy workspace`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_workspace
    return handle_workspace(dispatcher, cmd)


def _handle_recipe(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy recipe`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_recipe
    return handle_recipe(dispatcher, cmd)


def _handle_dashboard(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy dashboard`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_dashboard
    return handle_dashboard(dispatcher, cmd)


def _handle_sync(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy sync`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_sync
    return handle_sync(dispatcher, cmd)


def _handle_form(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy form`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_form
    return handle_form(dispatcher, cmd)


def _handle_doc(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy doc`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_doc
    return handle_doc(dispatcher, cmd)


def _handle_onboard(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy onboard`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_onboard
    return handle_onboard(dispatcher, cmd)


def _handle_gate(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy gate`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_gate
    return handle_gate(dispatcher, cmd)


def _handle_setpoint(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy setpoint`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_setpoint
    return handle_setpoint(dispatcher, cmd)


def _handle_schedule(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy schedule`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_schedule
    return handle_schedule(dispatcher, cmd)


def _handle_skm(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy skm`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_skm
    return handle_skm(dispatcher, cmd)


def _handle_automation(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Handle ``!murphy automation`` — delegate to management_systems.management_commands."""
    from management_systems.management_commands import handle_automation
    return handle_automation(dispatcher, cmd)
