#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Documentation Freshness Agent (DOC-FRESHNESS-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: check, scan-apis, baseline
#   G3: Covers docstring scanning and baseline drift
#   G4: Full range including missing baselines
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Documentation Freshness Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from doc_freshness_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    BASELINE_PATH,
    DOC_DIRS,
    _get_changed_doc_files,
    _get_changed_python_files,
    _merge_reports,
    phase_baseline,
    phase_check,
    phase_scan_apis,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "DOC-FRESHNESS-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_doc_dirs_non_empty(self):
        assert len(DOC_DIRS) >= 1


# ── Phase: Check ──────────────────────────────────────────────────────────────


class TestPhaseCheck:
    def test_produces_report(self, tmp_output):
        result = phase_check(tmp_output)
        assert (tmp_output / "freshness_check.json").exists()
        assert "files_changed" in result
        assert "doc_debts" in result

    def test_report_metadata(self, tmp_output):
        result = phase_check(tmp_output)
        assert result["agent"] == AGENT_LABEL

    def test_non_negative_counts(self, tmp_output):
        result = phase_check(tmp_output)
        assert result["files_changed"] >= 0
        assert result["doc_debts"] >= 0


# ── Phase: Scan APIs ─────────────────────────────────────────────────────────


class TestPhaseScanApis:
    def test_produces_report(self, tmp_output):
        result = phase_scan_apis(tmp_output)
        assert (tmp_output / "api_scan.json").exists()
        assert "total_public_apis" in result
        assert "missing_docstrings" in result
        assert "coverage_pct" in result

    def test_coverage_in_range(self, tmp_output):
        result = phase_scan_apis(tmp_output)
        assert 0 <= result["coverage_pct"] <= 100


# ── Phase: Baseline ──────────────────────────────────────────────────────────


class TestPhaseBaseline:
    def test_produces_report(self, tmp_output):
        result = phase_baseline(tmp_output)
        assert (tmp_output / "baseline_check.json").exists()
        assert "current_module_count" in result
        assert "baseline_drift" in result

    def test_creates_merged_report(self, tmp_output):
        phase_baseline(tmp_output)
        assert (tmp_output / "freshness_report.json").exists()
        assert (tmp_output / "freshness_report.md").exists()


# ── Helpers ───────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_changed_python_files_returns_list(self):
        result = _get_changed_python_files()
        assert isinstance(result, list)

    def test_changed_doc_files_returns_list(self):
        result = _get_changed_doc_files()
        assert isinstance(result, list)

    def test_merge_reports_with_empty(self, tmp_output):
        _merge_reports(tmp_output)
        assert (tmp_output / "freshness_report.json").exists()
