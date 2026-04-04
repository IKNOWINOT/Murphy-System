"""
Tests for feedback_integrator.py (Gap CFP-4 — Closed Learning Loop).

Covers:
- Correction signal updates state uncertainty
- Batch delta computation
- Recalibration trigger fires when threshold exceeded
- Recalibration trigger does NOT fire below threshold
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from feedback_integrator import FeedbackIntegrator, FeedbackSignal
from state_schema import StateVariable, StateVectorSchema, TypedStateVector


# ======================================================================
# Helpers
# ======================================================================

def _make_state(*names_uncertainties) -> TypedStateVector:
    """Create a TypedStateVector with given (name, uncertainty) pairs."""
    dims = [
        StateVariable(name=name, value=0.5, uncertainty=u)
        for name, u in names_uncertainties
    ]
    schema = StateVectorSchema(domain="test", dimensions=dims)
    return TypedStateVector(schema=schema)


def _make_correction(
    source_task_id: str,
    original: float,
    corrected: float,
    affected: list,
) -> FeedbackSignal:
    return FeedbackSignal(
        signal_type="correction",
        source_task_id=source_task_id,
        original_confidence=original,
        corrected_confidence=corrected,
        affected_state_variables=affected,
    )


# ======================================================================
# integrate() — correction signal updates state uncertainty
# ======================================================================

class TestIntegrate:
    """FeedbackIntegrator.integrate() applies corrections to state uncertainty."""

    def setup_method(self):
        self.integrator = FeedbackIntegrator()

    def test_correction_reduces_uncertainty(self):
        state = _make_state(("confidence", 0.8))
        signal = _make_correction("t1", original=0.3, corrected=0.7, affected=["confidence"])
        updated = self.integrator.integrate(signal, state)
        new_uncertainty = updated.get("confidence").uncertainty
        assert new_uncertainty < 0.8

    def test_correction_delta_is_magnitude_of_change(self):
        state = _make_state(("confidence", 0.5))
        signal = _make_correction("t1", original=0.4, corrected=0.9, affected=["confidence"])
        updated = self.integrator.integrate(signal, state)
        expected = 0.5 - abs(0.9 - 0.4)
        assert updated.get("confidence").uncertainty == pytest.approx(expected)

    def test_uncertainty_clamped_at_zero(self):
        state = _make_state(("confidence", 0.1))
        signal = _make_correction("t1", original=0.0, corrected=1.0, affected=["confidence"])
        updated = self.integrator.integrate(signal, state)
        assert updated.get("confidence").uncertainty >= 0.0

    def test_uncertainty_clamped_at_one(self):
        state = _make_state(("confidence", 0.95))
        # Non-correction signal increases uncertainty slightly via negative delta
        signal = FeedbackSignal(
            signal_type="feedback",
            source_task_id="t2",
            original_confidence=0.5,
            corrected_confidence=None,  # no corrected value → -0.05 delta
            affected_state_variables=["confidence"],
        )
        updated = self.integrator.integrate(signal, state)
        assert updated.get("confidence").uncertainty <= 1.0

    def test_integrate_multiple_variables(self):
        state = _make_state(("conf", 0.5), ("risk", 0.6))
        signal = _make_correction("t3", original=0.2, corrected=0.6, affected=["conf", "risk"])
        updated = self.integrator.integrate(signal, state)
        assert updated.get("conf").uncertainty < 0.5
        assert updated.get("risk").uncertainty < 0.6

    def test_integrate_adds_missing_variable(self):
        state = _make_state(("confidence", 0.5))
        signal = _make_correction("t4", original=0.4, corrected=0.8, affected=["new_dim"])
        updated = self.integrator.integrate(signal, state)
        assert "new_dim" in updated

    def test_integrate_returns_same_state_object(self):
        state = _make_state(("x", 0.3))
        signal = _make_correction("t5", original=0.3, corrected=0.7, affected=["x"])
        returned = self.integrator.integrate(signal, state)
        assert returned is state

    def test_non_correction_signal_reduces_uncertainty(self):
        state = _make_state(("x", 0.6))
        signal = FeedbackSignal(
            signal_type="feedback",
            source_task_id="t6",
            original_confidence=0.5,
            affected_state_variables=["x"],
        )
        updated = self.integrator.integrate(signal, state)
        assert updated.get("x").uncertainty < 0.6


# ======================================================================
# compute_learning_delta()
# ======================================================================

class TestComputeLearningDelta:
    """compute_learning_delta() returns per-variable uncertainty adjustments."""

    def setup_method(self):
        self.integrator = FeedbackIntegrator()

    def test_single_signal_delta(self):
        signals = [
            _make_correction("t1", original=0.3, corrected=0.7, affected=["conf"])
        ]
        deltas = self.integrator.compute_learning_delta(signals)
        assert "conf" in deltas
        assert deltas["conf"] == pytest.approx(-0.4)

    def test_multiple_signals_same_variable(self):
        signals = [
            _make_correction("t1", original=0.3, corrected=0.5, affected=["conf"]),
            _make_correction("t2", original=0.5, corrected=0.7, affected=["conf"]),
        ]
        deltas = self.integrator.compute_learning_delta(signals)
        # Each contributes -0.2; combined -0.4
        assert deltas["conf"] == pytest.approx(-0.4)

    def test_multiple_variables(self):
        signals = [
            _make_correction("t1", original=0.0, corrected=0.5, affected=["a", "b"])
        ]
        deltas = self.integrator.compute_learning_delta(signals)
        assert "a" in deltas
        assert "b" in deltas
        assert deltas["a"] == pytest.approx(-0.5)

    def test_empty_signals_returns_empty_dict(self):
        deltas = self.integrator.compute_learning_delta([])
        assert deltas == {}

    def test_no_correction_signal(self):
        signals = [
            FeedbackSignal(
                signal_type="feedback",
                source_task_id="t1",
                original_confidence=0.5,
                affected_state_variables=["x"],
            )
        ]
        deltas = self.integrator.compute_learning_delta(signals)
        assert "x" in deltas
        assert deltas["x"] < 0.0  # non-correction → small negative delta


# ======================================================================
# should_trigger_recalibration()
# ======================================================================

class TestShouldTriggerRecalibration:
    """should_trigger_recalibration() fires above threshold, not below."""

    def setup_method(self):
        self.integrator = FeedbackIntegrator()

    def test_fires_above_threshold(self):
        signals = [
            _make_correction("t1", original=0.0, corrected=0.8, affected=[]),
            _make_correction("t2", original=0.2, corrected=0.9, affected=[]),
        ]
        # average correction = (0.8 + 0.7) / 2 = 0.75 > 0.3
        assert self.integrator.should_trigger_recalibration(signals, threshold=0.3) is True

    def test_does_not_fire_below_threshold(self):
        signals = [
            _make_correction("t1", original=0.5, corrected=0.55, affected=[]),
            _make_correction("t2", original=0.6, corrected=0.65, affected=[]),
        ]
        # average correction = (0.05 + 0.05) / 2 = 0.05 < 0.3
        assert self.integrator.should_trigger_recalibration(signals, threshold=0.3) is False

    def test_fires_at_exact_threshold(self):
        signals = [
            _make_correction("t1", original=0.0, corrected=0.3, affected=[])
        ]
        # avg = 0.3 == threshold → should trigger
        assert self.integrator.should_trigger_recalibration(signals, threshold=0.3) is True

    def test_no_corrected_confidence_never_triggers(self):
        signals = [
            FeedbackSignal(
                signal_type="feedback",
                source_task_id="t1",
                original_confidence=0.5,
                corrected_confidence=None,
                affected_state_variables=[],
            )
        ]
        assert self.integrator.should_trigger_recalibration(signals, threshold=0.0) is False

    def test_empty_signals_never_triggers(self):
        assert self.integrator.should_trigger_recalibration([], threshold=0.0) is False

    def test_default_threshold_is_0_3(self):
        signals = [
            _make_correction("t1", original=0.0, corrected=0.4, affected=[])
        ]
        # 0.4 > 0.3 default
        assert self.integrator.should_trigger_recalibration(signals) is True
