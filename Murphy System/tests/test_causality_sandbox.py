"""
Tests for the CausalitySandboxEngine.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import uuid

import pytest


from causality_sandbox import (
    ActionRanking,
    AntibodyPattern,
    CandidateAction,
    CausalitySandboxEngine,
    SandboxReport,
    SimulationResult,
    SystemSnapshot,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

class _FakeGap:
    """Minimal stand-in for SelfFixLoop.Gap."""

    def __init__(
        self,
        gap_id: str = None,
        description: str = "timeout error in component",
        source: str = "health_check",
        severity: str = "medium",
        category: str = "timeout",
    ) -> None:
        self.gap_id = gap_id or str(uuid.uuid4())
        self.description = description
        self.source = source
        self.severity = severity
        self.category = category
        self.context = {}
        self.proposal_id = None
        self.pattern_id = None


class _FakeLoop:
    """Minimal stand-in for SelfFixLoop."""

    def __init__(self) -> None:
        self._runtime_config: dict = {"timeout_ms": 5000, "confidence_threshold": 0.7}
        self._recovery_procedures: dict = {}

    def get_status(self) -> dict:
        return {"health_status": "green"}

    def execute(self, plan: object) -> object:
        class _Exec:
            execution_id = str(uuid.uuid4())
            plan_id = getattr(plan, "plan_id", "")
            step_results: list = []
            tests_run: list = []
            gaps_before: list = []
            gaps_after: list = []
            regressions: list = []
            status = "success"
            duration_ms = 1.0
        return _Exec()

    def test(self, plan: object, execution: object) -> bool:
        return True

    def diagnose(self) -> list:
        return []


def _factory() -> _FakeLoop:
    return _FakeLoop()


@pytest.fixture()
def engine() -> CausalitySandboxEngine:
    return CausalitySandboxEngine(_factory, max_parallel_simulations=5, effectiveness_threshold=0.5)


@pytest.fixture()
def gap() -> _FakeGap:
    return _FakeGap()


# ---------------------------------------------------------------------------
# SystemSnapshot tests
# ---------------------------------------------------------------------------

class TestSystemSnapshot:
    def test_system_snapshot_capture_and_restore(self):
        """Snapshot round-trip preserves runtime_config state."""
        loop = _FakeLoop()
        loop._runtime_config = {"timeout_ms": 3000, "confidence_threshold": 0.8}

        snapshot = SystemSnapshot.capture(loop)

        assert snapshot.runtime_config == {"timeout_ms": 3000, "confidence_threshold": 0.8}
        assert snapshot.health_status == "green"

        # Mutate the loop
        loop._runtime_config["timeout_ms"] = 9999

        # Restore
        SystemSnapshot.restore(snapshot, loop)
        assert loop._runtime_config["timeout_ms"] == 3000

    def test_snapshot_has_unique_id(self):
        loop = _FakeLoop()
        s1 = SystemSnapshot.capture(loop)
        s2 = SystemSnapshot.capture(loop)
        assert s1.snapshot_id != s2.snapshot_id

    def test_snapshot_extracts_confidence_thresholds(self):
        loop = _FakeLoop()
        loop._runtime_config = {"confidence_threshold": 0.9, "foo_confidence": 0.5}
        snapshot = SystemSnapshot.capture(loop)
        assert "confidence_threshold" in snapshot.confidence_thresholds
        assert snapshot.confidence_thresholds["confidence_threshold"] == 0.9


# ---------------------------------------------------------------------------
# Action enumeration tests
# ---------------------------------------------------------------------------

class TestEnumerateActions:
    def test_enumerate_actions_generates_multiple_candidates(self, engine, gap):
        """At least 5 different candidate actions should be returned per gap."""
        candidates = engine.enumerate_actions(gap)
        assert len(candidates) >= 5

    def test_enumerate_actions_includes_noop_baseline(self, engine, gap):
        """The do-nothing baseline must always be present."""
        candidates = engine.enumerate_actions(gap)
        noop_actions = [a for a in candidates if a.fix_type == "noop"]
        assert len(noop_actions) >= 1, "No noop baseline found in candidates"

    def test_enumerate_actions_timeout_gap_gets_parametric_sweep(self, engine):
        """A timeout gap should generate multiple timeout delta variants."""
        timeout_gap = _FakeGap(description="timeout error", category="timeout")
        candidates = engine.enumerate_actions(timeout_gap)
        timeout_actions = [a for a in candidates if a.fix_type == "config_adjustment"]
        assert len(timeout_actions) >= 3, "Expected at least 3 parametric timeout variants"

    def test_enumerate_actions_confidence_gap_gets_delta_variants(self, engine):
        """A confidence gap should generate multiple confidence delta variants."""
        conf_gap = _FakeGap(description="confidence drift detected", category="confidence")
        candidates = engine.enumerate_actions(conf_gap)
        conf_actions = [a for a in candidates if "confidence" in a.action_id]
        assert len(conf_actions) >= 2

    def test_enumerate_actions_includes_composite(self, engine):
        """A composite action combining two simpler fixes should be generated."""
        gap = _FakeGap(description="timeout and confidence issue", category="timeout")
        candidates = engine.enumerate_actions(gap)
        composite_actions = [a for a in candidates if a.fix_type == "composite"]
        assert len(composite_actions) >= 1, "No composite action found"

    def test_parametric_sweep_different_delta_values(self, engine):
        """Parametric sweep should produce candidates with distinct delta values."""
        gap = _FakeGap(description="timeout error spike", category="timeout")
        candidates = engine.enumerate_actions(gap)
        deltas = set()
        for a in candidates:
            for step in a.fix_steps:
                if "delta_ms" in step:
                    deltas.add(step["delta_ms"])
        assert len(deltas) >= 3, f"Expected ≥3 distinct timeout deltas, got {deltas}"

    def test_all_actions_have_valid_action_ids(self, engine, gap):
        """Every candidate action must have a non-empty action_id."""
        candidates = engine.enumerate_actions(gap)
        for action in candidates:
            assert action.action_id, f"Action missing action_id: {action}"

    def test_all_actions_reference_correct_gap_id(self, engine, gap):
        """Every candidate action must reference the correct gap_id."""
        candidates = engine.enumerate_actions(gap)
        for action in candidates:
            assert action.gap_id == gap.gap_id


# ---------------------------------------------------------------------------
# Simulation tests
# ---------------------------------------------------------------------------

class TestSimulateAction:
    def test_simulate_action_returns_valid_scores(self, engine, gap):
        """Simulation effectiveness scores must be in [0.0, 1.0]."""
        candidates = engine.enumerate_actions(gap)
        snapshot = SystemSnapshot.capture(_FakeLoop())
        for action in candidates[:3]:
            result = engine.simulate_action(action, snapshot)
            assert 0.0 <= result.effectiveness_score <= 1.0, (
                f"Score out of range for {action.action_id}: {result.effectiveness_score}"
            )

    def test_noop_action_scores_zero(self, engine, gap):
        """The do-nothing baseline should always score 0.0."""
        noop = engine._make_noop(gap.gap_id)
        snapshot = SystemSnapshot.capture(_FakeLoop())
        result = engine.simulate_action(noop, snapshot)
        assert result.effectiveness_score == 0.0

    def test_simulation_result_has_duration(self, engine, gap):
        """Simulation results should record a non-negative duration."""
        candidates = engine.enumerate_actions(gap)
        snapshot = SystemSnapshot.capture(_FakeLoop())
        result = engine.simulate_action(candidates[0], snapshot)
        assert result.simulation_duration_ms >= 0.0

    def test_sandbox_isolation_does_not_modify_snapshot(self, engine, gap):
        """Running a simulation must not modify the original snapshot."""
        loop = _FakeLoop()
        loop._runtime_config = {"timeout_ms": 5000}
        snapshot = SystemSnapshot.capture(loop)
        original_config = dict(snapshot.runtime_config)

        candidates = engine.enumerate_actions(gap)
        engine.simulate_all(candidates[:3], snapshot)

        assert snapshot.runtime_config == original_config, (
            "Snapshot was mutated by simulation"
        )


# ---------------------------------------------------------------------------
# Ranking tests
# ---------------------------------------------------------------------------

class TestRankActions:
    def test_rank_actions_selects_highest_score(self, engine, gap):
        """The top-ranked action must have the highest effectiveness score."""
        results = [
            SimulationResult("a1", gap.gap_id, 0.9, 2, 0, [], 10.0, "green", [], 0.4),
            SimulationResult("a2", gap.gap_id, 0.6, 1, 1, [], 20.0, "yellow", [], 0.1),
            SimulationResult("a3", gap.gap_id, 0.3, 0, 2, [], 5.0, "red", [], -0.2),
        ]
        ranking = engine.rank_actions(gap.gap_id, results)
        assert ranking.selected_action_id == "a1"

    def test_rank_actions_secondary_fewer_side_effects(self, engine, gap):
        """When scores are equal, prefer fewer side effects."""
        results = [
            SimulationResult("a1", gap.gap_id, 0.8, 2, 0, [], 10.0, "green", ["fx1", "fx2"], 0.3),
            SimulationResult("a2", gap.gap_id, 0.8, 2, 0, [], 10.0, "green", [], 0.3),
        ]
        ranking = engine.rank_actions(gap.gap_id, results)
        assert ranking.selected_action_id == "a2"

    def test_rank_actions_returns_all_candidates(self, engine, gap):
        """All simulation results should appear in ranked_actions."""
        results = [
            SimulationResult(f"a{i}", gap.gap_id, float(i) / 10, 1, 0, [], 1.0, "green", [], 0.0)
            for i in range(5)
        ]
        ranking = engine.rank_actions(gap.gap_id, results)
        assert len(ranking.ranked_actions) == 5

    def test_rank_actions_empty_results_returns_noop(self, engine, gap):
        """Empty result list should return a fallback noop ranking."""
        ranking = engine.rank_actions(gap.gap_id, [])
        assert ranking.selected_action_id == "noop_fallback"


# ---------------------------------------------------------------------------
# Antibody memory tests
# ---------------------------------------------------------------------------

class TestAntibodyMemory:
    def test_antibody_memory_fast_path(self, engine, gap):
        """A known pattern with high confidence should trigger the fast path."""
        # Manually plant a high-confidence antibody
        action = engine._make_timeout_action(gap.gap_id, 50)
        sig = engine._compute_gap_signature(gap)
        pattern = AntibodyPattern(
            pattern_id=str(uuid.uuid4()),
            gap_signature=sig,
            winning_action=action,
            effectiveness_history=[0.9],
            times_used=5,
            times_succeeded=5,
            last_used="2024-01-01T00:00:00+00:00",
            confidence=0.9,
        )
        with engine._lock:
            engine._antibody_memory[sig] = pattern

        loop = _FakeLoop()
        report = engine.run_sandbox_cycle([gap], loop)
        assert report.antibody_hits >= 1

    def test_antibody_memory_learning(self, engine, gap):
        """After learn_from_outcome, antibody memory should be updated."""
        action = engine._make_timeout_action(gap.gap_id, 30)
        sim_result = SimulationResult(
            action_id=action.action_id,
            gap_id=gap.gap_id,
            effectiveness_score=0.85,
            tests_passed=2,
            tests_failed=0,
            regressions_detected=[],
            simulation_duration_ms=50.0,
            predicted_health_status="green",
            side_effects=[],
            confidence_delta=0.35,
        )
        engine.learn_from_outcome(action, sim_result, gap)

        sig = engine._compute_gap_signature(gap)
        with engine._lock:
            assert sig in engine._antibody_memory
            assert engine._antibody_memory[sig].times_used == 1

    def test_antibody_memory_pruning(self, engine):
        """Filling memory past the limit should prune the weakest entries."""
        # Plant 1010 patterns (> _MAX_ANTIBODY_ENTRIES = 1000)
        for i in range(1010):
            fake_gap = _FakeGap(
                description=f"unique gap description number {i}",
                category=f"category_{i}",
            )
            action = engine._make_noop(fake_gap.gap_id)
            sim_result = SimulationResult(
                action_id=action.action_id,
                gap_id=fake_gap.gap_id,
                effectiveness_score=float(i) / 1010,
                tests_passed=1,
                tests_failed=0,
                regressions_detected=[],
                simulation_duration_ms=1.0,
                predicted_health_status="green",
                side_effects=[],
                confidence_delta=0.0,
            )
            engine.learn_from_outcome(action, sim_result, fake_gap)

        with engine._lock:
            assert len(engine._antibody_memory) <= engine._MAX_ANTIBODY_ENTRIES

    def test_antibody_memory_updates_existing_pattern(self, engine, gap):
        """Calling learn_from_outcome twice for the same gap updates the pattern."""
        action = engine._make_timeout_action(gap.gap_id, 20)
        sim_result = SimulationResult(
            action_id=action.action_id,
            gap_id=gap.gap_id,
            effectiveness_score=0.7,
            tests_passed=1,
            tests_failed=0,
            regressions_detected=[],
            simulation_duration_ms=10.0,
            predicted_health_status="green",
            side_effects=[],
            confidence_delta=0.2,
        )
        engine.learn_from_outcome(action, sim_result, gap)
        engine.learn_from_outcome(action, sim_result, gap)

        sig = engine._compute_gap_signature(gap)
        with engine._lock:
            pattern = engine._antibody_memory[sig]
        assert pattern.times_used == 2


# ---------------------------------------------------------------------------
# Full cycle tests
# ---------------------------------------------------------------------------

class TestFullSandboxCycle:
    def test_full_sandbox_cycle_returns_report(self, engine, gap):
        """End-to-end: run_sandbox_cycle should return a valid SandboxReport."""
        loop = _FakeLoop()
        report = engine.run_sandbox_cycle([gap], loop)

        assert isinstance(report, SandboxReport)
        assert report.gaps_analyzed == 1
        assert len(report.rankings) == 1
        assert report.duration_ms >= 0.0

    def test_full_cycle_multiple_gaps(self, engine):
        """Cycle with multiple gaps should produce one ranking per gap."""
        gaps = [_FakeGap() for _ in range(3)]
        loop = _FakeLoop()
        report = engine.run_sandbox_cycle(gaps, loop)
        assert report.gaps_analyzed == 3
        assert len(report.rankings) == 3

    def test_chaos_verification_after_fix(self, engine, gap):
        """run_chaos_verification should return a list (may be empty)."""
        loop = _FakeLoop()
        new_gaps = engine.run_chaos_verification(loop)
        assert isinstance(new_gaps, list)

    def test_commit_action_below_threshold_returns_false(self, engine, gap):
        """commit_action should return False when the best score is below threshold."""
        result = SimulationResult(
            action_id="low_score_action",
            gap_id=gap.gap_id,
            effectiveness_score=0.1,
            tests_passed=0,
            tests_failed=1,
            regressions_detected=[],
            simulation_duration_ms=5.0,
            predicted_health_status="red",
            side_effects=[],
            confidence_delta=-0.4,
        )
        with engine._lock:
            engine._simulation_results["low_score_action"] = result

        ranking = ActionRanking(
            gap_id=gap.gap_id,
            ranked_actions=[("low_score_action", 0.1, result)],
            selected_action_id="low_score_action",
            selection_reason="test",
        )
        loop = _FakeLoop()
        assert engine.commit_action(ranking, loop) is False

    def test_composite_actions_have_combined_steps(self, engine, gap):
        """Composite actions should contain steps from both constituent actions."""
        gap = _FakeGap(description="timeout and confidence issue", category="timeout")
        candidates = engine.enumerate_actions(gap)
        composites = [a for a in candidates if a.fix_type == "composite"]
        assert composites, "No composite action generated"
        composite = composites[0]
        assert len(composite.fix_steps) >= 2, "Composite action should have at least 2 steps"
