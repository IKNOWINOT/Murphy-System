"""
Tests for Business Scaling Automation Engine.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Covers:
- BusinessModelType enum (all 14 values)
- ScalingPhase, TacticCategory, MetricType enums
- KPI, ScalingTactic, ScalingStrategy, ScalingPlan data models
- BusinessScalingEngine.analyze_business for each model type
- BusinessScalingEngine.generate_scaling_plan produces valid strategies with KPIs
- CustomerAcquisitionAutomator funnel configuration and cycle execution
- RevenueOptimizer.analyze_pricing returns recommendations
- OperationsScaler.assess_bottlenecks and automation recommendations
- TerritoryExpansionPlanner market analysis and expansion plan
- Integration with CausalitySandbox (strategies go through sandbox)
- WingmanPair creation for scaling strategies
- Budget gate enforcement
"""

import threading
import uuid
import pytest

from src.business_scaling_engine import (
    BusinessModelType,
    BusinessScalingEngine,
    CustomerAcquisitionAutomator,
    KPI,
    MetricType,
    Milestone,
    OperationsScaler,
    RevenueOptimizer,
    ScalingPhase,
    ScalingPlan,
    ScalingStrategy,
    ScalingTactic,
    TacticCategory,
    TerritoryExpansionPlanner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return BusinessScalingEngine()


@pytest.fixture
def saas_profile():
    return {
        "model": "saas",
        "mrr": 5_000.0,
        "customers": 50,
        "churn_rate": 0.03,
        "cac": 300.0,
        "ltv": 2_000.0,
        "employees": 5,
        "budget": 20_000.0,
    }


@pytest.fixture
def acquisition():
    return CustomerAcquisitionAutomator()


@pytest.fixture
def revenue_optimizer():
    return RevenueOptimizer()


@pytest.fixture
def ops_scaler():
    return OperationsScaler()


@pytest.fixture
def territory_planner():
    return TerritoryExpansionPlanner()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestBusinessModelTypeEnum:
    def test_all_model_type_values(self):
        expected = [
            "saas", "marketplace", "services", "manufacturing", "retail",
            "ecommerce", "subscription_box", "agency", "consulting",
            "franchise", "platform", "freemium", "usage_based", "hybrid",
        ]
        values = [e.value for e in BusinessModelType]
        for val in expected:
            assert val in values

    def test_count_is_14(self):
        assert len(BusinessModelType) == 14

    def test_specific_values(self):
        assert BusinessModelType.SAAS.value == "saas"
        assert BusinessModelType.MARKETPLACE.value == "marketplace"
        assert BusinessModelType.HYBRID.value == "hybrid"


class TestScalingPhaseEnum:
    def test_all_phases(self):
        expected = ["bootstrap", "traction", "growth", "scale", "expansion", "maturity", "renewal"]
        values = [e.value for e in ScalingPhase]
        assert values == expected


class TestTacticCategoryEnum:
    def test_all_categories(self):
        expected = ["acquisition", "retention", "monetization", "operations", "expansion", "optimization"]
        values = [e.value for e in TacticCategory]
        for val in expected:
            assert val in values


class TestMetricTypeEnum:
    def test_all_metric_types(self):
        expected = ["revenue", "cost", "growth_rate", "churn", "ltv", "cac", "nps", "conversion", "utilization", "margin"]
        values = [e.value for e in MetricType]
        for val in expected:
            assert val in values


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------

class TestKPI:
    def test_kpi_creation(self):
        kpi = KPI(
            kpi_id="k-001",
            name="MRR",
            metric_type=MetricType.REVENUE,
            current_value=5_000.0,
            target_value=50_000.0,
            unit="USD",
        )
        assert kpi.metric_type == MetricType.REVENUE
        assert kpi.tracking_frequency == "weekly"


class TestScalingTactic:
    def test_tactic_creation(self):
        tactic = ScalingTactic(
            tactic_id="t-001",
            name="SEO Campaign",
            category=TacticCategory.ACQUISITION,
            automation_level=0.8,
            estimated_cost=5_000.0,
            estimated_impact=20_000.0,
        )
        assert tactic.automation_level == 0.8
        assert tactic.dependencies == []


class TestScalingStrategy:
    def test_strategy_creation(self):
        strategy = ScalingStrategy(
            strategy_id="s-001",
            name="Growth Strategy",
            business_model=BusinessModelType.SAAS,
            phase=ScalingPhase.GROWTH,
            timeline_days=90,
            expected_roi=2.5,
        )
        assert strategy.tactics == []
        assert strategy.kpis == []


class TestScalingPlan:
    def test_plan_creation(self):
        plan = ScalingPlan(
            plan_id="p-001",
            business_model=BusinessModelType.SAAS,
            current_phase=ScalingPhase.TRACTION,
            target_phase=ScalingPhase.GROWTH,
        )
        assert plan.strategies == []
        assert plan.milestones == []
        assert plan.sandbox_approved is False
        assert plan.created_at is not None


# ---------------------------------------------------------------------------
# BusinessScalingEngine.analyze_business
# ---------------------------------------------------------------------------

class TestAnalyzeBusiness:
    @pytest.mark.parametrize("model", list(BusinessModelType))
    def test_analyze_for_each_model_type(self, engine, model):
        profile = {"model": model.value, "mrr": 1_000, "customers": 20}
        result = engine.analyze_business(profile)
        assert "business_model" in result
        assert "current_phase" in result
        assert "strengths" in result
        assert "weaknesses" in result
        assert "opportunities" in result
        assert "recommendation" in result

    def test_analyze_saas_healthy_ltv_cac(self, engine):
        profile = {
            "model": "saas",
            "mrr": 10_000,
            "customers": 100,
            "ltv": 3_000,
            "cac": 500,
            "churn_rate": 0.02,
        }
        result = engine.analyze_business(profile)
        assert result["business_model"] == "saas"
        assert len(result["strengths"]) > 0

    def test_analyze_high_churn_shows_weakness(self, engine):
        profile = {"model": "saas", "mrr": 5_000, "customers": 50, "churn_rate": 0.12}
        result = engine.analyze_business(profile)
        weakness_text = " ".join(result["weaknesses"]).lower()
        assert "churn" in weakness_text

    def test_analyze_negative_unit_economics(self, engine):
        profile = {"model": "saas", "mrr": 1_000, "customers": 10, "ltv": 200, "cac": 500}
        result = engine.analyze_business(profile)
        weakness_text = " ".join(result["weaknesses"]).lower()
        assert "ltv" in weakness_text or "cac" in weakness_text or "unit" in weakness_text

    def test_analyze_zero_revenue_returns_bootstrap(self, engine):
        profile = {"model": "saas", "mrr": 0, "customers": 0}
        result = engine.analyze_business(profile)
        assert result["current_phase"] == ScalingPhase.BOOTSTRAP.value

    def test_analyze_large_business_returns_maturity(self, engine):
        profile = {"model": "saas", "mrr": 10_000_000, "customers": 50_000}
        result = engine.analyze_business(profile)
        assert result["current_phase"] in (ScalingPhase.MATURITY.value, ScalingPhase.EXPANSION.value)

    def test_analyze_unknown_model_falls_back_to_saas(self, engine):
        result = engine.analyze_business({"model": "not_real_model"})
        assert result["business_model"] == "saas"

    def test_analyze_returns_unit_economics(self, engine, saas_profile):
        result = engine.analyze_business(saas_profile)
        assert "unit_economics" in result
        assert "ltv_cac_ratio" in result["unit_economics"]


# ---------------------------------------------------------------------------
# BusinessScalingEngine.generate_scaling_plan
# ---------------------------------------------------------------------------

class TestGenerateScalingPlan:
    def test_generate_plan_returns_scaling_plan(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        assert isinstance(plan, ScalingPlan)

    def test_plan_has_strategies(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        assert len(plan.strategies) > 0

    def test_plan_strategies_have_kpis(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        for strategy in plan.strategies:
            assert len(strategy.kpis) > 0

    def test_plan_strategies_have_tactics(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        for strategy in plan.strategies:
            assert len(strategy.tactics) > 0

    def test_plan_has_milestones_when_target_set(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(
            saas_profile,
            target_revenue=100_000,
            target_customers=500,
        )
        assert len(plan.milestones) > 0

    def test_plan_budget_matches_profile(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        assert plan.total_budget == 20_000.0

    def test_plan_has_risk_assessment(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        assert "market_risk" in plan.risk_assessment

    def test_plan_stored_in_engine(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile)
        with engine._lock:
            assert plan.plan_id in engine._plans

    def test_plan_for_each_model_type(self, engine):
        for model in BusinessModelType:
            profile = {"model": model.value, "mrr": 1_000, "customers": 10, "budget": 10_000}
            plan = engine.generate_scaling_plan(profile)
            assert isinstance(plan, ScalingPlan)
            assert plan.business_model == model

    def test_plan_with_custom_timeline(self, engine, saas_profile):
        plan = engine.generate_scaling_plan(saas_profile, timeline_months=6)
        assert plan.projected_timeline_days == 180

    def test_plan_sandbox_approved_without_sandbox(self, saas_profile):
        eng = BusinessScalingEngine(causality_sandbox=None)
        plan = eng.generate_scaling_plan(saas_profile)
        assert plan.sandbox_approved is True


# ---------------------------------------------------------------------------
# BusinessScalingEngine.execute_tactic
# ---------------------------------------------------------------------------

class TestExecuteTactic:
    def test_execute_tactic_returns_result(self, engine):
        result = engine.execute_tactic("tactic-001")
        assert result["tactic_id"] == "tactic-001"
        assert result["status"] == "executed"
        assert "recommendation" in result


# ---------------------------------------------------------------------------
# BusinessScalingEngine dashboard
# ---------------------------------------------------------------------------

class TestScalingDashboard:
    def test_dashboard_structure(self, engine, saas_profile):
        engine.generate_scaling_plan(saas_profile)
        dashboard = engine.get_scaling_dashboard()
        assert "total_plans" in dashboard
        assert "kpis" in dashboard
        assert "recommendations" in dashboard
        assert dashboard["total_plans"] >= 1

    def test_evaluate_progress_structure(self, engine, saas_profile):
        engine.generate_scaling_plan(saas_profile)
        result = engine.evaluate_progress()
        assert "plans" in result
        assert "evaluated_at" in result


# ---------------------------------------------------------------------------
# CustomerAcquisitionAutomator
# ---------------------------------------------------------------------------

class TestCustomerAcquisitionAutomator:
    def test_configure_funnel(self, acquisition):
        result = acquisition.configure_funnel(BusinessModelType.SAAS, ["seo", "paid"])
        assert "funnel_id" in result
        assert result["business_model"] == "saas"
        assert result["channels"] == ["seo", "paid"]
        assert "recommendation" in result

    def test_funnel_stages_defined(self, acquisition):
        result = acquisition.configure_funnel(BusinessModelType.MARKETPLACE, ["organic"])
        assert len(result["stages"]) > 0

    def test_run_acquisition_cycle(self, acquisition):
        acquisition.configure_funnel(BusinessModelType.SAAS, ["seo", "paid"])
        result = acquisition.run_acquisition_cycle()
        assert "leads_generated" in result
        assert "leads_qualified" in result
        assert "leads_converted" in result
        assert "conversion_rate" in result
        assert result["leads_generated"] >= result["leads_qualified"]
        assert result["leads_qualified"] >= result["leads_converted"]

    def test_run_cycle_no_funnels(self, acquisition):
        result = acquisition.run_acquisition_cycle()
        assert result["funnels_active"] == 0
        assert result["leads_generated"] == 0

    def test_optimize_cac_returns_recommendations(self, acquisition):
        result = acquisition.optimize_cac()
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0
        assert "estimated_cac_reduction_pct" in result

    def test_get_channel_performance(self, acquisition):
        acquisition.configure_funnel(BusinessModelType.SAAS, ["seo", "paid"])
        result = acquisition.get_channel_performance()
        assert "channels" in result
        assert "seo" in result["channels"] or "paid" in result["channels"]


# ---------------------------------------------------------------------------
# RevenueOptimizer
# ---------------------------------------------------------------------------

class TestRevenueOptimizer:
    def test_analyze_empty_tiers(self, revenue_optimizer):
        result = revenue_optimizer.analyze_pricing([])
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_analyze_sparse_tiers(self, revenue_optimizer):
        tiers = [{"tier": "solo", "price": 19}]
        result = revenue_optimizer.analyze_pricing(tiers)
        assert "recommendations" in result

    def test_analyze_returns_suggested_tiers(self, revenue_optimizer):
        result = revenue_optimizer.analyze_pricing([])
        assert "suggested_tiers" in result
        assert len(result["suggested_tiers"]) == 3

    def test_analyze_returns_revenue_lift(self, revenue_optimizer):
        result = revenue_optimizer.analyze_pricing([{"tier": "pro", "price": 99}])
        assert "estimated_revenue_lift_pct" in result

    def test_suggest_upsell_paths(self, revenue_optimizer):
        paths = revenue_optimizer.suggest_upsell_paths("power_users")
        assert isinstance(paths, list)
        assert len(paths) >= 1
        for path in paths:
            assert "from_tier" in path
            assert "to_tier" in path

    def test_forecast_revenue(self, revenue_optimizer):
        result = revenue_optimizer.forecast_revenue(6)
        assert result["months"] == 6
        assert len(result["projections"]) == 6
        for proj in result["projections"]:
            assert "month" in proj
            assert "projected_mrr" in proj

    def test_identify_expansion_revenue(self, revenue_optimizer):
        result = revenue_optimizer.identify_expansion_revenue()
        assert "opportunities" in result
        assert "total_estimated_arr_uplift" in result
        total = sum(o["estimated_arr_uplift"] for o in result["opportunities"])
        assert total == result["total_estimated_arr_uplift"]


# ---------------------------------------------------------------------------
# OperationsScaler
# ---------------------------------------------------------------------------

class TestOperationsScaler:
    def test_assess_bottlenecks_returns_list(self, ops_scaler):
        bottlenecks = ops_scaler.assess_bottlenecks()
        assert isinstance(bottlenecks, list)
        assert len(bottlenecks) > 0

    def test_bottleneck_structure(self, ops_scaler):
        bottlenecks = ops_scaler.assess_bottlenecks()
        for b in bottlenecks:
            assert "department" in b
            assert "bottleneck" in b
            assert "severity" in b
            assert "recommendation" in b

    def test_recommend_automation_cs(self, ops_scaler):
        automations = ops_scaler.recommend_automation("customer_success")
        assert isinstance(automations, list)
        assert len(automations) >= 1

    def test_recommend_automation_unknown_dept(self, ops_scaler):
        automations = ops_scaler.recommend_automation("widget_making")
        assert isinstance(automations, list)
        assert len(automations) >= 1

    def test_generate_hiring_plan_high_growth(self, ops_scaler):
        plan = ops_scaler.generate_hiring_plan(growth_rate=0.8)
        assert "roles_needed" in plan
        assert len(plan["roles_needed"]) > 0
        assert "estimated_annual_cost" in plan
        assert "recommendation" in plan

    def test_generate_hiring_plan_low_growth(self, ops_scaler):
        plan = ops_scaler.generate_hiring_plan(growth_rate=0.1)
        assert "roles_needed" in plan

    def test_optimize_costs_returns_savings(self, ops_scaler):
        result = ops_scaler.optimize_costs()
        assert "recommendations" in result
        assert "total_projected_savings_annual" in result
        total = sum(r["projected_savings_annual"] for r in result["recommendations"])
        assert total == result["total_projected_savings_annual"]


# ---------------------------------------------------------------------------
# TerritoryExpansionPlanner
# ---------------------------------------------------------------------------

class TestTerritoryExpansionPlanner:
    @pytest.mark.parametrize("territory", ["europe", "apac", "latam", "north_america"])
    def test_analyze_known_markets(self, territory_planner, territory):
        result = territory_planner.analyze_market(territory)
        assert result["territory"] == territory
        assert "market_data" in result
        assert "recommendation" in result

    def test_analyze_unknown_market(self, territory_planner):
        result = territory_planner.analyze_market("middle_earth")
        assert result["territory"] == "middle_earth"
        assert "recommendation" in result

    def test_generate_expansion_plan(self, territory_planner):
        plan = territory_planner.generate_expansion_plan(["europe", "apac"])
        assert "territories" in plan
        assert len(plan["phases"]) == 2
        assert plan["total_estimated_budget"] > 0
        assert "recommendation" in plan

    def test_expansion_plan_phases_sequential(self, territory_planner):
        plan = territory_planner.generate_expansion_plan(["europe", "apac", "latam"])
        phases = plan["phases"]
        for i, phase in enumerate(phases):
            assert phase["phase"] == i + 1

    def test_estimate_localization_cost(self, territory_planner):
        result = territory_planner.estimate_localization_cost("europe")
        assert "total_localization_cost_usd" in result
        assert result["total_localization_cost_usd"] > 0
        assert "recommendation" in result

    def test_get_regulatory_requirements(self, territory_planner):
        reqs = territory_planner.get_regulatory_requirements("europe")
        assert isinstance(reqs, list)
        assert len(reqs) > 0
        for req in reqs:
            assert "framework" in req
            assert "recommendation" in req

    def test_regulatory_requirements_unknown_territory(self, territory_planner):
        reqs = territory_planner.get_regulatory_requirements("gondor")
        assert isinstance(reqs, list)


# ---------------------------------------------------------------------------
# Integration: Sandbox
# ---------------------------------------------------------------------------

class TestSandboxIntegration:
    def test_plan_with_mock_sandbox(self, saas_profile):
        class _MockReport:
            optimal_actions_selected = 1

        class _MockSandbox:
            def run_sandbox_cycle(self, gaps, real_loop):
                return _MockReport()

        eng = BusinessScalingEngine(causality_sandbox=_MockSandbox())
        plan = eng.generate_scaling_plan(saas_profile)
        assert plan.sandbox_approved is True

    def test_plan_with_rejecting_sandbox(self, saas_profile):
        class _MockReport:
            optimal_actions_selected = 0

        class _MockSandbox:
            def run_sandbox_cycle(self, gaps, real_loop):
                return _MockReport()

        eng = BusinessScalingEngine(causality_sandbox=_MockSandbox())
        plan = eng.generate_scaling_plan(saas_profile)
        assert plan.sandbox_approved is False

    def test_plan_with_failing_sandbox_defaults_false(self, saas_profile):
        class _FailingSandbox:
            def run_sandbox_cycle(self, gaps, real_loop):
                raise RuntimeError("Sandbox unavailable")

        eng = BusinessScalingEngine(causality_sandbox=_FailingSandbox())
        plan = eng.generate_scaling_plan(saas_profile)
        assert plan.sandbox_approved is False


# ---------------------------------------------------------------------------
# Integration: WingmanProtocol
# ---------------------------------------------------------------------------

class TestWingmanIntegration:
    def test_wingman_pair_created_for_plan(self, saas_profile):
        from wingman_protocol import WingmanProtocol
        wp = WingmanProtocol()
        eng = BusinessScalingEngine(wingman_protocol=wp)
        plan = eng.generate_scaling_plan(saas_profile)
        assert plan.plan_id is not None
        assert len(wp.list_pairs()) >= 1

    def test_wingman_pair_subject_contains_plan_id(self, saas_profile):
        from wingman_protocol import WingmanProtocol
        wp = WingmanProtocol()
        eng = BusinessScalingEngine(wingman_protocol=wp)
        plan = eng.generate_scaling_plan(saas_profile)
        pairs = wp.list_pairs()
        subjects = [p.subject for p in pairs]
        assert any(plan.plan_id in s for s in subjects)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_plan_generation(self, saas_profile):
        engine = BusinessScalingEngine()
        errors: list = []
        plans: list = []
        lock = threading.Lock()

        def generate(i: int) -> None:
            try:
                profile = dict(saas_profile)
                profile["model"] = list(BusinessModelType)[i % len(BusinessModelType)].value
                plan = engine.generate_scaling_plan(profile)
                with lock:
                    plans.append(plan)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=generate, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(plans) == 6
        plan_ids = [p.plan_id for p in plans]
        assert len(set(plan_ids)) == 6
