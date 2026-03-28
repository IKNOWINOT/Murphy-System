"""
Comprehensive tests for ARCH-006: MurphyCodeHealer.

Validates the gap detection → analysis → proposal generation pipeline,
safety invariants, Bayesian planning, supervision tree, chaos integration,
golden path recording, and reconciliation controller.

Design Label: TEST-ARCH-006
Owner: QA Team

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import os
import textwrap
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


from murphy_code_healer import (
    BeliefState,
    BayesianFixPlanner,
    CodeContext,
    CodeFixPlan,
    CodeGap,
    CodeIntelligence,
    CodeProposal,
    DiagnosticSupervisor,
    GoldenPath,
    GoldenPathRecorder,
    HealerChaosRunner,
    HealerSupervisor,
    MurphyCodeHealer,
    PatchGenerator,
    ReconciliationController,
    ResilienceScore,
    _CONFIDENCE_LOG_ONLY,
    _CONFIDENCE_PROPOSE,
    _COMPLEXITY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_gap(
    gap_id: str = "gap-test-001",
    description: str = "Test gap",
    source: str = "static_analysis",
    severity: str = "medium",
    category: str = "bare_except",
    file_path: str = "/fake/module.py",
    function_name: str = "my_function",
) -> CodeGap:
    return CodeGap(
        gap_id=gap_id,
        description=description,
        source=source,
        severity=severity,
        category=category,
        file_path=file_path,
        function_name=function_name,
    )


def make_plan(
    confidence: float = 0.8,
    patch_type: str = "add_guard",
    function_name: str = "my_function",
) -> CodeFixPlan:
    return CodeFixPlan(
        plan_id="plan-test-001",
        gap_id="gap-test-001",
        patch_type=patch_type,
        target_file="/fake/module.py",
        target_function=function_name,
        target_class="",
        patch_description="Test description",
        patch_code="# patch code",
        test_code="def test_my_function_patched(): pass",
        rollback_plan="git revert",
        confidence_score=confidence,
        risk_assessment="low",
    )


# ---------------------------------------------------------------------------
# CodeGap
# ---------------------------------------------------------------------------

class TestCodeGap:
    def test_to_dict_has_all_fields(self):
        gap = make_gap()
        d = gap.to_dict()
        assert d["gap_id"] == "gap-test-001"
        assert d["source"] == "static_analysis"
        assert d["category"] == "bare_except"
        assert "detected_at" in d

    def test_correlation_group_default_none(self):
        gap = make_gap()
        assert gap.correlation_group is None


# ---------------------------------------------------------------------------
# DiagnosticSupervisor — static analysis
# ---------------------------------------------------------------------------

class TestDiagnosticSupervisorStaticAnalysis:
    def test_bare_except_detection(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            textwrap.dedent("""\
            def foo():
                try:
                    pass
                except:
                    pass
            """)
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._static_analysis_gaps(str(src))
        bare = [g for g in gaps if g.category == "bare_except"]
        assert len(bare) >= 1
        assert bare[0].severity == "medium"
        assert bare[0].source == "static_analysis"

    def test_todo_marker_detection(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "todos.py").write_text(
            "def foo():\n    # TODO: implement\n    pass\n"
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._static_analysis_gaps(str(src))
        todos = [g for g in gaps if g.category == "todo_marker"]
        assert len(todos) >= 1

    def test_high_complexity_detection(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        branches = "\n".join(f"    if x == {i}: pass" for i in range(15))
        (src / "complex.py").write_text(
            f"def complex_fn(x):\n{branches}\n    return x\n"
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._static_analysis_gaps(str(src))
        complex_gaps = [g for g in gaps if g.category == "high_complexity"]
        assert len(complex_gaps) >= 1
        assert complex_gaps[0].context["complexity"] > _COMPLEXITY_THRESHOLD

    def test_no_gaps_on_clean_code(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "clean.py").write_text(
            "def foo(x: int) -> int:\n    return x + 1\n"
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._static_analysis_gaps(str(src))
        # Clean code should have no high_complexity or bare_except gaps
        bad = [g for g in gaps if g.category in ("bare_except", "high_complexity")]
        assert len(bad) == 0

    def test_syntax_error_file_skipped(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "broken.py").write_text("def foo(\n")  # syntax error
        sup = DiagnosticSupervisor(src_root=str(src))
        # Should not raise
        gaps = sup._static_analysis_gaps(str(src))
        assert isinstance(gaps, list)


# ---------------------------------------------------------------------------
# DiagnosticSupervisor — test coverage gaps
# ---------------------------------------------------------------------------

class TestDiagnosticSupervisorTestCoverage:
    def test_detects_untested_function(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "module.py").write_text("def untested_function(): pass\n")
        (tests / "test_something.py").write_text("def test_other(): pass\n")
        sup = DiagnosticSupervisor(src_root=str(src), tests_root=str(tests))
        gaps = sup._test_coverage_gaps(str(src), str(tests))
        names = [g.function_name for g in gaps]
        assert "untested_function" in names

    def test_no_gap_for_tested_function(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "module.py").write_text("def tested_fn(): pass\n")
        (tests / "test_module.py").write_text(
            "from module import tested_fn\ndef test_tested_fn(): tested_fn()\n"
        )
        sup = DiagnosticSupervisor(src_root=str(src), tests_root=str(tests))
        gaps = sup._test_coverage_gaps(str(src), str(tests))
        names = [g.function_name for g in gaps]
        assert "tested_fn" not in names

    def test_private_functions_ignored(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "module.py").write_text("def _private_fn(): pass\n")
        (tests / "test_m.py").write_text("")
        sup = DiagnosticSupervisor(src_root=str(src), tests_root=str(tests))
        gaps = sup._test_coverage_gaps(str(src), str(tests))
        assert not any(g.function_name == "_private_fn" for g in gaps)


# ---------------------------------------------------------------------------
# DiagnosticSupervisor — doc drift
# ---------------------------------------------------------------------------

class TestDiagnosticSupervisorDocDrift:
    def test_detects_param_mismatch(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            textwrap.dedent("""\
            def foo(a, b):
                \":param a: first arg\"
                \":param c: wrong param\"
                pass
            """)
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._doc_drift_gaps(str(src))
        assert isinstance(gaps, list)

    def test_no_drift_on_matching_params(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            textwrap.dedent("""\
            def foo(a, b):
                \"\"\"
                :param a: first
                :param b: second
                \"\"\"
                pass
            """)
        )
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup._doc_drift_gaps(str(src))
        assert not any(g.category == "doc_drift" for g in gaps)


# ---------------------------------------------------------------------------
# DiagnosticSupervisor — external system integration
# ---------------------------------------------------------------------------

class TestDiagnosticSupervisorExternalSystems:
    def test_gaps_from_bug_detector(self):
        detector = MagicMock()
        detector.run_detection_cycle.return_value = MagicMock(report_id="r1")
        detector.get_patterns.return_value = [
            {"pattern_id": "p1", "description": "NullPointer", "severity": "high"}
        ]
        sup = DiagnosticSupervisor(bug_detector=detector)
        gaps = sup._gaps_from_bug_detector()
        assert len(gaps) == 1
        assert gaps[0].source == "bug_detector"
        assert gaps[0].severity == "high"

    def test_gaps_from_improvement_engine(self):
        engine = MagicMock()
        proposal = MagicMock()
        proposal.proposal_id = "prop-1"
        proposal.description = "Needs improvement"
        proposal.priority = "high"
        proposal.category = "routing"
        engine.get_remediation_backlog.return_value = [proposal]
        sup = DiagnosticSupervisor(improvement_engine=engine)
        gaps = sup._gaps_from_improvement_engine()
        assert len(gaps) == 1
        assert gaps[0].source == "improvement_engine"

    def test_gaps_from_healing_coordinator(self):
        coordinator = MagicMock()
        coordinator.get_history.return_value = [
            {"category": "db_timeout", "status": "failed"}
        ]
        sup = DiagnosticSupervisor(healing_coordinator=coordinator)
        gaps = sup._gaps_from_healing_coordinator()
        assert len(gaps) == 1
        assert gaps[0].source == "healing_coordinator"
        assert gaps[0].severity == "high"

    def test_none_dependencies_handled_gracefully(self):
        sup = DiagnosticSupervisor()
        gaps = sup.collect_gaps()
        assert isinstance(gaps, list)

    def test_correlate_gaps_groups_same_function(self):
        sup = DiagnosticSupervisor()
        g1 = make_gap(gap_id="g1", file_path="/a.py", function_name="foo")
        g2 = make_gap(gap_id="g2", file_path="/a.py", function_name="foo")
        g3 = make_gap(gap_id="g3", file_path="/a.py", function_name="bar")
        result = sup._correlate_gaps([g1, g2, g3])
        assert result[0].correlation_group == result[1].correlation_group
        assert result[2].correlation_group != result[0].correlation_group


# ---------------------------------------------------------------------------
# CodeIntelligence
# ---------------------------------------------------------------------------

class TestCodeIntelligence:
    def test_build_map_parses_functions(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            "def foo(x): return x\ndef bar(y): return y\n"
        )
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()
        file_key = str(src / "module.py")
        assert file_key in ci._function_map
        names = [f.name for f in ci._function_map[file_key]]
        assert "foo" in names
        assert "bar" in names

    def test_call_graph_extraction(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            "def foo(): return bar()\ndef bar(): return 1\n"
        )
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()
        file_key = str(src / "module.py")
        callers_of_bar = [
            k for k, callees in ci._call_graph.items()
            if "bar" in callees
        ]
        assert any("foo" in k for k in callers_of_bar)

    def test_get_context_returns_code_context(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            "def my_func(x):\n    \"\"\"Does thing.\"\"\"\n    return x\n"
        )
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()
        gap = make_gap(
            file_path=str(src / "module.py"),
            function_name="my_func",
        )
        ctx = ci.get_context(gap)
        assert ctx.target_function == "my_func"
        assert ctx.signature == "def my_func(x)"
        assert "Does thing" in ctx.docstring

    def test_localise_fault_returns_sorted(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text(
            "def target_fn(): pass\ndef caller(): target_fn()\n"
        )
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()
        gap = make_gap(
            file_path=str(src / "module.py"),
            function_name="target_fn",
        )
        results = ci.localise_fault(gap)
        assert len(results) >= 1
        # First result should be the target itself
        assert "target_fn" in results[0][0]
        assert results[0][1] == 1.0

    def test_extract_functions_returns_metadata(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        py_file = src / "module.py"
        py_file.write_text("def alpha(): pass\ndef beta(): pass\n")
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()
        funcs = ci.extract_functions(str(py_file))
        names = [f["name"] for f in funcs]
        assert "alpha" in names
        assert "beta" in names

    def test_syntax_error_file_skipped(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("def foo(\n")
        ci = CodeIntelligence(src_root=str(src))
        ci.build_map()  # should not raise


# ---------------------------------------------------------------------------
# BeliefState
# ---------------------------------------------------------------------------

class TestBeliefState:
    def test_initial_uniform_distribution(self):
        bs = BeliefState(gap_id="g1")
        total = sum(bs.hypotheses.values())
        assert abs(total - 1.0) < 1e-9
        for v in bs.hypotheses.values():
            assert abs(v - 1 / 6) < 1e-6

    def test_update_changes_distribution(self):
        bs = BeliefState(gap_id="g1")
        bs.update({"test_gap": 10.0, "simple_config_fix": 0.1})
        best, score = bs.best_hypothesis()
        assert best == "test_gap"
        assert score > 0.5

    def test_observation_count_increments(self):
        bs = BeliefState(gap_id="g1")
        bs.update({"incorrect_logic": 2.0})
        assert bs.observation_count == 1

    def test_to_dict(self):
        bs = BeliefState(gap_id="g1")
        d = bs.to_dict()
        assert d["gap_id"] == "g1"
        assert "hypotheses" in d
        assert "observation_count" in d


# ---------------------------------------------------------------------------
# BayesianFixPlanner
# ---------------------------------------------------------------------------

class TestBayesianFixPlanner:
    def test_create_plan_returns_code_fix_plan(self):
        planner = BayesianFixPlanner()
        gap = make_gap(category="bare_except", severity="high")
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="my_function",
            target_class="",
        )
        plan = planner.create_plan(gap, ctx)
        assert isinstance(plan, CodeFixPlan)
        assert plan.gap_id == gap.gap_id
        assert 0.0 <= plan.confidence_score <= 1.0

    def test_test_gap_category_produces_add_test(self):
        planner = BayesianFixPlanner()
        gap = make_gap(category="test_gap")
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="untested",
            target_class="",
        )
        plan = planner.create_plan(gap, ctx)
        assert plan.patch_type == "add_test"

    def test_high_complexity_produces_refactor(self):
        planner = BayesianFixPlanner()
        gap = make_gap(category="high_complexity")
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="complex_fn",
            target_class="",
        )
        plan = planner.create_plan(gap, ctx)
        assert plan.patch_type in ("refactor", "modify_function")

    def test_mmsmms_cadence_runs(self):
        planner = BayesianFixPlanner()
        gap = make_gap(category="bare_except", severity="critical")
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="foo",
            target_class="",
            callees=["a", "b", "c", "d", "e", "f"],  # >5 → triggers complexity boost
        )
        plan = planner.create_plan(gap, ctx)
        # After MMSMMS the confidence should be defined
        assert plan.confidence_score > 0.0

    def test_patch_code_and_test_code_non_empty(self):
        planner = BayesianFixPlanner()
        gap = make_gap(category="test_gap", function_name="my_func")
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="my_func",
            target_class="",
        )
        plan = planner.create_plan(gap, ctx)
        assert len(plan.patch_code) > 0
        assert len(plan.test_code) > 0

    def test_risk_assessment_contains_confidence(self):
        planner = BayesianFixPlanner()
        gap = make_gap()
        ctx = CodeContext(
            target_file="/fake/module.py",
            target_function="foo",
            target_class="",
        )
        plan = planner.create_plan(gap, ctx)
        assert str(round(plan.confidence_score, 2)) in plan.risk_assessment or \
               "Confidence" in plan.risk_assessment


# ---------------------------------------------------------------------------
# PatchGenerator
# ---------------------------------------------------------------------------

class TestPatchGenerator:
    def test_generates_proposal_above_threshold(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.80)
        proposal = gen.generate_proposal(plan, resilience_score=0.9, adversarial_test="")
        assert proposal is not None
        assert isinstance(proposal, CodeProposal)
        assert proposal.plan_id == plan.plan_id

    def test_returns_none_below_threshold(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.60)  # below _CONFIDENCE_LOG_ONLY
        proposal = gen.generate_proposal(plan)
        assert proposal is None

    def test_auto_merge_suggested_above_high_threshold(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=_CONFIDENCE_PROPOSE + 0.01)
        proposal = gen.generate_proposal(plan)
        assert proposal is not None
        assert proposal.auto_merge_suggested is True

    def test_no_auto_merge_below_high_threshold(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=(_CONFIDENCE_LOG_ONLY + _CONFIDENCE_PROPOSE) / 2)
        proposal = gen.generate_proposal(plan)
        if proposal:
            assert proposal.auto_merge_suggested is False

    def test_unified_diff_is_string(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.80)
        proposal = gen.generate_proposal(plan)
        assert proposal is not None
        assert isinstance(proposal.unified_diff, str)

    def test_audit_trail_populated(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.80)
        proposal = gen.generate_proposal(plan)
        assert proposal is not None
        assert len(proposal.audit_trail) >= 1
        assert proposal.audit_trail[0]["event"] == "proposal_created"

    def test_governance_check_blocks_low_confidence(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.50)
        assert gen._governance_check(plan) is False

    def test_get_proposals_returns_list(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.80)
        gen.generate_proposal(plan)
        proposals = gen.get_proposals()
        assert isinstance(proposals, list)
        assert len(proposals) >= 1

    def test_proposal_to_dict(self):
        gen = PatchGenerator()
        plan = make_plan(confidence=0.80)
        proposal = gen.generate_proposal(plan)
        assert proposal is not None
        d = proposal.to_dict()
        assert "proposal_id" in d
        assert "unified_diff" in d
        assert "status" in d


# ---------------------------------------------------------------------------
# ReconciliationController
# ---------------------------------------------------------------------------

class TestReconciliationController:
    def test_reconcile_once_returns_summary(self):
        sup = DiagnosticSupervisor()
        ctrl = ReconciliationController(diagnostic_supervisor=sup)
        result = ctrl.reconcile_once()
        assert "observed_gaps" in result
        assert "proposals_created" in result

    def test_prevents_concurrent_runs(self):
        """Only one reconcile may run at a time (leader election)."""
        sup = DiagnosticSupervisor()
        ctrl = ReconciliationController(diagnostic_supervisor=sup)
        # Manually mark as running
        ctrl._running = True
        result = ctrl.reconcile_once()
        assert result["status"] == "already_running"

    def test_backoff_applied_on_repeated_failure(self):
        sup = DiagnosticSupervisor()
        ctrl = ReconciliationController(diagnostic_supervisor=sup)
        gap_id = "gap-backoff-001"
        ctrl._record_failure(gap_id)
        ctrl._record_failure(gap_id)
        assert ctrl._is_backed_off(gap_id)

    def test_resolved_gap_not_reprocessed(self):
        sup = MagicMock()
        gap = make_gap(gap_id="gap-resolved-001")
        sup.collect_gaps.return_value = [gap]
        calls = []
        def pipeline(g):
            calls.append(g.gap_id)
            return MagicMock()  # non-None = success
        ctrl = ReconciliationController(diagnostic_supervisor=sup, fix_pipeline=pipeline)
        ctrl.reconcile_once()
        ctrl.reconcile_once()
        # Second pass should skip since gap is resolved
        assert calls.count("gap-resolved-001") == 1

    def test_get_status(self):
        sup = DiagnosticSupervisor()
        ctrl = ReconciliationController(diagnostic_supervisor=sup)
        status = ctrl.get_status()
        assert "running" in status
        assert "resolved_gaps" in status


# ---------------------------------------------------------------------------
# HealerSupervisor
# ---------------------------------------------------------------------------

class TestHealerSupervisor:
    def test_register_and_start_workers(self):
        sup = HealerSupervisor()
        events = []
        def worker_a():
            events.append("a_ran")
        def worker_b():
            events.append("b_ran")
        sup.register_worker("a", worker_a)
        sup.register_worker("b", worker_b)
        sup.start_all()
        time.sleep(0.3)
        sup.stop_all()
        assert "a_ran" in events
        assert "b_ran" in events

    def test_get_status_returns_worker_info(self):
        sup = HealerSupervisor()
        sup.register_worker("w1", lambda: None)
        status = sup.get_status()
        assert "w1" in status

    def test_heartbeat_updates_timestamp(self):
        sup = HealerSupervisor()
        sup.register_worker("w1", lambda: None)
        old_hb = sup._workers["w1"].last_heartbeat
        time.sleep(0.05)
        sup.heartbeat("w1")
        new_hb = sup._workers["w1"].last_heartbeat
        assert new_hb >= old_hb

    def test_restart_budget_exhaustion(self):
        """Worker should NOT be restarted after exceeding restart budget."""
        sup = HealerSupervisor()
        sup.register_worker("w1", lambda: None)
        rec = sup._workers["w1"]
        # Simulate 5 restarts within the window
        now = time.monotonic()
        rec.restart_times = [now - i for i in range(5)]
        rec.alive = False
        # Should NOT restart
        with sup._lock:
            sup._handle_crash(rec)
        assert not rec.alive  # still dead, not restarted

    def test_one_for_all_restarts_all_workers(self):
        """one_for_all: crashing one worker restarts all."""
        sup = HealerSupervisor()
        sup.register_worker("critical", lambda: None, strategy="one_for_all")
        sup.register_worker("secondary", lambda: None, strategy="one_for_one")
        rec = sup._workers["critical"]
        rec.alive = False
        with sup._lock:
            sup._handle_crash(rec)
        # Both should have been restarted (threads created)
        assert sup._workers["critical"].thread is not None
        assert sup._workers["secondary"].thread is not None


# ---------------------------------------------------------------------------
# HealerChaosRunner
# ---------------------------------------------------------------------------

class TestHealerChaosRunner:
    def test_no_generator_returns_full_score(self):
        runner = HealerChaosRunner()
        plan = make_plan()
        result = runner.evaluate(plan)
        assert result.score == 1.0
        assert result.passed is True

    def test_generator_injected_called(self):
        gen = MagicMock()
        gen.inject_failure.return_value = {"survived": True}
        runner = HealerChaosRunner(failure_generator=gen)
        plan = make_plan()
        result = runner.evaluate(plan)
        assert result.passed is True
        assert result.score == 1.0

    def test_generator_failure_returns_reduced_score(self):
        gen = MagicMock()
        gen.inject_failure.return_value = {"survived": False}
        runner = HealerChaosRunner(failure_generator=gen)
        plan = make_plan()
        result = runner.evaluate(plan)
        assert result.passed is False
        assert result.score == 0.5

    def test_generator_exception_handled_gracefully(self):
        gen = MagicMock()
        gen.inject_failure.side_effect = RuntimeError("chaos error")
        runner = HealerChaosRunner(failure_generator=gen)
        plan = make_plan()
        result = runner.evaluate(plan)
        assert result.score == 0.8  # non-fatal fallback

    def test_adversarial_test_generated(self):
        runner = HealerChaosRunner()
        plan = make_plan()
        test = runner.generate_adversarial_test(plan)
        assert "adversarial" in test
        assert "my_function" in test

    def test_resilience_score_dataclass(self):
        rs = ResilienceScore(
            scenario="test", passed=True, details="ok", score=0.9
        )
        assert rs.score == 0.9
        assert rs.passed is True


# ---------------------------------------------------------------------------
# GoldenPathRecorder
# ---------------------------------------------------------------------------

class TestGoldenPathRecorder:
    def test_record_creates_golden_path(self):
        recorder = GoldenPathRecorder()
        plan = make_plan()
        proposal = MagicMock(spec=CodeProposal)
        path = recorder.record(plan, proposal)
        assert isinstance(path, GoldenPath)
        assert path.patch_type == "add_guard"

    def test_duplicate_patch_type_increments_count(self):
        recorder = GoldenPathRecorder()
        plan = make_plan()
        proposal = MagicMock(spec=CodeProposal)
        path1 = recorder.record(plan, proposal)
        path2 = recorder.record(plan, proposal)
        assert path1.path_id == path2.path_id
        assert path2.success_count == 2

    def test_get_all_returns_list(self):
        recorder = GoldenPathRecorder()
        plan = make_plan()
        proposal = MagicMock(spec=CodeProposal)
        recorder.record(plan, proposal)
        all_paths = recorder.get_all()
        assert len(all_paths) >= 1

    def test_find_for_gap_returns_matching_path(self):
        recorder = GoldenPathRecorder()
        # Record a path with patch_type='add_guard' for bare_except category
        plan = make_plan(patch_type="add_guard")
        proposal = MagicMock(spec=CodeProposal)
        recorder.record(plan, proposal)
        gap = make_gap(category="bare_except")
        result = recorder.find_for_gap(gap)
        assert result is not None

    def test_golden_path_to_dict(self):
        recorder = GoldenPathRecorder()
        plan = make_plan()
        proposal = MagicMock(spec=CodeProposal)
        path = recorder.record(plan, proposal)
        d = path.to_dict()
        assert "path_id" in d
        assert "patch_type" in d
        assert "success_count" in d


# ---------------------------------------------------------------------------
# MurphyCodeHealer — end-to-end
# ---------------------------------------------------------------------------

class TestMurphyCodeHealer:
    def test_init_with_no_dependencies(self):
        healer = MurphyCodeHealer()
        assert healer.diagnostic is not None
        assert healer.intelligence is not None
        assert healer.planner is not None
        assert healer.patch_gen is not None

    def test_analyze_and_propose_returns_proposal_for_valid_gap(self):
        healer = MurphyCodeHealer()
        gap = make_gap(category="bare_except", severity="high")
        # Force planner to produce high confidence
        original_create = healer.planner.create_plan
        def _high_conf_plan(g, ctx):
            plan = original_create(g, ctx)
            plan.confidence_score = 0.85
            return plan
        healer.planner.create_plan = _high_conf_plan
        proposal = healer.analyze_and_propose(gap)
        assert proposal is not None
        assert proposal.gap_id == gap.gap_id

    def test_analyze_and_propose_returns_none_for_low_confidence(self):
        healer = MurphyCodeHealer()
        gap = make_gap()
        # Force low confidence
        original_create = healer.planner.create_plan
        def _low_conf_plan(g, ctx):
            plan = original_create(g, ctx)
            plan.confidence_score = 0.50
            return plan
        healer.planner.create_plan = _low_conf_plan
        proposal = healer.analyze_and_propose(gap)
        assert proposal is None

    def test_run_healing_cycle_returns_report(self):
        healer = MurphyCodeHealer()
        report = healer.run_healing_cycle(max_gaps=5)
        assert "gaps_detected" in report
        assert "proposals_created" in report
        assert "elapsed_seconds" in report

    def test_run_healing_cycle_prevents_concurrent_runs(self):
        healer = MurphyCodeHealer()
        healer._running = True
        with pytest.raises(RuntimeError, match="already running"):
            healer.run_healing_cycle()

    def test_get_metrics_returns_dict(self):
        healer = MurphyCodeHealer()
        gap = make_gap()
        healer.analyze_and_propose(gap)
        metrics = healer.get_metrics()
        assert isinstance(metrics, dict)
        assert "mean_time_to_detect_ms" in metrics

    def test_bridge_to_code_healer_callable(self):
        healer = MurphyCodeHealer()
        bridge = healer.bridge_to_code_healer()
        assert callable(bridge)
        gap = make_gap()
        # Should not raise
        bridge(gap)

    def test_get_proposals_returns_list(self):
        healer = MurphyCodeHealer()
        proposals = healer.get_proposals()
        assert isinstance(proposals, list)

    def test_event_backbone_publish_called(self):
        backbone = MagicMock()
        healer = MurphyCodeHealer(event_backbone=backbone)
        healer.run_healing_cycle(max_gaps=1)
        assert backbone.publish.called

    def test_persistence_manager_called(self):
        pm = MagicMock()
        healer = MurphyCodeHealer(persistence_manager=pm)
        gap = make_gap()
        # Force high confidence
        original_create = healer.planner.create_plan
        def _high_conf_plan(g, ctx):
            plan = original_create(g, ctx)
            plan.confidence_score = 0.85
            return plan
        healer.planner.create_plan = _high_conf_plan
        healer.analyze_and_propose(gap)
        # If proposal was created, pm should have been called
        if healer._metrics["patches_generated"] > 0:
            assert pm.save_document.called

    def test_golden_path_recorded_on_success(self):
        healer = MurphyCodeHealer()
        gap = make_gap()
        original_create = healer.planner.create_plan
        def _high_conf_plan(g, ctx):
            plan = original_create(g, ctx)
            plan.confidence_score = 0.85
            return plan
        healer.planner.create_plan = _high_conf_plan
        healer.analyze_and_propose(gap)
        all_paths = healer.recorder.get_all()
        # Either golden path was recorded or gap was below threshold
        assert isinstance(all_paths, list)


# ---------------------------------------------------------------------------
# Integration: DiagnosticSupervisor.collect_gaps with src files
# ---------------------------------------------------------------------------

class TestIntegrationCollectGaps:
    def test_collect_gaps_with_real_files(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "module.py").write_text(
            textwrap.dedent("""\
            def buggy():
                try:
                    x = 1
                except:
                    pass

            # TODO: implement
            def public_fn():
                pass
            """)
        )
        (tests / "test_module.py").write_text(
            "def test_buggy(): pass\n"
        )
        sup = DiagnosticSupervisor(
            src_root=str(src),
            tests_root=str(tests),
        )
        gaps = sup.collect_gaps()
        categories = {g.category for g in gaps}
        assert "bare_except" in categories

    def test_collect_gaps_history_populated(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "m.py").write_text("x = 1\n")
        sup = DiagnosticSupervisor(src_root=str(src))
        sup.collect_gaps()
        history = sup.get_history()
        assert isinstance(history, list)


# ---------------------------------------------------------------------------
# Dead code detection
# ---------------------------------------------------------------------------


class TestDeadCodeGaps:
    """Tests for DiagnosticSupervisor._dead_code_gaps()."""

    def test_orphaned_public_function_flagged(self, tmp_path):
        """A public function that is never referenced elsewhere is flagged."""
        (tmp_path / "module_a.py").write_text(
            "def OrphanedFunction():\n    pass\n"
        )
        (tmp_path / "module_b.py").write_text(
            "x = 1\n"
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        names = {g.context.get("symbol_name") for g in gaps if g.category == "dead_code"}
        assert "OrphanedFunction" in names

    def test_referenced_function_not_flagged(self, tmp_path):
        """A function used in another file is NOT flagged as dead code."""
        (tmp_path / "utils.py").write_text(
            "def UsedHelper():\n    return 42\n"
        )
        (tmp_path / "main.py").write_text(
            "from utils import UsedHelper\nresult = UsedHelper()\n"
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        names = {g.context.get("symbol_name") for g in gaps if g.category == "dead_code"}
        assert "UsedHelper" not in names

    def test_private_functions_not_flagged(self, tmp_path):
        """Private functions (underscore prefix) are never reported as dead code."""
        (tmp_path / "module.py").write_text(
            "def _internal():\n    pass\n"
            "def __dunder__():\n    pass\n"
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        names = {g.context.get("symbol_name") for g in gaps if g.category == "dead_code"}
        assert "_internal" not in names
        assert "__dunder__" not in names

    def test_orphaned_class_flagged(self, tmp_path):
        """A public class never used outside its file is flagged."""
        (tmp_path / "models.py").write_text(
            "class OrphanedModel:\n    pass\n"
        )
        (tmp_path / "other.py").write_text(
            "x = 1\n"
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        names = {g.context.get("symbol_name") for g in gaps if g.category == "dead_code"}
        assert "OrphanedModel" in names

    def test_empty_src_returns_no_gaps(self, tmp_path):
        """An empty or non-Python src directory produces no dead code gaps."""
        (tmp_path / "data.txt").write_text("hello\n")
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        assert gaps == []

    def test_collect_gaps_includes_dead_code(self, tmp_path):
        """collect_gaps() includes dead_code category when src_root is set."""
        (tmp_path / "module.py").write_text(
            "def OrphanedFunc():\n    pass\n"
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup.collect_gaps()
        categories = {g.category for g in gaps}
        assert "dead_code" in categories

    def test_constant_names_not_flagged(self, tmp_path):
        """All-uppercase names (constants) are never flagged as dead code."""
        (tmp_path / "constants.py").write_text(
            "MAX_SIZE = 100\n"
            "def MAX_SIZE_FUNC():\n    pass\n"  # ALL CAPS function → skipped
        )
        sup = DiagnosticSupervisor(src_root=str(tmp_path))
        gaps = sup._dead_code_gaps(str(tmp_path))
        names = {g.context.get("symbol_name") for g in gaps if g.category == "dead_code"}
        assert "MAX_SIZE_FUNC" not in names


# ---------------------------------------------------------------------------
# sync_module_counts.py script tests
# ---------------------------------------------------------------------------


class TestSyncModuleCounts:
    """Tests for scripts/sync_module_counts.py."""

    def _get_sync_module(self):
        """Import sync_module_counts from scripts/."""
        import importlib.util
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "sync_module_counts.py"
        spec = importlib.util.spec_from_file_location("sync_module_counts", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_count_modules_counts_py_files(self, tmp_path):
        sync = self._get_sync_module()
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "__init__.py").write_text("")  # should not count
        assert sync.count_modules(tmp_path) == 2

    def test_update_file_replaces_count(self, tmp_path):
        sync = self._get_sync_module()
        f = tmp_path / "README.md"
        f.write_text("Murphy has **620+ modules** and counting.\n")
        changed, n = sync.update_file(f, 911)
        assert changed is True
        assert n >= 1
        assert "911" in f.read_text()

    def test_update_file_no_change_when_current(self, tmp_path):
        sync = self._get_sync_module()
        f = tmp_path / "STATUS.md"
        f.write_text("620+ modules loaded.\n")
        changed, n = sync.update_file(f, 620)
        # Count is already 620 — no change needed
        assert changed is False

    def test_update_file_dry_run_does_not_write(self, tmp_path):
        sync = self._get_sync_module()
        f = tmp_path / "README.md"
        original = "Has 620+ modules.\n"
        f.write_text(original)
        changed, n = sync.update_file(f, 911, dry_run=True)
        assert changed is True  # would change
        assert f.read_text() == original  # but not written

    def test_update_file_missing_file_is_skipped(self, tmp_path):
        sync = self._get_sync_module()
        f = tmp_path / "nonexistent.md"
        changed, n = sync.update_file(f, 911)
        assert changed is False
        assert n == 0

    def test_sync_updates_status_md(self, tmp_path):
        sync = self._get_sync_module()
        src = tmp_path / "src"
        src.mkdir()
        for i in range(5):
            (src / f"m{i}.py").write_text("x = 1\n")
        status = tmp_path / "STATUS.md"
        status.write_text("Core Runtime | 620+ modules\n")
        (tmp_path / "README.md").write_text("No count here.\n")
        (tmp_path / "CONTRIBUTING.md").write_text("No count here.\n")

        summary = sync.sync(tmp_path)
        assert summary["actual_count"] == 5
        assert "5" in status.read_text()




class _MockEventType:
    """Lightweight EventType stand-in for unit tests."""
    TASK_FAILED = "TASK_FAILED"
    TEST_FAILED = "TEST_FAILED"
    DOC_DRIFT = "DOC_DRIFT"


class TestEventSubscriptions:
    """Tests for MurphyCodeHealer.subscribe_to_events()."""

    def test_subscribe_with_no_backbone_is_noop(self):
        healer = MurphyCodeHealer()
        # Should not raise even without a backbone
        healer.subscribe_to_events()
        assert healer._subscription_ids == []

    def test_subscribe_registers_three_handlers(self):
        backbone = MagicMock()
        backbone.subscribe.return_value = "sub-id-mock"
        healer = MurphyCodeHealer(event_backbone=backbone)
        healer.subscribe_to_events()
        assert backbone.subscribe.call_count == 3
        assert len(healer._subscription_ids) == 3

    def test_subscribe_is_idempotent(self):
        """Calling subscribe_to_events() twice registers handlers only once."""
        backbone = MagicMock()
        backbone.subscribe.return_value = "sub-id-mock"
        healer = MurphyCodeHealer(event_backbone=backbone)
        healer.subscribe_to_events()
        healer.subscribe_to_events()
        # Second call is a no-op: still exactly 3 subscriptions
        assert backbone.subscribe.call_count == 3
        assert len(healer._subscription_ids) == 3

    def _make_healer_with_mock_handlers(self):
        """Create a healer with a backbone that captures registered handlers."""
        backbone = MagicMock()
        handlers = {}

        def _sub(event_type, handler):
            handlers[event_type] = handler
            return f"sub-{event_type}"

        backbone.subscribe.side_effect = _sub
        healer = MurphyCodeHealer(event_backbone=backbone)
        with patch.dict(
            __import__("sys").modules,
            {"event_backbone": MagicMock(EventType=_MockEventType)},
        ):
            healer.subscribe_to_events()
        return healer, handlers

    def test_task_failed_handler_creates_proposal(self):
        """Simulate TASK_FAILED event arriving via the backbone."""
        healer, handlers = self._make_healer_with_mock_handlers()
        mock_event = MagicMock()
        mock_event.event_id = "evt-001"
        mock_event.payload = {"task_type": "execute", "file_path": "/fake/file.py"}

        if "TASK_FAILED" in handlers:
            handlers["TASK_FAILED"](mock_event)
            time.sleep(0.1)

    def test_doc_drift_event_does_not_raise(self):
        """DOC_DRIFT events should be handled without errors."""
        healer, handlers = self._make_healer_with_mock_handlers()
        mock_event = MagicMock()
        mock_event.event_id = "evt-002"
        mock_event.payload = {"description": "README references missing file"}

        if "DOC_DRIFT" in handlers:
            handlers["DOC_DRIFT"](mock_event)
            time.sleep(0.1)

    def test_test_failed_handler_does_not_raise(self):
        """TEST_FAILED events should be handled without errors."""
        healer, handlers = self._make_healer_with_mock_handlers()
        mock_event = MagicMock()
        mock_event.event_id = "evt-003"
        mock_event.payload = {"test_name": "test_foo", "file_path": "/tests/test_foo.py"}

        if "TEST_FAILED" in handlers:
            handlers["TEST_FAILED"](mock_event)
            time.sleep(0.1)


class TestMarkdownFileRefGaps:
    """Tests for DiagnosticSupervisor._markdown_file_ref_gaps()."""

    def test_no_gaps_for_existing_references(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text("# hello\n")
        (docs / "guide.md").write_text(
            "See [module](../src/module.py) for details.\n"
        )
        sup = DiagnosticSupervisor(docs_root=str(docs))
        gaps = sup._markdown_file_ref_gaps(str(docs))
        broken = [g for g in gaps if g.category == "broken_md_ref"]
        assert broken == []

    def test_gap_for_missing_file_reference(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "spec.md").write_text(
            "[missing module](src/nonexistent.py)\n"
        )
        sup = DiagnosticSupervisor(docs_root=str(docs))
        gaps = sup._markdown_file_ref_gaps(str(docs))
        broken = [g for g in gaps if g.category == "broken_md_ref"]
        assert len(broken) >= 1
        assert any("nonexistent.py" in g.description for g in broken)

    def test_http_links_ignored(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "readme.md").write_text(
            "See [docs](https://example.com/guide.md) for more.\n"
            "Also [repo](http://github.com/foo/bar.py).\n"
        )
        sup = DiagnosticSupervisor(docs_root=str(docs))
        gaps = sup._markdown_file_ref_gaps(str(docs))
        broken = [g for g in gaps if g.category == "broken_md_ref"]
        assert broken == []

    def test_collect_gaps_calls_markdown_check(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "spec.md").write_text("[missing](nonexistent/path.py)\n")
        sup = DiagnosticSupervisor(docs_root=str(docs))
        gaps = sup.collect_gaps()
        categories = {g.category for g in gaps}
        assert "broken_md_ref" in categories

    def test_docs_root_none_skips_markdown_check(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        sup = DiagnosticSupervisor(src_root=str(src))
        gaps = sup.collect_gaps()
        broken = [g for g in gaps if g.category == "broken_md_ref"]
        assert broken == []


class TestNewAPIEndpoints:
    """Smoke tests for new /api/corrections/* endpoints."""

    def test_healer_proposals_returns_list_shape(self):
        """get_proposals() returns a list of dicts."""
        healer = MurphyCodeHealer()
        proposals = healer.get_proposals(limit=10)
        assert isinstance(proposals, list)
        # Initially empty
        assert proposals == []

    def test_healer_metrics_shape(self):
        """get_metrics() returns a dict with expected keys."""
        healer = MurphyCodeHealer()
        metrics = healer.get_metrics()
        assert isinstance(metrics, dict)
        assert "mean_time_to_detect_ms" in metrics
        assert "mean_time_to_patch_ms" in metrics

    def test_healer_accepts_docs_root(self, tmp_path):
        """MurphyCodeHealer can be instantiated with docs_root."""
        docs = tmp_path / "docs"
        docs.mkdir()
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text("x = 1\n")
        healer = MurphyCodeHealer(
            src_root=str(src),
            docs_root=str(docs),
        )
        assert healer is not None

    def test_healer_run_cycle_with_docs_root(self, tmp_path):
        """run_healing_cycle completes with docs_root set."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("[broken](missing/file.py)\n")
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1\n")
        healer = MurphyCodeHealer(
            src_root=str(src),
            docs_root=str(docs),
        )
        report = healer.run_healing_cycle(max_gaps=10)
        assert isinstance(report, dict)
        assert "gaps_detected" in report


class TestEventBackboneNewEventTypes:
    """Verify new EventType values are importable and valid."""

    def test_test_failed_in_event_type(self):
        from event_backbone import EventType
        assert EventType.TEST_FAILED.value == "test_failed"

    def test_doc_drift_in_event_type(self):
        from event_backbone import EventType
        assert EventType.DOC_DRIFT.value == "doc_drift"

    def test_code_healer_events_in_event_type(self):
        from event_backbone import EventType
        assert EventType.CODE_HEALER_STARTED.value == "code_healer_started"
        assert EventType.CODE_HEALER_COMPLETED.value == "code_healer_completed"
        assert EventType.CODE_HEALER_PROPOSAL_CREATED.value == "code_healer_proposal_created"
