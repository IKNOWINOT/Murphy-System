"""
Murphy CLI — Split-screen orchestration commands
==================================================

``murphy split run``, ``murphy split status``, ``murphy split coordinate``.

Provides terminal access to Murphy's split-screen multi-cursor desktop
system.  Each zone runs its own independent cursor and task queue in
parallel — true console split-screen automation from the CLI.

Module label: CLI-CMD-SPLIT-001

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
    print_success,
    print_table,
    print_warning,
    render_response,
)


# ---------------------------------------------------------------------------
# Handlers  (CLI-CMD-SPLIT-HANDLERS-001)
# ---------------------------------------------------------------------------


def _cmd_split_run(parsed: Any, ctx: Any) -> int:
    """Run tasks across split-screen zones.  (CLI-CMD-SPLIT-RUN-001)

    Accepts a layout + per-zone task descriptions.  Each zone executes its
    task concurrently using an independent cursor.  Like console
    split-screen where each player has their own input stream.
    """
    client = ctx["client"]
    layout = parsed.flags.get("layout", "dual_h")

    # Collect zone task assignments from flags: --left, --right, --top, --bottom
    # or --zone-0, --zone-1, etc.
    zone_tasks: dict[str, str] = {}
    for key, val in parsed.flags.items():
        if key in ("left", "right", "top", "bottom"):
            zone_tasks[key] = val
        elif key.startswith("zone-") and isinstance(val, str):
            zone_tasks[key] = val

    # Also accept a config file
    config_file = parsed.flags.get("config")

    if not zone_tasks and not config_file:
        print_error(
            "Provide zone tasks or a config file:\n"
            "  murphy split run --layout dual_h --left 'api test' --right 'form test'\n"
            "  murphy split run --config multi-zone.json"
        )
        return 1

    body: dict[str, Any] = {"layout": layout}
    if zone_tasks:
        body["zone_tasks"] = zone_tasks
    if config_file:
        body["config_file"] = config_file

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/split/run → {json.dumps(body)}")
        return 0

    resp = client.post("/api/split/run", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            session_id = data.get("session_id", "—")
            zone_count = data.get("zone_count", 0)
            print_success(f"Split-screen session {session_id}: {zone_count} zones running")
            results = data.get("results", {})
            if results:
                headers = ["Zone", "Status", "Tasks", "Duration"]
                rows = [
                    [
                        str(zone),
                        str(info.get("status", "—")) if isinstance(info, dict) else "—",
                        str(info.get("tasks_run", "—")) if isinstance(info, dict) else "—",
                        f"{info.get('duration_ms', 0)}ms" if isinstance(info, dict) else "—",
                    ]
                    for zone, info in results.items()
                ]
                print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Split-screen run failed", code=resp.error_code)
    return 1


def _cmd_split_status(parsed: Any, ctx: Any) -> int:
    """Show status of all split-screen zones.  (CLI-CMD-SPLIT-STATUS-001)"""
    client = ctx["client"]
    session_id = parsed.flags.get("session") or parsed.flags.get("session_id") or parsed.flags.get("session-id", "")

    endpoint = "/api/split/status"
    if session_id:
        endpoint = f"/api/split/status?session_id={session_id}"

    resp = client.get(endpoint)
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        data = resp.data if isinstance(resp.data, dict) else {}
        state = data.get("state", "unknown")
        layout = data.get("layout", "—")
        zones = data.get("zones", [])
        print_info(f"Session state: {state}  |  Layout: {layout}")
        if zones:
            headers = ["Zone ID", "State", "Cursor", "Tasks Queued", "Tasks Done"]
            rows = [
                [
                    str(z.get("zone_id", "—")),
                    str(z.get("state", "—")),
                    str(z.get("cursor_id", "—")),
                    str(z.get("tasks_queued", 0)),
                    str(z.get("tasks_completed", 0)),
                ]
                for z in zones
            ]
            print_table(headers, rows)
        else:
            print_info("No active zones.")
        return 0
    print_error(resp.error_message or "Cannot fetch split status", code=resp.error_code)
    return 1


def _cmd_split_coordinate(parsed: Any, ctx: Any) -> int:
    """Run the SplitScreenCoordinator pipeline.  (CLI-CMD-SPLIT-COORD-001)

    Full pipeline: TRIAGE → EVIDENCE → SORT → DISPATCH → REPORT.
    Uses RubixEvidenceAdapter + TicketTriageEngine for intelligent
    zone prioritization before parallel execution.
    """
    client = ctx["client"]
    config_file = parsed.flags.get("config") or (
        parsed.positional[0] if parsed.positional else None
    )

    if not config_file:
        print_error(
            "Provide a coordination config:\n"
            "  murphy split coordinate --config multi-zone.json"
        )
        return 1

    body: dict[str, Any] = {"config_file": config_file}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/split/coordinate → {json.dumps(body)}")
        return 0

    resp = client.post("/api/split/coordinate", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            print_success("Coordination complete.")
            # Triage results
            triage = data.get("triage", {})
            if triage:
                print_info("Triage scores:")
                headers = ["Zone", "Severity", "Confidence"]
                rows = [
                    [str(z), str(t.get("severity", "—")), str(t.get("confidence", "—"))]
                    for z, t in triage.items()
                ]
                print_table(headers, rows)
            # Evidence results
            evidence = data.get("evidence", {})
            if evidence:
                print_info("Evidence verdicts:")
                headers = ["Zone", "Verdict", "Detail"]
                rows = [
                    [str(z), str(e.get("verdict", "—")), str(e.get("detail", "—"))]
                    for z, e in evidence.items()
                ]
                print_table(headers, rows)
            # Summary
            summary = data.get("summary", "")
            if summary:
                print_info(f"Summary: {summary}")
        return 0
    print_error(resp.error_message or "Coordination failed", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Registration  (CLI-CMD-SPLIT-REG-001)
# ---------------------------------------------------------------------------


def register(registry: CommandRegistry) -> None:
    """Register split-screen commands.  (CLI-CMD-SPLIT-REG-001)"""
    registry.register_resource("split", "Split-screen multi-cursor orchestration")

    registry.register(CommandDef(
        resource="split",
        name="run",
        handler=_cmd_split_run,
        description="Run tasks across split-screen zones in parallel",
        usage="murphy split run --layout dual_h --left 'task A' --right 'task B'",
        flags={
            "--layout": "Layout: single, dual_h, dual_v, triple_h, quad, hexa",
            "--left": "Task for left zone (dual_h/dual_v)",
            "--right": "Task for right zone (dual_h)",
            "--top": "Task for top zone (dual_v)",
            "--bottom": "Task for bottom zone (dual_v)",
            "--config": "Path to multi-zone configuration JSON",
        },
    ))
    registry.register(CommandDef(
        resource="split",
        name="status",
        handler=_cmd_split_status,
        description="Show status of all split-screen zones",
        usage="murphy split status [--session <session_id>]",
        flags={"--session": "Filter by session ID"},
    ))
    registry.register(CommandDef(
        resource="split",
        name="coordinate",
        handler=_cmd_split_coordinate,
        description="Run full coordination pipeline (triage → evidence → dispatch)",
        usage="murphy split coordinate --config multi-zone.json",
        flags={"--config": "Coordination config file"},
        aliases=["coord"],
    ))
