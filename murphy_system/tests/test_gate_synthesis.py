"""
Comprehensive test suite for Gate Synthesis Engine
Tests all critical functionality including adversarial scenarios
"""

import pytest
import os

# Add src to path

from gate_synthesis.models import (
    Gate,
    GateType,
    GateCategory,
    GateState,
    FailureMode,
    FailureModeType,
    RiskVector,
    ExposureSignal,
    RetirementCondition
)

from gate_synthesis.failure_mode_enumerator import FailureModeEnumerator
from gate_synthesis.murphy_estimator import MurphyProbabilityEstimator
from gate_synthesis.gate_generator import GateGenerator
from gate_synthesis.gate_lifecycle_manager import GateLifecycleManager

from confidence_engine.models import (
    ArtifactGraph,
    ArtifactNode,
    ArtifactType,
    ArtifactSource,
    Phase,
    ConfidenceState,
    AuthorityBand
)


class TestFailureModeEnumeration:
    """Test failure mode enumeration"""

    def test_semantic_drift_detection(self):
        """Test semantic drift detection"""
        enumerator = FailureModeEnumerator()
        graph = ArtifactGraph()

        # Add multiple unverified hypotheses
        for i in range(5):
            node = ArtifactNode(
                id=f"h{i}",
                type=ArtifactType.HYPOTHESIS,
                source=ArtifactSource.LLM,
                content={"text": f"Hypothesis {i}"}
            )
            graph.add_node(node)

        # High instability state
        confidence_state = ConfidenceState(
            confidence=0.3,
            generative_score=0.4,
            deterministic_score=0.2,
            epistemic_instability=0.7,
            phase=Phase.EXPAND
        )
        confidence_state.total_artifacts = 5
        confidence_state.verified_artifacts = 0

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.GENERATE,
            None
        )

        # Should detect semantic drift
        assert len(failure_modes) > 0
        assert any(fm.type == FailureModeType.SEMANTIC_DRIFT for fm in failure_modes)

    def test_authority_misuse_detection(self):
        """Test authority misuse detection"""
        enumerator = FailureModeEnumerator()
        graph = ArtifactGraph()

        # Low confidence but high authority
        confidence_state = ConfidenceState(
            confidence=0.4,
            generative_score=0.5,
            deterministic_score=0.3,
            epistemic_instability=0.3,
            phase=Phase.EXECUTE
        )

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.EXECUTE,  # High authority
            None
        )

        # Should detect authority misuse
        assert any(fm.type == FailureModeType.AUTHORITY_MISUSE for fm in failure_modes)

    def test_irreversible_action_detection(self):
        """Test irreversible action detection"""
        enumerator = FailureModeEnumerator()
        graph = ArtifactGraph()

        confidence_state = ConfidenceState(
            confidence=0.7,
            generative_score=0.7,
            deterministic_score=0.7,
            epistemic_instability=0.2,
            phase=Phase.EXECUTE
        )

        # Irreversible exposure
        exposure_signal = ExposureSignal(
            signal_id="test",
            external_side_effects=True,
            reversibility=0.2,  # Low reversibility
            blast_radius_estimate=0.6
        )

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.EXECUTE,
            exposure_signal
        )

        # Should detect irreversible action
        assert any(fm.type == FailureModeType.IRREVERSIBLE_ACTION for fm in failure_modes)


class TestMurphyProbabilityEstimation:
    """Test Murphy probability estimation"""

    def test_sigmoid_calculation(self):
        """Test sigmoid probability calculation"""
        estimator = MurphyProbabilityEstimator()

        # High risk vector
        high_risk = RiskVector(H=0.8, one_minus_D=0.7, exposure=0.6, authority_risk=0.7)
        high_prob = estimator.estimate_murphy_probability(high_risk)

        # Low risk vector
        low_risk = RiskVector(H=0.1, one_minus_D=0.1, exposure=0.1, authority_risk=0.1)
        low_prob = estimator.estimate_murphy_probability(low_risk)

        assert 0.0 <= high_prob <= 1.0
        assert 0.0 <= low_prob <= 1.0
        assert high_prob > low_prob

    def test_gate_required_threshold(self):
        """Test gate required threshold"""
        estimator = MurphyProbabilityEstimator()

        # Above threshold
        high_risk = RiskVector(H=0.7, one_minus_D=0.6, exposure=0.5, authority_risk=0.6)
        high_prob = estimator.estimate_murphy_probability(high_risk)

        assert estimator.requires_gate(high_prob) == True

        # Below threshold - use very low values
        low_risk = RiskVector(H=0.0, one_minus_D=0.0, exposure=0.0, authority_risk=0.0)
        low_prob = estimator.estimate_murphy_probability(low_risk)

        assert estimator.requires_gate(low_prob) == False

    def test_risk_path_forecasting(self):
        """Test risk path forecasting"""
        estimator = MurphyProbabilityEstimator()

        risk_vector = RiskVector(H=0.5, one_minus_D=0.4, exposure=0.3, authority_risk=0.4)

        failure_mode = FailureMode(
            id="fm1",
            type=FailureModeType.SEMANTIC_DRIFT,
            probability=0.6,
            impact=0.7,
            risk_vector=risk_vector,
            description="Test failure mode"
        )

        risk_path = estimator.forecast_risk_path(
            [failure_mode],
            ["step1", "step2", "step3"]
        )

        assert risk_path.cumulative_risk > 0.0
        assert risk_path.likelihood > 0.0
        assert len(risk_path.steps) == 3


class TestGateGeneration:
    """Test gate generation"""

    def test_semantic_stability_gate(self):
        """Test semantic stability gate generation"""
        generator = GateGenerator()

        risk_vector = RiskVector(H=0.7, one_minus_D=0.3, exposure=0.2, authority_risk=0.3)

        failure_mode = FailureMode(
            id="fm1",
            type=FailureModeType.SEMANTIC_DRIFT,
            probability=0.7,
            impact=0.6,
            risk_vector=risk_vector,
            description="Semantic drift detected"
        )

        gate = generator.generate_semantic_stability_gate(
            failure_mode,
            Phase.EXPAND,
            0.7
        )

        assert gate.type == GateType.CONSTRAINT
        assert gate.category == GateCategory.SEMANTIC_STABILITY
        assert gate.state == GateState.PROPOSED
        assert len(gate.retirement_conditions) > 0

    def test_verification_gate(self):
        """Test verification gate generation"""
        generator = GateGenerator()

        risk_vector = RiskVector(H=0.3, one_minus_D=0.7, exposure=0.2, authority_risk=0.3)

        failure_mode = FailureMode(
            id="fm2",
            type=FailureModeType.VERIFICATION_INSUFFICIENT,
            probability=0.6,
            impact=0.7,
            risk_vector=risk_vector,
            description="Insufficient verification"
        )

        gate = generator.generate_verification_gate(
            failure_mode,
            Phase.EXECUTE,
            0.6
        )

        assert gate.type == GateType.VERIFICATION
        assert gate.category == GateCategory.VERIFICATION_REQUIRED

    def test_authority_decay_gate(self):
        """Test authority decay gate generation"""
        generator = GateGenerator()

        risk_vector = RiskVector(H=0.3, one_minus_D=0.3, exposure=0.2, authority_risk=0.7)

        failure_mode = FailureMode(
            id="fm3",
            type=FailureModeType.AUTHORITY_MISUSE,
            probability=0.7,
            impact=0.8,
            risk_vector=risk_vector,
            description="Authority misuse"
        )

        gate = generator.generate_authority_decay_gate(
            failure_mode,
            AuthorityBand.EXECUTE,
            0.7
        )

        assert gate.type == GateType.AUTHORITY
        assert gate.category == GateCategory.AUTHORITY_DECAY
        assert 'downgrade_authority' in gate.enforcement_effect['action']

    def test_isolation_gate(self):
        """Test isolation gate generation"""
        generator = GateGenerator()

        risk_vector = RiskVector(H=0.2, one_minus_D=0.2, exposure=0.8, authority_risk=0.3)

        failure_mode = FailureMode(
            id="fm4",
            type=FailureModeType.BLAST_RADIUS_EXCEEDED,
            probability=0.8,
            impact=0.9,
            risk_vector=risk_vector,
            description="Blast radius exceeded"
        )

        gate = generator.generate_isolation_gate(
            failure_mode,
            0.8
        )

        assert gate.type == GateType.ISOLATION
        assert gate.category == GateCategory.ISOLATION_REQUIRED
        assert gate.priority >= 8  # High priority


class TestGateLifecycle:
    """Test gate lifecycle management"""

    def test_gate_activation(self):
        """Test gate activation"""
        manager = GateLifecycleManager()

        gate = Gate(
            id="test_gate",
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target="test_target",
            trigger_condition={},
            enforcement_effect={},
            state=GateState.PROPOSED
        )

        manager.add_gate(gate)
        success = manager.activate_gate("test_gate")

        assert success == True
        assert gate.state == GateState.ACTIVE
        assert gate.activated_at is not None

    def test_gate_retirement(self):
        """Test gate retirement"""
        manager = GateLifecycleManager()

        gate = Gate(
            id="test_gate",
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target="test_target",
            trigger_condition={},
            enforcement_effect={},
            state=GateState.ACTIVE
        )
        gate.activated_at = gate.created_at

        manager.add_gate(gate)

        # Mark as satisfied
        gate.state = GateState.SATISFIED

        success = manager.retire_gate("test_gate", "Test retirement")

        assert success == True
        assert gate.state == GateState.RETIRED
        assert gate.retired_at is not None

    def test_retirement_conditions(self):
        """Test retirement condition checking"""
        manager = GateLifecycleManager()

        gate = Gate(
            id="test_gate",
            type=GateType.VERIFICATION,
            category=GateCategory.VERIFICATION_REQUIRED,
            target="test_target",
            trigger_condition={},
            enforcement_effect={},
            state=GateState.ACTIVE,
            retirement_conditions=[
                RetirementCondition(
                    condition_type='verification_success',
                    threshold=0.7,
                    current_value=0.0
                )
            ]
        )
        gate.activated_at = gate.created_at

        manager.add_gate(gate)

        # Update with value below threshold
        can_retire = manager.update_retirement_conditions(
            "test_gate",
            {'verification_success': 0.5}
        )
        assert can_retire == False

        # Update with value above threshold
        can_retire = manager.update_retirement_conditions(
            "test_gate",
            {'verification_success': 0.8}
        )
        assert can_retire == True

    def test_conflict_resolution(self):
        """Test gate conflict resolution"""
        manager = GateLifecycleManager()

        # Create two gates for same target
        gate1 = Gate(
            id="gate1",
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target="same_target",
            trigger_condition={},
            enforcement_effect={},
            priority=5
        )

        gate2 = Gate(
            id="gate2",
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target="same_target",
            trigger_condition={},
            enforcement_effect={},
            priority=8  # Higher priority
        )

        resolved = manager.resolve_conflicts([gate1, gate2])

        # Should keep higher priority gate
        assert len(resolved) == 1
        assert resolved[0].id == "gate2"


class TestAdversarialScenarios:
    """Test adversarial scenarios"""

    def test_conflicting_constraints(self):
        """Test system response to conflicting constraints"""
        enumerator = FailureModeEnumerator()
        graph = ArtifactGraph()

        # Add conflicting constraints
        c1 = ArtifactNode(
            id="c1",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must allow access"}
        )
        c2 = ArtifactNode(
            id="c2",
            type=ArtifactType.CONSTRAINT,
            source=ArtifactSource.HUMAN,
            content={"rule": "System must deny access"}
        )

        graph.add_node(c1)
        graph.add_node(c2)

        confidence_state = ConfidenceState(
            confidence=0.5,
            generative_score=0.5,
            deterministic_score=0.5,
            epistemic_instability=0.6,
            phase=Phase.EXPAND
        )

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.GENERATE,
            None
        )

        # Should detect constraint violations
        assert len(failure_modes) > 0

    def test_fake_confidence_spike(self):
        """Test system response to fake confidence spike"""
        enumerator = FailureModeEnumerator()
        estimator = MurphyProbabilityEstimator()
        graph = ArtifactGraph()

        # High confidence but no verification
        confidence_state = ConfidenceState(
            confidence=0.9,  # High confidence
            generative_score=0.95,
            deterministic_score=0.2,  # Low verification
            epistemic_instability=0.1,
            phase=Phase.EXECUTE
        )
        confidence_state.verified_artifacts = 0
        confidence_state.total_artifacts = 10

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.EXECUTE,
            None
        )

        # Should detect verification insufficient
        assert any(fm.type == FailureModeType.VERIFICATION_INSUFFICIENT for fm in failure_modes)

        # Murphy probability should be high
        for fm in failure_modes:
            if fm.type == FailureModeType.VERIFICATION_INSUFFICIENT:
                murphy_prob = estimator.estimate_failure_mode_probability(fm)
                assert murphy_prob > 0.5

    def test_rapid_authority_escalation(self):
        """Test system response to rapid authority escalation"""
        enumerator = FailureModeEnumerator()
        generator = GateGenerator()

        graph = ArtifactGraph()

        # Low confidence but trying to escalate to execute
        confidence_state = ConfidenceState(
            confidence=0.4,
            generative_score=0.5,
            deterministic_score=0.3,
            epistemic_instability=0.4,
            phase=Phase.EXECUTE
        )

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.EXECUTE,  # Trying to execute
            None
        )

        # Should detect authority misuse
        authority_misuse = [fm for fm in failure_modes
                           if fm.type == FailureModeType.AUTHORITY_MISUSE]
        assert len(authority_misuse) > 0

        # Should generate authority decay gate
        murphy_probs = {fm.id: 0.7 for fm in failure_modes}
        gates = generator.generate_gates(
            failure_modes,
            Phase.EXECUTE,
            AuthorityBand.EXECUTE,
            murphy_probs
        )

        authority_gates = [g for g in gates
                          if g.category == GateCategory.AUTHORITY_DECAY]
        assert len(authority_gates) > 0

    def test_delayed_verification(self):
        """Test system response to delayed verification"""
        manager = GateLifecycleManager()

        # Create verification gate
        gate = Gate(
            id="verify_gate",
            type=GateType.VERIFICATION,
            category=GateCategory.VERIFICATION_REQUIRED,
            target="artifacts",
            trigger_condition={},
            enforcement_effect={},
            state=GateState.ACTIVE,
            retirement_conditions=[
                RetirementCondition(
                    condition_type='verification_success',
                    threshold=0.7,
                    current_value=0.0
                )
            ]
        )
        gate.activated_at = gate.created_at

        manager.add_gate(gate)

        # Verification delayed - gate should remain active
        can_retire = manager.update_retirement_conditions(
            "verify_gate",
            {'verification_success': 0.3}  # Still low
        )

        assert can_retire == False
        assert gate.state == GateState.ACTIVE

    def test_irreversible_action_proposal(self):
        """Test system response to irreversible action proposal"""
        enumerator = FailureModeEnumerator()
        generator = GateGenerator()
        estimator = MurphyProbabilityEstimator()

        graph = ArtifactGraph()

        confidence_state = ConfidenceState(
            confidence=0.8,
            generative_score=0.8,
            deterministic_score=0.8,
            epistemic_instability=0.1,
            phase=Phase.EXECUTE
        )

        # Irreversible action with high blast radius
        exposure_signal = ExposureSignal(
            signal_id="irreversible",
            external_side_effects=True,
            reversibility=0.1,  # Nearly irreversible
            blast_radius_estimate=0.9  # High blast radius
        )

        failure_modes = enumerator.enumerate_failure_modes(
            graph,
            confidence_state,
            AuthorityBand.EXECUTE,
            exposure_signal
        )

        # Should detect both irreversible action and blast radius
        assert any(fm.type == FailureModeType.IRREVERSIBLE_ACTION for fm in failure_modes)
        assert any(fm.type == FailureModeType.BLAST_RADIUS_EXCEEDED for fm in failure_modes)

        # Should generate isolation gates with high priority
        murphy_probs = {fm.id: estimator.estimate_failure_mode_probability(fm)
                       for fm in failure_modes}
        gates = generator.generate_gates(
            failure_modes,
            Phase.EXECUTE,
            AuthorityBand.EXECUTE,
            murphy_probs
        )

        isolation_gates = [g for g in gates
                          if g.category == GateCategory.ISOLATION_REQUIRED]
        assert len(isolation_gates) > 0
        assert all(g.priority >= 8 for g in isolation_gates)  # High priority


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
