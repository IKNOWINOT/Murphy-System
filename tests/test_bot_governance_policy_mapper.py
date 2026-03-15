"""Tests for the Bot Governance Policy Mapper."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.bot_governance_policy_mapper import (
    BotGovernancePolicyMapper,
    BotQuotaPolicy,
    GateCheckResult,
)


@pytest.fixture
def mapper():
    return BotGovernancePolicyMapper()


# ------------------------------------------------------------------
# Bot policy registration
# ------------------------------------------------------------------

class TestBotPolicyRegistration:
    def test_register_bot_default_values(self, mapper):
        policy = mapper.register_bot_policy("bot-1")
        assert isinstance(policy, BotQuotaPolicy)
        assert policy.bot_id == "bot-1"
        assert policy.max_requests_per_minute == 60
        assert policy.max_total_budget == 10000.0

    def test_register_bot_custom_values(self, mapper):
        policy = mapper.register_bot_policy(
            "bot-2", max_rpm=120, max_rph=2000,
            max_budget_task=50.0, max_total_budget=5000.0,
        )
        assert policy.max_requests_per_minute == 120
        assert policy.max_requests_per_hour == 2000
        assert policy.max_budget_per_task == 50.0
        assert policy.max_total_budget == 5000.0

    def test_register_duplicate_overwrites(self, mapper):
        mapper.register_bot_policy("bot-dup", max_rpm=10)
        mapper.register_bot_policy("bot-dup", max_rpm=99)
        profile = mapper.map_to_murphy_profile("bot-dup")
        assert profile["rate_limits"]["requests_per_minute"] == 99

    def test_policy_fields_complete(self, mapper):
        policy = mapper.register_bot_policy("bot-fields")
        assert hasattr(policy, "bot_id")
        assert hasattr(policy, "max_requests_per_minute")
        assert hasattr(policy, "max_requests_per_hour")
        assert hasattr(policy, "max_budget_per_task")
        assert hasattr(policy, "max_total_budget")
        assert hasattr(policy, "stability_threshold")
        assert hasattr(policy, "circuit_breaker_threshold")
        assert hasattr(policy, "is_active")


# ------------------------------------------------------------------
# Murphy profile mapping
# ------------------------------------------------------------------

class TestMurphyProfileMapping:
    def test_map_to_murphy_profile_structure(self, mapper):
        mapper.register_bot_policy("bot-map")
        profile = mapper.map_to_murphy_profile("bot-map")
        assert profile["bot_id"] == "bot-map"
        assert "budget_constraints" in profile
        assert "rate_limits" in profile

    def test_map_unknown_bot_raises(self, mapper):
        with pytest.raises(KeyError):
            mapper.map_to_murphy_profile("no-such-bot")

    def test_profile_includes_budget_constraints(self, mapper):
        mapper.register_bot_policy("bot-budget", max_budget_task=25.0, max_total_budget=500.0)
        profile = mapper.map_to_murphy_profile("bot-budget")
        assert profile["budget_constraints"]["per_task_limit"] == 25.0
        assert profile["budget_constraints"]["total_limit"] == 500.0

    def test_profile_includes_safety_level(self, mapper):
        mapper.register_bot_policy("bot-safe", stability_threshold=0.95)
        profile = mapper.map_to_murphy_profile("bot-safe")
        assert profile["safety_level"] == "critical"

    def test_default_policy_mappings_exist(self, mapper):
        mappings = mapper.get_policy_mappings()
        assert len(mappings) >= 6
        fields = {m["bot_policy_field"] for m in mappings}
        assert "max_budget_per_task" in fields
        assert "stability_threshold" in fields


# ------------------------------------------------------------------
# Gate checks
# ------------------------------------------------------------------

class TestGateChecks:
    def test_gate_allows_within_budget(self, mapper):
        mapper.register_bot_policy("bot-ok", max_total_budget=1000.0)
        result = mapper.check_gate("bot-ok", cost=10.0)
        assert isinstance(result, GateCheckResult)
        assert result.allowed is True

    def test_gate_denies_over_budget(self, mapper):
        mapper.register_bot_policy("bot-broke", max_total_budget=5.0)
        result = mapper.check_gate("bot-broke", cost=10.0)
        assert result.allowed is False
        assert "budget" in result.reason.lower()

    def test_gate_denies_over_quota(self, mapper):
        mapper.register_bot_policy("bot-quota", max_rpm=2)
        mapper.record_usage("bot-quota")
        mapper.record_usage("bot-quota")
        result = mapper.check_gate("bot-quota")
        assert result.allowed is False

    def test_gate_denies_inactive_bot(self, mapper):
        mapper.register_bot_policy("bot-off")
        mapper.deactivate_bot("bot-off")
        result = mapper.check_gate("bot-off")
        assert result.allowed is False
        assert "deactivated" in result.reason.lower()

    def test_gate_unknown_bot(self, mapper):
        result = mapper.check_gate("ghost-bot")
        assert result.allowed is False

    def test_gate_check_result_fields(self, mapper):
        mapper.register_bot_policy("bot-fields")
        result = mapper.check_gate("bot-fields")
        assert hasattr(result, "gate_name")
        assert hasattr(result, "allowed")
        assert hasattr(result, "reason")
        assert hasattr(result, "budget_remaining")
        assert hasattr(result, "quota_remaining")


# ------------------------------------------------------------------
# Usage tracking
# ------------------------------------------------------------------

class TestUsageTracking:
    def test_record_usage_increments(self, mapper):
        mapper.register_bot_policy("bot-use")
        mapper.record_usage("bot-use")
        mapper.record_usage("bot-use")
        profile = mapper.map_to_murphy_profile("bot-use")
        # Verify indirectly via gate remaining quota
        result = mapper.check_gate("bot-use")
        assert result.quota_remaining == 58  # 60 - 2

    def test_record_usage_adds_cost(self, mapper):
        mapper.register_bot_policy("bot-cost", max_total_budget=100.0)
        mapper.record_usage("bot-cost", cost=25.0)
        mapper.record_usage("bot-cost", cost=30.0)
        report = mapper.get_budget_report("bot-cost")
        bot = report["bots"][0]
        assert bot["current_budget_used"] == 55.0
        assert bot["budget_remaining"] == 45.0

    def test_reset_quotas_single_bot(self, mapper):
        mapper.register_bot_policy("bot-r1")
        mapper.record_usage("bot-r1")
        mapper.record_usage("bot-r1")
        mapper.reset_quotas("bot-r1")
        result = mapper.check_gate("bot-r1")
        assert result.quota_remaining == 60

    def test_reset_quotas_all_bots(self, mapper):
        mapper.register_bot_policy("bot-a")
        mapper.register_bot_policy("bot-b")
        mapper.record_usage("bot-a")
        mapper.record_usage("bot-b")
        mapper.reset_quotas()
        res_a = mapper.check_gate("bot-a")
        res_b = mapper.check_gate("bot-b")
        assert res_a.quota_remaining == 60
        assert res_b.quota_remaining == 60


# ------------------------------------------------------------------
# Bot lifecycle
# ------------------------------------------------------------------

class TestBotLifecycle:
    def test_deactivate_bot(self, mapper):
        mapper.register_bot_policy("bot-lc")
        mapper.deactivate_bot("bot-lc")
        result = mapper.check_gate("bot-lc")
        assert result.allowed is False

    def test_activate_bot(self, mapper):
        mapper.register_bot_policy("bot-lc2")
        mapper.deactivate_bot("bot-lc2")
        mapper.activate_bot("bot-lc2")
        result = mapper.check_gate("bot-lc2")
        assert result.allowed is True

    def test_deactivate_unknown_bot(self, mapper):
        with pytest.raises(KeyError):
            mapper.deactivate_bot("no-bot")


# ------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------

class TestReports:
    def test_budget_report_single_bot(self, mapper):
        mapper.register_bot_policy("bot-br", max_total_budget=200.0)
        mapper.record_usage("bot-br", cost=50.0)
        report = mapper.get_budget_report("bot-br")
        assert len(report["bots"]) == 1
        assert report["bots"][0]["utilisation_pct"] == 25.0

    def test_budget_report_all_bots(self, mapper):
        mapper.register_bot_policy("b1")
        mapper.register_bot_policy("b2")
        report = mapper.get_budget_report()
        assert len(report["bots"]) == 2

    def test_stability_report_structure(self, mapper):
        mapper.register_bot_policy("bot-sr")
        report = mapper.get_stability_report("bot-sr")
        assert report["report"] == "stability"
        assert "generated_at" in report
        bot = report["bots"][0]
        for key in ("bot_id", "status", "stability_threshold", "circuit_breaker_threshold",
                     "consecutive_failures", "circuit_open", "is_active"):
            assert key in bot

    def test_status_has_all_fields(self, mapper):
        status = mapper.get_status()
        expected = {"total_bots", "active_bots", "total_policy_mappings", "total_gate_checks"}
        assert expected.issubset(status.keys())
