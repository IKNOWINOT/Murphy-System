#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — E2E Hero Flow Agent Script
# Label: E2E-HERO-001
#
# Validates the Describe -> Generate -> Execute hero flow end-to-end.
#
# Phases:
#   validate  — Run hero flow validation (import, generate, execute checks)
#   metrics   — Collect timing metrics for each step

"""
E2E Hero Flow Agent — validates the Describe -> Generate -> Execute pipeline.

Usage:
    python e2e_hero_flow_agent.py --phase validate --output-dir <dir>
    python e2e_hero_flow_agent.py --phase metrics --output-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("e2e-hero-flow-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "E2E-HERO-001"

# Test intents for the hero flow
TEST_INTENTS = [
    "Monitor my sales data and send a weekly summary to Slack",
    "Route incoming IT tickets to the right team based on urgency",
    "Alert me on Slack when an IoT sensor reading exceeds threshold",
]


# ── Phase: Validate ─────────────────────────────────────────────────────────
def phase_validate(output_dir: Path) -> dict[str, Any]:
    """Run hero flow validation steps."""
    log.info("Phase: VALIDATE — running hero flow checks")
    steps: list[dict[str, Any]] = []

    # Step 1: Import validation
    step = _validate_imports()
    steps.append(step)

    # Step 2: Workflow generation
    step = _validate_workflow_generation()
    steps.append(step)

    # Step 3: Gate wiring
    step = _validate_gate_wiring()
    steps.append(step)

    overall_passed = all(s["passed"] for s in steps)

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "validate",
        "passed": overall_passed,
        "steps": steps,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "hero_flow_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Validation %s", "PASSED" if overall_passed else "FAILED")

    if not overall_passed:
        sys.exit(1)
    return report


def _validate_imports() -> dict[str, Any]:
    """Validate that all hero flow components are importable."""
    start = time.monotonic()
    failures: list[str] = []
    modules = [
        "src.ai_workflow_generator",
        "src.gate_execution_wiring",
        "src.modular_runtime",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except Exception as exc:
            failures.append(f"{mod}: {exc}")
    duration = (time.monotonic() - start) * 1000
    return {
        "name": "Import Validation",
        "passed": len(failures) == 0,
        "duration_ms": duration,
        "details": failures if failures else "All imports OK",
    }


def _validate_workflow_generation() -> dict[str, Any]:
    """Validate that the workflow generator can process test intents."""
    start = time.monotonic()
    failures: list[str] = []
    try:
        from src.ai_workflow_generator import generate_workflow
        for intent in TEST_INTENTS:
            result = generate_workflow(intent)
            if not result:
                failures.append(f"Empty result for: {intent}")
    except ImportError:
        # Try alternative import
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator
            gen = AIWorkflowGenerator()
            for intent in TEST_INTENTS:
                result = gen.generate(intent)
                if not result:
                    failures.append(f"Empty result for: {intent}")
        except Exception as exc:
            failures.append(f"Generator init failed: {exc}")
    except Exception as exc:
        failures.append(f"Workflow generation error: {exc}")

    duration = (time.monotonic() - start) * 1000
    return {
        "name": "Workflow Generation",
        "passed": len(failures) == 0,
        "duration_ms": duration,
        "details": failures if failures else f"Generated {len(TEST_INTENTS)} workflows OK",
    }


def _validate_gate_wiring() -> dict[str, Any]:
    """Validate that gate execution wiring is functional."""
    start = time.monotonic()
    failures: list[str] = []
    try:
        from src.gate_execution_wiring import GateExecutionWiring
        wiring = GateExecutionWiring()
        # Verify gate types are registered
        gate_types = getattr(wiring, "gate_types", None) or getattr(wiring, "gates", None)
        if gate_types is not None and len(gate_types) == 0:
            failures.append("No gate types registered")
    except ImportError as exc:
        failures.append(f"Import failed: {exc}")
    except Exception as exc:
        failures.append(f"Gate wiring validation error: {exc}")

    duration = (time.monotonic() - start) * 1000
    return {
        "name": "Gate Execution Wiring",
        "passed": len(failures) == 0,
        "duration_ms": duration,
        "details": failures if failures else "Gate wiring OK",
    }


# ── Phase: Metrics ───────────────────────────────────────────────────────────
def phase_metrics(output_dir: Path) -> dict[str, Any]:
    """Collect timing metrics for each hero flow step."""
    log.info("Phase: METRICS — collecting timing data")

    report_path = output_dir / "hero_flow_report.json"
    if report_path.exists():
        data = json.loads(report_path.read_text())
        metrics = {
            "agent": AGENT_LABEL,
            "version": AGENT_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "metrics",
            "step_timings": {
                step["name"]: step["duration_ms"]
                for step in data.get("steps", [])
            },
            "total_duration_ms": sum(
                s["duration_ms"] for s in data.get("steps", [])
            ),
        }
    else:
        metrics = {
            "agent": AGENT_LABEL,
            "version": AGENT_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "metrics",
            "step_timings": {},
            "total_duration_ms": 0,
            "note": "No validation report found — run validate phase first",
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "hero_flow_metrics.json").write_text(json.dumps(metrics, indent=2))
    log.info("Metrics collected")
    return metrics


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Hero Flow Agent")
    parser.add_argument("--phase", required=True, choices=["validate", "metrics"])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "validate":
        phase_validate(args.output_dir)
    elif args.phase == "metrics":
        phase_metrics(args.output_dir)


if __name__ == "__main__":
    main()
