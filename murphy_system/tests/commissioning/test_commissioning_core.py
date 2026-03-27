"""
Murphy System — Core Commissioning Tests
Owner: @test-lead
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Tests the commissioning infrastructure itself: Murphy user simulation,
screenshot capture, log validation, and state validation.
Validates that the commissioning framework is functional before running
higher-level business process and architecture tests.
"""

import pytest
from pathlib import Path

from tests.commissioning.murphy_user_simulator import (
    ActionResult,
    MurphyUserSimulator,
    UserRole,
)
from tests.commissioning.screenshot_manager import ScreenshotManager
from tests.commissioning.log_validator import LogValidator
from tests.commissioning.state_validator import StateValidator


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.1 — Murphy User Simulator Tests
# Owner: @test-lead | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


class TestMurphyUserSimulator:
    """Validates the Murphy user simulation system."""

    def test_murphy_user_creation(self):
        """@test-lead: Verify Murphy user is created with correct defaults."""
        murphy = MurphyUserSimulator()
        assert murphy.name == "Murphy"
        assert murphy.email == "murphy@murphysystem.ai"
        assert murphy.role == UserRole.ADMIN
        assert murphy.authenticated is False

    def test_murphy_login(self):
        """@test-lead: Verify Murphy can authenticate."""
        murphy = MurphyUserSimulator()
        result = murphy.login()
        assert result == ActionResult.SUCCESS
        assert murphy.authenticated is True
        assert murphy.current_section == "dashboard"

    def test_murphy_navigation(self):
        """@test-lead: Verify Murphy can navigate between sections."""
        murphy = MurphyUserSimulator()
        murphy.login()

        result = murphy.navigate_to("automation")
        assert result == ActionResult.SUCCESS
        assert murphy.current_section == "automation"

    def test_murphy_navigation_denied_without_login(self):
        """@test-lead: Verify unauthenticated navigation is denied."""
        murphy = MurphyUserSimulator()
        result = murphy.navigate_to("automation")
        assert result == ActionResult.DENIED

    def test_murphy_task_execution(self):
        """@test-lead: Verify Murphy can execute tasks."""
        murphy = MurphyUserSimulator()
        murphy.login()
        murphy.navigate_to("automation")

        result = murphy.execute_task("generate_report", {
            "type": "weekly",
            "format": "pdf",
        })
        assert result == ActionResult.SUCCESS

    def test_murphy_self_automation_enable(self):
        """@test-lead: Verify Murphy can enable self-automation mode."""
        murphy = MurphyUserSimulator()
        murphy.login()

        result = murphy.enable_self_automation(
            mode="semi_autonomous", risk_level="medium"
        )
        assert result == ActionResult.SUCCESS
        assert murphy.system_state["self_automation"]["enabled"] is True
        assert murphy.system_state["self_automation"]["mode"] == "semi_autonomous"

    def test_murphy_result_verification(self):
        """@test-lead: Verify result verification works correctly."""
        murphy = MurphyUserSimulator()
        murphy.login()
        murphy.enable_self_automation()

        assert murphy.verify_result({"enabled": True, "mode": "semi_autonomous"})

    def test_murphy_session_summary(self):
        """@test-lead: Verify session summary captures all actions."""
        murphy = MurphyUserSimulator()
        murphy.login()
        murphy.navigate_to("automation")
        murphy.execute_task("test_task", {"param": "value"})

        summary = murphy.get_session_summary()
        assert summary["total_actions"] == 3
        assert summary["successful_actions"] == 3
        assert summary["authenticated"] is True

    def test_murphy_full_commissioning_workflow(self):
        """@test-lead: End-to-end commissioning workflow."""
        murphy = MurphyUserSimulator()

        # Step 1: Login
        murphy.login("http://localhost:8000")
        assert murphy.authenticated

        # Step 2: Navigate to self-automation
        murphy.navigate_to("self-automation")
        assert murphy.current_section == "self-automation"

        # Step 3: Enable self-automation
        murphy.enable_self_automation(mode="semi_autonomous", risk_level="medium")
        assert murphy.system_state["self_automation"]["enabled"]

        # Step 4: Execute automation task
        murphy.navigate_to("automation")
        murphy.execute_task("generate_report", {"type": "weekly", "format": "pdf"})

        # Step 5: Verify session
        summary = murphy.get_session_summary()
        assert summary["total_actions"] == 5
        assert summary["failed_actions"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.2 — Screenshot Manager Tests
# Owner: @test-lead | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


class TestScreenshotManager:
    """Validates the screenshot capture and visual regression system."""

    def test_screenshot_capture(self, sandbox):
        """@test-lead: Verify screenshots can be captured."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))

        filepath = manager.capture("dashboard", "loaded", "<html>Dashboard</html>")
        assert filepath.exists()
        assert "dashboard_loaded" in filepath.name

    def test_baseline_set_and_compare(self, sandbox):
        """@test-lead: Verify baseline comparison works."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))
        content = "<html><body>Baseline Content</body></html>"

        manager.set_baseline("dashboard", content)
        matches, diff = manager.compare_to_baseline("dashboard", content)
        assert matches is True
        assert diff is None

    def test_visual_regression_detected(self, sandbox):
        """@test-lead: Verify visual regression is detected."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))
        original = "<html><body>Original</body></html>"
        modified = "<html><body>Modified</body></html>"

        manager.set_baseline("page", original)
        matches, diff = manager.compare_to_baseline("page", modified)
        assert matches is False
        assert "Visual regression detected" in diff

    def test_no_baseline_returns_false(self, sandbox):
        """@test-lead: Verify missing baseline is handled."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))
        matches, diff = manager.compare_to_baseline("nonexistent", "content")
        assert matches is False
        assert "No baseline found" in diff

    def test_capture_history(self, sandbox):
        """@test-lead: Verify capture history is tracked."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))

        manager.capture("page1", "step1", "<html>1</html>")
        manager.capture("page2", "step2", "<html>2</html>")

        history = manager.get_capture_history()
        assert len(history) == 2

    def test_report_generation(self, sandbox):
        """@test-lead: Verify report generation."""
        manager = ScreenshotManager(base_dir=str(sandbox / "screenshots"))
        content = "<html>Test</html>"

        manager.set_baseline("page", content)
        manager.capture("page", "check", content)
        manager.capture("other", "check", "<html>Other</html>")

        report = manager.generate_report()
        assert report["total_captures"] == 2
        assert report["total_baselines"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.3 — Log Validator Tests
# Owner: @sec-eng | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


class TestLogValidator:
    """Validates the audit log validation system."""

    def test_write_and_load_logs(self, persistence_sandbox):
        """@sec-eng: Verify logs can be written and loaded."""
        log_file = persistence_sandbox / "audit" / "audit.log"
        validator = LogValidator(log_file=str(log_file))

        validator.write_log_entry("LOGIN", user="Murphy", details="User logged in")
        validator.write_log_entry("EXECUTE", user="Murphy", details="Ran task")

        count = validator.load_logs()
        assert count == 2

    def test_validate_action_logged(self, persistence_sandbox):
        """@sec-eng: Verify action validation works."""
        log_file = persistence_sandbox / "audit" / "audit.log"
        validator = LogValidator(log_file=str(log_file))

        validator.write_log_entry("LOGIN", user="Murphy", details="Session start")
        validator.load_logs()

        matches = validator.validate_action_logged("LOGIN", "Murphy")
        assert len(matches) >= 1

    def test_validate_missing_action_raises(self, persistence_sandbox):
        """@sec-eng: Verify missing action raises assertion."""
        log_file = persistence_sandbox / "audit" / "audit.log"
        validator = LogValidator(log_file=str(log_file))

        validator.write_log_entry("LOGIN", user="Murphy")
        validator.load_logs()

        with pytest.raises(AssertionError):
            validator.validate_action_logged("NONEXISTENT", "Murphy")

    def test_validate_state_change(self, persistence_sandbox):
        """@sec-eng: Verify state change validation."""
        log_file = persistence_sandbox / "audit" / "audit.log"
        validator = LogValidator(log_file=str(log_file))

        validator.write_log_entry(
            "STATE_CHANGE",
            user="system",
            details="SalesEngine: inactive → active",
        )
        validator.load_logs()

        matches = validator.validate_state_change("SalesEngine", "inactive", "active")
        assert len(matches) >= 1

    def test_validate_no_errors(self, persistence_sandbox):
        """@sec-eng: Verify no-error validation passes for clean logs."""
        log_file = persistence_sandbox / "audit" / "audit.log"
        validator = LogValidator(log_file=str(log_file))

        validator.write_log_entry("LOGIN", user="Murphy", level="INFO")
        validator.load_logs()

        assert validator.validate_no_errors() is True


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.4 — State Validator Tests
# Owner: @sec-eng | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


class TestStateValidator:
    """Validates the state persistence and integrity system."""

    def test_load_and_save_state(self, persistence_sandbox):
        """@sec-eng: Verify state can be loaded and saved."""
        state_file = persistence_sandbox / "state.json"
        validator = StateValidator(state_file=str(state_file))

        validator.load_state()
        assert validator.state["system_version"] == "1.0.0"

    def test_component_state_management(self, persistence_sandbox):
        """@sec-eng: Verify component state can be set and validated."""
        state_file = persistence_sandbox / "state.json"
        validator = StateValidator(state_file=str(state_file))
        validator.load_state()

        validator.set_component_state("SalesEngine", {
            "status": "active",
            "leads_processed": 42,
        })

        assert validator.validate_component_state("SalesEngine", {
            "status": "active",
            "leads_processed": 42,
        })

    def test_automation_state_management(self, persistence_sandbox):
        """@sec-eng: Verify automation state persistence."""
        state_file = persistence_sandbox / "state.json"
        validator = StateValidator(state_file=str(state_file))
        validator.load_state()

        validator.set_automation_state("self_improvement", {
            "enabled": True,
            "mode": "semi_autonomous",
        })

        assert validator.validate_automation_enabled("self_improvement")

    def test_state_integrity_check(self, persistence_sandbox):
        """@sec-eng: Verify integrity check identifies issues."""
        state_file = persistence_sandbox / "state.json"
        validator = StateValidator(state_file=str(state_file))
        validator.load_state()

        results = validator.validate_state_integrity()
        assert len(results["passed"]) > 0

    def test_improvement_history(self, persistence_sandbox):
        """@sec-eng: Verify self-improvement history tracking."""
        state_file = persistence_sandbox / "state.json"
        validator = StateValidator(state_file=str(state_file))
        validator.load_state()

        validator.record_improvement({
            "type": "performance",
            "description": "Optimized query cache",
            "metric_before": 100,
            "metric_after": 50,
        })

        history = validator.get_improvement_history()
        assert len(history) == 1
        assert history[0]["type"] == "performance"

    def test_state_persistence_round_trip(self, persistence_sandbox):
        """@sec-eng: Verify state survives save/load round trip."""
        state_file = persistence_sandbox / "state.json"

        # Save state
        validator1 = StateValidator(state_file=str(state_file))
        validator1.load_state()
        validator1.set_component_state("TestComponent", {"status": "running"})
        validator1.save_state()

        # Load in new validator
        validator2 = StateValidator(state_file=str(state_file))
        validator2.load_state()
        assert validator2.validate_component_state("TestComponent", {
            "status": "running",
        })
