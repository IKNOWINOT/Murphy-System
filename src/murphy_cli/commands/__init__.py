"""
Murphy CLI — Command modules
=============================

Each sub-module registers its commands with the global registry during
``register_all_commands()``.

Module label: CLI-CMDS-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from murphy_cli.registry import CommandRegistry


def register_all_commands(registry: CommandRegistry) -> None:
    """Wire every command module into the registry.  (CLI-CMDS-REG-001)"""
    # Import each module and call its register() function.
    from murphy_cli.commands import auth
    from murphy_cli.commands import chat
    from murphy_cli.commands import config_cmd
    from murphy_cli.commands import forge
    from murphy_cli.commands import agents
    from murphy_cli.commands import automations
    from murphy_cli.commands import hitl
    from murphy_cli.commands import safety
    from murphy_cli.commands import system

    auth.register(registry)
    chat.register(registry)
    config_cmd.register(registry)
    forge.register(registry)
    agents.register(registry)
    automations.register(registry)
    hitl.register(registry)
    safety.register(registry)
    system.register(registry)
