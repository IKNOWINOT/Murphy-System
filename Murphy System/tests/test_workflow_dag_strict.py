"""
Test Suite: Workflow DAG Strict Mode — DEFICIENCY-6

Verifies:
  - Unhandled step in default mode succeeds with simulated=True AND logs a warning
  - Unhandled step in strict_mode=True fails
  - list_unhandled_actions() returns the correct set

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from workflow_dag_engine import (  # noqa: E402
    WorkflowDAGEngine,
    WorkflowDefinition,
    StepDefinition,
)


def _make_simple_workflow(action: str = "unregistered_action") -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-test",
        name="Test Workflow",
        steps=[
            StepDefinition(step_id="s1", name="Step 1", action=action),
        ],
    )


# ---------------------------------------------------------------------------
# Default mode — simulation + warning
# ---------------------------------------------------------------------------

class TestDefaultMode:
    def test_unhandled_step_completes_with_simulated(self):
        engine = WorkflowDAGEngine()
        wf = _make_simple_workflow("no_handler_here")
        engine.register_workflow(wf)
        exec_id = engine.create_execution("wf-test")
        result = engine.execute_workflow(exec_id)
        assert result["status"] == "completed"
        assert result["steps"]["s1"]["result"]["simulated"] is True

    def test_unhandled_step_logs_warning(self, caplog):
        engine = WorkflowDAGEngine()
        wf = _make_simple_workflow("missing_action")
        engine.register_workflow(wf)
        exec_id = engine.create_execution("wf-test")
        with caplog.at_level(logging.WARNING):
            engine.execute_workflow(exec_id)
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("missing_action" in m for m in warning_msgs), (
            f"Expected warning about 'missing_action', got: {warning_msgs}"
        )
        assert any("simulation" in m.lower() for m in warning_msgs), (
            f"Expected 'simulation' in warning, got: {warning_msgs}"
        )

    def test_registered_handler_runs_normally(self):
        engine = WorkflowDAGEngine()
        wf = _make_simple_workflow("my_action")
        engine.register_workflow(wf)
        engine.register_step_handler("my_action", lambda step, ctx: {"ok": True})
        exec_id = engine.create_execution("wf-test")
        result = engine.execute_workflow(exec_id)
        assert result["status"] == "completed"
        assert result["steps"]["s1"]["result"] == {"ok": True}
        # Should NOT be simulated
        assert result["steps"]["s1"]["result"].get("simulated") is None


# ---------------------------------------------------------------------------
# Strict mode — unhandled step fails
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_unhandled_step_fails_in_strict_mode(self):
        engine = WorkflowDAGEngine()
        wf = _make_simple_workflow("ghost_action")
        engine.register_workflow(wf)
        exec_id = engine.create_execution("wf-test")
        result = engine.execute_workflow(exec_id, strict_mode=True)
        assert result["status"] == "failed"
        assert result["steps"]["s1"]["status"] == "failed"

    def test_registered_handler_passes_in_strict_mode(self):
        engine = WorkflowDAGEngine()
        wf = _make_simple_workflow("real_action")
        engine.register_workflow(wf)
        engine.register_step_handler("real_action", lambda step, ctx: {"done": True})
        exec_id = engine.create_execution("wf-test")
        result = engine.execute_workflow(exec_id, strict_mode=True)
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# list_unhandled_actions
# ---------------------------------------------------------------------------

class TestListUnhandledActions:
    def test_returns_unhandled_actions(self):
        engine = WorkflowDAGEngine()
        wf = WorkflowDefinition(
            workflow_id="wf-mixed",
            name="Mixed Workflow",
            steps=[
                StepDefinition(step_id="s1", name="Step 1", action="handled_action"),
                StepDefinition(step_id="s2", name="Step 2", action="missing_action"),
                StepDefinition(step_id="s3", name="Step 3", action="another_missing"),
            ],
        )
        engine.register_workflow(wf)
        engine.register_step_handler("handled_action", lambda s, c: {})
        unhandled = engine.list_unhandled_actions()
        assert "missing_action" in unhandled
        assert "another_missing" in unhandled
        assert "handled_action" not in unhandled

    def test_empty_when_all_handled(self):
        engine = WorkflowDAGEngine()
        wf = WorkflowDefinition(
            workflow_id="wf-full",
            name="Fully Handled",
            steps=[
                StepDefinition(step_id="s1", name="Step 1", action="act_a"),
            ],
        )
        engine.register_workflow(wf)
        engine.register_step_handler("act_a", lambda s, c: {})
        assert engine.list_unhandled_actions() == []

    def test_returns_sorted_list(self):
        engine = WorkflowDAGEngine()
        wf = WorkflowDefinition(
            workflow_id="wf-sort",
            name="Sort Test",
            steps=[
                StepDefinition(step_id="s1", name="S1", action="zzz_action"),
                StepDefinition(step_id="s2", name="S2", action="aaa_action"),
            ],
        )
        engine.register_workflow(wf)
        result = engine.list_unhandled_actions()
        assert result == sorted(result)
