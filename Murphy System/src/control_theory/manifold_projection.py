"""
Modular Manifold Projection for the Murphy System.
Design Label: MANIFOLD-PROJ-001

Provides abstract and concrete manifold types for constraining state vectors,
weight matrices, and output embeddings to well-conditioned geometric surfaces.

Inspired by the "Modular Manifolds" approach (Thinking Machines Lab) — shifting
from reactive normalization to proactive manifold constraints that keep
parameters well-conditioned *by construction*.

Manifold types:
  - SphereManifold       — unit sphere S^{n-1} (or radius-r sphere)
  - StiefelManifold      — orthonormal frames St(n, k): W^T W = I_k
  - ObliqueManifold      — product of unit spheres (columns on S^{n-1})
  - SimplexManifold      — probability simplex Δ^{n-1}

Each manifold implements:
  - project(x)           — nearest-point projection π_M(x)
  - retract(x, v)        — retraction R_x(v) for optimization steps
  - geodesic_distance(x, y) — intrinsic distance on the manifold
  - is_on_manifold(x)    — membership test with configurable tolerance

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Numerical tolerance for manifold membership checks
_DEFAULT_TOLERANCE: float = 1e-7


# ------------------------------------------------------------------ #
# Abstract base
# ------------------------------------------------------------------ #

class Manifold(ABC):
    """Abstract manifold with projection, retraction, and geodesic distance."""

    @abstractmethod
    def project(self, x: np.ndarray) -> np.ndarray:
        """Project *x* onto the manifold (nearest-point projection π_M)."""

    @abstractmethod
    def retract(self, x: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Retraction R_x(v): move from *x* in tangent direction *v*, land on manifold."""

    @abstractmethod
    def geodesic_distance(self, x: np.ndarray, y: np.ndarray) -> float:
        """Intrinsic (geodesic) distance between two points on the manifold."""

    @abstractmethod
    def is_on_manifold(self, x: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        """Check whether *x* lies on the manifold within tolerance *tol*."""

    def distance_to_manifold(self, x: np.ndarray) -> float:
        """Euclidean distance from *x* to its projection on the manifold."""
        try:
            proj = self.project(x)
            return float(np.linalg.norm(x - proj))
        except Exception:  # MANIFOLD-PROJ-ERR-001
            logger.warning("MANIFOLD-PROJ-ERR-001: distance_to_manifold failed, returning 0.0")
            return 0.0


# ------------------------------------------------------------------ #
# SphereManifold — S^{n-1}(r)
# ------------------------------------------------------------------ #

class SphereManifold(Manifold):
    """
    Sphere manifold S^{n-1}(r) = { x ∈ ℝ^n : ‖x‖ = r }.

    Default radius r = 1.0 gives the standard unit sphere.
    """

    def __init__(self, radius: float = 1.0) -> None:
        if radius <= 0.0:
            raise ValueError(f"Radius must be positive, got {radius}")
        self.radius = radius

    def project(self, x: np.ndarray) -> np.ndarray:
        """π_S(x) = r · x / ‖x‖.  Zero vector maps to a canonical point."""
        norm = float(np.linalg.norm(x))
        if norm < 1e-15:
            # Degenerate: project to north pole
            result = np.zeros_like(x)
            result[0] = self.radius
            return result
        return self.radius * x / norm

    def retract(self, x: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Retraction via normalization: R_x(v) = r · (x + v) / ‖x + v‖."""
        return self.project(x + v)

    def geodesic_distance(self, x: np.ndarray, y: np.ndarray) -> float:
        """d(x, y) = r · arccos(⟨x, y⟩ / r²), clamped for numerical safety."""
        cos_angle = float(np.dot(x, y)) / (self.radius ** 2)
        cos_angle = max(-1.0, min(1.0, cos_angle))
        return self.radius * math.acos(cos_angle)

    def is_on_manifold(self, x: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        return abs(float(np.linalg.norm(x)) - self.radius) < tol


# ------------------------------------------------------------------ #
# StiefelManifold — St(n, k)
# ------------------------------------------------------------------ #

class StiefelManifold(Manifold):
    """
    Stiefel manifold St(n, k) = { W ∈ ℝ^{n×k} : W^T W = I_k }.

    For k = n this is the orthogonal group O(n).
    For k = 1 this is the unit sphere S^{n-1}.
    """

    def __init__(self, n: int, k: int) -> None:
        if k > n:
            raise ValueError(f"k ({k}) must be ≤ n ({n}) for St(n, k)")
        self.n = n
        self.k = k

    def project(self, W: np.ndarray) -> np.ndarray:
        """QR retraction: nearest orthonormal frame via QR decomposition."""
        W = np.atleast_2d(W)
        if W.shape != (self.n, self.k):
            raise ValueError(
                f"Expected shape ({self.n}, {self.k}), got {W.shape}"
            )
        return qr_retraction(W)

    def retract(self, W: np.ndarray, V: np.ndarray) -> np.ndarray:
        """QR retraction: R_W(V) = qf(W + V)."""
        return self.project(W + V)

    def geodesic_distance(self, W1: np.ndarray, W2: np.ndarray) -> float:
        """
        Approximate geodesic distance on St(n, k).

        Uses ‖log(W1^T W2)‖_F as a proxy (exact for O(n)).
        """
        M = W1.T @ W2
        # SVD-based log: d = ‖arccos(σ_i)‖ where σ_i are singular values
        s = np.linalg.svd(M, compute_uv=False)
        s = np.clip(s, -1.0, 1.0)
        return float(np.linalg.norm(np.arccos(s)))

    def is_on_manifold(self, W: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        W = np.atleast_2d(W)
        if W.shape != (self.n, self.k):
            return False
        eye_k = np.eye(self.k)
        return float(np.linalg.norm(W.T @ W - eye_k)) < tol


# ------------------------------------------------------------------ #
# ObliqueManifold — product of unit spheres (column-wise)
# ------------------------------------------------------------------ #

class ObliqueManifold(Manifold):
    """
    Oblique manifold OB(n, k) — each column of W ∈ ℝ^{n×k} lies on S^{n-1}.

    Useful for constraining state vectors where each component group
    should have unit norm independently.
    """

    def __init__(self, n: int, k: int) -> None:
        self.n = n
        self.k = k

    def project(self, W: np.ndarray) -> np.ndarray:
        """Normalize each column to unit norm."""
        W = np.atleast_2d(W)
        norms = np.linalg.norm(W, axis=0, keepdims=True)
        # Avoid division by zero — replace zero columns with canonical basis
        safe_norms = np.where(norms < 1e-15, 1.0, norms)
        result = W / safe_norms
        # Fix zero columns
        for j in range(result.shape[1]):
            if norms[0, j] < 1e-15:
                result[:, j] = 0.0
                result[0, j] = 1.0
        return result

    def retract(self, W: np.ndarray, V: np.ndarray) -> np.ndarray:
        return self.project(W + V)

    def geodesic_distance(self, W1: np.ndarray, W2: np.ndarray) -> float:
        """Sum of per-column geodesic distances on S^{n-1}."""
        total = 0.0
        for j in range(W1.shape[1]):
            cos_a = float(np.dot(W1[:, j], W2[:, j]))
            cos_a = max(-1.0, min(1.0, cos_a))
            total += math.acos(cos_a) ** 2
        return math.sqrt(total)

    def is_on_manifold(self, W: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        W = np.atleast_2d(W)
        norms = np.linalg.norm(W, axis=0)
        return all(abs(n - 1.0) < tol for n in norms)


# ------------------------------------------------------------------ #
# SimplexManifold — Δ^{n-1}
# ------------------------------------------------------------------ #

class SimplexManifold(Manifold):
    """
    Probability simplex Δ^{n-1} = { x ∈ ℝ^n : x_i ≥ 0, Σx_i = 1 }.

    Projection via the efficient algorithm of Duchi et al. (2008).
    """

    def project(self, x: np.ndarray) -> np.ndarray:
        """Project onto the probability simplex."""
        x = np.asarray(x, dtype=float)
        n = len(x)
        if n == 0:
            return x
        # Sort in descending order
        u = np.sort(x)[::-1]
        cumsum = np.cumsum(u)
        rho = np.max(np.where(u + (1.0 - cumsum) / np.arange(1, n + 1) > 0,
                               np.arange(1, n + 1), 0))
        if rho == 0:
            rho = 1
        theta = (cumsum[int(rho) - 1] - 1.0) / rho
        return np.maximum(x - theta, 0.0)

    def retract(self, x: np.ndarray, v: np.ndarray) -> np.ndarray:
        return self.project(x + v)

    def geodesic_distance(self, x: np.ndarray, y: np.ndarray) -> float:
        """
        Fisher–Rao distance on the simplex (Bhattacharyya angle):
        d(x, y) = 2 arccos(Σ √(x_i y_i)).
        """
        inner = float(np.sum(np.sqrt(np.maximum(x, 0.0) * np.maximum(y, 0.0))))
        inner = max(-1.0, min(1.0, inner))
        return 2.0 * math.acos(inner)

    def is_on_manifold(self, x: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        return (np.all(x >= -tol) and abs(float(np.sum(x)) - 1.0) < tol)


# ------------------------------------------------------------------ #
# Utility: QR retraction (shared by Stiefel and others)
# ------------------------------------------------------------------ #

def qr_retraction(W: np.ndarray) -> np.ndarray:
    """
    QR-based retraction onto St(n, k).

    Given W ∈ ℝ^{n×k}, compute Q from W = QR and return Q with
    positive diagonal on R (uniqueness convention).

    Design Label: MANIFOLD-PROJ-002
    """
    try:
        Q, R = np.linalg.qr(W)
        # Ensure uniqueness: make R diagonal positive
        signs = np.sign(np.diag(R))
        signs[signs == 0] = 1.0
        Q = Q * signs[np.newaxis, :]
        return Q
    except Exception:  # MANIFOLD-PROJ-ERR-002
        logger.warning("MANIFOLD-PROJ-ERR-002: QR retraction failed, returning input")
        return W


def cayley_retraction(W: np.ndarray, V: np.ndarray) -> np.ndarray:
    """
    Cayley retraction on St(n, k).

    R_W(V) = (I - τ/2 A)^{-1} (I + τ/2 A) W, where
    A = V W^T - W V^T (skew-symmetric) and τ = 1.

    Design Label: MANIFOLD-PROJ-003

    More accurate than QR for small steps but O(n³) in general.
    """
    try:
        n = W.shape[0]
        A = V @ W.T - W @ V.T
        I_n = np.eye(n)
        half_A = 0.5 * A
        left = np.linalg.inv(I_n - half_A)
        right = I_n + half_A
        return left @ right @ W
    except Exception:  # MANIFOLD-PROJ-ERR-003
        logger.warning("MANIFOLD-PROJ-ERR-003: Cayley retraction failed, falling back to QR")
        return qr_retraction(W + V)


# ------------------------------------------------------------------ #
# Manifold-constrained state vector projection
# ------------------------------------------------------------------ #

class ManifoldStateConstrainer:
    """
    Constrains MFGC state vectors to lie on a chosen manifold.
    Design Label: MANIFOLD-PROJ-004

    After each state update x_{t+1}, applies π_M(x_{t+1}) to project
    the state onto the configured manifold surface.

    Default: SphereManifold with radius = √(n × 0.25) (center of
    the [0,1]^n hypercube at distance √(n × 0.25) from origin).
    """

    def __init__(
        self,
        manifold: Optional[Manifold] = None,
        n_dims: int = 6,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.n_dims = n_dims
        if manifold is not None:
            self.manifold = manifold
        else:
            # Default: sphere of radius that keeps state near center of [0,1]^n
            default_radius = math.sqrt(n_dims * 0.25)
            self.manifold = SphereManifold(radius=default_radius)

    def constrain(self, state_vector: np.ndarray) -> np.ndarray:
        """
        Project *state_vector* onto the manifold.

        Returns the original vector unchanged if the constrainer is disabled
        or if projection fails (hardening: identity fallback).

        Design Label: MANIFOLD-PROJ-005
        """
        if not self.enabled:
            return state_vector

        try:
            projected = self.manifold.project(state_vector)
            logger.debug(
                "MANIFOLD-PROJ-005: Projected state (distance=%.6f)",
                float(np.linalg.norm(state_vector - projected)),
            )
            return projected
        except Exception as exc:  # MANIFOLD-PROJ-ERR-004
            logger.warning(
                "MANIFOLD-PROJ-ERR-004: State projection failed (%s), "
                "returning original vector",
                exc,
            )
            return state_vector

    def is_on_manifold(self, state_vector: np.ndarray, tol: float = _DEFAULT_TOLERANCE) -> bool:
        """Check if state is on the manifold."""
        try:
            return self.manifold.is_on_manifold(state_vector, tol=tol)
        except Exception:  # MANIFOLD-PROJ-ERR-005
            logger.warning("MANIFOLD-PROJ-ERR-005: Manifold check failed")
            return False

    def distance_from_manifold(self, state_vector: np.ndarray) -> float:
        """Compute distance from state to manifold surface."""
        return self.manifold.distance_to_manifold(state_vector)
