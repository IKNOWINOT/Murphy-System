"""
Murphy CLI — MultiCursorBrowser commands
=========================================

``murphy mcb launch``, ``murphy mcb zones``, ``murphy mcb navigate``,
``murphy mcb screenshot``, ``murphy mcb run``, ``murphy mcb record``,
``murphy mcb replay``, ``murphy mcb close``.

Exposes Murphy's native MultiCursorBrowser split-screen automation engine
from the terminal — no Playwright required.  This is the industry
differentiator: multi-cursor parallel browser/desktop automation controlled
entirely from a CLI.

Module label: CLI-CMD-MCB-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import sys
from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    bold,
    cyan,
    green,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    render_response,
)


# ---------------------------------------------------------------------------
# Handlers  (CLI-CMD-MCB-HANDLERS-001)
# ---------------------------------------------------------------------------


def _cmd_mcb_launch(parsed: Any, ctx: Any) -> int:
    """Launch a MultiCursorBrowser session.  (CLI-CMD-MCB-LAUNCH-001)

    Creates a new MCB session with the specified layout and returns
    the session ID + zone list.
    """
    client = ctx["client"]
    layout = parsed.flags.get("layout", "single")
    headless = "headless" in parsed.flags or parsed.flags.get("headless") is True
    agent_id = parsed.flags.get("agent_id") or parsed.flags.get("agent-id", "cli_default")

    body: dict[str, Any] = {
        "layout": layout,
        "headless": headless,
        "agent_id": agent_id,
    }

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/launch → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/launch", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            session_id = data.get("session_id", "—")
            zones = data.get("zones", [])
            print_success(f"MCB session launched: {session_id}")
            print_info(f"Layout: {layout}  |  Headless: {headless}  |  Zones: {len(zones)}")
            if zones:
                headers = ["Zone ID", "Name", "Width", "Height", "Label"]
                rows = [
                    [
                        str(z.get("zone_id", "—")),
                        str(z.get("name", "—")),
                        str(z.get("width", "—")),
                        str(z.get("height", "—")),
                        str(z.get("label", "—")),
                    ]
                    for z in zones
                ]
                print_table(headers, rows)
        return 0
    print_error(resp.error_message or "MCB launch failed", code=resp.error_code)
    return 1


def _cmd_mcb_zones(parsed: Any, ctx: Any) -> int:
    """List active MCB zones.  (CLI-CMD-MCB-ZONES-001)"""
    client = ctx["client"]
    session_id = parsed.flags.get("session") or parsed.flags.get("session_id") or parsed.flags.get("session-id", "")

    endpoint = "/api/mcb/zones"
    if session_id:
        endpoint = f"/api/mcb/zones?session_id={session_id}"

    resp = client.get(endpoint)
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        zones = resp.data if isinstance(resp.data, list) else (
            resp.data.get("zones", []) if isinstance(resp.data, dict) else []
        )
        if not zones:
            print_info("No active MCB zones.")
            return 0
        headers = ["Zone ID", "Name", "Position", "Size", "Cursor", "Label"]
        rows = [
            [
                str(z.get("zone_id", "—")),
                str(z.get("name", "—")),
                f"{z.get('x', 0)},{z.get('y', 0)}",
                f"{z.get('width', 0)}×{z.get('height', 0)}",
                str(z.get("cursor_id", "—")),
                str(z.get("label", "—")),
            ]
            for z in zones
        ]
        print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Cannot list MCB zones", code=resp.error_code)
    return 1


def _cmd_mcb_navigate(parsed: Any, ctx: Any) -> int:
    """Navigate an MCB zone to a URL.  (CLI-CMD-MCB-NAV-001)"""
    client = ctx["client"]
    zone_id = parsed.flags.get("zone") or (parsed.positional[0] if parsed.positional else None)
    url = parsed.flags.get("url") or (parsed.positional[1] if len(parsed.positional) > 1 else None)

    if not zone_id or not url:
        print_error("Usage: murphy mcb navigate --zone <zone_id> --url <url>")
        return 1

    body: dict[str, Any] = {"zone_id": zone_id, "url": url}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/navigate → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/navigate", json_body=body)
    if resp.success:
        print_success(f"Zone {zone_id} navigated to {url}")
        return 0
    print_error(resp.error_message or "Navigation failed", code=resp.error_code)
    return 1


def _cmd_mcb_screenshot(parsed: Any, ctx: Any) -> int:
    """Take a screenshot of one or all MCB zones.  (CLI-CMD-MCB-SCREEN-001)"""
    client = ctx["client"]
    zone_id = parsed.flags.get("zone", "all")
    out_path = parsed.flags.get("out", "./mcb_screenshot.png")

    body: dict[str, Any] = {"zone_id": zone_id, "out": out_path}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/screenshot → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/screenshot", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        saved_to = data.get("path", out_path)
        print_success(f"Screenshot saved: {saved_to}")
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        return 0
    print_error(resp.error_message or "Screenshot failed", code=resp.error_code)
    return 1


def _cmd_mcb_run(parsed: Any, ctx: Any) -> int:
    """Execute a NativeTask via the MCB runner.  (CLI-CMD-MCB-RUN-001)

    Accepts either a JSON task file (--task) or inline step notation (--steps).
    """
    client = ctx["client"]
    task_file = parsed.flags.get("task")
    steps_inline = parsed.flags.get("steps")
    zone_id = parsed.flags.get("zone", "")

    if not task_file and not steps_inline:
        print_error(
            "Provide --task <file.json> or --steps 'navigate:url,click:#btn'\n"
            "  Usage: murphy mcb run --task task.json [--zone <zone_id>]"
        )
        return 1

    body: dict[str, Any] = {}
    if task_file:
        body["task_file"] = task_file
    if steps_inline:
        body["steps_inline"] = steps_inline
    if zone_id:
        body["zone_id"] = zone_id

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/run → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/run", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            status = data.get("status", "unknown")
            steps_run = data.get("steps_executed", 0)
            steps_total = data.get("steps_total", 0)
            print_success(f"Task {status}: {steps_run}/{steps_total} steps executed")
            results = data.get("results", [])
            if results:
                headers = ["Step", "Action", "Status", "Duration"]
                rows = [
                    [
                        str(r.get("step", i + 1)),
                        str(r.get("action", "—")),
                        str(r.get("status", "—")),
                        f"{r.get('duration_ms', 0)}ms",
                    ]
                    for i, r in enumerate(results)
                ]
                print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Task execution failed", code=resp.error_code)
    return 1


def _cmd_mcb_record(parsed: Any, ctx: Any) -> int:
    """Start recording actions in an MCB zone.  (CLI-CMD-MCB-RECORD-001)"""
    client = ctx["client"]
    zone_id = parsed.flags.get("zone", "0")
    out_path = parsed.flags.get("out", "./recorded_task.json")

    body: dict[str, Any] = {"zone_id": zone_id, "output_path": out_path}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/record → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/record", json_body=body)
    if resp.success:
        print_success(f"Recording started on zone {zone_id} → {out_path}")
        return 0
    print_error(resp.error_message or "Recording failed to start", code=resp.error_code)
    return 1


def _cmd_mcb_replay(parsed: Any, ctx: Any) -> int:
    """Replay a previously recorded task.  (CLI-CMD-MCB-REPLAY-001)"""
    client = ctx["client"]
    task_file = parsed.flags.get("task") or (
        parsed.positional[0] if parsed.positional else None
    )
    zone_id = parsed.flags.get("zone", "")

    if not task_file:
        print_error("Provide a task file: murphy mcb replay --task recorded.json")
        return 1

    body: dict[str, Any] = {"task_file": task_file}
    if zone_id:
        body["zone_id"] = zone_id

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/replay → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/replay", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        status = data.get("status", "completed")
        print_success(f"Replay {status}")
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        return 0
    print_error(resp.error_message or "Replay failed", code=resp.error_code)
    return 1


def _cmd_mcb_close(parsed: Any, ctx: Any) -> int:
    """Close an MCB session.  (CLI-CMD-MCB-CLOSE-001)"""
    client = ctx["client"]
    session_id = parsed.flags.get("session") or parsed.flags.get("session_id") or parsed.flags.get("session-id", "")

    body: dict[str, Any] = {}
    if session_id:
        body["session_id"] = session_id

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/mcb/close → {json.dumps(body)}")
        return 0

    resp = client.post("/api/mcb/close", json_body=body)
    if resp.success:
        print_success("MCB session closed.")
        return 0
    print_error(resp.error_message or "Failed to close MCB session", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Registration  (CLI-CMD-MCB-REG-001)
# ---------------------------------------------------------------------------


def register(registry: CommandRegistry) -> None:
    """Register MultiCursorBrowser commands.  (CLI-CMD-MCB-REG-001)"""
    registry.register_resource("mcb", "MultiCursor browser automation (no Playwright)")

    registry.register(CommandDef(
        resource="mcb",
        name="launch",
        handler=_cmd_mcb_launch,
        description="Launch an MCB session with split-screen zones",
        usage="murphy mcb launch --layout quad [--headless] [--agent-id cli_default]",
        flags={
            "--layout": "Zone layout: single, dual_h, dual_v, triple_h, quad, hexa",
            "--headless": "Run headless (no visible browser)",
            "--agent-id": "Agent identity for this MCB controller",
        },
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="zones",
        handler=_cmd_mcb_zones,
        description="List active MCB zones and their cursors",
        usage="murphy mcb zones [--session <session_id>]",
        flags={"--session": "Filter by MCB session ID"},
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="navigate",
        handler=_cmd_mcb_navigate,
        description="Navigate an MCB zone to a URL",
        usage="murphy mcb navigate --zone <zone_id> --url <url>",
        flags={"--zone": "Target zone ID", "--url": "Destination URL"},
        aliases=["goto", "nav"],
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="screenshot",
        handler=_cmd_mcb_screenshot,
        description="Capture screenshot of one or all zones",
        usage="murphy mcb screenshot [--zone all] [--out ./screenshot.png]",
        flags={"--zone": "Zone ID or 'all'", "--out": "Output file path"},
        aliases=["snap"],
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="run",
        handler=_cmd_mcb_run,
        description="Execute a NativeTask via MCB runner",
        usage="murphy mcb run --task task.json [--zone <zone_id>]",
        flags={
            "--task": "Path to NativeTask JSON file",
            "--steps": "Inline steps: 'navigate:url,click:#btn'",
            "--zone": "Target zone ID",
        },
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="record",
        handler=_cmd_mcb_record,
        description="Record actions in an MCB zone to a task file",
        usage="murphy mcb record --zone 0 --out recorded.json",
        flags={"--zone": "Zone to record", "--out": "Output task file"},
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="replay",
        handler=_cmd_mcb_replay,
        description="Replay a previously recorded task",
        usage="murphy mcb replay --task recorded.json [--zone <zone_id>]",
        flags={"--task": "Task file to replay", "--zone": "Target zone ID"},
    ))
    registry.register(CommandDef(
        resource="mcb",
        name="close",
        handler=_cmd_mcb_close,
        description="Close an MCB session and release resources",
        usage="murphy mcb close [--session <session_id>]",
        flags={"--session": "Session ID to close"},
    ))
