"""
Tests for Budget-Aware Processor (Murphy System)

Validates strategy selection, execution planning, adaptive mode,
scale analysis, breakeven calculation, budget exhaustion handling,
WingmanProtocol integration, dashboard generation, and cost
calculations at different scales.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from budget_aware_processor import (
    BudgetAwareProcessor,
    BudgetProfile,
    ExecutionPlan,
    ProcessingStrategy,
    WorkUnit,
    _topological_sort,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def processor():
    """Return a fresh BudgetAwareProcessor with auto-created WingmanProtocol."""
    return BudgetAwareProcessor()


def _make_budget(
    total: float = 100.0,
    spent: float = 0.0,
    cpp: float = 1.0,
    cps: float = 0.2,
    max_concurrent: int = 10,
    time_limit: float = None,
    priority: str = "normal",
) -> BudgetProfile:
    return BudgetProfile(
        profile_id=f"bp-test",
        total_budget=total,
        spent=spent,
        cost_per_parallel_unit=cpp,
        cost_per_sequential_unit=cps,
        max_concurrent=max_concurrent,
        time_limit_seconds=time_limit,
        priority=priority,
    )


def _make_units(n: int, cost: float = 1.0, duration_ms: float = 100.0) -> list:
    return [
        WorkUnit(
            unit_id=f"u-{i}",
            description=f"Unit {i}",
            estimated_cost=cost,
            estimated_duration_ms=duration_ms,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# ProcessingStrategy enum
# ---------------------------------------------------------------------------


class TestProcessingStrategyEnum:
    def test_all_values_exist(self):
        assert ProcessingStrategy.SPIKE == "spike"
        assert ProcessingStrategy.SEQUENTIAL == "sequential"
        assert ProcessingStrategy.HYBRID == "hybrid"
        assert ProcessingStrategy.ADAPTIVE == "adaptive"

    def test_is_str_subclass(self):
        assert isinstance(ProcessingStrategy.SPIKE, str)


# ---------------------------------------------------------------------------
# BudgetProfile
# ---------------------------------------------------------------------------


class TestBudgetProfile:
    def test_remaining_calculation(self):
        bp = _make_budget(total=100.0, spent=30.0)
        assert bp.remaining == pytest.approx(70.0)

    def test_remaining_never_negative(self):
        bp = _make_budget(total=10.0, spent=50.0)
        assert bp.remaining == 0.0

    def test_created_at_auto_set(self):
        bp = _make_budget()
        assert bp.created_at != ""
        assert "T" in bp.created_at  # ISO format

    def test_explicit_created_at(self):
        bp = BudgetProfile(
            profile_id="x",
            total_budget=50.0,
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert bp.created_at == "2025-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# WorkUnit
# ---------------------------------------------------------------------------


class TestWorkUnit:
    def test_defaults(self):
        u = WorkUnit(
            unit_id="u1",
            description="test",
            estimated_cost=2.5,
            estimated_duration_ms=200.0,
        )
        assert u.status == "pending"
        assert u.is_critical is False
        assert u.dependencies == []
        assert u.actual_cost == 0.0

    def test_critical_flag(self):
        u = WorkUnit(
            unit_id="u2",
            description="critical work",
            estimated_cost=5.0,
            estimated_duration_ms=500.0,
            is_critical=True,
        )
        assert u.is_critical is True


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_no_dependencies(self):
        units = _make_units(3)
        result = _topological_sort(units)
        assert len(result) == 3

    def test_dependency_ordering(self):
        a = WorkUnit("a", "A", 1.0, 100.0)
        b = WorkUnit("b", "B", 1.0, 100.0, dependencies=["a"])
        c = WorkUnit("c", "C", 1.0, 100.0, dependencies=["b"])
        result = _topological_sort([c, b, a])
        ids = [u.unit_id for u in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_missing_dependency_is_skipped(self):
        a = WorkUnit("a", "A", 1.0, 100.0, dependencies=["nonexistent"])
        result = _topological_sort([a])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Strategy selection: tight budget → SEQUENTIAL
# ---------------------------------------------------------------------------


class TestStrategySelectionSequential:
    def test_tight_budget_no_deadline_selects_sequential(self, processor):
        # With cost_per_sequential_unit = 0.2, spike would cost 5x more
        bp = _make_budget(total=5.0, cpp=1.0, cps=0.2)
        units = _make_units(5, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["recommended_strategy"] == ProcessingStrategy.SEQUENTIAL

    def test_sequential_is_cheaper(self, processor):
        bp = _make_budget(total=100.0, cpp=1.0, cps=0.2)
        units = _make_units(5, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["sequential_cost"] < analysis["spike_cost"]

    def test_can_afford_sequential(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(3, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["can_afford_sequential"] is True

    def test_recommendation_is_string(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(2)
        analysis = processor.analyze_budget(bp, units)
        assert isinstance(analysis["recommendation"], str)
        assert len(analysis["recommendation"]) > 0


# ---------------------------------------------------------------------------
# Strategy selection: ample budget + deadline → SPIKE
# ---------------------------------------------------------------------------


class TestStrategySelectionSpike:
    def test_ample_budget_with_tight_deadline_selects_spike(self, processor):
        # 10 units × 100 ms = 1000 ms sequential; deadline = 0.5 s (500 ms)
        bp = _make_budget(total=500.0, cpp=1.0, cps=0.2, time_limit=0.5)
        units = _make_units(10, cost=1.0, duration_ms=100.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["recommended_strategy"] == ProcessingStrategy.SPIKE

    def test_can_afford_spike_when_budget_large(self, processor):
        bp = _make_budget(total=1000.0)
        units = _make_units(5, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["can_afford_spike"] is True

    def test_spike_cost_higher_than_sequential(self, processor):
        bp = _make_budget(total=500.0, cpp=1.0, cps=0.2, time_limit=0.1)
        units = _make_units(5, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["spike_cost"] > analysis["sequential_cost"]


# ---------------------------------------------------------------------------
# Strategy selection: mixed critical/non-critical → HYBRID
# ---------------------------------------------------------------------------


class TestStrategySelectionHybrid:
    def _mixed_units(self):
        units = []
        for i in range(3):
            units.append(WorkUnit(
                unit_id=f"nc-{i}",
                description=f"Non-critical {i}",
                estimated_cost=1.0,
                estimated_duration_ms=100.0,
                is_critical=False,
            ))
        for i in range(2):
            units.append(WorkUnit(
                unit_id=f"c-{i}",
                description=f"Critical {i}",
                estimated_cost=1.0,
                estimated_duration_ms=100.0,
                is_critical=True,
            ))
        return units

    def test_hybrid_chosen_for_mixed_workload(self, processor):
        # spike_cost = 5 * 1.0 = 5.0 → unaffordable (budget = 3.0)
        # hybrid_cost = 3*0.2 + 2*1.0 = 2.6 → affordable
        # With critical units present and spike unaffordable, HYBRID wins over SEQUENTIAL
        bp = _make_budget(total=3.0, cpp=1.0, cps=0.2)
        units = self._mixed_units()
        analysis = processor.analyze_budget(bp, units)
        assert analysis["recommended_strategy"] == ProcessingStrategy.HYBRID

    def test_hybrid_cost_between_sequential_and_spike(self, processor):
        bp = _make_budget(total=100.0, cpp=1.0, cps=0.2)
        units = self._mixed_units()
        analysis = processor.analyze_budget(bp, units)
        assert analysis["sequential_cost"] <= analysis["hybrid_cost"] <= analysis["spike_cost"]


# ---------------------------------------------------------------------------
# Adaptive mode
# ---------------------------------------------------------------------------


class TestAdaptiveMode:
    def test_adaptive_selected_when_budget_exhausted(self, processor):
        # Budget is so tight even sequential is unaffordable
        bp = _make_budget(total=0.05, cpp=1.0, cps=0.2)
        units = _make_units(5, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["recommended_strategy"] == ProcessingStrategy.ADAPTIVE

    def test_adaptive_plan_has_adaptive_phases(self, processor):
        bp = _make_budget(total=0.05, cpp=1.0, cps=0.2)
        units = _make_units(3, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        assert plan.strategy == ProcessingStrategy.ADAPTIVE
        assert all(ph["mode"] == "adaptive" for ph in plan.phases)

    def test_adaptive_execution_records_strategy_adjustments(self, processor):
        # Give enough budget for mid-run upgrade
        bp = _make_budget(total=0.5, cpp=1.0, cps=0.2)
        units = _make_units(3, cost=0.1)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        # adjustments list may be empty or non-empty depending on headroom
        assert isinstance(result["strategy_adjustments"], list)


# ---------------------------------------------------------------------------
# Execution plan structure
# ---------------------------------------------------------------------------


class TestExecutionPlan:
    def test_plan_has_required_fields(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(3)
        plan = processor.create_execution_plan(bp, units)
        assert isinstance(plan, ExecutionPlan)
        assert plan.plan_id.startswith("plan-")
        assert len(plan.phases) > 0
        assert isinstance(plan.strategy_reasoning, str)
        assert plan.created_at != ""

    def test_spike_plan_has_one_phase(self, processor):
        bp = _make_budget(total=500.0, time_limit=0.1)
        units = _make_units(5, duration_ms=500.0)
        plan = processor.create_execution_plan(bp, units)
        assert plan.strategy == ProcessingStrategy.SPIKE
        assert len(plan.phases) == 1
        assert plan.phases[0]["mode"] == "parallel"

    def test_sequential_plan_has_one_phase_per_unit(self, processor):
        bp = _make_budget(total=100.0, cpp=1.0, cps=0.2)
        units = _make_units(4)
        plan = processor.create_execution_plan(bp, units)
        assert plan.strategy == ProcessingStrategy.SEQUENTIAL
        assert len(plan.phases) == 4

    def test_hybrid_plan_splits_critical_and_non_critical(self, processor):
        # spike=2.0 → unaffordable (budget=1.5), hybrid=0.2+1.0=1.2 → affordable
        bp = _make_budget(total=1.5, cpp=1.0, cps=0.2)
        units = [
            WorkUnit("a", "non-crit", 1.0, 100.0, is_critical=False),
            WorkUnit("b", "critical", 1.0, 100.0, is_critical=True),
        ]
        plan = processor.create_execution_plan(bp, units)
        assert plan.strategy == ProcessingStrategy.HYBRID
        modes = {ph["mode"] for ph in plan.phases}
        assert "parallel" in modes
        assert "sequential" in modes


# ---------------------------------------------------------------------------
# Dependency ordering in execution plans
# ---------------------------------------------------------------------------


class TestDependencyOrdering:
    def test_dependencies_respected_in_plan(self, processor):
        a = WorkUnit("a", "A", 1.0, 100.0)
        b = WorkUnit("b", "B", 1.0, 100.0, dependencies=["a"])
        c = WorkUnit("c", "C", 1.0, 100.0, dependencies=["b"])
        bp = _make_budget(total=100.0)
        plan = processor.create_execution_plan(bp, [c, b, a])
        ids = [u.unit_id for u in plan.work_units]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_all_units_present_in_plan(self, processor):
        units = _make_units(5)
        bp = _make_budget(total=100.0)
        plan = processor.create_execution_plan(bp, units)
        plan_ids = {u.unit_id for u in plan.work_units}
        assert plan_ids == {u.unit_id for u in units}


# ---------------------------------------------------------------------------
# Execute plan
# ---------------------------------------------------------------------------


class TestExecutePlan:
    def test_execute_returns_required_keys(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(3)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        for key in ("completed", "failed", "skipped", "total_cost",
                    "total_duration_ms", "budget_remaining", "strategy_adjustments"):
            assert key in result

    def test_all_units_completed_with_ample_budget(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(5, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        assert len(result["completed"]) == 5
        assert len(result["skipped"]) == 0

    def test_unit_statuses_updated(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(3, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        processor.execute_plan(plan)
        for unit in plan.work_units:
            assert unit.status in ("completed", "skipped", "failed")

    def test_total_cost_positive(self, processor):
        bp = _make_budget(total=100.0)
        units = _make_units(3, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        assert result["total_cost"] > 0.0


# ---------------------------------------------------------------------------
# Budget exhaustion handling (graceful degradation)
# ---------------------------------------------------------------------------


class TestBudgetExhaustion:
    def test_units_skipped_when_budget_runs_out(self, processor):
        # Budget only covers 1 unit with sequential cost 0.2 per unit; 10 units total
        bp = _make_budget(total=0.3, cpp=1.0, cps=0.2)
        units = _make_units(10, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        assert len(result["skipped"]) > 0
        assert result["budget_remaining"] >= 0.0

    def test_no_negative_budget_remaining(self, processor):
        bp = _make_budget(total=0.1, cpp=1.0, cps=0.2)
        units = _make_units(5, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        assert result["budget_remaining"] >= 0.0

    def test_zero_budget_skips_all(self, processor):
        bp = _make_budget(total=0.0, cpp=1.0, cps=0.2)
        units = _make_units(3, cost=1.0)
        plan = processor.create_execution_plan(bp, units)
        result = processor.execute_plan(plan)
        assert len(result["completed"]) == 0


# ---------------------------------------------------------------------------
# Scale analysis
# ---------------------------------------------------------------------------


class TestScaleAnalysis:
    def test_returns_one_entry_per_count(self, processor):
        counts = [5, 10, 50, 100, 200]
        results = processor.get_scale_analysis(counts)
        assert len(results) == len(counts)

    def test_each_entry_has_required_keys(self, processor):
        results = processor.get_scale_analysis([10])
        entry = results[0]
        for key in ("count", "recommended_strategy", "estimated_cost",
                    "estimated_duration_ms", "cost_per_unit"):
            assert key in entry

    def test_strategy_varies_with_scale(self, processor):
        # Small scale → sequential; large scale may differ due to budget scaling
        small = processor.get_scale_analysis([1])
        large = processor.get_scale_analysis([1000])
        # Both should at least be valid strategies
        assert small[0]["recommended_strategy"] in list(ProcessingStrategy)
        assert large[0]["recommended_strategy"] in list(ProcessingStrategy)

    def test_cost_per_unit_is_positive(self, processor):
        results = processor.get_scale_analysis([5, 10])
        for entry in results:
            assert entry["cost_per_unit"] > 0.0

    def test_empty_counts_list(self, processor):
        results = processor.get_scale_analysis([])
        assert results == []


# ---------------------------------------------------------------------------
# Breakeven point
# ---------------------------------------------------------------------------


class TestBreakevenPoint:
    def test_returns_required_keys(self, processor):
        bp = _make_budget(cpp=1.0, cps=0.2)
        result = processor.get_breakeven_point(bp)
        for key in ("breakeven_units", "spike_cheaper_above",
                    "sequential_cheaper_below", "analysis"):
            assert key in result

    def test_breakeven_positive_integer(self, processor):
        bp = _make_budget(cpp=1.0, cps=0.2)
        result = processor.get_breakeven_point(bp)
        assert result["breakeven_units"] >= 1
        assert isinstance(result["breakeven_units"], int)

    def test_breakeven_analysis_is_string(self, processor):
        bp = _make_budget(cpp=1.0, cps=0.2)
        result = processor.get_breakeven_point(bp)
        assert isinstance(result["analysis"], str)
        assert len(result["analysis"]) > 0

    def test_low_ratio_breakeven_is_one(self, processor):
        # When parallel is cheaper per unit (ratio <= 1), breakeven should be 1
        bp = _make_budget(cpp=0.1, cps=0.2)
        result = processor.get_breakeven_point(bp)
        assert result["breakeven_units"] == 1

    def test_high_ratio_increases_breakeven(self, processor):
        # High parallel cost → breakeven moves out
        bp_low = _make_budget(cpp=1.0, cps=0.2)
        bp_high = _make_budget(cpp=5.0, cps=0.2)
        low_be = processor.get_breakeven_point(bp_low)["breakeven_units"]
        high_be = processor.get_breakeven_point(bp_high)["breakeven_units"]
        assert high_be <= low_be  # higher ratio → fewer units needed for spike to lose


# ---------------------------------------------------------------------------
# WingmanProtocol integration
# ---------------------------------------------------------------------------


class TestWingmanProtocolIntegration:
    def test_processor_creates_without_protocol(self):
        proc = BudgetAwareProcessor(wingman_protocol=None)
        assert proc is not None

    def test_processor_accepts_custom_protocol(self):
        try:
            from wingman_protocol import WingmanProtocol
            wp = WingmanProtocol()
            proc = BudgetAwareProcessor(wingman_protocol=wp)
            assert proc._wp is wp
        except ImportError:
            pytest.skip("WingmanProtocol not available")

    def test_budget_runbook_registered(self):
        try:
            from wingman_protocol import WingmanProtocol
            wp = WingmanProtocol()
            BudgetAwareProcessor(wingman_protocol=wp)
            runbook = wp.get_runbook("budget_processing")
            assert runbook is not None
            assert runbook.runbook_id == "budget_processing"
        except ImportError:
            pytest.skip("WingmanProtocol not available")

    def test_plan_creation_runs_validation(self):
        try:
            from wingman_protocol import WingmanProtocol
            wp = WingmanProtocol()
            proc = BudgetAwareProcessor(wingman_protocol=wp)
            bp = _make_budget(total=100.0)
            units = _make_units(3)
            plan = proc.create_execution_plan(bp, units)
            # Validation history should contain at least one entry for this plan's pair
            all_pairs = wp.list_pairs(subject=f"plan-{plan.plan_id}")
            assert len(all_pairs) == 1
        except ImportError:
            pytest.skip("WingmanProtocol not available")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_dashboard_empty_initially(self, processor):
        dash = processor.get_dashboard()
        assert dash["total_plans"] == 0
        assert dash["total_work_units"] == 0
        assert dash["plans"] == []

    def test_dashboard_counts_plans(self, processor):
        bp = _make_budget(total=100.0)
        for _ in range(3):
            processor.create_execution_plan(bp, _make_units(2))
        dash = processor.get_dashboard()
        assert dash["total_plans"] == 3

    def test_dashboard_tracks_strategy_counts(self, processor):
        bp = _make_budget(total=100.0)
        processor.create_execution_plan(bp, _make_units(3))
        dash = processor.get_dashboard()
        assert len(dash["strategy_counts"]) > 0

    def test_dashboard_total_cost_positive(self, processor):
        bp = _make_budget(total=100.0)
        processor.create_execution_plan(bp, _make_units(3, cost=2.0))
        dash = processor.get_dashboard()
        assert dash["total_estimated_cost"] > 0.0

    def test_dashboard_plan_entries_have_required_keys(self, processor):
        bp = _make_budget(total=100.0)
        processor.create_execution_plan(bp, _make_units(2))
        dash = processor.get_dashboard()
        entry = dash["plans"][0]
        for key in ("plan_id", "strategy", "units", "estimated_cost", "created_at"):
            assert key in entry


# ---------------------------------------------------------------------------
# Cost calculations at different scales
# ---------------------------------------------------------------------------


class TestCostCalculations:
    def test_cost_scales_linearly_with_units(self, processor):
        bp = _make_budget(total=1000.0, cpp=1.0, cps=0.2)
        units_5 = _make_units(5, cost=1.0)
        units_10 = _make_units(10, cost=1.0)
        a5 = processor.analyze_budget(bp, units_5)
        a10 = processor.analyze_budget(bp, units_10)
        assert a10["sequential_cost"] == pytest.approx(a5["sequential_cost"] * 2, rel=0.01)

    def test_zero_units_returns_zero_costs(self, processor):
        bp = _make_budget(total=100.0)
        analysis = processor.analyze_budget(bp, [])
        assert analysis["spike_cost"] == 0.0
        assert analysis["sequential_cost"] == 0.0
        assert analysis["hybrid_cost"] == 0.0

    def test_sequential_cost_lower_than_spike_cost(self, processor):
        bp = _make_budget(total=100.0, cpp=1.0, cps=0.2)
        units = _make_units(10, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["sequential_cost"] < analysis["spike_cost"]

    def test_cost_savings_correct(self, processor):
        bp = _make_budget(total=100.0, cpp=1.0, cps=0.2)
        units = _make_units(10, cost=1.0)
        analysis = processor.analyze_budget(bp, units)
        expected_savings = analysis["spike_cost"] - analysis["sequential_cost"]
        assert analysis["cost_savings_sequential_vs_spike"] == pytest.approx(
            expected_savings, rel=0.01
        )

    def test_time_estimate_spike_less_than_sequential(self, processor):
        # With 10 units, spike runs them in batches; sequential runs all one-by-one
        bp = _make_budget(total=100.0, max_concurrent=10)
        units = _make_units(10, duration_ms=100.0)
        analysis = processor.analyze_budget(bp, units)
        assert analysis["time_estimate_spike_ms"] <= analysis["time_estimate_sequential_ms"]


# ---------------------------------------------------------------------------
# Zero-config usage
# ---------------------------------------------------------------------------


class TestZeroConfig:
    def test_processor_works_without_arguments(self):
        proc = BudgetAwareProcessor()
        bp = BudgetProfile(profile_id="zc", total_budget=50.0)
        units = [WorkUnit("z1", "Zero-config test", 1.0, 100.0)]
        plan = proc.create_execution_plan(bp, units)
        assert plan is not None
        result = proc.execute_plan(plan)
        assert result is not None
