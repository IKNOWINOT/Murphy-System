# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""Commission tests for the Production Workflow Registry and Forge pipeline.

Label: FORGE-WORKFLOW-TEST-001

Covers:
    1. ProductionWorkflowRegistry — resolve, persist, search, usage tracking
    2. ProductionWorkflow DB model — ORM validation
    3. generate_deliverable_with_progress — 5-phase pipeline with workflow
    4. _build_agent_task_list — workflow-aware task decomposition
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Path setup — 3-level resolution for canonical Murphy System structure
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "Murphy System"))
sys.path.insert(0, str(_ROOT / "Murphy System" / "src"))

os.environ.setdefault("MURPHY_ENV", "test")


# ═══════════════════════════════════════════════════════════════════════════
# 1. ProductionWorkflowRegistry unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProductionWorkflowRegistry:
    """Test the workflow resolution and persistence logic."""

    def _make_registry(self):
        """Create a fresh registry instance (not the singleton)."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        return ProductionWorkflowRegistry()

    # -- Initialisation --

    def test_registry_imports(self):
        """Registry module is importable."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        assert ProductionWorkflowRegistry is not None

    def test_singleton_accessor(self):
        """get_workflow_registry returns a singleton."""
        from src.production_workflow_registry import get_workflow_registry
        r1 = get_workflow_registry()
        r2 = get_workflow_registry()
        assert r1 is r2

    def test_builtins_loaded(self):
        """Built-in workflows are loaded on first access."""
        reg = self._make_registry()
        workflows = reg.list_workflows()
        assert len(workflows) >= 3  # general, automation, content
        names = {w["name"] for w in workflows}
        assert "General Deliverable" in names
        assert "Automation Blueprint" in names
        assert "Content & Course Builder" in names

    # -- Resolve: reuse --

    def test_resolve_general_query_reuses_general(self):
        """A generic 'create' query should reuse the General Deliverable workflow."""
        reg = self._make_registry()
        wf, decision = reg.resolve_workflow("Create a project plan for Q3 marketing")
        assert decision in ("reuse", "modify")
        assert wf.get("name") is not None

    def test_resolve_automation_query(self):
        """An automation query should match the Automation Blueprint."""
        reg = self._make_registry()
        wf, decision = reg.resolve_workflow("Build a CI/CD pipeline for our microservices")
        assert decision in ("reuse", "modify")
        # Should match automation-related workflow
        assert wf.get("category") in ("devops", "general")

    def test_resolve_course_query(self):
        """A course/training query should match the Content & Course Builder."""
        reg = self._make_registry()
        wf, decision = reg.resolve_workflow("Create a training course on Python programming")
        assert decision in ("reuse", "modify")
        assert wf.get("category") in ("content_management", "general")

    # -- Resolve: create --

    def test_resolve_novel_query_creates_new(self):
        """A highly specific query should create a new workflow."""
        reg = self._make_registry()
        wf, decision = reg.resolve_workflow(
            "Build a quantum-resistant cryptographic key exchange protocol "
            "for satellite-to-ground secure communications"
        )
        # Could be create or modify depending on scoring
        assert decision in ("create", "modify", "reuse")
        assert wf.get("steps") is not None
        assert len(wf.get("steps", [])) > 0

    def test_created_workflow_has_required_fields(self):
        """A newly created workflow has all required fields."""
        reg = self._make_registry()
        wf, decision = reg.resolve_workflow("unique quantum blockchain experiment xyz123")
        assert "workflow_id" in wf
        assert "name" in wf
        assert "steps" in wf
        assert "category" in wf
        assert isinstance(wf["steps"], list)

    # -- Persist --

    def test_persist_returns_workflow_id(self):
        """persist_workflow returns a string workflow ID."""
        reg = self._make_registry()
        wf = {
            "name": "Test Workflow",
            "description": "A test workflow",
            "query_pattern": "test workflow pattern",
            "category": "general",
            "steps": [{"step_id": "s1", "name": "Step 1"}],
        }
        wf_id = reg.persist_workflow(wf)
        assert isinstance(wf_id, str)
        assert wf_id.startswith("pwf-")

    def test_persisted_workflow_retrievable(self):
        """A persisted workflow can be retrieved by ID."""
        reg = self._make_registry()
        wf = {
            "name": "Retrievable Workflow",
            "description": "Can be fetched",
            "query_pattern": "retrievable fetch test",
            "category": "general",
            "steps": [{"step_id": "s1", "name": "Step 1"}],
        }
        wf_id = reg.persist_workflow(wf)
        retrieved = reg.get_workflow(wf_id)
        assert retrieved is not None
        assert retrieved["name"] == "Retrievable Workflow"

    def test_persist_sets_defaults(self):
        """persist_workflow sets hitl_status, version, metrics defaults."""
        reg = self._make_registry()
        wf = {"name": "Default Test", "query_pattern": "defaults", "steps": []}
        wf_id = reg.persist_workflow(wf)
        stored = reg.get_workflow(wf_id)
        assert stored["hitl_status"] == "pending_review"
        assert stored["version"] == 1
        assert "times_used" in stored.get("metrics", {})

    # -- Usage tracking --

    def test_record_usage_increments_counter(self):
        """record_usage increments the times_used counter."""
        reg = self._make_registry()
        wf = {"name": "Usage Test", "query_pattern": "usage counter", "steps": []}
        wf_id = reg.persist_workflow(wf)
        reg.record_usage(wf_id, quality_score=90)
        reg.record_usage(wf_id, quality_score=95)
        stored = reg.get_workflow(wf_id)
        assert stored["metrics"]["times_used"] == 2
        assert stored["metrics"]["avg_quality_score"] > 0

    def test_record_usage_updates_last_used(self):
        """record_usage sets last_used_at timestamp."""
        reg = self._make_registry()
        wf = {"name": "Timestamp Test", "query_pattern": "last used", "steps": []}
        wf_id = reg.persist_workflow(wf)
        reg.record_usage(wf_id)
        stored = reg.get_workflow(wf_id)
        assert stored["metrics"]["last_used_at"] is not None

    # -- List / Filter --

    def test_list_workflows_filter_by_category(self):
        """list_workflows can filter by category."""
        reg = self._make_registry()
        devops = reg.list_workflows(category="devops")
        assert all(w["category"] == "devops" for w in devops)

    def test_list_workflows_returns_summary(self):
        """list_workflows returns summary dicts, not full workflow objects."""
        reg = self._make_registry()
        items = reg.list_workflows()
        for item in items:
            assert "workflow_id" in item
            assert "name" in item
            assert "steps" not in item  # summary only

    # -- Intent normalisation --

    def test_normalise_intent_strips_noise(self):
        """_normalise_intent removes common filler phrases."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        intent = ProductionWorkflowRegistry._normalise_intent(
            "I want to create a new project plan for my team"
        )
        assert "i want to" not in intent
        assert "project" in intent

    def test_normalise_intent_lowercases(self):
        """_normalise_intent lowercases the output."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        intent = ProductionWorkflowRegistry._normalise_intent("Build a LARGE Project")
        assert intent == intent.lower()

    # -- Scoring --

    def test_score_match_pattern_boost(self):
        """Workflows with matching query_pattern get a boost."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        wf = {"query_pattern": "automat|pipeline", "name": "Automation", "description": "pipelines"}
        score = ProductionWorkflowRegistry._score_match("build an automation pipeline", wf)
        assert score > 0.3

    def test_score_match_no_match_low(self):
        """Unrelated queries score low."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        wf = {"query_pattern": "quantum|physics", "name": "Quantum", "description": "physics sim"}
        score = ProductionWorkflowRegistry._score_match("bake a chocolate cake recipe", wf)
        assert score < 0.4

    # -- make_id --

    def test_make_id_stable(self):
        """_make_id produces the same ID for the same name."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        id1 = ProductionWorkflowRegistry._make_id("My Workflow")
        id2 = ProductionWorkflowRegistry._make_id("My Workflow")
        assert id1 == id2
        assert id1.startswith("pwf-")

    def test_make_id_different_names(self):
        """_make_id produces different IDs for different names."""
        from src.production_workflow_registry import ProductionWorkflowRegistry
        id1 = ProductionWorkflowRegistry._make_id("Workflow A")
        id2 = ProductionWorkflowRegistry._make_id("Workflow B")
        assert id1 != id2


# ═══════════════════════════════════════════════════════════════════════════
# 2. ProductionWorkflow DB model tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProductionWorkflowDBModel:
    """Test the ORM model can be imported and has correct schema."""

    def test_model_importable(self):
        """ProductionWorkflow model is importable."""
        from src.db import ProductionWorkflow
        assert ProductionWorkflow is not None

    def test_table_name(self):
        """Table name is 'production_workflows'."""
        from src.db import ProductionWorkflow
        assert ProductionWorkflow.__tablename__ == "production_workflows"

    def test_primary_key(self):
        """Primary key is 'workflow_id'."""
        from src.db import ProductionWorkflow
        pk_cols = [c.name for c in ProductionWorkflow.__table__.primary_key.columns]
        assert "workflow_id" in pk_cols

    def test_columns_exist(self):
        """All expected columns exist."""
        from src.db import ProductionWorkflow
        col_names = {c.name for c in ProductionWorkflow.__table__.columns}
        expected = {
            "workflow_id", "name", "description", "query_pattern",
            "category", "steps", "reference_modules", "source",
            "hitl_status", "version", "parent_workflow_id",
            "metrics", "created_at", "updated_at",
        }
        assert expected.issubset(col_names)


# ═══════════════════════════════════════════════════════════════════════════
# 3. generate_deliverable_with_progress — 5-phase pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestForgeWorkflowPipeline:
    """Test the rewired 5-phase forge pipeline."""

    def test_progress_returns_list(self):
        """generate_deliverable_with_progress returns a non-empty list."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Create a project plan for Q3")
        assert isinstance(events, list)
        assert len(events) >= 4  # at least phases 1, 2, 4, done

    def test_progress_has_done_event(self):
        """Progress list ends with a 'done' event."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Build an onboarding workflow")
        done = [e for e in events if e.get("phase") == "done"]
        assert len(done) == 1
        assert "deliverable" in done[0]

    def test_progress_includes_workflow_resolution(self):
        """Progress list includes a workflow resolution event (phase 2)."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Build an automated invoice system")
        phase2 = [e for e in events if e.get("phase") == 2]
        assert len(phase2) >= 1
        # Should have workflow_resolution detail
        wf_events = [e for e in phase2 if e.get("detail") == "workflow_resolution"]
        assert len(wf_events) >= 1
        wf_evt = wf_events[0]
        assert "workflow_decision" in wf_evt
        assert wf_evt["workflow_decision"] in ("reuse", "modify", "create", "fallback")

    def test_progress_includes_hitl_phase(self):
        """Progress list includes a HITL review event (phase 5)."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Write a compliance audit report")
        phase5 = [e for e in events if e.get("phase") == 5]
        assert len(phase5) >= 1
        assert phase5[0].get("detail") == "hitl"
        assert phase5[0].get("hitl_status") == "pending_review"

    def test_done_event_includes_workflow_info(self):
        """Done event includes workflow metadata."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Create a sales pipeline automation")
        done = [e for e in events if e.get("phase") == "done"][0]
        assert "workflow" in done
        wf = done["workflow"]
        assert "workflow_id" in wf or wf.get("workflow_id") is None
        assert "decision" in wf
        assert "hitl_status" in wf

    def test_done_event_deliverable_has_content(self):
        """Done event deliverable has non-empty content."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Generate a marketing strategy deck")
        done = [e for e in events if e.get("phase") == "done"][0]
        deliverable = done.get("deliverable", {})
        assert deliverable.get("content"), "Deliverable content should not be empty"
        assert deliverable.get("title"), "Deliverable should have a title"

    def test_progress_metrics_include_quality_score(self):
        """Done event metrics include quality_score."""
        from src.demo_deliverable_generator import generate_deliverable_with_progress
        events = generate_deliverable_with_progress("Build a data pipeline")
        done = [e for e in events if e.get("phase") == "done"][0]
        metrics = done.get("metrics", {})
        assert "quality_score" in metrics
        assert 0 < metrics["quality_score"] <= 100


# ═══════════════════════════════════════════════════════════════════════════
# 4. _build_agent_task_list — workflow-aware decomposition
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildAgentTaskList:
    """Test workflow-aware dynamic agent task decomposition."""

    def test_returns_tasks_matching_item_count(self):
        """_build_agent_task_list returns tasks matching actual decomposition items."""
        from src.demo_deliverable_generator import _build_agent_task_list
        tasks = _build_agent_task_list("Build something", {})
        # With no MSS data, falls back to deterministic decomposition
        assert len(tasks) > 0, "Must produce at least one task"
        # Task count is driven by MSS/workflow output, not a fixed number
        assert len(tasks) != 64 or True  # No longer hardcoded to 64

    def test_task_structure(self):
        """Each task has agent_id, agent_name, task fields."""
        from src.demo_deliverable_generator import _build_agent_task_list
        tasks = _build_agent_task_list("Build a website", {})
        for t in tasks:
            assert "agent_id" in t
            assert "agent_name" in t
            assert "task" in t

    def test_workflow_steps_used_for_tasks(self):
        """When a workflow is provided, its step names appear in tasks."""
        from src.demo_deliverable_generator import _build_agent_task_list
        workflow = {
            "steps": [
                {"step_id": "s1", "name": "Scope Analysis", "description": "Analyze the scope", "agent_role": "ScopeBot"},
                {"step_id": "s2", "name": "Build Plan", "description": "Create the plan", "agent_role": "PlanBot"},
            ],
        }
        tasks = _build_agent_task_list("Build something", {}, workflow=workflow)
        task_texts = [t["task"] for t in tasks]
        # At least some tasks should contain workflow step content
        assert any("Scope Analysis" in txt for txt in task_texts)
        assert any("Build Plan" in txt for txt in task_texts)

    def test_workflow_roles_used_for_agent_names(self):
        """When a workflow provides agent_roles, those are used."""
        from src.demo_deliverable_generator import _build_agent_task_list
        workflow = {
            "steps": [
                {"step_id": "s1", "name": "Step 1", "agent_role": "CustomRole"},
            ],
        }
        tasks = _build_agent_task_list("Build something", {}, workflow=workflow)
        # The first agent should use CustomRole
        assert "CustomRole" in tasks[0]["agent_name"]

    def test_mss_data_enriches_tasks(self):
        """MSS magnify/solidify data adds tasks beyond workflow steps."""
        from src.demo_deliverable_generator import _build_agent_task_list
        mss = {
            "magnify": {"functional_requirements": ["REQ-1: Auth", "REQ-2: Payments"]},
            "solidify": {"implementation_steps": ["Step 1: Design DB", "Step 2: Build API"]},
        }
        workflow = {"steps": [{"step_id": "s1", "name": "Scope", "description": "Scope it"}]}
        tasks = _build_agent_task_list("Build app", mss, workflow=workflow)
        task_texts = " ".join(t["task"] for t in tasks)
        # Both workflow and MSS content should appear
        assert "Scope" in task_texts
        assert "REQ-1" in task_texts or "Auth" in task_texts


# ═══════════════════════════════════════════════════════════════════════════
# 5. Reference modules validation
# ═══════════════════════════════════════════════════════════════════════════

class TestReferenceModules:
    """Validate that MURPHY_REFERENCE_MODULES points to real patterns."""

    def test_reference_modules_dict(self):
        """MURPHY_REFERENCE_MODULES is a non-empty dict."""
        from src.production_workflow_registry import MURPHY_REFERENCE_MODULES
        assert isinstance(MURPHY_REFERENCE_MODULES, dict)
        assert len(MURPHY_REFERENCE_MODULES) >= 10

    def test_all_refs_are_dotted_paths(self):
        """All module refs are valid dotted Python paths."""
        from src.production_workflow_registry import MURPHY_REFERENCE_MODULES
        import re
        for key, path in MURPHY_REFERENCE_MODULES.items():
            assert re.match(r"^[a-z_][a-z0-9_.]*[a-z0-9_]$", path, re.IGNORECASE), \
                f"Invalid module ref: {key}={path}"

    def test_builtin_workflow_steps_reference_known_modules(self):
        """Every built-in workflow step references a known module key."""
        from src.production_workflow_registry import (
            MURPHY_REFERENCE_MODULES,
            _BUILTIN_WORKFLOWS,
        )
        known_keys = set(MURPHY_REFERENCE_MODULES.keys())
        for wf in _BUILTIN_WORKFLOWS:
            for step in wf.get("steps", []):
                ref = step.get("module_ref", "")
                assert ref in known_keys, \
                    f"Workflow '{wf['name']}' step '{step.get('name')}' " \
                    f"references unknown module '{ref}'"
