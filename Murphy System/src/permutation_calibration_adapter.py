"""
Permutation Calibration Adapter for Murphy System

Bridges intake order generation to scoring. This adapter is responsible for:
- Generating candidate permutations of intake order
- Running exploratory evaluations (Mode A)
- Scoring sequence alternatives
- Feeding results to the policy registry for distillation

Reference: Permutation Calibration Application Spec Section 4 & 5.1
Owner: INONI LLC / Corey Post
"""

import itertools
import logging
import random
import threading
import uuid
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


class ExplorationMode(str, Enum):
    """Mode of permutation exploration."""
    EXHAUSTIVE = "exhaustive"    # Try all permutations (small sets only)
    SAMPLING = "sampling"        # Random sampling of permutations
    GREEDY = "greedy"            # Greedy best-first exploration
    BEAM_SEARCH = "beam_search"  # Beam search with pruning


class ScoringDimension(str, Enum):
    """Dimensions used for scoring sequence quality."""
    OUTCOME_QUALITY = "outcome_quality"
    CALIBRATION_QUALITY = "calibration_quality"
    STABILITY = "stability"
    LATENCY = "latency"
    COST = "cost"
    HITL_EFFICIENCY = "hitl_efficiency"
    GOVERNANCE_FIT = "governance_fit"


@dataclass
class IntakeItem:
    """Represents a single item in an intake sequence."""
    item_id: str
    item_type: str          # connector, api, feedback, telemetry, evidence
    source: str             # Source identifier
    priority: int = 0       # Base priority (higher = should come earlier)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermutationCandidate:
    """A candidate ordering to evaluate."""
    candidate_id: str
    ordering: List[str]     # List of item_ids in order
    generation_method: str  # How this candidate was generated
    parent_id: Optional[str] = None  # Parent candidate if derived
    
    
@dataclass
class ExplorationResult:
    """Result of evaluating a single permutation."""
    result_id: str
    candidate_id: str
    ordering: List[str]
    scores: Dict[str, float]
    aggregate_score: float
    execution_time_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplorationSession:
    """Tracks a single exploration session (Mode A run)."""
    session_id: str
    domain: str
    items: List[IntakeItem]
    mode: ExplorationMode
    max_candidates: int
    started_at: str
    completed_at: Optional[str] = None
    candidates_evaluated: int = 0
    best_result: Optional[ExplorationResult] = None
    status: str = "running"


@dataclass
class CalibrationConfig:
    """Configuration for the calibration adapter."""
    max_candidates_per_session: int = 100
    max_items_for_exhaustive: int = 6  # n! grows fast
    default_mode: ExplorationMode = ExplorationMode.SAMPLING
    sample_size: int = 20
    beam_width: int = 5
    scoring_weights: Dict[str, float] = field(default_factory=lambda: {
        ScoringDimension.OUTCOME_QUALITY.value: 0.25,
        ScoringDimension.CALIBRATION_QUALITY.value: 0.25,
        ScoringDimension.STABILITY.value: 0.20,
        ScoringDimension.LATENCY.value: 0.10,
        ScoringDimension.COST.value: 0.10,
        ScoringDimension.HITL_EFFICIENCY.value: 0.05,
        ScoringDimension.GOVERNANCE_FIT.value: 0.05,
    })
    respect_dependencies: bool = True
    budget_limit: Optional[float] = None
    time_limit_seconds: Optional[float] = None


class PermutationCalibrationAdapter:
    """Bridges intake order generation to scoring and policy discovery.
    
    This is the core Mode A engine that:
    1. Generates candidate orderings from intake items
    2. Evaluates each ordering using registered scorers
    3. Ranks results and identifies promising patterns
    4. Feeds winning patterns to the policy registry
    
    Implements spec Section 5.1: Learning the best order of evidence,
    connector usage, escalation, and sequence families.
    """
    
    _MAX_SESSIONS = 1_000
    _MAX_RESULTS = 10_000
    
    def __init__(self, config: Optional[CalibrationConfig] = None) -> None:
        self._lock = threading.Lock()
        self._config = config or CalibrationConfig()
        self._sessions: Dict[str, ExplorationSession] = {}
        self._results: Dict[str, List[ExplorationResult]] = {}
        self._scorers: Dict[str, Callable[[List[str], Dict[str, Any]], float]] = {}
        self._baseline_scorers: Dict[str, float] = {}
        self._history: List[Dict[str, Any]] = []
        
        # Register default scorers
        self._register_default_scorers()
        
        logger.info("PermutationCalibrationAdapter initialized")
    
    # ------------------------------------------------------------------
    # Scorer Registration
    # ------------------------------------------------------------------
    
    def register_scorer(
        self,
        dimension: ScoringDimension,
        scorer: Callable[[List[str], Dict[str, Any]], float],
        baseline: float = 0.5,
    ) -> None:
        """Register a scoring function for a dimension.
        
        Args:
            dimension: The scoring dimension this scorer evaluates
            scorer: Function (ordering, context) -> score (0.0-1.0)
            baseline: Expected baseline score for comparison
        """
        key = dimension.value
        self._scorers[key] = scorer
        self._baseline_scorers[key] = baseline
        logger.info("Registered scorer for dimension '%s'", key)
    
    def _register_default_scorers(self) -> None:
        """Register default placeholder scorers."""
        # These are simple heuristic scorers - in production, these would
        # be replaced with actual ML-based or empirical scorers
        
        def outcome_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder outcome quality scorer."""
            # In production: measure actual outcome quality
            # Here: random with slight preference for shorter orderings
            base = 0.5 + random.gauss(0, 0.15)
            length_bonus = max(0, 0.1 * (10 - len(ordering)) / 10)
            return _clamp(base + length_bonus)
        
        def calibration_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder calibration quality scorer."""
            # In production: measure confidence calibration
            return _clamp(0.5 + random.gauss(0, 0.1))
        
        def stability_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder stability scorer."""
            # In production: measure variance across runs
            return _clamp(0.6 + random.gauss(0, 0.1))
        
        def latency_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder latency scorer (higher = better/faster)."""
            # In production: measure actual latency
            return _clamp(0.7 + random.gauss(0, 0.1))
        
        def cost_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder cost scorer (higher = cheaper)."""
            # In production: measure actual cost
            return _clamp(0.8 + random.gauss(0, 0.1))
        
        def hitl_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder HITL efficiency scorer."""
            # In production: measure HITL interventions needed
            return _clamp(0.7 + random.gauss(0, 0.1))
        
        def governance_scorer(ordering: List[str], ctx: Dict[str, Any]) -> float:
            """Placeholder governance fit scorer."""
            # In production: measure compliance with governance rules
            return _clamp(0.9 + random.gauss(0, 0.05))
        
        self._scorers = {
            ScoringDimension.OUTCOME_QUALITY.value: outcome_scorer,
            ScoringDimension.CALIBRATION_QUALITY.value: calibration_scorer,
            ScoringDimension.STABILITY.value: stability_scorer,
            ScoringDimension.LATENCY.value: latency_scorer,
            ScoringDimension.COST.value: cost_scorer,
            ScoringDimension.HITL_EFFICIENCY.value: hitl_scorer,
            ScoringDimension.GOVERNANCE_FIT.value: governance_scorer,
        }
        self._baseline_scorers = {k: 0.5 for k in self._scorers}
    
    # ------------------------------------------------------------------
    # Exploration Session Management
    # ------------------------------------------------------------------
    
    def start_exploration(
        self,
        domain: str,
        items: List[IntakeItem],
        mode: Optional[ExplorationMode] = None,
        max_candidates: Optional[int] = None,
    ) -> str:
        """Start a new exploration session (Mode A).
        
        Args:
            domain: Domain/task family for this exploration
            items: List of intake items to permute
            mode: Exploration mode (default from config)
            max_candidates: Max candidates to evaluate (default from config)
            
        Returns:
            session_id: Unique identifier for this exploration session
        """
        session_id = f"exp-{uuid.uuid4().hex[:12]}"
        
        # Auto-select mode based on item count if not specified
        if mode is None:
            if len(items) <= self._config.max_items_for_exhaustive:
                mode = ExplorationMode.EXHAUSTIVE
            else:
                mode = self._config.default_mode
        
        max_candidates = max_candidates or self._config.max_candidates_per_session
        
        session = ExplorationSession(
            session_id=session_id,
            domain=domain,
            items=list(items),
            mode=mode,
            max_candidates=max_candidates,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        
        with self._lock:
            if len(self._sessions) >= self._MAX_SESSIONS:
                # Evict oldest completed sessions
                completed = [s for s in self._sessions.values() if s.status == "completed"]
                if completed:
                    completed.sort(key=lambda s: s.completed_at or s.started_at)
                    for s in completed[:len(completed)//2]:
                        del self._sessions[s.session_id]
                        self._results.pop(s.session_id, None)
            
            self._sessions[session_id] = session
            self._results[session_id] = []
            
        logger.info(
            "Started exploration session %s for domain '%s' with %d items (mode=%s)",
            session_id, domain, len(items), mode.value
        )
        return session_id
    
    def run_exploration(
        self,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        executor: Optional[Callable[[List[str]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the exploration session and return results.
        
        Args:
            session_id: ID of the exploration session
            context: Additional context for scoring
            executor: Optional function to actually execute orderings
            
        Returns:
            Results summary with best ordering found
        """
        context = context or {}
        
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return {"status": "error", "reason": "session_not_found", "session_id": session_id}
            if session.status != "running":
                return {"status": "error", "reason": "session_not_running", "session_id": session_id}
        
        # Generate candidates
        candidates = self._generate_candidates(session)
        
        # Evaluate each candidate
        results: List[ExplorationResult] = []
        for candidate in candidates:
            result = self._evaluate_candidate(session, candidate, context, executor)
            results.append(result)
            
            with self._lock:
                session.candidates_evaluated += 1
                if session.best_result is None or result.aggregate_score > session.best_result.aggregate_score:
                    session.best_result = result
                capped_append(self._results[session_id], result, self._MAX_RESULTS)
        
        # Complete session
        with self._lock:
            session.completed_at = datetime.now(timezone.utc).isoformat()
            session.status = "completed"
            best = session.best_result
        
        logger.info(
            "Completed exploration session %s: evaluated %d candidates, best score %.4f",
            session_id, len(results), best.aggregate_score if best else 0.0
        )
        
        return {
            "status": "completed",
            "session_id": session_id,
            "domain": session.domain,
            "candidates_evaluated": len(results),
            "best_result": self._result_to_dict(best) if best else None,
            "improvement_over_baseline": self._calculate_improvement(results) if results else 0.0,
        }
    
    def _generate_candidates(self, session: ExplorationSession) -> List[PermutationCandidate]:
        """Generate candidate orderings based on exploration mode."""
        item_ids = [item.item_id for item in session.items]
        
        if session.mode == ExplorationMode.EXHAUSTIVE:
            return self._generate_exhaustive(item_ids, session.max_candidates)
        elif session.mode == ExplorationMode.SAMPLING:
            return self._generate_sampling(item_ids, session.max_candidates)
        elif session.mode == ExplorationMode.GREEDY:
            return self._generate_greedy(item_ids, session)
        elif session.mode == ExplorationMode.BEAM_SEARCH:
            return self._generate_beam_search(item_ids, session)
        else:
            return self._generate_sampling(item_ids, session.max_candidates)
    
    def _generate_exhaustive(self, item_ids: List[str], max_candidates: int) -> List[PermutationCandidate]:
        """Generate all permutations (limited by max_candidates)."""
        candidates = []
        for i, perm in enumerate(itertools.permutations(item_ids)):
            if i >= max_candidates:
                break
            candidates.append(PermutationCandidate(
                candidate_id=f"cand-{uuid.uuid4().hex[:8]}",
                ordering=list(perm),
                generation_method="exhaustive",
            ))
        return candidates
    
    def _generate_sampling(self, item_ids: List[str], max_candidates: int) -> List[PermutationCandidate]:
        """Generate random sample of permutations."""
        candidates = []
        seen = set()
        attempts = 0
        max_attempts = max_candidates * 10
        
        while len(candidates) < max_candidates and attempts < max_attempts:
            attempts += 1
            perm = tuple(random.sample(item_ids, len(item_ids)))
            if perm not in seen:
                seen.add(perm)
                candidates.append(PermutationCandidate(
                    candidate_id=f"cand-{uuid.uuid4().hex[:8]}",
                    ordering=list(perm),
                    generation_method="sampling",
                ))
        
        return candidates
    
    def _generate_greedy(self, item_ids: List[str], session: ExplorationSession) -> List[PermutationCandidate]:
        """Generate candidates using greedy best-first approach."""
        # Start with random orderings, then greedily improve
        candidates = self._generate_sampling(item_ids, min(10, session.max_candidates))
        
        # For each starting point, generate neighbors by swapping adjacent items
        for base in list(candidates):
            if len(candidates) >= session.max_candidates:
                break
            for i in range(len(base.ordering) - 1):
                if len(candidates) >= session.max_candidates:
                    break
                neighbor = list(base.ordering)
                neighbor[i], neighbor[i+1] = neighbor[i+1], neighbor[i]
                candidates.append(PermutationCandidate(
                    candidate_id=f"cand-{uuid.uuid4().hex[:8]}",
                    ordering=neighbor,
                    generation_method="greedy_neighbor",
                    parent_id=base.candidate_id,
                ))
        
        return candidates[:session.max_candidates]
    
    def _generate_beam_search(self, item_ids: List[str], session: ExplorationSession) -> List[PermutationCandidate]:
        """Generate candidates using beam search."""
        beam_width = self._config.beam_width
        
        # Initial beam
        beam = self._generate_sampling(item_ids, beam_width)
        all_candidates = list(beam)
        
        # Expand beam iteratively
        while len(all_candidates) < session.max_candidates:
            new_beam = []
            for candidate in beam:
                # Generate neighbors
                for i in range(len(candidate.ordering) - 1):
                    neighbor = list(candidate.ordering)
                    neighbor[i], neighbor[i+1] = neighbor[i+1], neighbor[i]
                    new_beam.append(PermutationCandidate(
                        candidate_id=f"cand-{uuid.uuid4().hex[:8]}",
                        ordering=neighbor,
                        generation_method="beam_search",
                        parent_id=candidate.candidate_id,
                    ))
            
            if not new_beam:
                break
                
            # Keep top beam_width candidates (would need scoring here in production)
            random.shuffle(new_beam)
            beam = new_beam[:beam_width]
            all_candidates.extend(beam)
            
            if len(all_candidates) >= session.max_candidates:
                break
        
        return all_candidates[:session.max_candidates]
    
    def _evaluate_candidate(
        self,
        session: ExplorationSession,
        candidate: PermutationCandidate,
        context: Dict[str, Any],
        executor: Optional[Callable],
    ) -> ExplorationResult:
        """Evaluate a single candidate ordering."""
        import time
        start = time.time()
        
        scores: Dict[str, float] = {}
        try:
            # If executor provided, run it first to get execution context
            exec_context = dict(context)
            if executor:
                try:
                    exec_result = executor(candidate.ordering)
                    exec_context.update(exec_result if isinstance(exec_result, dict) else {})
                except Exception as e:
                    logger.warning("Executor failed for candidate %s: %s", candidate.candidate_id, e)
            
            # Score across all dimensions
            for dimension, scorer in self._scorers.items():
                try:
                    scores[dimension] = scorer(candidate.ordering, exec_context)
                except Exception as e:
                    logger.warning("Scorer '%s' failed: %s", dimension, e)
                    scores[dimension] = 0.5
            
            # Calculate weighted aggregate score
            aggregate = self._calculate_aggregate_score(scores)
            success = True
            error = None
            
        except Exception as e:
            logger.error("Evaluation failed for candidate %s: %s", candidate.candidate_id, e)
            scores = {d: 0.0 for d in self._scorers}
            aggregate = 0.0
            success = False
            error = str(e)
        
        execution_time_ms = (time.time() - start) * 1000
        
        return ExplorationResult(
            result_id=f"res-{uuid.uuid4().hex[:12]}",
            candidate_id=candidate.candidate_id,
            ordering=candidate.ordering,
            scores=scores,
            aggregate_score=aggregate,
            execution_time_ms=execution_time_ms,
            success=success,
            error=error,
            metadata={"generation_method": candidate.generation_method},
        )
    
    def _calculate_aggregate_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted aggregate score from dimension scores."""
        weights = self._config.scoring_weights
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            return sum(scores.values()) / len(scores) if scores else 0.0
        
        weighted_sum = 0.0
        for dimension, score in scores.items():
            weight = weights.get(dimension, 0.1)
            weighted_sum += score * weight
        
        return weighted_sum / total_weight
    
    def _calculate_improvement(self, results: List[ExplorationResult]) -> float:
        """Calculate improvement over baseline."""
        if not results:
            return 0.0
        
        baseline = sum(self._baseline_scorers.values()) / len(self._baseline_scorers)
        best_score = max(r.aggregate_score for r in results)
        
        return best_score - baseline
    
    def _result_to_dict(self, result: ExplorationResult) -> Dict[str, Any]:
        """Convert result to dict representation."""
        return {
            "result_id": result.result_id,
            "candidate_id": result.candidate_id,
            "ordering": result.ordering,
            "scores": result.scores,
            "aggregate_score": round(result.aggregate_score, 4),
            "execution_time_ms": round(result.execution_time_ms, 2),
            "success": result.success,
            "error": result.error,
            "timestamp": result.timestamp,
            "metadata": result.metadata,
        }
    
    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get details for an exploration session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            
            return {
                "session_id": session.session_id,
                "domain": session.domain,
                "mode": session.mode.value,
                "max_candidates": session.max_candidates,
                "candidates_evaluated": session.candidates_evaluated,
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "status": session.status,
                "best_result": self._result_to_dict(session.best_result) if session.best_result else None,
                "item_count": len(session.items),
            }
    
    def get_session_results(
        self,
        session_id: str,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get results from an exploration session."""
        with self._lock:
            results = self._results.get(session_id, [])
            # Sort by aggregate score descending
            sorted_results = sorted(results, key=lambda r: r.aggregate_score, reverse=True)
            if top_n:
                sorted_results = sorted_results[:top_n]
            return [self._result_to_dict(r) for r in sorted_results]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        with self._lock:
            total_sessions = len(self._sessions)
            completed = sum(1 for s in self._sessions.values() if s.status == "completed")
            total_results = sum(len(r) for r in self._results.values())
            
            return {
                "status": "ok",
                "total_sessions": total_sessions,
                "completed_sessions": completed,
                "running_sessions": total_sessions - completed,
                "total_results": total_results,
                "scorers_registered": len(self._scorers),
                "config": {
                    "max_candidates_per_session": self._config.max_candidates_per_session,
                    "default_mode": self._config.default_mode.value,
                    "max_items_for_exhaustive": self._config.max_items_for_exhaustive,
                },
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter operational status."""
        stats = self.get_statistics()
        return {
            "engine": "PermutationCalibrationAdapter",
            "operational": True,
            **stats,
        }
    
    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    
    def clear(self) -> None:
        """Clear all adapter state."""
        with self._lock:
            self._sessions.clear()
            self._results.clear()
            self._history.clear()
        logger.info("PermutationCalibrationAdapter cleared")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))


# ------------------------------------------------------------------
# Convenience factory
# ------------------------------------------------------------------

def create_intake_item(
    item_type: str,
    source: str,
    priority: int = 0,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> IntakeItem:
    """Factory function to create an IntakeItem."""
    return IntakeItem(
        item_id=f"item-{uuid.uuid4().hex[:8]}",
        item_type=item_type,
        source=source,
        priority=priority,
        dependencies=dependencies or [],
        metadata=metadata or {},
    )
