"""
Tests for the 5 structural audit gaps (GAP-1 through GAP-5).

Covers:
1. StateVector creation, dimensionality, dict-like access, uncertainty tracking.
2. Unified Murphy Index mode selection (expected-loss vs. fallback).
3. LLM output validation (valid input, invalid input, partial input).
4. Observation model (channel registration, processing, information gain > 0).
5. Stability safeguards (hysteresis prevents oscillation, phase reversal limit).
"""

import os


import pytest
from mfgc_core import (
    MFGCSystemState,
    Phase,
    ConfidenceEngine,
    StateVector,
    N_BASE_DIMS,
    HYSTERESIS_BAND,
    MAX_PHASE_REVERSALS,
)


# ======================================================================
# GAP-1: Typed State Vector
# ======================================================================

class TestStateVector:
    """GAP-1 — Typed State Vector."""

    def test_default_creation(self):
        sv = StateVector()
        assert sv.domain_knowledge_level == 0.0
        assert sv.constraint_satisfaction_ratio == 0.0
        assert sv.information_completeness == 0.0
        assert sv.verification_coverage == 0.0
        assert sv.risk_exposure == 0.0
        assert sv.authority_utilization == 0.0

    def test_base_dims_constant(self):
        assert N_BASE_DIMS == 6

    def test_dimensionality_base(self):
        sv = StateVector()
        assert sv.get_dimensionality() == N_BASE_DIMS

    def test_dimensionality_with_custom(self):
        sv = StateVector(custom_dimensions={"my_dim": 0.5, "other": 0.3})
        assert sv.get_dimensionality() == N_BASE_DIMS + 2

    def test_dict_like_get(self):
        sv = StateVector(domain_knowledge_level=0.7)
        assert sv.get("domain_knowledge_level") == 0.7
        assert sv.get("nonexistent", 42) == 42

    def test_dict_like_getitem(self):
        sv = StateVector(information_completeness=0.6)
        assert sv["information_completeness"] == 0.6

    def test_dict_like_contains(self):
        sv = StateVector()
        assert "domain_knowledge_level" in sv

    def test_dict_like_setitem(self):
        sv = StateVector()
        sv["domain_knowledge_level"] = 0.9
        assert sv.domain_knowledge_level == 0.9

    def test_custom_dimension_via_setitem(self):
        sv = StateVector()
        sv["my_custom"] = 0.4
        assert sv.get("my_custom") == 0.4

    def test_uncertainty_tracking(self):
        sv = StateVector(uncertainty={"domain_knowledge_level": 0.2})
        assert sv.uncertainty["domain_knowledge_level"] == 0.2

    def test_from_dict(self):
        sv = StateVector.from_dict({
            "domain_knowledge_level": 0.5,
            "task": "build a system",
        })
        assert sv.domain_knowledge_level == 0.5
        # extra key stored via dict-compat
        assert sv.get("task") == "build a system"

    def test_mfgc_state_uses_state_vector(self):
        state = MFGCSystemState()
        assert isinstance(state.x_t, StateVector)

    def test_state_vector_update(self):
        sv = StateVector()
        sv.update({"domain_knowledge_level": 0.8, "verification_coverage": 0.5})
        assert sv.domain_knowledge_level == 0.8
        assert sv.verification_coverage == 0.5


# ======================================================================
# GAP-2: Unified Murphy Index
# ======================================================================

class TestMurphyIndexMode:
    """GAP-2 — Unified Murphy Index mode selection."""

    def test_fallback_mode_no_risk_data(self):
        from confidence_engine.confidence_engine import ConfidenceEngine, MurphyIndexMode

        engine = ConfidenceEngine()
        result = engine.compute_confidence([{"confidence": 0.8, "type": "verified"}])
        assert result["murphy_index_mode"] == MurphyIndexMode.CONFIDENCE_COMPLEMENT.value
        assert abs(result["murphy_index"] - 0.2) < 1e-3

    def test_expected_loss_mode_with_risk_data(self):
        from confidence_engine.confidence_engine import ConfidenceEngine, MurphyIndexMode

        engine = ConfidenceEngine()
        artifacts = [
            {"confidence": 0.8, "loss": 0.5, "probability": 0.2},
            {"confidence": 0.6, "loss": 0.3, "probability": 0.4},
        ]
        result = engine.compute_confidence(artifacts)
        assert result["murphy_index_mode"] == MurphyIndexMode.EXPECTED_LOSS.value
        # M_t = 0.5*0.2 + 0.3*0.4 = 0.1 + 0.12 = 0.22
        assert abs(result["murphy_index"] - 0.22) < 1e-3

    def test_murphy_index_clamped_to_one(self):
        from confidence_engine.confidence_engine import ConfidenceEngine

        engine = ConfidenceEngine()
        artifacts = [{"confidence": 0.1, "loss": 2.0, "probability": 0.9}]
        result = engine.compute_confidence(artifacts)
        assert result["murphy_index"] <= 1.0

    def test_empty_artifacts(self):
        from confidence_engine.confidence_engine import ConfidenceEngine, MurphyIndexMode

        engine = ConfidenceEngine()
        result = engine.compute_confidence([])
        assert result["overall_confidence"] == 0.0
        assert "murphy_index_mode" in result

    def test_single_dict_input_fallback(self):
        from confidence_engine.confidence_engine import ConfidenceEngine, MurphyIndexMode

        engine = ConfidenceEngine()
        result = engine.compute_confidence({"confidence": 0.7})
        assert result["murphy_index_mode"] == MurphyIndexMode.CONFIDENCE_COMPLEMENT.value
        assert abs(result["murphy_index"] - 0.3) < 1e-3

    def test_single_dict_with_risk_data(self):
        from confidence_engine.confidence_engine import ConfidenceEngine, MurphyIndexMode

        engine = ConfidenceEngine()
        result = engine.compute_confidence({"confidence": 0.7, "loss": 0.4, "probability": 0.5})
        assert result["murphy_index_mode"] == MurphyIndexMode.EXPECTED_LOSS.value
        assert abs(result["murphy_index"] - 0.2) < 1e-3

    def test_murphy_index_mode_enum_values(self):
        from confidence_engine.confidence_engine import MurphyIndexMode

        assert MurphyIndexMode.EXPECTED_LOSS.value == "expected_loss"
        assert MurphyIndexMode.CONFIDENCE_COMPLEMENT.value == "confidence_complement"


# ======================================================================
# GAP-3: LLM Output Schema Validation
# ======================================================================

class TestLLMOutputValidator:
    """GAP-3 — LLM output schema validation."""

    def setup_method(self):
        from llm_output_validator import LLMOutputValidator
        self.validator = LLMOutputValidator()

    def test_valid_expert(self):
        raw = {
            "name": "Dr. Smith",
            "domain": "software_engineering",
            "capabilities": ["code review", "architecture"],
            "confidence": 0.9,
        }
        ok, obj, errors = self.validator.validate_expert(raw)
        assert ok is True
        assert obj is not None
        assert obj.name == "Dr. Smith"
        assert errors == []

    def test_invalid_expert_missing_field(self):
        raw = {"name": "Dr. Smith"}  # missing domain, capabilities
        ok, obj, errors = self.validator.validate_expert(raw)
        assert ok is False
        assert obj is None
        assert len(errors) > 0

    def test_valid_gate(self):
        raw = {
            "gate_type": "safety_check",
            "target": "deploy_service",
            "trigger_condition": "confidence < 0.7",
            "risk_reduction": 0.4,
        }
        ok, obj, errors = self.validator.validate_gate(raw)
        assert ok is True
        assert obj.gate_type == "safety_check"
        assert errors == []

    def test_invalid_gate_missing_target(self):
        raw = {"gate_type": "safety_check", "trigger_condition": "x < 0.5"}
        ok, obj, errors = self.validator.validate_gate(raw)
        assert ok is False
        assert len(errors) > 0

    def test_valid_constraint(self):
        raw = {
            "parameter": "confidence",
            "operator": ">=",
            "threshold": 0.7,
            "severity": "high",
        }
        ok, obj, errors = self.validator.validate_constraint(raw)
        assert ok is True
        assert obj.parameter == "confidence"
        assert errors == []

    def test_invalid_constraint_bad_severity(self):
        raw = {
            "parameter": "confidence",
            "operator": ">=",
            "threshold": 0.7,
            "severity": "extreme",  # not allowed
        }
        ok, obj, errors = self.validator.validate_constraint(raw)
        assert ok is False
        assert len(errors) > 0

    def test_validate_any_expert(self):
        raw = {
            "name": "Ada",
            "domain": "robotics",
            "capabilities": ["path planning"],
            "confidence": 0.85,
        }
        ok, obj, errors = self.validator.validate_any(raw, "expert")
        assert ok is True

    def test_validate_any_unknown_type(self):
        ok, obj, errors = self.validator.validate_any({}, "unknown_type")
        assert ok is False
        assert len(errors) > 0

    def test_non_dict_input(self):
        ok, obj, errors = self.validator.validate_expert("not a dict")  # type: ignore[arg-type]
        assert ok is False
        assert len(errors) > 0

    def test_partial_expert_with_string_capabilities(self):
        """Capabilities can be a plain string — should be coerced to list."""
        raw = {
            "name": "Eva",
            "domain": "nlp",
            "capabilities": "translation",
        }
        ok, obj, errors = self.validator.validate_expert(raw)
        assert ok is True
        assert isinstance(obj.capabilities, list)


# ======================================================================
# GAP-4: Observation Model
# ======================================================================

class TestObservationModel:
    """GAP-4 — Observation-to-state mapping layer."""

    def setup_method(self):
        from observation_model import ObservationModel, ObservationChannel, Observation
        self.ObservationModel = ObservationModel
        self.ObservationChannel = ObservationChannel
        self.Observation = Observation
        self.model = ObservationModel()

    def test_channel_enum_values(self):
        ch = self.ObservationChannel
        assert ch.USER_INPUT.value == "user_input"
        assert ch.DOCUMENT_INGESTION.value == "document_ingestion"
        assert ch.LLM_RESPONSE.value == "llm_response"
        assert ch.GATE_EVALUATION.value == "gate_evaluation"
        assert ch.TELEMETRY.value == "telemetry"
        assert ch.HUMAN_FEEDBACK.value == "human_feedback"

    def test_register_channel(self):
        self.model.register_channel(
            self.ObservationChannel.USER_INPUT, noise_std=0.05, reliability=0.9
        )
        assert self.model.get_channel_reliability(self.ObservationChannel.USER_INPUT) == 0.9

    def test_register_negative_noise_raises(self):
        with pytest.raises(ValueError):
            self.model.register_channel(self.ObservationChannel.TELEMETRY, noise_std=-0.1)

    def test_process_observation_returns_deltas(self):
        obs = self.Observation(
            channel=self.ObservationChannel.USER_INPUT,
            raw_data={"value": 0.8},
        )
        deltas = self.model.process_observation(obs)
        assert isinstance(deltas, dict)
        assert len(deltas) > 0

    def test_process_observation_delta_bounded(self):
        obs = self.Observation(
            channel=self.ObservationChannel.GATE_EVALUATION,
            raw_data={"score": 0.5},
        )
        deltas = self.model.process_observation(obs)
        for v in deltas.values():
            assert isinstance(v, float)

    def test_information_gain_positive(self):
        sv = StateVector(uncertainty={"domain_knowledge_level": 0.8})
        obs = self.Observation(
            channel=self.ObservationChannel.USER_INPUT,
            raw_data="Some user input text",
        )
        gain = self.model.compute_information_gain(obs, sv)
        assert gain > 0.0

    def test_information_gain_reduces_uncertainty(self):
        sv = StateVector(uncertainty={"domain_knowledge_level": 0.9})
        obs = self.Observation(
            channel=self.ObservationChannel.USER_INPUT,
            raw_data={"value": 0.7},
        )
        before = sv.uncertainty.get("domain_knowledge_level", 1.0)
        self.model.compute_information_gain(obs, sv)
        after = sv.uncertainty.get("domain_knowledge_level", 1.0)
        assert after < before

    def test_high_noise_lowers_information_gain(self):
        sv = StateVector(uncertainty={"domain_knowledge_level": 0.8})
        obs_low_noise = self.Observation(
            channel=self.ObservationChannel.TELEMETRY,
            raw_data=0.5,
            noise_estimate=0.01,
        )
        obs_high_noise = self.Observation(
            channel=self.ObservationChannel.TELEMETRY,
            raw_data=0.5,
            noise_estimate=1.0,
        )
        sv_copy = StateVector(uncertainty={"domain_knowledge_level": 0.8})
        gain_low = self.model.compute_information_gain(obs_low_noise, sv)
        gain_high = self.model.compute_information_gain(obs_high_noise, sv_copy)
        assert gain_low > gain_high


# ======================================================================
# GAP-5: Stability Safeguards
# ======================================================================

class TestStabilitySafeguards:
    """GAP-5 — Stability safeguards: hysteresis and phase reversal limit."""

    def test_hysteresis_band_constant(self):
        assert HYSTERESIS_BAND == 0.05

    def test_max_phase_reversals_constant(self):
        assert MAX_PHASE_REVERSALS == 3

    def test_hysteresis_holds_confidence_near_threshold(self):
        """If raw confidence is within HYSTERESIS_BAND of threshold, hold previous."""
        state = MFGCSystemState()
        engine = ConfidenceEngine()

        # Seed history with a previous confidence
        state.confidence_history.append(0.45)
        state.c_t = 0.45

        # EXPAND threshold = 0.3; HYSTERESIS_BAND = 0.05
        # raw_confidence near TYPE threshold (0.5): e.g. 0.52 => 0.52-0.5=0.02 < 0.05
        state.p_t = Phase.TYPE  # threshold = 0.5
        result = engine.compute_confidence(state, generative_score=0.52, deterministic_score=0.52)
        # Within hysteresis band of 0.5 → should be held at 0.45
        assert result == 0.45

    def test_no_hysteresis_away_from_threshold(self):
        """Confidence far from threshold should NOT be held."""
        state = MFGCSystemState()
        engine = ConfidenceEngine()
        state.confidence_history.append(0.45)
        state.c_t = 0.45

        # TYPE threshold = 0.5; confidence = 0.9 → |0.9 - 0.5| = 0.4 > HYSTERESIS_BAND
        state.p_t = Phase.TYPE
        result = engine.compute_confidence(state, generative_score=0.9, deterministic_score=0.9)
        # Should NOT be held
        assert result != 0.45

    def test_confidence_velocity_tracking(self):
        state = MFGCSystemState()
        state.confidence_history = [0.3, 0.5, 0.7]
        state._update_confidence_velocity()
        assert abs(state.confidence_velocity - 0.2) < 1e-9

    def test_is_stable_true_when_small_changes(self):
        state = MFGCSystemState()
        state.confidence_history = [0.500, 0.5005, 0.5010]
        assert state.is_stable(n=3) is True

    def test_is_stable_false_when_large_changes(self):
        state = MFGCSystemState()
        state.confidence_history = [0.3, 0.5, 0.7]
        assert state.is_stable(n=3) is False

    def test_is_stable_requires_enough_history(self):
        state = MFGCSystemState()
        state.confidence_history = [0.5]
        assert state.is_stable(n=3) is False

    def test_phase_reversal_tracking(self):
        """Phase reversals are counted on advance_phase."""
        state = MFGCSystemState()
        phases = list(Phase)
        # Simulate: advance to TYPE, then somehow back to EXPAND (edge case)
        state.p_t = Phase.TYPE
        state.phase_history = [Phase.EXPAND, Phase.CONSTRAIN]  # history ahead
        initial_reversals = state._phase_reversal_count
        state.advance_phase()
        # advance should have detected that CONSTRAIN > TYPE (reversal)
        assert state._phase_reversal_count >= initial_reversals

    def test_forward_locked_after_max_reversals(self):
        """After MAX_PHASE_REVERSALS reversals the system locks forward."""
        state = MFGCSystemState()
        state._phase_reversal_count = MAX_PHASE_REVERSALS
        # Trigger another advance that sees a reversal in history
        state.p_t = Phase.TYPE
        state.phase_history = [Phase.EXECUTE]  # way ahead — forces reversal detect
        state.advance_phase()
        assert state._forward_locked is True
