#!/usr/bin/env python3
# Copyright (C) 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Dependency Deprecation Agent (DEPRECATION-AGENT-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the four phases: diagnose, plan, fix, harden
#   G3: Covers all conditions: clean repo, deprecated repo, empty inputs
#   G4: Full range of fix types and edge cases
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Dependency Deprecation Agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure Murphy System/scripts is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dependency_deprecation_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    phase_diagnose,
    phase_fix,
    phase_harden,
    phase_plan,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_DEPRECATED_WORKFLOW = """\
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

SAMPLE_CLEAN_WORKFLOW = """\
name: CI
on: push
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""


@pytest.fixture
def tmp_output(tmp_path):
    """Provide a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def repo_with_deprecated(tmp_path):
    """Create a repo structure with deprecated workflows."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(SAMPLE_DEPRECATED_WORKFLOW)
    ms = tmp_path / "Murphy System" / "docs"
    ms.mkdir(parents=True)
    (tmp_path / "Murphy System" / "src").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def repo_clean(tmp_path):
    """Create a repo structure with no deprecated workflows."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(SAMPLE_CLEAN_WORKFLOW)
    ms = tmp_path / "Murphy System" / "docs"
    ms.mkdir(parents=True)
    (tmp_path / "Murphy System" / "src").mkdir(parents=True)
    return tmp_path


# ── Test: Diagnose Phase ─────────────────────────────────────────────────────

class TestDiagnosePhase:
    """G2: Tests the diagnose phase of the agent."""

    def test_diagnose_finds_deprecations(self, repo_with_deprecated, tmp_output):
        """G1: Diagnose detects deprecated actions."""
        result = phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        assert result["needs_action"] is True
        assert result["total_findings"] >= 2
        assert result["agent_version"] == AGENT_VERSION

    def test_diagnose_clean_repo(self, repo_clean, tmp_output):
        """G3: Clean repo produces needs_action=False."""
        result = phase_diagnose(str(repo_clean), str(tmp_output))
        assert result["needs_action"] is False
        assert result["total_findings"] == 0

    def test_diagnose_writes_report_file(self, repo_with_deprecated, tmp_output):
        """G5: Diagnose writes JSON report to output directory."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        report_file = tmp_output / "deprecation_diagnosis.json"
        assert report_file.exists()
        data = json.loads(report_file.read_text())
        assert "findings" in data
        assert "commissioning" in data

    def test_diagnose_with_ci_log(self, repo_clean, tmp_output, tmp_path):
        """G3: Diagnose incorporates CI log findings."""
        log_file = tmp_path / "ci.log"
        log_file.write_text("Node.js 20 actions are deprecated\n")
        result = phase_diagnose(
            str(repo_clean), str(tmp_output), ci_log_path=str(log_file)
        )
        assert result["total_findings"] >= 1

    def test_diagnose_missing_ci_log(self, repo_clean, tmp_output):
        """G3: Missing CI log file does not crash."""
        result = phase_diagnose(
            str(repo_clean), str(tmp_output),
            ci_log_path="/tmp/nonexistent_log.txt"
        )
        assert isinstance(result, dict)


# ── Test: Plan Phase ──────────────────────────────────────────────────────────

class TestPlanPhase:
    """G2: Tests the plan phase of the agent."""

    def test_plan_generates_steps(self, repo_with_deprecated, tmp_output):
        """G1: Plan generates fix steps from diagnosis."""
        diagnosis = phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        diag_path = tmp_output / "deprecation_diagnosis.json"
        plan = phase_plan(str(diag_path), str(tmp_output))
        assert plan["needs_action"] is True
        assert plan["total_steps"] >= 1

    def test_plan_no_action_for_clean(self, repo_clean, tmp_output):
        """G3: Clean diagnosis produces no-action plan."""
        phase_diagnose(str(repo_clean), str(tmp_output))
        diag_path = tmp_output / "deprecation_diagnosis.json"
        plan = phase_plan(str(diag_path), str(tmp_output))
        assert plan["needs_action"] is False
        assert plan["total_steps"] == 0

    def test_plan_writes_file(self, repo_with_deprecated, tmp_output):
        """G5: Plan writes JSON file to output directory."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        diag_path = tmp_output / "deprecation_diagnosis.json"
        phase_plan(str(diag_path), str(tmp_output))
        plan_file = tmp_output / "deprecation_fix_plan.json"
        assert plan_file.exists()

    def test_plan_includes_validation_step(self, repo_with_deprecated, tmp_output):
        """G4: Plan includes YAML validation step."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        plan = phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        actions = [s["action"] for s in plan["steps"]]
        assert "validate_yaml_syntax" in actions

    def test_plan_from_missing_file(self, tmp_output):
        """G3: Missing diagnosis file returns empty plan."""
        plan = phase_plan("/tmp/nonexistent.json", str(tmp_output))
        assert plan["needs_action"] is False


# ── Test: Fix Phase ───────────────────────────────────────────────────────────

class TestFixPhase:
    """G2: Tests the fix phase of the agent."""

    def test_fix_updates_workflow_files(self, repo_with_deprecated, tmp_output):
        """G1: Fix replaces deprecated action versions in files."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        result = phase_fix(
            str(tmp_output / "deprecation_fix_plan.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        assert result is True
        # Verify file was actually changed
        ci_yml = repo_with_deprecated / ".github" / "workflows" / "ci.yml"
        content = ci_yml.read_text()
        assert "actions/checkout@v3" not in content
        assert "actions/upload-artifact@v3" not in content

    def test_fix_no_action_plan(self, repo_clean, tmp_output):
        """G3: No-action plan produces no file changes."""
        phase_diagnose(str(repo_clean), str(tmp_output))
        phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        result = phase_fix(
            str(tmp_output / "deprecation_fix_plan.json"),
            str(repo_clean),
            str(tmp_output),
        )
        assert result is False

    def test_fix_writes_result_file(self, repo_with_deprecated, tmp_output):
        """G5: Fix writes result JSON and summary text."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        phase_fix(
            str(tmp_output / "deprecation_fix_plan.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        assert (tmp_output / "deprecation_fix_result.json").exists()
        assert (tmp_output / "fix_summary.txt").exists()


# ── Test: Harden Phase ───────────────────────────────────────────────────────

class TestHardenPhase:
    """G2: Tests the harden phase of the agent."""

    def test_harden_creates_deprecation_log(self, repo_with_deprecated, tmp_output):
        """G8: Harden creates/updates deprecation_log.md."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        phase_harden(
            str(tmp_output / "deprecation_diagnosis.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        log_path = repo_with_deprecated / "Murphy System" / "docs" / "deprecation_log.md"
        assert log_path.exists()
        content = log_path.read_text()
        assert "Deprecation Scan" in content
        assert "G1:" in content

    def test_harden_writes_hardening_report(self, repo_with_deprecated, tmp_output):
        """G9: Harden writes hardening report."""
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        phase_harden(
            str(tmp_output / "deprecation_diagnosis.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        report_file = tmp_output / "deprecation_hardening_report.json"
        assert report_file.exists()
        data = json.loads(report_file.read_text())
        assert "checks" in data
        assert len(data["checks"]) >= 3

    def test_harden_appends_to_existing_log(self, repo_with_deprecated, tmp_output):
        """G8: Harden appends to existing deprecation log."""
        log_path = repo_with_deprecated / "Murphy System" / "docs" / "deprecation_log.md"
        log_path.write_text("# Existing log\n---\n")
        phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        phase_harden(
            str(tmp_output / "deprecation_diagnosis.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        content = log_path.read_text()
        assert "# Existing log" in content
        assert "Deprecation Scan" in content


# ── Test: End-to-End Pipeline ─────────────────────────────────────────────────

class TestEndToEnd:
    """G7: Full pipeline from diagnose through harden."""

    def test_full_pipeline_deprecated_repo(self, repo_with_deprecated, tmp_output):
        """G1: Full pipeline diagnoses, plans, fixes, and hardens."""
        # Phase 1
        diagnosis = phase_diagnose(str(repo_with_deprecated), str(tmp_output))
        assert diagnosis["needs_action"] is True

        # Phase 2
        plan = phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        assert plan["needs_action"] is True

        # Phase 3
        fixed = phase_fix(
            str(tmp_output / "deprecation_fix_plan.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        assert fixed is True

        # Phase 4
        phase_harden(
            str(tmp_output / "deprecation_diagnosis.json"),
            str(repo_with_deprecated),
            str(tmp_output),
        )
        assert (tmp_output / "deprecation_hardening_report.json").exists()

    def test_full_pipeline_clean_repo(self, repo_clean, tmp_output):
        """G3: Full pipeline on clean repo does nothing."""
        diagnosis = phase_diagnose(str(repo_clean), str(tmp_output))
        assert diagnosis["needs_action"] is False

        plan = phase_plan(
            str(tmp_output / "deprecation_diagnosis.json"), str(tmp_output)
        )
        assert plan["needs_action"] is False

        fixed = phase_fix(
            str(tmp_output / "deprecation_fix_plan.json"),
            str(repo_clean),
            str(tmp_output),
        )
        assert fixed is False
