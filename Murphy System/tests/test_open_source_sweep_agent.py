#!/usr/bin/env python3
# Copyright (C) 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Open Source Sweep Agent (OSS-SWEEP-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: classify, audit, report
#   G3: Covers edge cases — empty dirs, missing files, mixed classifications
#   G4: Full range of community / proprietary / unclassified scenarios
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Open Source Sweep Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure Murphy System/scripts is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from open_source_sweep_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    COMMUNITY_LICENSE_MARKERS,
    COMMUNITY_MODULES,
    PROPRIETARY_LICENSE_MARKERS,
    PROPRIETARY_MODULES,
    VALID_COPYRIGHT_PATTERNS,
    _audit_module,
    _build_issues,
    _classify_single,
    _detect_leaks,
    _detect_license_marker,
    _has_copyright_header,
    _read_file_head,
    _render_markdown,
    _severity,
    phase_audit,
    phase_classify,
    phase_report,
    run_sweep,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    """Provide a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_src(tmp_path):
    """Provide a temp src/ with community, proprietary, and unclassified modules."""
    src = tmp_path / "src"
    src.mkdir()

    # Community module (single file)
    (src / "murphy_confidence.py").write_text(
        '# Copyright © 2024 Inoni LLC\n'
        '# License: Apache-2.0\n'
        '"""Murphy confidence scoring."""\n'
        'def score(): return 0.9\n'
    )

    # Proprietary package
    pkg = src / "billing"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '# Copyright (C) 2024 Inoni LLC\n'
        '# License: BSL-1.1\n'
        '"""Billing subsystem."""\n'
    )

    # Unclassified module
    (src / "some_helper.py").write_text(
        '# Copyright © 2024 Inoni LLC\n'
        '# License: BSL-1.1\n'
        '"""Some helper module."""\n'
    )

    # Module missing copyright and license
    (src / "no_header.py").write_text('def bare(): pass\n')

    # __init__.py should be skipped
    (src / "__init__.py").write_text("")

    return src


@pytest.fixture
def community_module_with_leak(tmp_path):
    """Provide a community module that references proprietary patterns."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "murphy_confidence.py").write_text(
        '# Copyright © 2024 Inoni LLC\n'
        '# License: Apache-2.0\n'
        '"""Murphy confidence scoring."""\n'
        'from billing_engine import BillingEngine\n'
        'SIEM_ENDPOINT = "https://siem.example.com"\n'
    )
    return src


@pytest.fixture
def classification_report(tmp_src):
    """Build a sample classification report."""
    return {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "classify",
        "total_modules": 4,
        "community_count": 1,
        "proprietary_count": 1,
        "unclassified_count": 2,
        "modules": [
            {"name": "murphy_confidence", "type": "module",
             "classification": "community",
             "path": str(tmp_src / "murphy_confidence.py")},
            {"name": "billing", "type": "package",
             "classification": "proprietary",
             "path": str(tmp_src / "billing")},
            {"name": "some_helper", "type": "module",
             "classification": "unclassified",
             "path": str(tmp_src / "some_helper.py")},
            {"name": "no_header", "type": "module",
             "classification": "unclassified",
             "path": str(tmp_src / "no_header.py")},
        ],
    }


@pytest.fixture
def audit_report():
    """Build a sample audit report with some issues."""
    return {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "audit",
        "total_audited": 4,
        "missing_copyright_count": 1,
        "no_license_count": 1,
        "license_mismatch_count": 0,
        "leak_count": 0,
        "modules_with_leaks": 0,
        "results": [],
        "missing_copyright": ["no_header"],
        "no_license": ["no_header"],
        "license_mismatches": [],
        "boundary_leaks": [],
    }


# ── Test: Constants ──────────────────────────────────────────────────────────


class TestConstants:
    """G1: Agent constants are correctly set."""

    def test_agent_label(self):
        assert AGENT_LABEL == "OSS-SWEEP-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_community_modules_non_empty(self):
        assert len(COMMUNITY_MODULES) > 0

    def test_proprietary_modules_non_empty(self):
        assert len(PROPRIETARY_MODULES) > 0

    def test_copyright_patterns_non_empty(self):
        assert len(VALID_COPYRIGHT_PATTERNS) > 0

    def test_license_markers_non_empty(self):
        assert len(COMMUNITY_LICENSE_MARKERS) > 0
        assert len(PROPRIETARY_LICENSE_MARKERS) > 0


# ── Test: _classify_single ───────────────────────────────────────────────────


class TestClassifySingle:
    """G2: Module names are classified into the correct bucket."""

    def test_community_exact(self):
        assert _classify_single("murphy_confidence") == "community"

    def test_community_prefix(self):
        assert _classify_single("murphy_confidence_v2") == "community"

    def test_proprietary_exact(self):
        assert _classify_single("billing") == "proprietary"

    def test_proprietary_prefix(self):
        assert _classify_single("billing_v2") == "proprietary"

    def test_unclassified(self):
        assert _classify_single("random_module") == "unclassified"

    def test_case_insensitive(self):
        """G3: Classification is case-insensitive."""
        assert _classify_single("Murphy_Confidence") == "community"
        assert _classify_single("BILLING") == "proprietary"

    def test_empty_name(self):
        assert _classify_single("") == "unclassified"


# ── Test: _read_file_head ────────────────────────────────────────────────────


class TestReadFileHead:
    """G3: File head reading handles edge cases."""

    def test_reads_first_lines(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        head = _read_file_head(f, max_lines=3)
        assert head.count("\n") == 3
        assert "line4" not in head

    def test_nonexistent_file(self, tmp_path):
        head = _read_file_head(tmp_path / "nonexistent.py")
        assert head == ""

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        head = _read_file_head(f)
        assert head == ""


# ── Test: _has_copyright_header ──────────────────────────────────────────────


class TestHasCopyrightHeader:
    """G5: Copyright detection works for valid Inoni headers."""

    def test_with_copyright_symbol(self):
        assert _has_copyright_header("# Copyright © 2024 Inoni LLC") is True

    def test_with_c_in_parens(self):
        assert _has_copyright_header("# Copyright (C) 2024 Inoni LLC") is True

    def test_without_inoni(self):
        assert _has_copyright_header("# Copyright (C) 2024 Some Corp") is False

    def test_no_copyright(self):
        assert _has_copyright_header("# Just a comment") is False

    def test_empty(self):
        assert _has_copyright_header("") is False


# ── Test: _detect_license_marker ─────────────────────────────────────────────


class TestDetectLicenseMarker:
    """G5: License marker detection."""

    def test_apache(self):
        marker = _detect_license_marker("# License: Apache-2.0\n")
        assert marker is not None
        assert "Apache" in marker

    def test_bsl(self):
        marker = _detect_license_marker("# License: BSL-1.1\n")
        assert marker is not None
        assert "BSL" in marker

    def test_no_marker(self):
        assert _detect_license_marker("# Just a comment\n") is None

    def test_case_insensitive(self):
        marker = _detect_license_marker("# license: apache-2.0\n")
        assert marker is not None


# ── Test: _detect_leaks ──────────────────────────────────────────────────────


class TestDetectLeaks:
    """G3: Proprietary leak detection in community modules."""

    def test_no_leaks_in_clean_file(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text('"""Clean community module."""\ndef compute(): return 42\n')
        leaks = _detect_leaks(f, "community")
        assert leaks == []

    def test_leaks_detected(self, tmp_path):
        f = tmp_path / "leaky.py"
        f.write_text('from billing_engine import BillingEngine\nSIEM_URL = "x"\n')
        leaks = _detect_leaks(f, "community")
        assert len(leaks) >= 1

    def test_no_check_for_proprietary(self, tmp_path):
        """G3: Proprietary modules are not scanned for leaks."""
        f = tmp_path / "internal.py"
        f.write_text('SIEM_URL = "audit"\nBillingEngine = True\n')
        leaks = _detect_leaks(f, "proprietary")
        assert leaks == []

    def test_no_check_for_unclassified(self, tmp_path):
        f = tmp_path / "misc.py"
        f.write_text('SIEM_URL = "x"\n')
        leaks = _detect_leaks(f, "unclassified")
        assert leaks == []

    def test_nonexistent_file(self, tmp_path):
        leaks = _detect_leaks(tmp_path / "gone.py", "community")
        assert leaks == []


# ── Test: _audit_module ──────────────────────────────────────────────────────


class TestAuditModule:
    """G5/G6: Single-module audit produces correct result."""

    def test_clean_module(self, tmp_src):
        mod = {
            "name": "murphy_confidence", "type": "module",
            "classification": "community",
            "path": str(tmp_src / "murphy_confidence.py"),
        }
        result = _audit_module(mod)
        assert result["has_copyright"] is True
        assert result["license_marker"] is not None
        assert result["leak_count"] == 0
        assert result["license_mismatch"] is False

    def test_missing_header(self, tmp_src):
        mod = {
            "name": "no_header", "type": "module",
            "classification": "unclassified",
            "path": str(tmp_src / "no_header.py"),
        }
        result = _audit_module(mod)
        assert result["has_copyright"] is False
        assert result["license_marker"] is None

    def test_package_audit(self, tmp_src):
        mod = {
            "name": "billing", "type": "package",
            "classification": "proprietary",
            "path": str(tmp_src / "billing"),
        }
        result = _audit_module(mod)
        assert result["has_copyright"] is True
        assert result["license_marker"] is not None


# ── Test: Phase Classify ─────────────────────────────────────────────────────


class TestPhaseClassify:
    """G1/G2: Classification phase produces correct report."""

    def test_classifies_all_modules(self, tmp_src, tmp_output, monkeypatch):
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", tmp_src)
        report = phase_classify(tmp_output)
        assert report["total_modules"] == 4
        assert report["community_count"] == 1
        assert report["proprietary_count"] == 1
        assert report["unclassified_count"] == 2

    def test_writes_json(self, tmp_src, tmp_output, monkeypatch):
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", tmp_src)
        phase_classify(tmp_output)
        report_path = tmp_output / "classification_report.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert data["phase"] == "classify"
        assert data["agent"] == AGENT_LABEL

    def test_empty_src(self, tmp_path, tmp_output, monkeypatch):
        empty = tmp_path / "empty_src"
        empty.mkdir()
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", empty)
        report = phase_classify(tmp_output)
        assert report["total_modules"] == 0

    def test_nonexistent_src(self, tmp_path, tmp_output, monkeypatch):
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", tmp_path / "nope")
        report = phase_classify(tmp_output)
        assert report["total_modules"] == 0


# ── Test: Phase Audit ────────────────────────────────────────────────────────


class TestPhaseAudit:
    """G5/G6: Audit phase produces correct report."""

    def test_audit_counts(self, classification_report, tmp_output):
        report = phase_audit(classification_report, tmp_output)
        assert report["total_audited"] == 4
        assert report["missing_copyright_count"] >= 1  # no_header has no copyright

    def test_writes_json(self, classification_report, tmp_output):
        phase_audit(classification_report, tmp_output)
        report_path = tmp_output / "audit_report.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert data["phase"] == "audit"

    def test_empty_modules(self, tmp_output):
        cls = {"modules": []}
        report = phase_audit(cls, tmp_output)
        assert report["total_audited"] == 0
        assert report["leak_count"] == 0

    def test_leak_detection_in_audit(self, community_module_with_leak, tmp_output):
        cls = {
            "modules": [{
                "name": "murphy_confidence", "type": "module",
                "classification": "community",
                "path": str(community_module_with_leak / "murphy_confidence.py"),
            }],
        }
        report = phase_audit(cls, tmp_output)
        assert report["leak_count"] >= 1
        assert report["modules_with_leaks"] >= 1


# ── Test: _build_issues ──────────────────────────────────────────────────────


class TestBuildIssues:
    """G7: Issue list is correctly built from audit findings."""

    def test_no_issues_for_clean_audit(self):
        audit = {
            "boundary_leaks": [],
            "license_mismatches": [],
            "missing_copyright": [],
            "no_license": [],
        }
        issues = _build_issues(audit)
        assert issues == []

    def test_leak_issue(self):
        audit = {
            "boundary_leaks": [{
                "module": "murphy_confidence",
                "leaks": [{"pattern": "SIEM", "match": "SIEM", "file": "x.py"}],
            }],
            "license_mismatches": [],
            "missing_copyright": [],
            "no_license": [],
        }
        issues = _build_issues(audit)
        assert len(issues) == 1
        assert issues[0]["severity"] == "CRITICAL"
        assert issues[0]["type"] == "boundary_leak"

    def test_missing_copyright_issue(self):
        audit = {
            "boundary_leaks": [],
            "license_mismatches": [],
            "missing_copyright": ["no_header"],
            "no_license": [],
        }
        issues = _build_issues(audit)
        assert len(issues) == 1
        assert issues[0]["severity"] == "MEDIUM"

    def test_license_mismatch_issue(self):
        audit = {
            "boundary_leaks": [],
            "license_mismatches": ["bad_module"],
            "missing_copyright": [],
            "no_license": [],
        }
        issues = _build_issues(audit)
        assert len(issues) == 1
        assert issues[0]["severity"] == "HIGH"

    def test_no_license_issue(self):
        audit = {
            "boundary_leaks": [],
            "license_mismatches": [],
            "missing_copyright": [],
            "no_license": ["bare_module"],
        }
        issues = _build_issues(audit)
        assert len(issues) == 1
        assert issues[0]["severity"] == "LOW"


# ── Test: _severity ──────────────────────────────────────────────────────────


class TestSeverity:
    """G5: Severity mapping is consistent."""

    def test_boundary_leak(self):
        assert _severity("boundary_leak") == "CRITICAL"

    def test_license_mismatch(self):
        assert _severity("license_mismatch") == "HIGH"

    def test_missing_copyright(self):
        assert _severity("missing_copyright") == "MEDIUM"

    def test_no_license(self):
        assert _severity("no_license") == "LOW"

    def test_unknown(self):
        assert _severity("unknown") == "INFO"


# ── Test: Phase Report ───────────────────────────────────────────────────────


class TestPhaseReport:
    """G7/G8: Report phase produces complete JSON + Markdown."""

    def test_report_json(self, tmp_output, audit_report):
        cls = {"total_modules": 4, "community_count": 1,
               "proprietary_count": 1, "unclassified_count": 2}
        report = phase_report(cls, audit_report, tmp_output)
        assert report["phase"] == "report"
        assert report["issue_count"] >= 2  # missing_copyright + no_license
        assert "commissioning_assessment" in report

    def test_report_writes_files(self, tmp_output, audit_report):
        cls = {"total_modules": 4, "community_count": 1,
               "proprietary_count": 1, "unclassified_count": 2}
        phase_report(cls, audit_report, tmp_output)
        # JSON (latest + dated)
        assert (tmp_output / "sweep_report_latest.json").exists()
        # Markdown
        md_files = list(tmp_output.glob("sweep_report_*.md"))
        assert len(md_files) >= 1

    def test_clean_audit_report(self, tmp_output):
        cls = {"total_modules": 2, "community_count": 1,
               "proprietary_count": 1, "unclassified_count": 0}
        audit = {
            "missing_copyright_count": 0, "no_license_count": 0,
            "license_mismatch_count": 0, "leak_count": 0,
            "boundary_leaks": [], "license_mismatches": [],
            "missing_copyright": [], "no_license": [],
        }
        report = phase_report(cls, audit, tmp_output)
        assert report["issue_count"] == 0
        assert report["commissioning_assessment"]["G1_boundary_intact"] is True


# ── Test: _render_markdown ───────────────────────────────────────────────────


class TestRenderMarkdown:
    """G8: Markdown rendering produces valid report."""

    def test_contains_header(self):
        cls = {"total_modules": 1, "community_count": 1,
               "proprietary_count": 0, "unclassified_count": 0}
        audit = {"missing_copyright_count": 0, "no_license_count": 0,
                 "license_mismatch_count": 0, "leak_count": 0}
        md = _render_markdown(cls, audit, [])
        assert "Open Source Sweep Report" in md
        assert AGENT_LABEL in md

    def test_issues_in_markdown(self):
        cls = {"total_modules": 1, "community_count": 1,
               "proprietary_count": 0, "unclassified_count": 0}
        audit = {"missing_copyright_count": 1, "no_license_count": 0,
                 "license_mismatch_count": 0, "leak_count": 0}
        issues = [{
            "id": "CR-MISSING-foo", "severity": "MEDIUM",
            "type": "missing_copyright", "module": "foo",
            "detail": "No copyright header", "commissioning": "G8",
        }]
        md = _render_markdown(cls, audit, issues)
        assert "CR-MISSING-foo" in md
        assert "Medium" in md or "MEDIUM" in md or "🟡" in md

    def test_all_clear(self):
        cls = {"total_modules": 1, "community_count": 1,
               "proprietary_count": 0, "unclassified_count": 0}
        audit = {"missing_copyright_count": 0, "no_license_count": 0,
                 "license_mismatch_count": 0, "leak_count": 0}
        md = _render_markdown(cls, audit, [])
        assert "All Clear" in md


# ── Test: run_sweep (Full Orchestration) ─────────────────────────────────────


class TestRunSweep:
    """G1: Full sweep orchestrator works end-to-end."""

    def test_full_sweep(self, tmp_src, tmp_output, monkeypatch):
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", tmp_src)
        report = run_sweep(str(tmp_output))
        assert report["phase"] == "report"
        assert report["classification_summary"]["total"] == 4
        assert (tmp_output / "classification_report.json").exists()
        assert (tmp_output / "audit_report.json").exists()
        assert (tmp_output / "sweep_report_latest.json").exists()

    def test_full_sweep_empty(self, tmp_path, monkeypatch):
        empty_src = tmp_path / "empty_src"
        empty_src.mkdir()
        out = tmp_path / "out"
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", empty_src)
        report = run_sweep(str(out))
        assert report["issue_count"] == 0


# ── Test: Leak Scenario End-to-End ───────────────────────────────────────────


class TestLeakScenario:
    """G3/G9: End-to-end leak detection scenario."""

    def test_leak_flagged_as_critical(self, community_module_with_leak, tmp_output, monkeypatch):
        monkeypatch.setattr("open_source_sweep_agent.MURPHY_SRC", community_module_with_leak)
        report = run_sweep(str(tmp_output))
        critical = [i for i in report["issues"] if i["severity"] == "CRITICAL"]
        assert len(critical) >= 1
        assert report["commissioning_assessment"]["G3_no_leaks"] is False
