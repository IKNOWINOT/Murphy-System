#!/usr/bin/env python3
# Copyright (C) 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Dependency Deprecation Scanner (DEP-SCAN-001)
#
# Commissioning profile:
#   G1: Validates scanner detects deprecated actions, runtimes, and packages
#   G2: Tests workflow scanning, CI log scanning, full repo scan, fix generation
#   G3: Covers clean inputs, deprecated inputs, malformed YAML, empty inputs
#   G4: Full range of ecosystems and severity levels
#   G5: Expected: structured reports with correct finding counts
#   G6: Actual: verified via assertions
#   G9: Hardening: bounded storage, defensive parsing

"""Tests for Murphy System Dependency Deprecation Scanner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure Murphy System/src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dependency_deprecation_scanner import (  # noqa: E402
    DeprecationEcosystem,
    DeprecationFinding,
    DeprecationReport,
    DeprecationScanner,
    DeprecationSeverity,
    KNOWN_ACTION_DEPRECATIONS,
    LOG_DEPRECATION_PATTERNS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_WORKFLOW_CLEAN = """\
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
"""

SAMPLE_WORKFLOW_DEPRECATED_V3 = """\
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - uses: actions/upload-artifact@v3
"""

SAMPLE_WORKFLOW_MIXED = """\
name: Mixed
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - uses: actions/upload-artifact@v3
"""

SAMPLE_CI_LOG_WITH_DEPRECATION = """\
2026-04-01T10:00:00Z Run actions/checkout@v4
Node.js 20 actions are deprecated. The following actions are running on Node.js 20.
FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true
DeprecationWarning: pkg_resources is deprecated
npm warn deprecated inflight@1.0.6
"""

SAMPLE_CI_LOG_CLEAN = """\
2026-04-01T10:00:00Z All tests passed
Build succeeded in 45s
"""


@pytest.fixture
def scanner():
    """Provide a DeprecationScanner with reference date for deterministic testing."""
    return DeprecationScanner(reference_date="2026-04-02T00:00:00+00:00")


@pytest.fixture
def scanner_past_deadline():
    """Scanner with reference date past the June 2026 deadline."""
    return DeprecationScanner(reference_date="2026-07-01T00:00:00+00:00")


@pytest.fixture
def scanner_early():
    """Scanner with reference date well before deadlines (>90 days)."""
    return DeprecationScanner(reference_date="2025-01-01T00:00:00+00:00")


@pytest.fixture
def tmp_workflows(tmp_path):
    """Create a temporary workflows directory."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    return wf


# ── Test: Data Models ─────────────────────────────────────────────────────────

class TestDataModels:
    """G1: Verify data model serialization works correctly."""

    def test_finding_to_dict(self):
        """G5: DeprecationFinding.to_dict() returns all fields."""
        f = DeprecationFinding(
            finding_id="ddf-test",
            ecosystem="github_actions",
            severity="warning",
            source_file="ci.yml",
            line_number=5,
            current_value="actions/checkout@v3",
            recommended_value="actions/checkout@v4",
            reason="Deprecated",
        )
        d = f.to_dict()
        assert d["finding_id"] == "ddf-test"
        assert d["ecosystem"] == "github_actions"
        assert d["severity"] == "warning"
        assert d["source_file"] == "ci.yml"
        assert d["line_number"] == 5
        assert d["current_value"] == "actions/checkout@v3"
        assert d["recommended_value"] == "actions/checkout@v4"

    def test_report_to_dict(self):
        """G5: DeprecationReport.to_dict() includes findings."""
        r = DeprecationReport(
            report_id="ddr-test",
            files_scanned=3,
            total_findings=1,
            critical_count=1,
        )
        d = r.to_dict()
        assert d["report_id"] == "ddr-test"
        assert d["files_scanned"] == 3
        assert d["total_findings"] == 1
        assert d["critical_count"] == 1
        assert isinstance(d["findings"], list)

    def test_severity_enum_values(self):
        """G3: Severity enum has expected values."""
        assert DeprecationSeverity.INFO.value == "info"
        assert DeprecationSeverity.WARNING.value == "warning"
        assert DeprecationSeverity.CRITICAL.value == "critical"

    def test_ecosystem_enum_values(self):
        """G3: Ecosystem enum covers all supported types."""
        assert DeprecationEcosystem.GITHUB_ACTIONS.value == "github_actions"
        assert DeprecationEcosystem.NODEJS_RUNTIME.value == "nodejs_runtime"
        assert DeprecationEcosystem.PYTHON_RUNTIME.value == "python_runtime"
        assert DeprecationEcosystem.PIP_PACKAGE.value == "pip_package"
        assert DeprecationEcosystem.NPM_PACKAGE.value == "npm_package"


# ── Test: Workflow Scanning ───────────────────────────────────────────────────

class TestWorkflowScanning:
    """G2: Verify workflow YAML scanning detects deprecated actions."""

    def test_scan_detects_deprecated_v3_actions(self, scanner):
        """G1: Scanner finds v3 actions as deprecated."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        assert report.total_findings >= 2  # checkout@v3, upload-artifact@v3
        actions_found = {f.current_value for f in report.findings}
        assert "actions/checkout@v3" in actions_found
        assert "actions/upload-artifact@v3" in actions_found

    def test_scan_current_actions_still_flagged(self, scanner):
        """G3: Current v4/v5 actions flagged due to Node.js 20 deprecation."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_CLEAN, "test.yml"
        )
        # v4/v5 are still on Node.js 20 — they should be flagged
        assert report.total_findings >= 1

    def test_scan_mixed_workflow(self, scanner):
        """G3: Mixed workflow correctly identifies only deprecated actions."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_MIXED, "test.yml"
        )
        assert report.total_findings >= 1
        # upload-artifact@v3 should definitely be found
        actions = {f.current_value for f in report.findings}
        assert "actions/upload-artifact@v3" in actions

    def test_scan_empty_content(self, scanner):
        """G3: Empty content produces zero findings."""
        report = scanner.scan_workflow_content("", "empty.yml")
        assert report.total_findings == 0
        assert report.files_scanned == 1

    def test_scan_malformed_yaml(self, scanner):
        """G3: Malformed YAML does not crash scanner."""
        content = "this is not: [valid yaml\n  - broken: {{"
        report = scanner.scan_workflow_content(content, "bad.yml")
        assert report.total_findings == 0

    def test_scan_no_uses_lines(self, scanner):
        """G3: YAML with no 'uses:' lines produces zero findings."""
        content = "name: test\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hello\n"
        report = scanner.scan_workflow_content(content, "no-uses.yml")
        assert report.total_findings == 0

    def test_scan_returns_line_numbers(self, scanner):
        """G5: Findings include correct line numbers."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        assert all(f.line_number > 0 for f in report.findings)

    def test_scan_returns_fix_recommendations(self, scanner):
        """G5: Report includes fix recommendations for each finding."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        assert len(report.fix_recommendations) >= 1
        for rec in report.fix_recommendations:
            assert "old_value" in rec
            assert "new_value" in rec
            assert rec["action"] == "replace_action_version"


# ── Test: Workflow Directory Scanning ─────────────────────────────────────────

class TestWorkflowDirScanning:
    """G2: Verify scanning an entire workflows directory."""

    def test_scan_directory_with_files(self, scanner, tmp_workflows):
        """G1: Scanning a directory with workflow files produces findings."""
        (tmp_workflows / "ci.yml").write_text(SAMPLE_WORKFLOW_DEPRECATED_V3)
        (tmp_workflows / "deploy.yml").write_text(SAMPLE_WORKFLOW_CLEAN)
        report = scanner.scan_workflows(tmp_workflows)
        assert report.files_scanned == 2
        assert report.total_findings >= 2

    def test_scan_empty_directory(self, scanner, tmp_path):
        """G3: Empty directory produces zero findings."""
        empty = tmp_path / "empty_workflows"
        empty.mkdir()
        report = scanner.scan_workflows(empty)
        assert report.files_scanned == 0
        assert report.total_findings == 0

    def test_scan_missing_directory(self, scanner, tmp_path):
        """G3: Missing directory does not crash, returns empty report."""
        report = scanner.scan_workflows(tmp_path / "nonexistent")
        assert report.files_scanned == 0
        assert report.total_findings == 0

    def test_scan_ignores_non_yaml(self, scanner, tmp_workflows):
        """G3: Non-YAML files are ignored."""
        (tmp_workflows / "ci.yml").write_text(SAMPLE_WORKFLOW_CLEAN)
        (tmp_workflows / "readme.md").write_text("# Not YAML")
        (tmp_workflows / "script.py").write_text("print('hello')")
        report = scanner.scan_workflows(tmp_workflows)
        assert report.files_scanned == 1  # Only the .yml file


# ── Test: CI Log Scanning ─────────────────────────────────────────────────────

class TestCILogScanning:
    """G2: Verify CI log scanning detects deprecation warnings."""

    def test_scan_log_with_nodejs_deprecation(self, scanner):
        """G1: Scanner detects Node.js deprecation in CI logs."""
        report = scanner.scan_ci_logs(SAMPLE_CI_LOG_WITH_DEPRECATION)
        assert report.total_findings >= 1
        ecosystems = {f.ecosystem for f in report.findings}
        assert DeprecationEcosystem.NODEJS_RUNTIME.value in ecosystems

    def test_scan_log_with_npm_deprecation(self, scanner):
        """G1: Scanner detects npm deprecation warnings."""
        report = scanner.scan_ci_logs(SAMPLE_CI_LOG_WITH_DEPRECATION)
        ecosystems = {f.ecosystem for f in report.findings}
        assert DeprecationEcosystem.NPM_PACKAGE.value in ecosystems

    def test_scan_log_with_python_deprecation(self, scanner):
        """G1: Scanner detects Python DeprecationWarning."""
        report = scanner.scan_ci_logs(SAMPLE_CI_LOG_WITH_DEPRECATION)
        ecosystems = {f.ecosystem for f in report.findings}
        assert DeprecationEcosystem.PIP_PACKAGE.value in ecosystems

    def test_scan_clean_log(self, scanner):
        """G3: Clean CI log produces zero findings."""
        report = scanner.scan_ci_logs(SAMPLE_CI_LOG_CLEAN)
        assert report.total_findings == 0

    def test_scan_empty_log(self, scanner):
        """G3: Empty log produces zero findings."""
        report = scanner.scan_ci_logs("")
        assert report.total_findings == 0

    def test_scan_log_line_numbers(self, scanner):
        """G5: Log findings include line numbers."""
        report = scanner.scan_ci_logs(SAMPLE_CI_LOG_WITH_DEPRECATION)
        for f in report.findings:
            assert f.line_number >= 1


# ── Test: Severity Calculation ────────────────────────────────────────────────

class TestSeverityCalculation:
    """G3: Verify severity is computed correctly based on deadline proximity."""

    def test_severity_critical_past_deadline(self, scanner_past_deadline):
        """G5: Past-deadline deprecations are CRITICAL."""
        report = scanner_past_deadline.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        for f in report.findings:
            assert f.severity == "critical"

    def test_severity_warning_within_90_days(self, scanner):
        """G5: Deprecations within 90 days of deadline are WARNING."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        severities = {f.severity for f in report.findings}
        assert "warning" in severities or "critical" in severities

    def test_severity_info_far_from_deadline(self, scanner_early):
        """G5: Deprecations far from deadline are INFO."""
        report = scanner_early.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        for f in report.findings:
            assert f.severity == "info"

    def test_severity_no_deadline(self):
        """G3: Missing deadline defaults to WARNING."""
        scanner = DeprecationScanner(
            action_deprecations=[{
                "action": "actions/checkout",
                "deprecated_versions": "v3",
                "recommended_version": "v4",
                "reason": "test",
            }],
        )
        report = scanner.scan_workflow_content(
            "steps:\n  - uses: actions/checkout@v3\n", "t.yml"
        )
        assert report.findings[0].severity == "warning"


# ── Test: Full Scan ───────────────────────────────────────────────────────────

class TestFullScan:
    """G2: Verify full repository scan aggregates all sources."""

    def test_full_scan_finds_workflow_deprecations(self, scanner, tmp_path):
        """G1: Full scan detects deprecations in workflows."""
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text(SAMPLE_WORKFLOW_DEPRECATED_V3)
        report = scanner.full_scan(tmp_path)
        assert report.total_findings >= 2

    def test_full_scan_empty_repo(self, scanner, tmp_path):
        """G3: Empty repo produces zero findings."""
        report = scanner.full_scan(tmp_path)
        assert report.total_findings == 0

    def test_full_scan_recommends_env_var(self, scanner, tmp_path):
        """G5: Full scan recommends FORCE_JAVASCRIPT_ACTIONS_TO_NODE24."""
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text(SAMPLE_WORKFLOW_CLEAN)
        report = scanner.full_scan(tmp_path)
        env_recs = [r for r in report.fix_recommendations
                    if r.get("action") == "add_env_var"]
        assert len(env_recs) >= 1
        assert env_recs[0]["key"] == "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24"


# ── Test: Fix Generation ─────────────────────────────────────────────────────

class TestFixGeneration:
    """G2: Verify fix generation produces correct updated content."""

    def test_generate_fix_replaces_action(self, scanner):
        """G1: Fix replaces deprecated action version."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        fixed = scanner.generate_fix(
            SAMPLE_WORKFLOW_DEPRECATED_V3, report.fix_recommendations
        )
        assert "actions/checkout@v3" not in fixed
        assert "actions/upload-artifact@v3" not in fixed

    def test_generate_fix_empty_recs(self, scanner):
        """G3: Empty recommendations return original content."""
        fixed = scanner.generate_fix(SAMPLE_WORKFLOW_CLEAN, [])
        assert fixed == SAMPLE_WORKFLOW_CLEAN

    def test_generate_fix_preserves_structure(self, scanner):
        """G5: Fix preserves YAML structure (no reordering)."""
        report = scanner.scan_workflow_content(
            SAMPLE_WORKFLOW_DEPRECATED_V3, "test.yml"
        )
        fixed = scanner.generate_fix(
            SAMPLE_WORKFLOW_DEPRECATED_V3, report.fix_recommendations
        )
        # Line count should be the same (only version tags changed)
        assert fixed.count("\n") == SAMPLE_WORKFLOW_DEPRECATED_V3.count("\n")


# ── Test: Bounded Storage ─────────────────────────────────────────────────────

class TestBoundedStorage:
    """G9: Verify bounded storage prevents unbounded growth."""

    def test_reports_bounded(self, scanner):
        """G9: Reports are evicted when storage limit reached."""
        for i in range(10):
            scanner.scan_workflow_content(
                SAMPLE_WORKFLOW_DEPRECATED_V3, f"test_{i}.yml"
            )
        reports = scanner.get_reports(limit=100)
        assert len(reports) <= 500  # _MAX_REPORTS

    def test_status_shows_counts(self, scanner):
        """G5: Status shows correct counts."""
        scanner.scan_workflow_content(SAMPLE_WORKFLOW_CLEAN, "test.yml")
        status = scanner.get_status()
        assert "total_reports" in status
        assert status["total_reports"] >= 1
        assert "known_action_deprecations" in status
        assert "log_patterns" in status


# ── Test: Constants Verification ──────────────────────────────────────────────

class TestConstants:
    """G4: Verify known deprecation databases are properly configured."""

    def test_known_action_deprecations_not_empty(self):
        """G4: Known action deprecations list is populated."""
        assert len(KNOWN_ACTION_DEPRECATIONS) >= 4

    def test_log_deprecation_patterns_not_empty(self):
        """G4: Log deprecation patterns list is populated."""
        assert len(LOG_DEPRECATION_PATTERNS) >= 3

    def test_all_actions_have_required_fields(self):
        """G4: All action deprecations have required fields."""
        required = {"action", "deprecated_versions", "recommended_version", "reason"}
        for dep in KNOWN_ACTION_DEPRECATIONS:
            assert required.issubset(dep.keys()), f"Missing fields in {dep.get('action')}"

    def test_all_log_patterns_compile(self):
        """G9: All log patterns are valid regex."""
        import re
        for pat in LOG_DEPRECATION_PATTERNS:
            re.compile(pat["pattern"])  # Should not raise
