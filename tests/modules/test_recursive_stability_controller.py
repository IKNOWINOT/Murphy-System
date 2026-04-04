"""
Tests for Recursive Stability Controller

Comprehensive test suite covering:
- State normalization
- Recursion energy estimation
- Stability score calculation
- Lyapunov monitoring
- Spawn control
- Gate damping
- Feedback isolation
- Control signal generation
"""

import pytest
import time
from src.recursive_stability_controller.state_variables import (
    StateVariables, StateNormalizer, NormalizedState
)
from src.recursive_stability_controller.recursion_energy import (
    RecursionEnergyEstimator, RecursionEnergyCoefficients
)
from src.recursive_stability_controller.stability_score import (
    StabilityScoreCalculator
)
from src.recursive_stability_controller.lyapunov_monitor import (
    LyapunovMonitor
)
from src.recursive_stability_controller.spawn_controller import (
    SpawnRateController, SpawnRequest
)
from src.recursive_stability_controller.gate_damping import (
    GateDampingController, GateSynthesisRequest
)
from src.recursive_stability_controller.feedback_isolation import (
    FeedbackIsolationRouter, Entity, Artifact, EvaluationRequest, EntityType
)
from src.recursive_stability_controller.control_signals import (
    ControlSignalGenerator, ControlMode
)


class TestStateNormalization:
    """Test state variable normalization"""

    def test_normalize_valid_state(self):
        """Test normalization of valid state"""
        normalizer = StateNormalizer()

        state = StateVariables(
            active_agents=50,
            active_gates=500,
            feedback_entropy=5.0,
            confidence=0.8,
            murphy_index=0.2,
            timestamp=time.time(),
            cycle_id=1
        )

        normalized = normalizer.normalize(state)

        assert normalized is not None
        assert 0.0 <= normalized.A_t <= 1.0
        assert 0.0 <= normalized.G_t <= 1.0
        assert 0.0 <= normalized.E_t <= 1.0
        assert normalized.C_t == 0.8
        assert normalized.M_t == 0.2

    def test_normalize_clamping(self):
        """Test clamping of out-of-range values"""
        normalizer = StateNormalizer()

        state = StateVariables(
            active_agents=150,  # Exceeds max (100)
            active_gates=1500,  # Exceeds max (1000)
            feedback_entropy=15.0,  # Exceeds max (10)
            confidence=0.8,
            murphy_index=0.2,
            timestamp=time.time(),
            cycle_id=1
        )

        normalized = normalizer.normalize(state)

        assert normalized is not None
        assert normalized.A_t == 1.0  # Clamped
        assert normalized.G_t == 1.0  # Clamped
        assert normalized.E_t == 1.0  # Clamped
        assert len(normalizer.get_alerts()) == 3  # 3 clamp alerts


class TestRecursionEnergy:
    """Test recursion energy estimation"""

    def test_estimate_energy(self):
        """Test recursion energy estimation"""
        estimator = RecursionEnergyEstimator()

        state = NormalizedState(
            A_t=0.5,
            G_t=0.5,
            E_t=0.4,
            C_t=0.7,
            M_t=0.3,
            timestamp=time.time(),
            cycle_id=1,
            raw_agents=50,
            raw_gates=500,
            raw_entropy=4.0
        )

        R_t = estimator.estimate(state)

        # R_t = 0.3*0.5 + 0.2*0.5 + 0.4*0.4 + 0.5*0.3 - 0.6*0.7
        # R_t = 0.15 + 0.1 + 0.16 + 0.15 - 0.42 = 0.14
        assert R_t >= 0.0
        assert 0.0 <= R_t <= 2.0  # Reasonable range

    def test_energy_breakdown(self):
        """Test recursion energy breakdown"""
        estimator = RecursionEnergyEstimator()

        state = NormalizedState(
            A_t=0.5,
            G_t=0.5,
            E_t=0.4,
            C_t=0.7,
            M_t=0.3,
            timestamp=time.time(),
            cycle_id=1,
            raw_agents=50,
            raw_gates=500,
            raw_entropy=4.0
        )

        breakdown = estimator.estimate_with_breakdown(state)

        assert "R_t" in breakdown
        assert "agent_contribution" in breakdown
        assert "gate_contribution" in breakdown
        assert "entropy_contribution" in breakdown
        assert "murphy_contribution" in breakdown
        assert "confidence_contribution" in breakdown
        assert "dominant_contributor" in breakdown


class TestStabilityScore:
    """Test stability score calculation"""

    def test_calculate_score(self):
        """Test stability score calculation"""
        calculator = StabilityScoreCalculator()

        R_t = 0.5
        score = calculator.calculate(R_t, time.time(), 1)

        # S(t) = 1 / (1 + 0.5) = 0.667
        assert 0.0 < score.score <= 1.0
        assert abs(score.score - 0.667) < 0.01
        assert score.recursion_energy == R_t

    def test_stability_levels(self):
        """Test stability level classification"""
        calculator = StabilityScoreCalculator()

        assert calculator.get_stability_level(0.3) == "critical"
        assert calculator.get_stability_level(0.6) == "unstable"
        assert calculator.get_stability_level(0.75) == "stable"
        assert calculator.get_stability_level(0.9) == "highly_stable"

    def test_control_modes(self):
        """Test control mode determination"""
        calculator = StabilityScoreCalculator()

        assert calculator.get_control_mode(0.3) == "emergency"
        assert calculator.get_control_mode(0.6) == "contraction"
        assert calculator.get_control_mode(0.75) == "normal"
        assert calculator.get_control_mode(0.9) == "expansion"


class TestLyapunovMonitor:
    """Test Lyapunov stability monitoring"""

    def test_lyapunov_stable(self):
        """Test Lyapunov stability (decreasing energy)"""
        monitor = LyapunovMonitor()

        # First cycle
        state1 = monitor.update(0.5, time.time(), 1)
        assert state1.V_t == 0.25
        assert state1.delta_V is None  # No previous

        # Second cycle (decreasing)
        state2 = monitor.update(0.4, time.time(), 2)
        assert abs(state2.V_t - 0.16) < 0.001  # Floating point tolerance
        assert state2.delta_V < 0  # Decreasing
        assert state2.is_stable

    def test_lyapunov_violation(self):
        """Test Lyapunov violation (increasing energy)"""
        monitor = LyapunovMonitor()

        # First cycle
        monitor.update(0.5, time.time(), 1)

        # Second cycle (increasing)
        state2 = monitor.update(0.6, time.time(), 2)
        assert state2.delta_V > 0  # Increasing
        assert not state2.is_stable
        assert len(monitor.get_violations()) == 1


class TestSpawnController:
    """Test spawn rate controller"""

    def test_spawn_approved(self):
        """Test spawn approval when criteria met"""
        controller = SpawnRateController()

        request = SpawnRequest(
            request_id="req1",
            agent_type="worker",
            priority=5,
            timestamp=time.time(),
            cycle_id=1,
            requester="orchestrator"
        )

        state = {
            "lyapunov_stable": True,
            "entropy": 0.3,
            "confidence": 0.8,
            "recursion_energy": 0.2,
            "estimated_spawn_impact": 0.05
        }

        response = controller.request_spawn(request, state)

        # Should be queued (never immediately approved)
        assert response.decision.value == "queued"

    def test_spawn_denied(self):
        """Test spawn denial when criteria not met"""
        controller = SpawnRateController()

        request = SpawnRequest(
            request_id="req1",
            agent_type="worker",
            priority=5,
            timestamp=time.time(),
            cycle_id=1,
            requester="orchestrator"
        )

        state = {
            "lyapunov_stable": False,  # Violation
            "entropy": 0.3,
            "confidence": 0.8,
            "recursion_energy": 0.2,
            "estimated_spawn_impact": 0.05
        }

        response = controller.request_spawn(request, state)

        assert response.decision.value == "denied"
        assert len(response.reasons) > 0


class TestGateDamping:
    """Test gate damping controller"""

    def test_gate_damping(self):
        """Test gate synthesis damping"""
        controller = GateDampingController()

        request = GateSynthesisRequest(
            request_id="req1",
            gate_type="safety",
            num_gates=10,
            timestamp=time.time(),
            cycle_id=1,
            requester="gate_engine"
        )

        # High confidence = more damping
        response = controller.request_synthesis(request, current_confidence=0.8)

        assert response.allowed_gates < request.num_gates
        assert response.damping_factor < 1.0

    def test_gate_capacity_limit(self):
        """Test gate capacity enforcement"""
        controller = GateDampingController()

        # Fill up to capacity
        for i in range(20):
            request = GateSynthesisRequest(
                request_id=f"req{i}",
                gate_type="safety",
                num_gates=50,
                timestamp=time.time(),
                cycle_id=i,
                requester="gate_engine"
            )
            controller.request_synthesis(request, current_confidence=0.5)

        # Should hit capacity limit
        capacity = controller.get_capacity()
        assert capacity["current"] <= controller.MAX_TOTAL_GATES


class TestFeedbackIsolation:
    """Test feedback isolation router"""

    def test_self_evaluation_blocked(self):
        """Test that self-evaluation is blocked"""
        router = FeedbackIsolationRouter()

        # Register entity
        entity = Entity(
            entity_id="agent1",
            entity_type=EntityType.GENERATOR,
            timestamp=time.time()
        )
        router.register_entity(entity)

        # Register artifact produced by entity
        artifact = Artifact(
            artifact_id="output1",
            producer_id="agent1",
            timestamp=time.time()
        )
        router.register_artifact(artifact)

        # Try to evaluate own output
        eval_req = EvaluationRequest(
            request_id="eval1",
            evaluator_id="agent1",
            artifact_id="output1",
            timestamp=time.time()
        )

        is_allowed, violation = router.check_evaluation(eval_req)

        assert not is_allowed
        assert violation is not None
        assert violation.violation_type == "self_evaluation"

    def test_valid_evaluation_allowed(self):
        """Test that valid evaluation is allowed"""
        router = FeedbackIsolationRouter()

        # Register entities
        generator = Entity(
            entity_id="generator1",
            entity_type=EntityType.GENERATOR,
            timestamp=time.time()
        )
        verifier = Entity(
            entity_id="verifier1",
            entity_type=EntityType.VERIFIER,
            timestamp=time.time()
        )
        router.register_entity(generator)
        router.register_entity(verifier)

        # Register artifact
        artifact = Artifact(
            artifact_id="output1",
            producer_id="generator1",
            timestamp=time.time()
        )
        router.register_artifact(artifact)

        # Verifier evaluates generator output
        eval_req = EvaluationRequest(
            request_id="eval1",
            evaluator_id="verifier1",
            artifact_id="output1",
            timestamp=time.time()
        )

        is_allowed, violation = router.check_evaluation(eval_req)

        assert is_allowed
        assert violation is None


class TestControlSignals:
    """Test control signal generation"""

    def test_emergency_mode(self):
        """Test emergency mode control signal"""
        generator = ControlSignalGenerator()

        signal = generator.generate_signal(
            stability_score=0.3,  # Below 0.5
            lyapunov_stable=True,
            entropy_decreasing=True,
            unresolved_failures=0,
            s_min=0.7,
            timestamp=time.time(),
            cycle_id=1
        )

        assert signal.mode == ControlMode.EMERGENCY
        assert not signal.allow_agent_spawn
        assert not signal.allow_gate_synthesis
        assert not signal.allow_execution
        assert signal.max_authority == "none"

    def test_normal_mode(self):
        """Test normal mode control signal"""
        generator = ControlSignalGenerator()

        signal = generator.generate_signal(
            stability_score=0.75,
            lyapunov_stable=True,
            entropy_decreasing=True,
            unresolved_failures=0,
            s_min=0.7,
            timestamp=time.time(),
            cycle_id=1
        )

        assert signal.mode == ControlMode.NORMAL
        assert signal.allow_agent_spawn
        assert signal.allow_gate_synthesis
        assert signal.allow_execution
        assert signal.max_authority == "medium"

    def test_re_expansion_criteria(self):
        """Test re-expansion criteria checking"""
        generator = ControlSignalGenerator()

        # Create stable history
        stability_history = [
            {"score": 0.8, "is_stable": True} for _ in range(5)
        ]
        lyapunov_history = [
            {"is_stable": True} for _ in range(5)
        ]
        entropy_history = [0.5, 0.4, 0.4, 0.3, 0.3]

        criteria_met, reasons = generator.check_re_expansion_criteria(
            stability_history,
            lyapunov_history,
            entropy_history,
            unresolved_failures=0,
            s_min=0.7
        )

        assert criteria_met
        assert "All re-expansion criteria satisfied" in reasons


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
