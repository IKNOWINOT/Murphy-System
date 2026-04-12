"""
Murphy CLI — Module commissioning commands
============================================

``murphy commission run``, ``murphy commission checklist``,
``murphy commission verify``.

Production commissioning from the terminal.  Validates that every module
does what it was designed to do, that the test profile reflects the full
range of capabilities, and that hardening has been applied.

Guiding principle: "Has the module been commissioned again after those steps?"

Module label: CLI-CMD-COMMISSION-001

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
# Handlers  (CLI-CMD-COMMISSION-HANDLERS-001)
# ---------------------------------------------------------------------------


def _cmd_commission_run(parsed: Any, ctx: Any) -> int:
    """Run the commissioning sequence for a module.  (CLI-CMD-COMMISSION-RUN-001)

    Executes the full validation pipeline:
      1. Module purpose verification (does it do what it was designed to do?)
      2. Condition enumeration (what conditions are possible?)
      3. Test profile check (does it reflect full capabilities?)
      4. Expected vs. actual result comparison
      5. Hardening verification (error codes, retry, guards)
      6. Documentation parity check
    """
    client = ctx["client"]
    module_name = parsed.flags.get("module") or (
        parsed.positional[0] if parsed.positional else None
    )

    if not module_name:
        print_error(
            "Specify a module to commission:\n"
            "  murphy commission run --module forge\n"
            "  murphy commission run --module llm"
        )
        return 1

    body: dict[str, Any] = {"module": module_name}
    strict = parsed.flags.get("strict")
    if strict:
        body["strict"] = True

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/commission/run → {json.dumps(body)}")
        return 0

    resp = client.post("/api/commission/run", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            status = data.get("status", "unknown")
            module = data.get("module", module_name)

            if status == "pass":
                print_success(f"Module '{module}' commissioned: PASS")
            elif status == "warn":
                print_warning(f"Module '{module}' commissioned with warnings")
            else:
                print_error(f"Module '{module}' commissioning: FAIL")

            checks = data.get("checks", [])
            if checks:
                headers = ["Check", "Status", "Detail"]
                rows = [
                    [
                        str(c.get("name", "—")),
                        "✓" if c.get("passed") else "✗",
                        str(c.get("detail", "—")),
                    ]
                    for c in checks
                    if isinstance(c, dict)
                ]
                if rows:
                    print_table(headers, rows)

            warnings = data.get("warnings", [])
            for w in warnings:
                print_warning(f"  ⚠ {w}")

            return 0 if status in ("pass", "warn") else 1
    print_error(resp.error_message or "Commission run failed", code=resp.error_code)
    return 1


def _cmd_commission_checklist(parsed: Any, ctx: Any) -> int:
    """Print the commissioning checklist for a module.  (CLI-CMD-COMMISSION-CHECKLIST-001)"""
    client = ctx["client"]
    module_name = parsed.flags.get("module") or (
        parsed.positional[0] if parsed.positional else None
    )

    if not module_name:
        print_error("Specify a module: murphy commission checklist --module forge")
        return 1

    resp = client.get(f"/api/commission/checklist/{module_name}")
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            module = data.get("module", module_name)
            print_info(f"Commissioning checklist for '{module}':")
            items = data.get("items", [])
            if items:
                for i, item in enumerate(items, 1):
                    if isinstance(item, dict):
                        done = item.get("done", False)
                        mark = "☑" if done else "☐"
                        print_info(f"  {mark} {item.get('description', '—')}")
                    else:
                        print_info(f"  ☐ {item}")
            else:
                print_info("  No checklist items defined.")
        return 0
    print_error(resp.error_message or "Cannot fetch checklist", code=resp.error_code)
    return 1


def _cmd_commission_verify(parsed: Any, ctx: Any) -> int:
    """Bulk commissioning verification.  (CLI-CMD-COMMISSION-VERIFY-001)

    Checks commissioning status of all modules (--all) or a specific module.
    """
    client = ctx["client"]
    verify_all = "all" in parsed.flags or parsed.flags.get("all") is True
    module_name = parsed.flags.get("module", "")

    endpoint = "/api/commission/verify"
    params: dict[str, str] = {}
    if verify_all:
        params["scope"] = "all"
    elif module_name:
        params["module"] = module_name
    else:
        print_error(
            "Specify --all or --module <name>:\n"
            "  murphy commission verify --all\n"
            "  murphy commission verify --module forge"
        )
        return 1

    if parsed.dry_run:
        print_info(f"DRY RUN: GET {endpoint} params={params}")
        return 0

    resp = client.get(endpoint, params=params)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            modules = data.get("modules", [])
            if modules:
                headers = ["Module", "Status", "Last Commissioned", "Issues"]
                rows = [
                    [
                        str(m.get("name", "—")),
                        "✓" if m.get("status") == "pass" else "✗",
                        str(m.get("last_commissioned", "—")),
                        str(m.get("issue_count", 0)),
                    ]
                    for m in modules
                    if isinstance(m, dict)
                ]
                if rows:
                    print_table(headers, rows)
                # Summary
                total = len(modules)
                passed = sum(1 for m in modules if isinstance(m, dict) and m.get("status") == "pass")
                print_info(f"Commissioned: {passed}/{total} modules")
                return 0 if passed == total else 1
            else:
                print_info("No modules found.")
        return 0
    print_error(resp.error_message or "Verification failed", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Registration  (CLI-CMD-COMMISSION-REG-001)
# ---------------------------------------------------------------------------


def register(registry: CommandRegistry) -> None:
    """Register commissioning commands.  (CLI-CMD-COMMISSION-REG-001)"""
    registry.register_resource("commission", "Module commissioning & validation")

    registry.register(CommandDef(
        resource="commission",
        name="run",
        handler=_cmd_commission_run,
        description="Run commissioning sequence for a module",
        usage="murphy commission run --module forge [--strict]",
        flags={"--module": "Module name", "--strict": "Fail on any warning"},
    ))
    registry.register(CommandDef(
        resource="commission",
        name="checklist",
        handler=_cmd_commission_checklist,
        description="Print commissioning checklist for a module",
        usage="murphy commission checklist --module forge",
        flags={"--module": "Module name"},
        aliases=["list", "ls"],
    ))
    registry.register(CommandDef(
        resource="commission",
        name="verify",
        handler=_cmd_commission_verify,
        description="Verify commissioning status (all or specific module)",
        usage="murphy commission verify --all",
        flags={"--all": "Check all modules", "--module": "Specific module name"},
        aliases=["check"],
    ))
