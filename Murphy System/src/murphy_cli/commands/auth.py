"""
Murphy CLI — Auth commands
==========================

``murphy auth login``, ``murphy auth logout``, ``murphy auth status``,
``murphy auth me``.

Module label: CLI-CMD-AUTH-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_info,
    print_kv,
    print_success,
    render_response,
)


def _cmd_login(parsed: Any, ctx: Any) -> int:
    """Authenticate with murphy.systems.  (CLI-CMD-AUTH-LOGIN-001)"""
    client = ctx["client"]
    config = ctx["config"]

    api_key = parsed.flags.get("api_key") or parsed.api_key

    if api_key:
        # API-key based auth — validate by calling /api/auth/me
        client.api_key = api_key
        resp = client.get("/api/auth/me")
        if resp.success:
            config.set("api_key", api_key)
            print_success(f"Authenticated successfully. Key stored in {config._path}")
            return 0
        else:
            # In development mode, the key might still be valid
            # Store it and inform the user
            config.set("api_key", api_key)
            print_success(f"API key stored in {config._path}")
            print_info("Could not verify key against server (server may be offline or in dev mode).")
            return 0

    # Email/password login
    email = parsed.flags.get("email")
    password = parsed.flags.get("password")

    if email and password:
        resp = client.post("/api/auth/login", json_body={
            "email": email,
            "password": password,
        })
        if resp.success and isinstance(resp.data, dict):
            token = resp.data.get("session_token", "")
            if token:
                config.set("api_key", token)
                print_success("Login successful. Session token stored.")
                return 0
            else:
                print_success("Login successful.")
                return 0
        else:
            print_error(
                resp.error_message or "Login failed",
                code=resp.error_code,
            )
            return 1

    print_error("Provide --api-key <key> or --email/--password for authentication.")
    return 1


def _cmd_logout(parsed: Any, ctx: Any) -> int:
    """Clear stored credentials.  (CLI-CMD-AUTH-LOGOUT-001)"""
    config = ctx["config"]
    client = ctx["client"]

    # Try server-side logout
    client.post("/api/auth/logout")

    config.delete("api_key")
    print_success("Logged out. Credentials removed.")
    return 0


def _cmd_auth_status(parsed: Any, ctx: Any) -> int:
    """Show current auth status.  (CLI-CMD-AUTH-STATUS-001)"""
    config = ctx["config"]
    client = ctx["client"]

    key = config.api_key
    if not key:
        print_info("Not authenticated. Run: murphy auth login --api-key <key>")
        return 0

    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"

    resp = client.get("/api/auth/me")
    if resp.success and isinstance(resp.data, dict):
        render_response(
            {"api_key": masked, **resp.data},
            output_format=parsed.output_format,
            title="Authentication Status",
        )
    else:
        print_kv({"api_key": masked, "server": "unreachable or dev mode"})

    return 0


def _cmd_auth_me(parsed: Any, ctx: Any) -> int:
    """Show current user profile.  (CLI-CMD-AUTH-ME-001)"""
    client = ctx["client"]
    resp = client.get("/api/auth/me")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Current User")
        return 0
    print_error(resp.error_message or "Could not fetch profile", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register auth commands.  (CLI-CMD-AUTH-REG-001)"""
    registry.register_resource("auth", "Authentication & credentials")

    registry.register(CommandDef(
        resource="auth",
        name="login",
        handler=_cmd_login,
        description="Authenticate with API key or email/password",
        usage="murphy auth login --api-key <key>",
        flags={
            "--api-key": "API key",
            "--email": "Account email",
            "--password": "Account password",
        },
    ))
    registry.register(CommandDef(
        resource="auth",
        name="logout",
        handler=_cmd_logout,
        description="Clear stored credentials",
        usage="murphy auth logout",
    ))
    registry.register(CommandDef(
        resource="auth",
        name="status",
        handler=_cmd_auth_status,
        description="Show current auth status",
        usage="murphy auth status",
    ))
    registry.register(CommandDef(
        resource="auth",
        name="me",
        handler=_cmd_auth_me,
        description="Show current user profile",
        usage="murphy auth me",
    ))
