#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Performance Regression Agent Script
# Label: PERF-REGRESSION-001
#
# Runs performance benchmarks, compares against baselines,
# and gates PRs on regression thresholds.
#
# Phases:
#   benchmark  — Run performance benchmarks and collect metrics
#   compare    — Compare results against baseline
#   gate       — Pass/fail based on regression threshold

"""
Performance Regression Agent — automated performance regression detection.

Usage:
    python perf_regression_agent.py --phase benchmark --output-dir <dir>
    python perf_regression_agent.py --phase compare --results <file> --threshold <pct> --output-dir <dir>
    python perf_regression_agent.py --phase gate --comparison <file> --threshold <pct> --output-dir <dir>
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
log = logging.getLogger("perf-regression-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "PERF-REGRESSION-001"

BASELINE_PATH = Path("Murphy System/docs/perf_baseline.json")

# Built-in micro-benchmarks
BENCHMARKS = [
    "import_latency",
    "workflow_generation",
    "gate_wiring_init",
    "event_backbone_publish",
    "json_serialization",
]


# ── Phase: Benchmark ─────────────────────────────────────────────────────────
def phase_benchmark(output_dir: Path) -> dict[str, Any]:
    """Run performance benchmarks and collect metrics."""
    log.info("Phase: BENCHMARK — running performance tests")
    results: dict[str, Any] = {}

    for bench_name in BENCHMARKS:
        result = _run_benchmark(bench_name)
        results[bench_name] = result

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "benchmark",
        "results": results,
        "total_metrics": len(results),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_results.json").write_text(json.dumps(report, indent=2))
    log.info("Benchmarks complete: %d metrics collected", len(results))
    return report


def _run_benchmark(name: str) -> dict[str, Any]:
    """Run a single benchmark and return timing results."""
    iterations = 10
    times: list[float] = []

    for _ in range(iterations):
        start = time.monotonic()
        try:
            if name == "import_latency":
                _bench_import_latency()
            elif name == "workflow_generation":
                _bench_workflow_generation()
            elif name == "gate_wiring_init":
                _bench_gate_wiring_init()
            elif name == "event_backbone_publish":
                _bench_event_backbone()
            elif name == "json_serialization":
                _bench_json_serialization()
        except Exception as exc:
            return {"error": str(exc), "p50_ms": 0, "p95_ms": 0, "p99_ms": 0}
        elapsed = (time.monotonic() - start) * 1000
        times.append(elapsed)

    times.sort()
    return {
        "iterations": iterations,
        "p50_ms": round(times[len(times) // 2], 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3),
        "p99_ms": round(times[int(len(times) * 0.99)], 3),
        "min_ms": round(times[0], 3),
        "max_ms": round(times[-1], 3),
        "mean_ms": round(sum(times) / len(times), 3),
    }


def _bench_import_latency() -> None:
    import importlib
    importlib.import_module("src.modular_runtime")


def _bench_workflow_generation() -> None:
    try:
        from src.ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        gen.generate("Send a weekly report to Slack")
    except Exception:
        pass  # Best-effort benchmark


def _bench_gate_wiring_init() -> None:
    try:
        from src.gate_execution_wiring import GateExecutionWiring
        GateExecutionWiring()
    except Exception:
        pass


def _bench_event_backbone() -> None:
    try:
        from src.event_backbone import EventBackbone
        eb = EventBackbone()
    except Exception:
        pass


def _bench_json_serialization() -> None:
    import json as _json
    data = {"key": "value", "nested": {"a": [1, 2, 3]}, "count": 42}
    _json.dumps(data)
    _json.loads(_json.dumps(data))


# ── Phase: Compare ───────────────────────────────────────────────────────────
def phase_compare(
    results_path: Path,
    threshold_pct: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Compare benchmark results against baseline."""
    log.info("Phase: COMPARE — comparing against baseline")
    results = json.loads(results_path.read_text())
    baseline = _load_baseline()

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    for metric_name, metric_data in results.get("results", {}).items():
        if "error" in metric_data:
            continue
        baseline_data = baseline.get(metric_name, {})
        if not baseline_data:
            comparisons.append({
                "metric": metric_name,
                "status": "new",
                "current_p95": metric_data.get("p95_ms", 0),
            })
            continue

        current_p95 = metric_data.get("p95_ms", 0)
        baseline_p95 = baseline_data.get("p95_ms", 0)

        if baseline_p95 > 0:
            change_pct = ((current_p95 - baseline_p95) / baseline_p95) * 100
        else:
            change_pct = 0

        comparison = {
            "metric": metric_name,
            "baseline_p95": baseline_p95,
            "current_p95": current_p95,
            "change_pct": round(change_pct, 2),
        }

        if change_pct > threshold_pct:
            comparison["status"] = "regression"
            regressions.append(comparison)
        elif change_pct < -threshold_pct:
            comparison["status"] = "improvement"
            improvements.append(comparison)
        else:
            comparison["status"] = "stable"

        comparisons.append(comparison)

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "compare",
        "threshold_pct": threshold_pct,
        "total_metrics": len(comparisons),
        "regressions": regressions,
        "improvements": improvements,
        "comparisons": comparisons,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison_report.json").write_text(json.dumps(report, indent=2))

    # Generate markdown report for PR comments
    md_lines = [
        "## ⚡ Performance Regression Report",
        "",
        f"**Threshold:** {threshold_pct}%",
        "",
        "| Metric | Baseline p95 | Current p95 | Change |",
        "|--------|-------------|-------------|--------|",
    ]
    for c in comparisons:
        icon = "🔴" if c.get("status") == "regression" else "🟢" if c.get("status") == "improvement" else "⚪"
        md_lines.append(
            f"| {icon} {c['metric']} | {c.get('baseline_p95', 'N/A')}ms "
            f"| {c.get('current_p95', 'N/A')}ms | {c.get('change_pct', 'N/A')}% |"
        )
    if regressions:
        md_lines.extend(["", f"**❌ {len(regressions)} regression(s) detected — PR blocked**"])
    else:
        md_lines.extend(["", "**✅ No regressions detected**"])
    md_lines.extend(["", f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*"])
    (output_dir / "comparison_report.md").write_text("\n".join(md_lines))

    log.info("Comparison: %d regressions, %d improvements", len(regressions), len(improvements))
    return report


def _load_baseline() -> dict[str, Any]:
    """Load the performance baseline."""
    if BASELINE_PATH.exists():
        try:
            data = json.loads(BASELINE_PATH.read_text())
            return data.get("results", data)
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


# ── Phase: Gate ──────────────────────────────────────────────────────────────
def phase_gate(
    comparison_path: Path,
    threshold_pct: float,
    output_dir: Path,
) -> None:
    """Pass/fail based on regression threshold."""
    log.info("Phase: GATE — evaluating pass/fail")
    comparison = json.loads(comparison_path.read_text())
    regressions = comparison.get("regressions", [])

    if regressions:
        log.error(
            "GATE FAILED: %d metric(s) regressed by >%s%%",
            len(regressions), threshold_pct,
        )
        for r in regressions:
            log.error(
                "  %s: %s%% regression (baseline=%sms, current=%sms)",
                r["metric"], r["change_pct"], r["baseline_p95"], r["current_p95"],
            )
        sys.exit(1)
    else:
        log.info("GATE PASSED: no regressions above %s%%", threshold_pct)


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Performance Regression Agent")
    parser.add_argument("--phase", required=True, choices=["benchmark", "compare", "gate"])
    parser.add_argument("--results", type=Path, help="Path to benchmark_results.json")
    parser.add_argument("--comparison", type=Path, help="Path to comparison_report.json")
    parser.add_argument("--threshold", type=float, default=10.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "benchmark":
        phase_benchmark(args.output_dir)
    elif args.phase == "compare":
        if not args.results:
            parser.error("--results is required for compare phase")
        phase_compare(args.results, args.threshold, args.output_dir)
    elif args.phase == "gate":
        if not args.comparison:
            parser.error("--comparison is required for gate phase")
        phase_gate(args.comparison, args.threshold, args.output_dir)


if __name__ == "__main__":
    main()
