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


# ---------------------------------------------------------------------------
# Production-readiness tests (30+ new cases)
# ---------------------------------------------------------------------------

import threading

class TestValidationMetricsProduction:

    def test_zero_division_safety_approval_rate(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1")
        assert m.approval_rate == 0.0

    def test_zero_division_safety_rejection_rate(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1")
        assert m.rejection_rate == 0.0

    def test_zero_division_avg_time(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1")
        assert m.avg_validation_time_s == 0.0

    def test_zero_division_human_override_rate(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1")
        assert m.human_override_rate == 0.0

    def test_zero_division_false_positive_rate(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1")
        assert m.false_positive_rate == 0.0

    def test_approval_rate_calculation(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1", total_validations=10, approved_count=7)
        assert abs(m.approval_rate - 0.7) < 1e-6

    def test_override_rate_calculation(self):
        from src.murphy_wingman_evolution import ValidationMetrics
        m = ValidationMetrics(pair_id="p1", total_validations=10, human_override_count=3)
        assert abs(m.human_override_rate - 0.3) < 1e-6


class TestWingmanScorecardProduction:

    def test_perfect_scorecard(self):
        from src.murphy_wingman_evolution import ValidationMetrics, WingmanScorecard
        m = ValidationMetrics(pair_id="p1", total_validations=10, approved_count=10,
                              false_positive_count=0, false_negative_count=0)
        sc = WingmanScorecard.compute(m)
        assert sc.precision == 1.0
        assert sc.recall == 1.0
        assert sc.f1 == 1.0

    def test_all_false_positives(self):
        from src.murphy_wingman_evolution import ValidationMetrics, WingmanScorecard
        m = ValidationMetrics(pair_id="p1", total_validations=5, approved_count=5,
                              false_positive_count=5, false_negative_count=0)
        sc = WingmanScorecard.compute(m)
        assert sc.precision == 0.0
        assert sc.f1 == 0.0

    def test_all_false_negatives(self):
        from src.murphy_wingman_evolution import ValidationMetrics, WingmanScorecard
        m = ValidationMetrics(pair_id="p1", total_validations=5, approved_count=0,
                              false_positive_count=0, false_negative_count=5)
        sc = WingmanScorecard.compute(m)
        assert sc.recall == 0.0
        assert sc.f1 == 0.0

    def test_mixed_scorecard(self):
        from src.murphy_wingman_evolution import ValidationMetrics, WingmanScorecard
        # 8 approved, 2 FP, 3 FN → TP=6, precision=6/8=0.75, recall=6/9=0.667
        m = ValidationMetrics(pair_id="p1", total_validations=10, approved_count=8,
                              false_positive_count=2, false_negative_count=3)
        sc = WingmanScorecard.compute(m)
        assert sc.precision > 0.0
        assert sc.recall > 0.0
        assert sc.f1 > 0.0


class TestRunbookEvolverProduction:

    def _make_history(self, rule_id, passes, fails):
        history = []
        for _ in range(passes):
            history.append({"results": [{"rule_id": rule_id, "passed": True}]})
        for _ in range(fails):
            history.append({"results": [{"rule_id": rule_id, "passed": False}]})
        return history

    def test_suggest_relax_for_never_failing_rule(self):
        from src.murphy_wingman_evolution import RunbookEvolver, ValidationMetrics
        evolver = RunbookEvolver()
        history = self._make_history("rule_always_pass", 10, 0)
        metrics = ValidationMetrics(pair_id="p1", total_validations=10)
        suggestions = evolver.analyze("p1", history, metrics)
        relax = [s for s in suggestions if s.suggestion_type == "relax"]
        assert len(relax) >= 1

    def test_suggest_tighten_for_always_failing_rule(self):
        from src.murphy_wingman_evolution import RunbookEvolver, ValidationMetrics
        evolver = RunbookEvolver()
        history = self._make_history("rule_always_fail", 0, 10)
        metrics = ValidationMetrics(pair_id="p1", total_validations=10)
        suggestions = evolver.analyze("p1", history, metrics)
        tighten = [s for s in suggestions if s.suggestion_type == "tighten"]
        assert len(tighten) >= 1

    def test_suggest_new_rule_for_high_override_rate(self):
        from src.murphy_wingman_evolution import RunbookEvolver, ValidationMetrics
        evolver = RunbookEvolver()
        metrics = ValidationMetrics(pair_id="p1", total_validations=10,
                                     human_override_count=5)
        suggestions = evolver.analyze("p1", [], metrics)
        add_rules = [s for s in suggestions if s.suggestion_type == "add"]
        assert len(add_rules) >= 1

    def test_no_suggestion_when_insufficient_data(self):
        from src.murphy_wingman_evolution import RunbookEvolver, ValidationMetrics
        evolver = RunbookEvolver()
        history = self._make_history("rule_x", 3, 0)  # only 3 samples
        metrics = ValidationMetrics(pair_id="p1", total_validations=3)
        suggestions = evolver.analyze("p1", history, metrics)
        # fewer than 5 samples → no suggestions for that rule
        assert all(s.rule_id != "rule_x" for s in suggestions if s.suggestion_type != "add")

    def test_get_suggestions_filter_by_pair(self):
        from src.murphy_wingman_evolution import RunbookEvolver, ValidationMetrics
        evolver = RunbookEvolver()
        hist = self._make_history("rule_x", 10, 0)
        metrics = ValidationMetrics(pair_id="pair-A", total_validations=10)
        evolver.analyze("pair-A", hist, metrics)
        evolver.analyze("pair-B", hist, metrics)
        sug_a = evolver.get_suggestions("pair-A")
        assert all(s.pair_id == "pair-A" for s in sug_a)


class TestAutoRunbookGeneratorProduction:

    def test_engineering_runbook(self):
        from src.murphy_wingman_evolution import AutoRunbookGenerator
        gen = AutoRunbookGenerator()
        rb = gen.generate("beam_calc", "engineering")
        assert "check_credential_active" in rb["rules"]
        assert rb["domain"] == "engineering"

    def test_safety_runbook(self):
        from src.murphy_wingman_evolution import AutoRunbookGenerator
        gen = AutoRunbookGenerator()
        rb = gen.generate("emergency_stop", "safety")
        assert "check_gate_clearance" in rb["rules"]

    def test_finance_runbook(self):
        from src.murphy_wingman_evolution import AutoRunbookGenerator
        gen = AutoRunbookGenerator()
        rb = gen.generate("invoice_approval", "finance")
        assert "check_budget_limit" in rb["rules"]

    def test_default_domain_fallback(self):
        from src.murphy_wingman_evolution import AutoRunbookGenerator
        gen = AutoRunbookGenerator()
        rb = gen.generate("unknown_subject")
        assert rb["domain"] == "default"
        assert "check_has_output" in rb["rules"]

    def test_runbook_has_id_and_timestamp(self):
        from src.murphy_wingman_evolution import AutoRunbookGenerator
        gen = AutoRunbookGenerator()
        rb = gen.generate("test_subject", "default")
        assert "runbook_id" in rb
        assert "generated_at" in rb


class TestCascadingWingmanProduction:

    def test_cascade_completes_in_order(self):
        from src.murphy_wingman_evolution import CascadingWingman, CascadeStage
        stages = [
            CascadeStage("s1", "wp-1", "execute"),
            CascadeStage("s2", "wp-2", "validate"),
            CascadeStage("s3", "wp-3", "credential_gate"),
        ]
        cw = CascadingWingman("cascade-1", stages)
        assert cw.current_stage().stage_id == "s1"
        cw.complete_stage("s1", {"approved": True})
        assert cw.current_stage().stage_id == "s2"
        cw.complete_stage("s2", {"approved": True})
        cw.complete_stage("s3", {"approved": True})
        assert cw.is_complete() is True

    def test_cascade_summary_reports_all_passed(self):
        from src.murphy_wingman_evolution import CascadingWingman, CascadeStage
        stages = [
            CascadeStage("s1", "wp-1", "execute"),
            CascadeStage("s2", "wp-2", "validate"),
        ]
        cw = CascadingWingman("cascade-2", stages)
        cw.complete_stage("s1", {"approved": True})
        cw.complete_stage("s2", {"approved": True})
        summary = cw.get_summary()
        assert summary["all_passed"] is True

    def test_cascade_not_complete_after_partial(self):
        from src.murphy_wingman_evolution import CascadingWingman, CascadeStage
        stages = [CascadeStage("s1", "wp-1", "execute"), CascadeStage("s2", "wp-2", "validate")]
        cw = CascadingWingman("cascade-3", stages)
        cw.complete_stage("s1", {"approved": True})
        assert cw.is_complete() is False

    def test_cascade_complete_stage_idempotent(self):
        from src.murphy_wingman_evolution import CascadingWingman, CascadeStage
        stages = [CascadeStage("s1", "wp-1", "execute")]
        cw = CascadingWingman("cascade-4", stages)
        r1 = cw.complete_stage("s1", {"approved": True})
        r2 = cw.complete_stage("s1", {"approved": True})
        assert r1 is True and r2 is False


class TestWingmanEvolutionProduction:

    def test_record_validation_creates_metrics(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        we.record_validation("pair-1", True, validation_time_s=0.5)
        m = we.get_metrics("pair-1")
        assert m is not None
        assert m.total_validations == 1
        assert m.approved_count == 1

    def test_record_multiple_validations(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        for _ in range(5):
            we.record_validation("pair-2", True)
        for _ in range(3):
            we.record_validation("pair-2", False)
        m = we.get_metrics("pair-2")
        assert m.total_validations == 8

    def test_scorecard_computed_from_metrics(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        for _ in range(10):
            we.record_validation("pair-3", True)
        sc = we.get_scorecard("pair-3")
        assert sc is not None
        assert sc.f1 >= 0.0

    def test_evolve_produces_suggestions(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        for _ in range(10):
            we.record_validation("pair-4", False)
        history = [{"results": [{"rule_id": "rule_x", "passed": False}]} for _ in range(10)]
        suggestions = we.evolve("pair-4", history)
        assert len(suggestions) >= 1

    def test_factory_creates_pair_for_drawing(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        pair = we.factory().auto_create_pair("beam drawing", "drawing")
        assert pair["domain"] == "engineering"
        assert "check_credential_active" in pair["runbook_spec"]["rules"]

    def test_status_report(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()
        we.record_validation("pair-5", True)
        we.factory().auto_create_pair("subject", "action")
        status = we.get_status()
        assert status["total_pairs_tracked"] >= 1
        assert status["factory_pairs_created"] >= 1

    def test_concurrent_validation_recording(self):
        from src.murphy_wingman_evolution import WingmanEvolution
        we = WingmanEvolution()

        def record():
            for _ in range(10):
                we.record_validation("pair-concurrent", True)

        threads = [threading.Thread(target=record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        m = we.get_metrics("pair-concurrent")
        assert m.total_validations == 50
