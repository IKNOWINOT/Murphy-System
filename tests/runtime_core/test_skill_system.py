"""
Tests for the Skill System (SK-001..SK-003).

Covers: registration, search, composition, DAG validation,
execution, workflow saving, sharing, and pipeline matching.
"""

from __future__ import annotations

import pytest

from src.skill_system.models import (
    SkillAccess,
    SkillComposition,
    SkillSpec,
    SkillStep,
    SkillStepStatus,
)
from src.skill_system.skill_manager import SkillManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return SkillManager()


@pytest.fixture
def simple_skill():
    return SkillSpec(
        skill_id="skill.hello",
        name="Hello World",
        description="A simple greeting skill.",
        owner_tenant="tenant_a",
        access=SkillAccess.PRIVATE,
    )


@pytest.fixture
def composed_skill():
    s1 = SkillStep(step_id="step1", name="Fetch", tool_id="tool.fetch")
    s2 = SkillStep(step_id="step2", name="Process", tool_id="tool.process",
                    depends_on=["step1"])
    return SkillSpec(
        skill_id="skill.etl",
        name="ETL Pipeline",
        description="Extract, transform, load data.",
        owner_tenant="tenant_a",
        access=SkillAccess.TENANT,
        composition=SkillComposition(
            steps=[s1, s2],
            entry_points=["step1"],
        ),
    )


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_get(self, manager, simple_skill):
        manager.register(simple_skill)
        fetched = manager.get("skill.hello")
        assert fetched.name == "Hello World"

    def test_unregister(self, manager, simple_skill):
        manager.register(simple_skill)
        removed = manager.unregister("skill.hello")
        assert removed.skill_id == "skill.hello"
        assert manager.count() == 0

    def test_count(self, manager, simple_skill, composed_skill):
        manager.register(simple_skill)
        manager.register(composed_skill)
        assert manager.count() == 2


# ---------------------------------------------------------------------------
# Search & discovery tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_list_skills(self, manager, simple_skill, composed_skill):
        manager.register(simple_skill)
        manager.register(composed_skill)
        all_skills = manager.list_skills()
        assert len(all_skills) == 2

    def test_list_by_access(self, manager, simple_skill, composed_skill):
        manager.register(simple_skill)
        manager.register(composed_skill)
        tenant_skills = manager.list_skills(access_filter=SkillAccess.TENANT)
        assert len(tenant_skills) == 1

    def test_search_by_text(self, manager, simple_skill, composed_skill):
        manager.register(simple_skill)
        manager.register(composed_skill)
        results = manager.search("ETL")
        assert len(results) == 1
        assert results[0].skill_id == "skill.etl"

    def test_search_with_tenant_isolation(self, manager, simple_skill):
        manager.register(simple_skill)
        # Private skill not visible to other tenant
        results = manager.search("Hello", tenant_id="tenant_b")
        assert len(results) == 0
        # Visible to owner
        results = manager.search("Hello", tenant_id="tenant_a")
        assert len(results) == 1

    def test_match_for_pipeline(self, manager, simple_skill):
        manager.register(simple_skill)
        match = manager.match_for_pipeline("Hello", tenant_id="tenant_a")
        assert match is not None
        assert match.skill_id == "skill.hello"

    def test_match_for_pipeline_no_match(self, manager):
        match = manager.match_for_pipeline("nonexistent query")
        assert match is None


# ---------------------------------------------------------------------------
# DAG validation tests
# ---------------------------------------------------------------------------

class TestDAGValidation:
    def test_valid_dag(self, manager, composed_skill):
        manager.register(composed_skill)
        errors = manager.validate_composition("skill.etl")
        assert errors == []

    def test_missing_dependency(self, manager):
        s1 = SkillStep(step_id="s1", tool_id="t1", depends_on=["nonexistent"])
        skill = SkillSpec(
            skill_id="bad",
            name="Bad Skill",
            composition=SkillComposition(steps=[s1]),
        )
        manager.register(skill)
        errors = manager.validate_composition("bad")
        assert any("unknown step" in e for e in errors)

    def test_missing_sub_skill(self, manager):
        s1 = SkillStep(step_id="s1", sub_skill_id="missing_skill")
        skill = SkillSpec(
            skill_id="ref_bad",
            name="Bad Ref",
            composition=SkillComposition(steps=[s1]),
        )
        manager.register(skill)
        errors = manager.validate_composition("ref_bad")
        assert any("unknown skill" in e for e in errors)

    def test_not_found(self, manager):
        errors = manager.validate_composition("nonexistent")
        assert any("not found" in e for e in errors)


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestExecution:
    def test_execute_simple(self, manager, composed_skill):
        manager.register(composed_skill)
        manager.register_tool_executor(
            "tool.fetch", lambda inp: {"data": "fetched"},
        )
        manager.register_tool_executor(
            "tool.process", lambda inp: {"result": "processed"},
        )
        record = manager.execute("skill.etl", {})
        assert record.status == SkillStepStatus.COMPLETED

    def test_execute_missing_skill(self, manager):
        record = manager.execute("nonexistent", {})
        assert record.status == SkillStepStatus.FAILED

    def test_execute_missing_tool(self, manager, composed_skill):
        manager.register(composed_skill)
        # Don't register executors
        record = manager.execute("skill.etl", {})
        assert record.status == SkillStepStatus.FAILED

    def test_execution_count_increments(self, manager, composed_skill):
        manager.register(composed_skill)
        manager.register_tool_executor("tool.fetch", lambda inp: {"data": "x"})
        manager.register_tool_executor("tool.process", lambda inp: {"r": "y"})
        manager.execute("skill.etl", {})
        skill = manager.get("skill.etl")
        assert skill.execution_count == 1
        assert skill.success_count == 1


# ---------------------------------------------------------------------------
# Workflow saving tests
# ---------------------------------------------------------------------------

class TestWorkflowSaving:
    def test_save_workflow_as_skill(self, manager):
        skill = manager.save_workflow_as_skill(
            "My Workflow",
            [
                {"step_id": "s1", "tool_id": "t1"},
                {"step_id": "s2", "tool_id": "t2", "depends_on": ["s1"]},
            ],
            tenant_id="tenant_a",
            description="A saved workflow",
            tags=["automation"],
        )
        assert skill.name == "My Workflow"
        assert len(skill.composition.steps) == 2
        assert manager.count() == 1


# ---------------------------------------------------------------------------
# Sharing tests
# ---------------------------------------------------------------------------

class TestSharing:
    def test_share_skill(self, manager, simple_skill):
        manager.register(simple_skill)
        manager.share_skill("skill.hello", SkillAccess.COMMUNITY)
        updated = manager.get("skill.hello")
        assert updated.access == SkillAccess.COMMUNITY

    def test_share_nonexistent(self, manager):
        with pytest.raises(KeyError):
            manager.share_skill("nonexistent", SkillAccess.COMMUNITY)

    def test_execution_log(self, manager):
        log = manager.get_execution_log()
        assert isinstance(log, list)
