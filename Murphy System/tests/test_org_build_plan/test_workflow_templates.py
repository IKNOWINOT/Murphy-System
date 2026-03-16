# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.workflow_templates module."""
import os


import pytest
from src.org_build_plan.workflow_templates import WorkflowTemplate, WorkflowTemplateLibrary


def test_templates_for_manufacturing():
    """Manufacturing industry returns at least 3 templates."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("manufacturing")
    assert len(templates) >= 3
    assert all(t.industry == "manufacturing" for t in templates)


def test_templates_for_finance():
    """Finance industry returns at least 3 templates."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("finance")
    assert len(templates) >= 3


def test_templates_for_energy():
    """Energy industry returns at least 3 templates."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("energy")
    assert len(templates) >= 3


def test_templates_for_unknown_industry_returns_empty():
    """Unknown industry returns an empty list."""
    lib = WorkflowTemplateLibrary()
    result = lib.get_templates_for_industry("alien_tech")
    assert result == []


def test_get_template_by_id():
    """get_template returns the correct template by ID."""
    lib = WorkflowTemplateLibrary()
    # Load manufacturing templates first
    templates = lib.get_templates_for_industry("manufacturing")
    assert templates
    tpl = lib.get_template(templates[0].template_id)
    assert tpl is not None
    assert tpl.template_id == templates[0].template_id


def test_get_template_unknown_returns_none():
    """get_template returns None for an unknown template_id."""
    lib = WorkflowTemplateLibrary()
    assert lib.get_template("does_not_exist") is None


def test_register_custom_template():
    """register_template adds a new template to the library."""
    lib = WorkflowTemplateLibrary()
    custom = WorkflowTemplate(
        template_id="custom_test_001",
        name="Custom Test Workflow",
        description="A test workflow",
        industry="other",
        category="operations",
        steps=[
            {
                "step_id": "step_1",
                "name": "Step One",
                "action": "test.action",
                "depends_on": [],
                "description": "First step",
            }
        ],
    )
    result = lib.register_template(custom)
    assert result is True
    retrieved = lib.get_template("custom_test_001")
    assert retrieved is not None
    assert retrieved.name == "Custom Test Workflow"


def test_register_duplicate_template_returns_false():
    """Registering a template with a duplicate ID returns False."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("manufacturing")
    existing = templates[0]
    duplicate = WorkflowTemplate(
        template_id=existing.template_id,
        name="Duplicate",
        description="Dup",
        industry="manufacturing",
        category="operations",
        steps=[],
    )
    result = lib.register_template(duplicate)
    assert result is False


def test_list_all_templates():
    """list_all_templates returns summary dicts with required keys."""
    lib = WorkflowTemplateLibrary()
    all_tpls = lib.list_all_templates()
    assert len(all_tpls) > 0
    for tpl_dict in all_tpls:
        assert "template_id" in tpl_dict
        assert "name" in tpl_dict
        assert "industry" in tpl_dict
        assert "category" in tpl_dict


def test_compile_to_dag():
    """compile_to_dag converts a template into a WorkflowDefinition."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("manufacturing")
    assert templates
    dag = lib.compile_to_dag(templates[0])
    assert dag.workflow_id.startswith("wf_")
    assert dag.name == templates[0].name
    assert len(dag.steps) == len(templates[0].steps)


def test_compiled_dag_step_dependencies_valid():
    """Step dependencies in compiled DAG reference existing step IDs."""
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("manufacturing")
    dag = lib.compile_to_dag(templates[0])
    step_ids = {s.step_id for s in dag.steps}
    for step in dag.steps:
        for dep in step.depends_on:
            assert dep in step_ids, \
                f"Step '{step.step_id}' depends on unknown '{dep}'"


def test_template_to_dict():
    """WorkflowTemplate.to_dict is JSON-serialisable."""
    import json
    lib = WorkflowTemplateLibrary()
    templates = lib.get_templates_for_industry("energy")
    d = templates[0].to_dict()
    assert "template_id" in d
    json.dumps(d)
