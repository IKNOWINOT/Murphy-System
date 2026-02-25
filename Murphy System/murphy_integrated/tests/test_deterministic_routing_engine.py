"""Tests for the Deterministic Routing Engine module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.deterministic_routing_engine import (
    DeterministicRoutingEngine,
    RoutingPolicy,
    RoutingDecision,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    return DeterministicRoutingEngine()


def _make_policy(**overrides):
    defaults = {
        "policy_id": "test-policy",
        "name": "Test Policy",
        "task_tags": ["test"],
        "route_type": "deterministic",
        "priority": 5,
        "fallback_route": "deterministic",
        "guardrails": {},
        "enabled": True,
    }
    defaults.update(overrides)
    return RoutingPolicy(**defaults)


# ------------------------------------------------------------------
# Default policy registration
# ------------------------------------------------------------------

class TestDefaultPolicies:
    def test_defaults_loaded_on_init(self, engine):
        policies = engine.list_policies()
        assert len(policies) >= 4

    def test_math_policy_exists(self, engine):
        p = engine.get_policy("policy-math")
        assert p["status"] == "ok"
        assert p["route_type"] == "deterministic"

    def test_validation_policy_exists(self, engine):
        p = engine.get_policy("policy-validation")
        assert p["status"] == "ok"
        assert p["route_type"] == "deterministic"

    def test_creative_policy_exists(self, engine):
        p = engine.get_policy("policy-creative")
        assert p["status"] == "ok"
        assert p["route_type"] == "llm"

    def test_analysis_policy_exists(self, engine):
        p = engine.get_policy("policy-analysis")
        assert p["status"] == "ok"
        assert p["route_type"] == "hybrid"

    def test_default_policy_tags(self, engine):
        p = engine.get_policy("policy-math")
        assert "math" in p["task_tags"]
        assert "compute" in p["task_tags"]


# ------------------------------------------------------------------
# Task routing by type / tags
# ------------------------------------------------------------------

class TestTaskRouting:
    def test_route_math_task(self, engine):
        result = engine.route_task("math")
        assert result["route_type"] == "deterministic"
        assert result["status"] == "routed"

    def test_route_creative_task(self, engine):
        result = engine.route_task("creative")
        assert result["route_type"] == "llm"

    def test_route_analysis_task(self, engine):
        result = engine.route_task("analysis")
        assert result["route_type"] == "hybrid"

    def test_route_by_tags(self, engine):
        result = engine.route_task("unknown", tags=["compute"])
        assert result["route_type"] == "deterministic"

    def test_route_by_task_type_match(self, engine):
        result = engine.route_task("validation")
        assert result["route_type"] == "deterministic"

    def test_route_unknown_defaults_deterministic(self, engine):
        result = engine.route_task("completely_unknown_xyz")
        assert result["route_type"] == "deterministic"
        assert result["matched_policy"] is None

    def test_route_decision_has_id(self, engine):
        result = engine.route_task("math")
        assert result["decision_id"].startswith("dec-")

    def test_route_decision_has_timestamp(self, engine):
        result = engine.route_task("math")
        assert "timestamp" in result
        assert "T" in result["timestamp"]

    def test_route_with_confidence(self, engine):
        result = engine.route_task("math", confidence=0.95)
        assert result["confidence"] == 0.95

    def test_route_matched_policy_recorded(self, engine):
        result = engine.route_task("math")
        assert result["matched_policy"] == "policy-math"


# ------------------------------------------------------------------
# Deterministic vs LLM routing
# ------------------------------------------------------------------

class TestDeterministicVsLLM:
    def test_compute_is_deterministic(self, engine):
        result = engine.route_task("task", tags=["compute"])
        assert result["route_type"] == "deterministic"

    def test_writing_is_llm(self, engine):
        result = engine.route_task("task", tags=["writing"])
        assert result["route_type"] == "llm"

    def test_brainstorm_is_llm(self, engine):
        result = engine.route_task("task", tags=["brainstorm"])
        assert result["route_type"] == "llm"

    def test_verify_is_deterministic(self, engine):
        result = engine.route_task("task", tags=["verify"])
        assert result["route_type"] == "deterministic"


# ------------------------------------------------------------------
# Hybrid routing
# ------------------------------------------------------------------

class TestHybridRouting:
    def test_research_is_hybrid(self, engine):
        result = engine.route_task("task", tags=["research"])
        assert result["route_type"] == "hybrid"

    def test_evaluate_is_hybrid(self, engine):
        result = engine.route_task("task", tags=["evaluate"])
        assert result["route_type"] == "hybrid"


# ------------------------------------------------------------------
# Guardrail evaluation
# ------------------------------------------------------------------

class TestGuardrails:
    def test_deterministic_guardrails(self, engine):
        gr = engine.evaluate_guardrails("deterministic", {})
        assert "timeout_enforcement" in gr
        assert "deterministic_output_validation" in gr

    def test_llm_guardrails(self, engine):
        gr = engine.evaluate_guardrails("llm", {})
        assert "content_filter" in gr
        assert "token_limit_enforcement" in gr

    def test_hybrid_guardrails(self, engine):
        gr = engine.evaluate_guardrails("hybrid", {})
        assert "deterministic_output_validation" in gr
        assert "content_filter" in gr

    def test_production_safety_gate(self, engine):
        gr = engine.evaluate_guardrails("deterministic", {"production": True})
        assert "production_safety_gate" in gr

    def test_strict_mode(self, engine):
        gr = engine.evaluate_guardrails("deterministic", {"strict": True})
        assert "strict_mode_enabled" in gr

    def test_pii_redaction_for_sensitive_llm(self, engine):
        gr = engine.evaluate_guardrails("llm", {"sensitive": True})
        assert "pii_redaction" in gr

    def test_guardrails_applied_in_route(self, engine):
        result = engine.route_task("math")
        assert len(result["guardrails_applied"]) > 0


# ------------------------------------------------------------------
# Fallback promotion
# ------------------------------------------------------------------

class TestFallbackPromotion:
    def test_promote_returns_promoted(self, engine):
        result = engine.promote_fallback("task-1", {"answer": 42})
        assert result["status"] == "promoted"
        assert result["promoted"] is True

    def test_promote_records_task_id(self, engine):
        result = engine.promote_fallback("task-abc", {"data": "x"})
        assert result["task_id"] == "task-abc"

    def test_promote_has_source(self, engine):
        result = engine.promote_fallback("t1", {})
        assert result["source"] == "mfgc_fallback"

    def test_promote_increments_stats(self, engine):
        engine.promote_fallback("t1", {})
        engine.promote_fallback("t2", {})
        stats = engine.get_routing_stats()
        assert stats["promotions_count"] == 2


# ------------------------------------------------------------------
# Routing statistics
# ------------------------------------------------------------------

class TestRoutingStats:
    def test_empty_stats(self, engine):
        stats = engine.get_routing_stats()
        assert stats["decisions_count"] == 0
        assert stats["average_confidence"] == 0.0
        assert stats["status"] == "ok"

    def test_stats_after_routing(self, engine):
        engine.route_task("math", confidence=0.8)
        engine.route_task("creative", confidence=0.6)
        stats = engine.get_routing_stats()
        assert stats["decisions_count"] == 2
        assert stats["average_confidence"] == 0.7

    def test_route_type_distribution(self, engine):
        engine.route_task("math")
        engine.route_task("creative")
        stats = engine.get_routing_stats()
        assert stats["route_type_distribution"]["deterministic"] >= 1
        assert stats["route_type_distribution"]["llm"] >= 1

    def test_policy_hit_rates(self, engine):
        engine.route_task("math")
        engine.route_task("math")
        stats = engine.get_routing_stats()
        assert stats["policy_hit_rates"]["policy-math"] == 2


# ------------------------------------------------------------------
# Decision history
# ------------------------------------------------------------------

class TestDecisionHistory:
    def test_empty_history(self, engine):
        h = engine.get_decision_history()
        assert h == []

    def test_history_recorded(self, engine):
        engine.route_task("math")
        h = engine.get_decision_history()
        assert len(h) == 1

    def test_history_filtered_by_type(self, engine):
        engine.route_task("math")
        engine.route_task("creative")
        h = engine.get_decision_history(task_type="math")
        assert len(h) == 1
        assert h[0]["task_type"] == "math"

    def test_history_limit(self, engine):
        for _ in range(10):
            engine.route_task("math")
        h = engine.get_decision_history(limit=3)
        assert len(h) == 3

    def test_history_most_recent_first(self, engine):
        engine.route_task("math", confidence=0.1)
        engine.route_task("math", confidence=0.9)
        h = engine.get_decision_history()
        assert h[0]["confidence"] == 0.9


# ------------------------------------------------------------------
# Route parity validation
# ------------------------------------------------------------------

class TestRouteParity:
    def test_parity_no_data(self, engine):
        result = engine.validate_route_parity("nonexistent")
        assert result["parity"] is True
        assert result["status"] == "no_data"

    def test_parity_consistent(self, engine):
        engine.route_task("math", confidence=0.8)
        engine.route_task("math", confidence=0.8)
        result = engine.validate_route_parity("math")
        assert result["parity"] is True
        assert result["status"] == "consistent"

    def test_parity_inconsistent(self, engine):
        # Route math deterministically, then register a conflicting policy
        engine.route_task("math", confidence=0.8)
        engine.register_policy(_make_policy(
            policy_id="override-math",
            task_tags=["math"],
            route_type="llm",
            priority=100,
        ))
        engine.route_task("math", confidence=0.5)
        result = engine.validate_route_parity("math")
        assert result["parity"] is False
        assert result["status"] == "inconsistent"

    def test_parity_variance(self, engine):
        engine.route_task("math", confidence=0.2)
        engine.route_task("math", confidence=0.8)
        result = engine.validate_route_parity("math")
        assert result["variance"] > 0


# ------------------------------------------------------------------
# Policy registration and retrieval
# ------------------------------------------------------------------

class TestPolicyManagement:
    def test_register_returns_id(self, engine):
        pid = engine.register_policy(_make_policy(policy_id="p1"))
        assert pid == "p1"

    def test_get_registered_policy(self, engine):
        engine.register_policy(_make_policy(policy_id="p1", name="Custom"))
        p = engine.get_policy("p1")
        assert p["name"] == "Custom"
        assert p["status"] == "ok"

    def test_get_nonexistent_policy(self, engine):
        p = engine.get_policy("nope")
        assert p["status"] == "not_found"

    def test_list_includes_registered(self, engine):
        engine.register_policy(_make_policy(policy_id="extra"))
        ids = [p["policy_id"] for p in engine.list_policies()]
        assert "extra" in ids


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_tags_default_deterministic(self, engine):
        result = engine.route_task("task", tags=["zzz_unknown"])
        assert result["route_type"] == "deterministic"
        assert result["matched_policy"] is None

    def test_no_tags_no_match(self, engine):
        result = engine.route_task("xyz_unique_type")
        assert result["matched_policy"] is None

    def test_disabled_policy_skipped(self, engine):
        engine.register_policy(_make_policy(
            policy_id="disabled",
            task_tags=["special"],
            route_type="llm",
            enabled=False,
        ))
        result = engine.route_task("task", tags=["special"])
        assert result["route_type"] == "deterministic"
        assert result["matched_policy"] is None

    def test_higher_priority_wins(self, engine):
        engine.register_policy(_make_policy(
            policy_id="low", task_tags=["dup"], route_type="llm", priority=1,
        ))
        engine.register_policy(_make_policy(
            policy_id="high", task_tags=["dup"], route_type="deterministic", priority=99,
        ))
        result = engine.route_task("task", tags=["dup"])
        assert result["route_type"] == "deterministic"
        assert result["matched_policy"] == "high"


# ------------------------------------------------------------------
# Clear / reset
# ------------------------------------------------------------------

class TestClearReset:
    def test_clear_resets_decisions(self, engine):
        engine.route_task("math")
        engine.clear()
        assert engine.get_routing_stats()["decisions_count"] == 0

    def test_clear_preserves_defaults(self, engine):
        engine.clear()
        p = engine.get_policy("policy-math")
        assert p["status"] == "ok"

    def test_clear_removes_custom_policies(self, engine):
        engine.register_policy(_make_policy(policy_id="custom-1"))
        engine.clear()
        p = engine.get_policy("custom-1")
        assert p["status"] == "not_found"

    def test_clear_resets_promotions(self, engine):
        engine.promote_fallback("t1", {})
        engine.clear()
        stats = engine.get_routing_stats()
        assert stats["promotions_count"] == 0


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_shape(self, engine):
        s = engine.get_status()
        assert s["engine"] == "DeterministicRoutingEngine"
        assert s["status"] == "active"
        assert "policies_registered" in s
        assert "total_decisions" in s
