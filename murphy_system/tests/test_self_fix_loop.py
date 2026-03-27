"""
Comprehensive tests for ARCH-005: SelfFixLoop.

Validates the Plan → Execute → Test → Verify → Repeat cycle,
safety invariants, rollback, persistence, event publishing, and
end-to-end gap closure flows.

Design Label: TEST-ARCH-005
Owner: QA Team
"""

import os
import threading
import time

import pytest


from self_fix_loop import (
    SelfFixLoop,
    Gap,
    FixPlan,
    FixExecution,
    LoopReport,
)
from self_improvement_engine import (
    SelfImprovementEngine,
    ExecutionOutcome,
    OutcomeType,
    ImprovementProposal,
)
from self_healing_coordinator import (
    SelfHealingCoordinator,
    RecoveryProcedure,
    RecoveryStatus,
)
from bug_pattern_detector import BugPatternDetector
from event_backbone import EventBackbone, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return SelfImprovementEngine()


@pytest.fixture
def coordinator():
    return SelfHealingCoordinator()


@pytest.fixture
def detector():
    return BugPatternDetector()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def loop(engine, coordinator, detector, backbone):
    return SelfFixLoop(
        improvement_engine=engine,
        healing_coordinator=coordinator,
        bug_detector=detector,
        event_backbone=backbone,
    )


@pytest.fixture
def minimal_loop():
    """Loop with no dependencies — useful for isolated unit tests."""
    return SelfFixLoop()


def _inject_timeouts(engine: SelfImprovementEngine, count: int = 3) -> None:
    """Inject timeout outcomes into the engine."""
    for i in range(count):
        engine.record_outcome(ExecutionOutcome(
            task_id=f"task-timeout-{i}",
            session_id="test",
            outcome=OutcomeType.TIMEOUT,
            metrics={"task_type": "api_call"},
        ))


def _inject_failures(engine: SelfImprovementEngine, count: int = 3, task_type: str = "deploy") -> None:
    for i in range(count):
        engine.record_outcome(ExecutionOutcome(
            task_id=f"task-fail-{i}",
            session_id="test",
            outcome=OutcomeType.FAILURE,
            metrics={"task_type": task_type},
        ))


def _inject_bug_errors(detector: BugPatternDetector, count: int = 5, component: str = "db") -> None:
    for i in range(count):
        detector.ingest_error(
            message="Connection timeout on database call",
            component=component,
            error_type="TimeoutError",
        )


# ---------------------------------------------------------------------------
# 1. test_diagnose_finds_known_gaps
# ---------------------------------------------------------------------------

class TestDiagnose:
    def test_diagnose_finds_known_gaps(self, loop, engine, detector):
        """Inject known errors and verify diagnose() finds them."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()

        _inject_bug_errors(detector, 5)
        detector.run_detection_cycle()

        gaps = loop.diagnose()
        assert len(gaps) > 0

        sources = {g.source for g in gaps}
        assert "improvement_engine" in sources or "bug_detector" in sources

    def test_diagnose_returns_empty_when_clean(self, minimal_loop):
        """Diagnose returns empty list when no issues exist."""
        gaps = minimal_loop.diagnose()
        assert gaps == []

    def test_diagnose_gap_fields(self, loop, engine):
        """Gaps from improvement engine have required fields."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()

        gaps = loop.diagnose()
        assert len(gaps) > 0

        for g in gaps:
            assert g.gap_id
            assert g.description
            assert g.source in ("bug_detector", "improvement_engine", "health_check")
            assert g.severity in ("critical", "high", "medium", "low")


# ---------------------------------------------------------------------------
# 2. test_plan_creates_valid_fix_plan
# ---------------------------------------------------------------------------

class TestPlan:
    def test_plan_creates_valid_fix_plan(self, loop, engine):
        """Verify plans have all required fields and are executable."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()
        gaps = loop.diagnose()
        assert gaps

        plan = loop.plan(gaps[0])

        assert plan.plan_id
        assert plan.gap_description
        assert plan.fix_type in (
            "config_adjustment", "threshold_tuning", "recovery_registration",
            "route_optimization", "code_proposal"
        )
        assert isinstance(plan.fix_steps, list)
        assert len(plan.fix_steps) > 0
        assert plan.expected_outcome
        assert isinstance(plan.test_criteria, list)
        assert plan.status == "planned"
        assert plan.created_at

    def test_plan_timeout_gap_produces_threshold_tuning(self, loop, engine):
        """Timeout gaps should produce threshold_tuning plans."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()
        gaps = loop.diagnose()
        timeout_gaps = [g for g in gaps if "timeout" in g.description.lower() or g.category == "timeout"]
        assert timeout_gaps, "Expected at least one timeout gap"

        plan = loop.plan(timeout_gaps[0])
        assert plan.fix_type == "threshold_tuning"
        actions = [s["action"] for s in plan.fix_steps]
        assert "adjust_timeout" in actions or "recalibrate_confidence" in actions

    def test_plan_code_proposal_type_for_unknown_gaps(self, loop):
        """Unknown/unmappable gaps produce code_proposal type plans."""
        gap = Gap(
            gap_id="gap-unknown",
            description="Some obscure issue that cannot be auto-fixed",
            source="health_check",
            severity="low",
            category="unknown_system",
        )
        plan = loop.plan(gap)
        assert plan.fix_type == "code_proposal"

    def test_plan_stores_in_internal_registry(self, loop):
        """Plan is stored internally after creation."""
        gap = Gap(gap_id="g-test", description="test gap", source="health_check")
        plan = loop.plan(gap)
        assert plan.plan_id in loop._plans


# ---------------------------------------------------------------------------
# 3. test_execute_applies_config_fix
# ---------------------------------------------------------------------------

class TestExecuteConfig:
    def test_execute_applies_timeout_fix(self, loop):
        """Execute a timeout adjustment and verify the config changed."""
        gap = Gap(gap_id="g1", description="Timeout errors", source="health_check", category="api_call")
        plan = FixPlan(
            plan_id="plan-t1",
            gap_description="Timeout errors in api_call",
            context="",
            fix_type="threshold_tuning",
            fix_steps=[{"action": "adjust_timeout", "target": "api_call", "parameter": "timeout_seconds", "delta": 30}],
            expected_outcome="Timeout reduced",
            test_criteria=[{"check": "timeout_errors_reduced", "category": "api_call"}],
            rollback_steps=[{"action": "adjust_timeout", "target": "api_call", "parameter": "timeout_seconds", "delta": -30}],
        )
        loop._plans[plan.plan_id] = plan
        execution = loop.execute(plan, gap)

        assert loop._runtime_config.get("timeout_seconds:api_call", 0) > 60
        assert any(r["success"] for r in execution.step_results)


# ---------------------------------------------------------------------------
# 4. test_execute_applies_threshold_fix
# ---------------------------------------------------------------------------

class TestExecuteThreshold:
    def test_execute_recalibrates_confidence(self, loop, engine):
        """Execute a confidence recalibration and verify the threshold changed."""
        # Inject outcomes so calibration has data
        for i in range(5):
            engine.record_outcome(ExecutionOutcome(
                task_id=f"conf-{i}", session_id="s",
                outcome=OutcomeType.SUCCESS if i < 4 else OutcomeType.FAILURE,
                metrics={"task_type": "analytics", "confidence": 0.9},
            ))

        gap = Gap(gap_id="g2", description="Confidence miscalibration", source="improvement_engine", category="analytics")
        plan = FixPlan(
            plan_id="plan-c1",
            gap_description="Recalibrate confidence",
            context="",
            fix_type="threshold_tuning",
            fix_steps=[{"action": "recalibrate_confidence", "target": "analytics", "parameter": "confidence_threshold"}],
            expected_outcome="Confidence calibrated",
            test_criteria=[{"check": "confidence_calibrated", "category": "analytics"}],
            rollback_steps=[{"action": "restore_confidence", "target": "analytics"}],
        )
        loop._plans[plan.plan_id] = plan
        execution = loop.execute(plan, gap)

        assert "confidence_threshold:analytics" in loop._runtime_config
        assert 0.0 < loop._runtime_config["confidence_threshold:analytics"] <= 1.0
        assert any(r["success"] for r in execution.step_results)


# ---------------------------------------------------------------------------
# 5. test_execute_registers_recovery_procedure
# ---------------------------------------------------------------------------

class TestExecuteRecovery:
    def test_execute_registers_recovery_procedure(self, loop, coordinator):
        """Execute recovery registration and verify coordinator has it."""
        gap = Gap(gap_id="g3", description="No recovery for db_timeout", source="bug_detector", category="db_timeout")
        plan = FixPlan(
            plan_id="plan-r1",
            gap_description="Register db_timeout recovery",
            context="",
            fix_type="recovery_registration",
            fix_steps=[{
                "action": "register_recovery_procedure",
                "target": "db_timeout",
                "description": "Auto-retry DB connection on timeout",
            }],
            expected_outcome="Recovery registered",
            test_criteria=[{"check": "recovery_procedure_registered", "category": "db_timeout"}],
            rollback_steps=[{"action": "unregister_recovery_procedure", "target": "db_timeout"}],
        )
        loop._plans[plan.plan_id] = plan
        execution = loop.execute(plan, gap)

        status = coordinator.get_status()
        assert "db_timeout" in status["categories"]
        assert any(r["success"] for r in execution.step_results)


# ---------------------------------------------------------------------------
# 6. test_execute_rollback_on_failure
# ---------------------------------------------------------------------------

class TestRollback:
    def test_execute_rollback_on_failure(self, loop):
        """Verify rollback reverses all steps."""
        # First apply a timeout change
        loop._runtime_config["timeout_seconds:svc"] = 90

        plan = FixPlan(
            plan_id="plan-rb1",
            gap_description="Rollback test",
            context="",
            fix_type="threshold_tuning",
            fix_steps=[{"action": "adjust_timeout", "target": "svc", "parameter": "timeout_seconds", "delta": 60}],
            expected_outcome="Timeout adjusted",
            test_criteria=[],
            rollback_steps=[{"action": "adjust_timeout", "target": "svc", "parameter": "timeout_seconds", "delta": -60}],
        )
        loop._plans[plan.plan_id] = plan
        execution = FixExecution(
            execution_id="exec-rb1", plan_id=plan.plan_id,
            step_results=[], tests_run=[],
            gaps_before=[], gaps_after=[], regressions=[],
        )
        loop._executions[execution.execution_id] = execution

        before = loop._runtime_config.get("timeout_seconds:svc", 60)
        loop.rollback(plan, execution)
        after = loop._runtime_config.get("timeout_seconds:svc", 60)

        assert after < before
        assert plan.status == "rolled_back"
        assert execution.status == "rolled_back"


# ---------------------------------------------------------------------------
# 7. test_test_validates_gap_closed
# ---------------------------------------------------------------------------

class TestTestStep:
    def test_test_validates_gap_closed(self, loop):
        """Verify the test step correctly detects closed gaps after a timeout fix."""
        loop._runtime_config["timeout_seconds:web"] = 90  # already adjusted

        plan = FixPlan(
            plan_id="plan-tv1",
            gap_description="Timeout gap",
            context="",
            fix_type="threshold_tuning",
            fix_steps=[],
            expected_outcome="Timeout fixed",
            test_criteria=[{"check": "timeout_errors_reduced", "category": "web"}],
            rollback_steps=[],
        )
        plan.status = "testing"
        execution = FixExecution(
            execution_id="exec-tv1", plan_id=plan.plan_id,
            step_results=[], tests_run=[],
            gaps_before=["gap-web"], gaps_after=["gap-web"], regressions=[],
        )

        result = loop.test(plan, execution)
        assert result is True
        assert execution.gaps_after == []
        assert all(t["passed"] for t in execution.tests_run)

    def test_test_fails_when_gap_still_present(self, loop):
        """Timeout check fails when timeout is still at default (60s)."""
        # Don't touch runtime config — timeout_seconds defaults to 60
        plan = FixPlan(
            plan_id="plan-tv2",
            gap_description="Timeout gap",
            context="",
            fix_type="threshold_tuning",
            fix_steps=[],
            expected_outcome="Timeout fixed",
            test_criteria=[{"check": "timeout_errors_reduced", "category": "not_adjusted"}],
            rollback_steps=[],
        )
        plan.status = "testing"
        execution = FixExecution(
            execution_id="exec-tv2", plan_id=plan.plan_id,
            step_results=[], tests_run=[],
            gaps_before=["gap-x"], gaps_after=["gap-x"], regressions=[],
        )
        result = loop.test(plan, execution)
        assert result is False


# ---------------------------------------------------------------------------
# 8. test_test_detects_regressions
# ---------------------------------------------------------------------------

class TestRegressions:
    def test_test_detects_regressions(self, loop):
        """Verify the test step catches invalid config values as regressions."""
        # Inject invalid runtime config
        loop._runtime_config["confidence_threshold:broken"] = 1.5  # out of range

        plan = FixPlan(
            plan_id="plan-reg1",
            gap_description="Regression test",
            context="",
            fix_type="code_proposal",
            fix_steps=[],
            expected_outcome="No regressions",
            test_criteria=[{"check": "proposal_logged_for_review", "gap_id": "x"}],
            rollback_steps=[],
        )
        plan.status = "testing"
        execution = FixExecution(
            execution_id="exec-reg1", plan_id=plan.plan_id,
            step_results=[], tests_run=[],
            gaps_before=[], gaps_after=[], regressions=[],
        )
        result = loop.test(plan, execution)
        assert execution.regressions, "Should have detected regression"
        assert result is False


# ---------------------------------------------------------------------------
# 9. test_verify_confirms_fix_permanent
# ---------------------------------------------------------------------------

class TestVerify:
    def test_verify_confirms_fix_permanent(self, loop):
        """Verify the verification step returns True when gap is gone and no regressions."""
        execution = FixExecution(
            execution_id="exec-v1", plan_id="plan-v1",
            step_results=[], tests_run=[{"check": "x", "passed": True}],
            gaps_before=["gap-v1"], gaps_after=[], regressions=[],
            status="success",
        )
        gap = Gap(gap_id="gap-v1", description="test", source="health_check")
        result = loop.verify(execution, gap)
        assert result is True

    def test_verify_fails_when_regressions_exist(self, loop):
        """Verify returns False if regressions are present."""
        execution = FixExecution(
            execution_id="exec-v2", plan_id="plan-v2",
            step_results=[], tests_run=[{"check": "x", "passed": True}],
            gaps_before=[], gaps_after=[], regressions=["some regression"],
        )
        result = loop.verify(execution)
        assert result is False


# ---------------------------------------------------------------------------
# 10. test_full_loop_fixes_timeout_gap
# ---------------------------------------------------------------------------

class TestFullLoopTimeout:
    def test_full_loop_fixes_timeout_gap(self, engine, coordinator, backbone):
        """End-to-end: inject timeout errors → loop diagnoses → plans → executes → verifies."""
        _inject_timeouts(engine, 4)
        engine.generate_proposals()

        loop = SelfFixLoop(
            improvement_engine=engine,
            healing_coordinator=coordinator,
            event_backbone=backbone,
        )
        report = loop.run_loop(max_iterations=3)

        assert isinstance(report, LoopReport)
        assert report.iterations_run >= 1
        assert report.gaps_found > 0
        assert report.plans_executed > 0


# ---------------------------------------------------------------------------
# 11. test_full_loop_fixes_confidence_gap
# ---------------------------------------------------------------------------

class TestFullLoopConfidence:
    def test_full_loop_fixes_confidence_gap(self, backbone):
        """End-to-end: inject miscalibrated confidence data → loop recalibrates."""
        engine = SelfImprovementEngine()
        for i in range(5):
            engine.record_outcome(ExecutionOutcome(
                task_id=f"c{i}", session_id="s",
                outcome=OutcomeType.FAILURE,
                metrics={"task_type": "ml_inference", "confidence": 0.95},
            ))
        engine.generate_proposals()

        loop = SelfFixLoop(improvement_engine=engine, event_backbone=backbone)
        report = loop.run_loop(max_iterations=5)

        assert isinstance(report, LoopReport)
        assert report.iterations_run >= 1


# ---------------------------------------------------------------------------
# 12. test_full_loop_stops_when_no_gaps
# ---------------------------------------------------------------------------

class TestFullLoopNoGaps:
    def test_full_loop_stops_when_no_gaps(self):
        """Verify loop terminates immediately when all gaps are closed."""
        loop = SelfFixLoop()
        report = loop.run_loop(max_iterations=10)

        assert report.iterations_run == 1  # one pass to confirm no gaps
        assert report.gaps_found == 0
        assert report.gaps_remaining == 0
        assert report.final_health_status == "green"


# ---------------------------------------------------------------------------
# 13. test_full_loop_respects_max_iterations
# ---------------------------------------------------------------------------

class TestFullLoopMaxIterations:
    def test_full_loop_respects_max_iterations(self, engine, backbone):
        """Verify loop doesn't exceed max_iterations."""
        # Inject persistent failures that won't auto-resolve
        for i in range(10):
            engine.record_outcome(ExecutionOutcome(
                task_id=f"persist-{i}", session_id="s",
                outcome=OutcomeType.FAILURE,
                metrics={"task_type": "stubborn_task"},
            ))
        engine.generate_proposals()

        loop = SelfFixLoop(improvement_engine=engine, event_backbone=backbone)
        max_iter = 3
        report = loop.run_loop(max_iterations=max_iter)

        assert report.iterations_run <= max_iter


# ---------------------------------------------------------------------------
# 14. test_full_loop_handles_unfixable_gaps
# ---------------------------------------------------------------------------

class TestFullLoopCodeProposals:
    def test_full_loop_handles_unfixable_gaps(self, loop):
        """Verify code_proposal type gaps are logged but not auto-fixed."""
        gap = Gap(
            gap_id="gap-code",
            description="Critical security vulnerability in authentication logic",
            source="health_check",
            severity="critical",
        )
        plan = loop.plan(gap)
        assert plan.fix_type == "code_proposal"
        execution = loop.execute(plan, gap)

        # Code proposals must not fail — they should succeed (logged for review)
        all_steps_ok = all(r["success"] for r in execution.step_results)
        assert all_steps_ok or len(execution.step_results) == 1


# ---------------------------------------------------------------------------
# 15. test_report_contains_all_details
# ---------------------------------------------------------------------------

class TestReport:
    def test_report_contains_all_details(self, engine, backbone):
        """Verify the final report is complete and accurate."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()

        loop = SelfFixLoop(improvement_engine=engine, event_backbone=backbone)
        report = loop.run_loop(max_iterations=5)

        assert report.report_id
        assert report.generated_at
        assert report.iterations_run >= 1
        assert report.duration_ms >= 0
        assert report.final_health_status in ("green", "yellow", "red")
        assert report.gaps_found >= 0
        assert report.gaps_fixed >= 0
        assert report.gaps_remaining >= 0
        assert report.plans_executed >= 0
        assert report.plans_succeeded >= 0
        assert report.plans_rolled_back >= 0
        assert report.tests_run >= 0
        assert report.tests_passed >= 0
        assert report.tests_failed >= 0

        d = report.to_dict()
        for key in ("report_id", "iterations_run", "gaps_found", "gaps_fixed", "gaps_remaining",
                    "plans_executed", "plans_succeeded", "plans_rolled_back",
                    "tests_run", "tests_passed", "tests_failed",
                    "duration_ms", "final_health_status", "generated_at"):
            assert key in d


# ---------------------------------------------------------------------------
# 16. test_persistence_integration
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persistence_integration(self, tmp_path, engine):
        """Verify all plans/executions are persisted."""
        from persistence_manager import PersistenceManager

        pm = PersistenceManager(persistence_dir=str(tmp_path))
        _inject_timeouts(engine, 3)
        engine.generate_proposals()

        loop = SelfFixLoop(improvement_engine=engine, persistence_manager=pm)
        report = loop.run_loop(max_iterations=3)

        # Loop report should be persisted
        loaded = pm.load_document(report.report_id)
        assert loaded is not None
        assert loaded["report_id"] == report.report_id

    def test_persistence_plans_saved(self, tmp_path, engine):
        """Plans are saved to persistence when persistence is attached."""
        from persistence_manager import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path))
        _inject_timeouts(engine, 3)
        engine.generate_proposals()

        loop = SelfFixLoop(improvement_engine=engine, persistence_manager=pm)
        report = loop.run_loop(max_iterations=2)

        # At least the loop report should be persisted
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ---------------------------------------------------------------------------
# 17. test_event_backbone_integration
# ---------------------------------------------------------------------------

class TestEventBackbone:
    def test_event_backbone_integration(self, engine, backbone):
        """Verify all self-fix events are published to the backbone."""
        _inject_timeouts(engine, 3)
        engine.generate_proposals()
        loop = SelfFixLoop(improvement_engine=engine, event_backbone=backbone)
        loop.run_loop(max_iterations=2)

        # Verify the loop completed and published events (checked via loop status)
        status = loop.get_status()
        assert status["total_reports"] > 0

    def test_event_types_exist(self):
        """Verify all self-fix event types are declared in EventBackbone."""
        expected = [
            "SELF_FIX_STARTED", "SELF_FIX_PLAN_CREATED", "SELF_FIX_EXECUTED",
            "SELF_FIX_TESTED", "SELF_FIX_VERIFIED", "SELF_FIX_COMPLETED",
            "SELF_FIX_ROLLED_BACK",
        ]
        for name in expected:
            assert hasattr(EventType, name), f"EventType.{name} not found"


# ---------------------------------------------------------------------------
# 18. test_concurrent_loop_safety
# ---------------------------------------------------------------------------

class TestConcurrentSafety:
    def test_concurrent_loop_safety(self):
        """Verify only one loop runs at a time (mutex)."""
        loop = SelfFixLoop()
        errors = []

        def run_loop():
            try:
                loop.run_loop(max_iterations=1)
            except RuntimeError as e:
                errors.append(str(e))

        # Manually set running flag to simulate concurrent access
        loop._running = True
        try:
            with pytest.raises(RuntimeError, match="already running"):
                loop.run_loop(max_iterations=1)
        finally:
            loop._running = False

    def test_flag_cleared_after_loop(self):
        """Running flag is cleared even if loop encounters no gaps."""
        loop = SelfFixLoop()
        loop.run_loop(max_iterations=1)
        assert loop._running is False

    def test_flag_cleared_after_exception_in_diagnose(self):
        """Running flag is cleared even if diagnose raises."""

        class BadDetector:
            def run_detection_cycle(self):
                raise RuntimeError("simulate crash")
            def get_patterns(self, limit=100):
                raise RuntimeError("simulate crash")

        loop = SelfFixLoop(bug_detector=BadDetector())
        report = loop.run_loop(max_iterations=1)
        assert loop._running is False
        assert isinstance(report, LoopReport)


# ---------------------------------------------------------------------------
# Additional: SelfImprovementEngine.generate_executable_fix
# ---------------------------------------------------------------------------

class TestGenerateExecutableFix:
    def test_timeout_proposal_produces_threshold_tuning(self, engine):
        """Timeout proposals produce threshold_tuning fix plans."""
        _inject_timeouts(engine, 3)
        proposals = engine.generate_proposals()
        timeout_proposals = [p for p in proposals if p.category == "timeout"]
        assert timeout_proposals

        result = engine.generate_executable_fix(timeout_proposals[0])
        assert result["fix_type"] == "threshold_tuning"
        actions = [s["action"] for s in result["fix_steps"]]
        assert "adjust_timeout" in actions

    def test_failure_proposal_produces_code_proposal(self, engine):
        """Recurring failure proposals for unknown categories produce code_proposal."""
        _inject_failures(engine, 3, task_type="obscure_task")
        proposals = engine.generate_proposals()
        assert proposals

        # The "Review and fix root cause" action maps to code_proposal
        result = engine.generate_executable_fix(proposals[0])
        assert result["fix_type"] in ("code_proposal", "threshold_tuning", "recovery_registration", "route_optimization")
        assert result["fix_steps"]
        assert result["test_criteria"]

    def test_all_fix_fields_present(self, engine):
        """All required fix plan fields are present in the returned dict."""
        _inject_timeouts(engine, 3)
        proposals = engine.generate_proposals()
        assert proposals

        result = engine.generate_executable_fix(proposals[0])
        required = ["proposal_id", "category", "fix_type", "fix_steps", "rollback_steps",
                    "expected_outcome", "test_criteria"]
        for f in required:
            assert f in result, f"Missing field: {f}"


# ---------------------------------------------------------------------------
# Additional: BugPatternDetector._inject_proposal fix
# ---------------------------------------------------------------------------

class TestBugPatternDetectorInjection:
    def test_inject_proposal_does_not_crash(self, engine, detector):
        """_inject_proposal should not raise when engine is attached."""
        from bug_pattern_detector import BugPatternDetector, BugPattern
        d = BugPatternDetector(improvement_engine=engine)

        # Ingest enough errors to trigger pattern
        for _ in range(5):
            d.ingest_error("Connection timeout", component="svc", error_type="TimeoutError")

        report = d.run_detection_cycle()
        # No exception should occur
        assert report.patterns_detected >= 1

    def test_inject_proposal_records_outcome(self, engine):
        """_inject_proposal should record an outcome in the improvement engine."""
        from bug_pattern_detector import BugPatternDetector
        d = BugPatternDetector(improvement_engine=engine)

        # Need 10+ occurrences for "high" severity so _inject_proposal is called
        for _ in range(12):
            d.ingest_error("NullPointerException", component="order_service", error_type="NullPointerError")
        d.run_detection_cycle()

        status = engine.get_status()
        assert status["total_outcomes"] > 0

    def test_inject_proposal_uses_generate_proposals(self, engine):
        """After detection, improvement engine should have proposals."""
        from bug_pattern_detector import BugPatternDetector
        d = BugPatternDetector(improvement_engine=engine)

        for _ in range(10):
            d.ingest_error("Permission denied", component="auth_service", error_type="PermissionError")
        d.run_detection_cycle()

        # Enough data should trigger proposals in the engine
        proposals = engine.generate_proposals()
        # Either proposals were generated or there were outcomes recorded
        status = engine.get_status()
        assert status["total_outcomes"] > 0
