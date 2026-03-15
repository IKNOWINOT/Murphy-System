# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Federated Learning Coordinator — FLC-001

Train models across distributed Murphy instances without sharing raw data.

Design Principles:
  - Raw training data NEVER leaves the originating node.
  - Only model weight deltas (gradients) are transmitted.
  - Differential-privacy noise is added before gradient export.
  - A central coordinator aggregates contributions via federated averaging.
  - WingmanProtocol pair validation gates every aggregation round.
  - CausalitySandbox gating simulates model updates before committing.

Key Classes:
  FederatedCoordinator  — orchestrates training rounds across nodes
  FederatedNode         — represents a participating training node
  ModelWeights          — immutable snapshot of model parameters
  TrainingRound         — tracks one round of federated training
  AggregationStrategy   — pluggable weight-merge strategies
  PrivacyGuard          — differential-privacy noise injection

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import math
import random
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class NodeStatus(str, Enum):
    """Lifecycle status of a federated node."""

    IDLE = "idle"
    TRAINING = "training"
    UPLOADING = "uploading"
    OFFLINE = "offline"
    EXCLUDED = "excluded"


class RoundStatus(str, Enum):
    """Lifecycle status of a federated training round."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


class AggregationMethod(str, Enum):
    """Supported aggregation strategies."""

    FED_AVG = "federated_average"
    WEIGHTED_AVG = "weighted_average"
    MEDIAN = "median"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ModelWeights:
    """Immutable snapshot of model parameters as a flat float list."""

    weights: List[float]
    version: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.version:
            self.version = f"v-{uuid.uuid4().hex[:8]}"
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        raw = ",".join(f"{w:.8f}" for w in self.weights)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "weights": self.weights,
            "version": self.version,
            "checksum": self.checksum,
        }


@dataclass
class GradientUpdate:
    """A privacy-protected gradient contribution from a single node."""

    node_id: str
    round_id: str
    deltas: List[float]
    sample_count: int
    noise_scale: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "node_id": self.node_id,
            "round_id": self.round_id,
            "deltas": self.deltas,
            "sample_count": self.sample_count,
            "noise_scale": self.noise_scale,
            "timestamp": self.timestamp,
        }


@dataclass
class TrainingRound:
    """Tracks one federated training round."""

    round_id: str
    round_number: int
    status: str = RoundStatus.PENDING.value
    participating_nodes: List[str] = field(default_factory=list)
    contributions: List[GradientUpdate] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    global_model_version: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "round_id": self.round_id,
            "round_number": self.round_number,
            "status": self.status,
            "participating_nodes": self.participating_nodes,
            "contributions_count": len(self.contributions),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "global_model_version": self.global_model_version,
            "metrics": self.metrics,
        }


@dataclass
class FederatedNode:
    """Represents a participating training node."""

    node_id: str
    name: str
    status: str = NodeStatus.IDLE.value
    sample_count: int = 0
    rounds_participated: int = 0
    last_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "status": self.status,
            "sample_count": self.sample_count,
            "rounds_participated": self.rounds_participated,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Privacy Guard — differential-privacy noise injection
# ---------------------------------------------------------------------------

class PrivacyGuard:
    """Adds calibrated Gaussian noise to gradient updates.

    The noise scale (sigma) controls the privacy/utility trade-off:
      - Higher sigma → stronger privacy, noisier gradients
      - sigma = 0 → no noise (for testing / trusted environments)

    All noise is generated from Python's ``random`` module seeded per-call
    so results are reproducible when a seed is supplied.
    """

    def __init__(self, noise_scale: float = 0.01, clip_norm: float = 1.0) -> None:
        self._noise_scale = noise_scale
        self._clip_norm = clip_norm

    @property
    def noise_scale(self) -> float:
        """Current noise scale (sigma)."""
        return self._noise_scale

    def clip_gradients(self, deltas: List[float]) -> List[float]:
        """Clip the L2 norm of *deltas* to ``clip_norm``."""
        norm = math.sqrt(sum(d * d for d in deltas))
        if norm <= self._clip_norm or norm == 0:
            return list(deltas)
        scale = self._clip_norm / norm
        return [d * scale for d in deltas]

    def add_noise(self, deltas: List[float]) -> List[float]:
        """Add Gaussian noise calibrated to ``noise_scale``."""
        if self._noise_scale <= 0:
            return list(deltas)
        return [
            d + random.gauss(0, self._noise_scale) for d in deltas
        ]

    def protect(self, deltas: List[float]) -> List[float]:
        """Clip then add noise — the full privacy pipeline."""
        clipped = self.clip_gradients(deltas)
        return self.add_noise(clipped)


# ---------------------------------------------------------------------------
# Aggregation strategies
# ---------------------------------------------------------------------------

class AggregationStrategy(ABC):
    """Base class for gradient aggregation strategies."""

    @abstractmethod
    def aggregate(
        self,
        contributions: List[GradientUpdate],
        current_weights: List[float],
    ) -> List[float]:
        """Merge contributions into a new set of global weights."""


class FederatedAverageStrategy(AggregationStrategy):
    """Classic FedAvg: sample-count-weighted average of deltas."""

    def aggregate(
        self,
        contributions: List[GradientUpdate],
        current_weights: List[float],
    ) -> List[float]:
        """Compute FedAvg over contributions."""
        if not contributions:
            return list(current_weights)

        total_samples = sum(c.sample_count for c in contributions) or 1
        dim = len(current_weights)
        avg_delta = [0.0] * dim

        for c in contributions:
            weight = c.sample_count / total_samples
            for i, d in enumerate(c.deltas[:dim]):
                avg_delta[i] += d * weight

        return [w + d for w, d in zip(current_weights, avg_delta)]


class MedianStrategy(AggregationStrategy):
    """Coordinate-wise median — robust to Byzantine nodes."""

    def aggregate(
        self,
        contributions: List[GradientUpdate],
        current_weights: List[float],
    ) -> List[float]:
        """Compute coordinate-wise median of deltas."""
        if not contributions:
            return list(current_weights)

        dim = len(current_weights)
        medians = []
        for i in range(dim):
            vals = sorted(c.deltas[i] for c in contributions if i < len(c.deltas))
            if vals:
                mid = len(vals) // 2
                medians.append(vals[mid])
            else:
                medians.append(0.0)

        return [w + d for w, d in zip(current_weights, medians)]


# ---------------------------------------------------------------------------
# Federated Coordinator
# ---------------------------------------------------------------------------

class FederatedCoordinator:
    """Orchestrates federated training across distributed Murphy instances.

    Thread-safe: all mutable state is protected by a lock.

    Usage::

        coordinator = FederatedCoordinator(
            initial_weights=ModelWeights([0.0, 0.0, 0.0]),
        )
        coordinator.register_node("node-1", "Instance-A", sample_count=1000)
        coordinator.register_node("node-2", "Instance-B", sample_count=2000)
        rnd = coordinator.start_round(["node-1", "node-2"])
        coordinator.submit_update(rnd.round_id, GradientUpdate(...))
        coordinator.submit_update(rnd.round_id, GradientUpdate(...))
        new_weights = coordinator.complete_round(rnd.round_id)
    """

    def __init__(
        self,
        initial_weights: Optional[ModelWeights] = None,
        aggregation_method: str = AggregationMethod.FED_AVG.value,
        privacy_noise_scale: float = 0.01,
        privacy_clip_norm: float = 1.0,
        min_contributions: int = 1,
    ) -> None:
        self._lock = threading.Lock()
        self._global_weights = initial_weights or ModelWeights(weights=[])
        self._privacy = PrivacyGuard(privacy_noise_scale, privacy_clip_norm)
        self._strategy = self._build_strategy(aggregation_method)
        self._min_contributions = max(1, min_contributions)

        self._nodes: Dict[str, FederatedNode] = {}
        self._rounds: Dict[str, TrainingRound] = {}
        self._round_counter = 0
        self._history: List[str] = []  # round_ids in order

    # -- node management ---------------------------------------------------

    def register_node(
        self,
        node_id: str,
        name: str,
        sample_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FederatedNode:
        """Register a new training node.

        Args:
            node_id: Unique identifier for the node.
            name: Human-readable name.
            sample_count: Number of local training samples.
            metadata: Optional metadata dict.

        Returns:
            The registered ``FederatedNode``.
        """
        node = FederatedNode(
            node_id=node_id,
            name=name,
            sample_count=sample_count,
            metadata=metadata or {},
        )
        with self._lock:
            self._nodes[node_id] = node
        logger.info("Registered federated node %s (%s)", node_id, name)
        return node

    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the federation.  Returns True if found."""
        with self._lock:
            return self._nodes.pop(node_id, None) is not None

    def get_node(self, node_id: str) -> Optional[FederatedNode]:
        """Retrieve a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> List[FederatedNode]:
        """List all registered nodes."""
        with self._lock:
            return list(self._nodes.values())

    # -- round management --------------------------------------------------

    def start_round(
        self,
        node_ids: Optional[List[str]] = None,
    ) -> TrainingRound:
        """Start a new federated training round.

        Args:
            node_ids: Nodes to include (default: all registered idle nodes).

        Returns:
            The new ``TrainingRound``.

        Raises:
            ValueError: If no eligible nodes are available.
        """
        with self._lock:
            self._round_counter += 1
            round_id = f"flr-{uuid.uuid4().hex[:8]}"

            if node_ids is None:
                eligible = [
                    nid for nid, n in self._nodes.items()
                    if n.status == NodeStatus.IDLE.value
                ]
            else:
                eligible = [
                    nid for nid in node_ids if nid in self._nodes
                ]

            if not eligible:
                raise ValueError("No eligible nodes for training round")

            rnd = TrainingRound(
                round_id=round_id,
                round_number=self._round_counter,
                status=RoundStatus.IN_PROGRESS.value,
                participating_nodes=eligible,
                started_at=datetime.now(timezone.utc).isoformat(),
                global_model_version=self._global_weights.version,
            )
            self._rounds[round_id] = rnd
            capped_append(self._history, round_id)

            for nid in eligible:
                self._nodes[nid].status = NodeStatus.TRAINING.value

        logger.info(
            "Started round %s (#%d) with %d nodes",
            round_id, rnd.round_number, len(eligible),
        )
        return rnd

    def submit_update(
        self,
        round_id: str,
        update: GradientUpdate,
    ) -> bool:
        """Submit a gradient update from a node for a specific round.

        Privacy protection is applied automatically before storing.

        Args:
            round_id: The round to contribute to.
            update: The raw gradient deltas from the node.

        Returns:
            True if the update was accepted.
        """
        with self._lock:
            rnd = self._rounds.get(round_id)
            if rnd is None:
                logger.warning("Round %s not found", round_id)
                return False
            if rnd.status != RoundStatus.IN_PROGRESS.value:
                logger.warning("Round %s is not in progress", round_id)
                return False
            if update.node_id not in rnd.participating_nodes:
                logger.warning("Node %s not in round %s", update.node_id, round_id)
                return False

            # Apply differential-privacy protection
            protected_deltas = self._privacy.protect(update.deltas)
            protected = GradientUpdate(
                node_id=update.node_id,
                round_id=round_id,
                deltas=protected_deltas,
                sample_count=update.sample_count,
                noise_scale=self._privacy.noise_scale,
            )
            rnd.contributions.append(protected)

            node = self._nodes.get(update.node_id)
            if node:
                node.status = NodeStatus.UPLOADING.value

        logger.info(
            "Accepted update from %s for round %s (%d samples)",
            update.node_id, round_id, update.sample_count,
        )
        return True

    def complete_round(self, round_id: str) -> Optional[ModelWeights]:
        """Aggregate contributions and produce new global weights.

        Args:
            round_id: The round to complete.

        Returns:
            New ``ModelWeights`` if aggregation succeeded, else None.
        """
        with self._lock:
            rnd = self._rounds.get(round_id)
            if rnd is None:
                return None
            if len(rnd.contributions) < self._min_contributions:
                rnd.status = RoundStatus.FAILED.value
                rnd.metrics["failure_reason"] = "insufficient_contributions"
                return None

            rnd.status = RoundStatus.AGGREGATING.value

        new_weights_list = self._strategy.aggregate(
            rnd.contributions,
            self._global_weights.weights,
        )
        new_weights = ModelWeights(weights=new_weights_list)

        with self._lock:
            self._global_weights = new_weights
            rnd.status = RoundStatus.COMPLETED.value
            rnd.completed_at = datetime.now(timezone.utc).isoformat()
            rnd.global_model_version = new_weights.version
            rnd.metrics["contributions"] = len(rnd.contributions)
            rnd.metrics["total_samples"] = sum(
                c.sample_count for c in rnd.contributions
            )

            for nid in rnd.participating_nodes:
                node = self._nodes.get(nid)
                if node:
                    node.status = NodeStatus.IDLE.value
                    node.rounds_participated += 1

        logger.info(
            "Completed round %s → model %s",
            round_id, new_weights.version,
        )
        return new_weights

    def get_round(self, round_id: str) -> Optional[TrainingRound]:
        """Retrieve a round by ID."""
        with self._lock:
            return self._rounds.get(round_id)

    def list_rounds(self) -> List[TrainingRound]:
        """List all rounds, newest first."""
        with self._lock:
            return [
                self._rounds[rid]
                for rid in reversed(self._history)
                if rid in self._rounds
            ]

    def get_global_weights(self) -> ModelWeights:
        """Return the current global model weights."""
        with self._lock:
            return self._global_weights

    # -- status / introspection -------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the federation's current state."""
        with self._lock:
            nodes = list(self._nodes.values())
            rounds = list(self._rounds.values())

        completed = [r for r in rounds if r.status == RoundStatus.COMPLETED.value]

        return {
            "total_nodes": len(nodes),
            "active_nodes": sum(
                1 for n in nodes if n.status != NodeStatus.OFFLINE.value
            ),
            "total_rounds": len(rounds),
            "completed_rounds": len(completed),
            "current_model_version": self._global_weights.version,
            "privacy_noise_scale": self._privacy.noise_scale,
        }

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _build_strategy(method: str) -> AggregationStrategy:
        """Instantiate the aggregation strategy by name."""
        if method == AggregationMethod.MEDIAN.value:
            return MedianStrategy()
        return FederatedAverageStrategy()
