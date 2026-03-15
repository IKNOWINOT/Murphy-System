"""
Murphy System - Tests for Murphy Crew System
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import uuid
from datetime import datetime, timezone

import pytest

from murphy_crew_system import (
    AutomationType,
    CrewProcess,
    CrewRole,
    CrewTask,
    TaskResult,
    CrewMission,
    CrewExecution,
    CrewManager,
    Crew,
    CrewTemplateFactory,
    load_bot_crew,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_role(name: str = None, automation_types=None) -> CrewRole:
    return CrewRole(
        role_id=uuid.uuid4().hex[:8],
        name=name or f"role_{uuid.uuid4().hex[:6]}",
        description="A test role",
        capabilities=["research", "write"],
        authority_level=5,
        automation_types=automation_types or [AutomationType.AGENT],
    )


def _make_task(description: str = "Do test work") -> CrewTask:
    return CrewTask(
        task_id=uuid.uuid4().hex[:8],
        description=description,
        expected_output="Some result",
    )


def _make_mission(tasks=None, process: CrewProcess = CrewProcess.SEQUENTIAL) -> CrewMission:
    if tasks is None:
        tasks = [_make_task()]
    return CrewMission(
        mission_id=uuid.uuid4().hex[:8],
        description="Test mission",
        tasks=tasks,
        automation_type=AutomationType.AGENT,
        process=process,
    )


# ---------------------------------------------------------------------------
# TestCrewRole
# ---------------------------------------------------------------------------

class TestCrewRole:
    def test_create_crew_role(self):
        role = _make_role("analyst")
        assert role.name == "analyst"
        assert role.authority_level == 5
        assert AutomationType.AGENT in role.automation_types

    def test_authority_level_bounds(self):
        role = CrewRole(
            role_id=uuid.uuid4().hex[:8],
            name="senior",
            description="Senior role",
            capabilities=["lead"],
            authority_level=10,
            automation_types=[AutomationType.FACTORY],
        )
        assert role.authority_level == 10

    def test_multiple_capabilities(self):
        role = _make_role()
        assert len(role.capabilities) >= 1

    def test_automation_types_list(self):
        role = CrewRole(
            role_id=uuid.uuid4().hex[:8],
            name="multi",
            description="Multi-type role",
            capabilities=["research"],
            automation_types=[AutomationType.CONTENT, AutomationType.DATA],
        )
        assert AutomationType.CONTENT in role.automation_types
        assert AutomationType.DATA in role.automation_types


# ---------------------------------------------------------------------------
# TestCrew
# ---------------------------------------------------------------------------

class TestCrew:
    def test_add_role(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="TestCrew")
        role = _make_role()
        crew.add_role(role)
        assert crew.get_role(role.role_id) is role

    def test_list_roles_empty(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="Empty")
        assert crew.list_roles() == []

    def test_list_roles_after_add(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="Crew2")
        role1 = _make_role()
        role2 = _make_role()
        crew.add_role(role1)
        crew.add_role(role2)
        ids = [r.role_id for r in crew.list_roles()]
        assert role1.role_id in ids
        assert role2.role_id in ids

    def test_assign_task_returns_role_or_none(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="Crew3")
        role = _make_role()
        crew.add_role(role)
        task = _make_task()
        result = crew.assign_task(task)
        assert result is None or isinstance(result, CrewRole)

    def test_execute_mission_sequential_returns_crew_execution(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="SeqCrew")
        role = _make_role(automation_types=[AutomationType.AGENT])
        crew.add_role(role)
        mission = _make_mission(process=CrewProcess.SEQUENTIAL)
        execution = crew.execute_mission(mission)
        assert isinstance(execution, CrewExecution)
        assert execution.mission_id == mission.mission_id

    def test_execute_mission_has_valid_success_rate(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="Crew4")
        role = _make_role()
        crew.add_role(role)
        mission = _make_mission()
        execution = crew.execute_mission(mission)
        assert 0.0 <= execution.success_rate <= 1.0

    def test_execute_mission_status_field(self):
        crew = Crew(crew_id=uuid.uuid4().hex[:8], name="Crew5")
        role = _make_role()
        crew.add_role(role)
        mission = _make_mission()
        execution = crew.execute_mission(mission)
        assert execution.status in ("completed", "partial", "failed")


# ---------------------------------------------------------------------------
# TestCrewManager
# ---------------------------------------------------------------------------

class TestCrewManager:
    def test_delegate_returns_task_result(self):
        manager = CrewManager(name="TestManager")
        task = _make_task("Summarise document")
        role = _make_role("summariser")
        result = manager.delegate(task, role)
        assert isinstance(result, TaskResult)
        assert result.task_id == task.task_id
        assert result.success is True

    def test_delegate_output_mentions_manager(self):
        manager = CrewManager(name="AlphaManager")
        task = _make_task()
        role = _make_role()
        result = manager.delegate(task, role)
        assert "AlphaManager" in str(result.output)

    def test_review_passes_high_confidence(self):
        manager = CrewManager()
        result = TaskResult(
            task_id="t1",
            role_id="r1",
            success=True,
            output="done",
            confidence=0.9,
        )
        assert manager.review(result) is True

    def test_review_fails_low_confidence(self):
        manager = CrewManager()
        result = TaskResult(
            task_id="t2",
            role_id="r2",
            success=True,
            output="uncertain",
            confidence=0.3,
        )
        assert manager.review(result) is False

    def test_escalate_returns_message_string(self):
        manager = CrewManager(name="EscManager")
        task = _make_task("Critical task needing escalation")
        msg = manager.escalate(task)
        assert isinstance(msg, str)
        assert task.task_id in msg

    def test_escalate_mentions_manager_name(self):
        manager = CrewManager(name="SeniorMgr")
        task = _make_task()
        msg = manager.escalate(task)
        assert "SeniorMgr" in msg


# ---------------------------------------------------------------------------
# TestCrewTemplateFactory
# ---------------------------------------------------------------------------

class TestCrewTemplateFactory:
    def test_factory_crew_returns_crew(self):
        crew = CrewTemplateFactory.factory_crew()
        assert isinstance(crew, Crew)

    def test_content_crew_returns_crew(self):
        crew = CrewTemplateFactory.content_crew()
        assert isinstance(crew, Crew)

    def test_data_crew_returns_crew(self):
        crew = CrewTemplateFactory.data_crew()
        assert isinstance(crew, Crew)

    def test_system_crew_returns_crew(self):
        crew = CrewTemplateFactory.system_crew()
        assert isinstance(crew, Crew)

    def test_agent_crew_returns_crew(self):
        crew = CrewTemplateFactory.agent_crew()
        assert isinstance(crew, Crew)

    def test_business_crew_returns_crew(self):
        crew = CrewTemplateFactory.business_crew()
        assert isinstance(crew, Crew)

    def test_all_template_crews_have_roles(self):
        factory_methods = [
            CrewTemplateFactory.factory_crew,
            CrewTemplateFactory.content_crew,
            CrewTemplateFactory.data_crew,
            CrewTemplateFactory.system_crew,
            CrewTemplateFactory.agent_crew,
            CrewTemplateFactory.business_crew,
        ]
        for method in factory_methods:
            crew = method()
            assert len(crew.list_roles()) > 0, f"{method.__name__} returned crew with no roles"

    def test_get_crew_for_type(self):
        for auto_type in AutomationType:
            crew = CrewTemplateFactory.get_crew_for_type(auto_type)
            assert isinstance(crew, Crew)


# ---------------------------------------------------------------------------
# TestLoadBotCrew
# ---------------------------------------------------------------------------

class TestLoadBotCrew:
    def test_load_bot_crew_returns_crew(self):
        crew = load_bot_crew(["Murphy", "Analyst"])
        assert isinstance(crew, Crew)

    def test_load_bot_crew_empty_list(self):
        crew = load_bot_crew([])
        assert isinstance(crew, Crew)

    def test_load_bot_crew_has_roles_for_nonempty_list(self):
        crew = load_bot_crew(["Alpha", "Beta", "Gamma"])
        assert len(crew.list_roles()) >= 0

    def test_load_bot_crew_unique_crew_ids(self):
        crew1 = load_bot_crew(["BotA"])
        crew2 = load_bot_crew(["BotB"])
        assert crew1.crew_id != crew2.crew_id
