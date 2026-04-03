#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Chaos Regression Agent (CHAOS-REGRESSION-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the two phases: run, gate
#   G3: Covers experiment execution and scoring logic
#   G4: Full range including passing and failing scores
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Chaos Regression Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from chaos_regression_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    EXPERIMENTS,
    _run_experiment,
    phase_gate,
    phase_run,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def passing_results(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "overall_score": 0.85,
        "threshold": 0.70,
        "experiments_run": 2,
        "recoveries": 2,
        "failures": 0,
        "experiments": [],
    }
    path = tmp_output / "chaos_results.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def failing_results(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "overall_score": 0.40,
        "threshold": 0.70,
        "experiments_run": 2,
        "recoveries": 0,
        "failures": 2,
        "experiments": [
            {"name": "test1", "recovered": False, "score": 0.2, "error": "ImportError"},
            {"name": "test2", "recovered": False, "score": 0.6, "error": "Timeout"},
        ],
    }
    path = tmp_output / "chaos_results.json"
    path.write_text(json.dumps(report))
    return path


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "CHAOS-REGRESSION-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_experiments_non_empty(self):
        assert len(EXPERIMENTS) >= 3
        for exp in EXPERIMENTS:
            assert "name" in exp
            assert "description" in exp
            assert "target" in exp


# ── _run_experiment ───────────────────────────────────────────────────────────


class TestRunExperiment:
    def test_importable_module_passes(self):
        experiment = {"name": "json_test", "description": "Test json",
                      "target": "json"}
        result = _run_experiment(experiment)
        assert result["recovered"] is True
        assert result["import_ok"] is True
        assert result["score"] > 0.5
        assert "duration_ms" in result

    def test_nonexistent_module_fails(self):
        experiment = {"name": "missing", "description": "Test missing",
                      "target": "src.__nonexistent_xyz__"}
        result = _run_experiment(experiment)
        assert result["recovered"] is False
        assert result["import_ok"] is False
        assert result["score"] == 0.0

    def test_result_has_duration(self):
        experiment = {"name": "test", "description": "d", "target": "json"}
        result = _run_experiment(experiment)
        assert result["duration_ms"] >= 0


# ── Phase: Run ────────────────────────────────────────────────────────────────


class TestPhaseRun:
    def test_produces_results(self, tmp_output):
        result = phase_run(0.70, tmp_output)
        assert (tmp_output / "chaos_results.json").exists()
        assert "overall_score" in result
        assert "experiments_run" in result
        assert "recoveries" in result
        assert "failures" in result
        assert result["recoveries"] + result["failures"] == result["experiments_run"]

    def test_score_bounded(self, tmp_output):
        result = phase_run(0.70, tmp_output)
        assert 0 <= result["overall_score"] <= 1.0


# ── Phase: Gate ───────────────────────────────────────────────────────────────


class TestPhaseGate:
    def test_passes_above_threshold(self, passing_results, tmp_output):
        # Should not raise
        phase_gate(passing_results, 0.70, tmp_output)

    def test_fails_below_threshold(self, failing_results, tmp_output):
        with pytest.raises(SystemExit) as exc_info:
            phase_gate(failing_results, 0.70, tmp_output)
        assert exc_info.value.code == 1

    def test_exact_threshold_passes(self, tmp_output):
        report = {"overall_score": 0.70, "experiments": []}
        path = tmp_output / "chaos_results.json"
        path.write_text(json.dumps(report))
        phase_gate(path, 0.70, tmp_output)  # Should not raise
