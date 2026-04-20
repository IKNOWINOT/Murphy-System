# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Golden Path Memory Bridge for Murphy System Runtime

This module captures and replays successful execution paths ("golden paths")
for accelerated task execution, providing:
- Recording successful execution paths with normalized specs
- Path matching and lookup based on task pattern similarity
- Confidence scoring by success count, failure count, and recency
- Path invalidation when conditions change
- Replay of known-good paths for knowledge/RAG usage
- Thread-safe in-memory persistence
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PathStatus(str, Enum):
    """Lifecycle status of a golden path."""
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


@dataclass
class GoldenPath:
    """A recorded successful execution path."""
    path_id: str
    task_pattern: str
    domain: str
    execution_spec: Dict[str, Any]
    success_count: int = 1
    failure_count: int = 0
    confidence_score: float = 0.7
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: PathStatus = PathStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PathMatchResult:
    """Result of a path matching query."""
    path_id: str
    task_pattern: str
    match_score: float
    confidence: float
    domain: str


class GoldenPathBridge:
    """Captures, stores, and replays golden execution paths.

    Provides similarity-based lookup so new tasks can reuse proven
    execution specs, boosting speed and reliability.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._paths: Dict[str, GoldenPath] = {}
        # Index by (task_pattern, domain) for fast exact lookups
        self._pattern_index: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_success(
        self,
        task_pattern: str,
        domain: str,
        execution_spec: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record or update a golden path for a successful execution.

        If a path with the same *task_pattern* and *domain* already exists,
        its counters and confidence are updated in place.  Otherwise a new
        path is created.  Returns the ``path_id``.
        """
        key = _pattern_key(task_pattern, domain)
        normalized = _normalize_spec(execution_spec)

        with self._lock:
            existing_id = self._pattern_index.get(key)
            if existing_id and existing_id in self._paths:
                path = self._paths[existing_id]
                path.success_count += 1
                path.confidence_score = min(1.0, path.confidence_score + 0.05)
                path.last_used_at = datetime.now(timezone.utc)
                path.execution_spec = normalized
                if metadata:
                    path.metadata.update(metadata)
                logger.info(
                    "Updated golden path %s (successes=%d, confidence=%.2f)",
                    path.path_id, path.success_count, path.confidence_score,
                )
                return path.path_id

            path_id = f"gp-{uuid.uuid4().hex[:12]}"
            path = GoldenPath(
                path_id=path_id,
                task_pattern=task_pattern,
                domain=domain,
                execution_spec=normalized,
                metadata=metadata or {},
            )
            self._paths[path_id] = path
            self._pattern_index[key] = path_id

        logger.info("Recorded new golden path %s for pattern '%s'", path_id, task_pattern)
        return path_id

    def record_failure(self, task_pattern: str, domain: str) -> None:
        """Increment failure count and reduce confidence for a matching path."""
        key = _pattern_key(task_pattern, domain)

        with self._lock:
            existing_id = self._pattern_index.get(key)
            if existing_id and existing_id in self._paths:
                path = self._paths[existing_id]
                path.failure_count += 1
                path.confidence_score = max(0.0, path.confidence_score - 0.15)
                logger.info(
                    "Recorded failure for path %s (failures=%d, confidence=%.2f)",
                    path.path_id, path.failure_count, path.confidence_score,
                )

    # ------------------------------------------------------------------
    # Matching / lookup
    # ------------------------------------------------------------------

    def find_matching_paths(
        self,
        task_pattern: str,
        domain: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[PathMatchResult]:
        """Find golden paths similar to *task_pattern*, sorted by relevance.

        Scoring rules:
        - Exact match on ``task_pattern`` → score 1.0
        - Substring overlap → score = overlap_ratio
        - Same domain → +0.2 boost
        - Filtered by *min_confidence*
        - Sorted by ``match_score * confidence_score`` descending
        """
        with self._lock:
            candidates = [
                p for p in self._paths.values()
                if p.status == PathStatus.ACTIVE
            ]

        results: List[PathMatchResult] = []
        for path in candidates:
            if path.confidence_score < min_confidence:
                continue

            score = _compute_match_score(task_pattern, path.task_pattern)
            if score <= 0.0:
                continue

            if domain and path.domain == domain:
                score = min(1.0, score + 0.2)

            results.append(PathMatchResult(
                path_id=path.path_id,
                task_pattern=path.task_pattern,
                match_score=round(score, 4),
                confidence=round(path.confidence_score, 4),
                domain=path.domain,
            ))

        results.sort(key=lambda r: r.match_score * r.confidence, reverse=True)
        return results

    def get_path(self, path_id: str) -> Optional[GoldenPath]:
        """Return a golden path by its id, or ``None``."""
        with self._lock:
            return self._paths.get(path_id)

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay_path(self, path_id: str) -> Optional[Dict[str, Any]]:
        """Return the execution spec for replay and bump usage counters.

        Returns ``None`` if the path does not exist or is not active.
        """
        with self._lock:
            path = self._paths.get(path_id)
            if path is None or path.status != PathStatus.ACTIVE:
                return None
            path.success_count += 1
            path.confidence_score = min(1.0, path.confidence_score + 0.05)
            path.last_used_at = datetime.now(timezone.utc)
            spec = dict(path.execution_spec)

        logger.info("Replayed golden path %s", path_id)
        return spec

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate_path(self, path_id: str, reason: str = "") -> bool:
        """Mark a path as invalidated.  Returns ``True`` on success."""
        with self._lock:
            path = self._paths.get(path_id)
            if path is None:
                logger.warning("Path %s not found for invalidation", path_id)
                return False
            path.status = PathStatus.INVALIDATED
            if reason:
                path.metadata["invalidation_reason"] = reason

        logger.info("Invalidated golden path %s: %s", path_id, reason)
        return True

    # ------------------------------------------------------------------
    # Statistics / status
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics across all golden paths."""
        with self._lock:
            paths = list(self._paths.values())

        if not paths:
            return {
                "total_paths": 0,
                "active_paths": 0,
                "invalidated_paths": 0,
                "avg_confidence": 0.0,
                "domain_breakdown": {},
            }

        active = [p for p in paths if p.status == PathStatus.ACTIVE]
        invalidated = [p for p in paths if p.status == PathStatus.INVALIDATED]

        domain_counts: Dict[str, int] = {}
        for p in paths:
            domain_counts[p.domain] = domain_counts.get(p.domain, 0) + 1

        avg_conf = _safe_mean([p.confidence_score for p in paths])

        return {
            "total_paths": len(paths),
            "active_paths": len(active),
            "invalidated_paths": len(invalidated),
            "avg_confidence": round(avg_conf, 4),
            "domain_breakdown": domain_counts,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return current bridge status."""
        with self._lock:
            total = len(self._paths)
            active = sum(1 for p in self._paths.values() if p.status == PathStatus.ACTIVE)
            invalidated = sum(1 for p in self._paths.values() if p.status == PathStatus.INVALIDATED)
            expired = sum(1 for p in self._paths.values() if p.status == PathStatus.EXPIRED)

        return {
            "total_paths": total,
            "active_paths": active,
            "invalidated_paths": invalidated,
            "expired_paths": expired,
            "bridge_operational": True,
        }

    # ------------------------------------------------------------------
    # Pipeline connection — Hero Flow Task 5
    # ------------------------------------------------------------------

    def execute_or_record(
        self,
        task_pattern: str,
        domain: str,
        execution_fn: Any,
        *,
        min_confidence: float = 0.75,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Attempt golden-path replay; on miss, execute and record the result.

        This is the single method that connects the golden path bridge back
        to the main execution pipeline:

        1. Look up matching golden paths with *min_confidence*.
        2. On hit — replay the stored execution spec (fast path).
        3. On miss — call *execution_fn(task_pattern)* (full pipeline),
           record a success, and return the result.
        4. On execution failure — call :meth:`record_failure` and re-raise.

        Parameters
        ----------
        task_pattern:
            The task or command string.
        domain:
            Domain hint for path matching.
        execution_fn:
            Callable ``(task_pattern: str) -> dict`` that executes the task
            via the full pipeline.
        min_confidence:
            Minimum bridge confidence to qualify for the fast path.
        metadata:
            Optional metadata to attach when recording a new path.

        Returns
        -------
        A dict with ``"source": "golden_path"`` on a cache hit or
        ``"source": "full_pipeline"`` on a cache miss (after executing).
        """
        matches = self.find_matching_paths(
            task_pattern, domain=domain, min_confidence=min_confidence
        )

        if matches:
            best = matches[0]
            spec = self.replay_path(best.path_id)
            if spec is not None:
                logger.info(
                    "GoldenPathBridge: fast-path hit for %r (path=%s, conf=%.2f)",
                    task_pattern, best.path_id, best.confidence,
                )
                return {"source": "golden_path", "path_id": best.path_id, **spec}

        # Full pipeline execution
        try:
            result = execution_fn(task_pattern)
        except Exception as exc:
            self.record_failure(task_pattern, domain)
            raise

        # Record the successful execution as a new golden path
        self.record_success(
            task_pattern,
            domain,
            result if isinstance(result, dict) else {"raw": result},
            metadata=metadata,
        )
        result_dict = result if isinstance(result, dict) else {"raw": result}
        result_dict["source"] = "full_pipeline"
        return result_dict

    # ------------------------------------------------------------------
    # Permutation Calibration Integration (Spec Section 3.4)
    # ------------------------------------------------------------------

    def record_sequence_path(
        self,
        sequence_id: str,
        domain: str,
        ordering: List[str],
        execution_spec: Dict[str, Any],
        outcome_quality: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a golden path from a learned sequence family.

        This implements spec Section 3.4: Record successful ordered evidence paths,
        compare new situations to known sequence families.

        Args:
            sequence_id: The sequence ID from permutation registry
            domain: Domain for the path
            ordering: The learned optimal ordering
            execution_spec: The execution specification
            outcome_quality: Quality score (0.0-1.0)
            metadata: Optional additional metadata

        Returns:
            The path_id for the recorded path
        """
        # Create task pattern from sequence
        task_pattern = f"seq:{sequence_id}:{':'.join(ordering[:3])}"

        # Enrich execution spec with ordering
        enriched_spec = dict(execution_spec)
        enriched_spec["learned_ordering"] = ordering
        enriched_spec["sequence_id"] = sequence_id
        enriched_spec["outcome_quality"] = outcome_quality

        # Enrich metadata
        full_metadata = metadata or {}
        full_metadata["source"] = "permutation_learning"
        full_metadata["ordering_length"] = len(ordering)

        return self.record_success(
            task_pattern=task_pattern,
            domain=domain,
            execution_spec=enriched_spec,
            metadata=full_metadata,
        )

    def find_sequence_matches(
        self,
        current_ordering: List[str],
        domain: str,
        min_confidence: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Find golden paths that match a given ordering pattern.

        This implements spec Section 3.4: Compare new situations to known
        sequence families, detect when a current case matches a known "golden order".

        Args:
            current_ordering: The current ordering to match
            domain: Domain to filter by
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching paths with similarity scores
        """
        with self._lock:
            candidates = [
                p for p in self._paths.values()
                if p.status == PathStatus.ACTIVE
                and p.domain == domain
                and p.confidence_score >= min_confidence
            ]

        matches = []
        for path in candidates:
            # Get ordering from extra namespace (due to normalization)
            extra = path.execution_spec.get("extra", {})
            stored_ordering = extra.get("learned_ordering", [])

            if not stored_ordering:
                continue

            similarity = self._compute_ordering_similarity(current_ordering, stored_ordering)

            if similarity > 0.3:  # Only include meaningful matches
                matches.append({
                    "path_id": path.path_id,
                    "sequence_id": extra.get("sequence_id"),
                    "stored_ordering": stored_ordering,
                    "similarity": round(similarity, 4),
                    "confidence": round(path.confidence_score, 4),
                    "outcome_quality": extra.get("outcome_quality", 0.0),
                    "combined_score": round(similarity * path.confidence_score, 4),
                })

        # Sort by combined score
        matches.sort(key=lambda m: m["combined_score"], reverse=True)
        return matches

    def _compute_ordering_similarity(
        self,
        ordering_a: List[str],
        ordering_b: List[str],
    ) -> float:
        """Compute similarity between two orderings.

        Uses a combination of:
        - Set overlap (which elements are present)
        - Position correlation (how similar the positions are)
        """
        if not ordering_a or not ordering_b:
            return 0.0

        # Set overlap
        set_a = set(ordering_a)
        set_b = set(ordering_b)
        overlap = len(set_a & set_b)
        union = len(set_a | set_b)
        jaccard = overlap / union if union > 0 else 0.0

        # Position similarity for common elements
        common = set_a & set_b
        if len(common) < 2:
            return jaccard

        # Kendall-tau style: count concordant vs discordant pairs
        concordant = 0
        discordant = 0
        common_list = list(common)

        for i, item_i in enumerate(common_list):
            for item_j in common_list[i+1:]:
                pos_a_i = ordering_a.index(item_i) if item_i in ordering_a else -1
                pos_a_j = ordering_a.index(item_j) if item_j in ordering_a else -1
                pos_b_i = ordering_b.index(item_i) if item_i in ordering_b else -1
                pos_b_j = ordering_b.index(item_j) if item_j in ordering_b else -1

                if pos_a_i >= 0 and pos_a_j >= 0 and pos_b_i >= 0 and pos_b_j >= 0:
                    if (pos_a_i < pos_a_j) == (pos_b_i < pos_b_j):
                        concordant += 1
                    else:
                        discordant += 1

        total_pairs = concordant + discordant
        position_similarity = concordant / total_pairs if total_pairs > 0 else 0.5

        # Weighted combination
        return 0.4 * jaccard + 0.6 * position_similarity

    def replay_sequence_path(
        self,
        sequence_id: str,
        domain: str,
    ) -> Optional[Dict[str, Any]]:
        """Replay a golden path by its sequence ID.

        This implements spec Section 3.4: Replay high-performing paths.

        Args:
            sequence_id: The sequence ID to replay
            domain: Domain to filter by

        Returns:
            The execution spec if found, None otherwise
        """
        with self._lock:
            for path in self._paths.values():
                extra = path.execution_spec.get("extra", {})
                if (path.status == PathStatus.ACTIVE
                    and path.domain == domain
                    and extra.get("sequence_id") == sequence_id):
                    # Found matching path - replay it
                    path.success_count += 1
                    path.confidence_score = min(1.0, path.confidence_score + 0.03)
                    path.last_used_at = datetime.now(timezone.utc)

                    spec = dict(path.execution_spec)
                    spec["replayed_from"] = path.path_id
                    spec["replay_count"] = path.success_count
                    # Flatten extra for convenience
                    spec["learned_ordering"] = extra.get("learned_ordering")
                    spec["sequence_id"] = extra.get("sequence_id")

                    logger.info("Replayed sequence path %s (seq=%s)", path.path_id, sequence_id)
                    return spec

        return None

    def get_sequence_path_stats(self) -> Dict[str, Any]:
        """Get statistics for sequence-based golden paths.

        Returns:
            Statistics on sequence paths vs regular paths
        """
        with self._lock:
            all_paths = list(self._paths.values())

        sequence_paths = [
            p for p in all_paths
            if p.execution_spec.get("extra", {}).get("learned_ordering")
        ]
        regular_paths = [
            p for p in all_paths
            if not p.execution_spec.get("extra", {}).get("learned_ordering")
        ]

        active_sequence = [p for p in sequence_paths if p.status == PathStatus.ACTIVE]
        active_regular = [p for p in regular_paths if p.status == PathStatus.ACTIVE]

        return {
            "status": "ok",
            "total_sequence_paths": len(sequence_paths),
            "active_sequence_paths": len(active_sequence),
            "total_regular_paths": len(regular_paths),
            "active_regular_paths": len(active_regular),
            "avg_sequence_confidence": round(
                _safe_mean([p.confidence_score for p in active_sequence]), 4
            ),
            "avg_regular_confidence": round(
                _safe_mean([p.confidence_score for p in active_regular]), 4
            ),
            "domains_with_sequences": list(set(p.domain for p in sequence_paths)),
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _pattern_key(task_pattern: str, domain: str) -> str:
    """Create a deterministic key for the pattern index."""
    return f"{task_pattern}||{domain}"


def _normalize_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an execution spec into a standard schema for persistence."""
    normalized: Dict[str, Any] = {
        "steps": spec.get("steps", []),
        "parameters": spec.get("parameters", {}),
        "constraints": spec.get("constraints", {}),
        "version": spec.get("version", "1.0"),
    }
    # Preserve any extra keys under an 'extra' namespace
    extra_keys = set(spec.keys()) - {"steps", "parameters", "constraints", "version"}
    if extra_keys:
        normalized["extra"] = {k: spec[k] for k in sorted(extra_keys)}
    return normalized


def _compute_match_score(query: str, pattern: str) -> float:
    """Compute a similarity score between *query* and *pattern*.

    - Exact match → 1.0
    - Substring containment → overlap ratio
    - No overlap → 0.0
    """
    if query == pattern:
        return 1.0

    query_lower = query.lower()
    pattern_lower = pattern.lower()

    if query_lower == pattern_lower:
        return 1.0

    if query_lower in pattern_lower or pattern_lower in query_lower:
        shorter = min(len(query_lower), len(pattern_lower))
        longer = max(len(query_lower), len(pattern_lower))
        return shorter / longer if longer > 0 else 0.0

    return 0.0


def _safe_mean(values: List[float]) -> float:
    """Return the mean of *values*, or 0.0 for an empty list."""
    return sum(values) / (len(values) or 1) if values else 0.0
