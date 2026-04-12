"""
Murphy CLI — Diagnostics commands
===================================

``murphy diagnose symptom``, ``murphy diagnose pipeline``, ``murphy diagnose drift``.

Self-diagnostics with symptom-based root cause analysis.  Maps symptoms
to validation chains and traces expected → actual results at every point
of operation.

Guiding principle: "If there are still problems, how do we restart the
process from the symptoms and work back through validation again?"

Module label: CLI-CMD-DIAGNOSE-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
from typing import Any

from murphy_cli.registry import CommandDef, CommandRegistry
from murphy_cli.output import (
    bold,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    red,
    render_response,
)


# ---------------------------------------------------------------------------
# Handlers  (CLI-CMD-DIAGNOSE-HANDLERS-001)
# ---------------------------------------------------------------------------


def _cmd_diagnose_symptom(parsed: Any, ctx: Any) -> int:
    """Diagnose a system issue from its symptom.  (CLI-CMD-DIAGNOSE-SYM-001)

    Takes a human-readable symptom description and traces it back through
    the validation chain to identify root causes, affected modules,
    and recommended remediation steps.
    """
    client = ctx["client"]
    symptom = parsed.flags.get("symptom") or (
        " ".join(parsed.positional) if parsed.positional else None
    )

    if not symptom:
        print_error(
            "Describe the symptom:\n"
            "  murphy diagnose symptom --symptom 'forge returns empty deliverable'\n"
            "  murphy diagnose symptom 'login fails with 500 error'"
        )
        return 1

    body: dict[str, Any] = {"symptom": symptom}

    if parsed.dry_run:
        print_info(f"DRY RUN: POST /api/diagnose/symptom → {json.dumps(body)}")
        return 0

    resp = client.post("/api/diagnose/symptom", json_body=body)
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            print_info(f"Symptom: {symptom}")

            # Root causes
            causes = data.get("root_causes", [])
            if causes:
                print_info("Root causes identified:")
                for i, cause in enumerate(causes, 1):
                    if isinstance(cause, dict):
                        print_info(
                            f"  {i}. [{cause.get('module', '?')}] "
                            f"{cause.get('description', '—')} "
                            f"(confidence: {cause.get('confidence', '—')})"
                        )
                    else:
                        print_info(f"  {i}. {cause}")

            # Affected modules
            modules = data.get("affected_modules", [])
            if modules:
                print_info(f"Affected modules: {', '.join(str(m) for m in modules)}")

            # Validation chain
            chain = data.get("validation_chain", [])
            if chain:
                print_info("Validation chain:")
                headers = ["Step", "Check", "Expected", "Actual", "Pass"]
                rows = [
                    [
                        str(i + 1),
                        str(c.get("check", "—")),
                        str(c.get("expected", "—")),
                        str(c.get("actual", "—")),
                        "✓" if c.get("passed") else "✗",
                    ]
                    for i, c in enumerate(chain)
                    if isinstance(c, dict)
                ]
                if rows:
                    print_table(headers, rows)

            # Remediation
            remediation = data.get("remediation", [])
            if remediation:
                print_info("Recommended actions:")
                for i, step in enumerate(remediation, 1):
                    print_info(f"  {i}. {step}")

        return 0
    print_error(resp.error_message or "Diagnosis failed", code=resp.error_code)
    return 1


def _cmd_diagnose_pipeline(parsed: Any, ctx: Any) -> int:
    """Show PipelineErrorTracker diagnostics for a forge run.  (CLI-CMD-DIAGNOSE-PIPE-001)"""
    client = ctx["client"]
    run_id = parsed.flags.get("run_id") or parsed.flags.get("run-id") or (
        parsed.positional[0] if parsed.positional else None
    )

    if not run_id:
        print_error("Provide a run ID: murphy diagnose pipeline --run-id <id>")
        return 1

    resp = client.get(f"/api/diagnose/pipeline/{run_id}")
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            print_info(f"Pipeline diagnostics for run {run_id}:")

            errors = data.get("errors", [])
            if errors:
                headers = ["Code", "Stage", "Message", "Fallback Used"]
                rows = [
                    [
                        str(e.get("code", "—")),
                        str(e.get("stage", "—")),
                        str(e.get("message", "—")),
                        str(e.get("fallback", "—")),
                    ]
                    for e in errors
                    if isinstance(e, dict)
                ]
                if rows:
                    print_table(headers, rows)
            else:
                print_success("No errors recorded for this run.")

            summary = data.get("summary", "")
            if summary:
                print_info(f"Summary: {summary}")
        return 0
    print_error(resp.error_message or "Pipeline diagnostics unavailable", code=resp.error_code)
    return 1


def _cmd_diagnose_drift(parsed: Any, ctx: Any) -> int:
    """Check for tree-divergence and source-drift issues.  (CLI-CMD-DIAGNOSE-DRIFT-001)

    Runs the same checks as CI: tree-divergence-check and source-drift-guard.
    """
    client = ctx["client"]

    if parsed.dry_run:
        print_info("DRY RUN: GET /api/diagnose/drift")
        return 0

    resp = client.get("/api/diagnose/drift")
    if resp.success:
        data = resp.data if isinstance(resp.data, dict) else {}
        if parsed.output_format == "json":
            render_response(data, output_format="json")
        else:
            tree_ok = data.get("tree_divergence_ok", False)
            source_ok = data.get("source_drift_ok", False)

            if tree_ok:
                print_success("Tree divergence check: PASS")
            else:
                print_warning("Tree divergence check: FAIL")
                diffs = data.get("tree_divergence_files", [])
                for f in diffs:
                    print_error(f"  Missing/diverged: {f}")

            if source_ok:
                print_success("Source drift guard: PASS")
            else:
                print_warning("Source drift guard: FAIL")
                drifted = data.get("source_drift_files", [])
                for f in drifted:
                    print_error(f"  Drifted: {f}")

            if tree_ok and source_ok:
                print_success("All drift checks passed.")
                return 0
            else:
                print_warning("Drift detected — copy Murphy System/ → root to fix.")
                return 1
    print_error(resp.error_message or "Drift check failed", code=resp.error_code)
    return 1


# ---------------------------------------------------------------------------
# Registration  (CLI-CMD-DIAGNOSE-REG-001)
# ---------------------------------------------------------------------------


def register(registry: CommandRegistry) -> None:
    """Register diagnostics commands.  (CLI-CMD-DIAGNOSE-REG-001)"""
    registry.register_resource("diagnose", "Self-diagnostics & root cause analysis")

    registry.register(CommandDef(
        resource="diagnose",
        name="symptom",
        handler=_cmd_diagnose_symptom,
        description="Trace a symptom back to root cause",
        usage="murphy diagnose symptom --symptom 'forge returns empty deliverable'",
        flags={"--symptom": "Human-readable symptom description"},
        aliases=["sym"],
    ))
    registry.register(CommandDef(
        resource="diagnose",
        name="pipeline",
        handler=_cmd_diagnose_pipeline,
        description="Show PipelineErrorTracker diagnostics for a forge run",
        usage="murphy diagnose pipeline --run-id <run_id>",
        flags={"--run-id": "Forge pipeline run ID"},
        aliases=["pipe"],
    ))
    registry.register(CommandDef(
        resource="diagnose",
        name="drift",
        handler=_cmd_diagnose_drift,
        description="Check for tree-divergence and source-drift issues",
        usage="murphy diagnose drift",
    ))
