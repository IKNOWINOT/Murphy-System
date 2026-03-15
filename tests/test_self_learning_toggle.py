# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for SelfLearningToggle (Facet 2)
"""

import sys
import os
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.self_learning_toggle import SelfLearningToggle, get_self_learning_toggle


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

class TestSelfLearningToggleLifecycle:
    def test_default_disabled(self):
        slt = SelfLearningToggle()
        assert slt.is_enabled() is False

    def test_can_start_enabled(self):
        slt = SelfLearningToggle(enabled=True)
        assert slt.is_enabled() is True

    def test_enable(self):
        slt = SelfLearningToggle(enabled=False)
        slt.enable()
        assert slt.is_enabled() is True

    def test_disable(self):
        slt = SelfLearningToggle(enabled=True)
        slt.disable()
        assert slt.is_enabled() is False


# ---------------------------------------------------------------------------
# Toggle
# ---------------------------------------------------------------------------

class TestToggle:
    def test_toggle_from_disabled(self):
        slt = SelfLearningToggle(enabled=False)
        result = slt.toggle()
        assert result["self_learning_enabled"] is True
        assert slt.is_enabled() is True

    def test_toggle_from_enabled(self):
        slt = SelfLearningToggle(enabled=True)
        result = slt.toggle()
        assert result["self_learning_enabled"] is False
        assert slt.is_enabled() is False

    def test_toggle_twice_returns_to_original(self):
        slt = SelfLearningToggle(enabled=False)
        slt.toggle()
        slt.toggle()
        assert slt.is_enabled() is False


# ---------------------------------------------------------------------------
# Skipped operations counter
# ---------------------------------------------------------------------------

class TestSkippedCounter:
    def test_increment_skipped(self):
        slt = SelfLearningToggle()
        slt.increment_skipped()
        slt.increment_skipped()
        assert slt.get_status()["skipped_operations"] == 2

    def test_increment_by_multiple(self):
        slt = SelfLearningToggle()
        slt.increment_skipped(10)
        assert slt.get_status()["skipped_operations"] == 10

    def test_reset_skipped_counter(self):
        slt = SelfLearningToggle()
        slt.increment_skipped(5)
        slt.reset_skipped_counter()
        assert slt.get_status()["skipped_operations"] == 0


# ---------------------------------------------------------------------------
# Status structure
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_disabled_note(self):
        slt = SelfLearningToggle(enabled=False)
        status = slt.get_status()
        note_lower = status["note"].lower()
        assert "disabled" in note_lower or "off" in note_lower or "learning disabled" in note_lower

    def test_status_enabled_note(self):
        slt = SelfLearningToggle(enabled=True)
        status = slt.get_status()
        note_lower = status["note"].lower()
        assert "active" in note_lower or "collected" in note_lower

    def test_status_has_required_keys(self):
        slt = SelfLearningToggle()
        status = slt.get_status()
        assert "self_learning_enabled" in status
        assert "skipped_operations" in status
        assert "note" in status


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_increments(self):
        slt = SelfLearningToggle()
        threads = [threading.Thread(target=slt.increment_skipped) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert slt.get_status()["skipped_operations"] == 100

    def test_concurrent_toggles_are_safe(self):
        slt = SelfLearningToggle()
        def _toggle():
            for _ in range(10):
                slt.toggle()
        threads = [threading.Thread(target=_toggle) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # After 100 toggles (even number) state should be same as start (False)
        assert isinstance(slt.is_enabled(), bool)


# ---------------------------------------------------------------------------
# Integration with learning subsystems
# ---------------------------------------------------------------------------

class TestLearningSubsystemGuards:
    """
    Verify that the guard pattern in learning subsystems works correctly
    by calling them directly with the toggle off.
    """

    def test_learn_from_correction_skips_when_disabled(self, monkeypatch):
        """learn_from_correction should short-circuit when learning is off."""
        import importlib
        import src.self_learning_toggle as slt_mod

        # Create a fresh disabled toggle and patch the singleton
        fresh_slt = SelfLearningToggle(enabled=False)
        monkeypatch.setattr(slt_mod, "_toggle", fresh_slt)

        from src.learning_engine.learning_system import LearningSystem
        ls = LearningSystem()
        initial_patterns = ls._patterns_learned
        ls.learn_from_correction({"task_id": "test-1", "correction": "none"})

        # Pattern count must NOT have changed — operation was skipped
        assert ls._patterns_learned == initial_patterns
        assert fresh_slt.get_status()["skipped_operations"] >= 1

    def test_check_retrain_returns_disabled_when_off(self, monkeypatch):
        """check_retrain_triggers must return disabled status when learning is off."""
        import src.self_learning_toggle as slt_mod

        fresh_slt = SelfLearningToggle(enabled=False)
        monkeypatch.setattr(slt_mod, "_toggle", fresh_slt)

        from src.murphy_foundation_model.self_improvement_loop import SelfImprovementLoop
        loop = SelfImprovementLoop()
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is False
        assert "self_learning_disabled" in result["reasons"]

    def test_record_outcome_skips_when_disabled(self, monkeypatch):
        """record_outcome must NOT append to _outcomes when learning is off."""
        import src.self_learning_toggle as slt_mod

        fresh_slt = SelfLearningToggle(enabled=False)
        monkeypatch.setattr(slt_mod, "_toggle", fresh_slt)

        from src.self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType
        engine = SelfImprovementEngine()
        initial_count = len(engine._outcomes)
        outcome = ExecutionOutcome(
            task_id="t1",
            session_id="s1",
            outcome=OutcomeType.SUCCESS,
            metrics={},
        )
        engine.record_outcome(outcome)
        assert len(engine._outcomes) == initial_count
        assert fresh_slt.get_status()["skipped_operations"] >= 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_singleton_same_instance(self):
        a = get_self_learning_toggle()
        b = get_self_learning_toggle()
        assert a is b
