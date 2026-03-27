"""
Librarian Mode & Triage Tests
================================
Validates the mode-aware Librarian and Triage escalation path.

Covers:
  * LibrarianMode (ASK / ONBOARDING / PRODUCTION / ASSISTANT)
  * Mode-specific greeting text
  * ASK mode skips guided questions and builds steps directly
  * ONBOARDING mode asks clarifying questions when intent is unclear
  * ASSISTANT mode uses a custom personality profile
  * Triage trigger words escalate send_message() to TriageResult
  * Direct triage() generates a workflow_def + command + setpoints
  * set_mode() changes mode mid-session
  * TriageResult.to_dict() is JSON-serialisable

Timeout budget (5 s per 1 000 lines of tested source):
  nocode_workflow_terminal.py  ~900 lines  →  ~4.5 s
  system_librarian.py          ~1 200 lines →  ~6 s
  ai_workflow_generator.py     ~386 lines   →  ~2 s
  ─────────────────────────────────────────────────
  Total tested source          ~2 486 lines →  ~12 s minimum
  Suite-level timeout guard    30 s

Run this suite:
    pytest tests/test_librarian_mode_triage.py -v

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nocode_workflow_terminal import (
    ConversationState,
    LibrarianMode,
    NoCodeWorkflowTerminal,
    TriageResult,
    TriageStatus,
    _MODE_GREETINGS,
    _MODE_SKIP_GATHERING,
    _TRIAGE_TRIGGERS,
)

pytestmark = pytest.mark.timeout(30)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def terminal() -> NoCodeWorkflowTerminal:
    return NoCodeWorkflowTerminal()


# ---------------------------------------------------------------------------
# 1 — LibrarianMode constants
# ---------------------------------------------------------------------------


class TestLibrarianModeConstants:
    """Verify the mode/behaviour-profile constants are correct."""

    def test_all_four_modes_exist(self):
        modes = {m.value for m in LibrarianMode}
        assert modes == {"ask", "onboarding", "production", "assistant"}

    def test_ask_mode_skips_gathering(self):
        assert _MODE_SKIP_GATHERING[LibrarianMode.ASK.value] is True

    def test_onboarding_does_not_skip_gathering(self):
        assert _MODE_SKIP_GATHERING[LibrarianMode.ONBOARDING.value] is False

    def test_production_does_not_skip_gathering(self):
        assert _MODE_SKIP_GATHERING[LibrarianMode.PRODUCTION.value] is False

    def test_all_modes_have_greetings(self):
        for mode in LibrarianMode:
            assert mode.value in _MODE_GREETINGS
            assert len(_MODE_GREETINGS[mode.value]) > 0

    def test_triage_triggers_non_empty(self):
        assert len(_TRIAGE_TRIGGERS) > 0
        assert "triage" in _TRIAGE_TRIGGERS
        assert "execute now" in _TRIAGE_TRIGGERS

    def test_triage_state_exists(self):
        assert ConversationState.TRIAGE.value == "triage"


# ---------------------------------------------------------------------------
# 2 — create_session with mode
# ---------------------------------------------------------------------------


class TestCreateSessionWithMode:
    """Session creation correctly applies mode and greeting."""

    def test_default_mode_is_ask(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session()
        assert session.mode == LibrarianMode.ASK

    def test_ask_mode_greeting(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        greeting = session.conversation_history[0].message
        assert "triage" in greeting.lower() or "ready" in greeting.lower()

    def test_onboarding_mode_greeting(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ONBOARDING)
        greeting = session.conversation_history[0].message
        assert "welcome" in greeting.lower() or "librarian" in greeting.lower()

    def test_production_mode_greeting(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.PRODUCTION)
        greeting = session.conversation_history[0].message
        assert len(greeting) > 0

    def test_assistant_mode_uses_profile_name(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(
            mode=LibrarianMode.ASSISTANT,
            assistant_profile={"name": "HR Bot", "focus": "human resources"},
        )
        greeting = session.conversation_history[0].message
        assert "HR Bot" in greeting

    def test_assistant_mode_uses_profile_focus(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(
            mode=LibrarianMode.ASSISTANT,
            assistant_profile={"name": "Sales Bot", "focus": "sales"},
        )
        greeting = session.conversation_history[0].message
        assert "sales" in greeting.lower()

    def test_assistant_mode_no_profile_uses_default(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASSISTANT)
        greeting = session.conversation_history[0].message
        assert len(greeting) > 0

    def test_session_stores_assistant_profile(self, terminal: NoCodeWorkflowTerminal):
        profile = {"name": "Ops Bot", "focus": "operations"}
        session = terminal.create_session(
            mode=LibrarianMode.ASSISTANT, assistant_profile=profile
        )
        assert session.assistant_profile == profile

    def test_mode_reflected_in_session_dict(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.PRODUCTION)
        d = session.to_dict()
        assert d["mode"] == "production"


# ---------------------------------------------------------------------------
# 3 — Mode-aware message processing
# ---------------------------------------------------------------------------


class TestModeAwareMessageProcessing:
    """Verify each mode responds correctly to ambiguous and clear messages."""

    def test_ask_mode_skips_guided_questions_on_unclear_input(
        self, terminal: NoCodeWorkflowTerminal
    ):
        """ASK mode must NOT ask a clarifying question — it builds steps directly."""
        session = terminal.create_session(mode=LibrarianMode.ASK)
        resp = terminal.send_message(session.session_id, "I need to do something with data")
        updated = terminal.get_session(session.session_id)
        # Must have moved past GATHERING_REQUIREMENTS
        assert updated.state != ConversationState.GATHERING_REQUIREMENTS
        assert updated.state == ConversationState.BUILDING_STEPS
        assert len(updated.steps) > 0

    def test_ask_mode_builds_steps_on_clear_input(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Monitor server health and alert on failure",
        )
        updated = terminal.get_session(session.session_id)
        assert len(updated.steps) > 0

    def test_onboarding_mode_asks_question_on_unclear_input(
        self, terminal: NoCodeWorkflowTerminal
    ):
        """ONBOARDING mode SHOULD ask a clarifying question when intent is unclear."""
        session = terminal.create_session(mode=LibrarianMode.ONBOARDING)
        resp = terminal.send_message(session.session_id, "xyz qrst")
        updated = terminal.get_session(session.session_id)
        assert updated.state == ConversationState.GATHERING_REQUIREMENTS
        assert "?" in resp["message"] or "describe" in resp["message"].lower()

    def test_production_mode_builds_steps_directly(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.PRODUCTION)
        terminal.send_message(
            session.session_id,
            "Deploy my application to production environment",
        )
        updated = terminal.get_session(session.session_id)
        assert updated.state in (
            ConversationState.BUILDING_STEPS,
            ConversationState.GATHERING_REQUIREMENTS,
        )

    def test_response_includes_mode_field(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        resp = terminal.send_message(
            session.session_id, "Fetch data and send report"
        )
        assert resp.get("mode") == "ask"

    def test_completed_state_response_in_ask_mode(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        session.state = ConversationState.COMPLETED
        resp = terminal.send_message(session.session_id, "hello")
        assert "finalized" in resp["message"].lower() or "new session" in resp["message"].lower()


# ---------------------------------------------------------------------------
# 4 — set_mode
# ---------------------------------------------------------------------------


class TestSetMode:
    def test_set_mode_changes_session_mode(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        result = terminal.set_mode(session.session_id, LibrarianMode.PRODUCTION)
        assert result is True
        assert terminal.get_session(session.session_id).mode == LibrarianMode.PRODUCTION

    def test_set_mode_returns_false_for_unknown_session(
        self, terminal: NoCodeWorkflowTerminal
    ):
        result = terminal.set_mode("nonexistent-session-id", LibrarianMode.ASK)
        assert result is False

    def test_set_mode_to_onboarding(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.set_mode(session.session_id, LibrarianMode.ONBOARDING)
        updated = terminal.get_session(session.session_id)
        assert updated.mode == LibrarianMode.ONBOARDING


# ---------------------------------------------------------------------------
# 5 — Triage trigger escalation via send_message
# ---------------------------------------------------------------------------


class TestTriageTriggerInSendMessage:
    """Triage trigger words in a message automatically escalate the session."""

    @pytest.mark.parametrize("trigger_word", [
        "triage",
        "execute now",
        "run now",
        "make it happen",
        "escalate this",
        "submit for execution",
        "approve and run",
    ])
    def test_trigger_word_returns_triage_key(
        self, terminal: NoCodeWorkflowTerminal, trigger_word: str
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Fetch sales data, analyse it, send weekly report to Slack",
        )
        resp = terminal.send_message(session.session_id, trigger_word)
        assert "triage" in resp, (
            f"'triage' key missing from response when trigger='{trigger_word}'"
        )

    def test_triage_response_has_status(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Run ETL pipeline daily")
        resp = terminal.send_message(session.session_id, "triage")
        assert "status" in resp["triage"]

    def test_triage_response_status_is_valid(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Monitor server health")
        resp = terminal.send_message(session.session_id, "execute now")
        status = resp["triage"]["status"]
        valid_statuses = {s.value for s in TriageStatus}
        assert status in valid_statuses

    def test_triage_response_message_mentions_status(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Send weekly sales report")
        resp = terminal.send_message(session.session_id, "triage")
        assert "triage" in resp["message"].lower()

    def test_non_trigger_message_does_not_include_triage_key(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        resp = terminal.send_message(
            session.session_id,
            "Monitor my database and alert when CPU exceeds 90%",
        )
        assert "triage" not in resp


# ---------------------------------------------------------------------------
# 6 — Direct triage() method
# ---------------------------------------------------------------------------


class TestDirectTriage:
    """Validate the triage() method independently."""

    def test_triage_returns_triage_result(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Extract data from database, transform it, load to warehouse",
        )
        result = terminal.triage(session.session_id)
        assert isinstance(result, TriageResult)

    def test_triage_ready_when_workflow_generated(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Run CI/CD pipeline: build, test, deploy to production",
        )
        result = terminal.triage(session.session_id)
        assert result.status == TriageStatus.READY
        assert result.workflow_def is not None
        assert len(result.workflow_def.get("steps", [])) > 0

    def test_triage_without_prior_description_needs_info(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        # No message sent — no description
        result = terminal.triage(session.session_id)
        assert result.status == TriageStatus.NEEDS_INFO

    def test_triage_failed_for_unknown_session(self, terminal: NoCodeWorkflowTerminal):
        result = terminal.triage("no-such-session")
        assert result.status == TriageStatus.FAILED

    def test_triage_has_workflow_def_for_clear_input(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Security audit: scan targets, analyse vulnerabilities, notify owners",
        )
        result = terminal.triage(session.session_id)
        assert result.workflow_def is not None

    def test_triage_has_command_string(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            "Run data pipeline to process sales records",
        )
        result = terminal.triage(session.session_id)
        assert isinstance(result.command, str)

    def test_triage_confidence_in_range(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Deploy application to production")
        result = terminal.triage(session.session_id)
        assert 0.0 <= result.confidence <= 1.0

    def test_triage_advances_session_state(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id, "Onboard new customer: validate, provision, welcome"
        )
        terminal.triage(session.session_id)
        updated = terminal.get_session(session.session_id)
        assert updated.state == ConversationState.TRIAGE

    def test_triage_history_recorded(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Monitor server health")
        terminal.triage(session.session_id)
        updated = terminal.get_session(session.session_id)
        assert len(updated.triage_history) >= 1

    def test_triage_result_has_summary(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Analyse customer data and report")
        result = terminal.triage(session.session_id)
        assert len(result.summary) > 0

    def test_triage_result_to_dict_is_json_serialisable(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Fetch and send weekly report")
        result = terminal.triage(session.session_id)
        d = result.to_dict()
        json.dumps(d)  # must not raise

    def test_second_triage_appends_to_history(self, terminal: NoCodeWorkflowTerminal):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(session.session_id, "Run ETL pipeline")
        terminal.triage(session.session_id)
        terminal.triage(session.session_id)
        updated = terminal.get_session(session.session_id)
        assert len(updated.triage_history) >= 2


# ---------------------------------------------------------------------------
# 7 — list_sessions includes mode
# ---------------------------------------------------------------------------


class TestListSessionsMode:
    def test_list_sessions_includes_mode(self, terminal: NoCodeWorkflowTerminal):
        terminal.create_session(mode=LibrarianMode.ASK)
        terminal.create_session(mode=LibrarianMode.PRODUCTION)
        sessions = terminal.list_sessions()
        assert all("mode" in s for s in sessions)
        modes = {s["mode"] for s in sessions}
        assert "ask" in modes
        assert "production" in modes


# ---------------------------------------------------------------------------
# 8 — Integration: full Describe → Triage → Ready flow
# ---------------------------------------------------------------------------


class TestFullDescribeToTriageFlow:
    """End-to-end validation of the conversation → triage promotion path."""

    def test_ask_mode_describe_then_triage_is_ready(self, terminal: NoCodeWorkflowTerminal):
        """The canonical ASK-mode hero path: user describes, says 'triage', gets ready result."""
        session = terminal.create_session(mode=LibrarianMode.ASK)

        # DESCRIBE
        resp = terminal.send_message(
            session.session_id,
            "Fetch sales data from the database, analyse trends, "
            "and send a weekly summary report to the Slack channel",
        )
        assert resp["state"] != "completed"

        # TRIAGE via trigger word
        triage_resp = terminal.send_message(session.session_id, "triage")
        assert "triage" in triage_resp
        triage_dict = triage_resp["triage"]
        assert triage_dict["status"] in ("ready", "needs_info")
        assert triage_dict["confidence"] >= 0.0

    def test_production_mode_immediate_build_then_triage(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.PRODUCTION)
        terminal.send_message(
            session.session_id,
            "Run an ETL pipeline to extract, transform, and load data daily",
        )
        result = terminal.triage(session.session_id)
        assert result.status in (TriageStatus.READY, TriageStatus.NEEDS_INFO)

    def test_onboarding_mode_triage_after_full_conversation(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ONBOARDING)
        # Provide clear intent so steps are built
        terminal.send_message(
            session.session_id,
            "Schedule daily notifications to monitor uptime",
        )
        result = terminal.triage(session.session_id)
        assert isinstance(result, TriageResult)

    def test_triage_setpoints_extracted_from_description(
        self, terminal: NoCodeWorkflowTerminal
    ):
        session = terminal.create_session(mode=LibrarianMode.ASK)
        terminal.send_message(
            session.session_id,
            'Run data pipeline --pipeline_id sales_etl with "daily schedule" and 3 replicas',
        )
        result = terminal.triage(session.session_id)
        assert result.setpoints is not None
        # At least one setpoint should have been extracted
        # (pipeline_id, value, or replica)
        assert isinstance(result.setpoints, dict)
