"""
Murphy System — Knostalgia Engine
==================================
Cognitive memory and reasoning system that models human memory with
impact-weighted decay, familiarity-based category reasoning, and causal
analysis of high-impact patterns for cross-domain replication.

Knostalgia is **category reasoning** — not nostalgia as emotion, but as an
epistemological mechanism.  The system learns by asking "what is this *like*?"
and inherits reasoning frameworks from the most similar prior experience.

Design principles
-----------------
1. Impact-weighted memory: weight = normalize(α * efficiency_delta + β * profit_delta)
2. Human memory model: SHORT_TERM (decays ~24-72hr) → LONG_TERM → DEEP_ARCHIVE
3. Memories are NEVER fired silently — always surfaced conversationally as HITL
   confirmation gates that also reinforce recall.
"""
from __future__ import annotations

import logging
import math
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ml_strategy_engine import AnomalyDetector, AnomalyMethod, _cosine_similarity

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class KnostalgiaMemory:
    """
    A single memory unit inside the Knostalgia Engine.

    The weight field decays over time following the adaptive-decay
    pattern from memory_manager_bot, but high-impact memories decay
    more slowly and have a spike floor to keep them accessible.
    """
    memory_id: str
    content: str
    summary: str
    context: str
    category: str
    reasoning_framework: Dict[str, Any]
    weight: float
    original_impact_weight: float
    efficiency_delta: float
    profit_delta: float
    created_at: float
    last_recall: float
    recall_count: int
    store: str                # "SHORT_TERM" | "LONG_TERM" | "DEEP_ARCHIVE"
    is_spike: bool
    causal_status: str        # "NONE" | "PENDING_ANALYSIS" | "ANALYZED" | "REPLICATED"
    embedding: List[float] = field(default_factory=list)


@dataclass
class RecallResult:
    """Result returned by KnostalgiaEngine.recall()."""
    recalled_memories: List[KnostalgiaMemory]
    new_memory_needed: bool
    recall_prompts: List[str]


# ──────────────────────────────────────────────────────────────────────
# Core engine
# ──────────────────────────────────────────────────────────────────────

class KnostalgiaEngine:
    """
    Knostalgia Engine — cognitive memory system for Murphy.

    Manages impact-weighted short-term and long-term memory stores with
    adaptive decay, spike detection, and HITL-gated recall surfacing.

    Thread-safe via a single internal Lock.
    """

    def __init__(
        self,
        alpha: float = 0.6,
        beta: float = 0.4,
        short_term_threshold: float = 0.4,
        short_term_recall_threshold: float = 0.75,
        long_term_recall_threshold: float = 0.85,
        spike_z_threshold: float = 2.5,
        base_decay_rate: float = 0.95,
        spike_floor: float = 0.15,
    ) -> None:
        """
        Args:
            alpha: Weight given to efficiency_delta when scoring impact.
            beta: Weight given to profit_delta when scoring impact.
            short_term_threshold: Weight threshold below which a SHORT_TERM
                memory is demoted to LONG_TERM.
            short_term_recall_threshold: Minimum weighted_similarity score
                required to surface a SHORT_TERM memory as a recall hit.
            long_term_recall_threshold: Minimum weighted_similarity score
                required to surface a LONG_TERM memory as a recall hit.
            spike_z_threshold: Z-score above which an impact weight is
                considered an anomalous spike and flagged for causal analysis.
            base_decay_rate: Multiplicative decay applied each cycle (0 < r ≤ 1).
            spike_floor: Minimum weight that spike-flagged memories never drop
                below, keeping them retrievable via explicit search.
        """
        self._alpha = alpha
        self._beta = beta
        self._short_term_threshold = short_term_threshold
        self._short_term_recall_threshold = short_term_recall_threshold
        self._long_term_recall_threshold = long_term_recall_threshold
        self._spike_z_threshold = spike_z_threshold
        self._base_decay_rate = base_decay_rate
        self._spike_floor = spike_floor

        self._memories: Dict[str, KnostalgiaMemory] = {}
        self._anomaly_detector = AnomalyDetector(
            method=AnomalyMethod.ZSCORE, threshold=spike_z_threshold
        )
        self._lock = threading.Lock()

        logger.info(
            "KnostalgiaEngine initialised (α=%.2f β=%.2f spike_z=%.1f)",
            alpha, beta, spike_z_threshold,
        )

    # ------------------------------------------------------------------
    # Impact scoring
    # ------------------------------------------------------------------

    def score_impact(self, efficiency_delta: float, profit_delta: float) -> float:
        """Compute impact weight as normalize(α * efficiency_delta + β * profit_delta).

        The raw score is clamped to [0.05, 1.0] so every memory has a
        non-zero starting weight.
        """
        raw = self._alpha * efficiency_delta + self._beta * profit_delta
        # Normalise to [0, 1] via tanh-like squashing then clamp
        normalised = (math.tanh(raw) + 1.0) / 2.0
        return max(0.05, min(1.0, normalised))

    # ------------------------------------------------------------------
    # Memory creation
    # ------------------------------------------------------------------

    def create_memory(
        self,
        content: str,
        summary: str,
        context: str,
        category: str,
        reasoning_framework: Dict[str, Any],
        efficiency_delta: float,
        profit_delta: float,
        embedding: Optional[List[float]] = None,
    ) -> KnostalgiaMemory:
        """Create a new memory, detect spikes, and store in SHORT_TERM.

        The impact weight is computed via :meth:`score_impact`.  If the
        resulting z-score exceeds ``spike_z_threshold`` the memory is
        flagged as a spike and queued for causal analysis.
        """
        now = time.time()
        impact_weight = self.score_impact(efficiency_delta, profit_delta)

        with self._lock:
            # Feed the anomaly detector so it learns the distribution
            result = self._anomaly_detector.detect(impact_weight)
            self._anomaly_detector.feed(impact_weight)

            is_spike = result.is_anomaly and result.score >= self._spike_z_threshold
            causal_status = "PENDING_ANALYSIS" if is_spike else "NONE"

            memory = KnostalgiaMemory(
                memory_id=str(uuid.uuid4()),
                content=content,
                summary=summary,
                context=context,
                category=category,
                reasoning_framework=reasoning_framework,
                weight=impact_weight,
                original_impact_weight=impact_weight,
                efficiency_delta=efficiency_delta,
                profit_delta=profit_delta,
                created_at=now,
                last_recall=now,
                recall_count=0,
                store="SHORT_TERM",
                is_spike=is_spike,
                causal_status=causal_status,
                embedding=embedding or [],
            )
            self._memories[memory.memory_id] = memory

        if is_spike:
            logger.info(
                "Spike detected: memory_id=%s z_score=%.2f category=%s",
                memory.memory_id, result.score, category,
            )

        return memory

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------

    def recall(
        self,
        query_embedding: List[float],
        query_text: str,
    ) -> RecallResult:
        """Search memory stores for matches to the query.

        Searches SHORT_TERM first (lower threshold), then LONG_TERM
        (higher threshold).  DEEP_ARCHIVE is excluded from automatic
        recall — it is only accessible via explicit search.

        Returns:
            A :class:`RecallResult` with matching memories, whether a
            new memory is needed, and pre-built recall prompts.
        """
        recalled: List[KnostalgiaMemory] = []

        with self._lock:
            short_term = [
                m for m in self._memories.values() if m.store == "SHORT_TERM"
            ]
            long_term = [
                m for m in self._memories.values() if m.store == "LONG_TERM"
            ]

        # Search short-term
        for memory in short_term:
            if not memory.embedding or not query_embedding:
                continue
            sim = _cosine_similarity(query_embedding, memory.embedding)
            weighted_sim = sim * memory.weight
            if weighted_sim >= self._short_term_recall_threshold:
                recalled.append(memory)

        # Fall back to long-term only when short-term has no hits
        if not recalled:
            for memory in long_term:
                if not memory.embedding or not query_embedding:
                    continue
                sim = _cosine_similarity(query_embedding, memory.embedding)
                weighted_sim = sim * memory.weight
                if weighted_sim >= self._long_term_recall_threshold:
                    recalled.append(memory)

        prompts = [self.build_recall_prompt(m) for m in recalled]
        new_memory_needed = len(recalled) == 0

        return RecallResult(
            recalled_memories=recalled,
            new_memory_needed=new_memory_needed,
            recall_prompts=prompts,
        )

    # ------------------------------------------------------------------
    # Recall prompt
    # ------------------------------------------------------------------

    def build_recall_prompt(self, memory: KnostalgiaMemory) -> str:
        """Return the human-readable recall prompt for HITL confirmation.

        The prompt serves dual purpose: it is both the confirmation gate
        (HITL) and the reinforcement that snaps the memory weight back.
        """
        return (
            f"Do you mean like {memory.summary}... "
            f"like that one time {memory.context}?"
        )

    # ------------------------------------------------------------------
    # Recall confirmation / rejection
    # ------------------------------------------------------------------

    def on_recall_confirmed(self, memory_id: str) -> None:
        """Confirm a recall hit — snap weight back and move to SHORT_TERM.

        Mimics the biological memory reinforcement: recalling a memory
        brings it back to peak salience (original_impact_weight) and
        moves it back into the active SHORT_TERM store.
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if memory is None:
                logger.warning("on_recall_confirmed: unknown memory_id=%s", memory_id)
                return
            memory.weight = memory.original_impact_weight
            memory.last_recall = time.time()
            memory.recall_count += 1
            if memory.store in ("LONG_TERM", "DEEP_ARCHIVE"):
                memory.store = "SHORT_TERM"
                logger.debug(
                    "Memory %s promoted to SHORT_TERM on recall confirmation",
                    memory_id,
                )

    def on_recall_rejected(self, memory_id: str) -> None:
        """Reject a recall hit — decrement weight and adjust confidence.

        A rejection signals the memory was not relevant, so its weight
        is nudged down slightly to reduce future false-positives.
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if memory is None:
                logger.warning("on_recall_rejected: unknown memory_id=%s", memory_id)
                return
            memory.weight = max(0.0, memory.weight - 0.05)
            logger.debug("Memory %s weight reduced to %.3f on rejection", memory_id, memory.weight)

    # ------------------------------------------------------------------
    # Decay cycle
    # ------------------------------------------------------------------

    def decay_cycle(self) -> None:
        """Apply one round of adaptive decay to all memories.

        Higher-weight memories decay more slowly because:
            adjusted_decay = base_decay_rate + (memory.weight * 0.04)

        Spike-flagged memories are never allowed to drop below
        ``spike_floor`` so they remain retrievable for causal analysis.

        After decay, :meth:`_promote_demote` re-classifies store tiers.
        """
        with self._lock:
            for memory in self._memories.values():
                adjusted_decay = self._base_decay_rate + (memory.weight * 0.04)
                memory.weight = memory.weight * adjusted_decay
                if memory.is_spike:
                    memory.weight = max(self._spike_floor, memory.weight)
            self._promote_demote()

        logger.debug("decay_cycle complete, memories=%d", len(self._memories))

    def _promote_demote(self) -> None:
        """Re-classify memory store tiers based on current weight.

        Must be called with ``self._lock`` held.

        SHORT_TERM < 0.4  →  LONG_TERM
        LONG_TERM  < 0.05 →  DEEP_ARCHIVE (never deleted, only dormant)
        """
        for memory in self._memories.values():
            if memory.store == "SHORT_TERM" and memory.weight < self._short_term_threshold:
                memory.store = "LONG_TERM"
                logger.debug("Memory %s demoted to LONG_TERM (weight=%.3f)", memory.memory_id, memory.weight)
            elif memory.store == "LONG_TERM" and memory.weight < 0.05:
                memory.store = "DEEP_ARCHIVE"
                logger.debug("Memory %s archived to DEEP_ARCHIVE (weight=%.3f)", memory.memory_id, memory.weight)

    # ------------------------------------------------------------------
    # Spike queries
    # ------------------------------------------------------------------

    def get_spikes(self, status: str = "PENDING_ANALYSIS") -> List[KnostalgiaMemory]:
        """Return all spike-flagged memories with the given causal status."""
        with self._lock:
            return [
                m for m in self._memories.values()
                if m.is_spike and m.causal_status == status
            ]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_memory(self, memory_id: str) -> Optional[KnostalgiaMemory]:
        """Retrieve a single memory by id (all stores, including DEEP_ARCHIVE)."""
        with self._lock:
            return self._memories.get(memory_id)

    def all_memories(self) -> List[KnostalgiaMemory]:
        """Return a snapshot of all memories (all stores)."""
        with self._lock:
            return list(self._memories.values())
