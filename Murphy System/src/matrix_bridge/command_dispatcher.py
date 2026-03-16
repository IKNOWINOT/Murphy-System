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
        # ── Multi-agent / Workflow subsystems ───────────────────────────────────
        self.register_handler("swarm", _handle_swarm, "Swarm system commands (propose, status, build, domain, orchestrate, crew)")
        self.register_handler("workflow", _handle_workflow, "Workflow commands (generate, templates, dag)")
        self.register_handler("agents", _handle_agents, "Agent subsystem commands (list, monitor, personas, runs, history)")
        # ── Self-healing / Intelligence / Research ───────────────────────────────
        self.register_handler("heal", _handle_heal, "Self-healing commands (status, fix, code, blackstart)")
        self.register_handler("research", _handle_research, "Research subsystem commands (run, query, advanced, multi)")
        self.register_handler("monitor", _handle_monitor, "Monitoring commands (health, logs, slo, telemetry, heartbeat)")
        # ── Execution / Confidence / Control ────────────────────────────────────
        self.register_handler("exec", _handle_exec, "Execution subsystem commands (run, status, packet, plan)")
        self.register_handler("confidence", _handle_confidence, "Confidence engine commands (status, score, gate)")
        # ── Security / Compliance / Governance / Safety ──────────────────────────
        self.register_handler("security", _handle_security, "Security subsystem commands (scan, audit, rbac, harden)")
        self.register_handler("compliance", _handle_compliance_cmd, "Compliance commands (status, scan, report, recommended)")
        self.register_handler("governance", _handle_governance, "Governance commands (status, authority, bypass)")
        self.register_handler("hitl", _handle_hitl, "Human-in-the-loop commands (status, graduate, level, approve)")
        self.register_handler("safety", _handle_safety, "Safety subsystem commands (status, validate, orchestrate)")
        # ── LLM / Knowledge ─────────────────────────────────────────────────────
        self.register_handler("llm", _handle_llm, "LLM subsystem commands (status, route, gate, swarm, validate)")
        self.register_handler("kb", _handle_kb, "Knowledge base commands (status, search, query, generate)")
        # ── Integrations / Finance / Trading ─────────────────────────────────────
        self.register_handler("integrations", _handle_integrations, "Integration commands (list, status, add, system)")
        self.register_handler("finance", _handle_finance, "Finance commands (report, portfolio, trading, invoice, budget)")
        self.register_handler("trading", _handle_trading, "Trading bot commands (status, approve, strategy, lifecycle)")
        # ── Infrastructure / Org / Data ──────────────────────────────────────────
        self.register_handler("infra", _handle_infra, "Infrastructure commands (k8s, docker, deploy, fleet, capacity)")
        self.register_handler("org", _handle_org, "Organisation commands (chart, compile, enforce, context)")
        self.register_handler("data", _handle_data, "Data pipeline commands (pipeline, archive, sync, schema)")


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


# ---------------------------------------------------------------------------
# Subsystem stub handlers (added by command registration audit)
# ---------------------------------------------------------------------------


def _handle_swarm(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route SWARM subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[SWARM] {sub} {args_str} — route to swarm subsystem handler".strip(),
        format="text",
    )


def _handle_workflow(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route WORKFLOW subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[WORKFLOW] {sub} {args_str} — route to workflow subsystem handler".strip(),
        format="text",
    )


def _handle_agents(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route AGENTS subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[AGENTS] {sub} {args_str} — route to agents subsystem handler".strip(),
        format="text",
    )


def _handle_heal(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route HEAL subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[HEAL] {sub} {args_str} — route to self-healing subsystem handler".strip(),
        format="text",
    )


def _handle_research(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route RESEARCH subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[RESEARCH] {sub} {args_str} — route to research subsystem handler".strip(),
        format="text",
    )


def _handle_monitor(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route MONITOR subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[MONITOR] {sub} {args_str} — route to monitoring subsystem handler".strip(),
        format="text",
    )


def _handle_exec(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route EXEC subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[EXEC] {sub} {args_str} — route to execution subsystem handler".strip(),
        format="text",
    )


def _handle_confidence(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route CONFIDENCE subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[CONFIDENCE] {sub} {args_str} — route to confidence subsystem handler".strip(),
        format="text",
    )


def _handle_security(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route SECURITY subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[SECURITY] {sub} {args_str} — route to security subsystem handler".strip(),
        format="text",
    )


def _handle_compliance_cmd(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Route COMPLIANCE subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[COMPLIANCE] {sub} {args_str} — route to compliance subsystem handler".strip(),
        format="text",
    )


def _handle_governance(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route GOVERNANCE subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[GOVERNANCE] {sub} {args_str} — route to governance subsystem handler".strip(),
        format="text",
    )


def _handle_hitl(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route HITL subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[HITL] {sub} {args_str} — route to HITL subsystem handler".strip(),
        format="text",
    )


def _handle_safety(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route SAFETY subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[SAFETY] {sub} {args_str} — route to safety subsystem handler".strip(),
        format="text",
    )


def _handle_llm(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route LLM subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[LLM] {sub} {args_str} — route to LLM subsystem handler".strip(),
        format="text",
    )


def _handle_kb(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route KB (knowledge base) subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[KB] {sub} {args_str} — route to knowledge subsystem handler".strip(),
        format="text",
    )


def _handle_integrations(
    dispatcher: CommandDispatcher, cmd: ParsedCommand
) -> CommandResponse:
    """Route INTEGRATIONS subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[INTEGRATIONS] {sub} {args_str} — route to integrations subsystem handler".strip(),
        format="text",
    )


def _handle_finance(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route FINANCE subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[FINANCE] {sub} {args_str} — route to finance subsystem handler".strip(),
        format="text",
    )


def _handle_trading(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route TRADING subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[TRADING] {sub} {args_str} — route to trading subsystem handler".strip(),
        format="text",
    )


def _handle_infra(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route INFRA subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[INFRA] {sub} {args_str} — route to infrastructure subsystem handler".strip(),
        format="text",
    )


def _handle_org(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route ORG subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[ORG] {sub} {args_str} — route to organisation subsystem handler".strip(),
        format="text",
    )


def _handle_data(dispatcher: CommandDispatcher, cmd: ParsedCommand) -> CommandResponse:
    """Route DATA subsystem commands."""
    sub = cmd.subcommand or ""
    args_str = " ".join(cmd.args)
    return CommandResponse(
        success=True,
        message=f"[DATA] {sub} {args_str} — route to data subsystem handler".strip(),
        format="text",
    )
