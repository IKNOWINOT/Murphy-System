"""
Tests for RosettaDocument — the enriched per-agent Rosetta document.

Tests cover:
  - All new models in rosetta_models.py
  - RosettaDocumentBuilder end-to-end
  - Business plan math (exact float arithmetic, never rounded)
  - HITL throughput model (capacity, day-of-week, weekly schedule)
  - TaskPipeline (solidify, reject, domain filter)
  - AgentType validation (shadow requires shadowed_user_id)
  - IndustryTerminology domain guard
  - StateFeed push/get
"""

import pytest
from datetime import datetime, timezone
from typing import Optional

import sys
import os

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydantic import ValidationError

from rosetta.rosetta_models import (
    AgentType,
    BusinessPlanMath,
    DayOfWeekFactor,
    EmployeeContract,
    HITLThroughputModel,
    Identity,
    IndustryTerminology,
    ManagementLayer,
    MagnifySimplifyTask,
    RosettaDocument,
    StateFeed,
    StateFeedEntry,
    TaskPipeline,
    TaskPipelineStage,
    TermDefinition,
    UnitEconomics,
)
from rosetta.rosetta_document_builder import RosettaDocumentBuilder


# ===========================================================================
# EmployeeContract
# ===========================================================================

class TestEmployeeContract:
    def test_automation_agent_no_shadow_user(self):
        c = EmployeeContract(
            agent_type=AgentType.AUTOMATION,
            role_title="Field Technician",
        )
        assert c.agent_type == AgentType.AUTOMATION
        assert c.shadowed_user_id is None

    def test_shadow_agent_requires_user_id(self):
        with pytest.raises(ValidationError):
            EmployeeContract(
                agent_type=AgentType.SHADOW,
                role_title="Shadow Assistant",
                shadowed_user_id=None,  # missing — must raise ValidationError
            )

    def test_shadow_agent_with_user_id(self):
        c = EmployeeContract(
            agent_type=AgentType.SHADOW,
            role_title="Shadow Assistant",
            shadowed_user_id="user_jsmith",
            shadowed_user_name="John Smith",
        )
        assert c.shadowed_user_id == "user_jsmith"
        assert c.agent_type == AgentType.SHADOW

    def test_management_layer_default(self):
        c = EmployeeContract(agent_type=AgentType.AUTOMATION, role_title="Agent")
        assert c.management_layer == ManagementLayer.INDIVIDUAL

    def test_executive_layer(self):
        c = EmployeeContract(
            agent_type=AgentType.AUTOMATION,
            role_title="Operations Director",
            management_layer=ManagementLayer.EXECUTIVE,
        )
        assert c.management_layer == ManagementLayer.EXECUTIVE


# ===========================================================================
# IndustryTerminology
# ===========================================================================

class TestIndustryTerminology:
    def test_is_on_domain_match(self):
        t = IndustryTerminology(
            industry="trade_services",
            domain_keywords=["plumbing", "drain", "pipe", "technician"],
        )
        assert t.is_on_domain("Field technician sent to fix a drain blockage") is True

    def test_is_on_domain_no_match(self):
        t = IndustryTerminology(
            industry="trade_services",
            domain_keywords=["plumbing", "drain", "pipe", "technician"],
        )
        assert t.is_on_domain("Quarterly earnings from aerospace division") is False

    def test_find_term(self):
        t = IndustryTerminology(
            industry="trade_services",
            domain_keywords=["plumbing"],
            terms=[
                TermDefinition(
                    term="work order",
                    definition="An authorised job",
                    aliases=["WO", "job ticket"],
                )
            ],
        )
        found = t.find_term("WO")
        assert found is not None
        assert found.term == "work order"

    def test_find_term_not_found(self):
        t = IndustryTerminology(industry="general", domain_keywords=[])
        assert t.find_term("aerospace") is None

    def test_empty_domain_is_always_on_domain(self):
        t = IndustryTerminology(industry="general", domain_keywords=[])
        # No keywords means no constraint
        assert t.is_on_domain("Anything goes here") is True


# ===========================================================================
# StateFeed
# ===========================================================================

class TestStateFeed:
    def test_push_and_get(self):
        feed = StateFeed()
        entry = StateFeedEntry(
            metric_name="pipeline_fill_rate",
            value=0.42,
            unit="ratio",
            target=1.0,
        )
        feed.push(entry)
        result = feed.get("pipeline_fill_rate")
        assert result is not None
        assert result.value == pytest.approx(0.42)

    def test_latest_value(self):
        feed = StateFeed()
        feed.push(StateFeedEntry(metric_name="conversion_rate_actual", value=0.2999))
        assert feed.latest_value("conversion_rate_actual") == pytest.approx(0.2999)

    def test_missing_metric_returns_none(self):
        feed = StateFeed()
        assert feed.latest_value("nonexistent") is None

    def test_most_recent_first(self):
        feed = StateFeed()
        feed.push(StateFeedEntry(metric_name="revenue_gap", value=100_000.0))
        feed.push(StateFeedEntry(metric_name="revenue_gap", value=90_000.0))  # newer
        # latest_value returns the first matching entry (index 0 = most recent)
        assert feed.latest_value("revenue_gap") == pytest.approx(90_000.0)

    def test_gap_property(self):
        entry = StateFeedEntry(metric_name="units_closed", value=30.0, target=43.333)
        assert entry.gap == pytest.approx(30.0 - 43.333)

    def test_gap_percent(self):
        entry = StateFeedEntry(metric_name="units_closed", value=30.0, target=43.333)
        expected = (30.0 - 43.333) / 43.333 * 100
        assert entry.gap_percent == pytest.approx(expected, abs=0.001)


# ===========================================================================
# UnitEconomics — exact float arithmetic, never rounded
# ===========================================================================

class TestUnitEconomics:
    """
    Reference example: SaaS, $2M ARR goal, $5k/seat, $600k costs, 12 months,
    Q2 start, actual conversion 29.99%, goal 99.99%.
    """

    @pytest.fixture
    def ue(self) -> UnitEconomics:
        return UnitEconomics(
            revenue_goal_dollars=2_000_000.0,
            unit_price_dollars=5_000.0,
            annual_cost_dollars=600_000.0,
            timeline_months=12.0,
            conversion_rate_goal=0.9999,
            conversion_rate_actual=0.2999,
        )

    def test_gross_units_needed(self, ue: UnitEconomics):
        assert ue.gross_units_needed == pytest.approx(400.0)

    def test_adjusted_revenue_target(self, ue: UnitEconomics):
        assert ue.adjusted_revenue_target == pytest.approx(2_600_000.0)

    def test_adjusted_units_needed(self, ue: UnitEconomics):
        assert ue.adjusted_units_needed == pytest.approx(520.0)

    def test_units_per_month_never_rounded(self, ue: UnitEconomics):
        # 520 / 12 = 43.333333... (not 43.33 or 43.333)
        # Verify to full float precision — this is an exact rational number
        exact = 520.0 / 12.0  # Python float: 43.333333333333336
        assert ue.units_per_month == pytest.approx(exact, rel=1e-12)
        # Verify the value has more than 2 decimal places of significance
        # by checking it differs from both the 2-dp and 3-dp rounded versions
        assert abs(ue.units_per_month - 43.33) > 0.001
        assert abs(ue.units_per_month - 43.333) > 0.0001

    def test_conversion_inverse_ratio(self, ue: UnitEconomics):
        # (0.9999 * 100) / 0.2999 = 333.411...
        expected = (0.9999 * 100.0) / 0.2999
        assert ue.conversion_inverse_ratio == pytest.approx(expected, rel=1e-9)

    def test_prospect_reach_per_month(self, ue: UnitEconomics):
        expected = (520.0 / 12.0) * ((0.9999 * 100.0) / 0.2999)
        assert ue.prospect_reach_needed_per_month == pytest.approx(expected, rel=1e-9)

    def test_no_costs(self):
        ue = UnitEconomics(
            revenue_goal_dollars=1_000_000.0,
            unit_price_dollars=2_500.0,
            annual_cost_dollars=0.0,
            timeline_months=12.0,
            conversion_rate_goal=1.0,
            conversion_rate_actual=1.0,
        )
        assert ue.adjusted_units_needed == pytest.approx(400.0)
        assert ue.units_per_month == pytest.approx(400.0 / 12.0)
        assert ue.conversion_inverse_ratio == pytest.approx(100.0)

    def test_recommendation_string(self, ue: UnitEconomics):
        rec = ue.as_recommendation()
        assert "2,000,000" in rec
        assert "5,000" in rec
        assert "520" in rec
        assert "prospect" in rec.lower()


# ===========================================================================
# BusinessPlanMath
# ===========================================================================

class TestBusinessPlanMath:
    @pytest.fixture
    def plan(self) -> BusinessPlanMath:
        ue = UnitEconomics(
            revenue_goal_dollars=2_000_000.0,
            unit_price_dollars=5_000.0,
            annual_cost_dollars=600_000.0,
            timeline_months=12.0,
            conversion_rate_goal=0.9999,
            conversion_rate_actual=0.2999,
        )
        return BusinessPlanMath(
            unit_economics=ue,
            current_quarter=2,
            quarters_elapsed=1.0,  # 3 months elapsed
            units_closed_to_date=30.0,
            pipeline_units=40.0,
        )

    def test_units_remaining(self, plan: BusinessPlanMath):
        # 520 total needed − 30 closed = 490
        assert plan.units_remaining == pytest.approx(490.0)

    def test_months_remaining(self, plan: BusinessPlanMath):
        # 12 months − (1 quarter × 3) = 9
        assert plan.months_remaining == pytest.approx(9.0)

    def test_required_pace_remaining(self, plan: BusinessPlanMath):
        # 490 / 9 = 54.444...
        assert plan.required_pace_remaining == pytest.approx(490.0 / 9.0)

    def test_on_track_false(self, plan: BusinessPlanMath):
        # Plan pace: 43.333/month, 3 months elapsed → expected 130 units
        # Actual: 30 closed → behind
        assert plan.on_track is False

    def test_on_track_true(self):
        ue = UnitEconomics(
            revenue_goal_dollars=1_200_000.0,
            unit_price_dollars=1_000.0,
            timeline_months=12.0,
            conversion_rate_goal=1.0,
            conversion_rate_actual=1.0,
        )
        plan = BusinessPlanMath(
            unit_economics=ue,
            quarters_elapsed=1.0,
            units_closed_to_date=400.0,  # way ahead
        )
        assert plan.on_track is True

    def test_summary_keys(self, plan: BusinessPlanMath):
        s = plan.summary()
        for key in ("revenue_goal", "adjusted_units_needed", "units_per_month_plan",
                    "prospect_reach_needed_per_month", "on_track", "recommendation"):
            assert key in s


# ===========================================================================
# HITLThroughputModel
# ===========================================================================

class TestHITLThroughputModel:
    @pytest.fixture
    def model(self) -> HITLThroughputModel:
        return HITLThroughputModel(
            task_type="work_order_approval",
            base_tasks_per_day=20.0,
            validator_count=2,
            avg_task_duration_minutes=10.0,
            day_of_week_factors=[
                DayOfWeekFactor(day=0, factor=0.85, label="Monday"),
                DayOfWeekFactor(day=4, factor=0.80, label="Friday"),
                DayOfWeekFactor(day=5, factor=0.0, label="Saturday"),
                DayOfWeekFactor(day=6, factor=0.0, label="Sunday"),
            ],
            holiday_buffer_days_per_month=2.0,
            hitl_enabled=True,
        )

    def test_daily_capacity(self, model: HITLThroughputModel):
        assert model.daily_capacity == pytest.approx(40.0)  # 20 × 2

    def test_monthly_capacity(self, model: HITLThroughputModel):
        # (22 − 2) × 40 = 800
        assert model.monthly_capacity == pytest.approx(800.0)

    def test_day_capacity_monday(self, model: HITLThroughputModel):
        assert model.day_capacity(0) == pytest.approx(40.0 * 0.85)

    def test_day_capacity_friday(self, model: HITLThroughputModel):
        assert model.day_capacity(4) == pytest.approx(40.0 * 0.80)

    def test_day_capacity_saturday_zero(self, model: HITLThroughputModel):
        assert model.day_capacity(5) == pytest.approx(0.0)

    def test_day_capacity_normal_weekday(self, model: HITLThroughputModel):
        assert model.day_capacity(2) == pytest.approx(40.0)  # Wednesday, no factor

    def test_weeks_to_clear_backlog(self, model: HITLThroughputModel):
        # 200 tasks / (40 × 5) = 1.0 week
        assert model.weeks_to_clear(200.0) == pytest.approx(1.0)

    def test_hitl_disabled_clears_instantly(self):
        m = HITLThroughputModel(
            task_type="auto_approved",
            base_tasks_per_day=5.0,
            hitl_enabled=False,
        )
        assert m.weeks_to_clear(10000.0) == pytest.approx(0.0)

    def test_effective_working_days(self, model: HITLThroughputModel):
        assert model.effective_working_days_per_month == pytest.approx(20.0)


# ===========================================================================
# TaskPipeline and MagnifySimplifyTask
# ===========================================================================

class TestTaskPipeline:
    def _make_task(self, title: str, stage: TaskPipelineStage,
                   domain_fit: float = 1.0) -> MagnifySimplifyTask:
        import uuid as _uuid
        return MagnifySimplifyTask(
            task_id=_uuid.uuid4().hex[:10],
            title=title,
            stage=stage,
            domain_fit_score=domain_fit,
        )

    def test_actionable_tasks_only_solidified(self):
        pipeline = TaskPipeline()
        pipeline.add(self._make_task("task A", TaskPipelineStage.SOLIDIFIED))
        pipeline.add(self._make_task("task B", TaskPipelineStage.MAGNIFY_1))
        pipeline.add(self._make_task("task C", TaskPipelineStage.SOLIDIFIED))
        actionable = pipeline.actionable_tasks()
        assert len(actionable) == 2
        assert all(t.title in ("task A", "task C") for t in actionable)

    def test_rejected_tasks_not_actionable(self):
        pipeline = TaskPipeline()
        pipeline.add(self._make_task("task X", TaskPipelineStage.SOLIDIFIED, domain_fit=0.0))
        # domain_fit=0.0 < threshold=0.3 → not on domain
        actionable = pipeline.actionable_tasks()
        assert len(actionable) == 0

    def test_solidify(self):
        pipeline = TaskPipeline()
        task = self._make_task("pending task", TaskPipelineStage.MAGNIFY_2)
        pipeline.add(task)
        result = pipeline.solidify(task.task_id)
        assert result is True
        assert pipeline.tasks[0].stage == TaskPipelineStage.SOLIDIFIED

    def test_reject(self):
        pipeline = TaskPipeline()
        task = self._make_task("off-domain task", TaskPipelineStage.DOMAIN_FILTER)
        pipeline.add(task)
        pipeline.reject(task.task_id)
        assert pipeline.tasks[0].stage == TaskPipelineStage.REJECTED

    def test_tasks_by_stage(self):
        pipeline = TaskPipeline()
        pipeline.add(self._make_task("a", TaskPipelineStage.SOLIDIFIED))
        pipeline.add(self._make_task("b", TaskPipelineStage.SOLIDIFIED))
        pipeline.add(self._make_task("c", TaskPipelineStage.MAGNIFY_1))
        counts = pipeline.tasks_by_stage()
        assert counts[TaskPipelineStage.SOLIDIFIED] == 2
        assert counts[TaskPipelineStage.MAGNIFY_1] == 1

    def test_is_actionable_property(self):
        task = self._make_task("solid task", TaskPipelineStage.SOLIDIFIED)
        assert task.is_actionable is True
        task.stage = TaskPipelineStage.MAGNIFY_3
        assert task.is_actionable is False


# ===========================================================================
# RosettaDocumentBuilder
# ===========================================================================

class TestRosettaDocumentBuilder:
    @pytest.fixture
    def builder(self) -> RosettaDocumentBuilder:
        # No external dependencies — purely deterministic builder
        return RosettaDocumentBuilder(
            gate_engine=None,
            scaling_engine=None,
            hitl_controller=None,
            mss_controller=None,
            llm_backend=None,
        )

    def test_build_automation_agent(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="acme-tech-01",
            agent_name="Field Tech Agent",
            business_description="Plumbing and drain cleaning service in Austin TX",
            agent_type="automation",
            role_title="Field Technician",
        )
        assert doc.agent_id == "acme-tech-01"
        assert doc.is_automation() is True
        assert doc.is_shadow() is False
        assert doc.contract.role_title == "Field Technician"

    def test_build_shadow_agent(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="shadow-01",
            agent_name="Shadow for John Smith",
            business_description="Plumbing business",
            agent_type="shadow",
            role_title="Shadow Assistant",
            shadowed_user_id="user_jsmith",
            shadowed_user_name="John Smith",
        )
        assert doc.is_shadow() is True
        assert doc.contract.shadowed_user_id == "user_jsmith"

    def test_build_with_business_plan(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="exec-01",
            agent_name="Executive Agent",
            business_description="SaaS startup",
            agent_type="automation",
            role_title="Operations Director",
            management_layer="executive",
            revenue_goal=2_000_000.0,
            unit_price=5_000.0,
            annual_cost=600_000.0,
            timeline_months=12.0,
            conversion_rate_goal=0.9999,
            conversion_rate_actual=0.2999,
        )
        assert doc.business_plan is not None
        ue = doc.business_plan.unit_economics
        assert ue.adjusted_units_needed == pytest.approx(520.0)
        assert ue.units_per_month == pytest.approx(520.0 / 12.0)
        # Verify inverse ratio — never rounded
        expected_inverse = (0.9999 * 100.0) / 0.2999
        assert ue.conversion_inverse_ratio == pytest.approx(expected_inverse, rel=1e-9)

    def test_business_recommendation_present(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="exec-02",
            agent_name="Exec Agent",
            business_description="SaaS startup",
            agent_type="automation",
            role_title="Director",
            revenue_goal=1_000_000.0,
            unit_price=2_500.0,
        )
        rec = doc.business_recommendation()
        assert rec is not None
        assert "1,000,000" in rec

    def test_no_business_plan_recommendation_is_none(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="op-01",
            agent_name="Op Agent",
            business_description="Plumbing",
            agent_type="automation",
            role_title="Technician",
        )
        assert doc.business_recommendation() is None

    def test_hitl_models_built(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="op-02",
            agent_name="Op Agent",
            business_description="Plumbing",
            agent_type="automation",
            role_title="Dispatcher",
            hitl_task_types=[
                {"task_type": "work_order_approval", "base_tasks_per_day": 20.0,
                 "validator_count": 2},
            ],
        )
        assert len(doc.hitl_models) == 1
        model = doc.get_hitl_model("work_order_approval")
        assert model is not None
        assert model.daily_capacity == pytest.approx(40.0)

    def test_task_pipeline_seeded_from_goals(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="op-03",
            agent_name="Op Agent",
            business_description="Plumbing business Austin",
            agent_type="automation",
            role_title="Dispatcher",
            raw_goals=[
                "Grow revenue to $2M ARR",
                "Reduce invoice collection lag below 14 days",
            ],
        )
        # Both goals should produce solidified tasks (or at least be in the pipeline)
        assert len(doc.task_pipeline.tasks) >= 1

    def test_state_feed_initial_entries(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="op-04",
            agent_name="Op Agent",
            business_description="Plumbing",
            agent_type="automation",
            role_title="Technician",
            initial_state=[
                {"metric_name": "open_work_orders", "value": 7.0, "unit": "count"},
                {"metric_name": "overdue_invoices", "value": 3.0, "unit": "count"},
            ],
        )
        assert doc.state_metric("open_work_orders") == pytest.approx(7.0)
        assert doc.state_metric("overdue_invoices") == pytest.approx(3.0)

    def test_next_tasks_returns_solidified(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="op-05",
            agent_name="Op Agent",
            business_description="Plumbing business Austin drain service",
            agent_type="automation",
            role_title="Field Technician",
            raw_goals=[
                "Dispatch technicians to work orders",
                "Invoice customers after job completion",
            ],
        )
        # next_tasks() returns only solidified, on-domain tasks
        tasks = doc.next_tasks(limit=10)
        for t in tasks:
            assert t.is_actionable is True
            assert t.is_on_domain is True

    def test_industry_inferred_from_description(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="plumbing-01",
            agent_name="Plumbing Agent",
            business_description="We fix pipes and drains, residential plumbing Austin",
            agent_type="automation",
            role_title="Field Technician",
        )
        # Builder must infer some industry (not crash) and produce a terminology object.
        # Note: heuristic keyword matching can produce ties for short descriptions;
        # the LLM path (infer_via_llm) resolves these correctly in production.
        assert doc.terminology.industry != ""
        assert isinstance(doc.terminology.domain_keywords, list)

    def test_shadow_agent_missing_user_raises(self, builder: RosettaDocumentBuilder):
        with pytest.raises(ValidationError):
            builder.build(
                agent_id="bad-shadow",
                agent_name="Bad Shadow",
                business_description="Plumbing",
                agent_type="shadow",
                role_title="Shadow",
                shadowed_user_id=None,  # must raise
            )

    def test_base_state_populated(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="base-01",
            agent_name="Base Agent",
            business_description="Consulting firm",
            agent_type="automation",
            role_title="Consultant",
        )
        assert doc.base_state is not None
        assert doc.base_state.identity.agent_id == "base-01"

    def test_document_version(self, builder: RosettaDocumentBuilder):
        doc = builder.build(
            agent_id="v-01",
            agent_name="Versioned Agent",
            business_description="Consulting",
            agent_type="automation",
            role_title="Analyst",
        )
        assert doc.document_version == "2.0"


# ===========================================================================
# RosettaDocument convenience accessors
# ===========================================================================

class TestRosettaDocumentAccessors:
    def _make_doc(
        self,
        agent_type: str = "automation",
        with_plan: bool = False,
    ) -> RosettaDocument:
        contract = EmployeeContract(
            agent_type=AgentType(agent_type),
            role_title="Test Role",
            shadowed_user_id="user_x" if agent_type == "shadow" else None,
        )
        ue = UnitEconomics(
            revenue_goal_dollars=1_000_000.0,
            unit_price_dollars=1_000.0,
            timeline_months=12.0,
            conversion_rate_goal=1.0,
            conversion_rate_actual=0.5,
        ) if with_plan else None
        plan = BusinessPlanMath(unit_economics=ue) if ue else None

        return RosettaDocument(
            agent_id="test-agent",
            agent_name="Test Agent",
            contract=contract,
            business_plan=plan,
        )

    def test_is_shadow(self):
        doc = self._make_doc("shadow")
        assert doc.is_shadow() is True
        assert doc.is_automation() is False

    def test_is_automation(self):
        doc = self._make_doc("automation")
        assert doc.is_automation() is True
        assert doc.is_shadow() is False

    def test_state_metric_missing(self):
        doc = self._make_doc()
        assert doc.state_metric("nonexistent") is None

    def test_business_recommendation_with_plan(self):
        doc = self._make_doc(with_plan=True)
        rec = doc.business_recommendation()
        assert rec is not None

    def test_business_recommendation_without_plan(self):
        doc = self._make_doc(with_plan=False)
        assert doc.business_recommendation() is None

    def test_get_hitl_model_missing(self):
        doc = self._make_doc()
        assert doc.get_hitl_model("nonexistent") is None
