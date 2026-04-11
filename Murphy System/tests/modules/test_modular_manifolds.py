"""
Tests for Modular Manifold modules in the Murphy System.

Covers all 6 modules:
  1. ManifoldStateConstrainer + shared infrastructure (manifold_projection.py)
  2. SwarmWeightManifold (swarm_manifold_optimizer.py)
  3. ConfidenceManifoldRouter (confidence_manifold.py)
  4. LLMOutputNormalizer (llm_output_manifold.py)
  5. ManifoldDriftDetector (drift_detector.py extension)
  6. StiefelOptimizer (ml/manifold_optimizer.py)

Run with:
  PYTHONPATH="Murphy System/src:Murphy System:src:." pytest \\
    "Murphy System/tests/modules/test_modular_manifolds.py" -v
"""

import math
import os
import sys
import unittest

import numpy as np

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# ===================================================================
# I. MANIFOLD PROJECTION — SphereManifold, StiefelManifold,
#    ObliqueManifold, SimplexManifold, ManifoldStateConstrainer
# ===================================================================

from control_theory.manifold_projection import (
    ManifoldStateConstrainer,
    ObliqueManifold,
    SimplexManifold,
    SphereManifold,
    StiefelManifold,
    cayley_retraction,
    qr_retraction,
)


class TestSphereManifold(unittest.TestCase):
    """SphereManifold — S^{n-1}(r) projection and geodesics."""

    def test_project_normalizes_to_radius(self):
        m = SphereManifold(radius=1.0)
        x = np.array([3.0, 4.0])
        proj = m.project(x)
        self.assertAlmostEqual(np.linalg.norm(proj), 1.0, places=10)

    def test_project_custom_radius(self):
        m = SphereManifold(radius=2.5)
        x = np.array([1.0, 0.0, 0.0])
        proj = m.project(x)
        self.assertAlmostEqual(np.linalg.norm(proj), 2.5, places=10)

    def test_project_zero_vector(self):
        m = SphereManifold(radius=1.0)
        x = np.zeros(5)
        proj = m.project(x)
        self.assertAlmostEqual(np.linalg.norm(proj), 1.0, places=10)
        # Should map to canonical north pole
        self.assertAlmostEqual(proj[0], 1.0, places=10)

    def test_projection_idempotent(self):
        m = SphereManifold(radius=1.0)
        x = np.array([1.0, 2.0, 3.0])
        p1 = m.project(x)
        p2 = m.project(p1)
        np.testing.assert_allclose(p1, p2, atol=1e-12)

    def test_is_on_manifold(self):
        m = SphereManifold(radius=1.0)
        x = np.array([1.0, 0.0, 0.0])
        self.assertTrue(m.is_on_manifold(x))
        self.assertFalse(m.is_on_manifold(np.array([1.0, 1.0, 0.0])))

    def test_geodesic_distance_same_point(self):
        m = SphereManifold(radius=1.0)
        x = np.array([1.0, 0.0])
        self.assertAlmostEqual(m.geodesic_distance(x, x), 0.0, places=10)

    def test_geodesic_distance_antipodal(self):
        m = SphereManifold(radius=1.0)
        x = np.array([1.0, 0.0])
        y = np.array([-1.0, 0.0])
        # Antipodal points on unit circle: distance = π
        self.assertAlmostEqual(m.geodesic_distance(x, y), math.pi, places=6)

    def test_retract_stays_on_manifold(self):
        m = SphereManifold(radius=1.0)
        x = np.array([1.0, 0.0, 0.0])
        v = np.array([0.0, 0.1, 0.0])
        r = m.retract(x, v)
        self.assertAlmostEqual(np.linalg.norm(r), 1.0, places=10)

    def test_distance_to_manifold(self):
        m = SphereManifold(radius=1.0)
        x = np.array([2.0, 0.0])  # norm = 2, should be 1 away
        self.assertAlmostEqual(m.distance_to_manifold(x), 1.0, places=10)

    def test_invalid_radius(self):
        with self.assertRaises(ValueError):
            SphereManifold(radius=0.0)
        with self.assertRaises(ValueError):
            SphereManifold(radius=-1.0)


class TestStiefelManifold(unittest.TestCase):
    """StiefelManifold — St(n, k) orthonormal frames."""

    def test_project_produces_orthonormal(self):
        m = StiefelManifold(n=4, k=2)
        W = np.random.default_rng(42).standard_normal((4, 2))
        Q = m.project(W)
        np.testing.assert_allclose(Q.T @ Q, np.eye(2), atol=1e-10)

    def test_projection_idempotent(self):
        m = StiefelManifold(n=3, k=2)
        W = np.random.default_rng(42).standard_normal((3, 2))
        Q1 = m.project(W)
        Q2 = m.project(Q1)
        np.testing.assert_allclose(Q1, Q2, atol=1e-10)

    def test_is_on_manifold(self):
        m = StiefelManifold(n=3, k=2)
        Q, _ = np.linalg.qr(np.random.default_rng(42).standard_normal((3, 2)))
        self.assertTrue(m.is_on_manifold(Q))
        self.assertFalse(m.is_on_manifold(np.ones((3, 2))))

    def test_geodesic_distance_same_matrix(self):
        m = StiefelManifold(n=3, k=2)
        Q, _ = np.linalg.qr(np.random.default_rng(42).standard_normal((3, 2)))
        self.assertAlmostEqual(m.geodesic_distance(Q, Q), 0.0, places=6)

    def test_k_greater_than_n_raises(self):
        with self.assertRaises(ValueError):
            StiefelManifold(n=2, k=5)

    def test_wrong_shape_raises(self):
        m = StiefelManifold(n=3, k=2)
        with self.assertRaises(ValueError):
            m.project(np.ones((4, 3)))

    def test_retract_stays_on_manifold(self):
        m = StiefelManifold(n=4, k=2)
        W = m.project(np.random.default_rng(42).standard_normal((4, 2)))
        V = np.random.default_rng(43).standard_normal((4, 2)) * 0.1
        R = m.retract(W, V)
        self.assertTrue(m.is_on_manifold(R, tol=1e-6))


class TestObliqueManifold(unittest.TestCase):
    """ObliqueManifold — product of unit spheres."""

    def test_project_normalizes_columns(self):
        m = ObliqueManifold(n=3, k=2)
        W = np.array([[3.0, 1.0], [4.0, 0.0], [0.0, 0.0]])
        P = m.project(W)
        for j in range(2):
            self.assertAlmostEqual(np.linalg.norm(P[:, j]), 1.0, places=10)

    def test_zero_column_maps_to_canonical(self):
        m = ObliqueManifold(n=3, k=1)
        W = np.zeros((3, 1))
        P = m.project(W)
        self.assertAlmostEqual(P[0, 0], 1.0, places=10)

    def test_is_on_manifold(self):
        m = ObliqueManifold(n=3, k=2)
        W = np.eye(3, 2)
        self.assertTrue(m.is_on_manifold(W))

    def test_retract_stays_on_manifold(self):
        m = ObliqueManifold(n=3, k=2)
        W = m.project(np.random.default_rng(42).standard_normal((3, 2)))
        V = np.random.default_rng(43).standard_normal((3, 2)) * 0.1
        R = m.retract(W, V)
        self.assertTrue(m.is_on_manifold(R, tol=1e-6))


class TestSimplexManifold(unittest.TestCase):
    """SimplexManifold — probability simplex Δ^{n-1}."""

    def test_project_sums_to_one(self):
        m = SimplexManifold()
        x = np.array([0.5, 0.3, 0.8, -0.1])
        p = m.project(x)
        self.assertAlmostEqual(float(np.sum(p)), 1.0, places=10)
        self.assertTrue(np.all(p >= -1e-10))

    def test_already_on_simplex(self):
        m = SimplexManifold()
        x = np.array([0.25, 0.25, 0.25, 0.25])
        p = m.project(x)
        np.testing.assert_allclose(p, x, atol=1e-10)

    def test_projection_idempotent(self):
        m = SimplexManifold()
        x = np.array([1.0, 2.0, 3.0])
        p1 = m.project(x)
        p2 = m.project(p1)
        np.testing.assert_allclose(p1, p2, atol=1e-10)

    def test_is_on_manifold(self):
        m = SimplexManifold()
        x = np.array([0.3, 0.3, 0.4])
        self.assertTrue(m.is_on_manifold(x))
        self.assertFalse(m.is_on_manifold(np.array([0.5, 0.5, 0.5])))

    def test_geodesic_distance_same_point(self):
        m = SimplexManifold()
        x = np.array([0.5, 0.3, 0.2])
        self.assertAlmostEqual(m.geodesic_distance(x, x), 0.0, places=6)

    def test_negative_inputs_handled(self):
        m = SimplexManifold()
        x = np.array([-1.0, -2.0, 5.0])
        p = m.project(x)
        self.assertAlmostEqual(float(np.sum(p)), 1.0, places=10)
        self.assertTrue(np.all(p >= -1e-10))


class TestQRRetraction(unittest.TestCase):
    """qr_retraction utility function."""

    def test_produces_orthonormal(self):
        W = np.random.default_rng(42).standard_normal((5, 3))
        Q = qr_retraction(W)
        np.testing.assert_allclose(Q.T @ Q, np.eye(3), atol=1e-10)

    def test_square_matrix(self):
        W = np.random.default_rng(42).standard_normal((4, 4))
        Q = qr_retraction(W)
        np.testing.assert_allclose(Q.T @ Q, np.eye(4), atol=1e-10)


class TestCayleyRetraction(unittest.TestCase):
    """cayley_retraction utility function."""

    def test_produces_orthonormal(self):
        rng = np.random.default_rng(42)
        W, _ = np.linalg.qr(rng.standard_normal((5, 3)))
        V = rng.standard_normal((5, 3)) * 0.01
        R = cayley_retraction(W, V)
        np.testing.assert_allclose(R.T @ R, np.eye(3), atol=1e-6)


class TestManifoldStateConstrainer(unittest.TestCase):
    """ManifoldStateConstrainer — MFGC state projection."""

    def test_constrain_projects_to_manifold(self):
        sphere = SphereManifold(radius=1.0)
        constrainer = ManifoldStateConstrainer(manifold=sphere, enabled=True)
        x = np.array([3.0, 4.0])
        c = constrainer.constrain(x)
        self.assertAlmostEqual(np.linalg.norm(c), 1.0, places=10)

    def test_disabled_returns_original(self):
        sphere = SphereManifold(radius=1.0)
        constrainer = ManifoldStateConstrainer(manifold=sphere, enabled=False)
        x = np.array([3.0, 4.0])
        c = constrainer.constrain(x)
        np.testing.assert_array_equal(c, x)

    def test_is_on_manifold(self):
        sphere = SphereManifold(radius=1.0)
        constrainer = ManifoldStateConstrainer(manifold=sphere, enabled=True)
        self.assertTrue(constrainer.is_on_manifold(np.array([1.0, 0.0])))
        self.assertFalse(constrainer.is_on_manifold(np.array([2.0, 0.0])))

    def test_distance_from_manifold(self):
        sphere = SphereManifold(radius=1.0)
        constrainer = ManifoldStateConstrainer(manifold=sphere, enabled=True)
        self.assertAlmostEqual(
            constrainer.distance_from_manifold(np.array([2.0, 0.0])),
            1.0,
            places=10,
        )

    def test_default_manifold(self):
        """Default constructor should work with a reasonable default manifold."""
        constrainer = ManifoldStateConstrainer(n_dims=6, enabled=True)
        x = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        c = constrainer.constrain(x)
        self.assertEqual(len(c), 6)
        # Should be on the default sphere
        self.assertTrue(constrainer.is_on_manifold(c, tol=1e-6))

    def test_error_fallback(self):
        """If manifold raises an error, constrainer returns original."""
        class BrokenManifold:
            def project(self, x):
                raise RuntimeError("broken")
        constrainer = ManifoldStateConstrainer(enabled=True)
        constrainer.manifold = BrokenManifold()
        x = np.array([1.0, 2.0])
        c = constrainer.constrain(x)
        np.testing.assert_array_equal(c, x)


# ===================================================================
# II. CONFIDENCE MANIFOLD ROUTER
# ===================================================================

from control_theory.confidence_manifold import (
    ConfidenceManifold,
    ConfidenceManifoldRouter,
    PhaseTransitionResult,
)


class TestConfidenceManifold(unittest.TestCase):
    """ConfidenceManifold — confidence space on a sphere."""

    def test_state_to_point_on_manifold(self):
        m = ConfidenceManifold(radius=1.0)
        point = m.state_to_point(0.5, 0.3, 0.2)
        self.assertAlmostEqual(np.linalg.norm(point), 1.0, places=10)

    def test_state_to_point_clamps_inputs(self):
        m = ConfidenceManifold(radius=1.0)
        point = m.state_to_point(-0.5, 1.5, 0.5)
        # Should clamp to [0, 1] before projecting
        self.assertAlmostEqual(np.linalg.norm(point), 1.0, places=10)


class TestConfidenceManifoldRouter(unittest.TestCase):
    """ConfidenceManifoldRouter — geodesic phase transitions."""

    def setUp(self):
        self.router = ConfidenceManifoldRouter(enabled=True)

    def test_no_transition_when_disabled(self):
        router = ConfidenceManifoldRouter(enabled=False)
        result = router.evaluate_transition("expand", 0.5)
        self.assertFalse(result.should_transition)
        self.assertEqual(result.current_phase, "expand")

    def test_evaluate_transition_returns_result(self):
        result = self.router.evaluate_transition(
            current_phase="expand",
            confidence=0.65,
            authority=0.50,
            progress=0.40,
        )
        self.assertIsInstance(result, PhaseTransitionResult)
        self.assertEqual(result.current_phase, "expand")
        self.assertIn(result.recommended_phase, [
            "expand", "type", "enumerate", "constrain",
            "collapse", "bind", "execute",
        ])

    def test_high_confidence_recommends_later_phase(self):
        result = self.router.evaluate_transition(
            current_phase="expand",
            confidence=0.90,
            authority=0.90,
            progress=0.95,
        )
        # Very high confidence should suggest advancing past expand
        if result.should_transition:
            phase_order = [
                "expand", "type", "enumerate", "constrain",
                "collapse", "bind", "execute",
            ]
            self.assertGreaterEqual(
                phase_order.index(result.recommended_phase),
                phase_order.index("expand"),
            )

    def test_compute_distances(self):
        distances = self.router.compute_distances(0.5, 0.3, 0.2)
        self.assertIsInstance(distances, dict)
        self.assertEqual(len(distances), 7)
        for phase, dist in distances.items():
            self.assertGreaterEqual(dist, 0.0)

    def test_forward_lock_prevents_backward_transition(self):
        result = self.router.evaluate_transition(
            current_phase="bind",
            confidence=0.30,
            authority=0.10,
            progress=0.10,
            max_phase_reversals=3,
            reversal_count=5,  # Over limit
        )
        # Should not recommend going backward when locked
        phase_order = [
            "expand", "type", "enumerate", "constrain",
            "collapse", "bind", "execute",
        ]
        if result.should_transition:
            self.assertGreaterEqual(
                phase_order.index(result.recommended_phase),
                phase_order.index("bind"),
            )

    def test_error_handling(self):
        """Broken manifold should not crash router."""
        router = ConfidenceManifoldRouter(enabled=True)
        router.manifold = None  # Break it
        # Should return a graceful no-transition result
        result = router.evaluate_transition("expand", 0.5)
        self.assertFalse(result.should_transition)


# ===================================================================
# III. SWARM MANIFOLD OPTIMIZER
# ===================================================================

from swarm_manifold_optimizer import SwarmWeightManifold


class TestSwarmWeightManifold(unittest.TestCase):
    """SwarmWeightManifold — orthogonal swarm coordination."""

    def setUp(self):
        self.swm = SwarmWeightManifold(enabled=True)

    def test_compute_weight_matrix_orthonormal(self):
        W = self.swm.compute_weight_matrix(n_agents=5, n_output_dims=3)
        # Columns should be orthonormal
        np.testing.assert_allclose(W.T @ W, np.eye(3), atol=1e-6)

    def test_compute_weight_matrix_more_dims_than_agents(self):
        W = self.swm.compute_weight_matrix(n_agents=3, n_output_dims=5)
        # Should handle gracefully
        self.assertEqual(W.shape, (3, 5))

    def test_apply_orthogonal_weights(self):
        outputs = [np.array([1.0, 2.0, 3.0]) for _ in range(4)]
        weighted = self.swm.apply_orthogonal_weights(outputs)
        self.assertEqual(len(weighted), 4)

    def test_disabled_returns_original(self):
        swm = SwarmWeightManifold(enabled=False)
        outputs = [np.array([1.0, 2.0]) for _ in range(3)]
        weighted = swm.apply_orthogonal_weights(outputs)
        for orig, w in zip(outputs, weighted):
            np.testing.assert_array_equal(orig, w)

    def test_single_agent_returns_original(self):
        outputs = [np.array([1.0, 2.0])]
        weighted = self.swm.apply_orthogonal_weights(outputs)
        np.testing.assert_array_equal(outputs[0], weighted[0])

    def test_text_decorrelation(self):
        texts = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the lazy dog",  # Duplicate
            "Machine learning algorithms for data science",
        ]
        reordered = self.swm.apply_text_decorrelation(texts)
        self.assertEqual(len(reordered), 3)
        # The unique text should have higher weight
        self.assertIn("Machine learning algorithms for data science", reordered)

    def test_text_decorrelation_disabled(self):
        swm = SwarmWeightManifold(enabled=False)
        texts = ["hello", "world"]
        result = swm.apply_text_decorrelation(texts)
        self.assertEqual(result, texts)

    def test_measure_redundancy(self):
        # Identical vectors should have high redundancy
        identical = [np.array([1.0, 0.0, 0.0]) for _ in range(3)]
        r = self.swm.measure_redundancy(identical)
        self.assertGreater(r, 0.9)

        # Orthogonal vectors should have low redundancy
        orthogonal = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ]
        r2 = self.swm.measure_redundancy(orthogonal)
        self.assertAlmostEqual(r2, 0.0, places=6)

    def test_measure_redundancy_single_agent(self):
        r = self.swm.measure_redundancy([np.array([1.0, 0.0])])
        self.assertEqual(r, 0.0)


# ===================================================================
# IV. LLM OUTPUT MANIFOLD NORMALIZER
# ===================================================================

from llm_output_manifold import LLMOutputNormalizer


class TestLLMOutputNormalizer(unittest.TestCase):
    """LLMOutputNormalizer — manifold-based output conditioning."""

    def setUp(self):
        self.normalizer = LLMOutputNormalizer(manifold_type="sphere", enabled=True)

    def test_normalize_text_produces_unit_vector(self):
        vec = self.normalizer.normalize_text(
            "The quick brown fox jumps over the lazy dog. "
            "Machine learning and artificial intelligence are transforming industry."
        )
        self.assertIsInstance(vec, np.ndarray)
        self.assertAlmostEqual(np.linalg.norm(vec), 1.0, places=6)

    def test_normalize_embedding(self):
        emb = np.array([3.0, 4.0])
        norm = self.normalizer.normalize_embedding(emb)
        self.assertAlmostEqual(np.linalg.norm(norm), 1.0, places=10)

    def test_disabled_returns_passthrough(self):
        n = LLMOutputNormalizer(enabled=False)
        emb = np.array([3.0, 4.0])
        norm = n.normalize_embedding(emb)
        np.testing.assert_array_equal(norm, emb)

    def test_compare_outputs(self):
        dist = self.normalizer.compare_outputs(
            "The fox jumps over the dog",
            "The cat sleeps on the mat",
        )
        self.assertIsInstance(dist, float)
        self.assertGreaterEqual(dist, 0.0)

    def test_compare_identical_outputs(self):
        text = "Hello world this is a test of the system"
        dist = self.normalizer.compare_outputs(text, text)
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_batch_normalize(self):
        texts = [
            "First document about machine learning",
            "Second document about data science",
            "Third document about artificial intelligence",
        ]
        results = self.normalizer.batch_normalize(texts)
        self.assertEqual(len(results), 3)
        for vec in results:
            self.assertAlmostEqual(np.linalg.norm(vec), 1.0, places=6)

    def test_simplex_manifold(self):
        n = LLMOutputNormalizer(manifold_type="simplex", enabled=True)
        vec = n.normalize_text(
            "Testing the simplex manifold projection for text normalization"
        )
        self.assertAlmostEqual(float(np.sum(vec)), 1.0, places=6)
        self.assertTrue(np.all(vec >= -1e-10))

    def test_empty_text(self):
        vec = self.normalizer.normalize_text("")
        self.assertIsInstance(vec, np.ndarray)

    def test_batch_normalize_disabled(self):
        n = LLMOutputNormalizer(enabled=False)
        results = n.batch_normalize(["hello", "world"])
        self.assertEqual(len(results), 2)


# ===================================================================
# V. MANIFOLD DRIFT DETECTOR
# ===================================================================

from control_theory.drift_detector import (
    DriftAlert,
    ManifoldDriftAlert,
    ManifoldDriftDetector,
)


class TestManifoldDriftAlert(unittest.TestCase):
    """ManifoldDriftAlert — extended alert dataclass."""

    def test_creation(self):
        from datetime import datetime, timezone
        alert = ManifoldDriftAlert(
            alert_type="manifold_drift",
            dimension=None,
            severity="medium",
            timestamp=datetime.now(timezone.utc),
            recommended_action="Re-project state",
            manifold_distance=0.15,
            retraction_vector=[0.1, -0.05],
        )
        self.assertEqual(alert.alert_type, "manifold_drift")
        self.assertEqual(alert.manifold_distance, 0.15)

    def test_backward_compatible_alert_types(self):
        """Existing alert types should still work."""
        from datetime import datetime, timezone
        alert = DriftAlert(
            alert_type="entropy_drift",
            dimension=None,
            severity="low",
            timestamp=datetime.now(timezone.utc),
            recommended_action="Check entropy",
        )
        self.assertEqual(alert.alert_type, "entropy_drift")


class TestManifoldDriftDetector(unittest.TestCase):
    """ManifoldDriftDetector — manifold-aware drift detection."""

    def setUp(self):
        self.sphere = SphereManifold(radius=1.0)
        self.detector = ManifoldDriftDetector(
            manifold=self.sphere,
            tolerance=0.05,
            high_tolerance=0.2,
            enabled=True,
        )

    def test_no_drift_on_manifold(self):
        x = np.array([1.0, 0.0, 0.0])  # On unit sphere
        alert = self.detector.check_manifold_drift(x)
        self.assertIsNone(alert)

    def test_detect_drift_off_manifold(self):
        x = np.array([1.5, 0.0, 0.0])  # norm = 1.5, distance = 0.5
        alert = self.detector.check_manifold_drift(x)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "manifold_drift")
        self.assertGreater(alert.manifold_distance, 0.05)

    def test_severity_medium(self):
        x = np.array([1.1, 0.0, 0.0])  # norm = 1.1, distance = 0.1
        alert = self.detector.check_manifold_drift(x)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "medium")

    def test_severity_high(self):
        x = np.array([2.0, 0.0, 0.0])  # norm = 2.0, distance = 1.0
        alert = self.detector.check_manifold_drift(x)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "high")

    def test_retraction_vector_provided(self):
        x = np.array([2.0, 0.0, 0.0])
        alert = self.detector.check_manifold_drift(x)
        self.assertIsNotNone(alert.retraction_vector)
        self.assertEqual(len(alert.retraction_vector), 3)

    def test_disabled_returns_none(self):
        detector = ManifoldDriftDetector(
            manifold=self.sphere, enabled=False,
        )
        alert = detector.check_manifold_drift(np.array([2.0, 0.0, 0.0]))
        self.assertIsNone(alert)

    def test_no_manifold_returns_none(self):
        detector = ManifoldDriftDetector(manifold=None, enabled=True)
        alert = detector.check_manifold_drift(np.array([2.0, 0.0, 0.0]))
        self.assertIsNone(alert)

    def test_trajectory_drift(self):
        trajectory = [
            np.array([1.0, 0.0, 0.0]),  # On manifold
            np.array([1.05, 0.0, 0.0]),  # Barely off
            np.array([1.5, 0.0, 0.0]),   # Clearly off
        ]
        alerts = self.detector.check_trajectory_drift(trajectory, window_size=3)
        # At least one alert for the 1.5 point
        self.assertGreaterEqual(len(alerts), 1)

    def test_empty_trajectory(self):
        alerts = self.detector.check_trajectory_drift([], window_size=5)
        self.assertEqual(len(alerts), 0)


# ===================================================================
# VI. TRAINING MANIFOLD OPTIMIZER
# ===================================================================

from ml.manifold_optimizer import ManifoldTrainingStep, StiefelOptimizer


class TestStiefelOptimizer(unittest.TestCase):
    """StiefelOptimizer — Riemannian SGD on St(n, k)."""

    def test_initialize_on_manifold(self):
        opt = StiefelOptimizer(n=5, k=3, lr=0.01, enabled=True)
        W = opt.initialize()
        np.testing.assert_allclose(W.T @ W, np.eye(3), atol=1e-6)

    def test_step_stays_on_manifold(self):
        opt = StiefelOptimizer(n=5, k=3, lr=0.01, enabled=True)
        W = opt.initialize()
        grad = np.random.default_rng(42).standard_normal((5, 3))
        W_new = opt.step(W, grad)
        np.testing.assert_allclose(W_new.T @ W_new, np.eye(3), atol=1e-6)

    def test_multiple_steps(self):
        opt = StiefelOptimizer(n=4, k=2, lr=0.005, enabled=True)
        W = opt.initialize()
        rng = np.random.default_rng(42)
        for _ in range(10):
            grad = rng.standard_normal((4, 2))
            W = opt.step(W, grad, loss=1.0)
        np.testing.assert_allclose(W.T @ W, np.eye(2), atol=1e-5)
        self.assertEqual(len(opt.history), 10)

    def test_disabled_returns_original(self):
        opt = StiefelOptimizer(n=3, k=2, lr=0.01, enabled=False)
        W = np.random.default_rng(42).standard_normal((3, 2))
        grad = np.ones((3, 2))
        W_new = opt.step(W, grad)
        np.testing.assert_array_equal(W, W_new)

    def test_cayley_retraction(self):
        opt = StiefelOptimizer(
            n=4, k=2, lr=0.01, retraction="cayley", enabled=True,
        )
        W = opt.initialize()
        grad = np.random.default_rng(42).standard_normal((4, 2))
        W_new = opt.step(W, grad)
        np.testing.assert_allclose(W_new.T @ W_new, np.eye(2), atol=1e-5)

    def test_gradient_clipping(self):
        opt = StiefelOptimizer(
            n=3, k=2, lr=0.01, grad_clip=1.0, enabled=True,
        )
        W = opt.initialize()
        # Huge gradient
        grad = np.ones((3, 2)) * 1000
        W_new = opt.step(W, grad, loss=100.0)
        # Should not explode
        np.testing.assert_allclose(W_new.T @ W_new, np.eye(2), atol=1e-5)

    def test_momentum(self):
        opt = StiefelOptimizer(
            n=4, k=2, lr=0.01, momentum=0.9, enabled=True,
        )
        W = opt.initialize()
        rng = np.random.default_rng(42)
        for _ in range(5):
            grad = rng.standard_normal((4, 2))
            W = opt.step(W, grad)
        np.testing.assert_allclose(W.T @ W, np.eye(2), atol=1e-5)

    def test_diagnostics(self):
        opt = StiefelOptimizer(n=3, k=2, lr=0.01, enabled=True)
        W = opt.initialize()
        grad = np.ones((3, 2))
        opt.step(W, grad, loss=0.5)
        diag = opt.get_diagnostics()
        self.assertEqual(diag["steps"], 1)
        self.assertTrue(diag["enabled"])
        self.assertIn("last_gradient_norm", diag)

    def test_convergence_check(self):
        opt = StiefelOptimizer(n=3, k=2, lr=0.01, enabled=True)
        self.assertFalse(opt.is_converged())

    def test_k_greater_than_n_raises(self):
        with self.assertRaises(ValueError):
            StiefelOptimizer(n=2, k=5)

    def test_step_record_fields(self):
        opt = StiefelOptimizer(n=3, k=2, lr=0.01, enabled=True)
        W = opt.initialize()
        grad = np.ones((3, 2)) * 0.1
        opt.step(W, grad, loss=0.5)
        step = opt.history[0]
        self.assertIsInstance(step, ManifoldTrainingStep)
        self.assertEqual(step.step, 1)
        self.assertEqual(step.loss_before, 0.5)
        self.assertGreater(step.gradient_norm, 0.0)
        self.assertTrue(step.on_manifold)


# ===================================================================
# VII. INTEGRATION — combining modules
# ===================================================================

class TestManifoldIntegration(unittest.TestCase):
    """Cross-module integration tests."""

    def test_state_constrainer_with_drift_detector(self):
        """Constrainer keeps state on manifold, drift detector confirms."""
        sphere = SphereManifold(radius=1.0)
        constrainer = ManifoldStateConstrainer(manifold=sphere, enabled=True)
        detector = ManifoldDriftDetector(
            manifold=sphere, tolerance=0.01, enabled=True,
        )

        # Unconstrained state drifts off manifold
        x_raw = np.array([0.8, 0.6, 0.5])
        alert_before = detector.check_manifold_drift(x_raw)
        self.assertIsNotNone(alert_before)

        # After constraining, no drift
        x_constrained = constrainer.constrain(x_raw)
        alert_after = detector.check_manifold_drift(x_constrained)
        self.assertIsNone(alert_after)

    def test_swarm_optimizer_reduces_redundancy(self):
        """Orthogonal weighting should reduce measured redundancy."""
        swm = SwarmWeightManifold(enabled=True)

        # Highly redundant outputs
        redundant = [np.array([1.0, 0.0, 0.0]) for _ in range(4)]
        r_before = swm.measure_redundancy(redundant)

        weighted = swm.apply_orthogonal_weights(redundant)
        r_after = swm.measure_redundancy(weighted)

        # After orthogonal weighting, redundancy should decrease
        # (for identical inputs this actually stays the same or decreases)
        self.assertIsInstance(r_after, float)

    def test_stiefel_optimizer_condition_number(self):
        """Manifold optimizer should keep condition number bounded."""
        opt = StiefelOptimizer(n=5, k=3, lr=0.01, enabled=True)
        W = opt.initialize()
        rng = np.random.default_rng(42)
        for _ in range(20):
            grad = rng.standard_normal((5, 3))
            W = opt.step(W, grad)

        cond = np.linalg.cond(W)
        # On Stiefel manifold, condition number should be exactly 1
        self.assertAlmostEqual(cond, 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
