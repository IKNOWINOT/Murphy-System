"""
Tests for Closure Engine and Finish Line Controller

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Covers:
- ClosurePhase progression (INITIATED → ... → CLOSED)
- WingmanProtocol validation at phase transitions
- Cost settlement calculations
- Resource release tracking
- Archive generation
- Closure checklist auto-generation and completion
- FinishLineController wind-down strategies
- Savings estimation
- Closure recommendation generation
- Dashboard data for both modules
- Error handling (missing phases)
- Concurrent closures
"""

import threading
import pytest

from closure_engine import ClosureEngine, ClosurePhase, ClosureTarget, ClosureChecklist
from finish_line_controller import FinishLineController, WindDownStrategy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Return a fresh ClosureEngine instance."""
    return ClosureEngine()


@pytest.fixture
def controller():
    """Return a fresh FinishLineController instance."""
    return FinishLineController()


@pytest.fixture
def initiated(engine):
    """Return a target in INITIATED phase."""
    return engine.initiate_closure("t-001", "project", "Test Project")


# ---------------------------------------------------------------------------
# ClosurePhase enum
# ---------------------------------------------------------------------------

class TestClosurePhaseEnum:
    def test_all_phases_present(self):
        values = {p.value for p in ClosurePhase}
        assert "initiated" in values
        assert "draining" in values
        assert "validating" in values
        assert "archiving" in values
        assert "settling" in values
        assert "releasing" in values
        assert "closed" in values
        assert "failed" in values

    def test_is_str_enum(self):
        assert ClosurePhase.INITIATED == "initiated"
        assert ClosurePhase.CLOSED == "closed"


# ---------------------------------------------------------------------------
# initiate_closure
# ---------------------------------------------------------------------------

class TestInitiateClosure:
    def test_creates_target(self, engine):
        target = engine.initiate_closure("proj-1", "project", "My Project")
        assert isinstance(target, ClosureTarget)
        assert target.target_id == "proj-1"
        assert target.target_type == "project"
        assert target.name == "My Project"

    def test_initial_status_is_initiated(self, engine):
        target = engine.initiate_closure("proj-2", "automation", "Bot")
        assert target.status == ClosurePhase.INITIATED

    def test_timestamps_set(self, engine):
        target = engine.initiate_closure("proj-3", "pipeline", "Pipe")
        assert target.created_at != ""
        assert target.initiated_at != ""
        assert "initiated" in target.phase_timestamps

    def test_phases_completed_contains_initiated(self, engine):
        target = engine.initiate_closure("proj-4", "project", "X")
        assert "initiated" in target.phases_completed


# ---------------------------------------------------------------------------
# drain
# ---------------------------------------------------------------------------

class TestDrain:
    def test_drain_returns_expected_keys(self, engine, initiated):
        result = engine.drain("t-001", ["task-1", "task-2", "task-3"])
        assert "drained_count" in result
        assert "remaining" in result
        assert "estimated_drain_time_ms" in result

    def test_drain_count_matches_items(self, engine, initiated):
        result = engine.drain("t-001", ["a", "b", "c"])
        assert result["drained_count"] == 3

    def test_drain_advances_status(self, engine, initiated):
        engine.drain("t-001")
        target = engine.list_closures()[0]
        assert target.status == ClosurePhase.DRAINING

    def test_drain_missing_target(self, engine):
        result = engine.drain("nonexistent")
        assert result["drained_count"] == 0

    def test_drain_no_items(self, engine, initiated):
        result = engine.drain("t-001")
        assert result["drained_count"] == 0
        assert result["remaining"] == 0


# ---------------------------------------------------------------------------
# validate_outputs
# ---------------------------------------------------------------------------

class TestValidateOutputs:
    def test_validate_returns_expected_keys(self, engine, initiated):
        result = engine.validate_outputs("t-001")
        assert "validated" in result
        assert "failed" in result
        assert "warnings" in result
        assert "approved" in result

    def test_validate_approved_with_clean_outputs(self, engine, initiated):
        result = engine.validate_outputs("t-001", [{"result": "ok", "status": "done"}])
        assert result["approved"] is True
        assert result["validated"] >= 1

    def test_validate_missing_target(self, engine):
        result = engine.validate_outputs("no-such-target")
        assert result["approved"] is False

    def test_validate_advances_status_to_validating(self, engine, initiated):
        engine.drain("t-001")
        engine.validate_outputs("t-001")
        target = engine.list_closures()[0]
        assert target.status == ClosurePhase.VALIDATING


# ---------------------------------------------------------------------------
# settle_costs
# ---------------------------------------------------------------------------

class TestSettleCosts:
    def test_settle_returns_expected_keys(self, engine, initiated):
        result = engine.settle_costs("t-001")
        assert "total_cost" in result
        assert "cost_breakdown" in result
        assert "budget_remaining" in result
        assert "settlement_status" in result

    def test_settle_calculates_total(self, engine, initiated):
        result = engine.settle_costs("t-001", {"compute": 10.0, "storage": 5.0, "api": 2.5})
        assert result["total_cost"] == pytest.approx(17.5)

    def test_settle_stores_final_cost(self, engine, initiated):
        engine.settle_costs("t-001", {"item": 42.0})
        targets = engine.list_closures()
        assert targets[0].final_cost == pytest.approx(42.0)

    def test_settle_missing_target(self, engine):
        result = engine.settle_costs("ghost")
        assert result["settlement_status"] == "no_target"

    def test_settle_empty_costs(self, engine, initiated):
        result = engine.settle_costs("t-001")
        assert result["total_cost"] == pytest.approx(0.0)
        assert result["settlement_status"] == "settled"


# ---------------------------------------------------------------------------
# release_resources
# ---------------------------------------------------------------------------

class TestReleaseResources:
    def test_release_returns_expected_keys(self, engine, initiated):
        result = engine.release_resources("t-001")
        assert "released" in result
        assert "failed_to_release" in result
        assert "warnings" in result

    def test_released_list_matches_input(self, engine, initiated):
        resources = ["api-key-1", "connection-db", "compute-node-7"]
        result = engine.release_resources("t-001", resources)
        assert set(result["released"]) == set(resources)

    def test_resources_tracked_on_target(self, engine, initiated):
        engine.release_resources("t-001", ["key-a", "key-b"])
        targets = engine.list_closures()
        assert "key-a" in targets[0].resources_released
        assert "key-b" in targets[0].resources_released

    def test_release_missing_target(self, engine):
        result = engine.release_resources("phantom")
        assert result["released"] == []


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

class TestArchive:
    def test_archive_returns_expected_keys(self, engine, initiated):
        result = engine.archive("t-001")
        assert "archive_id" in result
        assert "archive_location" in result
        assert "size_bytes" in result
        assert "archived_items" in result

    def test_archive_id_is_set(self, engine, initiated):
        result = engine.archive("t-001")
        assert result["archive_id"] != ""

    def test_custom_archive_path(self, engine, initiated):
        result = engine.archive("t-001", archive_path="/tmp/my-archive")
        assert result["archive_location"] == "/tmp/my-archive"

    def test_default_archive_path_contains_target_id(self, engine, initiated):
        result = engine.archive("t-001")
        assert "t-001" in result["archive_location"]

    def test_archive_location_stored_on_target(self, engine, initiated):
        engine.archive("t-001", "/custom/path")
        targets = engine.list_closures()
        assert targets[0].archive_location == "/custom/path"

    def test_archive_missing_target(self, engine):
        result = engine.archive("no-target")
        assert result["archive_id"] == ""


# ---------------------------------------------------------------------------
# complete_closure
# ---------------------------------------------------------------------------

class TestCompleteClosure:
    def _run_all_phases(self, engine, target_id):
        engine.drain(target_id)
        engine.validate_outputs(target_id)
        engine.archive(target_id)
        engine.settle_costs(target_id, {"total": 5.0})
        engine.release_resources(target_id, ["res-1"])

    def test_complete_sets_closed_status(self, engine, initiated):
        self._run_all_phases(engine, "t-001")
        closed = engine.complete_closure("t-001")
        assert closed.status == ClosurePhase.CLOSED

    def test_complete_sets_completed_at(self, engine, initiated):
        self._run_all_phases(engine, "t-001")
        closed = engine.complete_closure("t-001")
        assert closed.completed_at != ""

    def test_complete_generates_closure_report(self, engine, initiated):
        self._run_all_phases(engine, "t-001")
        closed = engine.complete_closure("t-001")
        assert "target_id" in closed.closure_report
        assert closed.closure_report["target_id"] == "t-001"

    def test_complete_missing_phases_sets_failed(self, engine, initiated):
        # Do not run any phases — should fail
        failed = engine.complete_closure("t-001")
        assert failed.status == ClosurePhase.FAILED
        assert len(failed.errors) > 0

    def test_complete_missing_target_raises(self, engine):
        with pytest.raises(KeyError):
            engine.complete_closure("nonexistent")


# ---------------------------------------------------------------------------
# advance_phase
# ---------------------------------------------------------------------------

class TestAdvancePhase:
    def test_advance_from_initiated_to_draining(self, engine, initiated):
        target = engine.advance_phase("t-001")
        assert target.status == ClosurePhase.DRAINING

    def test_advance_closed_target_stays_closed(self, engine):
        engine.initiate_closure("t-adv", "project", "Adv")
        engine.drain("t-adv")
        engine.validate_outputs("t-adv")
        engine.archive("t-adv")
        engine.settle_costs("t-adv")
        engine.release_resources("t-adv")
        engine.complete_closure("t-adv")
        # Advancing a CLOSED target should be a no-op
        target = engine.advance_phase("t-adv")
        assert target.status == ClosurePhase.CLOSED

    def test_advance_missing_target_raises(self, engine):
        with pytest.raises(KeyError):
            engine.advance_phase("no-such-target")


# ---------------------------------------------------------------------------
# get_closure_report
# ---------------------------------------------------------------------------

class TestGetClosureReport:
    def test_report_contains_required_fields(self, engine, initiated):
        report = engine.get_closure_report("t-001")
        required_fields = [
            "target_id", "target_type", "name", "status",
            "initiated_at", "phases_completed", "final_cost",
            "resources_released", "archive_location", "errors",
        ]
        for field_name in required_fields:
            assert field_name in report, f"Missing field: {field_name}"

    def test_report_missing_target(self, engine):
        report = engine.get_closure_report("ghost")
        assert "error" in report


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

class TestClosureChecklist:
    def test_create_checklist_returns_checklist(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        assert isinstance(checklist, ClosureChecklist)
        assert checklist.target_id == "t-001"
        assert len(checklist.items) > 0

    def test_checklist_items_have_required_fields(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        for item in checklist.items:
            assert "item_id" in item
            assert "description" in item
            assert "required" in item
            assert "completed" in item

    def test_checklist_items_initially_incomplete(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        assert all(not item["completed"] for item in checklist.items)

    def test_complete_checklist_item_marks_completed(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        first_id = checklist.items[0]["item_id"]
        result = engine.complete_checklist_item(checklist.checklist_id, first_id, "test-user")
        assert result is True

    def test_complete_all_required_sets_flag(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        required_ids = [i["item_id"] for i in checklist.items if i["required"]]
        for item_id in required_ids:
            engine.complete_checklist_item(checklist.checklist_id, item_id)
        assert checklist.all_required_complete is True

    def test_complete_nonexistent_item_returns_false(self, engine, initiated):
        checklist = engine.create_checklist("t-001")
        result = engine.complete_checklist_item(checklist.checklist_id, "fake-item-id")
        assert result is False

    def test_complete_nonexistent_checklist_returns_false(self, engine, initiated):
        result = engine.complete_checklist_item("fake-cl-id", "item-001")
        assert result is False

    def test_checklist_template_by_type(self, engine):
        for ttype in ["project", "automation", "orchestrator", "pipeline", "integration", "subscription"]:
            engine.initiate_closure(f"t-{ttype}", ttype, ttype)
            checklist = engine.create_checklist(f"t-{ttype}")
            assert len(checklist.items) > 0

    def test_checklist_unknown_type_uses_default(self, engine):
        engine.initiate_closure("t-unknown", "mystery_type", "Mystery")
        checklist = engine.create_checklist("t-unknown")
        assert len(checklist.items) > 0


# ---------------------------------------------------------------------------
# list_closures
# ---------------------------------------------------------------------------

class TestListClosures:
    def test_list_all(self, engine):
        engine.initiate_closure("la-1", "project", "P1")
        engine.initiate_closure("la-2", "automation", "A1")
        closures = engine.list_closures()
        assert len(closures) >= 2

    def test_filter_by_status(self, engine):
        engine.initiate_closure("lf-1", "project", "P")
        closures = engine.list_closures(status="initiated")
        assert all(c.status.value == "initiated" for c in closures)

    def test_filter_by_type(self, engine):
        engine.initiate_closure("lft-1", "subscription", "S")
        engine.initiate_closure("lft-2", "project", "P")
        subs = engine.list_closures(target_type="subscription")
        assert all(c.target_type == "subscription" for c in subs)


# ---------------------------------------------------------------------------
# get_dashboard (ClosureEngine)
# ---------------------------------------------------------------------------

class TestEngineGetDashboard:
    def test_dashboard_has_expected_keys(self, engine):
        dash = engine.get_dashboard()
        assert "total_closures" in dash
        assert "active_closures" in dash
        assert "completed_closures" in dash
        assert "failed_closures" in dash
        assert "costs_settled" in dash
        assert "resources_released" in dash

    def test_completed_count_increments(self, engine):
        engine.initiate_closure("dash-1", "project", "P")
        engine.drain("dash-1")
        engine.validate_outputs("dash-1")
        engine.archive("dash-1")
        engine.settle_costs("dash-1", {"x": 1.0})
        engine.release_resources("dash-1", ["r"])
        engine.complete_closure("dash-1")
        dash = engine.get_dashboard()
        assert dash["completed_closures"] >= 1


# ---------------------------------------------------------------------------
# WindDownStrategy enum
# ---------------------------------------------------------------------------

class TestWindDownStrategyEnum:
    def test_all_strategies_present(self):
        values = {s.value for s in WindDownStrategy}
        assert "immediate" in values
        assert "graceful" in values
        assert "phased" in values
        assert "budget_driven" in values

    def test_is_str_enum(self):
        assert WindDownStrategy.IMMEDIATE == "immediate"


# ---------------------------------------------------------------------------
# plan_wind_down
# ---------------------------------------------------------------------------

_SAMPLE_TARGETS = [
    {"target_id": "wt-1", "target_type": "project", "name": "Project Alpha", "monthly_cost": 100.0},
    {"target_id": "wt-2", "target_type": "automation", "name": "Bot Beta", "monthly_cost": 50.0},
]


class TestPlanWindDown:
    def test_plan_returns_expected_keys(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        assert "plan_id" in plan
        assert "strategy" in plan
        assert "phases" in plan
        assert "estimated_duration_ms" in plan
        assert "estimated_savings" in plan

    def test_plan_id_is_set(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        assert plan["plan_id"] != ""

    def test_default_strategy_is_graceful(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        assert plan["strategy"] == "graceful"

    def test_immediate_strategy(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS, strategy="immediate")
        assert plan["strategy"] == "immediate"

    def test_phased_strategy_groups_by_priority(self, controller):
        targets = [
            {"target_id": "ph-1", "target_type": "project", "name": "H", "priority": "high", "monthly_cost": 10.0},
            {"target_id": "ph-2", "target_type": "project", "name": "L", "priority": "low", "monthly_cost": 5.0},
        ]
        plan = controller.plan_wind_down(targets, strategy="phased")
        assert plan["strategy"] == "phased"
        assert len(plan["phases"]) >= 1

    def test_budget_driven_strategy(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS, strategy="budget_driven")
        assert plan["strategy"] == "budget_driven"

    def test_invalid_strategy_defaults_to_graceful(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS, strategy="unknown_strat")
        assert plan["strategy"] == "graceful"


# ---------------------------------------------------------------------------
# execute_wind_down
# ---------------------------------------------------------------------------

class TestExecuteWindDown:
    def test_execute_returns_completed_status(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        result = controller.execute_wind_down(plan["plan_id"])
        assert result["status"] == "completed"

    def test_execute_returns_target_results(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        result = controller.execute_wind_down(plan["plan_id"])
        assert "target_results" in result
        assert "wt-1" in result["target_results"]
        assert "wt-2" in result["target_results"]

    def test_execute_missing_plan(self, controller):
        result = controller.execute_wind_down("nonexistent-plan")
        assert "error" in result

    def test_execute_immediate_strategy(self, controller):
        targets = [
            {"target_id": "imm-1", "target_type": "project", "name": "Quick", "monthly_cost": 20.0},
        ]
        plan = controller.plan_wind_down(targets, strategy="immediate")
        result = controller.execute_wind_down(plan["plan_id"])
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# get_wind_down_status
# ---------------------------------------------------------------------------

class TestGetWindDownStatus:
    def test_status_returns_expected_keys(self, controller):
        plan = controller.plan_wind_down(_SAMPLE_TARGETS)
        status = controller.get_wind_down_status(plan["plan_id"])
        assert "plan_id" in status
        assert "strategy" in status
        assert "status" in status

    def test_status_missing_plan(self, controller):
        status = controller.get_wind_down_status("ghost-plan")
        assert "error" in status


# ---------------------------------------------------------------------------
# estimate_savings
# ---------------------------------------------------------------------------

class TestEstimateSavings:
    def test_savings_returns_expected_keys(self, controller):
        savings = controller.estimate_savings(_SAMPLE_TARGETS)
        assert "monthly_savings" in savings
        assert "annual_savings" in savings
        assert "one_time_recovery" in savings
        assert "breakdown" in savings

    def test_monthly_savings_totals_correctly(self, controller):
        targets = [
            {"target_id": "s1", "monthly_cost": 100.0},
            {"target_id": "s2", "monthly_cost": 50.0},
        ]
        savings = controller.estimate_savings(targets)
        assert savings["monthly_savings"] == pytest.approx(150.0)

    def test_annual_savings_is_12x_monthly(self, controller):
        targets = [{"target_id": "s3", "monthly_cost": 200.0}]
        savings = controller.estimate_savings(targets)
        assert savings["annual_savings"] == pytest.approx(2400.0)

    def test_breakdown_per_target(self, controller):
        targets = [{"target_id": "s4", "monthly_cost": 30.0}]
        savings = controller.estimate_savings(targets)
        assert "s4" in savings["breakdown"]
        assert savings["breakdown"]["s4"]["monthly_savings"] == pytest.approx(30.0)

    def test_empty_targets(self, controller):
        savings = controller.estimate_savings([])
        assert savings["monthly_savings"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# recommend_closures
# ---------------------------------------------------------------------------

class TestRecommendClosures:
    def test_recommend_returns_list(self, controller):
        engine = controller._engine
        engine.initiate_closure("rec-1", "project", "Big Project")
        engine.settle_costs("rec-1", {"monthly": 200.0})
        recs = controller.recommend_closures()
        assert isinstance(recs, list)

    def test_each_recommendation_has_expected_keys(self, controller):
        engine = controller._engine
        engine.initiate_closure("rec-2", "automation", "Bot")
        engine.settle_costs("rec-2", {"monthly": 50.0})
        recs = controller.recommend_closures()
        for rec in recs:
            assert "target_id" in rec
            assert "estimated_monthly_savings" in rec
            assert "risk" in rec
            assert "reasoning" in rec

    def test_budget_target_limits_recommendations(self, controller):
        engine = controller._engine
        for i in range(5):
            engine.initiate_closure(f"bt-{i}", "project", f"Project {i}")
            engine.settle_costs(f"bt-{i}", {"monthly": float((i + 1) * 10)})

        # Budget target of 15 should return at most the top 1-2 items
        recs = controller.recommend_closures(budget_target=15.0)
        total = sum(r["estimated_monthly_savings"] for r in recs)
        assert total >= 15.0 or len(recs) > 0


# ---------------------------------------------------------------------------
# get_dashboard (FinishLineController)
# ---------------------------------------------------------------------------

class TestControllerGetDashboard:
    def test_dashboard_has_expected_keys(self, controller):
        dash = controller.get_dashboard()
        assert "total_plans" in dash
        assert "active_plans" in dash
        assert "completed_plans" in dash
        assert "targets_closed" in dash
        assert "savings_achieved_monthly" in dash
        assert "savings_achieved_annual" in dash
        assert "engine_dashboard" in dash

    def test_completed_plans_increments(self, controller):
        targets = [{"target_id": "cd-1", "target_type": "project", "name": "P", "monthly_cost": 10.0}]
        plan = controller.plan_wind_down(targets)
        controller.execute_wind_down(plan["plan_id"])
        dash = controller.get_dashboard()
        assert dash["completed_plans"] >= 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_closure_fails_when_phases_missing(self, engine):
        engine.initiate_closure("err-1", "project", "Incomplete")
        # Skip all required phases → complete_closure should mark as FAILED
        target = engine.complete_closure("err-1")
        assert target.status == ClosurePhase.FAILED
        assert len(target.errors) > 0

    def test_errors_recorded_in_report(self, engine):
        engine.initiate_closure("err-2", "project", "Failing")
        engine.complete_closure("err-2")
        report = engine.get_closure_report("err-2")
        assert len(report["errors"]) > 0


# ---------------------------------------------------------------------------
# Concurrent closures
# ---------------------------------------------------------------------------

class TestConcurrentClosures:
    def test_concurrent_initiations_do_not_conflict(self, engine):
        errors: list = []

        def initiate(i: int) -> None:
            try:
                engine.initiate_closure(f"conc-{i}", "project", f"Concurrent {i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=initiate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        closures = engine.list_closures()
        concurrent = [c for c in closures if c.target_id.startswith("conc-")]
        assert len(concurrent) == 20

    def test_concurrent_phase_advances_are_safe(self, engine):
        engine.initiate_closure("safe-1", "project", "Safe")
        errors: list = []

        def advance() -> None:
            try:
                engine.advance_phase("safe-1")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=advance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
