"""Tests for the HITL Graduation Engine module."""

import os

import pytest
from datetime import datetime, timezone

from src.hitl_graduation_engine import (
    GRADUATION_THRESHOLD,
    HITLGraduationEngine,
    HITLItem,
    HITLRecommendation,
    HITLRegistry,
    SEVERITY_WEIGHTS,
    SUPERVISED_THRESHOLD,
)
from src.wingman_protocol import WingmanProtocol


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_protocol_with_history(approved_count: int, rejected_count: int) -> tuple:
    """Return (protocol, pair_id) pre-populated with the requested approval history."""
    protocol = WingmanProtocol()
    pair = protocol.create_pair(
        subject="test-subject",
        executor_id="exec-1",
        validator_id="val-1",
    )
    # Approved outputs pass the default runbook (non-empty result, no PII, etc.)
    for _ in range(approved_count):
        protocol.validate_output(pair.pair_id, {"result": "ok"})
    # Rejected outputs have an empty result, which triggers BLOCK
    for _ in range(rejected_count):
        protocol.validate_output(pair.pair_id, {})
    return protocol, pair.pair_id


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    return HITLGraduationEngine()


@pytest.fixture
def registry():
    return HITLRegistry()


@pytest.fixture
def protocol_10_approved():
    """10 approved, 0 rejected → success_rate = 1.0."""
    proto, pair_id = _make_protocol_with_history(10, 0)
    return proto, pair_id


@pytest.fixture
def protocol_8_approved_2_rejected():
    """8 approved, 2 rejected → success_rate = 0.8."""
    proto, pair_id = _make_protocol_with_history(8, 2)
    return proto, pair_id


@pytest.fixture
def protocol_empty():
    """No history → success_rate = 0.0."""
    protocol = WingmanProtocol()
    pair = protocol.create_pair("test", "e", "v")
    return protocol, pair.pair_id


# ------------------------------------------------------------------
# Graduation score math
# ------------------------------------------------------------------

class TestGraduationScoreMath:

    def test_success_rate_all_approved(self, engine, protocol_10_approved):
        proto, pair_id = protocol_10_approved
        sr = engine.compute_success_rate(proto, pair_id)
        assert sr == pytest.approx(1.0)

    def test_success_rate_partial(self, engine, protocol_8_approved_2_rejected):
        proto, pair_id = protocol_8_approved_2_rejected
        sr = engine.compute_success_rate(proto, pair_id)
        assert sr == pytest.approx(0.8)

    def test_success_rate_empty_history(self, engine, protocol_empty):
        proto, pair_id = protocol_empty
        sr = engine.compute_success_rate(proto, pair_id)
        assert sr == pytest.approx(0.0)

    def test_success_rate_unknown_pair(self, engine):
        protocol = WingmanProtocol()
        sr = engine.compute_success_rate(protocol, "wp-nonexistent")
        assert sr == pytest.approx(0.0)

    def test_risk_score_formula(self, engine):
        # R = weight × (1 - S) × consequence_factor
        # severity=high (0.8), S=0.8, cf=0.5 → 0.8 × 0.2 × 0.5 = 0.08
        r = engine.compute_risk_score(0.8, "high", 0.5)
        assert r == pytest.approx(0.8 * 0.2 * 0.5)

    def test_risk_score_critical_full_failure(self, engine):
        # severity=critical (1.0), S=0.0, cf=1.0 → 1.0 × 1.0 × 1.0 = 1.0
        r = engine.compute_risk_score(0.0, "critical", 1.0)
        assert r == pytest.approx(1.0)

    def test_risk_score_low_severity(self, engine):
        r = engine.compute_risk_score(0.5, "low", 0.5)
        assert r == pytest.approx(SEVERITY_WEIGHTS["low"] * 0.5 * 0.5)

    def test_impact_score_clamped_above(self, engine):
        # time_blocked > cycle_time should clamp to 1.0
        assert engine.compute_impact_score(7200.0, 3600.0) == pytest.approx(1.0)

    def test_impact_score_clamped_below(self, engine):
        assert engine.compute_impact_score(-1.0, 3600.0) == pytest.approx(0.0)

    def test_impact_score_half(self, engine):
        assert engine.compute_impact_score(1800.0, 3600.0) == pytest.approx(0.5)

    def test_impact_score_zero_cycle_time(self, engine):
        assert engine.compute_impact_score(100.0, 0.0) == pytest.approx(0.0)

    def test_graduation_score_formula(self, engine):
        # G = S × (1 - R) × I
        g = engine.compute_graduation_score(0.9, 0.1, 0.9)
        assert g == pytest.approx(0.9 * 0.9 * 0.9)

    def test_graduation_score_zero_when_impact_zero(self, engine):
        g = engine.compute_graduation_score(1.0, 0.0, 0.0)
        assert g == pytest.approx(0.0)

    def test_graduation_score_zero_when_success_zero(self, engine):
        g = engine.compute_graduation_score(0.0, 0.5, 1.0)
        assert g == pytest.approx(0.0)

    def test_severity_weight_mapping(self, engine):
        assert SEVERITY_WEIGHTS["critical"] == pytest.approx(1.0)
        assert SEVERITY_WEIGHTS["high"] == pytest.approx(0.8)
        assert SEVERITY_WEIGHTS["medium"] == pytest.approx(0.5)
        assert SEVERITY_WEIGHTS["low"] == pytest.approx(0.2)


# ------------------------------------------------------------------
# Mode transitions
# ------------------------------------------------------------------

class TestModeTransitions:

    def test_manual_to_supervised_on_sufficient_score(self, engine):
        mode = engine.recommend_mode("manual", SUPERVISED_THRESHOLD)
        assert mode == "supervised"

    def test_manual_stays_manual_below_threshold(self, engine):
        mode = engine.recommend_mode("manual", SUPERVISED_THRESHOLD - 0.01)
        assert mode == "manual"

    def test_supervised_to_automated_on_sufficient_score(self, engine):
        mode = engine.recommend_mode("supervised", GRADUATION_THRESHOLD)
        assert mode == "automated"

    def test_supervised_stays_supervised_below_auto_threshold(self, engine):
        mode = engine.recommend_mode("supervised", GRADUATION_THRESHOLD - 0.01)
        assert mode == "supervised"

    def test_registry_graduate_manual_to_supervised(self, registry):
        registry.register_item("i1", "ops", "desc")
        result = registry.graduate_item("i1", "supervised")
        assert result is True
        assert registry.get_item("i1").current_mode == "supervised"

    def test_registry_graduate_supervised_to_automated(self, registry):
        registry.register_item("i2", "ops", "desc")
        registry.graduate_item("i2", "supervised")
        result = registry.graduate_item("i2", "automated")
        assert result is True
        assert registry.get_item("i2").current_mode == "automated"

    def test_graduate_preserves_history(self, registry):
        registry.register_item("i3", "ops", "desc")
        registry.graduate_item("i3", "supervised")
        registry.graduate_item("i3", "automated")
        item = registry.get_item("i3")
        assert "manual" in item.mode_history
        assert "supervised" in item.mode_history

    def test_graduate_invalid_mode_returns_false(self, registry):
        registry.register_item("i4", "ops", "desc")
        result = registry.graduate_item("i4", "turbo_mode")
        assert result is False
        assert registry.get_item("i4").current_mode == "manual"

    def test_graduate_unknown_item_returns_false(self, registry):
        result = registry.graduate_item("nonexistent", "automated")
        assert result is False


# ------------------------------------------------------------------
# Rollback
# ------------------------------------------------------------------

class TestRollback:

    def test_rollback_from_supervised_to_manual(self, registry):
        registry.register_item("r1", "ops", "desc")
        registry.graduate_item("r1", "supervised")
        result = registry.rollback_item("r1")
        assert result is True
        assert registry.get_item("r1").current_mode == "manual"

    def test_rollback_from_automated_to_supervised(self, registry):
        registry.register_item("r2", "ops", "desc")
        registry.graduate_item("r2", "supervised")
        registry.graduate_item("r2", "automated")
        registry.rollback_item("r2")
        assert registry.get_item("r2").current_mode == "supervised"

    def test_rollback_always_available_multiple_times(self, registry):
        registry.register_item("r3", "ops", "desc")
        registry.graduate_item("r3", "supervised")
        registry.graduate_item("r3", "automated")
        assert registry.rollback_item("r3") is True  # automated → supervised
        assert registry.rollback_item("r3") is True  # supervised → manual
        assert registry.get_item("r3").current_mode == "manual"

    def test_rollback_when_no_history_returns_false(self, registry):
        # register_item starts with current_mode="manual" and mode_history=["manual"].
        # The first rollback pops the "manual" entry from history and sets current_mode
        # back to "manual", leaving history empty.  A second rollback has nothing left
        # to pop and must return False.
        registry.register_item("r4", "ops", "desc")
        registry.rollback_item("r4")   # pops the initial "manual" entry; history now []
        result = registry.rollback_item("r4")
        assert result is False

    def test_rollback_unknown_item_returns_false(self, registry):
        result = registry.rollback_item("nonexistent")
        assert result is False


# ------------------------------------------------------------------
# Recommendation generation
# ------------------------------------------------------------------

class TestRecommendationGeneration:

    def test_recommendation_fields_present(self, registry, protocol_10_approved):
        proto, pair_id = protocol_10_approved
        registry.register_item("rec1", "ops", "test process")
        rec = registry.evaluate_item(
            "rec1", proto, pair_id=pair_id, cycle_time=3600.0, time_blocked=3600.0
        )
        assert isinstance(rec, HITLRecommendation)
        assert rec.item_id == "rec1"
        assert rec.current_mode in ("manual", "supervised", "automated")
        assert rec.recommended_mode in ("manual", "supervised", "automated")
        assert isinstance(rec.graduation_score, float)
        assert isinstance(rec.success_rate, float)
        assert isinstance(rec.risk_score, float)
        assert isinstance(rec.impact_score, float)
        assert isinstance(rec.reasoning, str) and len(rec.reasoning) > 0
        assert 0.0 <= rec.confidence <= 1.0
        assert isinstance(rec.suggested_actions, list) and len(rec.suggested_actions) > 0
        assert isinstance(rec.rollback_plan, str) and len(rec.rollback_plan) > 0
        assert isinstance(rec.created_at, str)

    def test_reasoning_mentions_graduation_score(self, registry, protocol_10_approved):
        proto, pair_id = protocol_10_approved
        registry.register_item("rec2", "ops", "test")
        rec = registry.evaluate_item(
            "rec2", proto, pair_id=pair_id, cycle_time=3600.0, time_blocked=3600.0
        )
        assert "graduation score" in rec.reasoning.lower() or "%" in rec.reasoning

    def test_reasoning_mentions_recommended_mode(self, registry, protocol_10_approved):
        proto, pair_id = protocol_10_approved
        registry.register_item("rec3", "ops", "test")
        rec = registry.evaluate_item(
            "rec3", proto, pair_id=pair_id, cycle_time=3600.0, time_blocked=3600.0
        )
        assert rec.recommended_mode in rec.reasoning

    def test_rollback_plan_mentions_item_id(self, registry, protocol_empty):
        proto, pair_id = protocol_empty
        registry.register_item("rec4", "ops", "test")
        rec = registry.evaluate_item("rec4", proto, pair_id=pair_id)
        assert "rec4" in rec.rollback_plan

    def test_created_at_is_valid_iso_utc(self, registry, protocol_empty):
        proto, pair_id = protocol_empty
        registry.register_item("rec5", "ops", "test")
        rec = registry.evaluate_item("rec5", proto, pair_id=pair_id)
        # Should parse without error and be UTC
        dt = datetime.fromisoformat(rec.created_at)
        assert dt.tzinfo is not None

    def test_recommendation_stored_on_item(self, registry, protocol_10_approved):
        proto, pair_id = protocol_10_approved
        registry.register_item("rec6", "ops", "test")
        rec = registry.evaluate_item(
            "rec6", proto, pair_id=pair_id, cycle_time=3600.0, time_blocked=3600.0
        )
        item = registry.get_item("rec6")
        assert item.latest_recommendation is rec


# ------------------------------------------------------------------
# Boundary conditions
# ------------------------------------------------------------------

class TestBoundaryConditions:

    def test_g_exactly_at_graduation_threshold_recommends_automated(self, engine):
        # With G == GRADUATION_THRESHOLD the engine should recommend "automated"
        mode = engine.recommend_mode("supervised", GRADUATION_THRESHOLD)
        assert mode == "automated"

    def test_g_exactly_at_supervised_threshold_recommends_supervised(self, engine):
        mode = engine.recommend_mode("manual", SUPERVISED_THRESHOLD)
        assert mode == "supervised"

    def test_g_just_below_supervised_threshold_stays_manual(self, engine):
        mode = engine.recommend_mode("manual", SUPERVISED_THRESHOLD - 1e-9)
        assert mode == "manual"

    def test_g_just_below_graduation_threshold_stays_supervised(self, engine):
        mode = engine.recommend_mode("supervised", GRADUATION_THRESHOLD - 1e-9)
        assert mode == "supervised"

    def test_impact_score_exactly_one(self, engine):
        assert engine.compute_impact_score(3600.0, 3600.0) == pytest.approx(1.0)

    def test_impact_score_exactly_zero(self, engine):
        assert engine.compute_impact_score(0.0, 3600.0) == pytest.approx(0.0)

    def test_graduation_score_max(self, engine):
        # S=1, R=0, I=1 → G=1
        g = engine.compute_graduation_score(1.0, 0.0, 1.0)
        assert g == pytest.approx(1.0)

    def test_graduation_score_min(self, engine):
        g = engine.compute_graduation_score(0.0, 1.0, 0.0)
        assert g == pytest.approx(0.0)

    def test_unknown_severity_defaults_to_medium_weight(self, engine):
        r_unknown = engine.compute_risk_score(0.5, "nonexistent_severity", 1.0)
        r_medium = engine.compute_risk_score(0.5, "medium", 1.0)
        assert r_unknown == pytest.approx(r_medium)

    def test_register_item_with_unknown_severity_defaults_to_medium(self, registry):
        item = registry.register_item("bnd1", "ops", "desc", severity="super_critical")
        assert item.severity == "medium"


# ------------------------------------------------------------------
# Integration with WingmanProtocol
# ------------------------------------------------------------------

class TestWingmanIntegration:

    def test_evaluate_with_all_approved_reaches_supervised_or_automated(self):
        """With full approval rate and full impact, score should qualify for supervised."""
        protocol, pair_id = _make_protocol_with_history(10, 0)
        registry = HITLRegistry()
        registry.register_item(
            "int1", "ops", "full approval process",
            severity="low", consequence_factor=0.1,
        )
        rec = registry.evaluate_item(
            "int1", protocol, pair_id=pair_id,
            cycle_time=3600.0, time_blocked=3600.0,
        )
        assert rec.success_rate == pytest.approx(1.0)
        assert rec.graduation_score > SUPERVISED_THRESHOLD

    def test_evaluate_with_no_history_stays_manual(self):
        protocol = WingmanProtocol()
        pair = protocol.create_pair("s", "e", "v")
        registry = HITLRegistry()
        registry.register_item("int2", "ops", "no history process")
        rec = registry.evaluate_item(
            "int2", protocol, pair_id=pair.pair_id,
            cycle_time=3600.0, time_blocked=3600.0,
        )
        assert rec.success_rate == pytest.approx(0.0)
        assert rec.graduation_score == pytest.approx(0.0)
        assert rec.recommended_mode == "manual"

    def test_evaluate_all_returns_one_recommendation_per_item(self):
        protocol, pair_id = _make_protocol_with_history(5, 0)
        registry = HITLRegistry()
        registry.register_item("a1", "ops", "item a")
        registry.register_item("a2", "dev", "item b")
        # Use same pair_id for both (simplified integration)
        registry.evaluate_item("a1", protocol, pair_id=pair_id)
        registry.evaluate_item("a2", protocol, pair_id=pair_id)
        recs = registry.evaluate_all(protocol)
        assert len(recs) == 2

    def test_graduation_after_evaluation(self):
        protocol, pair_id = _make_protocol_with_history(10, 0)
        registry = HITLRegistry()
        registry.register_item(
            "int3", "ops", "high-volume approved process",
            severity="low", consequence_factor=0.05,
        )
        rec = registry.evaluate_item(
            "int3", protocol, pair_id=pair_id,
            cycle_time=100.0, time_blocked=100.0,
        )
        # G should be very high (low risk, perfect success, full impact)
        if rec.graduation_score >= GRADUATION_THRESHOLD:
            assert registry.graduate_item("int3", "automated") is True
            assert registry.get_item("int3").current_mode == "automated"
        elif rec.graduation_score >= SUPERVISED_THRESHOLD:
            assert registry.graduate_item("int3", "supervised") is True
            assert registry.get_item("int3").current_mode == "supervised"

    def test_full_journey_manual_supervised_automated_rollback(self):
        """Full lifecycle: register → evaluate → graduate → rollback."""
        protocol, pair_id = _make_protocol_with_history(10, 0)
        registry = HITLRegistry()
        registry.register_item(
            "journey1", "ops", "journey process",
            severity="low", consequence_factor=0.1,
        )

        # Step 1: move to supervised manually (simulate manual approval)
        assert registry.graduate_item("journey1", "supervised") is True

        # Step 2: move to automated
        assert registry.graduate_item("journey1", "automated") is True

        # Step 3: rollback to supervised
        assert registry.rollback_item("journey1") is True
        assert registry.get_item("journey1").current_mode == "supervised"

        # Step 4: rollback to manual
        assert registry.rollback_item("journey1") is True
        assert registry.get_item("journey1").current_mode == "manual"

    def test_dashboard_data_reflects_item_modes(self):
        protocol, pair_id = _make_protocol_with_history(5, 5)
        registry = HITLRegistry()
        registry.register_item("d1", "ops", "item1")
        registry.register_item("d2", "ops", "item2")
        registry.graduate_item("d2", "supervised")
        data = registry.get_dashboard_data()
        assert data["total_items"] == 2
        assert data["mode_counts"]["manual"] == 1
        assert data["mode_counts"]["supervised"] == 1
        assert "generated_at" in data

    def test_evaluate_unknown_item_raises(self):
        protocol, pair_id = _make_protocol_with_history(5, 0)
        registry = HITLRegistry()
        with pytest.raises(KeyError):
            registry.evaluate_item("nonexistent", protocol)

    def test_list_items_filter_by_domain(self):
        registry = HITLRegistry()
        registry.register_item("lf1", "ops", "ops item")
        registry.register_item("lf2", "dev", "dev item")
        registry.register_item("lf3", "ops", "another ops item")
        ops_items = registry.list_items(domain="ops")
        assert len(ops_items) == 2
        assert all(i.domain == "ops" for i in ops_items)

    def test_list_items_filter_by_mode(self):
        registry = HITLRegistry()
        registry.register_item("lm1", "ops", "item1")
        registry.register_item("lm2", "ops", "item2")
        registry.graduate_item("lm2", "supervised")
        supervised = registry.list_items(mode="supervised")
        assert len(supervised) == 1
        assert supervised[0].item_id == "lm2"
