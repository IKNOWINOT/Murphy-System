"""
Tests for Murphy Wingman Evolution (Subsystem 6).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import pytest

from src.murphy_wingman_evolution import (
    AutoRunbookGenerator,
    CascadeStage,
    CascadingWingman,
    RunbookEvolver,
    ValidationMetrics,
    WingmanEvolution,
    WingmanFactory,
    WingmanScorecard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def evolution():
    return WingmanEvolution()


@pytest.fixture
def factory():
    return WingmanFactory()


@pytest.fixture
def evolver():
    return RunbookEvolver()


# ---------------------------------------------------------------------------
# ValidationMetrics
# ---------------------------------------------------------------------------

class TestValidationMetrics:

    def test_approval_rate(self):
        m = ValidationMetrics(pair_id="p1", total_validations=10, approved_count=7, rejected_count=3)
        assert abs(m.approval_rate - 0.7) < 1e-9

    def test_rejection_rate(self):
        m = ValidationMetrics(pair_id="p1", total_validations=10, approved_count=7, rejected_count=3)
        assert abs(m.rejection_rate - 0.3) < 1e-9

    def test_avg_validation_time(self):
        m = ValidationMetrics(pair_id="p1", total_validations=4, total_validation_time_s=20.0)
        assert m.avg_validation_time_s == 5.0

    def test_zero_total_does_not_divide_by_zero(self):
        m = ValidationMetrics(pair_id="p0")
        assert m.approval_rate == 0.0
        assert m.rejection_rate == 0.0
        assert m.avg_validation_time_s == 0.0

    def test_human_override_rate(self):
        m = ValidationMetrics(pair_id="p1", total_validations=10, human_override_count=2)
        assert abs(m.human_override_rate - 0.2) < 1e-9


# ---------------------------------------------------------------------------
# WingmanScorecard
# ---------------------------------------------------------------------------

class TestWingmanScorecard:

    def test_perfect_precision_recall(self):
        m = ValidationMetrics(
            pair_id="p1",
            total_validations=10,
            approved_count=10,
            rejected_count=0,
            false_positive_count=0,
            false_negative_count=0,
        )
        sc = WingmanScorecard.compute(m)
        assert sc.precision == 1.0
        assert sc.recall == 1.0
        assert sc.f1 == 1.0

    def test_f1_zero_when_all_false_positive(self):
        m = ValidationMetrics(
            pair_id="p1",
            total_validations=5,
            approved_count=5,
            rejected_count=0,
            false_positive_count=5,
            false_negative_count=0,
        )
        sc = WingmanScorecard.compute(m)
        assert sc.precision == 0.0

    def test_computed_at_set(self):
        m = ValidationMetrics(pair_id="p1")
        sc = WingmanScorecard.compute(m)
        assert sc.computed_at is not None


# ---------------------------------------------------------------------------
# RunbookEvolver
# ---------------------------------------------------------------------------

class TestRunbookEvolver:

    def test_suggests_relax_for_never_failing_rule(self, evolver):
        history = [
            {"results": [{"rule_id": "check_has_output", "passed": True}]} for _ in range(10)
        ]
        m = ValidationMetrics(pair_id="p1", total_validations=10)
        suggestions = evolver.analyze("p1", history, m)
        assert any(s.rule_id == "check_has_output" and s.suggestion_type == "relax" for s in suggestions)

    def test_suggests_tighten_for_always_failing_rule(self, evolver):
        history = [
            {"results": [{"rule_id": "check_confidence_threshold", "passed": False}]} for _ in range(10)
        ]
        m = ValidationMetrics(pair_id="p1", total_validations=10)
        suggestions = evolver.analyze("p1", history, m)
        assert any(s.rule_id == "check_confidence_threshold" and s.suggestion_type == "tighten" for s in suggestions)

    def test_suggests_new_rule_high_override(self, evolver):
        m = ValidationMetrics(
            pair_id="p1",
            total_validations=10,
            human_override_count=4,
        )
        suggestions = evolver.analyze("p1", [], m)
        assert any(s.suggestion_type == "add" for s in suggestions)

    def test_no_suggestions_mixed_results(self, evolver):
        # Mix of passes and failures shouldn't trigger tighten/relax
        history = []
        for i in range(10):
            history.append({"results": [{"rule_id": "check_no_pii", "passed": i % 2 == 0}]})
        m = ValidationMetrics(pair_id="p1", total_validations=10)
        suggestions = evolver.analyze("p1", history, m)
        # Neither threshold triggered for 50/50 split
        rule_suggestions = [s for s in suggestions if s.rule_id == "check_no_pii"]
        assert len(rule_suggestions) == 0

    def test_get_suggestions_by_pair(self, evolver):
        history = [{"results": [{"rule_id": "rule_x", "passed": True}]} for _ in range(10)]
        m = ValidationMetrics(pair_id="pair-A", total_validations=10)
        evolver.analyze("pair-A", history, m)
        evolver.analyze("pair-B", history, m)
        assert all(s.pair_id == "pair-A" for s in evolver.get_suggestions("pair-A"))


# ---------------------------------------------------------------------------
# AutoRunbookGenerator
# ---------------------------------------------------------------------------

class TestAutoRunbookGenerator:

    def test_generates_runbook(self):
        gen = AutoRunbookGenerator()
        spec = gen.generate("PE Drawing Review", "engineering")
        assert spec["runbook_id"] is not None
        assert "engineering" in spec["domain"]
        assert len(spec["rules"]) > 0

    def test_default_domain_fallback(self):
        gen = AutoRunbookGenerator()
        spec = gen.generate("Unknown Subject")
        assert "check_has_output" in spec["rules"]

    def test_safety_domain_rules(self):
        gen = AutoRunbookGenerator()
        spec = gen.generate("Autonomy Decision", "safety")
        assert "check_gate_clearance" in spec["rules"]

    def test_finance_domain_rules(self):
        gen = AutoRunbookGenerator()
        spec = gen.generate("CPA Sign-off", "finance")
        assert "check_budget_limit" in spec["rules"]


# ---------------------------------------------------------------------------
# CascadingWingman
# ---------------------------------------------------------------------------

class TestCascadingWingman:

    def _make_cascade(self) -> CascadingWingman:
        return CascadingWingman(
            cascade_id="cas-1",
            stages=[
                CascadeStage("s1", "pair-1", "executor"),
                CascadeStage("s2", "pair-2", "validator"),
                CascadeStage("s3", "pair-3", "credential_gate", requires_credential=True),
            ],
        )

    def test_initial_state(self):
        cw = self._make_cascade()
        assert not cw.is_complete()
        assert cw.current_stage().stage_name == "executor"

    def test_complete_stages_in_order(self):
        cw = self._make_cascade()
        cw.complete_stage("s1", {"approved": True})
        assert cw.current_stage().stage_name == "validator"
        cw.complete_stage("s2", {"approved": True})
        assert cw.current_stage().stage_name == "credential_gate"
        cw.complete_stage("s3", {"approved": True})
        assert cw.is_complete()

    def test_complete_nonexistent_stage(self):
        cw = self._make_cascade()
        assert cw.complete_stage("nonexistent", {}) is False

    def test_summary(self):
        cw = self._make_cascade()
        cw.complete_stage("s1", {"approved": True})
        summary = cw.get_summary()
        assert summary["completed_stages"] == 1
        assert summary["total_stages"] == 3
        assert summary["is_complete"] is False


# ---------------------------------------------------------------------------
# WingmanFactory
# ---------------------------------------------------------------------------

class TestWingmanFactory:

    def test_auto_create_pair(self, factory):
        pair = factory.auto_create_pair("Drawing Approval", "drawing")
        assert pair["subject"] == "Drawing Approval"
        assert pair["capability_type"] == "drawing"
        assert pair["domain"] == "engineering"
        assert "runbook_spec" in pair

    def test_pair_has_ids(self, factory):
        pair = factory.auto_create_pair("Sensor Pipeline", "sensor_fusion")
        assert pair["executor_id"] is not None
        assert pair["validator_id"] is not None

    def test_list_pairs_all(self, factory):
        factory.auto_create_pair("A", "action")
        factory.auto_create_pair("B", "osmosis")
        assert len(factory.list_pairs()) == 2

    def test_list_pairs_filtered(self, factory):
        factory.auto_create_pair("A", "drawing")
        factory.auto_create_pair("B", "drawing")
        factory.auto_create_pair("C", "osmosis")
        assert len(factory.list_pairs("drawing")) == 2
        assert len(factory.list_pairs("osmosis")) == 1

    def test_custom_executor_validator(self, factory):
        pair = factory.auto_create_pair(
            "Custom", "action", executor_id="my-exec", validator_id="my-val"
        )
        assert pair["executor_id"] == "my-exec"
        assert pair["validator_id"] == "my-val"


# ---------------------------------------------------------------------------
# WingmanEvolution (integration)
# ---------------------------------------------------------------------------

class TestWingmanEvolution:

    def test_record_validation(self, evolution):
        evolution.record_validation("p1", approved=True, validation_time_s=0.5)
        evolution.record_validation("p1", approved=False)
        m = evolution.get_metrics("p1")
        assert m is not None
        assert m.total_validations == 2
        assert m.approved_count == 1
        assert m.rejected_count == 1

    def test_get_missing_metrics(self, evolution):
        assert evolution.get_metrics("nonexistent") is None

    def test_scorecard(self, evolution):
        evolution.record_validation("p1", approved=True)
        sc = evolution.get_scorecard("p1")
        assert sc is not None
        assert sc.pair_id == "p1"

    def test_evolve(self, evolution):
        evolution.record_validation("p1", approved=True)
        history = [{"results": [{"rule_id": "r1", "passed": True}]} for _ in range(10)]
        suggestions = evolution.evolve("p1", history)
        assert isinstance(suggestions, list)

    def test_get_status(self, evolution):
        evolution.record_validation("p1", approved=True)
        evolution.factory().auto_create_pair("X", "action")
        status = evolution.get_status()
        assert status["total_pairs_tracked"] == 1
        assert status["total_validations"] == 1
        assert status["factory_pairs_created"] == 1
