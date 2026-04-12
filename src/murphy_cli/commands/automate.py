"""
Murphy CLI — Native automation commands
=========================================

``murphy automate api``, ``murphy automate desktop``, ``murphy automate batch``.

Murphy's native automation stack (MurphyNativeRunner) replaces Playwright
for all browser, API, and desktop automation.  This module exposes that
stack from the terminal.

Module label: CLI-CMD-AUTOMATE-001

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
    render_response,
)


# ---------------------------------------------------------------------------
# Handlers  (CLI-CMD-AUTOMATE-HANDLERS-001)
# ---------------------------------------------------------------------------


def _cmd_automate_api(parsed: Any, ctx: Any) -> int:
    """Execute an API automation task.  (CLI-CMD-AUTOMATE-API-001)

    Uses MurphyAPIClient (urllib-based) — no Playwright needed.
    """
    client = ctx["client"]
    method = parsed.flags.get("method", "GET").upper()
    url = parsed.flags.get("url") or (parsed.positional[0] if parsed.positional else None)
    body_str = parsed.flags.get("body", "")
    headers_str = parsed.flags.get("headers", "")

    if not url:
        print_error("Provide a URL: murphy automate api --method GET --url /api/health")
        return 1

    body: dict[str, Any] = {
        "method": method,
        "url": url,
    }
    if body_str:
        body["body"] = body_str
    if headers_str:
        body["headers"] = headers_str

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/automate/api → {json.dumps(body)}")
        return 0

    resp = client.post("/api/automate/api", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            status = data.get("status_code", "—")
            duration = data.get("duration_ms", 0)
            print_success(f"{method} {url} → {status} ({duration}ms)")
            response_body = data.get("response_body")
            if response_body:
                print_info(f"Response: {response_body}")
        return 0
    print_error(resp.error_message or "API automation failed", code=resp.error_code)
    return 1


def _cmd_automate_desktop(parsed: Any, ctx: Any) -> int:
    """Execute a desktop automation action.  (CLI-CMD-AUTOMATE-DESKTOP-001)

    Uses GhostDesktopRunner (PyAutoGUI/OCR) — no Playwright needed.
    """
    client = ctx["client"]
    action = parsed.flags.get("action") or (parsed.positional[0] if parsed.positional else None)
    target = parsed.flags.get("target", "")

    if not action:
        print_error(
            "Provide an action:\n"
            "  murphy automate desktop --action click --target 'Submit Button'\n"
            "  murphy automate desktop --action type --target '#email' --value 'test@test.com'"
        )
        return 1

    body: dict[str, Any] = {"action": action}
    if target:
        body["target"] = target
    value = parsed.flags.get("value", "")
    if value:
        body["value"] = value

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/automate/desktop → {json.dumps(body)}")
        return 0

    resp = client.post("/api/automate/desktop", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            status = data.get("status", "completed")
            print_success(f"Desktop action '{action}' on '{target}': {status}")
        return 0
    print_error(resp.error_message or "Desktop automation failed", code=resp.error_code)
    return 1


def _cmd_automate_batch(parsed: Any, ctx: Any) -> int:
    """Execute a batch of automation tasks from a file.  (CLI-CMD-AUTOMATE-BATCH-001)"""
    client = ctx["client"]
    tasks_file = parsed.flags.get("tasks") or (
        parsed.positional[0] if parsed.positional else None
    )

    if not tasks_file:
        print_error("Provide a task file: murphy automate batch --tasks tasks.json")
        return 1

    body: dict[str, Any] = {"tasks_file": tasks_file}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/automate/batch → {json.dumps(body)}")
        return 0

    resp = client.post("/api/automate/batch", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            total = data.get("total", 0)
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            print_success(f"Batch complete: {passed}/{total} passed, {failed} failed")
            results = data.get("results", [])
            if results:
                headers = ["#", "Task", "Status", "Duration"]
                rows = [
                    [
                        str(i + 1),
                        str(r.get("description", r.get("task_id", "—"))),
                        str(r.get("status", "—")),
                        f"{r.get('duration_ms', 0)}ms",
                    ]
                    for i, r in enumerate(results)
                ]
                print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Batch automation failed", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Registration  (CLI-CMD-AUTOMATE-REG-001)
# ---------------------------------------------------------------------------


def register(registry: CommandRegistry) -> None:
    """Register native automation commands.  (CLI-CMD-AUTOMATE-REG-001)"""
    registry.register_resource("automate", "Native automation (no Playwright)")

    registry.register(CommandDef(
        resource="automate",
        name="api",
        handler=_cmd_automate_api,
        description="Execute an API call via native runner",
        usage="murphy automate api --method GET --url /api/health",
        flags={
            "--method": "HTTP method: GET, POST, PUT, DELETE",
            "--url": "Target URL or path",
            "--body": "Request body (JSON string)",
            "--headers": "Custom headers (JSON string)",
        },
    ))
    registry.register(CommandDef(
        resource="automate",
        name="desktop",
        handler=_cmd_automate_desktop,
        description="Execute a desktop automation action (GhostDesktop)",
        usage="murphy automate desktop --action click --target 'Submit'",
        flags={
            "--action": "Action: click, type, hotkey, focus, ocr",
            "--target": "Target element or window",
            "--value": "Value for type/fill actions",
        },
    ))
    registry.register(CommandDef(
        resource="automate",
        name="batch",
        handler=_cmd_automate_batch,
        description="Run a batch of tasks from a JSON file",
        usage="murphy automate batch --tasks tasks.json",
        flags={"--tasks": "Path to tasks JSON file"},
    ))
