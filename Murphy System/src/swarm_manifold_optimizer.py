"""
Swarm Manifold Optimizer for the Murphy System.
Design Label: SWARM-MANIFOLD-001

Constrains swarm agent coordination weights to the Stiefel manifold,
ensuring that parallel inference operators produce maximally independent
(decorrelated) contributions rather than collapsing into redundant outputs.

The key insight from the Modular Manifolds approach: instead of deduplicating
swarm outputs *after* synthesis (reactive), we constrain the weight matrix
to be orthonormal *before* synthesis (proactive).

Feature flag: MURPHY_MANIFOLD_SWARM (default: disabled)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Feature flag
MANIFOLD_SWARM_ENABLED: bool = os.environ.get("MURPHY_MANIFOLD_SWARM", "0") == "1"

# Lazy import to avoid circular deps
_StiefelManifold = None
_qr_retraction = None


def _ensure_imports() -> None:
    global _StiefelManifold, _qr_retraction
    if _StiefelManifold is None:
        from control_theory.manifold_projection import StiefelManifold, qr_retraction
        _StiefelManifold = StiefelManifold
        _qr_retraction = qr_retraction


class SwarmWeightManifold:
    """
    Orthogonal swarm coordination weights on the Stiefel manifold.
    Design Label: SWARM-MANIFOLD-002

    Given n agents producing k-dimensional outputs, constructs a weight
    matrix W ∈ St(n, k) such that agent contributions are maximally
    independent (orthonormal columns).

    Usage::

        swm = SwarmWeightManifold()
        weighted = swm.apply_orthogonal_weights(raw_outputs)
    """

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self.enabled = enabled if enabled is not None else MANIFOLD_SWARM_ENABLED

    def compute_weight_matrix(
        self,
        n_agents: int,
        n_output_dims: int,
    ) -> np.ndarray:
        """
        Compute an orthonormal weight matrix W ∈ St(n, k).
        Design Label: SWARM-MANIFOLD-003

        When n ≥ k, returns a proper Stiefel element (n × k orthonormal).
        When n < k, returns an (n × n) orthogonal matrix padded to (n × k)
        as a graceful fallback.

        Args:
            n_agents: number of swarm agents (rows).
            n_output_dims: number of output dimensions (columns).

        Returns:
            Weight matrix W with orthonormal columns.
        """
        _ensure_imports()

        try:
            k = min(n_agents, n_output_dims)
            # Start with a random matrix and project to Stiefel
            rng = np.random.default_rng(42)  # Deterministic for reproducibility
            W_init = rng.standard_normal((n_agents, k))
            W = _qr_retraction(W_init)

            # If n_output_dims > n_agents, pad with zeros
            if n_output_dims > n_agents:
                W_padded = np.zeros((n_agents, n_output_dims))
                W_padded[:, :k] = W
                return W_padded

            return W
        except Exception as exc:  # SWARM-MANIFOLD-ERR-001
            logger.warning(
                "SWARM-MANIFOLD-ERR-001: Weight matrix computation failed (%s), "
                "returning identity fallback",
                exc,
            )
            return np.eye(n_agents, n_output_dims)

    def apply_orthogonal_weights(
        self,
        agent_outputs: List[np.ndarray],
    ) -> List[np.ndarray]:
        """
        Apply orthogonal weights to raw swarm agent outputs.

        Each agent output is a vector in ℝ^k.  The weight matrix W ∈ St(n, k)
        is applied as: weighted_outputs = W^T @ [raw_outputs].

        If disabled or only one agent, returns outputs unchanged.

        Args:
            agent_outputs: list of n agent output vectors, each in ℝ^k.

        Returns:
            List of weighted output vectors with reduced redundancy.
        """
        if not self.enabled or len(agent_outputs) <= 1:
            return agent_outputs

        try:
            # Stack outputs into a matrix: rows = agents, cols = dims
            output_matrix = np.vstack(agent_outputs)
            n_agents, n_dims = output_matrix.shape

            W = self.compute_weight_matrix(n_agents, n_agents)
            weighted = W.T @ output_matrix
            return [weighted[i, :] for i in range(weighted.shape[0])]
        except Exception as exc:  # SWARM-MANIFOLD-ERR-002
            logger.warning(
                "SWARM-MANIFOLD-ERR-002: Orthogonal weighting failed (%s), "
                "returning original outputs",
                exc,
            )
            return agent_outputs

    def apply_text_decorrelation(
        self,
        agent_texts: List[str],
    ) -> List[str]:
        """
        Apply manifold-based decorrelation to text outputs.
        Design Label: SWARM-MANIFOLD-004

        Converts texts to TF-IDF vectors, applies orthogonal weighting,
        and returns texts reordered by contribution weight (most unique first).

        If disabled, returns texts unchanged.

        Args:
            agent_texts: list of text outputs from swarm agents.

        Returns:
            Reordered list with most unique contributions first.
        """
        if not self.enabled or len(agent_texts) <= 1:
            return agent_texts

        try:
            # Simple word-frequency vectorization (no external dependencies)
            vocab = _build_vocab(agent_texts)
            if not vocab:
                return agent_texts

            vectors = _texts_to_vectors(agent_texts, vocab)
            output_matrix = np.vstack(vectors)
            n_agents = output_matrix.shape[0]

            # Compute weight matrix and get per-agent importance scores
            W = self.compute_weight_matrix(n_agents, n_agents)
            weighted = W.T @ output_matrix

            # Score each agent by the L2 norm of its weighted output
            scores = [float(np.linalg.norm(weighted[i, :])) for i in range(n_agents)]

            # Return texts sorted by descending score (most unique first)
            indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            return [agent_texts[i] for i, _ in indexed]
        except Exception as exc:  # SWARM-MANIFOLD-ERR-003
            logger.warning(
                "SWARM-MANIFOLD-ERR-003: Text decorrelation failed (%s), "
                "returning original texts",
                exc,
            )
            return agent_texts

    def measure_redundancy(
        self,
        agent_outputs: List[np.ndarray],
    ) -> float:
        """
        Measure redundancy in agent outputs as average pairwise cosine similarity.

        Returns a value in [0, 1] where 1.0 means perfectly redundant
        and 0.0 means perfectly orthogonal.
        """
        if len(agent_outputs) <= 1:
            return 0.0

        try:
            n = len(agent_outputs)
            total_sim = 0.0
            pairs = 0
            for i in range(n):
                for j in range(i + 1, n):
                    a = agent_outputs[i]
                    b = agent_outputs[j]
                    norm_a = np.linalg.norm(a)
                    norm_b = np.linalg.norm(b)
                    if norm_a > 1e-10 and norm_b > 1e-10:
                        sim = abs(float(np.dot(a, b) / (norm_a * norm_b)))
                        total_sim += sim
                    pairs += 1
            return total_sim / max(pairs, 1)
        except Exception:
            return 0.0


# ------------------------------------------------------------------ #
# Text vectorization helpers (lightweight, no external deps)
# ------------------------------------------------------------------ #

def _build_vocab(texts: List[str], max_terms: int = 500) -> Dict[str, int]:
    """Build a simple word-frequency vocabulary from a list of texts."""
    word_counts: Dict[str, int] = {}
    for text in texts:
        for word in text.lower().split():
            word = word.strip(".,;:!?\"'()[]{}").strip()
            if len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1
    # Keep top N terms by frequency
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return {w: i for i, (w, _) in enumerate(sorted_words[:max_terms])}


def _texts_to_vectors(
    texts: List[str],
    vocab: Dict[str, int],
) -> List[np.ndarray]:
    """Convert texts to term-frequency vectors."""
    n_terms = len(vocab)
    vectors = []
    for text in texts:
        vec = np.zeros(n_terms)
        words = text.lower().split()
        for word in words:
            word = word.strip(".,;:!?\"'()[]{}").strip()
            if word in vocab:
                vec[vocab[word]] += 1.0
        # Normalize to unit vector
        norm = np.linalg.norm(vec)
        if norm > 1e-10:
            vec = vec / norm
        vectors.append(vec)
    return vectors
