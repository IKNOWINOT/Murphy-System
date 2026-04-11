"""
Murphy CLI — Command registry & dispatcher
===========================================

Central routing engine that maps ``(resource, command)`` pairs to handler
functions.  Inspired by MiniMax CLI's registry pattern.

Module label: CLI-REGISTRY-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from murphy_cli.args import ParsedArgs
from murphy_cli.output import (
    bold,
    cyan,
    dim,
    green,
    yellow,
)


# ---------------------------------------------------------------------------
# Command descriptor  (CLI-REGISTRY-CMD-001)
# ---------------------------------------------------------------------------

@dataclass
class CommandDef:
    """Metadata for a registered command.  (CLI-REGISTRY-CMD-001)"""

    resource: str                       # top-level resource group (e.g. "auth")
    name: str                           # command name (e.g. "login"), "" for default
    handler: Callable[..., int]         # fn(parsed_args, ctx) -> exit_code
    description: str = ""
    usage: str = ""
    flags: Dict[str, str] = field(default_factory=dict)  # --flag → help text
    aliases: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        if self.name:
            return f"{self.resource} {self.name}"
        return self.resource


# ---------------------------------------------------------------------------
# Registry  (CLI-REGISTRY-CORE-001)
# ---------------------------------------------------------------------------

class CommandRegistry:
    """Command registry and dispatcher.  (CLI-REGISTRY-CORE-001)"""

    def __init__(self) -> None:
        # Keyed by (resource, command_name)
        self._commands: Dict[tuple[str, str], CommandDef] = {}
        self._resource_descriptions: Dict[str, str] = {}

    def register(self, cmd: CommandDef) -> None:
        """Register a command definition.  (CLI-REGISTRY-REG-001)"""
        key = (cmd.resource, cmd.name)
        self._commands[key] = cmd
        for alias in cmd.aliases:
            self._commands[(cmd.resource, alias)] = cmd

    def register_resource(self, resource: str, description: str) -> None:
        """Register a resource group description.  (CLI-REGISTRY-RES-001)"""
        self._resource_descriptions[resource] = description

    def resolve(self, parsed: ParsedArgs) -> Optional[CommandDef]:
        """Resolve parsed args to a command.  (CLI-REGISTRY-RESOLVE-001)"""
        resource = parsed.resource or ""
        command = parsed.command or ""

        # Exact match
        key = (resource, command)
        if key in self._commands:
            return self._commands[key]

        # Resource-level default (command = "")
        default_key = (resource, "")
        if default_key in self._commands:
            # Push the command back onto positional if it wasn't consumed
            if command:
                parsed.positional.insert(0, command)
                parsed.command = None
            return self._commands[default_key]

        return None

    def all_commands(self) -> List[CommandDef]:
        """All unique registered commands.  (CLI-REGISTRY-ALL-001)"""
        seen: set[tuple[str, str]] = set()
        result: List[CommandDef] = []
        for cmd in self._commands.values():
            key = (cmd.resource, cmd.name)
            if key not in seen:
                seen.add(key)
                result.append(cmd)
        return sorted(result, key=lambda c: (c.resource, c.name))

    def resources(self) -> List[str]:
        """Unique resource names, sorted.  (CLI-REGISTRY-RESOURCES-001)"""
        return sorted(set(cmd.resource for cmd in self._commands.values()))

    # -- help rendering  (CLI-REGISTRY-HELP-001) ----------------------------

    def print_global_help(self) -> None:
        """Print top-level help.  (CLI-REGISTRY-HELP-001)"""
        sys.stdout.write(f"\n{bold('murphy')} — CLI for murphy.systems\n\n")
        sys.stdout.write(f"{bold('USAGE')}\n")
        sys.stdout.write(f"  murphy {dim('<resource>')} {dim('<command>')} {dim('[flags]')}\n\n")
        sys.stdout.write(f"{bold('RESOURCES')}\n")

        for res in self.resources():
            desc = self._resource_descriptions.get(res, "")
            sys.stdout.write(f"  {green(res.ljust(16))} {desc}\n")

        sys.stdout.write(f"\n{bold('GLOBAL FLAGS')}\n")
        sys.stdout.write(f"  {cyan('--api-key')}        API key for authentication\n")
        sys.stdout.write(f"  {cyan('--api-url')}        API base URL\n")
        sys.stdout.write(f"  {cyan('--output')}         Output format: text | json\n")
        sys.stdout.write(f"  {cyan('--timeout')}        Request timeout (seconds)\n")
        sys.stdout.write(f"  {cyan('--quiet')}          Suppress non-essential output\n")
        sys.stdout.write(f"  {cyan('--verbose')}        Enable debug output\n")
        sys.stdout.write(f"  {cyan('--no-color')}       Disable ANSI colours\n")
        sys.stdout.write(f"  {cyan('--dry-run')}        Preview without executing\n")
        sys.stdout.write(f"  {cyan('--non-interactive')} Disable prompts (CI/agent)\n")
        sys.stdout.write(f"  {cyan('--version')} / {cyan('-v')}  Show version\n")
        sys.stdout.write(f"  {cyan('--help')} / {cyan('-h')}     Show help\n")
        sys.stdout.write(f"\n  Run {yellow('murphy <resource> --help')} for resource-specific help.\n\n")
        sys.stdout.flush()

    def print_resource_help(self, resource: str) -> None:
        """Print help for a specific resource.  (CLI-REGISTRY-HELP-002)"""
        desc = self._resource_descriptions.get(resource, "")
        sys.stdout.write(f"\n{bold(f'murphy {resource}')} — {desc}\n\n")
        sys.stdout.write(f"{bold('COMMANDS')}\n")

        cmds = [c for c in self.all_commands() if c.resource == resource]
        for cmd in cmds:
            label = cmd.name if cmd.name else "(default)"
            sys.stdout.write(f"  {green(label.ljust(16))} {cmd.description}\n")
            if cmd.usage:
                sys.stdout.write(f"  {dim('  ' + cmd.usage)}\n")

        sys.stdout.write("\n")
        sys.stdout.flush()
