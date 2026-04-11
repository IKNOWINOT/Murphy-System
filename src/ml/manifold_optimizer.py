"""
Training Manifold Optimizer for the Murphy System ML subsystem.
Design Label: TRAIN-MANIFOLD-001

Provides Riemannian SGD on the Stiefel manifold for fine-tuning weight
matrices while maintaining orthonormality.  This is the closest analog
to the Stiefel-Muon optimizer described in the Modular Manifolds blog.

Supports two retraction methods:
  - QR retraction  (fast, O(nk²))
  - Cayley retraction (more accurate for small steps, O(n³))

Feature flag: MURPHY_MANIFOLD_TRAINING (default: disabled)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Feature flag
MANIFOLD_TRAINING_ENABLED: bool = os.environ.get("MURPHY_MANIFOLD_TRAINING", "0") == "1"

# Lazy imports
_StiefelManifold = None
_qr_retraction = None
_cayley_retraction = None


def _ensure_imports() -> None:
    global _StiefelManifold, _qr_retraction, _cayley_retraction
    if _StiefelManifold is None:
        from control_theory.manifold_projection import (
            StiefelManifold,
            cayley_retraction,
            qr_retraction,
        )
        _StiefelManifold = StiefelManifold
        _qr_retraction = qr_retraction
        _cayley_retraction = cayley_retraction


@dataclass
class ManifoldTrainingStep:
    """Record of a single training step on the Stiefel manifold."""

    step: int
    loss_before: float
    loss_after: float
    gradient_norm: float
    weight_condition_number: float
    on_manifold: bool
    retraction_method: str


class StiefelOptimizer:
    """
    Riemannian SGD on the Stiefel manifold.
    Design Label: TRAIN-MANIFOLD-002

    Keeps weight matrices on St(n, k) during gradient updates:
      1. Compute Euclidean gradient ∇L.
      2. Project gradient to the tangent space of St(n,k) at W.
      3. Apply retraction R_W(-lr · grad_tangent) → W_new on St(n,k).

    Usage::

        opt = StiefelOptimizer(n=10, k=5, lr=0.01)
        W = opt.initialize()
        for grad in gradients:
            W = opt.step(W, grad)
    """

    def __init__(
        self,
        n: int,
        k: int,
        lr: float = 0.01,
        retraction: Literal["qr", "cayley"] = "qr",
        momentum: float = 0.0,
        grad_clip: float = 10.0,
        enabled: Optional[bool] = None,
    ) -> None:
        """
        Args:
            n: number of rows (ambient dimension).
            k: number of columns (manifold dimension).
            lr: learning rate.
            retraction: "qr" or "cayley".
            momentum: momentum coefficient (0 = no momentum).
            grad_clip: maximum gradient norm before clipping.
            enabled: override for feature flag.
        """
        if k > n:
            raise ValueError(f"k ({k}) must be ≤ n ({n})")
        self.n = n
        self.k = k
        self.lr = lr
        self.retraction = retraction
        self.momentum = momentum
        self.grad_clip = grad_clip
        self.enabled = enabled if enabled is not None else MANIFOLD_TRAINING_ENABLED
        self._velocity: Optional[np.ndarray] = None
        self._step_count: int = 0
        self._history: List[ManifoldTrainingStep] = []

    def initialize(self, seed: int = 42) -> np.ndarray:
        """
        Initialize a random weight matrix on St(n, k).
        Design Label: TRAIN-MANIFOLD-003
        """
        _ensure_imports()
        rng = np.random.default_rng(seed)
        W_init = rng.standard_normal((self.n, self.k))
        return _qr_retraction(W_init)

    def step(
        self,
        W: np.ndarray,
        gradient: np.ndarray,
        loss: Optional[float] = None,
    ) -> np.ndarray:
        """
        Perform one Riemannian SGD step on St(n, k).

        Args:
            W: current weight matrix on St(n, k).
            gradient: Euclidean gradient ∇L with respect to W.
            loss: optional loss value for logging.

        Returns:
            Updated weight matrix W_new on St(n, k).
        """
        if not self.enabled:
            return W

        _ensure_imports()

        try:
            return self._step_impl(W, gradient, loss)
        except Exception as exc:  # TRAIN-MANIFOLD-ERR-001
            logger.warning(
                "TRAIN-MANIFOLD-ERR-001: Stiefel step failed (%s), "
                "returning original W",
                exc,
            )
            return W

    def _step_impl(
        self,
        W: np.ndarray,
        gradient: np.ndarray,
        loss: Optional[float],
    ) -> np.ndarray:
        """Core step implementation."""
        self._step_count += 1

        # 1. Clip gradient
        grad_norm = float(np.linalg.norm(gradient))
        if grad_norm > self.grad_clip:
            gradient = gradient * (self.grad_clip / grad_norm)
            grad_norm = self.grad_clip

        # 2. Project gradient to tangent space of St(n, k) at W
        # Tangent space projection: P_W(Z) = Z - W * sym(W^T Z)
        # where sym(A) = (A + A^T) / 2
        sym = (W.T @ gradient + gradient.T @ W) / 2.0
        tangent_grad = gradient - W @ sym

        # 3. Apply momentum
        if self.momentum > 0.0 and self._velocity is not None:
            tangent_grad = self.momentum * self._velocity + tangent_grad
        self._velocity = tangent_grad.copy()

        # 4. Retraction: R_W(-lr * tangent_grad)
        V = -self.lr * tangent_grad
        if self.retraction == "cayley":
            W_new = _cayley_retraction(W, V)
        else:
            W_new = _qr_retraction(W + V)

        # 5. Verify on manifold
        stiefel = _StiefelManifold(self.n, self.k)
        on_manifold = stiefel.is_on_manifold(W_new, tol=1e-6)
        if not on_manifold:
            # Force re-projection
            W_new = stiefel.project(W_new)

        # 6. Record step
        cond = float(np.linalg.cond(W_new))
        step_record = ManifoldTrainingStep(
            step=self._step_count,
            loss_before=loss if loss is not None else 0.0,
            loss_after=0.0,  # Will be filled by caller
            gradient_norm=grad_norm,
            weight_condition_number=cond,
            on_manifold=on_manifold,
            retraction_method=self.retraction,
        )
        self._history.append(step_record)

        logger.debug(
            "TRAIN-MANIFOLD-002: step=%d grad_norm=%.4f cond=%.4f on_manifold=%s",
            self._step_count, grad_norm, cond, on_manifold,
        )

        return W_new

    @property
    def history(self) -> List[ManifoldTrainingStep]:
        """Return training step history."""
        return list(self._history)

    def is_converged(self, tol: float = 1e-4, window: int = 5) -> bool:
        """
        Check if training has converged based on gradient norm history.

        Returns True if the average gradient norm over the last *window*
        steps is below *tol*.
        """
        if len(self._history) < window:
            return False
        recent = self._history[-window:]
        avg_grad = sum(s.gradient_norm for s in recent) / window
        return avg_grad < tol

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return optimizer diagnostics."""
        if not self._history:
            return {"steps": 0, "enabled": self.enabled}
        last = self._history[-1]
        return {
            "steps": self._step_count,
            "enabled": self.enabled,
            "last_gradient_norm": last.gradient_norm,
            "last_condition_number": last.weight_condition_number,
            "last_on_manifold": last.on_manifold,
            "retraction_method": self.retraction,
            "lr": self.lr,
            "momentum": self.momentum,
        }
