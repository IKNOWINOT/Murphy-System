"""
Murphy CLI — Chat commands
==========================

``murphy chat`` — send messages to the Murphy LLM and stream responses.

Module label: CLI-CMD-CHAT-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import sys
from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    print_error,
    print_info,
    print_json,
    print_stream_chunk,
    print_stream_done,
    render_response,
)


def _cmd_chat(parsed: Any, ctx: Any) -> int:
    """Send a chat message.  (CLI-CMD-CHAT-SEND-001)

    Supports ``--message`` flag or positional argument.  Streams response
    by default when output is ``text``.
    """
    client = ctx["client"]
    message = parsed.flags.get("message") or (
        " ".join(parsed.positional) if parsed.positional else None
    )

    if not message:
        # Read from stdin if piped
        if not sys.stdin.isatty():
            message = sys.stdin.read().strip()

    if not message:
        print_error("No message provided. Use --message or pipe via stdin.")
        return 1

    system_prompt = parsed.flags.get("system")
    model = parsed.flags.get("model")

    body: dict[str, Any] = {"message": message}
    if system_prompt:
        body["system_prompt"] = system_prompt
    if model:
        body["model"] = model

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/chat → {json.dumps(body)}")
        return 0

    # Try streaming first
    if parsed.output_format == "text" and not parsed.flags.get("no_stream"):
        streamed = False
        try:
            for frame in client.stream_sse(
                "/api/chat",
                method="POST",
                json_body=body,
                timeout=parsed.timeout,
            ):
                event = frame.get("event", "")
                data = frame.get("data", "")
                if event in ("token", "message", "delta"):
                    print_stream_chunk(data)
                    streamed = True
                elif event == "done":
                    break
                elif event == "error":
                    print_error(data, code="CLI-CMD-CHAT-ERR-002")
                    return 1
        except Exception:  # CLI-CMD-CHAT-ERR-001
            pass  # Fallback to non-streaming below

        if streamed:
            print_stream_done()
            return 0

    # Non-streaming fallback
    resp = client.post("/api/chat", json_body=body)
    if resp.success:
        if parsed.output_format == "json":
            print_json(resp.data)
        elif isinstance(resp.data, dict):
            content = resp.data.get("response") or resp.data.get("content") or resp.data.get("message", "")
            sys.stdout.write(f"{content}\n")
        else:
            sys.stdout.write(f"{resp.data}\n")
        return 0

    print_error(resp.error_message or "Chat request failed", code=resp.error_code)
    return 1


def _cmd_llm_status(parsed: Any, ctx: Any) -> int:
    """Show LLM provider status.  (CLI-CMD-CHAT-LLM-001)"""
    client = ctx["client"]
    resp = client.get("/api/llm/status")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="LLM Status")
        return 0
    print_error(resp.error_message or "Cannot fetch LLM status", code=resp.error_code)
    return 1


def _cmd_llm_providers(parsed: Any, ctx: Any) -> int:
    """List available LLM providers.  (CLI-CMD-CHAT-PROVIDERS-001)"""
    client = ctx["client"]
    resp = client.get("/api/llm/providers")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="LLM Providers")
        return 0
    print_error(resp.error_message or "Cannot fetch providers", code=resp.error_code)
    return 1


def _cmd_llm_configure(parsed: Any, ctx: Any) -> int:
    """Configure the active LLM provider.  (CLI-CMD-CHAT-CONFIGURE-001)"""
    client = ctx["client"]
    provider = parsed.flags.get("provider") or (parsed.positional[0] if parsed.positional else None)
    if not provider:
        print_error("Specify a provider: murphy llm configure --provider <name>")
        return 1
    resp = client.post("/api/llm/configure", json_body={"provider": provider})
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="LLM Configuration")
        return 0
    print_error(resp.error_message or "Configuration failed", code=resp.error_code)
    return 1


def _cmd_llm_test(parsed: Any, ctx: Any) -> int:
    """Test LLM provider connectivity.  (CLI-CMD-CHAT-TEST-001)"""
    client = ctx["client"]
    resp = client.post("/api/llm/test")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="LLM Test")
        return 0
    print_error(resp.error_message or "LLM test failed", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register chat/llm commands.  (CLI-CMD-CHAT-REG-001)"""
    registry.register_resource("chat", "Chat with Murphy AI")
    registry.register_resource("llm", "LLM provider management")

    registry.register(CommandDef(
        resource="chat",
        name="",
        handler=_cmd_chat,
        description="Send a message to Murphy AI",
        usage='murphy chat --message "Hello, Murphy"',
        flags={
            "--message": "Message text",
            "--system": "System prompt",
            "--model": "Model override",
            "--no-stream": "Disable streaming",
        },
    ))

    registry.register(CommandDef(
        resource="llm",
        name="status",
        handler=_cmd_llm_status,
        description="Show LLM provider status",
        usage="murphy llm status",
    ))
    registry.register(CommandDef(
        resource="llm",
        name="providers",
        handler=_cmd_llm_providers,
        description="List available LLM providers",
        usage="murphy llm providers",
    ))
    registry.register(CommandDef(
        resource="llm",
        name="configure",
        handler=_cmd_llm_configure,
        description="Set active LLM provider",
        usage="murphy llm configure --provider deepinfra",
        flags={"--provider": "Provider name"},
    ))
    registry.register(CommandDef(
        resource="llm",
        name="test",
        handler=_cmd_llm_test,
        description="Test LLM provider connectivity",
        usage="murphy llm test",
    ))
