"""
Murphy CLI — System commands
=============================

``murphy status``, ``murphy health``, ``murphy manifest``,
``murphy integrations``, ``murphy credentials``, ``murphy admin``.

Module label: CLI-CMD-SYS-001

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


# ---------------------------------------------------------------------------
# System / health  (CLI-CMD-SYS-HEALTH-001)
# ---------------------------------------------------------------------------

def _cmd_status(parsed: Any, ctx: Any) -> int:
    """Show full system status.  (CLI-CMD-SYS-STATUS-001)"""
    client = ctx["client"]
    resp = client.get("/api/status")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="System Status")
        return 0
    print_error(resp.error_message or "Cannot reach server", code=resp.error_code)
    return 1


def _cmd_health(parsed: Any, ctx: Any) -> int:
    """Health check (no auth required).  (CLI-CMD-SYS-HEALTH-001)"""
    client = ctx["client"]
    resp = client.get("/api/health")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Health Check")
        return 0
    print_error(resp.error_message or "Health check failed", code=resp.error_code)
    return 1


def _cmd_manifest(parsed: Any, ctx: Any) -> int:
    """Show API manifest.  (CLI-CMD-SYS-MANIFEST-001)"""
    client = ctx["client"]
    resp = client.get("/api/manifest")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="API Manifest")
        return 0
    print_error(resp.error_message or "Cannot fetch manifest", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Integrations  (CLI-CMD-SYS-INT-001)
# ---------------------------------------------------------------------------

def _cmd_integrations_list(parsed: Any, ctx: Any) -> int:
    """List available integrations.  (CLI-CMD-SYS-INTLIST-001)"""
    client = ctx["client"]
    resp = client.get("/api/integrations")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Integrations")
        return 0
    print_error(resp.error_message or "Cannot list integrations", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Credentials  (CLI-CMD-SYS-CRED-001)
# ---------------------------------------------------------------------------

def _cmd_credentials_list(parsed: Any, ctx: Any) -> int:
    """List stored credentials.  (CLI-CMD-SYS-CREDLIST-001)"""
    client = ctx["client"]
    resp = client.get("/api/credentials/list")
    if resp.success:
        if parsed.output_format == "json":
            render_response(resp.data, output_format="json")
            return 0
        items = resp.data if isinstance(resp.data, list) else []
        if not items:
            render_response({"message": "No credentials stored"}, output_format="text")
            return 0
        headers = ["Provider", "Status", "Last Used"]
        rows = [
            [
                str(c.get("provider", "—")),
                str(c.get("status", "—")),
                str(c.get("last_used", "—")),
            ]
            for c in items
        ]
        print_table(headers, rows)
        return 0
    print_error(resp.error_message or "Cannot list credentials", code=resp.error_code)
    return 1


def _cmd_credentials_store(parsed: Any, ctx: Any) -> int:
    """Store a credential.  (CLI-CMD-SYS-CREDSTORE-001)"""
    client = ctx["client"]
    provider = parsed.flags.get("provider")
    key = parsed.flags.get("key")
    if not provider or not key:
        print_error("Usage: murphy credentials store --provider <name> --key <value>")
        return 1
    resp = client.post("/api/credentials/store", json_body={
        "provider": provider,
        "api_key": key,
    })
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Credential Stored")
        return 0
    print_error(resp.error_message or "Failed to store credential", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Admin  (CLI-CMD-SYS-ADMIN-001)
# ---------------------------------------------------------------------------

def _cmd_admin_stats(parsed: Any, ctx: Any) -> int:
    """Platform statistics.  (CLI-CMD-SYS-ADMINSTATS-001)"""
    client = ctx["client"]
    resp = client.get("/api/admin/stats")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Platform Stats")
        return 0
    print_error(resp.error_message or "Cannot fetch stats", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register system commands.  (CLI-CMD-SYS-REG-001)"""
    registry.register_resource("status", "System status")
    registry.register_resource("health", "Health check")
    registry.register_resource("manifest", "API manifest")
    registry.register_resource("integrations", "Integration management")
    registry.register_resource("credentials", "Credential management")
    registry.register_resource("admin", "Administration")

    # Top-level system commands (no sub-command needed)
    registry.register(CommandDef(
        resource="status",
        name="",
        handler=_cmd_status,
        description="Show system status",
        usage="murphy status",
    ))
    registry.register(CommandDef(
        resource="health",
        name="",
        handler=_cmd_health,
        description="Health check (no auth)",
        usage="murphy health",
    ))
    registry.register(CommandDef(
        resource="manifest",
        name="",
        handler=_cmd_manifest,
        description="Show API manifest",
        usage="murphy manifest",
    ))

    # Integrations
    registry.register(CommandDef(
        resource="integrations",
        name="list",
        handler=_cmd_integrations_list,
        description="List integrations",
        usage="murphy integrations list",
        aliases=["ls"],
    ))

    # Credentials
    registry.register(CommandDef(
        resource="credentials",
        name="list",
        handler=_cmd_credentials_list,
        description="List stored credentials",
        usage="murphy credentials list",
        aliases=["ls"],
    ))
    registry.register(CommandDef(
        resource="credentials",
        name="store",
        handler=_cmd_credentials_store,
        description="Store a credential",
        usage="murphy credentials store --provider deepinfra --key <key>",
        flags={"--provider": "Provider name", "--key": "API key value"},
    ))

    # Admin
    registry.register(CommandDef(
        resource="admin",
        name="stats",
        handler=_cmd_admin_stats,
        description="Platform statistics",
        usage="murphy admin stats",
    ))
