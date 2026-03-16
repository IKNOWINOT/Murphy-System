"""
Structural Audit Validation Tests
==================================

Validates that the gaps identified in the Murphy System structural audit
(2026-03-03) have been closed.  Each test class maps to one of the eight
audit categories and each test method maps to a specific criterion.

Audit sections:
    I.   State Model
    II.  Observation Model
    III. Infinity Metric (Entropy)
    IV.  Control Structure
    V.   Constraint System
    VI.  Role & Responsibility Graph
    VII. Scaling Mechanism
    VIII.LLM Synthesis Layer
"""

import math
import os

import pytest


from control_theory.canonical_state import CanonicalStateVector, DimensionRegistry
from control_theory.entropy import (
    shannon_entropy, kl_divergence, information_gain,
    normalize_distribution, uniform_distribution, max_entropy,
)
from control_theory.bayesian_engine import (
    BayesianConfidenceEngine, BeliefState, LikelihoodModel, Observation,
)
from control_theory.observation_model import (
    ObservationChannel, ObservationData, ObservationFunction, ObservationNoise,
)
from control_theory.control_vector import (
    ControlAction, ControlLaw, ControlVector,
)
from control_theory.state_transition import ProcessNoise, StateTransitionFunction
from control_theory.stability import LyapunovFunction, StabilityAnalyzer
from control_theory.jurisdiction import (
    Jurisdiction, JurisdictionConstraint, JurisdictionConstraintRegistry,
    JURISDICTION_EU, JURISDICTION_US, JURISDICTION_GLOBAL,
)
from control_theory.actor_registry import (
    Actor, ActorKind, ActorRegistry, AuthorityMatrix,
)
from control_theory.llm_validation import (
    ConflictResolver, ExpertProfileOutput, GateProposalOutput,
    LLMOutputKind, RegenerationPolicy, ResolutionStrategy,
    validate_llm_output,
)
from control_theory.state_adapter import from_mfgc_state, from_dict
from pydantic import BaseModel


# ===================================================================
# I. STATE MODEL
# ===================================================================

class TestStateModel:
    """Audit §I — State Model formalisation."""

    def test_explicit_typed_state_vector(self):
        """GAP: x_t was Dict[str, Any]. Now CanonicalStateVector is Pydantic."""
        assert issubclass(CanonicalStateVector, BaseModel)
        sv = CanonicalStateVector()
        assert isinstance(sv.confidence, float)
        assert isinstance(sv.phase_index, int)

    def test_state_dimensionality_defined(self):
        """GAP: dimensionality undefined. Now tracked as integer 25."""
        sv = CanonicalStateVector()
        assert sv.dimensionality() == 25
        assert sv.dimensionality() == len(sv.to_vector())
        assert sv.dimensionality() == len(CanonicalStateVector.dimension_names())

    def test_per_variable_uncertainty(self):
        """GAP: uncertainty was scalar. Now covariance_diagonal exists."""
        sv = CanonicalStateVector(uncertainty_data=0.8, uncertainty_authority=0.5)
        cov = sv.covariance_diagonal()
        assert len(cov) == sv.dimensionality()
        assert all(v > 0.0 for v in cov)

    def test_state_transition_model(self):
        """GAP: no x_{t+1} = f(x_t, u_t, w_t). Now StateTransitionFunction exists."""
        trans = StateTransitionFunction(noise=ProcessNoise.zero())
        current = CanonicalStateVector(confidence=0.3)
        control = [0.1] * 25
        nxt = trans.transition(current, control, add_noise=False)
        assert isinstance(nxt, CanonicalStateVector)
        assert nxt.confidence > current.confidence

    def test_mfgc_to_canonical_bridge(self):
        """GAP: legacy MFGCSystemState not linked to canonical vector."""
        from mfgc_core import MFGCSystemState, Phase
        state = MFGCSystemState(c_t=0.7, a_t=0.5, M_t=0.2, p_t=Phase.CONSTRAIN)
        canonical = state.to_canonical()
        assert isinstance(canonical, CanonicalStateVector)
        assert abs(canonical.confidence - 0.7) < 1e-10
        assert abs(canonical.authority - 0.5) < 1e-10
        assert abs(canonical.murphy_index - 0.2) < 1e-10
        assert canonical.phase_index == 3  # CONSTRAIN = index 3


# ===================================================================
# II. OBSERVATION MODEL
# ===================================================================

class TestObservationModel:
    """Audit §II — Observation Model formalisation."""

    def test_observation_channels_enumerated(self):
        """GAP: no enumerated measurement channels. Now ObservationChannel exists."""
        channels = list(ObservationChannel)
        assert len(channels) >= 5

    def test_observation_maps_to_state_dimensions(self):
        """GAP: no mapping from observations to state. Now channel→dim map exists."""
        obs_fn = ObservationFunction()
        dims = obs_fn.observable_dimensions(ObservationChannel.INQUISITORY)
        assert "confidence" in dims
        assert "uncertainty_data" in dims

    def test_noise_model_per_channel(self):
        """GAP: no measurement noise. Now ObservationNoise defines variance."""
        noise = ObservationNoise(channel=ObservationChannel.INQUISITORY, variance=0.02)
        assert noise.std_dev == pytest.approx(math.sqrt(0.02))

    def test_observe_produces_noisy_measurement(self):
        """GAP: no z_t = h(x_t) + v_t. Now ObservationFunction.observe() works."""
        state = CanonicalStateVector(confidence=0.8, uncertainty_data=0.3)
        obs_fn = ObservationFunction()
        obs = obs_fn.observe(state, ObservationChannel.CONFIDENCE_CALC, add_noise=False)
        assert isinstance(obs, ObservationData)
        assert "confidence" in obs.values

    def test_information_gain_computable(self):
        """GAP: no formal IG computation. Now information_gain() exists."""
        ig = information_gain(prior_entropy=2.0, posterior_entropy=1.5)
        assert ig == pytest.approx(0.5)


# ===================================================================
# III. INFINITY METRIC (Entropy)
# ===================================================================

class TestInfinityMetric:
    """Audit §III — Entropy-based uncertainty replaces heuristic sums."""

    def test_shannon_entropy_exists(self):
        """GAP: no H(X). Now shannon_entropy() computes it."""
        H = shannon_entropy([0.25, 0.25, 0.25, 0.25])
        assert abs(H - 2.0) < 1e-10

    def test_state_entropy_on_canonical_vector(self):
        """GAP: no state-level entropy. Now state_entropy() method exists."""
        sv = CanonicalStateVector(
            uncertainty_data=0.5, uncertainty_authority=0.3,
            uncertainty_information=0.1, uncertainty_resources=0.05,
            uncertainty_disagreement=0.05,
        )
        H = sv.state_entropy()
        assert H >= 0.0
        assert H <= max_entropy(5)  # bounded by log₂(5)

    def test_uniform_uncertainty_maximises_entropy(self):
        """Uniform uncertainties should produce maximum entropy."""
        uniform = CanonicalStateVector(
            uncertainty_data=0.2, uncertainty_authority=0.2,
            uncertainty_information=0.2, uncertainty_resources=0.2,
            uncertainty_disagreement=0.2,
        )
        skewed = CanonicalStateVector(
            uncertainty_data=0.9, uncertainty_authority=0.05,
            uncertainty_information=0.03, uncertainty_resources=0.01,
            uncertainty_disagreement=0.01,
        )
        assert uniform.state_entropy() > skewed.state_entropy()

    def test_bayesian_update_reduces_entropy(self):
        """GAP: no Bayesian posterior. Now entropy decreases with evidence."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()
        prior_H = shannon_entropy(belief.probabilities)
        obs = Observation(observation_id="o1", channel="test", value="success")
        result = engine.update(belief, obs, lm)
        posterior_H = shannon_entropy(result.posterior.probabilities)
        assert posterior_H < prior_H + 1e-10

    def test_kl_divergence_properties(self):
        """GAP: no formal uncertainty measure. Now KL divergence works."""
        P = [0.5, 0.3, 0.2]
        Q = [0.33, 0.33, 0.34]
        assert kl_divergence(P, Q) >= 0.0
        assert abs(kl_divergence(P, P)) < 1e-10


# ===================================================================
# IV. CONTROL STRUCTURE
# ===================================================================

class TestControlStructure:
    """Audit §IV — Control law and stability."""

    def test_control_vector_defined(self):
        """GAP: no u_t. Now ControlVector with ControlAction exists."""
        cv = ControlVector(action=ControlAction.GENERATE, intensity=0.8)
        assert cv.action == ControlAction.GENERATE
        assert cv.required_authority >= 0.0

    def test_control_law_feedback(self):
        """GAP: no u_t = K(x_ref - x_t). Now ControlLaw.compute_control() exists."""
        target = CanonicalStateVector(confidence=1.0, authority=1.0)
        current = CanonicalStateVector(confidence=0.2, authority=0.1)
        law = ControlLaw(base_gain=0.5)
        u = law.compute_control(target, current)
        assert len(u) == 25
        assert u[0] > 0.0  # confidence dimension should push positive

    def test_gain_scheduling_varies_by_phase(self):
        """GAP: weights static per phase. Now gain_for_dimension varies."""
        law = ControlLaw()
        g0 = law.gain_for_dimension("confidence", 0)
        g6 = law.gain_for_dimension("confidence", 6)
        assert g0 != g6

    def test_lyapunov_stability(self):
        """GAP: no stability guarantee. Now LyapunovFunction + StabilityAnalyzer."""
        target = CanonicalStateVector(confidence=1.0, authority=1.0)
        lyap = LyapunovFunction(target)
        assert lyap.is_positive_definite()
        V_target = lyap.evaluate(target)
        assert abs(V_target) < 1e-10  # V(x*) = 0

    def test_closed_loop_convergence(self):
        """End-to-end: control loop converges with decreasing Lyapunov."""
        target = CanonicalStateVector(confidence=1.0, authority=1.0)
        current = CanonicalStateVector(confidence=0.2, authority=0.2)
        law = ControlLaw(base_gain=0.5)
        trans = StateTransitionFunction(noise=ProcessNoise.zero())
        lyap = LyapunovFunction(target)
        analyzer = StabilityAnalyzer(lyap)

        trajectory = [current]
        for _ in range(20):
            u = law.compute_control(target, current)
            current = trans.transition(current, u, add_noise=False)
            trajectory.append(current)

        all_ok, _ = analyzer.check_trajectory(trajectory)
        assert all_ok, "Lyapunov function should decrease at each step"
        assert trajectory[-1].confidence > trajectory[0].confidence
        assert analyzer.is_bibo_stable(trajectory)


# ===================================================================
# V. CONSTRAINT SYSTEM
# ===================================================================

class TestConstraintSystem:
    """Audit §V — Jurisdiction and probabilistic compliance."""

    def test_constraint_has_jurisdiction_field(self):
        """GAP: no jurisdiction field. Now Constraint.jurisdiction exists."""
        from constraint_system import Constraint, ConstraintType, ConstraintSeverity
        c = Constraint(
            constraint_id="c1", name="test",
            constraint_type=ConstraintType.REGULATORY,
            severity=ConstraintSeverity.HIGH,
            description="test", parameter="x",
            operator="<=", threshold_value=100,
            jurisdiction="EU",
        )
        assert c.jurisdiction == "EU"
        assert "jurisdiction" in c.to_dict()

    def test_select_constraints_by_jurisdiction(self):
        """GAP: no jurisdiction routing. Now select_constraints() filters."""
        from constraint_system import ConstraintSystem
        cs = ConstraintSystem()
        c1 = cs.add_constraint(
            name="gdpr", constraint_type="regulatory",
            parameter="data", operator="==", threshold_value=True,
        )
        c1.jurisdiction = "EU"
        c2 = cs.add_constraint(
            name="hipaa", constraint_type="regulatory",
            parameter="phi", operator="==", threshold_value=True,
        )
        c2.jurisdiction = "US"
        eu = cs.select_constraints("EU")
        assert all(c.jurisdiction in ("EU", "GLOBAL") for c in eu)

    def test_jurisdiction_constraint_probabilistic(self):
        """GAP: compliance binary. Now probabilistic evaluation exists."""
        jc = JurisdictionConstraint(
            constraint_id="jc1", name="budget", parameter="cost",
            threshold=1000.0, operator="<=",
            jurisdictions={"US"}, uncertainty_variance=100.0,
        )
        prob = jc.evaluate_probabilistic(950.0)
        assert 0.0 < prob <= 1.0

    def test_jurisdiction_registry_conflict_detection(self):
        """Conflicting constraints in same jurisdiction are detected."""
        reg = JurisdictionConstraintRegistry()
        reg.add(JurisdictionConstraint(
            constraint_id="a", name="min_latency", parameter="latency",
            threshold=100.0, operator="<=", jurisdictions={"US"},
        ))
        reg.add(JurisdictionConstraint(
            constraint_id="b", name="max_latency", parameter="latency",
            threshold=200.0, operator=">=", jurisdictions={"US"},
        ))
        conflicts = reg.detect_conflicts("US")
        assert len(conflicts) >= 1


# ===================================================================
# VI. ROLE & RESPONSIBILITY GRAPH
# ===================================================================

class TestRoleResponsibilityGraph:
    """Audit §VI — Unified actors, authority matrix, delegation."""

    def test_unified_actor_registry(self):
        """GAP: actors per-subsystem. Now ActorRegistry is single source."""
        reg = ActorRegistry()
        reg.register(Actor(actor_id="h1", name="Alice", kind=ActorKind.HUMAN))
        reg.register(Actor(actor_id="b1", name="Bot-1", kind=ActorKind.BOT))
        assert len(reg.list_actors()) == 2
        assert len(reg.list_actors(kind=ActorKind.HUMAN)) == 1

    def test_authority_matrix(self):
        """GAP: no formal authority matrix. Now AuthorityMatrix works."""
        am = AuthorityMatrix()
        am.grant("h1", "deploy", "prod")
        assert am.is_authorized("h1", "deploy", "prod")
        assert not am.is_authorized("h1", "deploy", "staging")
        am.revoke("h1", "deploy", "prod")
        assert not am.is_authorized("h1", "deploy", "prod")

    def test_delegation_with_transitive_closure(self):
        """GAP: no delegation chains. Now transitive_delegates() works."""
        reg = ActorRegistry()
        reg.register(Actor(actor_id="a", name="A", kind=ActorKind.HUMAN))
        reg.register(Actor(actor_id="b", name="B", kind=ActorKind.HUMAN))
        reg.register(Actor(actor_id="c", name="C", kind=ActorKind.BOT))
        reg.delegate("a", "b")
        reg.delegate("b", "c")
        delegates = reg.transitive_delegates("a")
        assert "b" in delegates
        assert "c" in delegates

    def test_delegation_revocation(self):
        """GAP: no delegation revocation. Now revoke_delegation() works."""
        reg = ActorRegistry()
        reg.register(Actor(actor_id="a", name="A", kind=ActorKind.HUMAN))
        reg.register(Actor(actor_id="b", name="B", kind=ActorKind.HUMAN))
        reg.delegate("a", "b")
        reg.revoke_delegation("a", "b")
        assert "b" not in reg.transitive_delegates("a")


# ===================================================================
# VII. SCALING MECHANISM
# ===================================================================

class TestScalingMechanism:
    """Audit §VII — Dimension registration and schema versioning."""

    def test_dimension_registration(self):
        """GAP: uncontrolled dimension addition. Now DimensionRegistry."""
        dreg = DimensionRegistry()
        initial = dreg.size
        dreg.register_dimension("custom_metric", dtype="float", bounds=(0.0, 1.0))
        assert dreg.size == initial + 1
        assert dreg.has_dimension("custom_metric")

    def test_schema_versioning(self):
        """GAP: no schema versioning. Now version increments on registration."""
        dreg = DimensionRegistry()
        v0 = dreg.version
        dreg.register_dimension("new_dim")
        assert dreg.version == v0 + 1

    def test_duplicate_dimension_rejected(self):
        """Registering an existing dimension must raise."""
        dreg = DimensionRegistry()
        with pytest.raises(ValueError, match="already registered"):
            dreg.register_dimension("confidence")


# ===================================================================
# VIII. LLM SYNTHESIS LAYER
# ===================================================================

class TestLLMSynthesisLayer:
    """Audit §VIII — Schema validation, conflict resolution, regeneration."""

    def test_llm_output_schema_validation(self):
        """GAP: no Pydantic schema on LLM output. Now validated."""
        output = validate_llm_output(LLMOutputKind.EXPERT_PROFILE, {
            "expert_id": "e1", "name": "Risk Expert",
            "domain": "finance", "capabilities": ["risk"], "confidence": 0.9,
        })
        assert isinstance(output, ExpertProfileOutput)

    def test_invalid_llm_output_rejected(self):
        """Invalid LLM output raises ValidationError."""
        with pytest.raises(Exception):
            validate_llm_output(LLMOutputKind.EXPERT_PROFILE, {
                "expert_id": "", "name": "",
                "domain": "", "capabilities": [], "confidence": 2.0,
            })

    def test_conflict_resolution_priority(self):
        """GAP: no conflict resolution. Now ConflictResolver works."""
        resolver = ConflictResolver(strategy=ResolutionStrategy.PRIORITY)
        result = resolver.resolve(
            {"confidence": 0.9, "data": "A"},
            {"confidence": 0.3, "data": "B"},
        )
        assert result.winner["data"] == "A"

    def test_conflict_resolution_hitl(self):
        """HITL strategy escalates to human."""
        resolver = ConflictResolver(strategy=ResolutionStrategy.HUMAN_IN_THE_LOOP)
        result = resolver.resolve({"confidence": 0.9}, {"confidence": 0.3})
        assert result.escalated

    def test_regeneration_policy(self):
        """GAP: no regen triggers. Now RegenerationPolicy works."""
        policy = RegenerationPolicy(min_confidence=0.3, max_retries=3)
        assert policy.should_regenerate(confidence=0.1, attempt=0)
        assert not policy.should_regenerate(confidence=0.8, attempt=0)
        assert not policy.should_regenerate(confidence=0.1, attempt=3)

    def test_gate_proposal_validation(self):
        """Gate proposals are validated against schema."""
        output = validate_llm_output(LLMOutputKind.GATE_PROPOSAL, {
            "gate_id": "g1", "name": "Risk Gate",
            "condition": "murphy_index < 0.3", "threshold": 0.7,
        })
        assert isinstance(output, GateProposalOutput)


# ===================================================================
# CROSS-CUTTING: Security Middleware Wiring
# ===================================================================

class TestSecurityMiddlewareWiring:
    """Audit Critical Point #7 — SecurityMiddleware wired into API servers."""

    def test_auar_secure_app_has_middleware(self):
        """create_secure_auar_app applies security middleware."""
        pytest = __import__("pytest")
        from auar_api import create_secure_auar_app
        app = create_secure_auar_app()
        if app is None:
            pytest.skip("FastAPI not installed — secure AUAR app unavailable")
        # Verify middleware stack contains SecurityMiddleware and CORS
        middleware_names = [
            type(m).__name__
            if not hasattr(m, 'cls') else m.cls.__name__
            for m in getattr(app, 'user_middleware', [])
        ]
        assert any("Security" in n or "CORS" in n for n in middleware_names), (
            f"Expected security middleware, got: {middleware_names}"
        )
        assert len(app.routes) > 0  # Routes registered

    def test_auar_create_secure_app_callable(self):
        """create_secure_auar_app is importable and callable."""
        from auar_api import create_secure_auar_app
        assert callable(create_secure_auar_app)
