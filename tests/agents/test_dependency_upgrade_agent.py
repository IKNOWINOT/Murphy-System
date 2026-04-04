#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Dependency Upgrade Agent (DEP-UPGRADE-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: scan, upgrade, report
#   G3: Covers outdated/vulnerability detection and edge cases
#   G4: Full range including empty scan results
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Dependency Upgrade Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dependency_upgrade_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    REQUIREMENTS_FILES,
    _find_requirements_files,
    _get_outdated_packages,
    _get_vulnerabilities,
    phase_report,
    phase_scan,
    phase_upgrade,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def scan_report_path(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "scan",
        "outdated": [
            {"name": "requests", "version": "2.28.0", "latest_version": "2.31.0"},
            {"name": "flask", "version": "2.3.0", "latest_version": "3.0.0"},
        ],
        "vulnerabilities": [
            {"name": "requests", "version": "2.28.0",
             "description": "CVE-2023-XXXX: SSRF bypass"},
        ],
        "requirements_files": ["requirements.txt"],
        "outdated_count": 2,
        "vulnerability_count": 1,
    }
    path = tmp_output / "scan_report.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def empty_scan_report(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "scan",
        "outdated": [],
        "vulnerabilities": [],
        "requirements_files": [],
        "outdated_count": 0,
        "vulnerability_count": 0,
    }
    path = tmp_output / "scan_report.json"
    path.write_text(json.dumps(report))
    return path


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "DEP-UPGRADE-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_requirements_files_list(self):
        assert len(REQUIREMENTS_FILES) >= 3


# ── Phase: Scan ───────────────────────────────────────────────────────────────


class TestPhaseScan:
    def test_produces_scan_report(self, tmp_output):
        result = phase_scan(tmp_output)
        assert (tmp_output / "scan_report.json").exists()
        assert "outdated" in result
        assert "vulnerabilities" in result
        assert "outdated_count" in result
        assert "vulnerability_count" in result

    def test_report_metadata(self, tmp_output):
        result = phase_scan(tmp_output)
        assert result["agent"] == AGENT_LABEL

    @patch("dependency_upgrade_agent.subprocess.run")
    def test_handles_pip_timeout(self, mock_run, tmp_output):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pip", timeout=120)
        packages = _get_outdated_packages()
        assert packages == []


# ── Phase: Upgrade ────────────────────────────────────────────────────────────


class TestPhaseUpgrade:
    def test_produces_upgrade_report(self, scan_report_path, tmp_output):
        result = phase_upgrade(scan_report_path, tmp_output)
        assert (tmp_output / "upgrade_report.json").exists()
        assert "upgrades_applied" in result
        assert result["total_upgrades"] == 2

    def test_empty_scan_produces_zero_upgrades(self, empty_scan_report, tmp_output):
        result = phase_upgrade(empty_scan_report, tmp_output)
        assert result["total_upgrades"] == 0


# ── Phase: Report ─────────────────────────────────────────────────────────────


class TestPhaseReport:
    def test_produces_markdown_report(self, scan_report_path, tmp_output):
        result = phase_report(scan_report_path, "true", tmp_output)
        assert (tmp_output / "upgrade_report.md").exists()
        assert result["tests_passed"] is True

    def test_tests_failed_flag(self, scan_report_path, tmp_output):
        result = phase_report(scan_report_path, "false", tmp_output)
        assert result["tests_passed"] is False

    def test_markdown_contains_packages(self, scan_report_path, tmp_output):
        phase_report(scan_report_path, "true", tmp_output)
        md = (tmp_output / "upgrade_report.md").read_text()
        assert "requests" in md
        assert "flask" in md


# ── Helpers ───────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_find_requirements_files_returns_list(self):
        result = _find_requirements_files()
        assert isinstance(result, list)

    def test_get_outdated_returns_list(self):
        result = _get_outdated_packages()
        assert isinstance(result, list)
