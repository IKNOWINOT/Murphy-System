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
