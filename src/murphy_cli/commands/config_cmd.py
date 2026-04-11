"""
Murphy CLI — Config commands
============================

``murphy config get``, ``murphy config set``, ``murphy config list``,
``murphy config reset``.

Module label: CLI-CMD-CONFIG-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_json,
    print_kv,
    print_success,
    render_response,
)


def _cmd_config_get(parsed: Any, ctx: Any) -> int:
    """Get a config value.  (CLI-CMD-CONFIG-GET-001)"""
    config = ctx["config"]
    key = parsed.flags.get("key") or (parsed.positional[0] if parsed.positional else None)
    if not key:
        print_error("Specify a key: murphy config get --key <name>")
        return 1

    value = config.get(key)
    if value is None:
        print_error(f"Key '{key}' not set.")
        return 1

    if parsed.output_format == "json":
        print_json({key: value})
    else:
        print_kv({key: value})
    return 0


def _cmd_config_set(parsed: Any, ctx: Any) -> int:
    """Set a config value.  (CLI-CMD-CONFIG-SET-001)"""
    config = ctx["config"]
    key = parsed.flags.get("key") or (parsed.positional[0] if len(parsed.positional) > 0 else None)
    value = parsed.flags.get("value") or (parsed.positional[1] if len(parsed.positional) > 1 else None)
    if not key or value is None:
        print_error("Usage: murphy config set --key <name> --value <val>")
        return 1

    config.set(key, value)
    print_success(f"Set {key} = {value}")
    return 0


def _cmd_config_list(parsed: Any, ctx: Any) -> int:
    """List all config values.  (CLI-CMD-CONFIG-LIST-001)"""
    config = ctx["config"]
    data = config.all()
    # Mask api_key for display
    if "api_key" in data:
        key = str(data["api_key"])
        data["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    render_response(data, output_format=parsed.output_format, title="CLI Configuration")
    return 0


def _cmd_config_reset(parsed: Any, ctx: Any) -> int:
    """Reset config to defaults.  (CLI-CMD-CONFIG-RESET-001)"""
    config = ctx["config"]
    from murphy_cli.config import DEFAULTS
    for key in list(config.all().keys()):
        config.delete(key)
    for key, val in DEFAULTS.items():
        config.set(key, val)
    print_success("Configuration reset to defaults.")
    return 0


def register(registry: CommandRegistry) -> None:
    """Register config commands.  (CLI-CMD-CONFIG-REG-001)"""
    registry.register_resource("config", "CLI configuration management")

    registry.register(CommandDef(
        resource="config",
        name="get",
        handler=_cmd_config_get,
        description="Get a config value",
        usage="murphy config get --key api_url",
        flags={"--key": "Config key name"},
    ))
    registry.register(CommandDef(
        resource="config",
        name="set",
        handler=_cmd_config_set,
        description="Set a config value",
        usage="murphy config set --key api_url --value https://murphy.systems",
        flags={"--key": "Config key name", "--value": "Value to set"},
    ))
    registry.register(CommandDef(
        resource="config",
        name="list",
        handler=_cmd_config_list,
        description="List all config values",
        usage="murphy config list",
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="config",
        name="reset",
        handler=_cmd_config_reset,
        description="Reset to defaults",
        usage="murphy config reset",
    ))
