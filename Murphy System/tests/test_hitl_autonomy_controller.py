"""Tests for the HITL Autonomy Controller module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone, timedelta
import pytest
from src.hitl_autonomy_controller import (
    AutonomyPolicy,
    HITLAutonomyController,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def controller():
    return HITLAutonomyController()


def _make_policy(
    policy_id="pol-1",
    name="default",
    confidence_threshold=0.95,
    hitl_required=True,
    auto_approve_below_risk=0.2,
    max_autonomous_actions=10,
    cooldown_seconds=300,
    enabled=True,
):
    return AutonomyPolicy(
        policy_id=policy_id,
        name=name,
        confidence_threshold=confidence_threshold,
        hitl_required=hitl_required,
        auto_approve_below_risk=auto_approve_below_risk,
        max_autonomous_actions=max_autonomous_actions,
        cooldown_seconds=cooldown_seconds,
        enabled=enabled,
    )


# ------------------------------------------------------------------
# Policy registration and retrieval
# ------------------------------------------------------------------

class TestPolicyManagement:
    def test_register_policy(self, controller):
        pid = controller.register_policy(_make_policy(policy_id="p1"))
        assert pid == "p1"

    def test_get_policy(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", name="test"))
        result = controller.get_policy("p1")
        assert result["status"] == "ok"
        assert result["name"] == "test"
        assert result["confidence_threshold"] == 0.95

    def test_get_unknown_policy(self, controller):
        result = controller.get_policy("nonexistent")
        assert result["status"] == "error"
        assert result["reason"] == "unknown_policy"

    def test_list_policies_empty(self, controller):
        assert controller.list_policies() == []

    def test_list_policies(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        controller.register_policy(_make_policy(policy_id="p2"))
        policies = controller.list_policies()
        assert len(policies) == 2
        ids = {p["policy_id"] for p in policies}
        assert ids == {"p1", "p2"}

    def test_register_overwrites_existing(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", name="old"))
        controller.register_policy(_make_policy(policy_id="p1", name="new"))
        assert controller.get_policy("p1")["name"] == "new"
        assert len(controller.list_policies()) == 1


# ------------------------------------------------------------------
# Autonomy evaluation
# ------------------------------------------------------------------

class TestAutonomyEvaluation:
    def test_no_policies_registered(self, controller):
        result = controller.evaluate_autonomy("deploy", 0.99, 0.1)
        assert result["autonomous"] is False
        assert result["reason"] == "no_policies_registered"
        assert result["requires_hitl"] is True

    def test_high_confidence_low_risk_autonomous(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.evaluate_autonomy("deploy", 0.98, 0.1, policy_id="p1")
        assert result["autonomous"] is True
        assert result["reason"] == "low_risk_auto_approved"
        assert result["requires_hitl"] is False

    def test_low_confidence_requires_hitl(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.evaluate_autonomy("deploy", 0.80, 0.1, policy_id="p1")
        assert result["autonomous"] is False
        assert result["reason"] == "confidence_below_threshold"
        assert result["requires_hitl"] is True

    def test_high_confidence_high_risk(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.evaluate_autonomy("deploy", 0.99, 0.5, policy_id="p1")
        assert result["autonomous"] is True
        assert result["reason"] == "high_confidence_autonomous"

    def test_disabled_policy(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", enabled=False))
        result = controller.evaluate_autonomy("deploy", 0.99, 0.1, policy_id="p1")
        assert result["autonomous"] is False
        assert result["reason"] == "policy_disabled"

    def test_uses_first_policy_if_none_specified(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.evaluate_autonomy("deploy", 0.99, 0.1)
        assert result["policy_applied"] == "p1"
        assert result["autonomous"] is True

    def test_returns_confidence_and_risk(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.evaluate_autonomy("deploy", 0.96, 0.15, policy_id="p1")
        assert result["confidence"] == 0.96
        assert result["risk_level"] == 0.15


# ------------------------------------------------------------------
# HITL arm/disarm
# ------------------------------------------------------------------

class TestHITLArmDisarm:
    def test_arm_hitl(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", hitl_required=False))
        result = controller.arm_hitl("p1")
        assert result["status"] == "armed"
        assert result["hitl_required"] is True
        # Verify policy is updated
        assert controller.get_policy("p1")["hitl_required"] is True

    def test_disarm_hitl(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", hitl_required=True))
        result = controller.disarm_hitl("p1")
        assert result["status"] == "disarmed"
        assert result["hitl_required"] is False
        assert controller.get_policy("p1")["hitl_required"] is False

    def test_arm_unknown_policy(self, controller):
        result = controller.arm_hitl("nonexistent")
        assert result["status"] == "error"
        assert result["reason"] == "unknown_policy"

    def test_disarm_unknown_policy(self, controller):
        result = controller.disarm_hitl("nonexistent")
        assert result["status"] == "error"
        assert result["reason"] == "unknown_policy"

    def test_disarm_enables_autonomy(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", hitl_required=True))
        # With HITL armed, low confidence still blocked
        result = controller.evaluate_autonomy("deploy", 0.80, 0.1, policy_id="p1")
        assert result["autonomous"] is False
        # Disarm HITL
        controller.disarm_hitl("p1")
        result = controller.evaluate_autonomy("deploy", 0.80, 0.1, policy_id="p1")
        assert result["autonomous"] is True


# ------------------------------------------------------------------
# Action recording
# ------------------------------------------------------------------

class TestActionRecording:
    def test_record_action_returns_id(self, controller):
        action_id = controller.record_action("deploy", True, "success", 0.98)
        assert isinstance(action_id, str)
        assert len(action_id) == 12

    def test_record_multiple_actions(self, controller):
        ids = set()
        for i in range(5):
            ids.add(controller.record_action(f"task-{i}", True, "success", 0.95))
        assert len(ids) == 5

    def test_action_appears_in_stats(self, controller):
        controller.record_action("deploy", True, "success", 0.99)
        stats = controller.get_autonomy_stats()
        assert stats["total_actions"] == 1


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

class TestAutonomyStats:
    def test_empty_stats(self, controller):
        stats = controller.get_autonomy_stats()
        assert stats["total_actions"] == 0
        assert stats["autonomous_count"] == 0
        assert stats["hitl_count"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["outcomes"] == {}

    def test_stats_counts(self, controller):
        controller.record_action("deploy", True, "success", 0.99)
        controller.record_action("deploy", True, "success", 0.97)
        controller.record_action("deploy", False, "failure", 0.80)
        stats = controller.get_autonomy_stats()
        assert stats["total_actions"] == 3
        assert stats["autonomous_count"] == 2
        assert stats["hitl_count"] == 1

    def test_stats_avg_confidence(self, controller):
        controller.record_action("a", True, "success", 1.0)
        controller.record_action("b", True, "success", 0.5)
        stats = controller.get_autonomy_stats()
        assert stats["avg_confidence"] == 0.75

    def test_stats_outcomes_breakdown(self, controller):
        controller.record_action("a", True, "success", 0.99)
        controller.record_action("b", True, "success", 0.97)
        controller.record_action("c", False, "failure", 0.80)
        controller.record_action("d", True, "timeout", 0.90)
        stats = controller.get_autonomy_stats()
        assert stats["outcomes"]["success"] == 2
        assert stats["outcomes"]["failure"] == 1
        assert stats["outcomes"]["timeout"] == 1


# ------------------------------------------------------------------
# Cooldown
# ------------------------------------------------------------------

class TestCooldown:
    def test_no_cooldown_by_default(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        result = controller.check_cooldown("p1")
        assert result["in_cooldown"] is False

    def test_trigger_cooldown(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", cooldown_seconds=600))
        result = controller.trigger_cooldown("p1")
        assert result["status"] == "cooldown_triggered"
        assert result["cooldown_seconds"] == 600

    def test_in_cooldown_after_trigger(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", cooldown_seconds=600))
        controller.trigger_cooldown("p1")
        result = controller.check_cooldown("p1")
        assert result["in_cooldown"] is True
        assert "remaining_seconds" in result

    def test_cooldown_blocks_autonomy(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", cooldown_seconds=600))
        controller.trigger_cooldown("p1")
        result = controller.evaluate_autonomy("deploy", 0.99, 0.1, policy_id="p1")
        assert result["autonomous"] is False
        assert result["reason"] == "policy_in_cooldown"

    def test_trigger_cooldown_unknown_policy(self, controller):
        result = controller.trigger_cooldown("nonexistent")
        assert result["status"] == "error"

    def test_check_cooldown_unknown_policy(self, controller):
        result = controller.check_cooldown("nonexistent")
        assert result["status"] == "error"

    def test_cooldown_resets_action_count(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", max_autonomous_actions=2))
        controller.evaluate_autonomy("a", 0.99, 0.1, policy_id="p1")
        controller.trigger_cooldown("p1")
        # After cooldown trigger, count is reset to 0
        assert controller._autonomy_sessions["p1"]["autonomous_action_count"] == 0


# ------------------------------------------------------------------
# Max autonomous actions
# ------------------------------------------------------------------

class TestMaxAutonomousActions:
    def test_max_actions_limit(self, controller):
        controller.register_policy(_make_policy(policy_id="p1", max_autonomous_actions=2))
        r1 = controller.evaluate_autonomy("a", 0.99, 0.1, policy_id="p1")
        assert r1["autonomous"] is True
        r2 = controller.evaluate_autonomy("b", 0.99, 0.1, policy_id="p1")
        assert r2["autonomous"] is True
        r3 = controller.evaluate_autonomy("c", 0.99, 0.1, policy_id="p1")
        assert r3["autonomous"] is False
        assert r3["reason"] == "max_autonomous_actions_reached"


# ------------------------------------------------------------------
# Reset
# ------------------------------------------------------------------

class TestReset:
    def test_reset_clears_all(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        controller.record_action("deploy", True, "success", 0.99)
        controller.trigger_cooldown("p1")
        controller.reset()
        assert controller.list_policies() == []
        assert controller.get_autonomy_stats()["total_actions"] == 0

    def test_reset_allows_fresh_start(self, controller):
        controller.register_policy(_make_policy(policy_id="p1"))
        controller.reset()
        controller.register_policy(_make_policy(policy_id="p2"))
        policies = controller.list_policies()
        assert len(policies) == 1
        assert policies[0]["policy_id"] == "p2"
