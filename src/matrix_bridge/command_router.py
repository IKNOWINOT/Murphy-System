# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Command Router — routes ``!murphy`` Matrix messages to Murphy subsystems.

Supported syntax::

    !murphy <subsystem> <command> [args...]
    !murphy help [subsystem]
    !murphy <top-level-command> [args...]

Natural-language routing falls back to the system_librarian when no exact
match is found and ``nlp_enabled=True``.

Results are returned as ``(plain, html)`` tuples suitable for
:meth:`~murphy.matrix_bridge.MatrixClient.send_formatted`.

Permission levels
-----------------
admin    → all commands
operator → everything except env/admin commands
viewer   → read-only / query commands only
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MessagePair = Tuple[str, str]  # (plain, html)

# ---------------------------------------------------------------------------
# Permission levels
# ---------------------------------------------------------------------------

PERM_VIEWER = 0
PERM_OPERATOR = 50
PERM_ADMIN = 100

_PERM_NAMES: Dict[int, str] = {
    PERM_VIEWER: "viewer",
    PERM_OPERATOR: "operator",
    PERM_ADMIN: "admin",
}


# ---------------------------------------------------------------------------
# Command descriptor
# ---------------------------------------------------------------------------

@dataclass
class CommandDef:
    """Describes a single routable command."""

    name: str
    handler: Callable[..., Awaitable[MessagePair]]
    description: str = ""
    usage: str = ""
    min_permission: int = PERM_VIEWER
    aliases: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolver callback type
# ---------------------------------------------------------------------------

#: Signature: ``(subsystem: str, command: str, args: list[str]) → MessagePair``
SubsystemCallable = Callable[[str, str, List[str]], Awaitable[MessagePair]]


def _h(text: str) -> str:
    """HTML-escape *text*."""
    import html as _html_mod
    return _html_mod.escape(str(text))


# ---------------------------------------------------------------------------
# CommandRouter
# ---------------------------------------------------------------------------

class CommandRouter:
    """Routes ``!murphy`` commands from Matrix to Murphy subsystems.

    Parameters
    ----------
    prefix:
        Command prefix (default ``!murphy``).
    nlp_enabled:
        Fall back to system_librarian for unrecognised commands.
    permission_resolver:
        ``async (user_id: str) → int`` — returns the permission level for a
        Matrix user.  Defaults to granting everyone ``PERM_OPERATOR``.
    """

    def __init__(
        self,
        prefix: str = "!murphy",
        nlp_enabled: bool = False,
        permission_resolver: Optional[Callable[[str], Awaitable[int]]] = None,
    ) -> None:
        self.prefix = prefix
        self.nlp_enabled = nlp_enabled
        self._permission_resolver = permission_resolver or self._default_permission
        self._commands: Dict[str, CommandDef] = {}
        self._subsystem_handler: Optional[SubsystemCallable] = None
        self._nlp_handler: Optional[
            Callable[[str, str], Awaitable[MessagePair]]
        ] = None
        self._register_builtins()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_command(self, cmd: CommandDef) -> None:
        """Register a :class:`CommandDef`.  Aliases are registered too."""
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def set_subsystem_handler(self, handler: SubsystemCallable) -> None:
        """Register a generic ``(subsystem, command, args) → MessagePair`` handler."""
        self._subsystem_handler = handler

    def set_nlp_handler(
        self, handler: Callable[[str, str], Awaitable[MessagePair]]
    ) -> None:
        """Register a natural-language fallback ``(user_id, text) → MessagePair``."""
        self._nlp_handler = handler

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self, user_id: str, room_id: str, message: str
    ) -> Optional[MessagePair]:
        """Parse *message* and dispatch to the appropriate handler.

        Returns ``None`` if the message is not a recognised command.
        """
        stripped = message.strip()
        if not stripped.lower().startswith(self.prefix.lower()):
            return None

        body = stripped[len(self.prefix):].strip()
        if not body:
            return await self._handle_help(user_id, [])

        try:
            parts = shlex.split(body)
        except ValueError:
            parts = body.split()

        if not parts:
            return await self._handle_help(user_id, [])

        perm = await self._permission_resolver(user_id)
        top = parts[0].lower()

        # Built-in top-level commands
        if top in self._commands:
            cmd = self._commands[top]
            if perm < cmd.min_permission:
                return self._permission_denied(user_id, top, perm, cmd.min_permission)
            try:
                return await cmd.handler(user_id, parts[1:])
            except Exception as exc:
                logger.exception("Command handler error for %s: %s", top, exc)
                return self._fmt_error(f"Internal error: {exc}")

        # Subsystem routing: !murphy <subsystem> <command> [args...]
        if len(parts) >= 2 and self._subsystem_handler:
            subsystem = parts[0]
            command = parts[1]
            args = parts[2:]
            if perm < PERM_OPERATOR:
                return self._permission_denied(user_id, f"{subsystem} {command}", perm, PERM_OPERATOR)
            try:
                return await self._subsystem_handler(subsystem, command, args)
            except Exception as exc:
                logger.exception("Subsystem handler error for %s/%s: %s", subsystem, command, exc)
                return self._fmt_error(f"Subsystem error: {exc}")

        # NLP fallback
        if self.nlp_enabled and self._nlp_handler:
            try:
                return await self._nlp_handler(user_id, stripped)
            except Exception as exc:
                logger.warning("NLP handler error: %s", exc)

        return self._fmt_error(
            f"Unknown command: ``{_h(top)}``.  Try ``{_h(self.prefix)} help``."
        )

    # ------------------------------------------------------------------
    # Built-in commands
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        self.register_command(CommandDef(
            name="help",
            handler=self._handle_help,
            description="Show available commands",
            usage="help [subsystem]",
            min_permission=PERM_VIEWER,
        ))
        self.register_command(CommandDef(
            name="ping",
            handler=self._handle_ping,
            description="Check bot responsiveness",
            usage="ping",
            min_permission=PERM_VIEWER,
        ))
        self.register_command(CommandDef(
            name="whoami",
            handler=self._handle_whoami,
            description="Show your permission level",
            usage="whoami",
            min_permission=PERM_VIEWER,
        ))
        self.register_command(CommandDef(
            name="commands",
            handler=self._handle_commands,
            description="List all registered commands",
            usage="commands",
            min_permission=PERM_VIEWER,
            aliases=["cmds"],
        ))

    async def _handle_help(self, user_id: str, args: List[str]) -> MessagePair:
        lines_plain = [f"{self.prefix} command reference", ""]
        rows_html = ""
        for name, cmd in sorted(self._commands.items()):
            if cmd.name != name:
                continue  # skip alias entries
            rows_html += (
                f"<tr><td><code>{_h(self.prefix)} {_h(cmd.usage or cmd.name)}</code></td>"
                f"<td>{_h(cmd.description)}</td></tr>"
            )
            lines_plain.append(f"  {self.prefix} {cmd.usage or cmd.name}  — {cmd.description}")
        plain = "\n".join(lines_plain)
        html = (
            f"<b>☠ Murphy Bot — Command Reference</b><br>"
            f"<table><tr><th>Command</th><th>Description</th></tr>"
            f"{rows_html}</table>"
        )
        return plain, html

    async def _handle_ping(self, user_id: str, args: List[str]) -> MessagePair:
        return "Pong! Murphy System is operational.", "<b>Pong!</b> Murphy System is operational. ✅"

    async def _handle_whoami(self, user_id: str, args: List[str]) -> MessagePair:
        perm = await self._permission_resolver(user_id)
        perm_name = _PERM_NAMES.get(perm, str(perm))
        plain = f"User: {user_id}  Permission: {perm_name} ({perm})"
        html = (
            f"<b>User:</b> <code>{_h(user_id)}</code><br>"
            f"<b>Permission:</b> {_h(perm_name)} ({perm})"
        )
        return plain, html

    async def _handle_commands(self, user_id: str, args: List[str]) -> MessagePair:
        names = sorted({cmd.name for cmd in self._commands.values()})
        plain = "Registered commands:\n" + "\n".join(f"  {self.prefix} {n}" for n in names)
        items = "".join(f"<li><code>{_h(self.prefix)} {_h(n)}</code></li>" for n in names)
        html = f"<b>Registered commands:</b><ul>{items}</ul>"
        return plain, html

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _default_permission(user_id: str) -> int:
        return PERM_OPERATOR

    def _permission_denied(
        self, user_id: str, command: str, have: int, need: int
    ) -> MessagePair:
        have_name = _PERM_NAMES.get(have, str(have))
        need_name = _PERM_NAMES.get(need, str(need))
        plain = (
            f"Permission denied for {user_id}: "
            f"command '{command}' requires {need_name}, you have {have_name}."
        )
        html = (
            f"<b>🚫 Permission denied</b><br>"
            f"Command <code>{_h(command)}</code> requires <b>{_h(need_name)}</b> "
            f"but you have <b>{_h(have_name)}</b>."
        )
        return plain, html

    @staticmethod
    def _fmt_error(msg: str) -> MessagePair:
        plain = f"Error: {msg}"
        html = f"<b>❌ Error:</b> {msg}"
        return plain, html


__all__ = [
    "CommandRouter",
    "CommandDef",
    "MessagePair",
    "PERM_VIEWER",
    "PERM_OPERATOR",
    "PERM_ADMIN",
]
