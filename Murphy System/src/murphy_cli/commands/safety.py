"""
Murphy CLI — Safety & emergency commands
=========================================

``murphy safety status``, ``murphy emergency stop``, ``murphy emergency status``.

Module label: CLI-CMD-SAFETY-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_success,
    print_warning,
    red,
    render_response,
)


def _cmd_safety_status(parsed: Any, ctx: Any) -> int:
    """Show safety monitoring status.  (CLI-CMD-SAFETY-STATUS-001)"""
    client = ctx["client"]
    resp = client.get("/api/safety/status")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Safety Status")
        return 0
    print_error(resp.error_message or "Cannot fetch safety status", code=resp.error_code)
    return 1


def _cmd_emergency_stop(parsed: Any, ctx: Any) -> int:
    """Trigger emergency stop of all automations.  (CLI-CMD-SAFETY-ESTOP-001)

    This is a destructive action — requires ``--confirm`` flag.
    """
    client = ctx["client"]
    if not parsed.flags.get("confirm") and not parsed.non_interactive:
        print_warning(
            "Emergency stop will halt ALL running automations.\n"
            "  Add --confirm to proceed, or use --non-interactive."
        )
        return 1

    resp = client.post("/api/emergency/stop")
    if resp.success:
        print_success(red("EMERGENCY STOP activated. All automations halted."))
        return 0
    print_error(resp.error_message or "Emergency stop failed", code=resp.error_code)
    return 1


def _cmd_emergency_status(parsed: Any, ctx: Any) -> int:
    """Show emergency stop status.  (CLI-CMD-SAFETY-ESTATUS-001)"""
    client = ctx["client"]
    resp = client.get("/api/emergency/status")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Emergency Status")
        return 0
    print_error(resp.error_message or "Cannot fetch emergency status", code=resp.error_code)
    return 1


def _cmd_gates_list(parsed: Any, ctx: Any) -> int:
    """List governance gates.  (CLI-CMD-SAFETY-GATES-001)"""
    client = ctx["client"]
    resp = client.get("/api/gates")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Governance Gates")
        return 0
    print_error(resp.error_message or "Cannot list gates", code=resp.error_code)
    return 1


def _cmd_gates_arm(parsed: Any, ctx: Any) -> int:
    """Arm (enable) a governance gate.  (CLI-CMD-SAFETY-GATEARM-001)"""
    client = ctx["client"]
    gate_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not gate_id:
        print_error("Specify gate ID: murphy gates arm --id <gate_id>")
        return 1
    resp = client.post(f"/api/gates/{gate_id}/arm")
    if resp.success:
        print_success(f"Gate {gate_id} armed.")
        return 0
    print_error(resp.error_message or "Failed to arm gate", code=resp.error_code)
    return 1


def _cmd_gates_disarm(parsed: Any, ctx: Any) -> int:
    """Disarm (disable) a governance gate.  (CLI-CMD-SAFETY-GATEDISARM-001)"""
    client = ctx["client"]
    gate_id = parsed.flags.get("id") or (parsed.positional[0] if parsed.positional else None)
    if not gate_id:
        print_error("Specify gate ID: murphy gates disarm --id <gate_id>")
        return 1
    resp = client.post(f"/api/gates/{gate_id}/disarm")
    if resp.success:
        print_success(f"Gate {gate_id} disarmed.")
        return 0
    print_error(resp.error_message or "Failed to disarm gate", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register safety commands.  (CLI-CMD-SAFETY-REG-001)"""
    registry.register_resource("safety", "Safety monitoring")
    registry.register_resource("emergency", "Emergency controls")
    registry.register_resource("gates", "Governance gate management")

    registry.register(CommandDef(
        resource="safety",
        name="status",
        handler=_cmd_safety_status,
        description="Show safety monitoring status",
        usage="murphy safety status",
    ))

    registry.register(CommandDef(
        resource="emergency",
        name="stop",
        handler=_cmd_emergency_stop,
        description="Emergency halt all automations",
        usage="murphy emergency stop --confirm",
        flags={"--confirm": "Confirm destructive action"},
    ))
    registry.register(CommandDef(
        resource="emergency",
        name="status",
        handler=_cmd_emergency_status,
        description="Show emergency stop status",
        usage="murphy emergency status",
    ))

    registry.register(CommandDef(
        resource="gates",
        name="list",
        handler=_cmd_gates_list,
        description="List governance gates",
        usage="murphy gates list",
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="gates",
        name="arm",
        handler=_cmd_gates_arm,
        description="Arm (enable) a gate",
        usage="murphy gates arm --id <gate_id>",
        flags={"--id": "Gate ID"},
    ))
    registry.register(CommandDef(
        resource="gates",
        name="disarm",
        handler=_cmd_gates_disarm,
        description="Disarm (disable) a gate",
        usage="murphy gates disarm --id <gate_id>",
        flags={"--id": "Gate ID"},
    ))
