"""
External AI Agent Benchmark Test Suite.

Runs Murphy System against major public AI agent benchmarks:
  * SWE-bench  — software-engineering task resolution
  * GAIA       — multi-step tool-use assistant tasks
  * AgentBench — 8-environment agent evaluation
  * WebArena   — web automation goal completion
  * ToolBench  — tool/API selection and calling (BFCL)
  * τ-Bench    — multi-turn HITL workflow completion
  * Terminal-Bench — CLI/system automation

Gating
------
Tests are gated by the ``MURPHY_RUN_EXTERNAL_BENCHMARKS=1`` environment
variable.  When the variable is not set, all tests in this module are
skipped.  Individual adapters may perform additional skips when their
external data or dependencies are unavailable.

Usage
-----
Run all external benchmarks::

    MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/test_external_benchmarks.py -v

Run only one benchmark::

    MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest tests/benchmarks/test_external_benchmarks.py -k swe_bench -v

Save results JSON to a specific path::

    MURPHY_BENCHMARK_RESULTS_DIR=/tmp/results MURPHY_RUN_EXTERNAL_BENCHMARKS=1 pytest ...

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "murphy_system" / "src"))
sys.path.insert(0, str(ROOT / "murphy_system"))

# ---------------------------------------------------------------------------
# Env-var gate (same pattern as test_integration_speed.py)
# ---------------------------------------------------------------------------

_RUN_EXTERNAL = bool(os.environ.get("MURPHY_RUN_EXTERNAL_BENCHMARKS"))

pytestmark = [
    pytest.mark.benchmark_external,
    pytest.mark.skipif(
        not _RUN_EXTERNAL,
        reason=(
            "External benchmark tests are disabled. "
            "Set MURPHY_RUN_EXTERNAL_BENCHMARKS=1 to enable."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Adapter imports (guarded — only the package itself, not heavy deps)
# ---------------------------------------------------------------------------

try:
    from src.benchmark_adapters import (
        ADAPTER_REGISTRY,
        AgentBenchAdapter,
        GAIAAdapter,
        SWEBenchAdapter,
        TauBenchAdapter,
        TerminalBenchAdapter,
        ToolBenchAdapter,
        WebArenaAdapter,
    )

    _ADAPTERS_AVAILABLE = True
except ImportError as _import_err:
    _ADAPTERS_AVAILABLE = False
    _ADAPTER_IMPORT_ERROR = str(_import_err)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESULTS_DIR = Path(
    os.environ.get(
        "MURPHY_BENCHMARK_RESULTS_DIR",
        ROOT / "murphy_system" / "documentation" / "testing",
    )
)

_ALL_RESULTS: dict[str, Any] = {}


def _save_results(name: str, result: Any) -> None:
    """Persist a suite result to JSON and accumulate in ``_ALL_RESULTS``."""
    _ALL_RESULTS[name] = result.to_dict() if hasattr(result, "to_dict") else result
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"benchmark_{name.replace('-', '_')}_results.json"
    out_path.write_text(json.dumps(_ALL_RESULTS[name], indent=2), encoding="utf-8")


def _require_adapters() -> None:
    """Skip if adapters could not be imported."""
    if not _ADAPTERS_AVAILABLE:
        pytest.skip(f"benchmark_adapters package not importable: {_ADAPTER_IMPORT_ERROR}")  # type: ignore[name-defined]


# ---------------------------------------------------------------------------
# Adapter discovery test
# ---------------------------------------------------------------------------


def test_adapter_registry_populated() -> None:
    """All expected benchmark adapters must be discoverable via ADAPTER_REGISTRY."""
    _require_adapters()
    expected = {
        "swe-bench",
        "gaia",
        "agent-bench",
        "web-arena",
        "tool-bench",
        "tau-bench",
        "terminal-bench",
    }
    assert expected.issubset(set(ADAPTER_REGISTRY.keys())), (
        f"Missing adapters: {expected - set(ADAPTER_REGISTRY.keys())}"
    )


# ---------------------------------------------------------------------------
# SWE-bench
# ---------------------------------------------------------------------------


def test_swe_bench(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """SWE-bench Lite: Murphy's code-generation and bug-fixing capability.

    Test ID: EXT-BENCH-001
    """
    _require_adapters()
    adapter = SWEBenchAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("swe-bench", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "swe-bench"
    assert "tasks_total" in scores
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "swe_bench_results.json")


# ---------------------------------------------------------------------------
# GAIA
# ---------------------------------------------------------------------------


def test_gaia(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """GAIA: Murphy's multi-step tool-use assistant capabilities.

    Test ID: EXT-BENCH-002
    """
    _require_adapters()
    adapter = GAIAAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("gaia", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "gaia"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "gaia_results.json")


# ---------------------------------------------------------------------------
# AgentBench
# ---------------------------------------------------------------------------


def test_agent_bench(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """AgentBench: Murphy across 8 diverse agent environments.

    Test ID: EXT-BENCH-003
    """
    _require_adapters()
    adapter = AgentBenchAdapter()
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("agent-bench", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "agent-bench"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "agent_bench_results.json")


# ---------------------------------------------------------------------------
# WebArena
# ---------------------------------------------------------------------------


def test_web_arena(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """WebArena: Murphy's web automation goal-completion rate.

    Test ID: EXT-BENCH-004
    """
    _require_adapters()
    adapter = WebArenaAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("web-arena", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "web-arena"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "web_arena_results.json")


# ---------------------------------------------------------------------------
# ToolBench / BFCL
# ---------------------------------------------------------------------------


def test_tool_bench(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """ToolBench/BFCL: Murphy's tool selection accuracy and API calling.

    Test ID: EXT-BENCH-005
    """
    _require_adapters()
    adapter = ToolBenchAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("tool-bench", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "tool-bench"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "tool_bench_results.json")


# ---------------------------------------------------------------------------
# τ-Bench
# ---------------------------------------------------------------------------


def test_tau_bench(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """τ-Bench: Murphy's multi-turn HITL workflow completion.

    Test ID: EXT-BENCH-006
    """
    _require_adapters()
    adapter = TauBenchAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("tau-bench", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "tau-bench"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "tau_bench_results.json")


# ---------------------------------------------------------------------------
# Terminal-Bench
# ---------------------------------------------------------------------------


def test_terminal_bench(benchmark_max_tasks: int, benchmark_output_dir: Path) -> None:
    """Terminal-Bench: Murphy's CLI and system automation capabilities.

    Test ID: EXT-BENCH-007
    """
    _require_adapters()
    adapter = TerminalBenchAdapter(max_tasks=benchmark_max_tasks)
    adapter.setup()

    suite = adapter.run_suite()
    _save_results("terminal-bench", suite)

    scores = adapter.score()
    assert scores["benchmark"] == "terminal-bench"
    assert 0.0 <= scores.get("success_rate", 0.0) <= 1.0

    adapter.export_results(benchmark_output_dir / "terminal_bench_results.json")


# ---------------------------------------------------------------------------
# Consolidated report
# ---------------------------------------------------------------------------


def test_generate_consolidated_report() -> None:
    """Generate a consolidated JSON + markdown report of all benchmark results.

    Test ID: EXT-BENCH-REPORT-001
    """
    _require_adapters()
    if not _ALL_RESULTS:
        pytest.skip("No benchmark results collected — run individual benchmarks first.")

    # JSON report ----------------------------------------------------------------
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    consolidated_json = _RESULTS_DIR / "BENCHMARK_EXTERNAL_RESULTS.json"
    consolidated_json.write_text(
        json.dumps(_ALL_RESULTS, indent=2), encoding="utf-8"
    )

    # Markdown report ------------------------------------------------------------
    lines = [
        "# Murphy System — External Benchmark Results",
        "",
        "| Benchmark | Tasks | Succeeded | Success Rate | Mean Score |",
        "|-----------|-------|-----------|--------------|------------|",
    ]
    for bench_name, result_dict in _ALL_RESULTS.items():
        total = result_dict.get("tasks_total", 0)
        succeeded = result_dict.get("tasks_succeeded", 0)
        rate = result_dict.get("success_rate", 0.0)
        mean_score = result_dict.get("mean_score", 0.0)
        lines.append(
            f"| {bench_name} | {total} | {succeeded} "
            f"| {rate:.1%} | {mean_score:.3f} |"
        )

    md_path = _RESULTS_DIR / "BENCHMARK_EXTERNAL_RESULTS.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert consolidated_json.exists()
    assert md_path.exists()
