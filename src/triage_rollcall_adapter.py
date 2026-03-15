"""
Triage Rollcall Adapter for Murphy System Orchestrators

Implements a capability-rollcall stage before swarm expansion
(Section 15.3.1: Triage capability injection), providing:
- A capability registry of bot/archetype candidates
- Rollcall confidence probing on each candidate before selection
- Ranking by capability match, confidence, cost, and stability
- Domain context filtering for targeted candidate selection
- Thread-safe operation for concurrent orchestrator access
"""

import logging
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CandidateStatus(str, Enum):
    """Availability status of a bot candidate."""
    AVAILABLE = "available"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class BotCandidate:
    """A registered bot/archetype candidate in the capability registry."""
    candidate_id: str
    name: str
    capabilities: List[str]
    domains: List[str]
    status: CandidateStatus
    confidence: float
    cost_per_call: float
    stability_score: float
    last_probed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollcallResult:
    """Result of probing and ranking a single candidate during rollcall."""
    candidate_id: str
    name: str
    match_score: float
    confidence: float
    combined_score: float
    status: CandidateStatus


class TriageRollcallAdapter:
    """Performs capability rollcall and triage before swarm expansion.

    Maintains a registry of bot candidates, probes their readiness,
    and returns a ranked candidate set for the orchestrator to use.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._candidates: Dict[str, BotCandidate] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_candidate(
        self,
        name: str,
        capabilities: List[str],
        domains: Optional[List[str]] = None,
        cost_per_call: float = 1.0,
        stability_score: float = 1.0,
    ) -> str:
        """Register a new bot candidate and return its candidate_id."""
        candidate_id = f"bot-{uuid.uuid4().hex[:8]}"
        candidate = BotCandidate(
            candidate_id=candidate_id,
            name=name,
            capabilities=list(capabilities),
            domains=list(domains) if domains else [],
            status=CandidateStatus.AVAILABLE,
            confidence=0.0,
            cost_per_call=cost_per_call,
            stability_score=stability_score,
        )
        with self._lock:
            self._candidates[candidate_id] = candidate
        logger.info("Registered candidate %s (%s)", candidate_id, name)
        return candidate_id

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    def update_candidate_status(self, candidate_id: str, status: CandidateStatus) -> bool:
        """Update the status of a registered candidate. Returns True on success."""
        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                logger.warning("Candidate %s not found", candidate_id)
                return False
            candidate.status = status
        logger.info("Updated candidate %s status to %s", candidate_id, status.value)
        return True

    # ------------------------------------------------------------------
    # Probing
    # ------------------------------------------------------------------

    def probe_candidate(self, candidate_id: str) -> Optional[float]:
        """Probe a candidate and return a simulated confidence score.

        Returns None if the candidate is not found.
        """
        with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                logger.warning("Candidate %s not found for probing", candidate_id)
                return None
            confidence = random.uniform(0.5, 1.0)
            candidate.confidence = confidence
            candidate.last_probed = datetime.now(timezone.utc)
        logger.debug("Probed candidate %s: confidence=%.4f", candidate_id, confidence)
        return confidence

    # ------------------------------------------------------------------
    # Rollcall
    # ------------------------------------------------------------------

    def rollcall(
        self,
        task: str,
        constraints: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
        max_results: int = 10,
    ) -> List[RollcallResult]:
        """Probe all eligible candidates and return ranked results.

        Skips BUSY and OFFLINE candidates. DEGRADED candidates receive
        a 0.5x confidence penalty.
        """
        with self._lock:
            candidates = list(self._candidates.values())

        task_lower = task.lower()
        results: List[RollcallResult] = []

        for candidate in candidates:
            if candidate.status in (CandidateStatus.BUSY, CandidateStatus.OFFLINE):
                continue

            # Probe confidence
            confidence = self.probe_candidate(candidate.candidate_id)
            if confidence is None:
                continue

            # Apply degraded penalty
            if candidate.status == CandidateStatus.DEGRADED:
                confidence *= 0.5

            # Compute match_score
            if candidate.capabilities:
                matched = sum(
                    1 for cap in candidate.capabilities if cap.lower() in task_lower
                )
                match_score = matched / (len(candidate.capabilities) or 1)
            else:
                match_score = 0.0

            # Domain boost
            if domain and domain.lower() in [d.lower() for d in candidate.domains]:
                match_score = min(match_score + 0.2, 1.0)

            # Combined score
            cost_factor = (1.0 - min(candidate.cost_per_call, 10.0) / 10.0) * 0.1
            combined_score = (
                (match_score * 0.4)
                + (confidence * 0.3)
                + (candidate.stability_score * 0.2)
                + cost_factor
            )

            results.append(RollcallResult(
                candidate_id=candidate.candidate_id,
                name=candidate.name,
                match_score=round(match_score, 4),
                confidence=round(confidence, 4),
                combined_score=round(combined_score, 4),
                status=candidate.status,
            ))

        results.sort(key=lambda r: r.combined_score, reverse=True)
        logger.info("Rollcall returned %d results for task: %s", len(results[:max_results]), task[:60])
        return results[:max_results]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_candidate(self, candidate_id: str) -> Optional[BotCandidate]:
        """Return a candidate by ID, or None if not found."""
        with self._lock:
            return self._candidates.get(candidate_id)

    def list_candidates(self, status: Optional[CandidateStatus] = None) -> List[BotCandidate]:
        """Return all candidates, optionally filtered by status."""
        with self._lock:
            if status is not None:
                return [c for c in self._candidates.values() if c.status == status]
            return list(self._candidates.values())

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current adapter status."""
        with self._lock:
            total = len(self._candidates)
            by_status: Dict[str, int] = {}
            for c in self._candidates.values():
                by_status[c.status.value] = by_status.get(c.status.value, 0) + 1

        return {
            "total_candidates": total,
            "candidates_by_status": by_status,
        }
