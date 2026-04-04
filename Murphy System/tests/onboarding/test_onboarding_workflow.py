# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for create_onboarding_workflow: DAG validity, step count, topological sort."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG
from src.platform_onboarding.workflow_definition import create_onboarding_workflow
from src.workflow_dag_engine import WorkflowDefinition, WorkflowDAGEngine


def test_returns_workflow_definition():
    wf = create_onboarding_workflow()
    assert isinstance(wf, WorkflowDefinition)


def test_workflow_has_correct_step_count():
    wf = create_onboarding_workflow()
    assert len(wf.steps) == len(TASK_CATALOG)


def test_workflow_id():
    wf = create_onboarding_workflow()
    assert wf.workflow_id == "murphy_platform_onboarding_v1"


def test_dag_has_no_cycles():
    wf = create_onboarding_workflow()
    engine = WorkflowDAGEngine()
    assert engine._validate_dag(wf), "DAG validation failed (cycle detected)"


def test_dag_registers_successfully():
    wf = create_onboarding_workflow()
    engine = WorkflowDAGEngine()
    result = engine.register_workflow(wf)
    assert result is True


def test_topological_sort_works():
    wf = create_onboarding_workflow()
    engine = WorkflowDAGEngine()
    engine.register_workflow(wf)
    order = engine._topological_sort(wf)
    assert order is not None
    assert len(order) == len(TASK_CATALOG)


def test_topological_sort_respects_dependencies():
    wf = create_onboarding_workflow()
    engine = WorkflowDAGEngine()
    engine.register_workflow(wf)
    order = engine._topological_sort(wf)
    position = {step_id: i for i, step_id in enumerate(order)}

    # 1.02 (EIN) must come before 1.01 (SAM.gov)
    assert position["1.02"] < position["1.01"]

    # 1.01 must come before 1.03 (Grants.gov)
    assert position["1.01"] < position["1.03"]

    # [1.01, 1.03, 1.05] must all come before 2.01 (SBIR Phase I)
    assert position["1.01"] < position["2.01"]
    assert position["1.03"] < position["2.01"]
    assert position["1.05"] < position["2.01"]


def test_step_metadata_contains_url():
    wf = create_onboarding_workflow()
    for step in wf.steps:
        assert "url" in step.metadata, f"{step.step_id}: missing 'url' in metadata"
        assert step.metadata["url"].startswith("https://")


def test_conditional_steps_have_condition():
    from src.platform_onboarding.task_catalog import TASK_CATALOG
    # Only tasks that are conditional AND have an explicit condition string
    conditional_tasks_with_cond = {
        t.task_id for t in TASK_CATALOG if t.is_conditional and t.condition
    }
    wf = create_onboarding_workflow()
    step_map = {s.step_id: s for s in wf.steps}
    for tid in conditional_tasks_with_cond:
        step = step_map[tid]
        assert step.condition is not None, f"{tid}: conditional step missing condition"
