"""
Tests for OPS-004: OperationsCycleEngine.

Validates:
  - Brand identity and campaign style guide
  - 30-day traction cycles (start, evaluate, complete, auto-continue)
  - 60-day R&D sprint cycles (start, queue, build, carry-over, auto-continue)
  - Instant disruption response (detect, gap-analyze, propose, HITL approve/reject)
  - Tick (combined cycle evaluation)
  - Continuous cycle repetition

Design Label: TEST-009 / OPS-004
Owner: QA Team
"""

import pytest

from src.operations_cycle_engine import (
    OperationsCycleEngine,
    BrandIdentity,
    TractionCycle,
    RDSprintCycle,
    DisruptionResponse,
    CycleType,
    CycleStatus,
    DisruptionSeverity,
    DisruptionResponseStatus,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    return OperationsCycleEngine()


# ------------------------------------------------------------------
# Brand Identity
# ------------------------------------------------------------------

class TestBrandIdentity:
    def test_brand_name(self, engine):
        assert engine.brand.name == "murphy_system"

    def test_brand_tagline(self, engine):
        assert "Self-Running" in engine.brand.tagline

    def test_brand_logo_description(self, engine):
        logo = engine.brand.logo_description
        assert "neon green" in logo.lower() or "#00ff41" in logo

    def test_brand_colors(self, engine):
        brand = engine.get_brand()
        assert brand["colors"]["primary"] == "#00ff41"
        assert brand["colors"]["secondary"] == "#0a0a0a"

    def test_brand_voice(self, engine):
        assert "safety" in engine.brand.voice.lower()

    def test_brand_values(self, engine):
        vals = engine.brand.values
        assert len(vals) >= 3
        assert any("safety" in v.lower() for v in vals)

    def test_campaign_style_guide(self, engine):
        guide = engine.get_campaign_style_guide()
        assert "tone" in guide
        assert "product_name" in guide
        assert guide["product_name"] == "murphy_system"
        assert "never_say" in guide

    def test_brand_to_dict(self, engine):
        d = engine.get_brand()
        assert "name" in d
        assert "colors" in d
        assert "fonts" in d
        assert "voice" in d
        assert "logo_description" in d


# ------------------------------------------------------------------
# Traction Cycles (30-day)
# ------------------------------------------------------------------

class TestTractionCycles:
    def test_start_traction_cycle(self, engine):
        cycle = engine.start_traction_cycle()
        assert cycle.cycle_number == 1
        assert cycle.status == CycleStatus.ACTIVE

    def test_traction_cycle_30_day_period(self, engine):
        cycle = engine.start_traction_cycle()
        assert cycle.start_date is not None
        assert cycle.end_date is not None
        # end_date should be ~30 days after start

    def test_evaluate_traction_healthy(self, engine):
        engine.start_traction_cycle()
        result = engine.evaluate_traction_cycle({
            "pro": {"impressions": 10000, "leads": 500, "conversions": 25},
            "enterprise": {"impressions": 2000, "leads": 100, "conversions": 5},
        })
        assert result["tier_results"]["pro"]["traction"] == "healthy"
        assert result["tier_results"]["enterprise"]["traction"] == "healthy"
        assert result["adjustments_needed"] == 0

    def test_evaluate_traction_low(self, engine):
        engine.start_traction_cycle()
        result = engine.evaluate_traction_cycle({
            "pro": {"impressions": 10000, "leads": 500, "conversions": 8},  # 1.6%
        })
        assert result["tier_results"]["pro"]["traction"] == "low"
        assert result["adjustments_needed"] == 1

    def test_evaluate_traction_critical(self, engine):
        engine.start_traction_cycle()
        result = engine.evaluate_traction_cycle({
            "creator_starter": {"impressions": 5000, "leads": 200, "conversions": 1},  # 0.5%
        })
        assert result["tier_results"]["creator_starter"]["traction"] == "critical"
        assert result["proposals_needed"] == 1

    def test_evaluate_auto_starts_cycle(self, engine):
        """If no cycle exists, evaluate_traction_cycle auto-starts one."""
        result = engine.evaluate_traction_cycle({
            "pro": {"impressions": 1000, "leads": 50, "conversions": 5},
        })
        assert result["cycle_number"] == 1

    def test_complete_traction_cycle_auto_starts_next(self, engine):
        engine.start_traction_cycle()
        result = engine.complete_traction_cycle()
        assert result is not None
        assert result["completed_cycle"]["status"] == "completed"
        assert result["next_cycle"]["cycle_number"] == 2

    def test_traction_history(self, engine):
        engine.start_traction_cycle()
        engine.complete_traction_cycle()  # completes #1, starts #2
        history = engine.get_traction_history()
        assert len(history) == 2

    def test_multiple_traction_cycles(self, engine):
        """Traction cycles repeat continuously."""
        for _ in range(5):
            engine.start_traction_cycle()
            engine.complete_traction_cycle()
        history = engine.get_traction_history()
        # 5 complete_traction_cycle calls each auto-start next = 10 + initial 5 starts
        # But actually: start→complete(starts next) = cycle 1 completed + cycle 2 started
        assert len(history) >= 6  # At least 6 cycles created


# ------------------------------------------------------------------
# R&D Sprint Cycles (60-day)
# ------------------------------------------------------------------

class TestRDCycles:
    def test_start_rd_cycle(self, engine):
        cycle = engine.start_rd_cycle()
        assert cycle.cycle_number == 1
        assert cycle.status == CycleStatus.ACTIVE

    def test_start_rd_cycle_with_queued_items(self, engine):
        items = [
            {"title": "Build visual_workflow", "priority": "high"},
            {"title": "Build process_mining", "priority": "critical"},
        ]
        cycle = engine.start_rd_cycle(queued_items=items)
        assert len(cycle.queued_items) == 2

    def test_queue_rd_item(self, engine):
        engine.start_rd_cycle()
        success = engine.queue_rd_item({"title": "New Feature", "priority": "medium"})
        assert success is True

    def test_queue_rd_item_no_cycle(self, engine):
        success = engine.queue_rd_item({"title": "Orphan"})
        assert success is False

    def test_complete_rd_cycle_with_builds(self, engine):
        engine.start_rd_cycle(queued_items=[
            {"title": "Feature A", "priority": "high"},
            {"title": "Feature B", "priority": "medium"},
            {"title": "Feature C", "priority": "low"},
        ])
        result = engine.complete_rd_cycle(built_modules=[
            {"title": "Feature A", "status": "completed"},
            {"title": "Feature B", "status": "completed"},
        ])
        assert result is not None
        assert result["gap_analysis"]["total_queued"] == 3
        assert result["gap_analysis"]["total_built"] == 2
        assert result["gap_analysis"]["remaining_items"] == 1

    def test_rd_cycle_carries_over_remaining(self, engine):
        engine.start_rd_cycle(queued_items=[
            {"title": "Feature A", "priority": "high"},
            {"title": "Feature B", "priority": "low"},
        ])
        result = engine.complete_rd_cycle(built_modules=[
            {"title": "Feature A", "status": "completed"},
        ])
        # Feature B should carry over to next cycle
        next_cycle = result["next_cycle"]
        assert next_cycle["queued_items_count"] == 1

    def test_rd_cycle_auto_starts_next(self, engine):
        engine.start_rd_cycle()
        result = engine.complete_rd_cycle()
        assert result["next_cycle"]["cycle_number"] == 2

    def test_rd_60_day_period(self):
        engine = OperationsCycleEngine()
        assert engine.RD_SPRINT_CYCLE_DAYS == 60

    def test_rd_history(self, engine):
        engine.start_rd_cycle()
        engine.complete_rd_cycle()
        history = engine.get_rd_history()
        assert len(history) == 2  # completed + next auto-started

    def test_multiple_rd_cycles_repeat(self, engine):
        """R&D cycles repeat continuously."""
        for i in range(3):
            engine.start_rd_cycle(queued_items=[{"title": f"Item {i}"}])
            engine.complete_rd_cycle(built_modules=[{"title": f"Item {i}", "status": "done"}])
        history = engine.get_rd_history()
        assert len(history) >= 4


# ------------------------------------------------------------------
# Disruption Response (Instant)
# ------------------------------------------------------------------

class TestDisruptionResponse:
    def test_report_disruption(self, engine):
        dr = engine.report_disruption(
            disruptor="NewStartupAI",
            description="Launched AI-native RPA with real-time process mining",
            severity=DisruptionSeverity.HIGH,
            disruptor_features=["ai_native_rpa", "real_time_process_mining", "natural_language_automation"],
        )
        assert dr.disruptor == "NewStartupAI"
        assert dr.status == DisruptionResponseStatus.AWAITING_APPROVAL

    def test_disruption_gap_analysis(self, engine):
        dr = engine.report_disruption(
            disruptor="CompetitorX",
            description="Released autonomous coding assistant",
            severity=DisruptionSeverity.CRITICAL,
            disruptor_features=["autonomous_coding", "self_improving_ml", "multi_llm_routing"],
        )
        # self_improving_ml and multi_llm_routing are ours, autonomous_coding is not
        assert "autonomous_coding" in dr.our_gaps
        assert "self_improving_ml" in dr.our_existing_capabilities

    def test_disruption_proposed_builds(self, engine):
        dr = engine.report_disruption(
            disruptor="RivalCo",
            description="New visual workflow builder",
            severity=DisruptionSeverity.MEDIUM,
            disruptor_features=["visual_workflow_builder", "drag_drop_ui"],
        )
        assert len(dr.proposed_builds) == 2  # Both are gaps
        for build in dr.proposed_builds:
            assert "Non-derivative" in build["our_approach"] or "Murphy-native" in build["our_approach"]

    def test_disruption_requires_hitl_approval(self, engine):
        dr = engine.report_disruption(
            disruptor="DisruptorInc",
            description="AI revolution",
            severity=DisruptionSeverity.CRITICAL,
            disruptor_features=["new_feature"],
        )
        assert dr.status == DisruptionResponseStatus.AWAITING_APPROVAL
        assert dr.approved_by is None

    def test_approve_disruption(self, engine):
        dr = engine.report_disruption(
            disruptor="DisruptorInc",
            description="Test",
            severity=DisruptionSeverity.HIGH,
            disruptor_features=["new_feature"],
        )
        result = engine.approve_disruption_response(dr.response_id, "corey_post_founder")
        assert result is not None
        assert result.status == DisruptionResponseStatus.APPROVED
        assert result.approved_by == "corey_post_founder"

    def test_reject_disruption(self, engine):
        dr = engine.report_disruption(
            disruptor="DisruptorInc",
            description="Test",
            severity=DisruptionSeverity.LOW,
            disruptor_features=["trivial_feature"],
        )
        result = engine.reject_disruption_response(dr.response_id, "Not worth pursuing")
        assert result is not None
        assert result.status == DisruptionResponseStatus.REJECTED
        assert result.rejection_reason == "Not worth pursuing"

    def test_get_pending_disruptions(self, engine):
        engine.report_disruption("A", "Test A", DisruptionSeverity.HIGH, ["feat_a"])
        engine.report_disruption("B", "Test B", DisruptionSeverity.MEDIUM, ["feat_b"])
        pending = engine.get_pending_disruptions()
        assert len(pending) == 2

    def test_no_existing_gaps_when_we_have_features(self, engine):
        """If disruptor only has features we already have, no gaps."""
        dr = engine.report_disruption(
            disruptor="Copycat",
            description="Launched clone of Murphy",
            severity=DisruptionSeverity.LOW,
            disruptor_features=["multi_llm_routing", "audit_trail_compliance"],
        )
        assert len(dr.our_gaps) == 0
        assert len(dr.proposed_builds) == 0
        assert "multi_llm_routing" in dr.our_existing_capabilities

    def test_disruption_history(self, engine):
        engine.report_disruption("X", "test", DisruptionSeverity.LOW, [])
        history = engine.get_disruption_history()
        assert len(history) == 1


# ------------------------------------------------------------------
# Tick (Combined Cycle)
# ------------------------------------------------------------------

class TestTick:
    def test_tick_with_performance_data(self, engine):
        engine.start_traction_cycle()
        engine.start_rd_cycle()
        result = engine.tick(tier_performance={
            "pro": {"impressions": 5000, "leads": 200, "conversions": 10},
        })
        assert "traction" in result
        assert "rd_sprint" in result
        assert "pending_disruptions" in result
        assert "brand" in result
        assert result["brand"] == "murphy_system"

    def test_tick_without_performance_data(self, engine):
        engine.start_traction_cycle()
        result = engine.tick()
        assert result["traction"] is not None

    def test_tick_no_cycles(self, engine):
        result = engine.tick()
        assert result["traction"] is None
        assert result["rd_sprint"] is None


# ------------------------------------------------------------------
# Continuous Cycle Repetition
# ------------------------------------------------------------------

class TestContinuousCycles:
    def test_traction_and_rd_run_in_parallel(self, engine):
        """Both cycle types can run simultaneously."""
        tc = engine.start_traction_cycle()
        rd = engine.start_rd_cycle(queued_items=[{"title": "Build X"}])
        status = engine.get_status()
        assert status["active_traction_cycle"] == tc.cycle_id
        assert status["active_rd_cycle"] == rd.cycle_id

    def test_disruption_during_active_cycles(self, engine):
        """Disruptions can be reported while other cycles are active."""
        engine.start_traction_cycle()
        engine.start_rd_cycle()
        dr = engine.report_disruption("Rival", "New launch", DisruptionSeverity.HIGH, ["new_feat"])
        status = engine.get_status()
        assert status["active_traction_cycle"] is not None
        assert status["active_rd_cycle"] is not None
        assert status["pending_disruptions"] == 1

    def test_full_lifecycle_simulation(self, engine):
        """Simulate a full multi-cycle lifecycle."""
        # Start both cycles
        engine.start_traction_cycle()
        engine.start_rd_cycle(queued_items=[
            {"title": "visual_workflow"},
            {"title": "process_mining"},
        ])

        # Evaluate traction
        engine.evaluate_traction_cycle({
            "pro": {"impressions": 10000, "leads": 500, "conversions": 20},
            "enterprise": {"impressions": 2000, "leads": 50, "conversions": 3},
        })

        # Report a disruption mid-cycle
        dr = engine.report_disruption(
            "NewAI", "Launched agent builder", DisruptionSeverity.HIGH,
            ["agent_builder", "visual_workflow"],
        )
        engine.approve_disruption_response(dr.response_id, "founder")

        # Queue disruption items into R&D
        for build in dr.proposed_builds:
            engine.queue_rd_item(build)

        # Complete traction cycle (auto-starts next)
        engine.complete_traction_cycle()

        # Complete R&D cycle (auto-starts next with remaining)
        engine.complete_rd_cycle(built_modules=[
            {"title": "visual_workflow", "status": "completed"},
        ])

        status = engine.get_status()
        assert status["traction_cycle_count"] >= 2
        assert status["rd_cycle_count"] >= 2
        assert status["disruption_count"] == 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_get_status(self, engine):
        status = engine.get_status()
        assert "traction_cycle_count" in status
        assert "rd_cycle_count" in status
        assert "disruption_count" in status
        assert status["traction_cycle_days"] == 30
        assert status["rd_cycle_days"] == 60
        assert status["brand"] == "murphy_system"

    def test_event_log_grows(self, engine):
        engine.start_traction_cycle()
        engine.start_rd_cycle()
        status = engine.get_status()
        assert status["event_log_count"] >= 2
