"""
Murphy CLI — Agent commands
============================

``murphy agents list``, ``murphy agents inspect``, ``murphy agents dashboard``.

Module label: CLI-CMD-AGENTS-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_table,
    render_response,
)


def _cmd_agents_list(parsed: Any, ctx: Any) -> int:
    """List active agents.  (CLI-CMD-AGENTS-LIST-001)"""
    client = ctx["client"]
    resp = client.get("/api/agents")
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        # Table display
        agents = resp.data if isinstance(resp.data, list) else []
        if not agents:
            render_response({"message": "No active agents"}, output_format="text")
            return 0
        headers = ["ID", "Name", "Role", "Status"]
        rows = [
            [
                str(a.get("id", a.get("agent_id", "—"))),
                str(a.get("name", "—")),
                str(a.get("role", "—")),
                str(a.get("status", "—")),
            ]
            for a in agents
        ]
        print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Cannot list agents", code=resp.error_code)
    return 1


def _cmd_agents_inspect(parsed: Any, ctx: Any) -> int:
    """Inspect a specific agent.  (CLI-CMD-AGENTS-INSPECT-001)"""
    client = ctx["client"]
    agent_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not agent_id:
        print_error("Specify agent ID: murphy agents inspect --id <id>")
        return 1
    resp = client.get(f"/api/agents/{agent_id}")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title=f"Agent {agent_id}")
        return 0
    print_error(resp.error_message or "Agent not found", code=resp.error_code)
    return 1


def _cmd_agents_dashboard(parsed: Any, ctx: Any) -> int:
    """Agent dashboard snapshot.  (CLI-CMD-AGENTS-DASH-001)"""
    client = ctx["client"]
    resp = client.get("/api/agent-dashboard/snapshot")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Agent Dashboard")
        return 0
    print_error(resp.error_message or "Dashboard unavailable", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register agent commands.  (CLI-CMD-AGENTS-REG-001)"""
    registry.register_resource("agents", "Agent management & monitoring")

    registry.register(CommandDef(
        resource="agents",
        name="list",
        handler=_cmd_agents_list,
        description="List active agents",
        usage="murphy agents list",
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="agents",
        name="inspect",
        handler=_cmd_agents_inspect,
        description="Inspect a specific agent",
        usage="murphy agents inspect --id <agent_id>",
        flags={"--id": "Agent ID"},
    ))
    registry.register(CommandDef(
        resource="agents",
        name="dashboard",
        handler=_cmd_agents_dashboard,
        description="Agent dashboard snapshot",
        usage="murphy agents dashboard",
    ))
