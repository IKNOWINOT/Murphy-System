#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Deploy Recovery Agent (RECOVERY-AGENT-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the four phases: diagnose, plan, fix, harden
#   G3: Covers all root-cause categories and edge cases
#   G4: Full range of error patterns and empty/corrupt inputs
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Deploy Recovery Agent."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure Murphy System/scripts is importable

from deploy_recovery_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    CATEGORY_DEPENDENCY,
    CATEGORY_DEPLOY_SCRIPT,
    CATEGORY_DEPLOY_SSH,
    CATEGORY_IMPORT_ERROR,
    CATEGORY_SOURCE_DRIFT,
    CATEGORY_SYNTAX_ERROR,
    CATEGORY_TEST_FAILURE,
    CATEGORY_TIMEOUT,
    CATEGORY_UNKNOWN,
    _extract_context,
    phase_diagnose,
    phase_fix,
    phase_harden,
    phase_plan,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    """Provide a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_logs(tmp_path):
    """Provide a temporary logs directory."""
    logs = tmp_path / "logs"
    logs.mkdir()
    return logs


@pytest.fixture
def sample_diagnosis(tmp_output):
    """Create a sample diagnosis report."""
    report = {
        "agent_version": AGENT_VERSION,
        "agent_label": AGENT_LABEL,
        "run_id": "12345",
        "head_sha": "abc1234",
        "root_cause_category": CATEGORY_IMPORT_ERROR,
        "summary": "import_error: 1 occurrence(s)",
        "unique_issues": ["Missing Python module import"],
        "failed_jobs": [],
        "evidence_count": 1,
        "evidence": [
            {
                "pattern": r"ModuleNotFoundError.*",
                "category": CATEGORY_IMPORT_ERROR,
                "description": "Missing Python module import",
                "matched_text": "ModuleNotFoundError: No module named 'foo_module'",
                "context": "line before\nModuleNotFoundError: No module named 'foo_module'\nline after",
            }
        ],
        "commissioning": {
            "G1_does_it_work": False,
            "G2_intended_purpose": "Deploy Murphy System",
            "G3_possible_conditions": [CATEGORY_IMPORT_ERROR],
            "G5_expected_result": "Successful deploy",
            "G6_actual_result": "Failure — import_error",
        },
    }
    path = tmp_output / "diagnosis_report.json"
    path.write_text(json.dumps(report, indent=2))
    return path


# ── Phase: Diagnose ──────────────────────────────────────────────────────────


class TestPhaseDiagnose:
    """G1: Diagnose phase produces structured diagnosis from logs."""

    def test_diagnose_import_error(self, tmp_logs, tmp_output):
        """G3: Detects ModuleNotFoundError in logs."""
        (tmp_logs / "run_failed.log").write_text(
            "Step 5/8\nModuleNotFoundError: No module named 'missing_pkg'\nFailed"
        )
        report = phase_diagnose(str(tmp_logs), "99999", "deadbeef", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_IMPORT_ERROR
        assert report["run_id"] == "99999"
        assert report["head_sha"] == "deadbeef"
        assert report["evidence_count"] >= 1
        assert (tmp_output / "diagnosis_report.json").exists()

    def test_diagnose_test_failure(self, tmp_logs, tmp_output):
        """G3: Detects pytest FAILED lines."""
        (tmp_logs / "job_123.log").write_text(
            "FAILED tests/test_foo.py::test_bar - AssertionError\n"
            "ERROR tests/test_baz.py::test_qux\n"
        )
        report = phase_diagnose(str(tmp_logs), "10001", "cafe1234", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_TEST_FAILURE
        assert report["evidence_count"] >= 1

    def test_diagnose_dependency_timeout(self, tmp_logs, tmp_output):
        """G3: Detects pip install timeout."""
        (tmp_logs / "run_failed.log").write_text(
            "pip install -r requirements.txt timed out\n"
        )
        report = phase_diagnose(str(tmp_logs), "10002", "babe5678", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_DEPENDENCY

    def test_diagnose_syntax_error(self, tmp_logs, tmp_output):
        """G3: Detects SyntaxError."""
        (tmp_logs / "run_failed.log").write_text(
            'File "src/foo.py", line 42\n'
            "SyntaxError: unexpected indent\n"
        )
        report = phase_diagnose(str(tmp_logs), "10003", "1234abcd", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_SYNTAX_ERROR

    def test_diagnose_ssh_failure(self, tmp_logs, tmp_output):
        """G3: Detects SSH connection failure."""
        (tmp_logs / "run_failed.log").write_text(
            "ssh: connect to host 1.2.3.4 port 22: Connection refused\n"
        )
        report = phase_diagnose(str(tmp_logs), "10004", "ffff0000", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_DEPLOY_SSH

    def test_diagnose_source_drift(self, tmp_logs, tmp_output):
        """G3: Detects source drift / tree divergence."""
        (tmp_logs / "run_failed.log").write_text(
            "tree-divergence-check FAILED: files diverge between src/ and Murphy System/src/\n"
        )
        report = phase_diagnose(str(tmp_logs), "10005", "aaaa1111", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_SOURCE_DRIFT

    def test_diagnose_deploy_script_failure(self, tmp_logs, tmp_output):
        """G3: Detects systemd service failure."""
        (tmp_logs / "run_failed.log").write_text(
            "systemctl restart murphy-production\n"
            "systemctl status: inactive (dead)\n"
            "Health check failed after rollback\n"
        )
        report = phase_diagnose(str(tmp_logs), "10006", "bbbb2222", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_DEPLOY_SCRIPT

    def test_diagnose_empty_logs(self, tmp_logs, tmp_output):
        """G3: Handles empty log directory gracefully."""
        report = phase_diagnose(str(tmp_logs), "10007", "cccc3333", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_UNKNOWN
        assert report["evidence_count"] == 0

    def test_diagnose_corrupt_json_metadata(self, tmp_logs, tmp_output):
        """G3: Handles malformed failed_jobs.json."""
        (tmp_logs / "failed_jobs.json").write_text("NOT VALID JSON {{{\n")
        report = phase_diagnose(str(tmp_logs), "10008", "dddd4444", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_UNKNOWN
        assert report["failed_jobs"] == []

    def test_diagnose_multiple_categories(self, tmp_logs, tmp_output):
        """G3: When multiple error types present, most frequent wins."""
        (tmp_logs / "run_failed.log").write_text(
            "ModuleNotFoundError: No module named 'a'\n"
            "ModuleNotFoundError: No module named 'b'\n"
            "ModuleNotFoundError: No module named 'c'\n"
            "SyntaxError: invalid syntax\n"
        )
        report = phase_diagnose(str(tmp_logs), "10009", "eeee5555", str(tmp_output))

        # Import error appears 3 times vs syntax 1 time
        assert report["root_cause_category"] == CATEGORY_IMPORT_ERROR

    def test_diagnose_report_has_commissioning_fields(self, tmp_logs, tmp_output):
        """G9: Report includes commissioning metadata."""
        (tmp_logs / "run_failed.log").write_text("some error\n")
        report = phase_diagnose(str(tmp_logs), "99", "aaa", str(tmp_output))

        assert "commissioning" in report
        assert "G1_does_it_work" in report["commissioning"]
        assert "G5_expected_result" in report["commissioning"]

    def test_diagnose_timeout_pattern(self, tmp_logs, tmp_output):
        """G3: Detects generic timeout."""
        (tmp_logs / "run_failed.log").write_text(
            "Operation timed out after 300 seconds\n"
        )
        report = phase_diagnose(str(tmp_logs), "10010", "ff001122", str(tmp_output))

        assert report["root_cause_category"] == CATEGORY_TIMEOUT


# ── Phase: Plan ───────────────────────────────────────────────────────────────


class TestPhasePlan:
    """G1: Plan phase generates structured fix plans."""

    def test_plan_import_error(self, sample_diagnosis, tmp_output):
        """G3: Import error diagnosis → import fix + sync steps."""
        plan = phase_plan(str(sample_diagnosis), str(tmp_output))

        assert plan["root_cause_category"] == CATEGORY_IMPORT_ERROR
        assert plan["total_steps"] >= 3  # fix import + sync + test + docs
        actions = [s["action"] for s in plan["steps"]]
        assert "check_and_fix_import" in actions
        assert "sync_tree" in actions

    def test_plan_dependency_error(self, tmp_output):
        """G3: Dependency diagnosis → requirements check step."""
        diag = tmp_output / "diag.json"
        diag.write_text(json.dumps({
            "root_cause_category": CATEGORY_DEPENDENCY,
            "evidence": [{
                "matched_text": "Could not find a version that satisfies the requirement foo==9.9.9"
            }],
        }))
        plan = phase_plan(str(diag), str(tmp_output))

        actions = [s["action"] for s in plan["steps"]]
        assert "check_requirements" in actions

    def test_plan_source_drift(self, tmp_output):
        """G3: Source drift diagnosis → sync step."""
        diag = tmp_output / "diag.json"
        diag.write_text(json.dumps({
            "root_cause_category": CATEGORY_SOURCE_DRIFT,
            "evidence": [],
        }))
        plan = phase_plan(str(diag), str(tmp_output))

        actions = [s["action"] for s in plan["steps"]]
        assert "sync_canonical_source" in actions

    def test_plan_ssh_failure(self, tmp_output):
        """G3: SSH failure → manual action documented."""
        diag = tmp_output / "diag.json"
        diag.write_text(json.dumps({
            "root_cause_category": CATEGORY_DEPLOY_SSH,
            "evidence": [],
        }))
        plan = phase_plan(str(diag), str(tmp_output))

        manual_steps = [s for s in plan["steps"] if s.get("manual")]
        assert len(manual_steps) >= 1

    def test_plan_unknown_still_has_validation(self, tmp_output):
        """G4: Even unknown category includes test + doc steps."""
        diag = tmp_output / "diag.json"
        diag.write_text(json.dumps({
            "root_cause_category": CATEGORY_UNKNOWN,
            "evidence": [],
        }))
        plan = phase_plan(str(diag), str(tmp_output))

        actions = [s["action"] for s in plan["steps"]]
        assert "run_local_tests" in actions
        assert "update_documentation" in actions

    def test_plan_includes_commissioning(self, sample_diagnosis, tmp_output):
        """G9: Plan includes commissioning metadata."""
        plan = phase_plan(str(sample_diagnosis), str(tmp_output))

        assert "commissioning" in plan
        assert "G4_test_coverage" in plan["commissioning"]
        assert "G8_documentation" in plan["commissioning"]

    def test_plan_file_written(self, sample_diagnosis, tmp_output):
        """G5: Plan is written to fix_plan.json."""
        phase_plan(str(sample_diagnosis), str(tmp_output))
        assert (tmp_output / "fix_plan.json").exists()

    def test_plan_missing_diagnosis(self, tmp_output):
        """G3: Handles missing diagnosis file gracefully."""
        plan = phase_plan("/nonexistent/path.json", str(tmp_output))
        assert plan["root_cause_category"] == CATEGORY_UNKNOWN


# ── Phase: Fix ────────────────────────────────────────────────────────────────


class TestPhaseFix:
    """G1: Fix phase executes plan steps safely."""

    def test_fix_writes_summary(self, tmp_output):
        """G5: Fix always writes a summary file."""
        plan = {
            "steps": [
                {"action": "run_local_tests", "description": "Test"},
            ],
        }
        plan_path = tmp_output / "fix_plan.json"
        plan_path.write_text(json.dumps(plan))

        phase_fix(str(plan_path), str(tmp_output))
        assert (tmp_output / "fix_summary.txt").exists()
        assert (tmp_output / "fix_result.json").exists()

    def test_fix_empty_plan(self, tmp_output):
        """G3: Empty plan → no fixes applied."""
        plan_path = tmp_output / "fix_plan.json"
        plan_path.write_text(json.dumps({"steps": []}))

        result = phase_fix(str(plan_path), str(tmp_output))
        assert result is False

    def test_fix_unknown_action(self, tmp_output):
        """G3: Unknown actions are logged but don't crash."""
        plan_path = tmp_output / "fix_plan.json"
        plan_path.write_text(json.dumps({
            "steps": [{"action": "teleport_to_mars", "description": "Impossible fix"}],
        }))

        result = phase_fix(str(plan_path), str(tmp_output))
        assert result is False

    def test_fix_missing_plan_file(self, tmp_output):
        """G3: Missing plan file handled gracefully."""
        result = phase_fix("/nonexistent/plan.json", str(tmp_output))
        assert result is False

    def test_fix_result_has_commissioning(self, tmp_output):
        """G9: Fix result includes commissioning fields."""
        plan_path = tmp_output / "fix_plan.json"
        plan_path.write_text(json.dumps({"steps": []}))
        phase_fix(str(plan_path), str(tmp_output))

        result = json.loads((tmp_output / "fix_result.json").read_text())
        assert "commissioning" in result
        assert "G6_actual_result" in result["commissioning"]


# ── Phase: Harden ─────────────────────────────────────────────────────────────


class TestPhaseHarden:
    """G1: Harden phase updates docs and checks production readiness."""

    def test_harden_creates_recovery_log(self, sample_diagnosis, tmp_output):
        """G8: Recovery log is created/updated."""
        # Patch MURPHY_SYSTEM to use tmp dir
        with patch("deploy_recovery_agent.MURPHY_SYSTEM", tmp_output / "murphy"):
            with patch("deploy_recovery_agent.ROOT_SCRIPTS", tmp_output / "scripts"):
                (tmp_output / "murphy" / "docs").mkdir(parents=True)
                phase_harden(str(sample_diagnosis), str(tmp_output))

                log_path = tmp_output / "murphy" / "docs" / "recovery_log.md"
                assert log_path.exists()
                content = log_path.read_text()
                assert "Recovery Entry" in content
                assert "12345" in content  # run_id from sample diagnosis

    def test_harden_appends_to_existing_log(self, sample_diagnosis, tmp_output):
        """G8: Multiple recoveries append to same log."""
        with patch("deploy_recovery_agent.MURPHY_SYSTEM", tmp_output / "murphy"):
            with patch("deploy_recovery_agent.ROOT_SCRIPTS", tmp_output / "scripts"):
                docs_dir = tmp_output / "murphy" / "docs"
                docs_dir.mkdir(parents=True)
                (docs_dir / "recovery_log.md").write_text("# Existing Log\n\n---\n")

                phase_harden(str(sample_diagnosis), str(tmp_output))

                content = (docs_dir / "recovery_log.md").read_text()
                assert "Existing Log" in content
                assert "Recovery Entry" in content

    def test_harden_writes_hardening_report(self, sample_diagnosis, tmp_output):
        """G9: Hardening report is generated."""
        with patch("deploy_recovery_agent.MURPHY_SYSTEM", tmp_output / "murphy"):
            with patch("deploy_recovery_agent.ROOT_SCRIPTS", tmp_output / "scripts"):
                (tmp_output / "murphy" / "docs").mkdir(parents=True)
                phase_harden(str(sample_diagnosis), str(tmp_output))

                report_path = tmp_output / "hardening_report.json"
                assert report_path.exists()
                report = json.loads(report_path.read_text())
                assert "checks" in report
                assert len(report["checks"]) > 0


# ── Helper functions ──────────────────────────────────────────────────────────


class TestHelpers:
    """G1: Helper functions work correctly."""

    def test_extract_context_middle(self):
        """G5: Context extraction returns surrounding lines."""
        text = "line0\nline1\nline2\nTARGET\nline4\nline5\nline6"
        # Position of "TARGET" in text
        pos = text.index("TARGET")
        ctx = _extract_context(text, pos, radius=1)
        assert "TARGET" in ctx
        assert "line2" in ctx  # 1 line before
        assert "line4" in ctx  # 1 line after

    def test_extract_context_beginning(self):
        """G3: Context extraction at beginning of text."""
        text = "FIRST\nsecond\nthird"
        ctx = _extract_context(text, 0, radius=2)
        assert "FIRST" in ctx

    def test_extract_context_empty(self):
        """G3: Context extraction on empty text."""
        ctx = _extract_context("", 0, radius=2)
        assert ctx == ""
