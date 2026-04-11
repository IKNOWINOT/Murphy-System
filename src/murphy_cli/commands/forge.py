"""
Murphy CLI — Forge commands
============================

``murphy forge generate``, ``murphy forge status``, ``murphy forge export``,
``murphy forge formats``.

The forge is Murphy's AI-powered deliverable generation engine.

Module label: CLI-CMD-FORGE-001

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
    print_warning,
    render_response,
)


def _cmd_forge_generate(parsed: Any, ctx: Any) -> int:
    """Generate a deliverable via the forge.  (CLI-CMD-FORGE-GEN-001)

    Streams progress events (agent assignments, build metrics) and outputs
    the final deliverable content.
    """
    client = ctx["client"]
    query = parsed.flags.get("query") or (
        " ".join(parsed.positional) if parsed.positional else None
    )
    if not query:
        print_error("Provide a query: murphy forge generate --query 'Build an onboarding app'")
        return 1

    business_type = parsed.flags.get("business_type", "")
    model = parsed.flags.get("model", "")

    body: dict[str, Any] = {"query": query}
    if business_type:
        body["business_type"] = business_type
    if model:
        body["model"] = model

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/demo/forge-stream → {json.dumps(body)}")
        return 0

    # Stream the forge build
    if parsed.output_format == "text":
        agent_count = 0
        build_time = 0.0
        deliverable_content = ""
        has_streamed = False

        try:
            for frame in client.stream_sse(
                "/api/demo/forge-stream",
                method="POST",
                json_body=body,
                timeout=max(parsed.timeout, 120),
            ):
                event = frame.get("event", "")
                data_str = frame.get("data", "")

                if event == "agent":
                    try:
                        agent_data = json.loads(data_str)
                        name = agent_data.get("name", "Agent")
                        role = agent_data.get("role", "")
                        status = agent_data.get("status", "")
                        sys.stderr.write(f"  {green('▸')} {name} ({role}) — {status}\n")
                        sys.stderr.flush()
                        agent_count += 1
                    except json.JSONDecodeError:
                        pass
                    has_streamed = True

                elif event == "progress":
                    try:
                        prog = json.loads(data_str)
                        pct = prog.get("percent", "")
                        msg = prog.get("message", "")
                        sys.stderr.write(f"  {cyan('⟳')} {pct}% — {msg}\n")
                        sys.stderr.flush()
                    except json.JSONDecodeError:
                        pass
                    has_streamed = True

                elif event == "metrics":
                    try:
                        metrics = json.loads(data_str)
                        build_time = metrics.get("build_time_seconds", 0)
                        human_hours = metrics.get("predicted_human_hours", 0)
                        roi = metrics.get("roi_multiplier", 0)
                        sys.stderr.write(
                            f"\n  {bold('Build complete')} in {build_time:.1f}s"
                            f" — est. {human_hours:.1f}h human equivalent"
                            f" — ROI: {roi:.0f}x\n"
                        )
                        sys.stderr.flush()
                    except json.JSONDecodeError:
                        pass

                elif event == "content":
                    deliverable_content += data_str
                    has_streamed = True

                elif event == "done":
                    try:
                        done_data = json.loads(data_str)
                        if isinstance(done_data, dict):
                            deliverable_content = done_data.get(
                                "deliverable", deliverable_content
                            )
                    except json.JSONDecodeError:
                        if data_str and not deliverable_content:
                            deliverable_content = data_str
                    break

                elif event == "error":
                    print_error(data_str, code="CLI-CMD-FORGE-ERR-002")
                    return 1

        except Exception as exc:  # CLI-CMD-FORGE-ERR-001
            if not has_streamed:
                # Fallback to non-streaming
                return _forge_generate_sync(client, body, parsed)
            print_error(f"Stream interrupted: {exc}", code="CLI-CMD-FORGE-ERR-001")
            return 1

        if deliverable_content:
            sys.stdout.write(f"\n{deliverable_content}\n")
            sys.stdout.flush()
            return 0
        elif has_streamed:
            print_warning("Forge completed but no deliverable content received.")
            return 0
        else:
            return _forge_generate_sync(client, body, parsed)

    # JSON output — use sync endpoint
    return _forge_generate_sync(client, body, parsed)


def _forge_generate_sync(client: Any, body: dict, parsed: Any) -> int:
    """Synchronous forge fallback.  (CLI-CMD-FORGE-SYNC-001)"""
    resp = client.post("/api/demo/deliverable", json_body=body, timeout=120)
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Forge Deliverable")
        return 0
    print_error(resp.error_message or "Forge generation failed", code=resp.error_code)
    return 1


def _cmd_forge_formats(parsed: Any, ctx: Any) -> int:
    """List available export formats.  (CLI-CMD-FORGE-FORMATS-001)"""
    client = ctx["client"]
    resp = client.get("/api/demo/deliverable/formats")
    if resp.success:
        render_response(resp.data, output_format=parsed.output_format, title="Export Formats")
        return 0
    print_error(resp.error_message or "Cannot fetch formats", code=resp.error_code)
    return 1


def _cmd_forge_export(parsed: Any, ctx: Any) -> int:
    """Export a deliverable in a specific format.  (CLI-CMD-FORGE-EXPORT-001)"""
    client = ctx["client"]
    fmt = parsed.flags.get("format", "md")
    content = parsed.flags.get("content", "")
    out_file = parsed.flags.get("out")

    if not content and not sys.stdin.isatty():
        content = sys.stdin.read()

    if not content:
        print_error("Provide content via --content or pipe via stdin.")
        return 1

    resp = client.post("/api/demo/deliverable/export", json_body={
        "content": content,
        "format": fmt,
    })

    if resp.success and isinstance(resp.data, dict):
        exported = resp.data.get("content", resp.data.get("data", ""))
        if out_file:
            with open(out_file, "w", encoding="utf-8") as fh:
                fh.write(str(exported))
            print_success(f"Exported to {out_file}")
        else:
            sys.stdout.write(str(exported) + "\n")
        return 0

    print_error(resp.error_message or "Export failed", code=resp.error_code)
    return 1


def register(registry: CommandRegistry) -> None:
    """Register forge commands.  (CLI-CMD-FORGE-REG-001)"""
    registry.register_resource("forge", "AI deliverable generation")

    registry.register(CommandDef(
        resource="forge",
        name="generate",
        handler=_cmd_forge_generate,
        description="Generate an AI deliverable",
        usage="murphy forge generate --query 'Build an onboarding app'",
        flags={
            "--query": "Generation query / description",
            "--business-type": "Business type context",
            "--model": "Model override",
        },
        aliases=["gen", "build"],
    ))
    registry.register(CommandDef(
        resource="forge",
        name="formats",
        handler=_cmd_forge_formats,
        description="List export formats",
        usage="murphy forge formats",
    ))
    registry.register(CommandDef(
        resource="forge",
        name="export",
        handler=_cmd_forge_export,
        description="Export deliverable to a format",
        usage="murphy forge export --format pdf --out deliverable.pdf",
        flags={
            "--format": "Export format (txt, pdf, html, docx, md)",
            "--content": "Content to export",
            "--out": "Output file path",
        },
    ))
