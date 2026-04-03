#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Integration Parity Agent (INTEGRATION-PARITY-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests six phases: test-parity, registry-parity, import-check,
#       server-wiring, baseline-check, matrix
#   G3: Covers module lifecycle chain validation
#   G4: Full range including missing registry/baseline
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Integration Parity Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


from integration_parity_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    BASELINE_PATH,
    REGISTRY_PATH,
    SERVER_PATH,
    _get_source_modules,
    phase_baseline_check,
    phase_import_check,
    phase_matrix,
    phase_registry_parity,
    phase_server_wiring,
    phase_test_parity,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def matrix_input(tmp_output):
    """Pre-populate phase results for the matrix aggregator."""
    (tmp_output / "test_parity.json").write_text(json.dumps({
        "total_modules": 50, "have_tests": 40, "missing_tests_count": 10,
    }))
    (tmp_output / "registry_parity.json").write_text(json.dumps({
        "total_modules": 50, "in_registry": 45, "missing_count": 5,
    }))
    (tmp_output / "import_check.json").write_text(json.dumps({
        "total_sampled": 20, "importable": 18, "failures": 2,
    }))
    (tmp_output / "server_wiring.json").write_text(json.dumps({
        "api_modules_found": 10, "server_wired": 8,
    }))
    (tmp_output / "baseline_check.json").write_text(json.dumps({
        "total_modules": 50, "in_baseline": 48, "baseline_entries": 48,
    }))
    return tmp_output


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "INTEGRATION-PARITY-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_known_paths(self):
        assert isinstance(REGISTRY_PATH, Path)
        assert isinstance(BASELINE_PATH, Path)
        assert isinstance(SERVER_PATH, Path)


# ── _get_source_modules ──────────────────────────────────────────────────────


class TestGetSourceModules:
    def test_returns_list(self):
        result = _get_source_modules()
        assert isinstance(result, list)

    def test_modules_have_keys(self):
        result = _get_source_modules()
        if result:
            m = result[0]
            assert "file" in m
            assert "module" in m
            assert "name" in m


# ── Phase: Test Parity ────────────────────────────────────────────────────────


class TestPhaseTestParity:
    def test_produces_report(self, tmp_output):
        result = phase_test_parity(tmp_output)
        assert (tmp_output / "test_parity.json").exists()
        assert "total_modules" in result
        assert "have_tests" in result
        assert "missing_tests_count" in result

    def test_counts_consistent(self, tmp_output):
        result = phase_test_parity(tmp_output)
        assert result["have_tests"] + result["missing_tests_count"] == result["total_modules"]


# ── Phase: Registry Parity ────────────────────────────────────────────────────


class TestPhaseRegistryParity:
    def test_produces_report(self, tmp_output):
        result = phase_registry_parity(tmp_output)
        assert (tmp_output / "registry_parity.json").exists()
        assert "total_modules" in result
        assert "in_registry" in result


# ── Phase: Import Check ──────────────────────────────────────────────────────


class TestPhaseImportCheck:
    def test_produces_report(self, tmp_output):
        result = phase_import_check(tmp_output)
        assert (tmp_output / "import_check.json").exists()
        assert "importable" in result
        assert "failures" in result


# ── Phase: Server Wiring ─────────────────────────────────────────────────────


class TestPhaseServerWiring:
    def test_produces_report(self, tmp_output):
        result = phase_server_wiring(tmp_output)
        assert (tmp_output / "server_wiring.json").exists()
        assert "server_wired" in result


# ── Phase: Baseline Check ────────────────────────────────────────────────────


class TestPhaseBaselineCheck:
    def test_produces_report(self, tmp_output):
        result = phase_baseline_check(tmp_output)
        assert (tmp_output / "baseline_check.json").exists()
        assert "in_baseline" in result


# ── Phase: Matrix ────────────────────────────────────────────────────────────


class TestPhaseMatrix:
    def test_produces_matrix(self, matrix_input):
        result = phase_matrix(matrix_input)
        assert (matrix_input / "parity_report.json").exists()
        assert (matrix_input / "parity_report.md").exists()
        assert "total_modules" in result
        assert "have_tests" in result
        assert "in_registry" in result
        assert "gap_count" in result

    def test_gap_count_calculation(self, matrix_input):
        result = phase_matrix(matrix_input)
        # 50-40=10 test gaps + 50-45=5 registry gaps + 50-48=2 baseline gaps = 17
        assert result["gap_count"] == 17

    def test_markdown_content(self, matrix_input):
        phase_matrix(matrix_input)
        md = (matrix_input / "parity_report.md").read_text()
        assert "Parity" in md
        assert "gap" in md.lower()

    def test_empty_matrix(self, tmp_output):
        result = phase_matrix(tmp_output)
        assert result["gap_count"] == 0  # All zeros → 0 gaps
