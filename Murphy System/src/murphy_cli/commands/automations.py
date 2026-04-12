"""
Murphy CLI — Automation commands
=================================

``murphy automations list``, ``murphy execute``, ``murphy workflows``.

Module label: CLI-CMD-AUTO-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_info,
    print_table,
    render_response,
)


def _cmd_automations_list(parsed: Any, ctx: Any) -> int:
    """List automations.  (CLI-CMD-AUTO-LIST-001)"""
    client = ctx["client"]
    resp = client.get("/api/automations")
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        items = resp.data if isinstance(resp.data, list) else []
        if not items:
            render_response({"message": "No automations"}, output_format="text")
            return 0
        headers = ["ID", "Name", "Status", "Type"]
        rows = [
            [
                str(a.get("id", a.get("automation_id", "—"))),
                str(a.get("name", "—")),
                str(a.get("status", "—")),
                str(a.get("type", a.get("automation_type", "—"))),
            ]
            for a in items
        ]
        print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Cannot list automations", code=resp.error_code)
    return 1


def _cmd_automations_inspect(parsed: Any, ctx: Any) -> int:
    """Inspect a specific automation.  (CLI-CMD-AUTO-INSPECT-001)"""
    client = ctx["client"]
    auto_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not auto_id:
        print_error("Specify automation ID: murphy automations inspect --id <id>")
        return 1
    resp = client.get(f"/api/automations/{auto_id}")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title=f"Automation {auto_id}")
        return 0
    print_error(resp.error_message or "Automation not found", code=resp.error_code)
    return 1


def _cmd_execute(parsed: Any, ctx: Any) -> int:
    """Submit a task for execution.  (CLI-CMD-AUTO-EXEC-001)"""
    client = ctx["client"]
    task = parsed.flags.get("task") or (
        " ".join(parsed.positional) if parsed.positional else None
    )
    if not task:
        print_error("Provide a task: murphy execute --task 'Process invoices'")
        return 1

    body: dict[str, Any] = {"task": task}
    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/execute → {json.dumps(body)}")
        return 0

    resp = client.post("/api/execute", json_body=body)
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Execution Result")
        return 0
    print_error(resp.error_message or "Execution failed", code=resp.error_code)
    return 1


def _cmd_workflows_list(parsed: Any, ctx: Any) -> int:
    """List workflows.  (CLI-CMD-AUTO-WF-LIST-001)"""
    client = ctx["client"]
    resp = client.get("/api/workflows")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Workflows")
        return 0
    print_error(resp.error_message or "Cannot list workflows", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register automation commands.  (CLI-CMD-AUTO-REG-001)"""
    registry.register_resource("automations", "Automation management")
    registry.register_resource("execute", "Task execution")
    registry.register_resource("workflows", "Workflow management")

    registry.register(CommandDef(
        resource="automations",
        name="list",
        handler=_cmd_automations_list,
        description="List automations",
        usage="murphy automations list",
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="automations",
        name="inspect",
        handler=_cmd_automations_inspect,
        description="Inspect automation details",
        usage="murphy automations inspect --id <automation_id>",
        flags={"--id": "Automation ID"},
    ))

    registry.register(CommandDef(
        resource="execute",
        name="",
        handler=_cmd_execute,
        description="Submit a task for execution",
        usage="murphy execute --task 'Process invoices'",
        flags={"--task": "Task description"},
    ))

    registry.register(CommandDef(
        resource="workflows",
        name="list",
        handler=_cmd_workflows_list,
        description="List workflows",
        usage="murphy workflows list",
        aliases=["ls"],
    ))
