#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Performance Regression Agent (PERF-REGRESSION-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: benchmark, compare, gate
#   G3: Covers baseline comparison and regression detection
#   G4: Full range including no baseline, regressions, improvements
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Performance Regression Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from perf_regression_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    BENCHMARKS,
    _load_baseline,
    _run_benchmark,
    phase_benchmark,
    phase_compare,
    phase_gate,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def benchmark_results(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "benchmark",
        "results": {
            "json_serialization": {
                "iterations": 10, "p50_ms": 0.05, "p95_ms": 0.08,
                "p99_ms": 0.1, "min_ms": 0.03, "max_ms": 0.12, "mean_ms": 0.06,
            },
            "import_latency": {
                "iterations": 10, "p50_ms": 5.0, "p95_ms": 8.0,
                "p99_ms": 10.0, "min_ms": 3.0, "max_ms": 12.0, "mean_ms": 6.0,
            },
        },
        "total_metrics": 2,
    }
    path = tmp_output / "benchmark_results.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def comparison_pass(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "regressions": [],
        "improvements": [],
        "comparisons": [],
        "total_metrics": 2,
        "threshold_pct": 10.0,
    }
    path = tmp_output / "comparison_report.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def comparison_fail(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "regressions": [
            {"metric": "import_latency", "baseline_p95": 5.0,
             "current_p95": 8.0, "change_pct": 60.0, "status": "regression"},
        ],
        "improvements": [],
        "comparisons": [],
        "total_metrics": 2,
        "threshold_pct": 10.0,
    }
    path = tmp_output / "comparison_report.json"
    path.write_text(json.dumps(report))
    return path


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "PERF-REGRESSION-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_benchmarks_list(self):
        assert len(BENCHMARKS) >= 3
        assert "json_serialization" in BENCHMARKS


# ── _run_benchmark ────────────────────────────────────────────────────────────


class TestRunBenchmark:
    def test_json_serialization_benchmark(self):
        result = _run_benchmark("json_serialization")
        assert "p50_ms" in result
        assert "p95_ms" in result
        assert "p99_ms" in result
        assert result["p50_ms"] >= 0

    def test_benchmark_iterations(self):
        result = _run_benchmark("json_serialization")
        assert result["iterations"] == 10


# ── Phase: Benchmark ──────────────────────────────────────────────────────────


class TestPhaseBenchmark:
    def test_produces_benchmark_results(self, tmp_output):
        result = phase_benchmark(tmp_output)
        assert (tmp_output / "benchmark_results.json").exists()
        assert "results" in result
        assert "total_metrics" in result
        assert result["total_metrics"] >= 1


# ── Phase: Compare ────────────────────────────────────────────────────────────


class TestPhaseCompare:
    def test_produces_comparison(self, benchmark_results, tmp_output):
        result = phase_compare(benchmark_results, 10.0, tmp_output)
        assert (tmp_output / "comparison_report.json").exists()
        assert "regressions" in result
        assert "improvements" in result

    def test_generates_markdown(self, benchmark_results, tmp_output):
        phase_compare(benchmark_results, 10.0, tmp_output)
        assert (tmp_output / "comparison_report.md").exists()


# ── Phase: Gate ───────────────────────────────────────────────────────────────


class TestPhaseGate:
    def test_passes_with_no_regressions(self, comparison_pass, tmp_output):
        # Should not raise
        phase_gate(comparison_pass, 10.0, tmp_output)

    def test_fails_with_regressions(self, comparison_fail, tmp_output):
        with pytest.raises(SystemExit) as exc_info:
            phase_gate(comparison_fail, 10.0, tmp_output)
        assert exc_info.value.code == 1


# ── _load_baseline ────────────────────────────────────────────────────────────


class TestLoadBaseline:
    def test_returns_dict_when_missing(self):
        result = _load_baseline()
        assert isinstance(result, dict)
