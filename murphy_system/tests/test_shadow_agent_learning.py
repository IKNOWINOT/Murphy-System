"""
Tests for shadow agent learning — observe_action, ask_clarifying_question,
propose_automation, get_learning_summary.

These methods were added to ShadowAgentIntegration in Part 5 of the feature.

Design Label: TEST-SHADOW-LEARN-001
Owner: QA Team
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


from shadow_agent_integration import (
    AccountType,
    ShadowAgentIntegration,
    ShadowStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration():
    return ShadowAgentIntegration()


@pytest.fixture
def user_account(integration):
    return integration.create_account("Alice", AccountType.USER)


@pytest.fixture
def shadow(integration, user_account):
    return integration.create_shadow_agent(
        primary_role_id="role-dev",
        account_id=user_account.account_id,
        department="engineering",
        permissions=["read", "write"],
    )


# ---------------------------------------------------------------------------
# observe_action
# ---------------------------------------------------------------------------


class TestObserveAction:
    def test_observe_returns_observation_entry(self, integration, shadow):
        entry = integration.observe_action(
            shadow.agent_id,
            action_type="run_command",
            action_data={"command": "pytest"},
        )
        assert "observation_id" in entry
        assert entry["action_type"] == "run_command"
        assert entry["observed_at"]

    def test_observe_unknown_agent_returns_error(self, integration):
        result = integration.observe_action("notexist", "click", {})
        assert "error" in result

    def test_multiple_observations_accumulate(self, integration, shadow):
        for i in range(5):
            integration.observe_action(shadow.agent_id, f"action_{i}", {"i": i})
        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["total_observations"] == 5

    def test_observation_type_tracked(self, integration, shadow):
        integration.observe_action(shadow.agent_id, "run_pytest", {})
        integration.observe_action(shadow.agent_id, "run_pytest", {})
        integration.observe_action(shadow.agent_id, "git_commit", {})
        summary = integration.get_learning_summary(shadow.agent_id)
        freq = summary["action_frequency"]
        assert freq.get("run_pytest", 0) == 2
        assert freq.get("git_commit", 0) == 1

    def test_observation_is_thread_safe(self, integration, shadow):
        def observe_n(n):
            for _ in range(n):
                integration.observe_action(shadow.agent_id, "bulk_action", {})

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(observe_n, 25) for _ in range(4)]
            for f in futs:
                f.result()

        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["total_observations"] == 100


# ---------------------------------------------------------------------------
# ask_clarifying_question
# ---------------------------------------------------------------------------


class TestAskClarifyingQuestion:
    def test_returns_question_with_id(self, integration, shadow):
        result = integration.ask_clarifying_question(shadow.agent_id)
        assert "question_id" in result
        assert "question" in result
        assert len(result["question"]) > 5

    def test_unknown_agent_returns_error(self, integration):
        result = integration.ask_clarifying_question("bad-id")
        assert "error" in result

    def test_question_references_top_action_when_observations_exist(
        self, integration, shadow
    ):
        for _ in range(10):
            integration.observe_action(shadow.agent_id, "deploy", {})

        result = integration.ask_clarifying_question(shadow.agent_id)
        # Should mention the most-frequent action
        assert "deploy" in result["question"]

    def test_context_summary_included(self, integration, shadow):
        integration.observe_action(shadow.agent_id, "api_call", {})
        result = integration.ask_clarifying_question(shadow.agent_id)
        assert "context_summary" in result

    def test_no_observations_returns_generic_question(self, integration, shadow):
        result = integration.ask_clarifying_question(shadow.agent_id)
        assert result["question"]   # non-empty


# ---------------------------------------------------------------------------
# propose_automation
# ---------------------------------------------------------------------------


class TestProposeAutomation:
    def test_returns_proposal_dict(self, integration, shadow):
        proposal = integration.propose_automation(shadow.agent_id)
        assert "proposal_id" in proposal
        assert "description" in proposal
        assert proposal["approved"] is False

    def test_proposal_requires_hitl_approval(self, integration, shadow):
        proposal = integration.propose_automation(shadow.agent_id)
        assert proposal["approved"] is False, "Proposals must start unapproved (HITL required)"

    def test_proposal_with_explicit_pattern(self, integration, shadow):
        pattern = {"action_type": "send_report", "frequency": 12}
        proposal = integration.propose_automation(shadow.agent_id, pattern=pattern)
        assert "send_report" in proposal["description"]

    def test_proposal_from_observations(self, integration, shadow):
        for _ in range(8):
            integration.observe_action(shadow.agent_id, "build_docker", {})
        proposal = integration.propose_automation(shadow.agent_id)
        assert "build_docker" in proposal["description"]

    def test_proposals_accumulate_in_summary(self, integration, shadow):
        integration.propose_automation(shadow.agent_id)
        integration.propose_automation(shadow.agent_id)
        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["total_proposals"] == 2
        assert summary["pending_proposals"] == 2
        assert summary["approved_proposals"] == 0

    def test_unknown_agent_returns_error(self, integration):
        result = integration.propose_automation("notexist")
        assert "error" in result


# ---------------------------------------------------------------------------
# get_learning_summary
# ---------------------------------------------------------------------------


class TestGetLearningSummary:
    def test_summary_for_new_agent(self, integration, shadow):
        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["agent_id"] == shadow.agent_id
        assert summary["total_observations"] == 0
        assert summary["total_proposals"] == 0

    def test_summary_unknown_agent(self, integration):
        result = integration.get_learning_summary("bad-id")
        assert "error" in result

    def test_summary_reflects_all_activity(self, integration, shadow):
        integration.observe_action(shadow.agent_id, "click", {})
        integration.observe_action(shadow.agent_id, "click", {})
        integration.propose_automation(shadow.agent_id)

        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["total_observations"] == 2
        assert summary["total_proposals"] == 1
        assert summary["pending_proposals"] == 1

    def test_action_frequency_computed_correctly(self, integration, shadow):
        for _ in range(3):
            integration.observe_action(shadow.agent_id, "alpha", {})
        for _ in range(7):
            integration.observe_action(shadow.agent_id, "beta", {})

        summary = integration.get_learning_summary(shadow.agent_id)
        freq = summary["action_frequency"]
        assert freq["alpha"] == 3
        assert freq["beta"] == 7

    def test_observation_cap_does_not_raise(self, integration, shadow):
        """Bounded list should handle large numbers without error."""
        for i in range(1100):
            integration.observe_action(shadow.agent_id, "spam", {"i": i})
        # Should not raise; cap is 1000
        summary = integration.get_learning_summary(shadow.agent_id)
        assert summary["total_observations"] <= 1000


# ---------------------------------------------------------------------------
# Audit log coverage
# ---------------------------------------------------------------------------


class TestLearningAuditLog:
    def test_observe_adds_audit_entry(self, integration, shadow):
        before = len(integration._audit_log)
        integration.observe_action(shadow.agent_id, "test_act", {})
        assert len(integration._audit_log) > before

    def test_propose_adds_audit_entry(self, integration, shadow):
        before = len(integration._audit_log)
        integration.propose_automation(shadow.agent_id)
        assert len(integration._audit_log) > before
