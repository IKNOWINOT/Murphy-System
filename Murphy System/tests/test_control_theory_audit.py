"""
Comprehensive tests for the Murphy System control-theory formalizations.

Each test class maps to one section of the structural audit and verifies
that the identified gaps have been closed.
"""

import math
import os
import unittest


from control_theory.canonical_state import (
    CanonicalStateVector,
    DimensionRegistry,
    _DIMENSION_NAMES,
)
from control_theory.entropy import (
    information_gain,
    kl_divergence,
    max_entropy,
    normalize_distribution,
    shannon_entropy,
    uniform_distribution,
)
from control_theory.bayesian_engine import (
    BayesianConfidenceEngine,
    BeliefState,
    LikelihoodModel,
    Observation,
)
from control_theory.observation_model import (
    ObservationChannel,
    ObservationData,
    ObservationFunction,
    ObservationNoise,
)
from control_theory.control_vector import (
    ControlAction,
    ControlLaw,
    ControlVector,
)
from control_theory.state_transition import (
    ProcessNoise,
    StateTransitionFunction,
)
from control_theory.stability import (
    LyapunovFunction,
    StabilityAnalyzer,
)
from control_theory.jurisdiction import (
    Jurisdiction,
    JurisdictionConstraint,
    JurisdictionConstraintRegistry,
    JURISDICTION_EU,
    JURISDICTION_US,
)
from control_theory.actor_registry import (
    Actor,
    ActorKind,
    ActorRegistry,
    AuthorityMatrix,
)
from control_theory.llm_validation import (
    ConflictResolver,
    ExpertProfileOutput,
    GateProposalOutput,
    LLMOutputKind,
    RecommendationOutput,
    RegenerationPolicy,
    ResolutionStrategy,
    validate_llm_output,
)


# ===================================================================
# I. STATE MODEL
# ===================================================================

class TestCanonicalStateVector(unittest.TestCase):
    """Audit §I — Explicit state vector, typed fields, dimensionality."""

    def test_explicit_typed_fields(self):
        """State vector has explicitly typed, enumerated fields (not Dict[str, Any])."""
        sv = CanonicalStateVector()
        self.assertIsInstance(sv.confidence, float)
        self.assertIsInstance(sv.authority, float)
        self.assertIsInstance(sv.phase_index, int)
        self.assertIsInstance(sv.gate_count, int)

    def test_dimensionality_is_tracked(self):
        """dim(x_t) is a tracked integer."""
        sv = CanonicalStateVector()
        self.assertEqual(sv.dimensionality(), 25)
        self.assertEqual(len(_DIMENSION_NAMES), 25)

    def test_to_vector_and_back(self):
        """Roundtrip: to_vector → from_vector preserves values."""
        sv = CanonicalStateVector(confidence=0.8, authority=0.5, phase_index=3)
        vec = sv.to_vector()
        sv2 = CanonicalStateVector.from_vector(vec)
        self.assertAlmostEqual(sv2.confidence, 0.8)
        self.assertAlmostEqual(sv2.authority, 0.5)
        self.assertEqual(sv2.phase_index, 3)

    def test_clamping_out_of_range(self):
        """Validators clamp values to valid ranges."""
        sv = CanonicalStateVector(confidence=2.0, authority=-0.5, phase_index=10)
        self.assertEqual(sv.confidence, 1.0)
        self.assertEqual(sv.authority, 0.0)
        self.assertEqual(sv.phase_index, 6)

    def test_dimension_names_canonical_order(self):
        """Dimension names are in a fixed canonical order."""
        names = CanonicalStateVector.dimension_names()
        self.assertEqual(names[0], "confidence")
        self.assertEqual(names[3], "phase_index")
        self.assertEqual(len(names), 25)

    def test_covariance_diagonal_default(self):
        """Per-variable uncertainty produces heuristic covariance diagonal."""
        sv = CanonicalStateVector(uncertainty_data=0.5, uncertainty_authority=0.8)
        cov = sv.covariance_diagonal()
        self.assertEqual(len(cov), 25)
        # Higher uncertainty → higher variance
        self.assertGreater(cov[0], 0.0)  # confidence variance
        self.assertTrue(all(v > 0 for v in cov))

    def test_covariance_diagonal_explicit(self):
        """Explicit variances override heuristic defaults."""
        sv = CanonicalStateVector()
        variances = [0.1] * 25
        cov = sv.covariance_diagonal(variances)
        self.assertEqual(cov, variances)

    def test_covariance_diagonal_wrong_length_raises(self):
        """Wrong variance length raises ValueError."""
        sv = CanonicalStateVector()
        with self.assertRaises(ValueError):
            sv.covariance_diagonal([0.1] * 5)

    def test_norm(self):
        """L2 norm is non-negative."""
        sv = CanonicalStateVector(confidence=0.5, authority=0.3)
        self.assertGreater(sv.norm(), 0.0)

    def test_from_vector_wrong_length(self):
        """from_vector rejects wrong-length input."""
        with self.assertRaises(ValueError):
            CanonicalStateVector.from_vector([1.0, 2.0])


class TestDimensionRegistry(unittest.TestCase):
    """Audit §VII — Mechanism for adding state dimensions with versioning."""

    def test_initial_dimensions(self):
        """Registry starts with all 25 canonical dimensions."""
        reg = DimensionRegistry()
        self.assertEqual(reg.size, 25)
        self.assertEqual(reg.version, 1)

    def test_register_new_dimension(self):
        """Adding a dimension increments version and size."""
        reg = DimensionRegistry()
        reg.register_dimension("custom_metric", dtype="float", bounds=(0.0, 100.0))
        self.assertEqual(reg.size, 26)
        self.assertEqual(reg.version, 2)
        self.assertTrue(reg.has_dimension("custom_metric"))

    def test_duplicate_dimension_raises(self):
        """Registering an existing dimension raises ValueError."""
        reg = DimensionRegistry()
        with self.assertRaises(ValueError):
            reg.register_dimension("confidence")


class TestStateTransition(unittest.TestCase):
    """Audit §I — Time evolution model  x_{t+1} = f(x_t, u_t, w_t)."""

    def test_deterministic_transition(self):
        """x_{t+1} = x_t + u_t  (no noise)."""
        f = StateTransitionFunction(noise=ProcessNoise.zero())
        state = CanonicalStateVector(confidence=0.5, authority=0.3)
        control = [0.0] * 25
        control[0] = 0.1  # bump confidence
        next_state = f.transition(state, control, add_noise=False)
        self.assertAlmostEqual(next_state.confidence, 0.6)

    def test_clamping_after_transition(self):
        """State is clamped to valid bounds after transition."""
        f = StateTransitionFunction(noise=ProcessNoise.zero())
        state = CanonicalStateVector(confidence=0.95)
        control = [0.0] * 25
        control[0] = 0.2  # would push confidence to 1.15
        next_state = f.transition(state, control, add_noise=False)
        self.assertAlmostEqual(next_state.confidence, 1.0)

    def test_predict_horizon(self):
        """Predict rolls out multiple deterministic steps."""
        f = StateTransitionFunction(noise=ProcessNoise.zero())
        state = CanonicalStateVector(confidence=0.1)
        control = [0.0] * 25
        control[0] = 0.1
        trajectory = f.predict(state, control, horizon=3)
        self.assertEqual(len(trajectory), 3)
        self.assertAlmostEqual(trajectory[0].confidence, 0.2)
        self.assertAlmostEqual(trajectory[1].confidence, 0.3)

    def test_wrong_control_length_raises(self):
        """Control vector of wrong length raises ValueError."""
        f = StateTransitionFunction()
        state = CanonicalStateVector()
        with self.assertRaises(ValueError):
            f.transition(state, [0.0, 0.0])

    def test_process_noise_adds_randomness(self):
        """With noise, repeated transitions produce different results."""
        noise = ProcessNoise(variances=tuple(0.1 for _ in _DIMENSION_NAMES))
        f = StateTransitionFunction(noise=noise)
        state = CanonicalStateVector(confidence=0.5)
        control = [0.0] * 25
        results = set()
        for _ in range(10):
            ns = f.transition(state, control, add_noise=True)
            results.add(round(ns.confidence, 4))
        self.assertGreater(len(results), 1, "Noise should produce variation")


# ===================================================================
# II. OBSERVATION MODEL
# ===================================================================

class TestObservationModel(unittest.TestCase):
    """Audit §II — Formal observation function z_t = h(x_t) + v_t."""

    def test_observation_channels_defined(self):
        """All 8 observation channels are enumerated."""
        channels = list(ObservationChannel)
        self.assertEqual(len(channels), 8)

    def test_channel_state_mapping(self):
        """Each channel declares what state dimensions it can update."""
        obs_fn = ObservationFunction()
        for ch in ObservationChannel:
            dims = obs_fn.observable_dimensions(ch)
            self.assertIsInstance(dims, set)
            self.assertTrue(len(dims) > 0, f"Channel {ch} has no observable dims")

    def test_observe_without_noise(self):
        """h(x_t) projects state onto channel's visible dimensions."""
        obs_fn = ObservationFunction()
        state = CanonicalStateVector(confidence=0.75, murphy_index=0.2)
        obs = obs_fn.observe(state, ObservationChannel.CONFIDENCE_CALC, add_noise=False)
        self.assertIn("confidence", obs.values)
        self.assertAlmostEqual(obs.values["confidence"], 0.75)

    def test_observe_with_noise(self):
        """z_t = h(x_t) + v_t adds noise."""
        obs_fn = ObservationFunction()
        state = CanonicalStateVector(confidence=0.5)
        observations = [
            obs_fn.observe(state, ObservationChannel.CONFIDENCE_CALC, add_noise=True)
            for _ in range(20)
        ]
        values = [o.values.get("confidence", 0.5) for o in observations]
        # With noise, not all values should be exactly 0.5
        self.assertTrue(
            any(abs(v - 0.5) > 1e-9 for v in values),
            "Noise should cause variation"
        )

    def test_observability_check(self):
        """Can check if state is fully observable across all channels."""
        obs_fn = ObservationFunction()
        all_obs = obs_fn.all_observable_dimensions()
        unobs = obs_fn.unobservable_dimensions()
        # Together they should cover all dimensions
        self.assertEqual(all_obs | unobs, set(_DIMENSION_NAMES))

    def test_noise_model_per_channel(self):
        """Each channel has a noise model with variance and reliability."""
        obs_fn = ObservationFunction()
        for ch in ObservationChannel:
            noise = obs_fn.noise_models.get(ch)
            self.assertIsNotNone(noise, f"No noise model for {ch}")
            self.assertGreaterEqual(noise.variance, 0.0)
            self.assertGreaterEqual(noise.reliability, 0.0)
            self.assertLessEqual(noise.reliability, 1.0)

    def test_register_custom_channel(self):
        """Can register a new channel's observable dimensions."""
        obs_fn = ObservationFunction()
        obs_fn.register_channel(
            ObservationChannel.SENSOR_TELEMETRY,
            {"uptime_seconds", "cpu_usage_percent", "active_tasks"},
            ObservationNoise(channel=ObservationChannel.SENSOR_TELEMETRY, variance=0.05),
        )
        dims = obs_fn.observable_dimensions(ObservationChannel.SENSOR_TELEMETRY)
        self.assertIn("active_tasks", dims)

    def test_register_invalid_dimension_raises(self):
        """Registering unknown dimension raises ValueError."""
        obs_fn = ObservationFunction()
        with self.assertRaises(ValueError):
            obs_fn.register_channel(
                ObservationChannel.SENSOR_TELEMETRY,
                {"nonexistent_dim"},
            )


# ===================================================================
# III. INFINITY METRIC (Information-Theoretic)
# ===================================================================

class TestEntropyAndInformationTheory(unittest.TestCase):
    """Audit §III — Shannon entropy, convergence, optimal questions."""

    def test_shannon_entropy_uniform(self):
        """H(uniform) = log₂(n)."""
        n = 4
        dist = uniform_distribution(n)
        h = shannon_entropy(dist)
        self.assertAlmostEqual(h, math.log2(n), places=5)

    def test_shannon_entropy_point_mass(self):
        """H(point mass) = 0."""
        h = shannon_entropy([1.0, 0.0, 0.0])
        self.assertAlmostEqual(h, 0.0)

    def test_kl_divergence_same_distribution(self):
        """D_KL(P || P) = 0."""
        p = [0.5, 0.3, 0.2]
        self.assertAlmostEqual(kl_divergence(p, p), 0.0, places=5)

    def test_kl_divergence_non_negative(self):
        """D_KL(P || Q) >= 0."""
        p = [0.7, 0.2, 0.1]
        q = [0.3, 0.4, 0.3]
        self.assertGreaterEqual(kl_divergence(p, q), 0.0)

    def test_information_gain_positive_on_update(self):
        """IG = H(prior) - H(posterior) ≥ 0 on informative observation."""
        engine = BayesianConfidenceEngine()
        prior = engine.create_prior()
        obs = Observation(observation_id="obs1", channel="test", value="success")
        lm = engine.create_magnify_likelihood()
        result = engine.update(prior, obs, lm)
        self.assertGreaterEqual(result.information_gained, 0.0)

    def test_entropy_trajectory_non_increasing(self):
        """Entropy should decrease with informative observations (convergence)."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()
        entropies = [belief.entropy()]
        for i in range(5):
            obs = Observation(observation_id=f"obs{i}", channel="test", value="success")
            result = engine.update(belief, obs, lm)
            belief = result.posterior
            entropies.append(belief.entropy())
        # Entropy should be non-increasing with consistent observations
        for i in range(len(entropies) - 1):
            self.assertGreaterEqual(
                entropies[i] + 1e-9, entropies[i + 1],
                f"Entropy increased at step {i}: {entropies[i]} → {entropies[i+1]}"
            )

    def test_optimal_question_selection(self):
        """q* = argmax_q IG(q) selects the most informative question."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm_good = engine.create_solidify_likelihood()  # strong signal
        lm_weak = engine.create_simplify_likelihood()   # weaker signal
        best_q, best_eig = engine.select_optimal_question(
            belief,
            candidate_questions=["solidify", "simplify"],
            likelihood_models={"solidify": lm_good, "simplify": lm_weak},
        )
        self.assertIsInstance(best_q, str)
        self.assertGreaterEqual(best_eig, 0.0)

    def test_covariance_diagonal_tracks_uncertainty(self):
        """Covariance entries reflect per-variable uncertainty."""
        sv_low = CanonicalStateVector(uncertainty_data=0.1)
        sv_high = CanonicalStateVector(uncertainty_data=0.9)
        cov_low = sv_low.covariance_diagonal()
        cov_high = sv_high.covariance_diagonal()
        # confidence variance (index 0) should be higher when uncertainty_data is higher
        self.assertGreater(cov_high[0], cov_low[0])


# ===================================================================
# IV. CONTROL STRUCTURE
# ===================================================================

class TestControlVector(unittest.TestCase):
    """Audit §IV — Defined control vector u_t ∈ U."""

    def test_control_actions_enumerated(self):
        """All system actions are enumerated as ControlAction."""
        actions = list(ControlAction)
        self.assertGreaterEqual(len(actions), 5)
        names = {a.value for a in actions}
        self.assertIn("generate", names)
        self.assertIn("deploy", names)
        self.assertIn("escalate", names)

    def test_control_vector_has_typed_fields(self):
        """ControlVector has action, intensity, target_dimensions, parameters."""
        cv = ControlVector(
            action=ControlAction.GENERATE,
            intensity=0.8,
            target_dimensions=["confidence"],
        )
        self.assertEqual(cv.action, ControlAction.GENERATE)
        self.assertEqual(cv.intensity, 0.8)

    def test_authority_requirement(self):
        """Each action has a required authority level."""
        cv_gen = ControlVector(action=ControlAction.GENERATE)
        cv_deploy = ControlVector(action=ControlAction.DEPLOY)
        self.assertLess(cv_gen.required_authority, cv_deploy.required_authority)

    def test_is_authorized(self):
        """Authorization check works for control vector."""
        cv = ControlVector(action=ControlAction.DEPLOY)  # requires 0.9
        self.assertFalse(cv.is_authorized(0.5))
        self.assertTrue(cv.is_authorized(0.95))


class TestControlLaw(unittest.TestCase):
    """Audit §IV — Control law u_t = K_t × e_t with gain scheduling."""

    def test_compute_error(self):
        """Error = target - current."""
        law = ControlLaw()
        target = CanonicalStateVector(confidence=1.0, authority=0.8)
        current = CanonicalStateVector(confidence=0.5, authority=0.3)
        error = law.compute_error(target, current)
        self.assertAlmostEqual(error[0], 0.5)  # confidence gap
        self.assertAlmostEqual(error[1], 0.5)  # authority gap

    def test_gain_scheduling_by_phase(self):
        """Gains shift from generative to deterministic across phases."""
        law = ControlLaw()
        # EXPAND phase (0): generative gain is high
        g_expand = law.gain_for_dimension("confidence", phase_index=0)
        # EXECUTE phase (6): generative gain is low
        g_execute = law.gain_for_dimension("confidence", phase_index=6)
        self.assertGreater(g_expand, g_execute)

    def test_compute_control_returns_correct_length(self):
        """Control output has same dimensionality as state."""
        law = ControlLaw()
        target = CanonicalStateVector(confidence=1.0)
        current = CanonicalStateVector(confidence=0.5)
        control = law.compute_control(target, current)
        self.assertEqual(len(control), 25)

    def test_suggest_action(self):
        """suggest_action returns a valid ControlVector."""
        law = ControlLaw()
        target = CanonicalStateVector(confidence=1.0)
        current = CanonicalStateVector(confidence=0.1)
        cv = law.suggest_action(target, current)
        self.assertIsInstance(cv, ControlVector)
        self.assertIsInstance(cv.action, ControlAction)


class TestStability(unittest.TestCase):
    """Audit §IV — Lyapunov stability guarantees."""

    def test_lyapunov_at_equilibrium_is_zero(self):
        """V(x*) = 0."""
        eq = CanonicalStateVector(confidence=1.0, authority=1.0)
        lyap = LyapunovFunction(eq)
        self.assertAlmostEqual(lyap.evaluate(eq), 0.0)

    def test_lyapunov_positive_away_from_equilibrium(self):
        """V(x) > 0 for x ≠ x*."""
        eq = CanonicalStateVector(confidence=1.0, authority=1.0)
        lyap = LyapunovFunction(eq)
        state = CanonicalStateVector(confidence=0.5, authority=0.5)
        self.assertGreater(lyap.evaluate(state), 0.0)

    def test_lyapunov_decrease_under_control(self):
        """V(x_{t+1}) < V(x_t) when moving toward equilibrium."""
        eq = CanonicalStateVector(confidence=1.0, authority=1.0)
        lyap = LyapunovFunction(eq)
        analyzer = StabilityAnalyzer(lyap)

        state = CanonicalStateVector(confidence=0.5, authority=0.5)
        closer = CanonicalStateVector(confidence=0.7, authority=0.7)
        result = analyzer.check_step(state, closer)
        self.assertTrue(result.is_decreasing)

    def test_bibo_stability(self):
        """BIBO: all states in trajectory remain bounded."""
        eq = CanonicalStateVector(confidence=1.0)
        lyap = LyapunovFunction(eq)
        analyzer = StabilityAnalyzer(lyap)
        trajectory = [
            CanonicalStateVector(confidence=0.3),
            CanonicalStateVector(confidence=0.5),
            CanonicalStateVector(confidence=0.8),
        ]
        self.assertTrue(analyzer.is_bibo_stable(trajectory))

    def test_lyapunov_gradient(self):
        """Gradient ∂V/∂x is computed correctly."""
        eq = CanonicalStateVector(confidence=1.0)
        lyap = LyapunovFunction(eq, weights=[1.0] * 25)
        state = CanonicalStateVector(confidence=0.5)
        grad = lyap.gradient(state)
        self.assertEqual(len(grad), 25)
        # ∂V/∂confidence = 2 × 1.0 × (0.5 - 1.0) = -1.0
        self.assertAlmostEqual(grad[0], -1.0)

    def test_trajectory_stability(self):
        """Full trajectory approaching equilibrium is Lyapunov stable."""
        eq = CanonicalStateVector(confidence=1.0, authority=1.0)
        lyap = LyapunovFunction(eq)
        analyzer = StabilityAnalyzer(lyap)
        trajectory = [
            CanonicalStateVector(confidence=0.2, authority=0.2),
            CanonicalStateVector(confidence=0.4, authority=0.4),
            CanonicalStateVector(confidence=0.6, authority=0.6),
            CanonicalStateVector(confidence=0.8, authority=0.8),
        ]
        all_ok, results = analyzer.check_trajectory(trajectory)
        self.assertTrue(all_ok)

    def test_positive_definite_check(self):
        """Weight matrix is positive definite."""
        eq = CanonicalStateVector()
        lyap = LyapunovFunction(eq, weights=[1.0] * 25)
        self.assertTrue(lyap.is_positive_definite())


# ===================================================================
# V. CONSTRAINT SYSTEM
# ===================================================================

class TestJurisdictionConstraints(unittest.TestCase):
    """Audit §V — Jurisdiction-based rule mapping & probabilistic compliance."""

    def test_jurisdiction_field_on_constraint(self):
        """Constraints have a jurisdiction field."""
        c = JurisdictionConstraint(
            constraint_id="c1",
            name="GDPR",
            parameter="data_retention",
            threshold=90.0,
            operator="<=",
            jurisdictions={"EU"},
        )
        self.assertIn("EU", c.jurisdictions)

    def test_select_by_jurisdiction(self):
        """select_constraints(jurisdiction) returns only applicable constraints."""
        registry = JurisdictionConstraintRegistry()
        registry.add(JurisdictionConstraint(
            constraint_id="gdpr", name="GDPR", parameter="retention",
            threshold=90, jurisdictions={"EU"},
        ))
        registry.add(JurisdictionConstraint(
            constraint_id="hipaa", name="HIPAA", parameter="phi",
            threshold=100, jurisdictions={"US"},
        ))
        registry.add(JurisdictionConstraint(
            constraint_id="global", name="Encryption", parameter="key_length",
            threshold=256, jurisdictions={"GLOBAL"},
        ))
        eu_constraints = registry.select_constraints("EU")
        self.assertEqual(len(eu_constraints), 2)  # GDPR + GLOBAL
        us_constraints = registry.select_constraints("US")
        self.assertEqual(len(us_constraints), 2)  # HIPAA + GLOBAL

    def test_deterministic_evaluation(self):
        """Binary satisfaction check works."""
        c = JurisdictionConstraint(
            constraint_id="c1", name="budget", parameter="cost",
            threshold=1000.0, operator="<=",
        )
        self.assertTrue(c.evaluate_deterministic(500.0))
        self.assertFalse(c.evaluate_deterministic(1500.0))

    def test_probabilistic_compliance(self):
        """P(g_i(x) ≤ 0) ≥ 1 - ε under Gaussian uncertainty."""
        c = JurisdictionConstraint(
            constraint_id="c1", name="budget", parameter="cost",
            threshold=1000.0, operator="<=",
            epsilon=0.05, uncertainty_variance=100.0,  # σ=10
        )
        # Value well below threshold → high probability of satisfaction
        self.assertTrue(c.is_probabilistically_satisfied(900.0))
        # Value at threshold → ~50% → fails with ε=0.05
        self.assertFalse(c.is_probabilistically_satisfied(1000.0))

    def test_probabilistic_no_uncertainty(self):
        """With zero variance, probabilistic = deterministic."""
        c = JurisdictionConstraint(
            constraint_id="c1", name="test", parameter="x",
            threshold=5.0, operator="<=",
            uncertainty_variance=0.0,
        )
        self.assertAlmostEqual(c.evaluate_probabilistic(3.0), 1.0)
        self.assertAlmostEqual(c.evaluate_probabilistic(6.0), 0.0)

    def test_conflict_detection(self):
        """Detect conflicting constraints within a jurisdiction."""
        registry = JurisdictionConstraintRegistry()
        registry.add(JurisdictionConstraint(
            constraint_id="c1", name="min_speed", parameter="speed",
            threshold=100, operator=">=", jurisdictions={"US"},
        ))
        registry.add(JurisdictionConstraint(
            constraint_id="c2", name="max_speed", parameter="speed",
            threshold=50, operator="<=", jurisdictions={"US"},
        ))
        conflicts = registry.detect_conflicts("US")
        self.assertGreater(len(conflicts), 0)


class TestConstraintSystemJurisdiction(unittest.TestCase):
    """Audit §V — jurisdiction field on existing Constraint dataclass."""

    def test_constraint_has_jurisdiction_field(self):
        """The existing Constraint dataclass has a jurisdiction field."""
        from constraint_system import Constraint, ConstraintType, ConstraintSeverity
        c = Constraint(
            constraint_id="c1",
            name="test",
            constraint_type=ConstraintType.REGULATORY,
            severity=ConstraintSeverity.HIGH,
            description="test",
            parameter="x",
            operator="<=",
            threshold_value=100,
            jurisdiction="EU",
        )
        self.assertEqual(c.jurisdiction, "EU")
        self.assertIn("jurisdiction", c.to_dict())

    def test_constraint_system_select_by_jurisdiction(self):
        """ConstraintSystem.select_constraints filters by jurisdiction."""
        from constraint_system import ConstraintSystem
        cs = ConstraintSystem()
        c1 = cs.add_constraint(
            name="gdpr_test", constraint_type="regulatory",
            parameter="data", operator="==", threshold_value=True,
        )
        c1.jurisdiction = "EU"
        c2 = cs.add_constraint(
            name="hipaa_test", constraint_type="regulatory",
            parameter="phi", operator="==", threshold_value=True,
        )
        c2.jurisdiction = "US"
        eu_results = cs.select_constraints("EU")
        self.assertTrue(all(c.jurisdiction in ("EU", "GLOBAL") for c in eu_results))


# ===================================================================
# VI. ROLE & RESPONSIBILITY GRAPH
# ===================================================================

class TestActorRegistry(unittest.TestCase):
    """Audit §VI — Unified actor model, authority matrix, delegation."""

    def test_actor_registration(self):
        """Actors can be registered with canonical identity."""
        registry = ActorRegistry()
        actor = Actor(actor_id="a1", name="Alice", kind=ActorKind.HUMAN, role="admin")
        registry.register(actor)
        self.assertIsNotNone(registry.get("a1"))

    def test_authority_matrix_grant_revoke(self):
        """Authority matrix A[actor, action, resource] → bool."""
        matrix = AuthorityMatrix()
        matrix.grant("a1", "deploy", "production")
        self.assertTrue(matrix.is_authorized("a1", "deploy", "production"))
        matrix.revoke("a1", "deploy", "production")
        self.assertFalse(matrix.is_authorized("a1", "deploy", "production"))

    def test_authority_matrix_wildcard(self):
        """Wildcard resource grants access to all resources for an action."""
        matrix = AuthorityMatrix()
        matrix.grant("a1", "read", "*")
        self.assertTrue(matrix.is_authorized("a1", "read", "anything"))

    def test_onboard_with_initial_grants(self):
        """onboard_actor sets initial authority grants."""
        registry = ActorRegistry()
        actor = Actor(actor_id="b1", name="Bot1", kind=ActorKind.BOT)
        registry.onboard(actor, initial_grants=[("generate", "candidates"), ("filter", "*")])
        self.assertTrue(registry.authority.is_authorized("b1", "generate", "candidates"))
        self.assertTrue(registry.authority.is_authorized("b1", "filter", "any"))

    def test_delegation_graph(self):
        """Delegation with transitive closure."""
        registry = ActorRegistry()
        a = Actor(actor_id="a1", name="Alice", kind=ActorKind.HUMAN)
        b = Actor(actor_id="b1", name="Bob", kind=ActorKind.HUMAN)
        c = Actor(actor_id="c1", name="Charlie", kind=ActorKind.BOT)
        registry.register(a)
        registry.register(b)
        registry.register(c)
        registry.delegate("a1", "b1")
        registry.delegate("b1", "c1")
        delegates = registry.transitive_delegates("a1")
        self.assertIn("b1", delegates)
        self.assertIn("c1", delegates)  # transitive

    def test_revoke_delegation(self):
        """Delegation can be revoked."""
        registry = ActorRegistry()
        a = Actor(actor_id="a1", name="A", kind=ActorKind.HUMAN)
        b = Actor(actor_id="b1", name="B", kind=ActorKind.HUMAN)
        registry.register(a)
        registry.register(b)
        registry.delegate("a1", "b1")
        registry.revoke_delegation("a1", "b1")
        self.assertNotIn("b1", registry.transitive_delegates("a1"))

    def test_list_actors_by_kind(self):
        """Can filter actors by kind."""
        registry = ActorRegistry()
        registry.register(Actor(actor_id="h1", name="H", kind=ActorKind.HUMAN))
        registry.register(Actor(actor_id="b1", name="B", kind=ActorKind.BOT))
        humans = registry.list_actors(kind=ActorKind.HUMAN)
        self.assertEqual(len(humans), 1)
        self.assertEqual(humans[0].actor_id, "h1")


# ===================================================================
# VII. SCALING MECHANISM
# ===================================================================

class TestScalingMechanisms(unittest.TestCase):
    """Audit §VII — Dimension registration, constraint dependency."""

    def test_dimension_registration_protocol(self):
        """register_dimension(name, type, bounds) adds to state schema."""
        reg = DimensionRegistry()
        initial = reg.size
        reg.register_dimension("gpu_utilization", "float", (0.0, 100.0))
        self.assertEqual(reg.size, initial + 1)
        self.assertTrue(reg.has_dimension("gpu_utilization"))

    def test_schema_versioning(self):
        """Version increments on dimension registration."""
        reg = DimensionRegistry()
        v1 = reg.version
        reg.register_dimension("new_dim")
        self.assertEqual(reg.version, v1 + 1)


# ===================================================================
# VIII. LLM SYNTHESIS LAYER
# ===================================================================

class TestLLMValidation(unittest.TestCase):
    """Audit §VIII — Structural schema validation for LLM outputs."""

    def test_expert_profile_valid(self):
        """Valid ExpertProfileOutput passes Pydantic validation."""
        data = {
            "expert_id": "exp1",
            "name": "Security Expert",
            "domain": "cybersecurity",
            "capabilities": ["penetration testing"],
            "confidence": 0.85,
        }
        result = validate_llm_output(LLMOutputKind.EXPERT_PROFILE, data)
        self.assertEqual(result.expert_id, "exp1")

    def test_expert_profile_invalid_raises(self):
        """Invalid ExpertProfileOutput raises ValidationError."""
        from pydantic import ValidationError
        data = {"expert_id": "", "name": "", "domain": ""}  # empty strings
        with self.assertRaises(ValidationError):
            validate_llm_output(LLMOutputKind.EXPERT_PROFILE, data)

    def test_gate_proposal_valid(self):
        """Valid GateProposalOutput passes validation."""
        data = {
            "gate_id": "g1",
            "name": "Auth Gate",
            "condition": "confidence > 0.8",
            "threshold": 0.8,
            "severity": "high",
        }
        result = validate_llm_output(LLMOutputKind.GATE_PROPOSAL, data)
        self.assertEqual(result.severity, "high")

    def test_gate_proposal_invalid_severity(self):
        """Invalid severity raises ValidationError."""
        from pydantic import ValidationError
        data = {
            "gate_id": "g1",
            "name": "Test",
            "condition": "x > 0",
            "threshold": 0.5,
            "severity": "INVALID",
        }
        with self.assertRaises(ValidationError):
            validate_llm_output(LLMOutputKind.GATE_PROPOSAL, data)

    def test_recommendation_output_valid(self):
        """Valid RecommendationOutput passes validation."""
        data = {
            "recommendation_id": "r1",
            "title": "Use microservices",
            "description": "Better scalability",
            "confidence": 0.7,
            "pros": ["scalable"],
            "cons": ["complex"],
        }
        result = validate_llm_output(LLMOutputKind.RECOMMENDATION, data)
        self.assertIsInstance(result, RecommendationOutput)


class TestConflictResolution(unittest.TestCase):
    """Audit §VIII — Explicit conflict resolution strategy."""

    def test_priority_resolution(self):
        """Higher-confidence output wins in priority strategy."""
        resolver = ConflictResolver(ResolutionStrategy.PRIORITY)
        a = {"confidence": 0.9, "data": "A"}
        b = {"confidence": 0.3, "data": "B"}
        result = resolver.resolve(a, b)
        self.assertEqual(result.winner, a)
        self.assertFalse(result.escalated)

    def test_hitl_escalation(self):
        """HITL strategy escalates to human."""
        resolver = ConflictResolver(ResolutionStrategy.HUMAN_IN_THE_LOOP)
        a = {"confidence": 0.5}
        b = {"confidence": 0.5}
        result = resolver.resolve(a, b)
        self.assertTrue(result.escalated)
        self.assertIsNone(result.winner)


class TestRegenerationPolicy(unittest.TestCase):
    """Audit §VIII — Regeneration triggers with retry budget."""

    def test_low_confidence_triggers_regen(self):
        """confidence < threshold triggers regeneration."""
        policy = RegenerationPolicy(min_confidence=0.3, max_retries=3)
        self.assertTrue(policy.should_regenerate(confidence=0.1, attempt=0))

    def test_constraint_violation_triggers_regen(self):
        """Constraint violation triggers regeneration."""
        policy = RegenerationPolicy()
        self.assertTrue(policy.should_regenerate(
            confidence=0.9, constraint_violated=True, attempt=0
        ))

    def test_max_retries_stops_regen(self):
        """Regeneration stops after max retries."""
        policy = RegenerationPolicy(max_retries=3)
        self.assertFalse(policy.should_regenerate(confidence=0.1, attempt=3))

    def test_schema_invalid_triggers_regen(self):
        """Invalid schema triggers regeneration."""
        policy = RegenerationPolicy(require_schema_valid=True)
        self.assertTrue(policy.should_regenerate(
            confidence=0.9, schema_valid=False, attempt=0
        ))

    def test_good_output_no_regen(self):
        """Good output does not trigger regeneration."""
        policy = RegenerationPolicy(min_confidence=0.3)
        self.assertFalse(policy.should_regenerate(
            confidence=0.9, constraint_violated=False, schema_valid=True, attempt=0
        ))


# ===================================================================
# Integration: Full control loop
# ===================================================================

class TestFullControlLoop(unittest.TestCase):
    """End-to-end test: observe → compute control → transition → check stability."""

    def test_closed_loop_convergence(self):
        """
        Starting from a low-confidence state, the control loop should drive
        the system toward the target with decreasing Lyapunov function.
        """
        target = CanonicalStateVector(confidence=1.0, authority=1.0)
        current = CanonicalStateVector(confidence=0.2, authority=0.2)

        law = ControlLaw(base_gain=0.5)
        trans = StateTransitionFunction(noise=ProcessNoise.zero())
        lyap = LyapunovFunction(target)
        analyzer = StabilityAnalyzer(lyap)

        trajectory = [current]
        for _ in range(20):
            control = law.compute_control(target, current)
            current = trans.transition(current, control, add_noise=False)
            trajectory.append(current)

        # Lyapunov function should decrease at each step
        all_ok, results = analyzer.check_trajectory(trajectory)
        self.assertTrue(all_ok, "Lyapunov function should decrease at each step")

        # Final state should be closer to target than initial
        self.assertGreater(trajectory[-1].confidence, trajectory[0].confidence)
        self.assertGreater(trajectory[-1].authority, trajectory[0].authority)

        # BIBO stability
        self.assertTrue(analyzer.is_bibo_stable(trajectory))


if __name__ == "__main__":
    unittest.main()
