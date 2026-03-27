"""
Tests for the MFGC Control Plane modules.

Covers:
- StateVector: creation, serialization, dimensionality, diff
- ObservationVector: creation, channel mapping
- ObservationMapping.map_to_state()
- ControlLaw.compute_control()
- StabilityMonitor oscillation detection
- FormalConstraint.evaluate()
- LLMOutputValidator: accepts valid, rejects invalid
- All new modules import correctly
"""

import os
import pytest



# ------------------------------------------------------------------ #
# Import verification
# ------------------------------------------------------------------ #


def test_all_modules_import():
    """All control_plane sub-modules must import without error."""
    from control_plane.state_vector import StateVector
    from control_plane.observation_model import (
        ObservationChannel,
        ObservationVector,
        ObservationNoise,
        ObservationMapping,
        information_gain,
    )
    from control_plane.control_loop import (
        ControlVector,
        ControlLaw,
        StabilityMonitor,
        StabilityViolation,
        ControlAuthorityMatrix,
    )
    from control_plane.formal_constraints import (
        FormalConstraint,
        MinimumConfidenceConstraint,
        MaximumRiskConstraint,
        LambdaConstraint,
        JurisdictionRegistry,
        ProbabilisticConstraintChecker,
    )
    from control_plane.llm_output_schemas import (
        ExpertGenerationOutput,
        GateProposalOutput,
        CandidateGenerationOutput,
        DomainAnalysisOutput,
        LLMOutputValidator,
        ConflictResolver,
        RegenerationTrigger,
    )


def test_control_plane_package_exports():
    """Top-level control_plane package must export all new symbols."""
    import control_plane
    assert hasattr(control_plane, 'StateVector')
    assert hasattr(control_plane, 'ObservationVector')
    assert hasattr(control_plane, 'ControlVector')
    assert hasattr(control_plane, 'ControlLaw')
    assert hasattr(control_plane, 'StabilityMonitor')
    assert hasattr(control_plane, 'FormalConstraint')
    assert hasattr(control_plane, 'LLMOutputValidator')


# ------------------------------------------------------------------ #
# StateVector
# ------------------------------------------------------------------ #


class TestStateVector:
    def test_default_creation(self):
        from control_plane.state_vector import StateVector
        sv = StateVector()
        assert sv.confidence == 0.0
        assert sv.version == 1

    def test_custom_values(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(confidence=0.8, authority=0.6, phase=0.5)
        assert sv.confidence == 0.8
        assert sv.authority == 0.6
        assert sv.phase == 0.5

    def test_dimensionality_base(self):
        from control_plane.state_vector import StateVector
        sv = StateVector()
        assert sv.dimensionality() == 10  # 10 base dims

    def test_dimensionality_with_extra(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(extra_dimensions={"custom_a": 0.3, "custom_b": 0.7})
        assert sv.dimensionality() == 12

    def test_to_vector_length(self):
        from control_plane.state_vector import StateVector
        sv = StateVector()
        vec = sv.to_vector()
        assert len(vec) == 10
        assert all(isinstance(v, float) for v in vec)

    def test_to_vector_extra_sorted(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(extra_dimensions={"z_dim": 0.9, "a_dim": 0.1})
        vec = sv.to_vector()
        assert len(vec) == 12
        # extra dims sorted by key: a_dim then z_dim
        assert vec[10] == pytest.approx(0.1)
        assert vec[11] == pytest.approx(0.9)

    def test_to_dict(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(confidence=0.7)
        d = sv.to_dict()
        assert d["confidence"] == pytest.approx(0.7)
        assert "phase" in d

    def test_diff(self):
        from control_plane.state_vector import StateVector
        a = StateVector(confidence=0.8, authority=0.5)
        b = StateVector(confidence=0.3, authority=0.2)
        d = a.diff(b)
        assert d["confidence"] == pytest.approx(0.5)
        assert d["authority"] == pytest.approx(0.3)

    def test_diff_symmetric(self):
        from control_plane.state_vector import StateVector
        a = StateVector(confidence=0.2)
        b = StateVector(confidence=0.9)
        assert a.diff(b)["confidence"] == pytest.approx(-0.7)
        assert b.diff(a)["confidence"] == pytest.approx(0.7)

    def test_with_update(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(confidence=0.5)
        sv2 = sv.with_update(confidence=0.9)
        assert sv.confidence == pytest.approx(0.5)
        assert sv2.confidence == pytest.approx(0.9)

    def test_version_field(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(version=3)
        assert sv.version == 3

    def test_timestamps_present(self):
        from control_plane.state_vector import StateVector
        sv = StateVector()
        assert sv.created_at is not None
        assert sv.updated_at is not None

    def test_invalid_confidence_rejected(self):
        from control_plane.state_vector import StateVector
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            StateVector(confidence=1.5)

    def test_serialization_round_trip(self):
        from control_plane.state_vector import StateVector
        sv = StateVector(confidence=0.6, murphy_index=0.4)
        d = sv.model_dump()
        sv2 = StateVector(**d)
        assert sv2.confidence == pytest.approx(sv.confidence)
        assert sv2.murphy_index == pytest.approx(sv.murphy_index)


# ------------------------------------------------------------------ #
# ObservationVector + channel mapping
# ------------------------------------------------------------------ #


class TestObservationModel:
    def test_observation_vector_default(self):
        from control_plane.observation_model import ObservationVector
        ov = ObservationVector()
        assert ov.user_input_signal is None
        assert ov.llm_response_quality is None

    def test_observation_vector_with_values(self):
        from control_plane.observation_model import ObservationVector
        ov = ObservationVector(user_input_signal=0.8, llm_response_quality=0.6)
        assert ov.user_input_signal == pytest.approx(0.8)
        assert ov.llm_response_quality == pytest.approx(0.6)

    def test_active_channels_filters_none(self):
        from control_plane.observation_model import ObservationVector, ObservationChannel
        ov = ObservationVector(user_input_signal=0.5)
        active = ov.active_channels()
        assert ObservationChannel.USER_INPUT in active
        assert len(active) == 1

    def test_observation_channel_enum_members(self):
        from control_plane.observation_model import ObservationChannel
        assert ObservationChannel.USER_INPUT.value == "user_input"
        assert ObservationChannel.LLM_RESPONSE_QUALITY.value == "llm_response_quality"
        assert ObservationChannel.GATE_EVALUATION_RESULT.value == "gate_evaluation_result"

    def test_observation_noise_dataclass(self):
        from control_plane.observation_model import ObservationChannel, ObservationNoise
        noise = ObservationNoise(channel=ObservationChannel.TELEMETRY_READING, sigma=0.1)
        assert noise.sigma == pytest.approx(0.1)
        assert noise.confidence_lower <= 0.0
        assert noise.confidence_upper >= 0.0

    def test_map_to_state_updates_dimension(self):
        from control_plane.observation_model import ObservationVector, ObservationMapping
        from control_plane.state_vector import StateVector
        prior = StateVector(confidence=0.3)
        obs = ObservationVector(llm_response_quality=0.9)
        mapping = ObservationMapping()
        posterior = mapping.map_to_state(obs, prior)
        # LLM quality → confidence dimension; should increase
        assert posterior.confidence > prior.confidence

    def test_map_to_state_empty_observation(self):
        from control_plane.observation_model import ObservationVector, ObservationMapping
        from control_plane.state_vector import StateVector
        prior = StateVector(confidence=0.5)
        obs = ObservationVector()
        mapping = ObservationMapping()
        posterior = mapping.map_to_state(obs, prior)
        assert posterior.confidence == pytest.approx(prior.confidence)

    def test_information_gain_positive(self):
        from control_plane.observation_model import information_gain
        from control_plane.state_vector import StateVector
        state = StateVector(confidence=0.3, information_completeness=0.2)
        gain = information_gain("What is the primary domain constraint?", state)
        assert gain > 0.0

    def test_information_gain_trivial_question(self):
        from control_plane.observation_model import information_gain
        from control_plane.state_vector import StateVector
        state = StateVector(confidence=0.3)
        gain = information_gain("ok", state)
        assert gain >= 0.0


# ------------------------------------------------------------------ #
# ControlLaw + StabilityMonitor
# ------------------------------------------------------------------ #


class TestControlLaw:
    def test_compute_control_returns_control_vector(self):
        from control_plane.control_loop import ControlLaw, ControlVector
        from control_plane.state_vector import StateVector
        law = ControlLaw(gain=1.0, threshold=0.05)
        state = StateVector(confidence=0.3, information_completeness=0.2)
        target = StateVector(confidence=0.9, information_completeness=0.9)
        cv = law.compute_control(state, target)
        assert isinstance(cv, ControlVector)

    def test_compute_control_activates_ask_question(self):
        from control_plane.control_loop import ControlLaw
        from control_plane.state_vector import StateVector
        law = ControlLaw(gain=1.0, threshold=0.05)
        state = StateVector(information_completeness=0.1)
        target = StateVector(information_completeness=0.9)
        cv = law.compute_control(state, target)
        assert cv.ask_question is True

    def test_compute_control_execute_when_close(self):
        from control_plane.control_loop import ControlLaw
        from control_plane.state_vector import StateVector
        law = ControlLaw(gain=1.0, threshold=0.1)
        # State nearly equal to target
        state = StateVector(confidence=0.99, information_completeness=0.99)
        target = StateVector(confidence=1.0, information_completeness=1.0)
        cv = law.compute_control(state, target)
        assert cv.execute_action is True

    def test_control_vector_is_null_when_no_actions(self):
        from control_plane.control_loop import ControlVector
        cv = ControlVector()
        assert cv.is_null()


class TestStabilityMonitor:
    def test_no_violation_when_monotone(self):
        from control_plane.control_loop import StabilityMonitor
        monitor = StabilityMonitor(max_reversals=3)
        for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
            monitor.record(v)  # should not raise

    def test_violation_on_oscillation(self):
        from control_plane.control_loop import StabilityMonitor, StabilityViolation
        monitor = StabilityMonitor(max_reversals=2, min_net_gain=0.5)
        # Oscillate: up, down, up, down
        pattern = [0.5, 0.6, 0.4, 0.6, 0.4]
        with pytest.raises(StabilityViolation):
            for v in pattern:
                monitor.record(v)

    def test_reversal_count_tracked(self):
        from control_plane.control_loop import StabilityMonitor, StabilityViolation
        monitor = StabilityMonitor(max_reversals=10, min_net_gain=0.0)
        try:
            for v in [0.5, 0.6, 0.4, 0.6, 0.4]:
                monitor.record(v)
        except StabilityViolation:
            pass
        assert monitor.reversal_count >= 1

    def test_reset_clears_state(self):
        from control_plane.control_loop import StabilityMonitor
        monitor = StabilityMonitor(max_reversals=2, min_net_gain=0.5)
        monitor.record(0.5)
        monitor.record(0.6)
        monitor.reset()
        assert monitor.reversal_count == 0


class TestControlAuthorityMatrix:
    def test_default_no_authority(self):
        from control_plane.control_loop import ControlAuthorityMatrix
        cam = ControlAuthorityMatrix()
        assert not cam.is_permitted("agent_1", "execute_action")

    def test_registered_actor_permitted(self):
        from control_plane.control_loop import ControlAuthorityMatrix
        cam = ControlAuthorityMatrix()
        cam.register_actor("agent_1", authority_level=3)
        assert cam.is_permitted("agent_1", "execute_action")

    def test_insufficient_level_denied(self):
        from control_plane.control_loop import ControlAuthorityMatrix
        cam = ControlAuthorityMatrix()
        cam.register_actor("agent_1", authority_level=1)
        assert not cam.is_permitted("agent_1", "execute_action")

    def test_explicit_grant(self):
        from control_plane.control_loop import ControlAuthorityMatrix
        cam = ControlAuthorityMatrix()
        cam.register_actor("agent_1", authority_level=0)
        cam.grant("agent_1", "ask_question")
        assert cam.is_permitted("agent_1", "ask_question")

    def test_explicit_revoke(self):
        from control_plane.control_loop import ControlAuthorityMatrix
        cam = ControlAuthorityMatrix()
        cam.register_actor("agent_1", authority_level=3)
        cam.revoke("agent_1", "execute_action")
        assert not cam.is_permitted("agent_1", "execute_action")


# ------------------------------------------------------------------ #
# FormalConstraints
# ------------------------------------------------------------------ #


class TestFormalConstraints:
    def test_minimum_confidence_satisfied(self):
        from control_plane.formal_constraints import MinimumConfidenceConstraint
        from control_plane.state_vector import StateVector
        c = MinimumConfidenceConstraint(threshold=0.5)
        state = StateVector(confidence=0.8)
        assert c.evaluate(state) <= 0.0
        assert c.is_satisfied(state)

    def test_minimum_confidence_violated(self):
        from control_plane.formal_constraints import MinimumConfidenceConstraint
        from control_plane.state_vector import StateVector
        c = MinimumConfidenceConstraint(threshold=0.5)
        state = StateVector(confidence=0.3)
        assert c.evaluate(state) > 0.0
        assert not c.is_satisfied(state)

    def test_maximum_risk_satisfied(self):
        from control_plane.formal_constraints import MaximumRiskConstraint
        from control_plane.state_vector import StateVector
        c = MaximumRiskConstraint(threshold=0.7)
        state = StateVector(risk_exposure=0.4)
        assert c.evaluate(state) <= 0.0
        assert c.is_satisfied(state)

    def test_maximum_risk_violated(self):
        from control_plane.formal_constraints import MaximumRiskConstraint
        from control_plane.state_vector import StateVector
        c = MaximumRiskConstraint(threshold=0.7)
        state = StateVector(risk_exposure=0.9)
        assert c.evaluate(state) > 0.0
        assert not c.is_satisfied(state)

    def test_lambda_constraint(self):
        from control_plane.formal_constraints import LambdaConstraint
        from control_plane.state_vector import StateVector
        c = LambdaConstraint(
            name="phase_threshold",
            g=lambda s: s.phase - 0.5,
        )
        assert c.is_satisfied(StateVector(phase=0.3))
        assert not c.is_satisfied(StateVector(phase=0.8))

    def test_jurisdiction_registry(self):
        from control_plane.formal_constraints import (
            JurisdictionRegistry,
            MinimumConfidenceConstraint,
            MaximumRiskConstraint,
        )
        from control_plane.state_vector import StateVector
        reg = JurisdictionRegistry()
        reg.register("EU", MinimumConfidenceConstraint(0.4))
        reg.register("EU", MaximumRiskConstraint(0.8))
        state = StateVector(confidence=0.6, risk_exposure=0.3)
        assert reg.all_satisfied("EU", state)
        assert "EU" in reg.list_jurisdictions()

    def test_probabilistic_checker(self):
        from control_plane.formal_constraints import (
            ProbabilisticConstraintChecker,
            MinimumConfidenceConstraint,
        )
        from control_plane.state_vector import StateVector
        checker = ProbabilisticConstraintChecker(n_samples=100, seed=7)
        c = MinimumConfidenceConstraint(threshold=0.2)
        state = StateVector(confidence=0.9)
        prob = checker.probability_satisfied(c, state, uncertainty=0.05)
        # With high confidence and low threshold, probability should be high
        assert prob > 0.8

    def test_probabilistic_checker_low_confidence(self):
        from control_plane.formal_constraints import (
            ProbabilisticConstraintChecker,
            MinimumConfidenceConstraint,
        )
        from control_plane.state_vector import StateVector
        checker = ProbabilisticConstraintChecker(n_samples=100, seed=9)
        c = MinimumConfidenceConstraint(threshold=0.9)
        state = StateVector(confidence=0.1)
        prob = checker.probability_satisfied(c, state, uncertainty=0.05)
        # With very low confidence, constraint almost certainly violated
        assert prob < 0.2


# ------------------------------------------------------------------ #
# LLM Output Schemas + Validator
# ------------------------------------------------------------------ #


class TestLLMOutputSchemas:
    def test_expert_generation_output_valid(self):
        from control_plane.llm_output_schemas import ExpertGenerationOutput
        output = ExpertGenerationOutput(
            expert_name="Dr. Smith",
            domain="biomedical",
            confidence=0.9,
        )
        assert output.expert_name == "Dr. Smith"
        assert output.domain == "biomedical"

    def test_gate_proposal_output_valid(self):
        from control_plane.llm_output_schemas import GateProposalOutput
        output = GateProposalOutput(
            gate_id="g-001",
            gate_name="Regulatory Gate",
            gate_type="compliance",
            severity="high",
        )
        assert output.severity == "high"

    def test_gate_proposal_invalid_severity(self):
        from control_plane.llm_output_schemas import GateProposalOutput
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            GateProposalOutput(
                gate_id="g-001",
                gate_name="Bad Gate",
                gate_type="test",
                severity="extreme",  # invalid
            )

    def test_candidate_generation_output(self):
        from control_plane.llm_output_schemas import CandidateGenerationOutput
        output = CandidateGenerationOutput(
            candidates=[{"id": "c1", "score": 0.8}],
            confidence=0.7,
        )
        assert len(output.candidates) == 1

    def test_domain_analysis_output(self):
        from control_plane.llm_output_schemas import DomainAnalysisOutput
        output = DomainAnalysisOutput(
            domain="finance",
            complexity_score=0.8,
            key_entities=["market", "risk"],
        )
        assert output.complexity_score == pytest.approx(0.8)


class TestLLMOutputValidator:
    def test_validate_valid_output(self):
        from control_plane.llm_output_schemas import LLMOutputValidator, ExpertGenerationOutput
        validator = LLMOutputValidator()
        raw = {"expert_name": "Dr. Jones", "domain": "law", "confidence": 0.85}
        valid, model, errors = validator.validate(raw, ExpertGenerationOutput)
        assert valid is True
        assert model is not None
        assert errors == []

    def test_validate_invalid_output(self):
        from control_plane.llm_output_schemas import LLMOutputValidator, ExpertGenerationOutput
        validator = LLMOutputValidator()
        raw = {"expert_name": "Dr. Jones"}  # missing required 'domain'
        valid, model, errors = validator.validate(raw, ExpertGenerationOutput)
        assert valid is False
        assert model is None
        assert len(errors) > 0

    def test_validate_confidence_out_of_range(self):
        from control_plane.llm_output_schemas import LLMOutputValidator, ExpertGenerationOutput
        validator = LLMOutputValidator()
        raw = {"expert_name": "Dr. Jones", "domain": "law", "confidence": 2.5}
        valid, model, errors = validator.validate(raw, ExpertGenerationOutput)
        assert valid is False

    def test_conflict_resolver_averages_floats(self):
        from control_plane.llm_output_schemas import ConflictResolver
        resolver = ConflictResolver()
        outputs = [{"confidence": 0.6}, {"confidence": 0.8}]
        merged = resolver.resolve(outputs)
        assert merged["confidence"] == pytest.approx(0.7)

    def test_conflict_resolver_union_lists(self):
        from control_plane.llm_output_schemas import ConflictResolver
        resolver = ConflictResolver()
        outputs = [
            {"tags": ["a", "b"]},
            {"tags": ["b", "c"]},
        ]
        merged = resolver.resolve(outputs)
        assert set(merged["tags"]) == {"a", "b", "c"}

    def test_regeneration_trigger_on_invalid(self):
        from control_plane.llm_output_schemas import RegenerationTrigger
        trigger = RegenerationTrigger(confidence_threshold=0.5, max_retries=3)
        assert trigger.should_regenerate({}, is_valid=False, call_id="call1")

    def test_regeneration_trigger_on_low_confidence(self):
        from control_plane.llm_output_schemas import RegenerationTrigger
        trigger = RegenerationTrigger(confidence_threshold=0.5, max_retries=3)
        output = {"confidence": 0.2}
        assert trigger.should_regenerate(output, is_valid=True, call_id="call2")

    def test_regeneration_trigger_stops_at_max_retries(self):
        from control_plane.llm_output_schemas import RegenerationTrigger
        trigger = RegenerationTrigger(confidence_threshold=0.5, max_retries=2)
        output = {"confidence": 0.1}
        trigger.should_regenerate(output, is_valid=True, call_id="call3")
        trigger.should_regenerate(output, is_valid=True, call_id="call3")
        # Third call should return False (max_retries reached)
        assert not trigger.should_regenerate(output, is_valid=True, call_id="call3")

    def test_regeneration_trigger_no_regen_on_good_output(self):
        from control_plane.llm_output_schemas import RegenerationTrigger
        trigger = RegenerationTrigger(confidence_threshold=0.5, max_retries=3)
        output = {"confidence": 0.9}
        assert not trigger.should_regenerate(output, is_valid=True, call_id="call4")
