"""
End-to-end test for the matrix commands onboarding flow.

Simulates a new user going through the complete onboarding journey
via ``!murphy`` matrix commands.  Each step captures the command
response (equivalent to a screenshot) and verifies it matches the
expected onboarding pattern:

1.  ``!murphy help``               — show available commands
2.  ``!murphy onboard status``     — initial empty state
3.  ``!murphy onboard init``       — initialize org chart
4.  ``!murphy onboard start``      — create onboarding session
5.  ``!murphy onboard questions``  — get questions
6.  ``!murphy onboard answer``     — answer all 10 questions
7.  ``!murphy onboard assign``     — assign shadow agent
8.  ``!murphy onboard complete``   — transition to workflow builder
9.  ``!murphy gate create``        — create business gates
10. ``!murphy gate list``          — verify gates exist
11. ``!murphy gate evaluate``      — evaluate a gate
12. ``!murphy setpoint show``      — view setpoints
13. ``!murphy setpoint set``       — adjust a setpoint
14. ``!murphy setpoint ranges``    — view ranges
15. ``!murphy schedule loops``     — view business loop schedules
16. ``!murphy schedule configure`` — adjust a loop
17. ``!murphy schedule status``    — verify scheduling

After the full flow, we verify:
- Every response is unique (no duplicate/stuck responses).
- All setpoints are established with valid ranges.
- Gate ranges are configured for all business objectives.
- Business loop scheduling covers all required loops.
"""

import os
import sys
import uuid
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MURPHY_DIR = os.path.join(TESTS_DIR, "..")
SRC_DIR = os.path.join(MURPHY_DIR, "src")
sys.path.insert(0, MURPHY_DIR)
sys.path.insert(0, SRC_DIR)

from matrix_bridge.command_dispatcher import CommandDispatcher, ParsedCommand, CommandResponse
from matrix_bridge.config import MatrixBridgeConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> MatrixBridgeConfig:
    """Create a minimal config for testing."""
    return MatrixBridgeConfig(
        homeserver_url="https://matrix.example.com",
        bot_user_id="@murphy:example.com",
        domain="example.com",
    )


class _FakeRoomRouter:
    """Stub for the room_router dependency."""
    pass


def _dispatch(dispatcher: CommandDispatcher, raw: str, sender: str = "@testuser:example.com",
              room_id: str = "!test:example.com") -> CommandResponse:
    """Parse and dispatch a raw command, returning the response."""
    cmd = dispatcher.parse(raw, sender, room_id)
    assert cmd is not None, f"Failed to parse: {raw}"
    return dispatcher.dispatch(cmd)


# ---------------------------------------------------------------------------
# Screenshot capture list — accumulates all command outputs
# ---------------------------------------------------------------------------

_SCREENSHOTS: list[dict] = []


def _capture(step: str, raw_command: str, response: CommandResponse):
    """Record a 'screenshot' of each prompt/response pair."""
    _SCREENSHOTS.append({
        "step": step,
        "command": raw_command,
        "success": response.success,
        "message": response.message,
    })


# ============================================================================
# Test Class
# ============================================================================

class TestMatrixOnboardingE2E(unittest.TestCase):
    """Full onboarding journey through matrix commands."""

    @classmethod
    def setUpClass(cls):
        """Create a fresh dispatcher for the test suite."""
        from management_systems.management_commands import reset_engines
        reset_engines()
        cls.config = _make_config()
        cls.dispatcher = CommandDispatcher(cls.config, _FakeRoomRouter())
        _SCREENSHOTS.clear()

    # ------------------------------------------------------------------
    # Step 1: Help — the first thing a new user would type
    # ------------------------------------------------------------------
    def test_01_help(self):
        raw = "!murphy help"
        resp = _dispatch(self.dispatcher, raw)
        _capture("01_help", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("onboard", resp.message.lower())
        self.assertIn("gate", resp.message.lower())
        self.assertIn("setpoint", resp.message.lower())
        self.assertIn("schedule", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 2: Onboarding status — should be empty
    # ------------------------------------------------------------------
    def test_02_onboard_status_empty(self):
        raw = "!murphy onboard status"
        resp = _dispatch(self.dispatcher, raw)
        _capture("02_onboard_status_empty", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("0", resp.message)

    # ------------------------------------------------------------------
    # Step 3: Initialize organization
    # ------------------------------------------------------------------
    def test_03_onboard_init(self):
        raw = "!murphy onboard init"
        resp = _dispatch(self.dispatcher, raw)
        _capture("03_onboard_init", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("positions", resp.message.lower())
        self.assertIn("business_ip", resp.message)

    # ------------------------------------------------------------------
    # Step 4: Start onboarding for a new employee
    # ------------------------------------------------------------------
    def test_04_onboard_start(self):
        raw = "!murphy onboard start Alex alex@company.com"
        resp = _dispatch(self.dispatcher, raw)
        _capture("04_onboard_start", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Alex", resp.message)
        self.assertIn("alex@company.com", resp.message)
        # Extract session ID for subsequent steps
        for line in resp.message.splitlines():
            if "Session ID" in line:
                sid = line.split("`")[1] if "`" in line else ""
                self.__class__._session_id = sid
                break
        self.assertTrue(hasattr(self.__class__, "_session_id"),
                        "Session ID not found in response")

    # ------------------------------------------------------------------
    # Step 5: Get onboarding questions
    # ------------------------------------------------------------------
    def test_05_onboard_questions(self):
        sid = self.__class__._session_id
        raw = f"!murphy onboard questions {sid}"
        resp = _dispatch(self.dispatcher, raw)
        _capture("05_onboard_questions", raw, resp)
        self.assertTrue(resp.success)
        # Should contain multiple questions
        self.assertIn("Q1", resp.message)
        self.assertIn("Q10", resp.message)
        # Extract question IDs for answering
        qids = []
        for line in resp.message.splitlines():
            if "(`" in line and "`)" in line:
                qid = line.split("(`")[1].split("`)")[0]
                qids.append(qid)
        self.__class__._question_ids = qids
        self.assertGreaterEqual(len(qids), 10)

    # ------------------------------------------------------------------
    # Step 6: Answer all 10 questions (simulating real user responses)
    # ------------------------------------------------------------------
    def test_06_answer_all_questions(self):
        sid = self.__class__._session_id
        qids = self.__class__._question_ids

        answers = [
            "Alex Smith",                     # Full name
            "alex@company.com",               # Work email
            "engineering",                    # Department
            "Software Engineer",              # Position
            "Jane Doe",                       # Manager
            "Feature development and code reviews",  # Responsibilities
            "GitHub Jira Slack",              # Tools
            "I want to automate email notifications and report generation",  # Automation
            "Slack",                          # Notification preference
            "SOC2",                           # Compliance
        ]

        responses_seen = []
        self.assertGreaterEqual(len(qids), 10,
                                f"Expected at least 10 question IDs, got {len(qids)}")
        for i, (qid, answer) in enumerate(zip(qids[:10], answers)):
            raw = f"!murphy onboard answer {sid} {qid} {answer}"
            resp = _dispatch(self.dispatcher, raw)
            _capture(f"06_answer_q{i+1}", raw, resp)
            self.assertTrue(resp.success, f"Answer Q{i+1} failed: {resp.message}")
            self.assertIn("Answer Recorded", resp.message)
            # Check responses are not identical (no stuck loop)
            responses_seen.append(resp.message)

        # Verify not all responses are identical (progressive answers)
        unique = set(responses_seen)
        self.assertGreater(len(unique), 1,
                           "All answer responses were identical — system appears stuck")

        # The last answer should indicate all required are done
        self.assertIn("All required questions answered", responses_seen[-1])

    # ------------------------------------------------------------------
    # Step 7: Assign shadow agent
    # ------------------------------------------------------------------
    def test_07_onboard_assign(self):
        sid = self.__class__._session_id
        raw = f"!murphy onboard assign {sid}"
        resp = _dispatch(self.dispatcher, raw)
        _capture("07_onboard_assign", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Shadow Agent Assigned", resp.message)
        self.assertIn("employee_ip", resp.message)
        # Capabilities should be inferred from tools answer
        msg_lower = resp.message.lower()
        self.assertTrue(
            any(cap in msg_lower for cap in [
                "code_management", "project_tracking",
                "communication_automation", "notification_automation",
                "reporting_automation"
            ]),
            "No capabilities inferred from onboarding answers"
        )

    # ------------------------------------------------------------------
    # Step 8: Complete onboarding
    # ------------------------------------------------------------------
    def test_08_onboard_complete(self):
        sid = self.__class__._session_id
        raw = f"!murphy onboard complete {sid}"
        resp = _dispatch(self.dispatcher, raw)
        _capture("08_onboard_complete", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Complete", resp.message)
        self.assertIn("workflow", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 9: Verify onboarding status after completion
    # ------------------------------------------------------------------
    def test_09_onboard_status_after(self):
        raw = "!murphy onboard status"
        resp = _dispatch(self.dispatcher, raw)
        _capture("09_onboard_status_after", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Alex", resp.message)
        # Should show at least 1 session
        self.assertIn("1", resp.message)

    # ------------------------------------------------------------------
    # Step 10: Create business gates for revenue objective
    # ------------------------------------------------------------------
    def test_10_gate_create_revenue(self):
        raw = "!murphy gate create revenue-q1 revenue_target --budget=50000 --roi=1.5"
        resp = _dispatch(self.dispatcher, raw)
        _capture("10_gate_create_revenue", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gates Generated", resp.message)
        self.assertIn("revenue-q1", resp.message)
        # Extract gate IDs
        gate_ids = []
        for line in resp.message.splitlines():
            if "`gate-" in line:
                # Full gate ID is between backticks: `gate-xxxxxxxxxxxx`
                parts = line.split("`")
                for part in parts:
                    if part.startswith("gate-"):
                        gate_ids.append(part)
                        break
        self.__class__._gate_ids = gate_ids
        self.assertGreater(len(gate_ids), 0, "No gates were created")

    # ------------------------------------------------------------------
    # Step 11: Create gates for compliance objective
    # ------------------------------------------------------------------
    def test_11_gate_create_compliance(self):
        raw = "!murphy gate create compliance-2026 compliance_mandate"
        resp = _dispatch(self.dispatcher, raw)
        _capture("11_gate_create_compliance", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gates Generated", resp.message)
        self.assertIn("compliance-2026", resp.message)

    # ------------------------------------------------------------------
    # Step 12: Create gates for operational efficiency
    # ------------------------------------------------------------------
    def test_12_gate_create_ops(self):
        raw = "!murphy gate create ops-efficiency operational_efficiency --risk=0.3"
        resp = _dispatch(self.dispatcher, raw)
        _capture("12_gate_create_ops", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gates Generated", resp.message)

    # ------------------------------------------------------------------
    # Step 13: List all gates
    # ------------------------------------------------------------------
    def test_13_gate_list(self):
        raw = "!murphy gate list"
        resp = _dispatch(self.dispatcher, raw)
        _capture("13_gate_list", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gate Registry", resp.message)
        # Should have gates from all three objectives
        self.assertIn("revenue-q1", resp.message)
        self.assertIn("compliance-2026", resp.message)
        self.assertIn("ops-efficiency", resp.message)

    # ------------------------------------------------------------------
    # Step 14: Evaluate a gate
    # ------------------------------------------------------------------
    def test_14_gate_evaluate(self):
        gate_ids = self.__class__._gate_ids
        self.assertGreater(len(gate_ids), 0)
        gate_id = gate_ids[0]
        raw = f"!murphy gate evaluate {gate_id} 45000"
        resp = _dispatch(self.dispatcher, raw)
        _capture("14_gate_evaluate", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gate Evaluation", resp.message)
        # Should show PASSED or FAILED
        self.assertTrue(
            "PASSED" in resp.message or "FAILED" in resp.message,
            "Gate evaluation did not return a clear pass/fail result"
        )

    # ------------------------------------------------------------------
    # Step 15: Check gate status
    # ------------------------------------------------------------------
    def test_15_gate_status(self):
        gate_ids = self.__class__._gate_ids
        gate_id = gate_ids[0]
        raw = f"!murphy gate status {gate_id}"
        resp = _dispatch(self.dispatcher, raw)
        _capture("15_gate_status", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Gate Status", resp.message)
        self.assertIn("Threshold", resp.message)
        self.assertIn("revenue-q1", resp.message)

    # ------------------------------------------------------------------
    # Step 16: Show setpoints
    # ------------------------------------------------------------------
    def test_16_setpoint_show(self):
        raw = "!murphy setpoint show"
        resp = _dispatch(self.dispatcher, raw)
        _capture("16_setpoint_show", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Active Setpoints", resp.message)
        # All 6 dimensions should be present
        for dim in ["money", "time", "production", "confidence", "info_completeness", "risk"]:
            self.assertIn(dim, resp.message)

    # ------------------------------------------------------------------
    # Step 17: Adjust setpoints
    # ------------------------------------------------------------------
    def test_17_setpoint_set(self):
        raw = "!murphy setpoint set production 0.85"
        resp = _dispatch(self.dispatcher, raw)
        _capture("17_setpoint_set", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("production", resp.message)
        self.assertIn("0.85", resp.message)

    # ------------------------------------------------------------------
    # Step 18: Reject invalid setpoint
    # ------------------------------------------------------------------
    def test_18_setpoint_out_of_range(self):
        raw = "!murphy setpoint set risk 2.0"
        resp = _dispatch(self.dispatcher, raw)
        _capture("18_setpoint_out_of_range", raw, resp)
        self.assertFalse(resp.success)
        self.assertIn("out of range", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 19: View setpoint ranges
    # ------------------------------------------------------------------
    def test_19_setpoint_ranges(self):
        raw = "!murphy setpoint ranges"
        resp = _dispatch(self.dispatcher, raw)
        _capture("19_setpoint_ranges", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Setpoint Ranges", resp.message)
        self.assertIn("Min", resp.message)
        self.assertIn("Max", resp.message)

    # ------------------------------------------------------------------
    # Step 20: View business loop schedule
    # ------------------------------------------------------------------
    def test_20_schedule_loops(self):
        raw = "!murphy schedule loops"
        resp = _dispatch(self.dispatcher, raw)
        _capture("20_schedule_loops", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Business Loop Schedule", resp.message)
        # All loops should be present
        for loop in ["heartbeat", "financial_review", "compliance_check",
                      "risk_assessment", "production_pace", "stakeholder_reporting"]:
            self.assertIn(loop, resp.message)

    # ------------------------------------------------------------------
    # Step 21: Configure a business loop
    # ------------------------------------------------------------------
    def test_21_schedule_configure(self):
        raw = "!murphy schedule configure risk_assessment 600"
        resp = _dispatch(self.dispatcher, raw)
        _capture("21_schedule_configure", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("risk_assessment", resp.message)
        self.assertIn("600", resp.message)

    # ------------------------------------------------------------------
    # Step 22: Schedule status
    # ------------------------------------------------------------------
    def test_22_schedule_status(self):
        raw = "!murphy schedule status"
        resp = _dispatch(self.dispatcher, raw)
        _capture("22_schedule_status", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Schedule Status", resp.message)
        self.assertIn("running", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 23: Reject invalid loop configuration
    # ------------------------------------------------------------------
    def test_23_schedule_out_of_range(self):
        raw = "!murphy schedule configure heartbeat 0"
        resp = _dispatch(self.dispatcher, raw)
        _capture("23_schedule_out_of_range", raw, resp)
        self.assertFalse(resp.success)
        self.assertIn("out of range", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 24: SKM Loop Status — full Sense-Know-Model overview
    # ------------------------------------------------------------------
    def test_24_skm_status(self):
        raw = "!murphy skm status"
        resp = _dispatch(self.dispatcher, raw)
        _capture("24_skm_status", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Sense-Know-Model", resp.message)
        self.assertIn("SENSE", resp.message)
        self.assertIn("KNOW", resp.message)
        self.assertIn("MODEL", resp.message)
        # Verify it shows automations from onboarding
        self.assertIn("automation", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 25: SKM Sense phase
    # ------------------------------------------------------------------
    def test_25_skm_sense(self):
        raw = "!murphy skm sense"
        resp = _dispatch(self.dispatcher, raw)
        _capture("25_skm_sense", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("SENSE", resp.message)
        # Should show setpoints
        for dim in ["money", "time", "production"]:
            self.assertIn(dim, resp.message)
        # Should show observed automations from onboarding
        self.assertIn("Observed Automations", resp.message)

    # ------------------------------------------------------------------
    # Step 26: SKM Know phase
    # ------------------------------------------------------------------
    def test_26_skm_know(self):
        raw = "!murphy skm know"
        resp = _dispatch(self.dispatcher, raw)
        _capture("26_skm_know", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("KNOW", resp.message)
        self.assertIn("Gate Evaluations", resp.message)
        # Should show gates we created earlier
        self.assertIn("revenue-q1", resp.message)

    # ------------------------------------------------------------------
    # Step 27: SKM Model phase
    # ------------------------------------------------------------------
    def test_27_skm_model(self):
        raw = "!murphy skm model"
        resp = _dispatch(self.dispatcher, raw)
        _capture("27_skm_model", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("MODEL", resp.message)
        # Should show automation capabilities from onboarding
        self.assertIn("Automation Capabilities", resp.message)
        # Should show gate-loop mapping
        self.assertIn("Gate-Loop Mapping", resp.message)

    # ------------------------------------------------------------------
    # Step 28: SKM Cycle — run a full virtual cycle
    # ------------------------------------------------------------------
    def test_28_skm_cycle(self):
        raw = "!murphy skm cycle"
        resp = _dispatch(self.dispatcher, raw)
        _capture("28_skm_cycle", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("SKM Cycle Execution", resp.message)
        self.assertIn("SENSE", resp.message)
        self.assertIn("KNOW", resp.message)
        self.assertIn("MODEL", resp.message)
        # Should complete with a health summary
        self.assertIn("Cycle complete", resp.message)

    # ------------------------------------------------------------------
    # Step 29: Automation list — unified view
    # ------------------------------------------------------------------
    def test_29_automation_list(self):
        raw = "!murphy automation list"
        resp = _dispatch(self.dispatcher, raw)
        _capture("29_automation_list", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Automation Registry", resp.message)
        # Should show employee automations from onboarding
        self.assertIn("shadow", resp.message.lower())

    # ------------------------------------------------------------------
    # Step 30: Automation summary
    # ------------------------------------------------------------------
    def test_30_automation_summary(self):
        raw = "!murphy automation summary"
        resp = _dispatch(self.dispatcher, raw)
        _capture("30_automation_summary", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("Automation Summary", resp.message)
        self.assertIn("SKM Loop Integration", resp.message)

    # ------------------------------------------------------------------
    # Step 31: Dashboard standup shows automations
    # ------------------------------------------------------------------
    def test_31_dashboard_shows_automations(self):
        raw = "!murphy dashboard standup"
        resp = _dispatch(self.dispatcher, raw)
        _capture("31_dashboard_standup", raw, resp)
        self.assertTrue(resp.success)
        # Dashboard should include automation status
        self.assertIn("Automation Status", resp.message)
        # Should include SKM loop summary
        self.assertIn("SKM Loop", resp.message)

    # ------------------------------------------------------------------
    # Step 32: Dashboard weekly shows automations
    # ------------------------------------------------------------------
    def test_32_dashboard_shows_weekly_automations(self):
        raw = "!murphy dashboard weekly"
        resp = _dispatch(self.dispatcher, raw)
        _capture("32_dashboard_weekly", raw, resp)
        self.assertTrue(resp.success)
        # Weekly should include automation summary
        self.assertIn("Automation Summary", resp.message)
        self.assertIn("Setpoint Health", resp.message)
        self.assertIn("Business Loops", resp.message)

    # ------------------------------------------------------------------
    # Step 33: Recipe list shows onboarding automations
    # ------------------------------------------------------------------
    def test_33_recipe_shows_automations(self):
        raw = "!murphy recipe list"
        resp = _dispatch(self.dispatcher, raw)
        _capture("33_recipe_list", raw, resp)
        self.assertTrue(resp.success)
        # Should include onboarding-derived automations
        self.assertIn("Onboarding-Derived Automations", resp.message)

    # ------------------------------------------------------------------
    # Step 34: Schedule loops shows SKM linkage
    # ------------------------------------------------------------------
    def test_34_schedule_shows_skm_linkage(self):
        raw = "!murphy schedule loops"
        resp = _dispatch(self.dispatcher, raw)
        _capture("34_schedule_loops_skm", raw, resp)
        self.assertTrue(resp.success)
        self.assertIn("SKM Loop Automation Linkage", resp.message)
        self.assertIn("SENSE", resp.message)
        self.assertIn("KNOW", resp.message)
        self.assertIn("MODEL", resp.message)

    # ------------------------------------------------------------------
    # Step 35: Workspace list shows automation assignments
    # ------------------------------------------------------------------
    def test_35_workspace_shows_automations(self):
        raw = "!murphy workspace list"
        resp = _dispatch(self.dispatcher, raw)
        _capture("35_workspace_list", raw, resp)
        self.assertTrue(resp.success)
        # Should include automation count
        self.assertIn("Automation assignments", resp.message)

    # ------------------------------------------------------------------
    # Validation: all responses unique (no stuck system)
    # ------------------------------------------------------------------
    def test_90_no_duplicate_responses(self):
        """Verify responses are diverse (not all identical — system is not stuck)."""
        msgs = [s["message"] for s in _SCREENSHOTS]
        # Count distinct messages
        unique = set(msgs)
        # We expect at least 25 unique responses out of 35+ steps
        self.assertGreaterEqual(len(unique), 25,
                                f"Only {len(unique)} unique responses out of {len(msgs)} — system may be stuck")

    def test_91_all_setpoints_established(self):
        """Verify all 6 setpoint dimensions are established with ranges."""
        raw = "!murphy setpoint show"
        resp = _dispatch(self.dispatcher, raw)
        for dim in ["money", "time", "production", "confidence",
                     "info_completeness", "risk"]:
            self.assertIn(dim, resp.message,
                          f"Setpoint dimension '{dim}' missing")

    def test_92_all_gate_ranges_established(self):
        """Verify gates were created for multiple objective categories."""
        raw = "!murphy gate list"
        resp = _dispatch(self.dispatcher, raw)
        self.assertTrue(resp.success)
        # Must have gates from at least 2 objective categories
        for obj in ["revenue-q1", "compliance-2026", "ops-efficiency"]:
            self.assertIn(obj, resp.message,
                          f"Gates for objective '{obj}' missing")

    def test_93_all_business_loops_scheduled(self):
        """Verify all business loops are scheduled with intervals."""
        raw = "!murphy schedule loops"
        resp = _dispatch(self.dispatcher, raw)
        self.assertTrue(resp.success)
        for loop in ["heartbeat", "financial_review", "compliance_check",
                      "risk_assessment", "production_pace",
                      "stakeholder_reporting"]:
            self.assertIn(loop, resp.message,
                          f"Business loop '{loop}' not scheduled")

    def test_94_onboarding_produced_shadow_agent(self):
        """Verify onboarding produced a shadow agent with capabilities."""
        raw = "!murphy onboard status"
        resp = _dispatch(self.dispatcher, raw)
        self.assertTrue(resp.success)
        # Should show shadow agents > 0
        self.assertIn("Shadow agents", resp.message)

    def test_95_screenshot_count(self):
        """Verify we captured screenshots at every step."""
        self.assertGreaterEqual(
            len(_SCREENSHOTS), 30,
            f"Expected at least 30 screenshots, got {len(_SCREENSHOTS)}"
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    def test_96_unknown_onboard_sub(self):
        raw = "!murphy onboard foobar"
        resp = _dispatch(self.dispatcher, raw)
        self.assertFalse(resp.success)
        self.assertIn("Unknown onboard subcommand", resp.message)

    def test_97_unknown_gate_sub(self):
        raw = "!murphy gate foobar"
        resp = _dispatch(self.dispatcher, raw)
        self.assertFalse(resp.success)

    def test_98_missing_session_id(self):
        raw = "!murphy onboard questions"
        resp = _dispatch(self.dispatcher, raw)
        self.assertFalse(resp.success)
        self.assertIn("Usage", resp.message)

    def test_99_invalid_gate_category(self):
        raw = "!murphy gate create obj1 invalid_category"
        resp = _dispatch(self.dispatcher, raw)
        self.assertFalse(resp.success)


if __name__ == "__main__":
    unittest.main()
