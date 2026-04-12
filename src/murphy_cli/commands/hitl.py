"""
Murphy CLI — HITL (Human-in-the-Loop) commands
================================================

``murphy hitl queue``, ``murphy hitl approve``, ``murphy hitl reject``,
``murphy hitl inspect``.

Module label: CLI-CMD-HITL-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_success,
    print_table,
    render_response,
)


def _cmd_hitl_queue(parsed: Any, ctx: Any) -> int:
    """View the HITL approval queue.  (CLI-CMD-HITL-QUEUE-001)"""
    client = ctx["client"]
    resp = client.get("/api/hitl/queue")
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        items = resp.data if isinstance(resp.data, list) else (
            resp.data.get("items", []) if isinstance(resp.data, dict) else []
        )
        if not items:
            render_response({"message": "HITL queue is empty"}, output_format="text")
            return 0
        headers = ["ID", "Type", "Status", "Created"]
        rows = [
            [
                str(item.get("id", item.get("hitl_id", "—"))),
                str(item.get("type", item.get("action_type", "—"))),
                str(item.get("status", "—")),
                str(item.get("created_at", item.get("created", "—"))),
            ]
            for item in items
        ]
        print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Cannot fetch HITL queue", code=resp.error_code)
    return 1


def _cmd_hitl_inspect(parsed: Any, ctx: Any) -> int:
    """Inspect a HITL item.  (CLI-CMD-HITL-INSPECT-001)"""
    client = ctx["client"]
    hitl_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not hitl_id:
        print_error("Specify HITL ID: murphy hitl inspect --id <id>")
        return 1
    resp = client.get(f"/api/hitl/{hitl_id}")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title=f"HITL Item {hitl_id}")
        return 0
    print_error(resp.error_message or "HITL item not found", code=resp.error_code)
    return 1


def _cmd_hitl_approve(parsed: Any, ctx: Any) -> int:
    """Approve a HITL item.  (CLI-CMD-HITL-APPROVE-001)"""
    client = ctx["client"]
    hitl_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not hitl_id:
        print_error("Specify HITL ID: murphy hitl approve --id <id>")
        return 1
    reason = parsed.flags.get("reason", "")
    body: dict[str, Any] = {}
    if reason:
        body["reason"] = reason
    resp = client.post(f"/api/hitl/{hitl_id}/approve", json_body=body)
    if resp.success:
        print_success(f"HITL item {hitl_id} approved.")
        return 0
    print_error(resp.error_message or "Approval failed", code=resp.error_code)
    return 1


def _cmd_hitl_reject(parsed: Any, ctx: Any) -> int:
    """Reject a HITL item.  (CLI-CMD-HITL-REJECT-001)"""
    client = ctx["client"]
    hitl_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not hitl_id:
        print_error("Specify HITL ID: murphy hitl reject --id <id>")
        return 1
    reason = parsed.flags.get("reason", "")
    body: dict[str, Any] = {}
    if reason:
        body["reason"] = reason
    resp = client.post(f"/api/hitl/{hitl_id}/reject", json_body=body)
    if resp.success:
        print_success(f"HITL item {hitl_id} rejected.")
        return 0
    print_error(resp.error_message or "Rejection failed", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register HITL commands.  (CLI-CMD-HITL-REG-001)"""
    registry.register_resource("hitl", "Human-in-the-loop approval workflows")

    registry.register(CommandDef(
        resource="hitl",
        name="queue",
        handler=_cmd_hitl_queue,
        description="View approval queue",
        usage="murphy hitl queue",
        aliases=["list", "ls"],
    ))
    registry.register(CommandDef(
        resource="hitl",
        name="inspect",
        handler=_cmd_hitl_inspect,
        description="Inspect a HITL item",
        usage="murphy hitl inspect --id <id>",
        flags={"--id": "HITL item ID"},
    ))
    registry.register(CommandDef(
        resource="hitl",
        name="approve",
        handler=_cmd_hitl_approve,
        description="Approve a pending action",
        usage="murphy hitl approve --id <id> --reason 'Looks good'",
        flags={"--id": "HITL item ID", "--reason": "Approval reason"},
    ))
    registry.register(CommandDef(
        resource="hitl",
        name="reject",
        handler=_cmd_hitl_reject,
        description="Reject a pending action",
        usage="murphy hitl reject --id <id> --reason 'Needs revision'",
        flags={"--id": "HITL item ID", "--reason": "Rejection reason"},
    ))
