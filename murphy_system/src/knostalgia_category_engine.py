"""
Murphy System — Knostalgia Category Engine
============================================
Category reasoning through familiarity matching.

Knostalgia is **epistemological**, not emotional: the system categorises
inputs by asking "what is this *like*?" and inherits proven reasoning
frameworks from the most similar prior experience rather than performing
cold algorithmic clustering.

Each category is represented as a *prototype* — a centroid embedding of
all confirmed members — with a Bayesian confidence score that grows as
more examples are confirmed and contracts when the category is misidentified.

Thread-safe via internal Lock.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.knostalgia_engine import RecallResult
from src.ml_strategy_engine import _cosine_similarity

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CategoryPrototype:
    """
    Prototype representation of a memory category.

    The embedding is the centroid of all confirmed member embeddings.
    Bayesian confidence reflects how coherent and stable this category
    has proven to be over time.
    """
    category_id: str
    name: str
    embedding: List[float]
    reasoning_framework: Dict[str, Any]
    member_count: int
    confidence: float
    created_at: float


@dataclass
class CategoryContext:
    """Result returned by KnostalgiaCategoryEngine.categorize()."""
    category: CategoryPrototype
    confidence: float
    inherited_reasoning_framework: Dict[str, Any]
    is_new_category: bool


# ──────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────

class KnostalgiaCategoryEngine:
    """
    Category reasoning engine for the Knostalgia pipeline.

    Categorises new inputs by similarity to existing prototypes.  When
    recalled memories are available their category is inherited directly
    (familiarity-first).  Bayesian updates keep confidence calibrated as
    more examples flow through the system.
    """

    def __init__(
        self,
        category_confidence_threshold: float = 0.6,
        new_category_threshold: float = 0.5,
    ) -> None:
        """
        Args:
            category_confidence_threshold: Minimum posterior probability
                required to assign an existing category to a new input.
            new_category_threshold: Minimum cosine similarity to the
                nearest prototype before a new category is forked rather
                than created from scratch.
        """
        self._confidence_threshold = category_confidence_threshold
        self._new_category_threshold = new_category_threshold
        self._prototypes: Dict[str, CategoryPrototype] = {}
        self._lock = threading.Lock()

        logger.info(
            "KnostalgiaCategoryEngine initialised "
            "(conf_threshold=%.2f new_threshold=%.2f)",
            category_confidence_threshold, new_category_threshold,
        )

    # ------------------------------------------------------------------
    # Categorisation
    # ------------------------------------------------------------------

    def categorize(
        self,
        input_embedding: List[float],
        memory_context: RecallResult,
    ) -> CategoryContext:
        """Assign a category to *input_embedding* using knostalgia reasoning.

        If ``memory_context`` contains recalled memories their category is
        inherited (familiarity-first path).  Otherwise the engine computes
        Bayesian posterior probabilities against all known prototypes and
        selects the best match above ``category_confidence_threshold``, or
        creates a new category when nothing qualifies.

        Args:
            input_embedding: Vector representation of the new input.
            memory_context: The :class:`RecallResult` from the Knostalgia
                memory recall step.

        Returns:
            A :class:`CategoryContext` with the assigned category and the
            inherited reasoning framework.
        """
        # Fast path: inherit from recalled memory
        if memory_context.recalled_memories:
            best_memory = max(
                memory_context.recalled_memories,
                key=lambda m: _cosine_similarity(input_embedding, m.embedding)
                if m.embedding else 0.0,
            )
            with self._lock:
                proto = self._prototypes.get(best_memory.category)
            if proto is None:
                # Build a transient prototype from the memory's category
                proto = self._make_prototype(
                    name=best_memory.category,
                    embedding=best_memory.embedding or input_embedding,
                    reasoning_framework=best_memory.reasoning_framework,
                )
                with self._lock:
                    self._prototypes[proto.category_id] = proto

            prior = proto.confidence
            likelihood = _cosine_similarity(input_embedding, proto.embedding) if proto.embedding else 0.5
            evidence = self._marginal_likelihood(input_embedding)
            posterior = self._bayesian_update(likelihood, prior, evidence)

            return CategoryContext(
                category=proto,
                confidence=posterior,
                inherited_reasoning_framework=proto.reasoning_framework,
                is_new_category=False,
            )

        # Slow path: compare against all known prototypes
        with self._lock:
            prototypes = list(self._prototypes.values())

        best_proto: Optional[CategoryPrototype] = None
        best_posterior: float = 0.0

        for proto in prototypes:
            if not proto.embedding:
                continue
            likelihood = _cosine_similarity(input_embedding, proto.embedding)
            evidence = self._marginal_likelihood(input_embedding)
            posterior = self._bayesian_update(likelihood, proto.confidence, evidence)
            if posterior > best_posterior:
                best_posterior = posterior
                best_proto = proto

        if best_proto is not None and best_posterior >= self._confidence_threshold:
            return CategoryContext(
                category=best_proto,
                confidence=best_posterior,
                inherited_reasoning_framework=best_proto.reasoning_framework,
                is_new_category=False,
            )

        # Check whether we should fork from the nearest prototype or create fresh
        if best_proto is not None:
            sim = _cosine_similarity(input_embedding, best_proto.embedding)
            if sim >= self._new_category_threshold:
                new_proto = self.fork_category(best_proto.category_id, input_embedding)
                return CategoryContext(
                    category=new_proto,
                    confidence=sim,
                    inherited_reasoning_framework=new_proto.reasoning_framework,
                    is_new_category=True,
                )

        # No match at all — create a brand-new category
        new_proto = self._make_prototype(
            name=f"category_{uuid.uuid4().hex[:8]}",
            embedding=input_embedding,
            reasoning_framework={},
        )
        with self._lock:
            self._prototypes[new_proto.category_id] = new_proto

        return CategoryContext(
            category=new_proto,
            confidence=0.5,
            inherited_reasoning_framework={},
            is_new_category=True,
        )

    # ------------------------------------------------------------------
    # Prototype updates
    # ------------------------------------------------------------------

    def update_prototype(
        self,
        category_id: str,
        new_embedding: List[float],
        confirmed: bool = True,
    ) -> None:
        """Update the prototype centroid with a new confirmed/rejected member.

        Performs an incremental Bayesian update of the embedding (running
        centroid) and adjusts the category confidence accordingly.

        Args:
            category_id: ID of the category prototype to update.
            new_embedding: The embedding to incorporate.
            confirmed: True if the categorisation was confirmed by HITL.
        """
        with self._lock:
            proto = self._prototypes.get(category_id)
            if proto is None:
                logger.warning("update_prototype: unknown category_id=%s", category_id)
                return

            if confirmed:
                proto.member_count += 1
                # Incremental centroid update
                n = proto.member_count
                proto.embedding = [
                    ((n - 1) * old + new) / n
                    for old, new in zip(proto.embedding, new_embedding)
                ] if proto.embedding else list(new_embedding)
                # Bayesian confidence nudge upward
                proto.confidence = min(1.0, proto.confidence + (1.0 - proto.confidence) * 0.1)
            else:
                # Rejection decreases confidence slightly
                proto.confidence = max(0.0, proto.confidence - 0.05)

    def fork_category(
        self,
        parent_category_id: str,
        seed_embedding: List[float],
    ) -> CategoryPrototype:
        """Create a new child category derived from *parent_category_id*.

        The forked category inherits the parent's reasoning framework as a
        starting point and begins with half the parent's confidence.

        Args:
            parent_category_id: ID of the parent prototype.
            seed_embedding: Embedding of the seed example for the new category.

        Returns:
            The newly created :class:`CategoryPrototype`.
        """
        with self._lock:
            parent = self._prototypes.get(parent_category_id)

        if parent is None:
            logger.warning("fork_category: unknown parent_category_id=%s", parent_category_id)
            parent_framework: Dict[str, Any] = {}
            parent_name = "unknown"
            parent_confidence = 0.5
        else:
            parent_framework = dict(parent.reasoning_framework)
            parent_name = parent.name
            parent_confidence = parent.confidence

        new_proto = self._make_prototype(
            name=f"{parent_name}_fork_{uuid.uuid4().hex[:6]}",
            embedding=seed_embedding,
            reasoning_framework=parent_framework,
            initial_confidence=parent_confidence * 0.5,
        )
        with self._lock:
            self._prototypes[new_proto.category_id] = new_proto

        logger.info(
            "Forked category %s from parent %s", new_proto.category_id, parent_category_id
        )
        return new_proto

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_prototype(self, category_id: str) -> Optional[CategoryPrototype]:
        """Return the prototype for *category_id*, or None if not found."""
        with self._lock:
            return self._prototypes.get(category_id)

    def all_prototypes(self) -> List[CategoryPrototype]:
        """Return a snapshot of all known category prototypes."""
        with self._lock:
            return list(self._prototypes.values())

    def find_by_name(self, name: str) -> Optional[CategoryPrototype]:
        """Find a prototype by its human-readable name (case-sensitive)."""
        with self._lock:
            for proto in self._prototypes.values():
                if proto.name == name:
                    return proto
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_prototype(
        self,
        name: str,
        embedding: List[float],
        reasoning_framework: Dict[str, Any],
        initial_confidence: float = 0.5,
    ) -> CategoryPrototype:
        """Construct a new CategoryPrototype (does NOT add to internal dict)."""
        return CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name=name,
            embedding=list(embedding),
            reasoning_framework=reasoning_framework,
            member_count=1,
            confidence=initial_confidence,
            created_at=time.time(),
        )

    def _bayesian_update(
        self, likelihood: float, prior: float, evidence: float
    ) -> float:
        """Compute Bayesian posterior: (likelihood * prior) / evidence."""
        if evidence == 0.0:
            return 0.0
        return (likelihood * prior) / evidence

    def _marginal_likelihood(self, input_embedding: List[float]) -> float:
        """Compute marginal likelihood P(embedding) across all prototypes.

        Used as the denominator in Bayes' theorem.  Falls back to 1.0 when
        no prototypes exist to avoid division by zero.
        """
        with self._lock:
            prototypes = list(self._prototypes.values())

        if not prototypes:
            return 1.0

        total = sum(
            _cosine_similarity(input_embedding, p.embedding) * p.confidence
            for p in prototypes
            if p.embedding
        )
        return total if total > 0.0 else 1.0
