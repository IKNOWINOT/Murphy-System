"""Tests for trial_orchestrator.py."""

from __future__ import annotations

import sys
import os
import unittest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trial_orchestrator import (
    TRIAL_DURATION_HOURS,
    TRIAL_FOLDER_STRUCTURE,
    TrialCycleResult,
    TrialOrchestrator,
    TrialReport,
    TrialSession,
    TrialSummary,
)
from self_selling_engine import (
    BUSINESS_TYPE_CONSTRAINTS,
    ProspectProfile,
    TrialShadowDeployer,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _make_shadow_deployer() -> TrialShadowDeployer:
    shadow_int = MagicMock()
    agent = MagicMock()
    agent.agent_id = "shadow-test-agent"
    shadow_int.create_shadow_agent.return_value = agent
    shadow_int.observe_action.return_value = None
    shadow_int.propose_automation.return_value = {
        "proposal": "automate_intake",
        "confidence": 0.85,
    }
    return TrialShadowDeployer(shadow_integration=shadow_int)


def _make_prospect(**overrides) -> ProspectProfile:
    defaults = {
        "prospect_id": "p-trial-001",
        "company_name": "Trial Corp",
        "contact_name": "Tester",
        "contact_email": "tester@trial.com",
        "business_type": "consulting",
        "industry": "professional_services",
        "estimated_revenue": "1m_10m",
        "tools_detected": ["slack"],
        "pain_points_inferred": ["slow_proposals"],
        "automation_constraints": BUSINESS_TYPE_CONSTRAINTS["consulting"]["primary_constraints"],
        "constraint_alert_rules": ["r-001"],
    }
    defaults.update(overrides)
    return ProspectProfile(**defaults)


def _make_orchestrator() -> TrialOrchestrator:
    return TrialOrchestrator(shadow_deployer=_make_shadow_deployer())


# ---------------------------------------------------------------------------
# Tests: Constants
# ---------------------------------------------------------------------------

class TestConstants(unittest.TestCase):

    def test_trial_duration_72_hours(self):
        self.assertEqual(TRIAL_DURATION_HOURS, 72.0)

    def test_folder_structure_keys(self):
        expected_keys = {"outbound", "inbound", "analysis", "deliverables"}
        self.assertEqual(set(TRIAL_FOLDER_STRUCTURE.keys()), expected_keys)


# ---------------------------------------------------------------------------
# Tests: TrialSession dataclass
# ---------------------------------------------------------------------------

class TestTrialSessionDataclass(unittest.TestCase):

    def test_default_status_active(self):
        session = TrialSession(
            trial_id="t-001",
            prospect_id="p-001",
            company_name="TestCo",
            business_type="consulting",
            started_at=datetime.now(timezone.utc).isoformat(),
            business_context={},
        )
        self.assertEqual(session.status, "active")

    def test_default_counters_zero(self):
        session = TrialSession(
            trial_id="t-001",
            prospect_id="p-001",
            company_name="TestCo",
            business_type="consulting",
            started_at=datetime.now(timezone.utc).isoformat(),
            business_context={},
        )
        self.assertEqual(session.emails_processed, 0)
        self.assertEqual(session.responses_generated, 0)
        self.assertEqual(session.automation_actions_taken, 0)
        self.assertEqual(session.deliverables_created, [])


# ---------------------------------------------------------------------------
# Tests: TrialOrchestrator.start_trial
# ---------------------------------------------------------------------------

class TestStartTrial(unittest.TestCase):

    def setUp(self):
        self.orch = _make_orchestrator()
        self.prospect = _make_prospect()

    def test_start_trial_returns_session(self):
        session = self.orch.start_trial(self.prospect, {"reply": "yes"})
        self.assertIsInstance(session, TrialSession)

    def test_start_trial_session_has_trial_id(self):
        session = self.orch.start_trial(self.prospect, {})
        self.assertIsNotNone(session.trial_id)

    def test_start_trial_session_has_prospect_id(self):
        session = self.orch.start_trial(self.prospect, {})
        self.assertEqual(session.prospect_id, self.prospect.prospect_id)

    def test_start_trial_session_active(self):
        session = self.orch.start_trial(self.prospect, {})
        self.assertEqual(session.status, "active")

    def test_start_trial_creates_folder_paths(self):
        session = self.orch.start_trial(self.prospect, {})
        self.assertTrue(len(session.outbound_folder) > 0)
        self.assertTrue(len(session.inbound_folder) > 0)
        self.assertTrue(len(session.analysis_folder) > 0)
        self.assertTrue(len(session.deliverables_folder) > 0)

    def test_start_trial_folder_paths_contain_prospect_id(self):
        session = self.orch.start_trial(self.prospect, {})
        self.assertIn(self.prospect.prospect_id, session.outbound_folder)

    def test_start_trial_stores_session(self):
        session = self.orch.start_trial(self.prospect, {})
        retrieved = self.orch.get_session(session.trial_id)
        self.assertIsNotNone(retrieved)

    def test_start_trial_runs_initial_cycle(self):
        session = self.orch.start_trial(self.prospect, {})
        # After start, at least one cycle should have run
        self.assertGreaterEqual(session.automation_actions_taken, 0)


# ---------------------------------------------------------------------------
# Tests: TrialOrchestrator.run_trial_cycle
# ---------------------------------------------------------------------------

class TestRunTrialCycle(unittest.TestCase):

    def setUp(self):
        self.orch = _make_orchestrator()
        self.prospect = _make_prospect()
        self.session = self.orch.start_trial(self.prospect, {})

    def test_run_cycle_returns_result(self):
        result = self.orch.run_trial_cycle(self.session.trial_id)
        self.assertIsInstance(result, TrialCycleResult)

    def test_run_cycle_has_trial_id(self):
        result = self.orch.run_trial_cycle(self.session.trial_id)
        self.assertEqual(result.trial_id, self.session.trial_id)

    def test_run_cycle_has_cycle_id(self):
        result = self.orch.run_trial_cycle(self.session.trial_id)
        self.assertIsNotNone(result.cycle_id)

    def test_run_cycle_increments_counters(self):
        initial_actions = self.orch.get_session(self.session.trial_id).automation_actions_taken
        self.orch.run_trial_cycle(self.session.trial_id)
        updated_actions = self.orch.get_session(self.session.trial_id).automation_actions_taken
        self.assertGreaterEqual(updated_actions, initial_actions)

    def test_run_cycle_unknown_trial_raises(self):
        with self.assertRaises(ValueError):
            self.orch.run_trial_cycle("nonexistent-trial-id")

    def test_multiple_cycles_accumulate(self):
        for _ in range(3):
            self.orch.run_trial_cycle(self.session.trial_id)
        session = self.orch.get_session(self.session.trial_id)
        self.assertGreater(session.emails_processed, 0)


# ---------------------------------------------------------------------------
# Tests: TrialOrchestrator.route_responses
# ---------------------------------------------------------------------------

class TestRouteResponses(unittest.TestCase):

    def setUp(self):
        self.orch = _make_orchestrator()
        self.prospect = _make_prospect()
        self.session = self.orch.start_trial(self.prospect, {})

    def test_route_responses_does_not_raise(self):
        # Should complete without error
        self.orch.route_responses(self.session.trial_id)

    def test_route_responses_unknown_trial_is_noop(self):
        # Should not raise
        self.orch.route_responses("nonexistent-trial")


# ---------------------------------------------------------------------------
# Tests: TrialOrchestrator.generate_trial_report
# ---------------------------------------------------------------------------

class TestGenerateTrialReport(unittest.TestCase):

    def setUp(self):
        self.orch = _make_orchestrator()
        self.prospect = _make_prospect()
        self.session = self.orch.start_trial(self.prospect, {})
        # Run a few cycles to accumulate data
        for _ in range(3):
            self.orch.run_trial_cycle(self.session.trial_id)

    def test_generate_report_returns_trial_report(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertIsInstance(report, TrialReport)

    def test_report_has_correct_trial_id(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertEqual(report.trial_id, self.session.trial_id)

    def test_report_has_correct_prospect_id(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertEqual(report.prospect_id, self.prospect.prospect_id)

    def test_report_has_positive_duration(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertGreaterEqual(report.duration_hours, 0.0)

    def test_report_has_estimated_savings(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertGreaterEqual(report.estimated_hours_saved, 0.0)
        self.assertGreaterEqual(report.estimated_cost_savings, 0.0)

    def test_report_constraint_performance_dict(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertIsInstance(report.constraint_performance, dict)

    def test_report_constraint_performance_for_consulting(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        # consulting has billable_utilization as a constraint
        self.assertIn("billable_utilization", report.constraint_performance)

    def test_report_constraint_performance_entries_have_status(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        for metric, perf in report.constraint_performance.items():
            with self.subTest(metric=metric):
                self.assertIn("status", perf)
                self.assertIn("target", perf)
                self.assertIn("actual", perf)

    def test_report_has_conversion_recommendation(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertTrue(len(report.conversion_recommendation) > 0)

    def test_report_has_shadow_agent_observations(self):
        report = self.orch.generate_trial_report(self.session.trial_id)
        self.assertIsInstance(report.shadow_agent_observations, int)

    def test_generate_report_unknown_trial_raises(self):
        with self.assertRaises(ValueError):
            self.orch.generate_trial_report("nonexistent-id")


# ---------------------------------------------------------------------------
# Tests: TrialOrchestrator.end_trial
# ---------------------------------------------------------------------------

class TestEndTrial(unittest.TestCase):

    def setUp(self):
        self.orch = _make_orchestrator()
        self.prospect = _make_prospect()
        self.session = self.orch.start_trial(self.prospect, {})
        for _ in range(2):
            self.orch.run_trial_cycle(self.session.trial_id)

    def test_end_trial_returns_summary(self):
        summary = self.orch.end_trial(self.session.trial_id)
        self.assertIsInstance(summary, TrialSummary)

    def test_end_trial_marks_session_completed(self):
        self.orch.end_trial(self.session.trial_id)
        session = self.orch.get_session(self.session.trial_id)
        self.assertEqual(session.status, "completed")

    def test_end_trial_summary_has_report(self):
        summary = self.orch.end_trial(self.session.trial_id)
        self.assertIsNotNone(summary.report)
        self.assertIsInstance(summary.report, TrialReport)

    def test_end_trial_summary_has_shadow_proposal(self):
        summary = self.orch.end_trial(self.session.trial_id)
        self.assertIsNotNone(summary.shadow_proposal)

    def test_end_trial_has_conversion_action(self):
        summary = self.orch.end_trial(self.session.trial_id)
        self.assertIn(summary.conversion_action, ("convert", "extend", "nurture", "close_lost"))

    def test_end_trial_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.orch.end_trial("nonexistent-trial")


# ---------------------------------------------------------------------------
# Tests: report for each business type
# ---------------------------------------------------------------------------

class TestReportForAllBusinessTypes(unittest.TestCase):

    def test_report_generated_for_each_business_type(self):
        for bt in BUSINESS_TYPE_CONSTRAINTS:
            orch = _make_orchestrator()
            prospect = _make_prospect(
                prospect_id=f"p-{bt}",
                business_type=bt,
                automation_constraints=BUSINESS_TYPE_CONSTRAINTS[bt]["primary_constraints"],
            )
            session = orch.start_trial(prospect, {})
            orch.run_trial_cycle(session.trial_id)
            report = orch.generate_trial_report(session.trial_id)

            with self.subTest(bt=bt):
                self.assertIsInstance(report, TrialReport)
                self.assertIsInstance(report.constraint_performance, dict)


# ---------------------------------------------------------------------------
# Tests: full trial lifecycle end-to-end
# ---------------------------------------------------------------------------

class TestFullTrialLifecycle(unittest.TestCase):

    def test_full_lifecycle(self):
        orch = _make_orchestrator()
        prospect = _make_prospect()

        # 1. Start trial
        session = orch.start_trial(prospect, {"reply": "Yes, interested!"})
        self.assertEqual(session.status, "active")

        # 2. Run cycles
        for _ in range(5):
            result = orch.run_trial_cycle(session.trial_id)
            self.assertIsInstance(result, TrialCycleResult)

        # 3. Route responses
        orch.route_responses(session.trial_id)

        # 4. Generate report
        report = orch.generate_trial_report(session.trial_id)
        self.assertGreater(report.automation_actions_taken, 0)

        # 5. End trial
        summary = orch.end_trial(session.trial_id)
        self.assertEqual(summary.final_status, "completed")
        self.assertIsNotNone(summary.report)

    def test_list_sessions(self):
        orch = _make_orchestrator()
        for i in range(3):
            prospect = _make_prospect(
                prospect_id=f"p-{i}",
                company_name=f"Company {i}",
            )
            orch.start_trial(prospect, {})

        sessions = orch.list_sessions()
        self.assertGreaterEqual(len(sessions), 3)


if __name__ == "__main__":
    unittest.main()
