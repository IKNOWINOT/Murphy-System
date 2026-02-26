"""
Tests for ARCH-001: SelfImprovementEngine persistence wiring.

Validates that the SelfImprovementEngine can save and restore state
via PersistenceManager, surviving simulated restarts.

Design Label: TEST-001 / ARCH-001
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from self_improvement_engine import (
    ExecutionOutcome,
    ImprovementProposal,
    OutcomeType,
    SelfImprovementEngine,
)
from persistence_manager import PersistenceManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def engine(pm):
    return SelfImprovementEngine(persistence_manager=pm)


def _make_outcome(task_id="t1", session_id="s1", outcome=OutcomeType.SUCCESS,
                  task_type="deploy", duration=1.0, confidence=0.9, route="deterministic"):
    return ExecutionOutcome(
        task_id=task_id,
        session_id=session_id,
        outcome=outcome,
        metrics={"task_type": task_type, "duration": duration,
                 "confidence": confidence, "route": route},
    )


# ------------------------------------------------------------------
# Backward compatibility: no persistence_manager
# ------------------------------------------------------------------

class TestNoPersistence:
    def test_engine_works_without_persistence(self):
        engine = SelfImprovementEngine()
        engine.record_outcome(_make_outcome())
        assert engine.get_status()["total_outcomes"] == 1

    def test_save_state_returns_false_without_pm(self):
        engine = SelfImprovementEngine()
        assert engine.save_state() is False

    def test_load_state_returns_false_without_pm(self):
        engine = SelfImprovementEngine()
        assert engine.load_state() is False


# ------------------------------------------------------------------
# Persistence round-trip
# ------------------------------------------------------------------

class TestPersistenceRoundTrip:
    def test_save_and_load_outcomes(self, pm):
        engine1 = SelfImprovementEngine(persistence_manager=pm)
        for i in range(3):
            engine1.record_outcome(_make_outcome(task_id=f"t-{i}"))
        assert engine1.save_state() is True

        engine2 = SelfImprovementEngine(persistence_manager=pm)
        assert engine2.get_status()["total_outcomes"] == 0
        assert engine2.load_state() is True
        assert engine2.get_status()["total_outcomes"] == 3

    def test_save_and_load_proposals(self, pm):
        engine1 = SelfImprovementEngine(persistence_manager=pm)
        for i in range(3):
            engine1.record_outcome(_make_outcome(
                task_id=f"fail-{i}", outcome=OutcomeType.FAILURE, task_type="integration"))
        engine1.generate_proposals()
        assert engine1.get_status()["total_proposals"] > 0
        engine1.save_state()

        engine2 = SelfImprovementEngine(persistence_manager=pm)
        engine2.load_state()
        assert engine2.get_status()["total_proposals"] == engine1.get_status()["total_proposals"]

    def test_save_and_load_corrections(self, pm):
        engine1 = SelfImprovementEngine(persistence_manager=pm)
        for i in range(3):
            engine1.record_outcome(_make_outcome(
                task_id=f"fail-{i}", outcome=OutcomeType.FAILURE, task_type="deploy"))
        proposals = engine1.generate_proposals()
        if proposals:
            engine1.apply_correction(proposals[0].proposal_id, "fixed")
        engine1.save_state()

        engine2 = SelfImprovementEngine(persistence_manager=pm)
        engine2.load_state()
        assert engine2.get_status()["corrections_log_size"] == engine1.get_status()["corrections_log_size"]

    def test_load_state_returns_false_when_empty(self, pm):
        engine = SelfImprovementEngine(persistence_manager=pm)
        assert engine.load_state() is False

    def test_outcome_types_preserved(self, pm):
        engine1 = SelfImprovementEngine(persistence_manager=pm)
        engine1.record_outcome(_make_outcome(outcome=OutcomeType.FAILURE))
        engine1.record_outcome(_make_outcome(task_id="t2", outcome=OutcomeType.TIMEOUT))
        engine1.save_state()

        engine2 = SelfImprovementEngine(persistence_manager=pm)
        engine2.load_state()
        summary = engine2.get_learning_summary()
        assert summary["outcome_distribution"]["failure"] == 1
        assert summary["outcome_distribution"]["timeout"] == 1
