#!/usr/bin/env python3
# Copyright (C) 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Production Readiness Executor Agent (READINESS-EXECUTOR-001)
#
# Commissioning profile:
#   G1: Validates each action handler produces correct outputs
#   G2: Tests the load/plan/execute/report pipeline
#   G3: Covers empty checklists, dry-run, unknown actions
#   G4: Full range of action types and edge cases
#   G5: Expected: structured execution report with per-task results
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Production Readiness Executor Agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from production_readiness_executor_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    ACTION_HANDLERS,
    action_catalog_debt,
    action_create_test_stub,
    action_fix_bare_excepts,
    action_fix_import,
    action_sync_source_parity,
    action_update_env_example,
    build_execution_plan,
    execute_plan,
    generate_execution_report,
    load_checklist,
    run_executor,
)


# -- Fixtures ----------------------------------------------------------------

@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def sample_checklist(tmp_path):
    """Create a sample scanner checklist JSON."""
    checklist = {
        "agent_version": "1.0.0",
        "agent_label": "READINESS-SCANNER-001",
        "scan_date": "2026-04-02",
        "scan_timestamp": "2026-04-02T09:00:00+00:00",
        "summary": {"total_human_tasks": 1, "total_agent_tasks": 2},
        "human_tasks": [
            {"id": "H-1", "title": "Human task", "category": "security",
             "description": "Review secrets", "priority": "CRITICAL"}
        ],
        "agent_tasks": [
            {"id": "PARITY-001", "category": "source_parity", "priority": "HIGH",
             "title": "Fix parity", "description": "Sync files",
             "commissioning": "G8", "action": "sync_source_parity", "details": {}},
            {"id": "DEBT-INVENTORY", "category": "technical_debt", "priority": "LOW",
             "title": "Catalog debt", "description": "Generate report",
             "commissioning": "G7", "action": "catalog_debt",
             "details": {"total": 50, "by_type": {"TODO": 30, "FIXME": 20}}},
        ],
    }
    path = tmp_path / "checklist.json"
    path.write_text(json.dumps(checklist, indent=2))
    return path


@pytest.fixture
def empty_checklist(tmp_path):
    checklist = {
        "agent_version": "1.0.0",
        "scan_date": "2026-04-02",
        "summary": {"total_human_tasks": 0, "total_agent_tasks": 0},
        "human_tasks": [],
        "agent_tasks": [],
    }
    path = tmp_path / "empty_checklist.json"
    path.write_text(json.dumps(checklist, indent=2))
    return path


# -- Test: Load Checklist -----------------------------------------------------

class TestLoadChecklist:
    def test_load_valid(self, sample_checklist):
        data = load_checklist(str(sample_checklist))
        assert data["scan_date"] == "2026-04-02"
        assert len(data["agent_tasks"]) == 2

    def test_load_missing_file(self, tmp_path):
        data = load_checklist(str(tmp_path / "nonexistent.json"))
        assert data == {}

    def test_load_corrupt_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        data = load_checklist(str(bad))
        assert data == {}


# -- Test: Build Execution Plan -----------------------------------------------

class TestBuildExecutionPlan:
    def test_plan_orders_by_priority(self, sample_checklist):
        data = load_checklist(str(sample_checklist))
        plan = build_execution_plan(data)
        assert len(plan) == 2
        assert plan[0]["priority"] == "HIGH"
        assert plan[1]["priority"] == "LOW"

    def test_plan_empty_tasks(self, empty_checklist):
        data = load_checklist(str(empty_checklist))
        plan = build_execution_plan(data)
        assert plan == []


# -- Test: Action Handlers ----------------------------------------------------

class TestActionSyncSourceParity:
    def test_dry_run(self):
        result = action_sync_source_parity({}, dry_run=True)
        assert result["status"] == "skipped"

    def test_missing_script(self, monkeypatch, tmp_path):
        monkeypatch.setattr("production_readiness_executor_agent.ROOT_SCRIPTS", tmp_path / "nope")
        result = action_sync_source_parity({}, dry_run=False)
        assert result["status"] == "failed"


class TestActionCreateTestStub:
    def test_dry_run(self):
        task = {"details": {"module": "foo"}}
        result = action_create_test_stub(task, dry_run=True)
        assert result["status"] == "skipped"

    def test_no_module_name(self):
        result = action_create_test_stub({"details": {}})
        assert result["status"] == "failed"

    def test_creates_file(self, monkeypatch, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "widget.py").write_text("class Widget: pass\n")
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_TESTS", tests_dir)
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_SRC", src_dir)
        task = {"details": {"module": "widget"}}
        result = action_create_test_stub(task, dry_run=False)
        assert result["status"] == "success"
        assert (tests_dir / "test_widget.py").exists()

    def test_skips_existing(self, monkeypatch, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_existing.py").write_text("pass\n")
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_TESTS", tests_dir)
        task = {"details": {"module": "existing"}}
        result = action_create_test_stub(task, dry_run=False)
        assert result["status"] == "skipped"


class TestActionFixImport:
    def test_dry_run(self):
        result = action_fix_import({"details": {"module": "x"}}, dry_run=True)
        assert result["status"] == "skipped"

    def test_no_module(self):
        result = action_fix_import({"details": {}})
        assert result["status"] == "failed"

    def test_missing_from_both(self, monkeypatch, tmp_path):
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_SRC", tmp_path / "m")
        monkeypatch.setattr("production_readiness_executor_agent.ROOT_SRC", tmp_path / "r")
        (tmp_path / "m").mkdir()
        (tmp_path / "r").mkdir()
        result = action_fix_import({"details": {"module": "ghost"}})
        assert result["status"] == "needs_review"


class TestActionCatalogDebt:
    def test_dry_run(self):
        result = action_catalog_debt({"details": {"total": 10, "by_type": {}}}, dry_run=True)
        assert result["status"] == "skipped"

    def test_creates_report(self, monkeypatch, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_DOCS", docs)
        task = {"details": {"total": 42, "by_type": {"TODO": 30, "FIXME": 12}}}
        result = action_catalog_debt(task)
        assert result["status"] == "success"
        assert (docs / "debt_catalog.md").exists()


class TestActionUpdateEnvExample:
    def test_dry_run(self):
        result = action_update_env_example({"details": {"missing_vars": ["X"]}}, dry_run=True)
        assert result["status"] == "skipped"

    def test_missing_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_SYSTEM", tmp_path)
        result = action_update_env_example({"details": {"missing_vars": ["X"]}})
        assert result["status"] == "failed"


# -- Test: Execute Plan -------------------------------------------------------

class TestExecutePlan:
    def test_execute_with_dry_run(self):
        plan = [{"step": 1, "task_id": "T-1", "action": "sync_source_parity",
                 "priority": "HIGH", "title": "Sync", "description": "d",
                 "commissioning": "G8", "details": {}, "status": "pending"}]
        results = execute_plan(plan, dry_run=True)
        assert len(results) == 1
        assert results[0]["result"]["status"] == "skipped"

    def test_unknown_action(self):
        plan = [{"step": 1, "task_id": "T-1", "action": "unknown_action",
                 "priority": "LOW", "title": "Unknown", "description": "d",
                 "commissioning": "G1", "details": {}, "status": "pending"}]
        results = execute_plan(plan)
        assert results[0]["result"]["status"] == "skipped"


# -- Test: Report Generation --------------------------------------------------

class TestGenerateExecutionReport:
    def test_report_structure(self, tmp_output):
        checklist = {"scan_date": "2026-04-02"}
        results = [
            {"step": 1, "task_id": "T-1", "action": "sync_source_parity",
             "priority": "HIGH", "title": "Sync", "description": "d",
             "commissioning": "G8", "details": {}, "status": "done",
             "result": {"status": "success", "detail": "ok"},
             "executed_at": "2026-04-02T11:00:00+00:00"},
        ]
        report = generate_execution_report(checklist, [], results, str(tmp_output))
        assert report["agent_version"] == AGENT_VERSION
        assert report["summary"]["succeeded"] == 1
        assert report["summary"]["total_tasks"] == 1
        json_files = list(tmp_output.glob("execution_report_*.json"))
        assert len(json_files) >= 1
        md_files = list(tmp_output.glob("execution_report_*.md"))
        assert len(md_files) >= 1


# -- Test: Full Pipeline (integration) ----------------------------------------

class TestRunExecutor:
    def test_dry_run_pipeline(self, sample_checklist, tmp_output, monkeypatch):
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_DOCS",
                            tmp_output.parent / "docs")
        (tmp_output.parent / "docs").mkdir(exist_ok=True)
        report = run_executor(str(sample_checklist), str(tmp_output), dry_run=True)
        assert report["summary"]["total_tasks"] == 2
        assert report["summary"]["skipped"] == 2

    def test_empty_checklist_pipeline(self, empty_checklist, tmp_output, monkeypatch):
        monkeypatch.setattr("production_readiness_executor_agent.MURPHY_DOCS",
                            tmp_output.parent / "docs")
        (tmp_output.parent / "docs").mkdir(exist_ok=True)
        report = run_executor(str(empty_checklist), str(tmp_output))
        assert report["summary"]["total_tasks"] == 0

    def test_missing_checklist(self, tmp_output):
        report = run_executor("/tmp/nonexistent_checklist.json", str(tmp_output))
        assert "error" in report
