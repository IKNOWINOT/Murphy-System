"""
Tests for the ImmuneMemorySystem.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import uuid

import pytest


from immune_memory import Antibody, Antigen, ImmuneMemorySystem, MemoryCell


# ---------------------------------------------------------------------------
# Fixtures
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


class _FakeAction:
    """Minimal stand-in for CandidateAction."""

    def __init__(self) -> None:
        self.action_id = str(uuid.uuid4())
        self.fix_type = "config_adjustment"
        self.fix_steps = [{"action": "adjust_timeout", "delta_ms": 50}]
        self.rollback_steps = [{"action": "adjust_timeout", "delta_ms": -50}]
        self.test_criteria = [{"check": "timeout_errors_reduced"}]
        self.expected_outcome = "timeout_increased"


@pytest.fixture()
def memory() -> ImmuneMemorySystem:
    return ImmuneMemorySystem(similarity_threshold=0.7, max_memory_cells=10)


@pytest.fixture()
def gap() -> _FakeGap:
    return _FakeGap()


@pytest.fixture()
def action() -> _FakeAction:
    return _FakeAction()


# ---------------------------------------------------------------------------
# Core memorise / recognise tests
# ---------------------------------------------------------------------------

class TestMemorizeAndRecognize:
    def test_memorize_and_recognize(self, memory, gap, action):
        """Store a pattern and then recognise the same gap."""
        memory.memorize(gap, action, effectiveness=0.9)
        cell = memory.recognize(gap)
        assert cell is not None, "Expected to recognise the stored gap pattern"

    def test_recognize_returns_none_for_unknown_gap(self, memory):
        """A gap never seen before should not be recognised."""
        unknown_gap = _FakeGap(description="completely novel unknown situation xyz", category="novel")
        cell = memory.recognize(unknown_gap)
        assert cell is None

    def test_memorize_strengthens_existing_cell(self, memory, gap, action):
        """Calling memorize twice for the same gap should increase maturity."""
        memory.memorize(gap, action, effectiveness=0.8)
        memory.memorize(gap, action, effectiveness=0.9)
        # Memory should still have only one cell for this gap
        stats = memory.get_statistics()
        assert stats["cell_count"] == 1
        # Maturity should be 2
        cell = memory.recognize(gap)
        assert cell is not None
        assert cell.antibody.maturity == 2


# ---------------------------------------------------------------------------
# Similarity threshold tests
# ---------------------------------------------------------------------------

class TestSimilarityThreshold:
    def test_similar_gap_is_matched(self, memory):
        """A gap with a slightly different description but same category should match."""
        original_gap = _FakeGap(
            description="timeout error in component alpha",
            category="timeout",
        )
        similar_gap = _FakeGap(
            description="timeout error in component beta",
            category="timeout",
        )
        action = _FakeAction()
        memory.memorize(original_gap, action, effectiveness=0.9)
        # lower the threshold so similar (but not identical) gaps match
        memory._threshold = 0.3
        cell = memory.recognize(similar_gap)
        assert cell is not None, "Expected similar gap to be matched"

    def test_dissimilar_gap_is_not_matched(self):
        """A completely unrelated gap should not match."""
        strict_memory = ImmuneMemorySystem(similarity_threshold=0.99, max_memory_cells=10)
        stored_gap = _FakeGap(description="timeout overflow database connection", category="db")
        unrelated_gap = _FakeGap(description="authentication failure jwt expired", category="auth")
        action = _FakeAction()
        strict_memory.memorize(stored_gap, action, effectiveness=0.8)
        cell = strict_memory.recognize(unrelated_gap)
        assert cell is None, "Expected dissimilar gap to not be matched"


# ---------------------------------------------------------------------------
# Decay tests
# ---------------------------------------------------------------------------

class TestDecay:
    def test_decay_reduces_potency(self, memory, gap, action):
        """decay() should reduce cell potency."""
        memory.memorize(gap, action, effectiveness=0.9)
        cell = memory.recognize(gap)
        assert cell is not None
        initial_potency = cell.potency

        memory.decay()

        cell_after = memory.recognize(gap)
        # The potency should be reduced (if cell still exists)
        if cell_after is not None:
            assert cell_after.potency < initial_potency or cell_after.potency == 0.0

    def test_decay_removes_depleted_cells(self):
        """Cells with very high decay rates should be removed by decay()."""
        memory = ImmuneMemorySystem(similarity_threshold=0.5, max_memory_cells=50)
        gap = _FakeGap()
        action = _FakeAction()
        memory.memorize(gap, action, effectiveness=0.8)

        # Force cell potency near zero
        cell = memory.recognize(gap)
        assert cell is not None
        with memory._lock:
            cell.potency = 0.05
            cell.decay_rate = 0.1  # one decay step will drop below 0.1 threshold

        memory.decay()

        # Cell should have been removed
        cell_after = memory.recognize(gap)
        assert cell_after is None, "Depleted cell should have been removed"


# ---------------------------------------------------------------------------
# Max memory pruning tests
# ---------------------------------------------------------------------------

class TestMaxMemoryPruning:
    def test_max_memory_pruning(self):
        """Filling past max_memory_cells should prune the weakest cells."""
        memory = ImmuneMemorySystem(similarity_threshold=0.5, max_memory_cells=5)
        for i in range(10):
            gap = _FakeGap(
                description=f"unique description number {i} something different",
                category=f"cat_{i}",
                source=f"src_{i}",
            )
            action = _FakeAction()
            memory.memorize(gap, action, effectiveness=float(i) / 10)

        stats = memory.get_statistics()
        assert stats["cell_count"] <= 5, (
            f"Expected ≤5 cells after pruning, got {stats['cell_count']}"
        )


# ---------------------------------------------------------------------------
# Statistics tests
# ---------------------------------------------------------------------------

class TestStatistics:
    def test_statistics_correct_counts(self, memory, gap, action):
        """get_statistics should return accurate cell count and averages."""
        memory.memorize(gap, action, effectiveness=0.8)
        stats = memory.get_statistics()
        assert stats["cell_count"] == 1
        assert 0.0 <= stats["avg_effectiveness"] <= 1.0

    def test_statistics_empty_memory(self):
        """get_statistics on an empty memory should return zero counts."""
        memory = ImmuneMemorySystem()
        stats = memory.get_statistics()
        assert stats["cell_count"] == 0
        assert stats["avg_effectiveness"] == 0.0

    def test_statistics_top_patterns(self, memory):
        """get_statistics should include top patterns list."""
        for i in range(3):
            gap = _FakeGap(
                description=f"gap type {i} description here",
                category=f"cat_{i}",
                source="test",
            )
            action = _FakeAction()
            memory.memorize(gap, action, effectiveness=float(i + 1) / 3)

        stats = memory.get_statistics()
        assert "top_patterns" in stats
        assert len(stats["top_patterns"]) <= 5


# ---------------------------------------------------------------------------
# Activate test
# ---------------------------------------------------------------------------

class TestActivate:
    def test_activate_returns_candidate_action(self, memory, gap, action):
        """activate() should return a CandidateAction with the correct gap_id."""
        from causality_sandbox import CandidateAction

        memory.memorize(gap, action, effectiveness=0.85)
        cell = memory.recognize(gap)
        assert cell is not None

        candidate = memory.activate(cell, gap)
        assert isinstance(candidate, CandidateAction)
        assert candidate.gap_id == gap.gap_id

    def test_activate_boosts_potency(self, memory, gap, action):
        """activate() should increase cell potency."""
        memory.memorize(gap, action, effectiveness=0.8)
        cell = memory.recognize(gap)
        assert cell is not None

        # Force potency down
        with memory._lock:
            cell.potency = 0.5

        memory.activate(cell, gap)
        assert cell.potency > 0.5
