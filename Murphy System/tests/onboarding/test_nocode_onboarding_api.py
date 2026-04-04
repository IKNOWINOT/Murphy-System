"""
Tests for the no-code onboarding API endpoints.

Validates that the Setup Wizard and Onboarding Automation Engine are
properly exposed via REST API for no-code access.

Design Label: TEST-ONBOARDING-API
Owner: QA Team
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from setup_wizard import SetupWizard, SetupProfile, CORE_MODULES
from onboarding_automation_engine import (
    OnboardingAutomationEngine,
    OnboardingStatus,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Test: Setup Wizard API contract (validates what the API endpoints return)
# ---------------------------------------------------------------------------

class TestSetupWizardAPIContract:
    """Validate that the SetupWizard produces data suitable for API responses."""

    def test_questions_serializable(self):
        """All questions can be serialized to JSON with required structure."""
        wiz = SetupWizard()
        questions = wiz.get_questions()
        serialized = json.dumps(questions)
        loaded = json.loads(serialized)
        assert len(loaded) == len(questions)
        for q in loaded:
            assert "id" in q
            assert "text" in q
            assert "question_type" in q
            assert "field" in q

    def test_profile_serializable(self):
        """Profile can be converted to dict and serialized."""
        from dataclasses import asdict
        wiz = SetupWizard()
        wiz.apply_answer("q1", "Test Corp")
        profile = wiz.get_profile()
        profile_dict = asdict(profile)
        serialized = json.dumps(profile_dict)
        loaded = json.loads(serialized)
        assert loaded["organization_name"] == "Test Corp"

    def test_config_serializable(self):
        """Generated config can be serialized to JSON."""
        wiz = SetupWizard()
        wiz.apply_answer("q1", "Test Corp")
        profile = wiz.get_profile()
        config = wiz.generate_config(profile)
        serialized = json.dumps(config)
        loaded = json.loads(serialized)
        assert "modules" in loaded
        assert "bots" in loaded

    def test_validation_result_serializable(self):
        """Validation result can be serialized to JSON."""
        wiz = SetupWizard()
        result = wiz.validate_profile(wiz.get_profile())
        serialized = json.dumps(result)
        loaded = json.loads(serialized)
        assert "valid" in loaded
        assert "issues" in loaded

    def test_summary_is_string(self):
        """Summary returns a plain string."""
        wiz = SetupWizard()
        wiz.apply_answer("q1", "Test Corp")
        summary = wiz.summarize(wiz.get_profile())
        assert isinstance(summary, str)
        assert "Test Corp" in summary

    def test_wizard_reset_produces_fresh_state(self):
        """Creating a new wizard gives a fresh profile."""
        wiz1 = SetupWizard()
        wiz1.apply_answer("q1", "Company A")
        assert wiz1.get_profile().organization_name == "Company A"

        wiz2 = SetupWizard()
        assert wiz2.get_profile().organization_name == ""

    def test_full_wizard_flow(self):
        """Simulate a complete no-code wizard flow via API contract."""
        wiz = SetupWizard()

        # Step 1: Get questions
        questions = wiz.get_questions()
        assert len(questions) >= 10

        # Step 2: Answer all questions
        answers = {
            "q1": "Acme Corp",
            "q2": "technology",
            "q3": "medium",
            "q4": ["data", "agent"],
            "q5": "standard",
            "q6": False,
            "q7": [],
            "q8": False,
            "q9": "deepinfra",
            "q10": ["SOC2"],
            "q11": "docker",
            "q12": True,
        }
        for qid, answer in answers.items():
            result = wiz.apply_answer(qid, answer)
            assert result["ok"], f"Failed to apply {qid}: {result.get('error')}"

        # Step 3: Validate
        validation = wiz.validate_profile(wiz.get_profile())
        assert validation["valid"] is True

        # Step 4: Generate config
        config = wiz.generate_config(wiz.get_profile())
        assert config["organization"]["name"] == "Acme Corp"
        assert "data" in config["automation"]["enabled_types"]
        assert len(config["modules"]) > len(CORE_MODULES)
        assert len(config["bots"]) > 0

        # Step 5: Summary
        summary = wiz.summarize(wiz.get_profile())
        assert "Acme Corp" in summary
        assert "technology" in summary


# ---------------------------------------------------------------------------
# Test: Onboarding Engine API contract
# ---------------------------------------------------------------------------

class TestOnboardingEngineAPIContract:
    """Validate that the Onboarding Engine produces data suitable for API responses."""

    def test_profile_to_dict_serializable(self):
        """Profile to_dict() output can be serialized to JSON."""
        engine = OnboardingAutomationEngine()
        profile = engine.create_onboarding("Alice", "dev", "engineering")
        d = profile.to_dict()
        serialized = json.dumps(d)
        loaded = json.loads(serialized)
        assert loaded["employee_name"] == "Alice"
        assert loaded["profile_id"].startswith("onb-")
        assert len(loaded["tasks"]) > 0

    def test_list_profiles_serializable(self):
        """list_profiles returns JSON-serializable data."""
        engine = OnboardingAutomationEngine()
        engine.create_onboarding("A", "dev", "engineering")
        engine.create_onboarding("B", "agent", "support")
        profiles = engine.list_profiles()
        serialized = json.dumps(profiles)
        loaded = json.loads(serialized)
        assert len(loaded) == 2

    def test_get_status_serializable(self):
        """get_status returns JSON-serializable data."""
        engine = OnboardingAutomationEngine()
        engine.create_onboarding("A", "dev", "engineering")
        status = engine.get_status()
        serialized = json.dumps(status)
        loaded = json.loads(serialized)
        assert loaded["total_profiles"] == 1

    def test_complete_task_api_flow(self):
        """Simulate the complete task API flow."""
        engine = OnboardingAutomationEngine()
        profile = engine.create_onboarding("Bob", "dev", "engineering")

        # Get profile
        profile_dict = engine.get_profile(profile.profile_id)
        assert profile_dict is not None
        assert profile_dict["progress_pct"] == 0.0

        # Complete first task
        task_id = profile_dict["tasks"][0]["task_id"]
        updated = engine.complete_task(profile.profile_id, task_id)
        assert updated is not None

        # Verify progress
        updated_dict = engine.get_profile(profile.profile_id)
        assert updated_dict["progress_pct"] > 0.0
        assert updated_dict["status"] == "in_progress"

    def test_skip_task_api_flow(self):
        """Simulate the skip task API flow."""
        engine = OnboardingAutomationEngine()
        profile = engine.create_onboarding("Carol", "agent", "support")

        task_id = profile.tasks[0].task_id
        updated = engine.skip_task(profile.profile_id, task_id)
        assert updated is not None

        updated_dict = engine.get_profile(profile.profile_id)
        skipped = [t for t in updated_dict["tasks"] if t["task_id"] == task_id]
        assert skipped[0]["status"] == "skipped"

    def test_nonexistent_profile_returns_none(self):
        """Requesting a non-existent profile returns None (for 404 response)."""
        engine = OnboardingAutomationEngine()
        result = engine.get_profile("nonexistent-id")
        assert result is None

    def test_complete_task_nonexistent_returns_none(self):
        """Completing a task on non-existent profile returns None (for 404)."""
        engine = OnboardingAutomationEngine()
        result = engine.complete_task("nonexistent-id", "task-xxx")
        assert result is None

    def test_full_onboarding_lifecycle(self):
        """Test the complete employee onboarding lifecycle via API contract."""
        engine = OnboardingAutomationEngine()

        # Create
        profile = engine.create_onboarding(
            employee_name="Dave",
            role="backend engineer",
            department="engineering",
            mentor="Senior Dev",
        )
        assert profile.status == OnboardingStatus.CREATED

        # List
        profiles = engine.list_profiles()
        assert len(profiles) == 1
        assert profiles[0]["employee_name"] == "Dave"

        # Complete all tasks
        for task in profile.tasks:
            engine.complete_task(profile.profile_id, task.task_id)

        # Verify completed
        final = engine.get_profile(profile.profile_id)
        assert final["status"] == "completed"
        assert final["progress_pct"] == 100.0

        # Status
        status = engine.get_status()
        assert status["total_profiles"] == 1
        assert status["by_status"].get("completed", 0) == 1


# ---------------------------------------------------------------------------
# Test: Integration of wizard + onboarding
# ---------------------------------------------------------------------------

class TestNoCodeOnboardingIntegration:
    """Test that both systems can work together."""

    def test_wizard_and_engine_independent(self):
        """Wizard and engine can be instantiated independently."""
        wiz = SetupWizard()
        engine = OnboardingAutomationEngine()
        assert wiz is not None
        assert engine is not None

    def test_wizard_generates_config_engine_creates_profiles(self):
        """Wizard config and engine profiles are independent workflows."""
        wiz = SetupWizard()
        wiz.apply_answer("q1", "Acme Corp")
        config = wiz.generate_config(wiz.get_profile())

        engine = OnboardingAutomationEngine()
        profile = engine.create_onboarding("New Hire", "dev", "engineering")

        # Both produce valid data
        assert config["organization"]["name"] == "Acme Corp"
        assert profile.employee_name == "New Hire"
