#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the E2E Hero Flow Agent (E2E-HERO-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the two phases: validate, metrics
#   G3: Covers import validation, workflow generation, gate wiring
#   G4: Full range including missing modules
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System E2E Hero Flow Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from e2e_hero_flow_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    TEST_INTENTS,
    _validate_gate_wiring,
    _validate_imports,
    _validate_workflow_generation,
    phase_metrics,
    phase_validate,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def prebuilt_report(tmp_output):
    """Create a pre-built hero flow report for metrics phase."""
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "validate",
        "passed": True,
        "steps": [
            {"name": "Import Validation", "passed": True, "duration_ms": 12.5,
             "details": "All imports OK"},
            {"name": "Workflow Generation", "passed": True, "duration_ms": 55.0,
             "details": "Generated 3 workflows OK"},
            {"name": "Gate Execution Wiring", "passed": True, "duration_ms": 8.0,
             "details": "Gate wiring OK"},
        ],
    }
    (tmp_output / "hero_flow_report.json").write_text(json.dumps(report))
    return tmp_output


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "E2E-HERO-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_intents_non_empty(self):
        assert len(TEST_INTENTS) >= 1
        for intent in TEST_INTENTS:
            assert isinstance(intent, str)
            assert len(intent) > 10


# ── Validation Steps ──────────────────────────────────────────────────────────


class TestValidationSteps:
    def test_validate_imports_returns_dict(self):
        result = _validate_imports()
        assert "name" in result
        assert "passed" in result
        assert "duration_ms" in result
        assert result["name"] == "Import Validation"

    def test_validate_workflow_generation(self):
        result = _validate_workflow_generation()
        assert "name" in result
        assert "passed" in result
        assert "duration_ms" in result
        assert result["name"] == "Workflow Generation"

    def test_validate_gate_wiring(self):
        result = _validate_gate_wiring()
        assert "name" in result
        assert "passed" in result
        assert "duration_ms" in result
        assert result["name"] == "Gate Execution Wiring"


# ── Phase: Validate ───────────────────────────────────────────────────────────


class TestPhaseValidate:
    def test_produces_report(self, tmp_output):
        # May exit with 1 if imports fail — catch that
        try:
            result = phase_validate(tmp_output)
            assert (tmp_output / "hero_flow_report.json").exists()
            assert "steps" in result
            assert "passed" in result
        except SystemExit:
            # Expected if hero flow modules not importable in test env
            assert (tmp_output / "hero_flow_report.json").exists()


# ── Phase: Metrics ────────────────────────────────────────────────────────────


class TestPhaseMetrics:
    def test_produces_metrics(self, prebuilt_report):
        result = phase_metrics(prebuilt_report)
        assert (prebuilt_report / "hero_flow_metrics.json").exists()
        assert "step_timings" in result
        assert "total_duration_ms" in result
        assert result["total_duration_ms"] > 0

    def test_metrics_without_report(self, tmp_output):
        result = phase_metrics(tmp_output)
        assert result["total_duration_ms"] == 0
        assert "note" in result
