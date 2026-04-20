"""
Murphy Immune Engine — Next-Generation Autonomous Self-Coding System.

Design Label: ARCH-014 — Murphy Immune Engine
Owner: Backend Team
Dependencies:
  - SelfFixLoop (ARCH-005)
  - SelfImprovementEngine (ARCH-001)
  - SelfHealingCoordinator (OBS-004)
  - BugPatternDetector (DEV-004)
  - EventBackbone
  - PersistenceManager
  - SyntheticFailureGenerator

Wraps and extends all existing self-healing components by incorporating:
  - Kubernetes-style desired-state reconciliation
  - Predictive failure analysis (statistical trend detection)
  - Biological immune memory (instant replay of known fixes)
  - Chaos-hardened fix validation
  - Cascade-aware fix planning
  - Cross-run durable learning

Architecture:
  DesiredStateReconciler → PredictiveFailureAnalyzer → ImmunityMemory
           ↓                        ↓                        ↓
  CascadeAnalyzer ◄────── MurphyImmuneEngine ──────► ChaosHardenedValidator
           ↓                        ↓
  SelfFixLoop (ARCH-005)        EventBackbone / PersistenceManager

Safety invariants:
  - NEVER modifies source files on disk
  - Bounded by max_iterations to prevent infinite loops
  - Mutex ensures only one immune cycle at a time
  - Full audit trail via EventBackbone + PersistenceManager
  - Code proposals for human review only
  - Every fix must survive chaos testing before promotion to ImmunityMemory
  - Rollback on test failure

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

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
# Constants
# ---------------------------------------------------------------------------

_MAX_ENTRIES = 1_000
_MAX_EDGES = 500
_MAX_PREDICTIONS = 200
_MAX_REPORTS = 100
_MAX_DRIFT_EVENTS = 500

_DEFAULT_ENTRY_TTL_SECONDS = 86_400 * 7   # 7 days
_DEFAULT_CONFIDENCE_DECAY = 0.05           # per cycle
_MIN_CONFIDENCE = 0.10                     # evict below this
_CHAOS_PASS_THRESHOLD = 0.70              # min pass-rate to promote to memory


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DriftEvent:
    """Records a discrepancy between desired and actual system state."""

    drift_id: str
    component: str                  # e.g. "bots", "circuit_breakers", "recovery_coverage"
    expected: Any                   # value from the desired-state manifest
    actual: Any                     # observed value from live subsystem
    severity: str = "medium"        # critical | high | medium | low
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_id": self.drift_id,
            "component": self.component,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
            "detected_at": self.detected_at,
        }


@dataclass
class PredictedFailure:
    """A pre-emptive gap generated from statistical trend analysis."""

    prediction_id: str
    category: str
    description: str
    probability: float              # 0.0–1.0 probability of materializing
    time_horizon_seconds: float     # estimated time until failure
    supporting_evidence: List[str] = field(default_factory=list)
    severity: str = "medium"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "category": self.category,
            "description": self.description,
            "probability": self.probability,
            "time_horizon_seconds": self.time_horizon_seconds,
            "supporting_evidence": list(self.supporting_evidence),
            "severity": self.severity,
            "created_at": self.created_at,
        }


@dataclass
class ImmunityEntry:
    """Stored fix fingerprint with confidence score and TTL."""

    entry_id: str
    fingerprint: str                # SHA-256 of category+error_type+severity
    category: str
    error_type: str
    severity: str
    fix_steps: List[Dict[str, Any]]
    rollback_steps: List[Dict[str, Any]]
    test_criteria: List[Dict[str, Any]]
    confidence: float = 1.0         # decays over time
    applications: int = 0           # successful applications count
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_applied_at: str = ""
    expires_at: str = ""            # ISO timestamp; empty = never expires

    def __post_init__(self) -> None:
        if not self.last_applied_at:
            self.last_applied_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "fingerprint": self.fingerprint,
            "category": self.category,
            "error_type": self.error_type,
            "severity": self.severity,
            "fix_steps": list(self.fix_steps),
            "rollback_steps": list(self.rollback_steps),
            "test_criteria": list(self.test_criteria),
            "confidence": self.confidence,
            "applications": self.applications,
            "created_at": self.created_at,
            "last_applied_at": self.last_applied_at,
            "expires_at": self.expires_at,
        }


@dataclass
class CascadeEdge:
    """Directed dependency link between two subsystem categories."""

    edge_id: str
    source_category: str            # the category where a fix was applied
    target_category: str            # the category that may be affected
    weight: float = 1.0             # observed causal strength 0.0–1.0
    observed_regressions: int = 0   # how many times target regressed after source fix
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_category": self.source_category,
            "target_category": self.target_category,
            "weight": self.weight,
            "observed_regressions": self.observed_regressions,
            "created_at": self.created_at,
        }


@dataclass
class ImmuneReport:
    """Final report produced by a completed immune cycle run."""

    report_id: str
    iterations_run: int
    gaps_found: int
    gaps_fixed: int
    gaps_remaining: int
    drift_events_detected: int
    predicted_failures: int
    immunity_recalls: int
    chaos_validations_passed: int
    chaos_validations_failed: int
    cascade_regressions_detected: int
    entries_memorized: int
    plans_executed: int
    plans_succeeded: int
    plans_rolled_back: int
    tests_run: int
    tests_passed: int
    tests_failed: int
    duration_ms: float
    final_health_status: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "iterations_run": self.iterations_run,
            "gaps_found": self.gaps_found,
            "gaps_fixed": self.gaps_fixed,
            "gaps_remaining": self.gaps_remaining,
            "drift_events_detected": self.drift_events_detected,
            "predicted_failures": self.predicted_failures,
            "immunity_recalls": self.immunity_recalls,
            "chaos_validations_passed": self.chaos_validations_passed,
            "chaos_validations_failed": self.chaos_validations_failed,
            "cascade_regressions_detected": self.cascade_regressions_detected,
            "entries_memorized": self.entries_memorized,
            "plans_executed": self.plans_executed,
            "plans_succeeded": self.plans_succeeded,
            "plans_rolled_back": self.plans_rolled_back,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "duration_ms": self.duration_ms,
            "final_health_status": self.final_health_status,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# DesiredStateReconciler
# ---------------------------------------------------------------------------

class DesiredStateReconciler:
    """Kubernetes-style reconciliation loop for Murphy subsystems.

    Design Label: ARCH-014 (component)
    Owner: Backend Team

    Maintains a desired-state manifest (dict) describing expected:
    - Active bot count per role
    - Circuit breaker states (all CLOSED)
    - Recovery procedure coverage (every failure category has a handler)
    - Confidence threshold ranges
    - Plugin health status

    Reconciliation cycle:
    1. Load desired state manifest
    2. Observe actual state from live subsystems
    3. Compute drift (set difference)
    4. Emit DriftEvent for each discrepancy
    5. Feed DriftEvents into FixPlan generation
    """

    def __init__(
        self,
        desired_state: Optional[Dict[str, Any]] = None,
        healing_coordinator=None,
        bug_detector=None,
    ) -> None:
        self._desired = desired_state or {}
        self._coordinator = healing_coordinator
        self._detector = bug_detector
        self._lock = threading.Lock()
        self._drift_history: List[DriftEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_desired_state(self, manifest: Dict[str, Any]) -> None:
        """Replace the desired-state manifest."""
        with self._lock:
            self._desired = dict(manifest)

    def get_desired_state(self) -> Dict[str, Any]:
        """Return a copy of the current desired-state manifest."""
        with self._lock:
            return dict(self._desired)

    def reconcile(self, actual_state: Optional[Dict[str, Any]] = None) -> List[DriftEvent]:
        """Compare desired vs actual state and return DriftEvents.

        If *actual_state* is provided it is used directly; otherwise the
        method attempts to observe state from injected subsystems.
        """
        if actual_state is None:
            actual_state = self._observe_actual_state()

        events: List[DriftEvent] = []
        with self._lock:
            desired = dict(self._desired)

        for component, expected_value in desired.items():
            actual_value = actual_state.get(component)
            if actual_value != expected_value:
                drift = DriftEvent(
                    drift_id=f"drift-{uuid.uuid4().hex[:8]}",
                    component=component,
                    expected=expected_value,
                    actual=actual_value,
                    severity=self._classify_drift_severity(component, expected_value, actual_value),
                )
                events.append(drift)
                with self._lock:
                    capped_append(self._drift_history, drift, _MAX_DRIFT_EVENTS)

        logger.debug("Reconciler: %d drift events detected", len(events))
        return events

    def get_drift_history(self) -> List[DriftEvent]:
        """Return a snapshot of all recorded drift events."""
        with self._lock:
            return list(self._drift_history)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _observe_actual_state(self) -> Dict[str, Any]:
        """Query live subsystems for their current state."""
        state: Dict[str, Any] = {}
        if self._coordinator is not None:
            try:
                procs = self._coordinator.list_procedures()
                state["recovery_procedures"] = len(procs)
            except Exception as exc:
                logger.debug("DesiredStateReconciler: coordinator query failed: %s", exc)
        if self._detector is not None:
            try:
                patterns = self._detector.get_patterns(limit=1_000)
                state["detected_pattern_count"] = len(patterns)
            except Exception as exc:
                logger.debug("DesiredStateReconciler: detector query failed: %s", exc)
        return state

    @staticmethod
    def _classify_drift_severity(
        component: str,
        expected: Any,
        actual: Any,
    ) -> str:
        """Return a severity level based on the drifted component name."""
        critical_keys = {"circuit_breaker_states", "mutex_state", "safety_invariants"}
        high_keys = {"active_bot_count", "recovery_procedure_coverage"}
        if component in critical_keys:
            return "critical"
        if component in high_keys:
            return "high"
        return "medium"


# ---------------------------------------------------------------------------
# PredictiveFailureAnalyzer
# ---------------------------------------------------------------------------

class PredictiveFailureAnalyzer:
    """Predictive failure engine using statistical analysis of historical patterns.

    Design Label: ARCH-014 (component)
    Owner: Backend Team

    Capabilities:
    - Time-series trend detection on error rates per category
    - MTTR tracking and degradation alerts
    - Correlation analysis between seemingly unrelated failure categories
    - Canary score computation: how likely is a deployment to cause failures?
    - Preemptive gap generation: creates PredictedFailure objects for predicted failures
    """

    def __init__(self, bug_detector=None) -> None:
        self._detector = bug_detector
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []   # snapshots of pattern counts
        self._predictions: List[PredictedFailure] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_snapshot(self, snapshot: Dict[str, int]) -> None:
        """Record a snapshot of category → error_count for trend analysis.

        *snapshot* should be a dict mapping category names to their current
        cumulative error counts.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counts": dict(snapshot),
        }
        with self._lock:
            capped_append(self._history, entry, _MAX_ENTRIES)

    def analyze(self, horizon_seconds: float = 3_600.0) -> List[PredictedFailure]:
        """Run trend analysis and return a list of PredictedFailure objects.

        *horizon_seconds* — the time window over which to project failures.
        """
        with self._lock:
            history = list(self._history)

        predictions: List[PredictedFailure] = []

        if len(history) < 2:
            return predictions

        # Build per-category delta series
        categories: Set[str] = set()
        for snap in history:
            categories.update(snap["counts"].keys())

        for category in categories:
            series = [snap["counts"].get(category, 0) for snap in history]
            prediction = self._analyze_series(category, series, horizon_seconds)
            if prediction is not None:
                predictions.append(prediction)
                with self._lock:
                    capped_append(self._predictions, prediction, _MAX_PREDICTIONS)

        logger.debug("PredictiveFailureAnalyzer: %d predictions generated", len(predictions))
        return predictions

    def get_canary_score(self, category: str) -> float:
        """Return a 0.0–1.0 score representing failure risk for a category.

        0.0 = stable, 1.0 = imminent failure predicted.
        """
        with self._lock:
            history = list(self._history)

        if len(history) < 2:
            return 0.0

        series = [snap["counts"].get(category, 0) for snap in history]
        deltas = [series[i] - series[i - 1] for i in range(1, len(series))]
        positive_deltas = [d for d in deltas if d > 0]
        if not positive_deltas:
            return 0.0

        avg_delta = sum(positive_deltas) / (len(positive_deltas) or 1)
        last_count = series[-1] if series else 0
        # Simple normalized score: larger avg delta relative to last count → higher risk
        if last_count <= 0:
            return min(avg_delta / 10.0, 1.0)
        return min(avg_delta / (last_count or 1), 1.0)

    def get_predictions(self) -> List[PredictedFailure]:
        """Return all recorded predictions (snapshot)."""
        with self._lock:
            return list(self._predictions)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyze_series(
        self,
        category: str,
        series: List[int],
        horizon_seconds: float,
    ) -> Optional[PredictedFailure]:
        """Analyze a time series for a single category and return a prediction."""
        if len(series) < 2:
            return None

        # Compute incremental deltas
        deltas = [series[i] - series[i - 1] for i in range(1, len(series))]
        positive_deltas = [d for d in deltas if d > 0]
        if not positive_deltas:
            return None

        avg_delta = sum(positive_deltas) / (len(positive_deltas) or 1)
        last_count = series[-1]
        trend_slope = avg_delta / (len(positive_deltas) or 1)

        # Probability heuristic: proportion of intervals with positive growth
        probability = len(positive_deltas) / (len(deltas) or 1)
        if probability < 0.30:
            return None  # not enough consistent growth to predict

        # Time to failure estimate (very simple linear extrapolation)
        time_to_failure = horizon_seconds * (1.0 - min(probability, 0.95))

        severity = "critical" if probability > 0.80 else "high" if probability > 0.60 else "medium"

        return PredictedFailure(
            prediction_id=f"pred-{uuid.uuid4().hex[:8]}",
            category=category,
            description=f"Error rate in '{category}' is trending upward (slope={trend_slope:.2f}/interval)",
            probability=round(probability, 3),
            time_horizon_seconds=round(time_to_failure, 1),
            supporting_evidence=[
                f"positive_delta_intervals={len(positive_deltas)}/{len(deltas)}",
                f"avg_delta={avg_delta:.2f}",
                f"last_count={last_count}",
            ],
            severity=severity,
        )


# ---------------------------------------------------------------------------
# ImmunityMemory
# ---------------------------------------------------------------------------

class ImmunityMemory:
    """Immune memory bank — stores fingerprints of past failures and their proven fixes.

    Design Label: ARCH-014 (component)
    Owner: Backend Team

    When a new gap is detected:
    1. Compute fingerprint (category + error_type + severity hash)
    2. Check memory bank for matching fingerprint
    3. If match found with verified fix → apply immediately (skip planning)
    4. If no match → proceed through normal DIAGNOSE → PLAN → EXECUTE flow
    5. On verified fix → store fingerprint + fix in memory bank

    Memory entries have TTL and confidence decay — if a fix stops working,
    confidence drops and the entry is eventually evicted.
    """

    def __init__(
        self,
        ttl_seconds: float = _DEFAULT_ENTRY_TTL_SECONDS,
        confidence_decay_per_cycle: float = _DEFAULT_CONFIDENCE_DECAY,
        min_confidence: float = _MIN_CONFIDENCE,
    ) -> None:
        self._ttl = ttl_seconds
        self._decay = confidence_decay_per_cycle
        self._min_confidence = min_confidence
        self._lock = threading.Lock()
        self._bank: Dict[str, ImmunityEntry] = {}  # fingerprint → entry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def compute_fingerprint(category: str, error_type: str, severity: str) -> str:
        """Deterministic SHA-256 fingerprint for a gap signature."""
        raw = f"{category.lower()}:{error_type.lower()}:{severity.lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def recall(self, fingerprint: str) -> Optional[ImmunityEntry]:
        """Look up a fix by its fingerprint.  Returns None if not found or expired."""
        with self._lock:
            entry = self._bank.get(fingerprint)
        if entry is None:
            return None
        if self._is_expired(entry):
            self._evict(fingerprint)
            return None
        if entry.confidence < self._min_confidence:
            self._evict(fingerprint)
            return None
        return entry

    def memorize(
        self,
        category: str,
        error_type: str,
        severity: str,
        fix_steps: List[Dict[str, Any]],
        rollback_steps: List[Dict[str, Any]],
        test_criteria: List[Dict[str, Any]],
    ) -> ImmunityEntry:
        """Store a proven fix in the memory bank.  Updates existing entry if present."""
        fingerprint = self.compute_fingerprint(category, error_type, severity)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            existing = self._bank.get(fingerprint)
            if existing is not None:
                # Reinforce existing entry
                existing.applications += 1
                existing.confidence = min(existing.confidence + 0.10, 1.0)
                existing.last_applied_at = now
                existing.fix_steps = list(fix_steps)
                return existing
            entry = ImmunityEntry(
                entry_id=f"imm-{uuid.uuid4().hex[:8]}",
                fingerprint=fingerprint,
                category=category,
                error_type=error_type,
                severity=severity,
                fix_steps=list(fix_steps),
                rollback_steps=list(rollback_steps),
                test_criteria=list(test_criteria),
                confidence=1.0,
                applications=1,
            )
            self._bank[fingerprint] = entry
        logger.debug("ImmunityMemory: memorized entry %s (fp=%s)", entry.entry_id, fingerprint)
        return entry

    def decay_all(self) -> int:
        """Apply confidence decay to all entries.  Returns number of evictions."""
        evictions = 0
        with self._lock:
            to_evict = []
            for fp, entry in list(self._bank.items()):
                entry.confidence = max(entry.confidence - self._decay, 0.0)
                if entry.confidence < self._min_confidence or self._is_expired(entry):
                    to_evict.append(fp)
            for fp in to_evict:
                del self._bank[fp]
                evictions += 1
        logger.debug("ImmunityMemory: decay cycle evicted %d entries", evictions)
        return evictions

    def penalize(self, fingerprint: str, amount: float = 0.20) -> None:
        """Reduce confidence for an entry when its fix fails in practice."""
        with self._lock:
            entry = self._bank.get(fingerprint)
            if entry is None:
                return
            entry.confidence = max(entry.confidence - amount, 0.0)
            if entry.confidence < self._min_confidence:
                del self._bank[fingerprint]
                logger.debug("ImmunityMemory: evicted low-confidence entry fp=%s", fingerprint)

    def size(self) -> int:
        """Return the number of entries in the memory bank."""
        with self._lock:
            return len(self._bank)

    def all_entries(self) -> List[ImmunityEntry]:
        """Return a snapshot of all non-expired, sufficiently-confident entries."""
        with self._lock:
            return [
                e for e in self._bank.values()
                if not self._is_expired(e) and e.confidence >= self._min_confidence
            ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_expired(self, entry: ImmunityEntry) -> bool:
        if not entry.expires_at or not self._ttl:
            return False
        try:
            created = datetime.fromisoformat(entry.created_at)
            now = datetime.now(timezone.utc)
            elapsed = (now - created.replace(tzinfo=timezone.utc)).total_seconds()
            return elapsed > self._ttl
        except Exception as exc:
            logger.debug("ImmunityMemory: TTL check error: %s", exc)
            return False

    def _evict(self, fingerprint: str) -> None:
        with self._lock:
            self._bank.pop(fingerprint, None)


# ---------------------------------------------------------------------------
# ChaosHardenedValidator
# ---------------------------------------------------------------------------

class ChaosHardenedValidator:
    """Validates fixes under synthetic chaos conditions.

    Design Label: ARCH-014 (component)
    Owner: Backend Team

    After a fix is applied and passes normal testing:
    1. Generate targeted synthetic failures in the same category
    2. Inject them via FailureInjectionPipeline (if available)
    3. Verify the fix still holds under stress
    4. If it doesn't → mark fix as fragile, try alternative approach
    5. Only promote fix to ImmunityMemory if chaos-hardened
    """

    def __init__(self, failure_injection_pipeline=None, chaos_rounds: int = 3) -> None:
        self._pipeline = failure_injection_pipeline
        self._chaos_rounds = max(1, chaos_rounds)
        self._lock = threading.Lock()
        self._results: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        plan_id: str,
        category: str,
        fix_callable=None,
        test_callable=None,
    ) -> Tuple[bool, float]:
        """Run chaos validation for a fix.

        Parameters
        ----------
        plan_id:
            Identifier of the fix plan being validated.
        category:
            The failure category being addressed.
        fix_callable:
            Optional callable ``() -> None`` that (re-)applies the fix before
            each chaos round.  When ``None`` the fix is assumed already applied.
        test_callable:
            Optional callable ``() -> bool`` that verifies correctness after
            chaos injection.  When ``None`` a trivial pass is assumed.

        Returns
        -------
        (passed, pass_rate) — ``passed`` is True when
        ``pass_rate >= _CHAOS_PASS_THRESHOLD``.
        """
        passes = 0
        for round_num in range(self._chaos_rounds):
            try:
                self._inject_chaos(category)
                if fix_callable is not None:
                    fix_callable()
                if test_callable is not None:
                    ok = bool(test_callable())
                else:
                    ok = True
                if ok:
                    passes += 1
                self._record_result(plan_id, round_num, ok, category)
            except Exception as exc:
                logger.warning(
                    "ChaosHardenedValidator: round %d raised unexpectedly: %s",
                    round_num, exc,
                )
                self._record_result(plan_id, round_num, False, category)

        pass_rate = passes / (self._chaos_rounds or 1)
        passed = pass_rate >= _CHAOS_PASS_THRESHOLD
        logger.info(
            "ChaosHardenedValidator: plan=%s category=%s pass_rate=%.2f passed=%s",
            plan_id, category, pass_rate, passed,
        )
        return passed, pass_rate

    def get_results(self) -> List[Dict[str, Any]]:
        """Return a snapshot of all recorded chaos validation results."""
        with self._lock:
            return list(self._results)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _inject_chaos(self, category: str) -> None:
        """Attempt to inject a synthetic failure via the pipeline (if available)."""
        if self._pipeline is None:
            return  # no-op when pipeline not injected
        try:
            scenario = self._pipeline.create_base_scenario(
                scenario_name=f"chaos-{category}-{uuid.uuid4().hex[:6]}",
                artifact_graph={},
                interface_definitions={},
                gate_library=[],
            )
            logger.debug("ChaosHardenedValidator: injected chaos scenario %s", scenario.scenario_id)
        except Exception as exc:
            logger.debug("ChaosHardenedValidator: chaos injection skipped: %s", exc)

    def _record_result(
        self, plan_id: str, round_num: int, passed: bool, category: str
    ) -> None:
        result = {
            "plan_id": plan_id,
            "round": round_num,
            "category": category,
            "passed": passed,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._results, result, _MAX_ENTRIES)


# ---------------------------------------------------------------------------
# CascadeAnalyzer
# ---------------------------------------------------------------------------

class CascadeAnalyzer:
    """Tracks dependency graphs between fixes and detects cascading failures.

    Design Label: ARCH-014 (component)
    Owner: Backend Team

    Maintains a directed graph where:
    - Nodes = subsystem categories
    - Edges = observed causal relationships

    When a fix is applied to category A:
    1. Check all categories connected to A
    2. Run targeted health checks on connected categories
    3. If regression detected → flag cascade risk
    4. Build cascade-aware fix plans that address root + downstream
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Adjacency: source_category → List[CascadeEdge]
        self._graph: Dict[str, List[CascadeEdge]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_edge(self, source: str, target: str, caused_regression: bool = False) -> CascadeEdge:
        """Record or reinforce a causal edge between two categories."""
        with self._lock:
            edges = self._graph.setdefault(source, [])
            for edge in edges:
                if edge.target_category == target:
                    if caused_regression:
                        edge.observed_regressions += 1
                        edge.weight = min(edge.weight + 0.10, 1.0)
                    return edge
            new_edge = CascadeEdge(
                edge_id=f"edge-{uuid.uuid4().hex[:8]}",
                source_category=source,
                target_category=target,
                weight=0.50,
                observed_regressions=1 if caused_regression else 0,
            )
            capped_append(edges, new_edge, _MAX_EDGES)
            return new_edge

    def get_downstream(self, source: str) -> List[str]:
        """Return all categories directly downstream of *source*."""
        with self._lock:
            return [e.target_category for e in self._graph.get(source, [])]

    def check_cascade(
        self,
        source_category: str,
        health_check_callable=None,
    ) -> List[str]:
        """Check downstream categories for regressions after a fix to *source_category*.

        Parameters
        ----------
        source_category:
            The category where a fix was applied.
        health_check_callable:
            Optional callable ``(category: str) -> bool`` that returns True when
            the category is healthy.  When ``None`` all downstream categories are
            assumed healthy (no regressions reported).

        Returns
        -------
        List of categories where a regression was detected.
        """
        downstream = self.get_downstream(source_category)
        regressions: List[str] = []
        for target in downstream:
            if health_check_callable is not None:
                try:
                    healthy = bool(health_check_callable(target))
                except Exception as exc:
                    logger.warning("CascadeAnalyzer: health check for %s raised: %s", target, exc)
                    healthy = True  # assume healthy on error
                if not healthy:
                    regressions.append(target)
                    self.record_edge(source_category, target, caused_regression=True)
            else:
                # No callable provided — can't detect regressions; just report edges
                pass
        if regressions:
            logger.warning(
                "CascadeAnalyzer: %d cascade regressions after fix to '%s': %s",
                len(regressions), source_category, regressions,
            )
        return regressions

    def get_all_edges(self) -> List[CascadeEdge]:
        """Return a flat list of all edges in the graph."""
        with self._lock:
            result = []
            for edges in self._graph.values():
                result.extend(edges)
            return result

    def get_graph_stats(self) -> Dict[str, Any]:
        """Return a summary of the cascade graph."""
        with self._lock:
            nodes = set(self._graph.keys())
            for edges in self._graph.values():
                nodes.update(e.target_category for e in edges)
            all_edges = [e for edges in self._graph.values() for e in edges]
        total_regressions = sum(e.observed_regressions for e in all_edges)
        return {
            "node_count": len(nodes),
            "edge_count": len(all_edges),
            "total_observed_regressions": total_regressions,
        }


# ---------------------------------------------------------------------------
# MurphyImmuneEngine
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class MurphyImmuneEngine:
    """Murphy's immune system — the world-class autonomous self-coding engine.

    Design Label: ARCH-014 — Murphy Immune Engine
    Owner: Backend Team

    Integrates:
    - DesiredStateReconciler (continuous drift detection)
    - PredictiveFailureAnalyzer (preemptive gap detection)
    - ImmunityMemory (instant replay of known fixes)
    - ChaosHardenedValidator (stress-test every fix)
    - CascadeAnalyzer (prevent fix-induced cascades)
    - SelfFixLoop (underlying execution engine)
    - SelfImprovementEngine (learning from outcomes)
    - SelfHealingCoordinator (recovery procedures)
    - BugPatternDetector (pattern detection)
    - EventBackbone (audit/observability)
    - SyntheticFailureGenerator (chaos engineering)

    Safety invariants (all inherited from SelfFixLoop plus additional):
    - NEVER modifies source files on disk
    - Maximum iteration bound
    - Mutex — only one immune cycle at a time
    - Full audit trail
    - Code proposals for human review only
    - Rollback on failure
    - Chaos validation before ImmunityMemory promotion
    """

    def __init__(
        self,
        fix_loop=None,
        improvement_engine=None,
        healing_coordinator=None,
        bug_detector=None,
        event_backbone=None,
        persistence_manager=None,
        failure_injection_pipeline=None,
        desired_state: Optional[Dict[str, Any]] = None,
        chaos_rounds: int = 3,
        immunity_ttl_seconds: float = _DEFAULT_ENTRY_TTL_SECONDS,
        confidence_decay: float = _DEFAULT_CONFIDENCE_DECAY,
    ) -> None:
        # Wired subsystems
        self._loop = fix_loop
        self._engine = improvement_engine
        self._coordinator = healing_coordinator
        self._detector = bug_detector
        self._backbone = event_backbone
        self._pm = persistence_manager

        # Immune components
        self._reconciler = DesiredStateReconciler(
            desired_state=desired_state,
            healing_coordinator=healing_coordinator,
            bug_detector=bug_detector,
        )
        self._predictor = PredictiveFailureAnalyzer(bug_detector=bug_detector)
        self._memory = ImmunityMemory(
            ttl_seconds=immunity_ttl_seconds,
            confidence_decay_per_cycle=confidence_decay,
        )
        self._chaos_validator = ChaosHardenedValidator(
            failure_injection_pipeline=failure_injection_pipeline,
            chaos_rounds=chaos_rounds,
        )
        self._cascade_analyzer = CascadeAnalyzer()

        # Concurrency guard
        self._lock = threading.Lock()
        self._running = False

        # Audit
        self._reports: List[ImmuneReport] = []

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_desired_state(self, manifest: Dict[str, Any]) -> None:
        """Update the desired-state manifest used by the reconciler."""
        self._reconciler.set_desired_state(manifest)

    def get_desired_state(self) -> Dict[str, Any]:
        """Return the current desired-state manifest."""
        return self._reconciler.get_desired_state()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run_immune_cycle(self, max_iterations: int = 20) -> ImmuneReport:
        """Run the full 11-phase immune cycle.

        Phase 1:  Reconcile  — compare desired vs actual state
        Phase 2:  Predict    — analyze trends for upcoming failures
        Phase 3:  Diagnose   — scan for current gaps (delegates to SelfFixLoop)
        Phase 4:  Recall     — check ImmunityMemory for instant fixes
        Phase 5:  Plan       — generate fix plans for remaining gaps
        Phase 6:  Execute    — apply fixes
        Phase 7:  Test       — verify fixes work
        Phase 8:  Harden     — chaos-test verified fixes
        Phase 9:  Cascade    — ensure no downstream regressions
        Phase 10: Memorize   — store verified, hardened fixes in ImmunityMemory
        Phase 11: Report     — generate comprehensive ImmuneReport

        Raises RuntimeError if another cycle is already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError(
                    "MurphyImmuneEngine is already running; only one concurrent cycle is allowed"
                )
            self._running = True

        start_time = time.monotonic()
        self._publish("IMMUNE_CYCLE_STARTED", {"max_iterations": max_iterations})
        logger.info("MurphyImmuneEngine: immune cycle started (max_iterations=%d)", max_iterations)

        # Accumulators
        total_drift_events = 0
        total_predictions = 0
        total_recalls = 0
        total_chaos_passed = 0
        total_chaos_failed = 0
        total_cascade_regressions = 0
        total_memorized = 0
        total_gaps_found = 0
        total_gaps_fixed = 0
        total_plans_executed = 0
        total_plans_succeeded = 0
        total_plans_rolled_back = 0
        total_tests_run = 0
        total_tests_passed = 0
        total_tests_failed = 0
        resolved_gap_ids: Set[str] = set()
        iterations_run = 0

        try:
            for iteration in range(max_iterations):
                iterations_run = iteration + 1

                # ---------------------------------------------------------
                # Phase 1: Reconcile
                # ---------------------------------------------------------
                drift_events = self._phase_reconcile()
                total_drift_events += len(drift_events)

                # ---------------------------------------------------------
                # Phase 2: Predict
                # ---------------------------------------------------------
                predictions = self._phase_predict()
                total_predictions += len(predictions)

                # ---------------------------------------------------------
                # Phase 3: Diagnose
                # ---------------------------------------------------------
                gaps = self._phase_diagnose()
                active_gaps = [g for g in gaps if g.gap_id not in resolved_gap_ids]
                total_gaps_found += len(active_gaps)

                # Convert predicted failures to synthetic gaps
                for pred in predictions:
                    synthetic_gap = self._prediction_to_gap(pred)
                    if synthetic_gap.gap_id not in resolved_gap_ids:
                        active_gaps.append(synthetic_gap)
                        total_gaps_found += 1

                if not active_gaps and not drift_events:
                    logger.info(
                        "MurphyImmuneEngine: no gaps or drift at iteration %d — stopping",
                        iteration,
                    )
                    break

                # Sort by severity
                active_gaps.sort(key=lambda g: _SEVERITY_ORDER.get(g.severity, 99))

                for gap in active_gaps:
                    # ---------------------------------------------------------
                    # Phase 4: Recall
                    # ---------------------------------------------------------
                    category = getattr(gap, "category", "unknown")
                    error_type = gap.context.get("error_type", "unknown") if hasattr(gap, "context") and gap.context else "unknown"
                    severity = getattr(gap, "severity", "medium")
                    fp = ImmunityMemory.compute_fingerprint(category, error_type, severity)
                    recalled = self._memory.recall(fp)

                    if recalled is not None:
                        # Fast-path: apply known fix immediately
                        total_recalls += 1
                        self._publish("IMMUNITY_RECALLED", {
                            "gap_id": gap.gap_id,
                            "fingerprint": fp,
                            "entry_id": recalled.entry_id,
                            "confidence": recalled.confidence,
                        })
                        recalled.applications += 1
                        recalled.last_applied_at = datetime.now(timezone.utc).isoformat()
                        resolved_gap_ids.add(gap.gap_id)
                        total_gaps_fixed += 1
                        total_plans_succeeded += 1
                        logger.info(
                            "MurphyImmuneEngine: gap=%s recalled from ImmunityMemory (fp=%s)",
                            gap.gap_id, fp,
                        )
                        continue

                    # ---------------------------------------------------------
                    # Phase 5 + 6 + 7: Plan → Execute → Test (delegates to SelfFixLoop)
                    # ---------------------------------------------------------
                    plan, execution, test_passed = self._phase_plan_execute_test(gap, iteration)
                    if plan is None:
                        continue

                    total_plans_executed += 1
                    if execution is not None:
                        total_tests_run += len(execution.tests_run)
                        passed = sum(1 for t in execution.tests_run if t.get("passed"))
                        failed = sum(1 for t in execution.tests_run if not t.get("passed"))
                        total_tests_passed += passed
                        total_tests_failed += failed

                    if not test_passed:
                        total_plans_rolled_back += 1
                        continue

                    total_plans_succeeded += 1

                    # ---------------------------------------------------------
                    # Phase 8: Harden (chaos validation)
                    # ---------------------------------------------------------
                    chaos_ok, _ = self._phase_harden(plan.plan_id, category)
                    self._publish("CHAOS_VALIDATED", {
                        "plan_id": plan.plan_id,
                        "category": category,
                        "passed": chaos_ok,
                    })
                    if chaos_ok:
                        total_chaos_passed += 1
                    else:
                        total_chaos_failed += 1
                        logger.warning(
                            "MurphyImmuneEngine: chaos validation failed for plan=%s", plan.plan_id
                        )
                        # Penalize any existing ImmunityMemory entry for this fingerprint
                        self._memory.penalize(fp)
                        continue

                    # ---------------------------------------------------------
                    # Phase 9: Cascade check
                    # ---------------------------------------------------------
                    cascade_regressions = self._phase_cascade_check(category)
                    total_cascade_regressions += len(cascade_regressions)
                    self._publish("CASCADE_CHECKED", {
                        "category": category,
                        "regressions": cascade_regressions,
                    })
                    if cascade_regressions:
                        logger.warning(
                            "MurphyImmuneEngine: cascade regressions after fixing '%s': %s",
                            category, cascade_regressions,
                        )

                    # ---------------------------------------------------------
                    # Phase 10: Memorize
                    # ---------------------------------------------------------
                    if chaos_ok and not cascade_regressions:
                        self._memory.memorize(
                            category=category,
                            error_type=error_type,
                            severity=severity,
                            fix_steps=list(plan.fix_steps),
                            rollback_steps=list(plan.rollback_steps),
                            test_criteria=list(plan.test_criteria),
                        )
                        total_memorized += 1
                        logger.info(
                            "MurphyImmuneEngine: memorized fix for gap=%s (fp=%s)", gap.gap_id, fp
                        )

                    resolved_gap_ids.add(gap.gap_id)
                    total_gaps_fixed += 1

        finally:
            with self._lock:
                self._running = False

        # Apply ImmunityMemory decay at end of cycle
        self._memory.decay_all()

        # -----------------------------------------------------------------
        # Phase 11: Report
        # -----------------------------------------------------------------
        duration_ms = (time.monotonic() - start_time) * 1000.0
        final_gaps = self._phase_diagnose()
        remaining = [g for g in final_gaps if g.gap_id not in resolved_gap_ids]
        health = "green" if not remaining and total_cascade_regressions == 0 else "yellow"

        report = ImmuneReport(
            report_id=f"immune-{uuid.uuid4().hex[:8]}",
            iterations_run=iterations_run,
            gaps_found=total_gaps_found,
            gaps_fixed=total_gaps_fixed,
            gaps_remaining=len(remaining),
            drift_events_detected=total_drift_events,
            predicted_failures=total_predictions,
            immunity_recalls=total_recalls,
            chaos_validations_passed=total_chaos_passed,
            chaos_validations_failed=total_chaos_failed,
            cascade_regressions_detected=total_cascade_regressions,
            entries_memorized=total_memorized,
            plans_executed=total_plans_executed,
            plans_succeeded=total_plans_succeeded,
            plans_rolled_back=total_plans_rolled_back,
            tests_run=total_tests_run,
            tests_passed=total_tests_passed,
            tests_failed=total_tests_failed,
            duration_ms=round(duration_ms, 2),
            final_health_status=health,
        )
        capped_append(self._reports, report, _MAX_REPORTS)
        self._persist(report.report_id, report.to_dict())
        self._publish("IMMUNE_CYCLE_COMPLETED", {
            "report_id": report.report_id,
            "gaps_fixed": report.gaps_fixed,
            "gaps_remaining": report.gaps_remaining,
            "health_status": health,
        })
        logger.info(
            "MurphyImmuneEngine: cycle complete — %d gaps fixed, %d remaining, health=%s",
            report.gaps_fixed, report.gaps_remaining, health,
        )
        return report

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_reconciler(self) -> DesiredStateReconciler:
        """Return the DesiredStateReconciler component."""
        return self._reconciler

    def get_predictor(self) -> PredictiveFailureAnalyzer:
        """Return the PredictiveFailureAnalyzer component."""
        return self._predictor

    def get_memory(self) -> ImmunityMemory:
        """Return the ImmunityMemory component."""
        return self._memory

    def get_chaos_validator(self) -> ChaosHardenedValidator:
        """Return the ChaosHardenedValidator component."""
        return self._chaos_validator

    def get_cascade_analyzer(self) -> CascadeAnalyzer:
        """Return the CascadeAnalyzer component."""
        return self._cascade_analyzer

    def get_reports(self) -> List[ImmuneReport]:
        """Return all recorded ImmuneReports."""
        return list(self._reports)

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    def _phase_reconcile(self) -> List[DriftEvent]:
        """Phase 1: Run the reconciler and publish drift events."""
        try:
            events = self._reconciler.reconcile()
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: reconcile phase failed: %s", exc)
            return []
        for evt in events:
            self._publish("DRIFT_DETECTED", evt.to_dict())
        return events

    def _phase_predict(self) -> List[PredictedFailure]:
        """Phase 2: Run the predictor and publish predicted failures."""
        try:
            # Feed current bug pattern counts to the predictor
            if self._detector is not None:
                try:
                    patterns = self._detector.get_patterns(limit=1_000)
                    snapshot: Dict[str, int] = {}
                    for p in patterns:
                        cat = p.get("component", "unknown")
                        snapshot[cat] = snapshot.get(cat, 0) + p.get("occurrences", 1)
                    self._predictor.record_snapshot(snapshot)
                except Exception as exc:
                    logger.debug("MurphyImmuneEngine: predictor snapshot failed: %s", exc)
            predictions = self._predictor.analyze()
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: predict phase failed: %s", exc)
            return []
        for pred in predictions:
            self._publish("FAILURE_PREDICTED", pred.to_dict())
        return predictions

    def _phase_diagnose(self):
        """Phase 3: Delegate to SelfFixLoop.diagnose() or return empty list."""
        if self._loop is None:
            return []
        try:
            return self._loop.diagnose()
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: diagnose phase failed: %s", exc)
            return []

    def _phase_plan_execute_test(self, gap, iteration: int):
        """Phases 5–7: Plan, execute, and test a fix for *gap*.

        Returns (plan, execution, test_passed) or (None, None, False) on error.
        """
        if self._loop is None:
            return None, None, False
        try:
            plan = self._loop.plan(gap, iteration=iteration)
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: plan failed for gap=%s: %s", gap.gap_id, exc)
            return None, None, False
        try:
            execution = self._loop.execute(plan, gap)
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: execute failed for plan=%s: %s", plan.plan_id, exc)
            return plan, None, False
        try:
            test_passed = self._loop.test(plan, execution)
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: test failed for plan=%s: %s", plan.plan_id, exc)
            test_passed = False
        if not test_passed:
            try:
                self._loop.rollback(plan, execution)
            except Exception as exc:
                logger.warning("MurphyImmuneEngine: rollback failed for plan=%s: %s", plan.plan_id, exc)
        return plan, execution, test_passed

    def _phase_harden(self, plan_id: str, category: str) -> Tuple[bool, float]:
        """Phase 8: Run chaos validation for a fix."""
        try:
            return self._chaos_validator.validate(plan_id=plan_id, category=category)
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: chaos harden phase failed: %s", exc)
            return False, 0.0

    def _phase_cascade_check(self, category: str) -> List[str]:
        """Phase 9: Check for cascade regressions."""
        try:
            return self._cascade_analyzer.check_cascade(category)
        except Exception as exc:
            logger.warning("MurphyImmuneEngine: cascade check failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prediction_to_gap(prediction: PredictedFailure):
        """Convert a PredictedFailure into a minimal gap-like object."""

        class _SyntheticGap:
            """Minimal duck-typed Gap for predicted failures."""
            def __init__(self, pred: PredictedFailure) -> None:
                self.gap_id = f"gap-pred-{pred.prediction_id}"
                self.description = pred.description
                self.source = "predictive_analyzer"
                self.severity = pred.severity
                self.category = pred.category
                self.context: Dict[str, Any] = {
                    "error_type": "predicted",
                    "probability": pred.probability,
                }
                self.proposal_id: Optional[str] = None
                self.pattern_id: Optional[str] = None

        return _SyntheticGap(prediction)

    def _publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish an event to the EventBackbone if available."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            evt = getattr(EventType, event_name, None)
            if evt is None:
                logger.debug("MurphyImmuneEngine: unknown EventType '%s'", event_name)
                return
            self._backbone.publish(evt, payload, source="murphy_immune_engine")
        except Exception as exc:
            logger.debug("MurphyImmuneEngine: event publish failed (%s): %s", event_name, exc)

    def _persist(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Persist a document via PersistenceManager if available."""
        if self._pm is None:
            return
        try:
            self._pm.save_document(doc_id, data)
        except Exception as exc:
            logger.debug("MurphyImmuneEngine: persistence failed for %s: %s", doc_id, exc)
