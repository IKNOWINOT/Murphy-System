"""
LLM Output Manifold Normalizer for the Murphy System.
Design Label: LLM-MANIFOLD-001

Applies manifold retraction to normalize LLM output embeddings onto a unit
sphere or simplex before downstream processing (MSS Magnify/Solidify, swarm
synthesis).  This ensures consistent output magnitude regardless of which
LLM provider (DeepInfra primary, Together.ai fallback, LocalLLMFallback)
generated the response.

Key insight: different providers produce outputs with different magnitude
distributions.  Manifold projection normalizes these onto a common surface
*before* combining, rather than trying to compensate *after* the fact.

Feature flag: MURPHY_MANIFOLD_LLM (default: disabled)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Feature flag
MANIFOLD_LLM_ENABLED: bool = os.environ.get("MURPHY_MANIFOLD_LLM", "0") == "1"

# Lazy import to avoid circular deps
_SphereManifold = None
_SimplexManifold = None


def _ensure_imports() -> None:
    global _SphereManifold, _SimplexManifold
    if _SphereManifold is None:
        from control_theory.manifold_projection import SphereManifold, SimplexManifold
        _SphereManifold = SphereManifold
        _SimplexManifold = SimplexManifold


class LLMOutputNormalizer:
    """
    Manifold-based normalization of LLM outputs.
    Design Label: LLM-MANIFOLD-002

    Normalizes text-derived feature vectors onto a chosen manifold so that
    outputs from different LLM providers have comparable magnitudes and
    geometric properties before entering the MSS pipeline.

    Usage::

        normalizer = LLMOutputNormalizer()
        embedding = normalizer.normalize_text("LLM output text...")
        # embedding is now on the unit sphere
    """

    def __init__(
        self,
        manifold_type: str = "sphere",
        enabled: Optional[bool] = None,
        max_vocab: int = 500,
    ) -> None:
        """
        Args:
            manifold_type: "sphere" for unit sphere, "simplex" for probability simplex.
            enabled: override for feature flag.
            max_vocab: maximum vocabulary size for text vectorization.
        """
        self.manifold_type = manifold_type
        self.enabled = enabled if enabled is not None else MANIFOLD_LLM_ENABLED
        self.max_vocab = max_vocab
        self._manifold = None

    def _get_manifold(self):
        """Lazy-initialize the manifold."""
        if self._manifold is None:
            _ensure_imports()
            if self.manifold_type == "simplex":
                self._manifold = _SimplexManifold()
            else:
                self._manifold = _SphereManifold(radius=1.0)
        return self._manifold

    def normalize_text(self, text: str) -> np.ndarray:
        """
        Convert text to a normalized vector on the manifold.
        Design Label: LLM-MANIFOLD-003

        Process:
          1. Build a TF-IDF-like feature vector from the text.
          2. Project onto the configured manifold.
          3. Return the normalized vector.

        Args:
            text: raw LLM output text.

        Returns:
            Normalized feature vector on the manifold.
            Returns a zero vector if text is empty or normalization fails.
        """
        if not self.enabled:
            # Return a simple unit vector based on text length
            return np.array([1.0, 0.0])

        try:
            features = self._text_to_features(text)
            if features is None or len(features) == 0:
                return np.array([1.0])

            manifold = self._get_manifold()
            return manifold.project(features)
        except Exception as exc:  # LLM-MANIFOLD-ERR-001
            logger.warning(
                "LLM-MANIFOLD-ERR-001: Text normalization failed (%s), "
                "returning unit vector",
                exc,
            )
            return np.array([1.0])

    def normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """
        Project a pre-computed embedding vector onto the manifold.

        Args:
            embedding: raw embedding vector from an LLM provider.

        Returns:
            Normalized embedding on the manifold surface.
        """
        if not self.enabled:
            return embedding

        try:
            manifold = self._get_manifold()
            return manifold.project(embedding)
        except Exception as exc:  # LLM-MANIFOLD-ERR-002
            logger.warning(
                "LLM-MANIFOLD-ERR-002: Embedding normalization failed (%s), "
                "returning original",
                exc,
            )
            return embedding

    def compare_outputs(
        self,
        text_a: str,
        text_b: str,
    ) -> float:
        """
        Compute geodesic distance between two LLM outputs on the manifold.

        Useful for measuring how different two provider outputs are after
        normalization.

        Args:
            text_a: first LLM output.
            text_b: second LLM output.

        Returns:
            Geodesic distance (≥ 0). Lower means more similar.
        """
        try:
            # Build shared vocabulary
            vocab = _build_vocab([text_a, text_b], max_terms=self.max_vocab)
            if not vocab:
                return 0.0

            vec_a = _text_to_vector(text_a, vocab)
            vec_b = _text_to_vector(text_b, vocab)

            manifold = self._get_manifold()
            proj_a = manifold.project(vec_a)
            proj_b = manifold.project(vec_b)

            return manifold.geodesic_distance(proj_a, proj_b)
        except Exception as exc:  # LLM-MANIFOLD-ERR-003
            logger.warning(
                "LLM-MANIFOLD-ERR-003: Output comparison failed (%s)",
                exc,
            )
            return 0.0

    def batch_normalize(
        self,
        texts: List[str],
    ) -> List[np.ndarray]:
        """
        Normalize a batch of LLM outputs onto the manifold.

        Uses a shared vocabulary built from all texts for consistency.

        Args:
            texts: list of LLM output texts.

        Returns:
            List of normalized vectors, one per text.
        """
        if not self.enabled or not texts:
            return [np.array([1.0]) for _ in texts]

        try:
            vocab = _build_vocab(texts, max_terms=self.max_vocab)
            if not vocab:
                return [np.array([1.0]) for _ in texts]

            manifold = self._get_manifold()
            results = []
            for text in texts:
                vec = _text_to_vector(text, vocab)
                results.append(manifold.project(vec))
            return results
        except Exception as exc:  # LLM-MANIFOLD-ERR-003
            logger.warning(
                "LLM-MANIFOLD-ERR-003: Batch normalization failed (%s)",
                exc,
            )
            return [np.array([1.0]) for _ in texts]

    def _text_to_features(self, text: str) -> Optional[np.ndarray]:
        """Convert a single text to a feature vector."""
        vocab = _build_vocab([text], max_terms=self.max_vocab)
        if not vocab:
            return None
        return _text_to_vector(text, vocab)


# ------------------------------------------------------------------ #
# Text vectorization helpers
# ------------------------------------------------------------------ #

def _build_vocab(texts: List[str], max_terms: int = 500) -> Dict[str, int]:
    """Build vocabulary from texts."""
    word_counts: Dict[str, int] = {}
    for text in texts:
        for word in text.lower().split():
            word = word.strip(".,;:!?\"'()[]{}").strip()
            if len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return {w: i for i, (w, _) in enumerate(sorted_words[:max_terms])}


def _text_to_vector(text: str, vocab: Dict[str, int]) -> np.ndarray:
    """Convert text to a TF vector using the given vocabulary."""
    n_terms = len(vocab)
    vec = np.zeros(n_terms)
    words = text.lower().split()
    total_words = max(len(words), 1)
    for word in words:
        word = word.strip(".,;:!?\"'()[]{}").strip()
        if word in vocab:
            vec[vocab[word]] += 1.0
    # TF normalization
    vec = vec / total_words
    return vec
