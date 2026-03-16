"""
Tests for BIZ-003: OnboardingAutomationEngine.

Validates profile creation, task management, progress tracking,
checklist generation, and EventBackbone integration.

Design Label: TEST-005 / BIZ-003
Owner: QA Team
"""

import os
import pytest


from onboarding_automation_engine import (
    OnboardingAutomationEngine,
    OnboardingProfile,
    OnboardingStatus,
    TaskStatus,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def engine():
    return OnboardingAutomationEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return OnboardingAutomationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Profile creation
# ------------------------------------------------------------------

class TestProfileCreation:
    def test_create_engineering_profile(self, engine):
        profile = engine.create_onboarding(
            employee_name="Alice",
            role="backend engineer",
            department="engineering",
        )
        assert profile.profile_id.startswith("onb-")
        assert profile.employee_name == "Alice"
        assert profile.status == OnboardingStatus.CREATED
        assert len(profile.tasks) > 0

    def test_create_support_profile(self, engine):
        profile = engine.create_onboarding(
            employee_name="Bob",
            role="support agent",
            department="support",
        )
        assert len(profile.tasks) > 0
        categories = {t.category for t in profile.tasks}
        assert "training" in categories

    def test_create_default_profile(self, engine):
        profile = engine.create_onboarding(
            employee_name="Carol",
            role="analyst",
            department="finance",
        )
        assert len(profile.tasks) > 0

    def test_profile_to_dict(self, engine):
        profile = engine.create_onboarding(
            employee_name="Dave",
            role="dev",
            department="engineering",
        )
        d = profile.to_dict()
        assert "profile_id" in d
        assert "tasks" in d
        assert "progress_pct" in d

    def test_mentor_assignment(self, engine):
        profile = engine.create_onboarding(
            employee_name="Eve",
            role="dev",
            department="engineering",
            mentor="Senior Dev",
        )
        assert profile.mentor == "Senior Dev"


# ------------------------------------------------------------------
# Task management
# ------------------------------------------------------------------

class TestTaskManagement:
    def test_complete_task(self, engine):
        profile = engine.create_onboarding(
            employee_name="Alice",
            role="dev",
            department="engineering",
        )
        task_id = profile.tasks[0].task_id
        updated = engine.complete_task(profile.profile_id, task_id)
        assert updated is not None
        completed_task = next(t for t in updated.tasks if t.task_id == task_id)
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.completed_at is not None

    def test_complete_moves_to_in_progress(self, engine):
        profile = engine.create_onboarding(
            employee_name="Bob",
            role="dev",
            department="engineering",
        )
        task_id = profile.tasks[0].task_id
        updated = engine.complete_task(profile.profile_id, task_id)
        assert updated.status == OnboardingStatus.IN_PROGRESS

    def test_skip_task(self, engine):
        profile = engine.create_onboarding(
            employee_name="Carol",
            role="dev",
            department="engineering",
        )
        task_id = profile.tasks[0].task_id
        updated = engine.skip_task(profile.profile_id, task_id)
        assert updated is not None
        skipped = next(t for t in updated.tasks if t.task_id == task_id)
        assert skipped.status == TaskStatus.SKIPPED

    def test_complete_all_tasks(self, engine):
        profile = engine.create_onboarding(
            employee_name="Dave",
            role="dev",
            department="engineering",
        )
        for task in profile.tasks:
            engine.complete_task(profile.profile_id, task.task_id)
        updated_dict = engine.get_profile(profile.profile_id)
        assert updated_dict["status"] == "completed"
        assert updated_dict["progress_pct"] == 100.0

    def test_complete_nonexistent_profile(self, engine):
        assert engine.complete_task("nonexistent", "task-xxx") is None


# ------------------------------------------------------------------
# Progress tracking
# ------------------------------------------------------------------

class TestProgress:
    def test_progress_starts_at_zero(self, engine):
        profile = engine.create_onboarding(
            employee_name="Alice",
            role="dev",
            department="engineering",
        )
        assert profile.progress_pct == 0.0

    def test_progress_increases(self, engine):
        profile = engine.create_onboarding(
            employee_name="Bob",
            role="dev",
            department="engineering",
        )
        engine.complete_task(profile.profile_id, profile.tasks[0].task_id)
        updated = engine.get_profile(profile.profile_id)
        assert updated["progress_pct"] > 0.0


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_list_profiles(self, engine):
        engine.create_onboarding("A", "dev", "engineering")
        engine.create_onboarding("B", "agent", "support")
        profiles = engine.list_profiles()
        assert len(profiles) == 2

    def test_filter_by_department(self, engine):
        engine.create_onboarding("A", "dev", "engineering")
        engine.create_onboarding("B", "agent", "support")
        eng_only = engine.list_profiles(department="engineering")
        assert len(eng_only) == 1


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_task_completion_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        profile = wired_engine.create_onboarding("Alice", "dev", "engineering")
        wired_engine.complete_task(profile.profile_id, profile.tasks[0].task_id)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "onboarding_automation_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, engine):
        engine.create_onboarding("Alice", "dev", "engineering")
        status = engine.get_status()
        assert status["total_profiles"] == 1
        assert status["persistence_attached"] is False
