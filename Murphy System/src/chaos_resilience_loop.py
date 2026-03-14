"""
Chaos Resilience Loop for Murphy System.

Design Label: ARCH-006 — Continuous Chaos Resilience Verification
Owner: Platform Engineering
Dependencies:
  - SyntheticFailureGenerator (generates controlled failures)
  - SelfFixLoop (ARCH-005 — receives actionable gaps)
  - SelfHealingCoordinator (OBS-004)
  - EventBackbone
  - PersistenceManager

Implements continuous automated chaos testing:
  Generate → Inject → Observe → Score → Feed-Back

Inspired by Netflix Chaos Engineering, adapted for Murphy's architecture
where targets are confidence engines, gates, bot orchestration, and
recovery procedures rather than infrastructure.

Safety invariants:
  - NEVER touches production — uses SyntheticFailureGenerator's safety guarantees
  - Bounded by max_experiments to prevent runaway chaos
  - Results feed directly into SelfFixLoop as actionable gaps
  - Full audit trail via PersistenceManager and EventBackbone
  - Thread-safe: all shared state guarded by Lock
  - Requires HIGH authority to run (compatible with GovernanceKernel)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResilienceHypothesis:
    """Describes a resilience expectation that will be verified by chaos experiment.

    A hypothesis states what *should* happen when a specific failure occurs.
    If the system behaves as expected, the hypothesis is validated (score → 1.0).
    If it does not, the experiment exposes a gap that feeds back into SelfFixLoop.
    """
    hypothesis_id: str
    description: str
    target_component: str
    failure_type: str
    expected_behavior: str
    max_acceptable_recovery_time_sec: float = 60.0
    max_acceptable_confidence_drop: float = 0.3


@dataclass
class ResilienceExperiment:
    """Records the full outcome of a single chaos resilience experiment."""
    experiment_id: str
    hypothesis_id: str
    injected_failure: Any            # reference to FailureCase
    recovery_observed: bool
    recovery_time_sec: float
    confidence_drop: float
    gates_that_fired: List[str]
    gates_that_missed: List[str]
    regression_detected: bool
    score: float                     # 0.0 = total failure, 1.0 = perfect resilience
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        failure_dict: Any = None
        if self.injected_failure is not None:
            try:
                failure_dict = self.injected_failure.to_dict()
            except Exception as exc:
                logger.debug("Could not serialise injected_failure: %s", exc)
                failure_dict = str(self.injected_failure)
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "injected_failure": failure_dict,
            "recovery_observed": self.recovery_observed,
            "recovery_time_sec": round(self.recovery_time_sec, 4),
            "confidence_drop": round(self.confidence_drop, 4),
            "gates_that_fired": list(self.gates_that_fired),
            "gates_that_missed": list(self.gates_that_missed),
            "regression_detected": self.regression_detected,
            "score": round(self.score, 4),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ResilienceScorecard:
    """Aggregated scorecard produced after running a suite of experiments."""
    overall_score: float
    component_scores: Dict[str, float]
    weakest_components: List[str]
    recommendations: List[str]
    experiments_run: int
    experiments_passed: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "component_scores": {k: round(v, 4) for k, v in self.component_scores.items()},
            "weakest_components": list(self.weakest_components),
            "recommendations": list(self.recommendations),
            "experiments_run": self.experiments_run,
            "experiments_passed": self.experiments_passed,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _compute_experiment_score(
    hypothesis: ResilienceHypothesis,
    recovery_observed: bool,
    recovery_time_sec: float,
    confidence_drop: float,
    gates_that_fired: List[str],
    gates_that_missed: List[str],
    regression_detected: bool,
) -> float:
    """Compute a 0.0-1.0 resilience score for one experiment.

    Weights:
      - Recovery observed:       40%
      - Recovery within time:    30%
      - Confidence drop bounded: 20%
      - No regression:           10%

    An additional gate-coverage penalty scales the total down proportionally
    when expected gates were missed.

    Returns:
        0.0 if recovery was not observed at all (total failure).
        1.0 if every criterion passes perfectly.
        Proportional value in between for partial success.
    """
    if not recovery_observed:
        return 0.0

    score = 0.4   # recovery observed

    max_time = max(hypothesis.max_acceptable_recovery_time_sec, 0.001)
    if recovery_time_sec <= max_time:
        score += 0.3
    else:
        score += 0.3 * min(1.0, max_time / recovery_time_sec)

    max_drop = max(hypothesis.max_acceptable_confidence_drop, 0.001)
    if confidence_drop <= max_drop:
        score += 0.2
    else:
        score += 0.2 * min(1.0, max_drop / confidence_drop)

    if not regression_detected:
        score += 0.1

    total_gates = len(gates_that_fired) + len(gates_that_missed)
    if total_gates > 0:
        miss_ratio = len(gates_that_missed) / total_gates
        score = score * (1.0 - miss_ratio * 0.5)

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Built-in hypothesis library
# ---------------------------------------------------------------------------

_BUILTIN_HYPOTHESES: List[Dict[str, Any]] = [
    {
        "hypothesis_id": "hyp-builtin-001",
        "description": "Timeout cluster should be caught by threshold tuning within 60s",
        "target_component": "threshold_tuning",
        "failure_type": "delayed_verification",
        "expected_behavior": "Gate should catch timeout cluster and trigger threshold tuning within 60 seconds",
        "max_acceptable_recovery_time_sec": 60.0,
        "max_acceptable_confidence_drop": 0.3,
    },
    {
        "hypothesis_id": "hyp-builtin-002",
        "description": "Skipped gate should trigger confidence grounding check",
        "target_component": "confidence_engine",
        "failure_type": "skipped_gate",
        "expected_behavior": "Skipped gate event should trigger a confidence grounding verification check",
        "max_acceptable_recovery_time_sec": 30.0,
        "max_acceptable_confidence_drop": 0.2,
    },
    {
        "hypothesis_id": "hyp-builtin-003",
        "description": "False confidence inflation should be detected and corrected",
        "target_component": "confidence_engine",
        "failure_type": "false_confidence",
        "expected_behavior": "False confidence inflation should be detected by recalibration gate and corrected",
        "max_acceptable_recovery_time_sec": 45.0,
        "max_acceptable_confidence_drop": 0.4,
    },
    {
        "hypothesis_id": "hyp-builtin-004",
        "description": "Missing rollback should trigger recovery procedure registration",
        "target_component": "recovery_coordinator",
        "failure_type": "missing_rollback",
        "expected_behavior": "Missing rollback detection should automatically register a recovery procedure",
        "max_acceptable_recovery_time_sec": 30.0,
        "max_acceptable_confidence_drop": 0.25,
    },
]


# ---------------------------------------------------------------------------
# ChaosResilienceLoop
# ---------------------------------------------------------------------------

class ChaosResilienceLoop:
    """Continuous automated chaos resilience testing engine.

    Design Label: ARCH-006
    Owner: Platform Engineering

    The loop follows the cycle:
      HYPOTHESIS → INJECT → OBSERVE → SCORE → FEED-BACK

    Produces a :class:`ResilienceScorecard` and converts weak spots into
    :class:`~self_fix_loop.Gap` objects that are fed into SelfFixLoop.

    Safety invariants:
      - Only uses SyntheticFailureGenerator (never touches production)
      - Bounded by max_experiments
      - Full audit trail via EventBackbone and PersistenceManager
      - Thread-safe (single mutex for experiment runs)

    Usage::

        loop = ChaosResilienceLoop(
            failure_generator=pipeline,
            self_fix_loop=fix_loop,
            healing_coordinator=coordinator,
            event_backbone=backbone,
            persistence_manager=pm,
        )
        suite_results = loop.run_suite(loop.builtin_hypotheses())
        scorecard = loop.generate_scorecard()
        loop.feed_gaps_to_self_fix()
    """

    def __init__(
        self,
        failure_generator=None,
        self_fix_loop=None,
        healing_coordinator=None,
        event_backbone=None,
        persistence_manager=None,
    ) -> None:
        self._failure_generator = failure_generator
        self._self_fix_loop = self_fix_loop
        self._coordinator = healing_coordinator
        self._backbone = event_backbone
        self._pm = persistence_manager

        self._lock = threading.Lock()

        # Experiment state
        self._hypotheses: Dict[str, ResilienceHypothesis] = {}
        self._experiments: List[ResilienceExperiment] = []
        self._scorecards: List[ResilienceScorecard] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def define_hypothesis(
        self,
        hypothesis_id: str,
        description: str,
        target_component: str,
        failure_type: str,
        expected_behavior: str,
        max_acceptable_recovery_time_sec: float = 60.0,
        max_acceptable_confidence_drop: float = 0.3,
    ) -> ResilienceHypothesis:
        """Define a new resilience hypothesis and register it for later use.

        Args:
            hypothesis_id: Unique identifier for this hypothesis.
            description: Human-readable summary of the hypothesis.
            target_component: Which subsystem this hypothesis tests.
            failure_type: FailureType value string (e.g. ``"skipped_gate"``).
            expected_behavior: Description of the expected recovery behaviour.
            max_acceptable_recovery_time_sec: Maximum recovery time allowed.
            max_acceptable_confidence_drop: Maximum confidence drop allowed.

        Returns:
            The created :class:`ResilienceHypothesis`.
        """
        hypothesis = ResilienceHypothesis(
            hypothesis_id=hypothesis_id,
            description=description,
            target_component=target_component,
            failure_type=failure_type,
            expected_behavior=expected_behavior,
            max_acceptable_recovery_time_sec=max_acceptable_recovery_time_sec,
            max_acceptable_confidence_drop=max_acceptable_confidence_drop,
        )
        with self._lock:
            self._hypotheses[hypothesis_id] = hypothesis
        logger.debug("Hypothesis defined: %s", hypothesis_id)
        return hypothesis

    def run_experiment(self, hypothesis: ResilienceHypothesis) -> ResilienceExperiment:
        """Inject a synthetic failure, observe recovery, measure, and score.

        The experiment:
        1. Generates a :class:`FailureCase` using SyntheticFailureGenerator.
        2. Runs a sandboxed simulation via FailureInjectionPipeline.
        3. Extracts recovery metrics from the SimulationResult.
        4. Scores the result against the hypothesis criteria.

        Args:
            hypothesis: The hypothesis to test.

        Returns:
            A fully populated :class:`ResilienceExperiment`.
        """
        experiment_id = f"exp-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()

        self._publish_event("CHAOS_EXPERIMENT_STARTED", {
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "failure_type": hypothesis.failure_type,
            "target_component": hypothesis.target_component,
        })

        start_mono = time.monotonic()

        # Step 1: generate the failure case
        failure_case = self._generate_failure_case(hypothesis.failure_type)

        # Step 2: run sandboxed simulation
        sim_result = self._simulate_failure(failure_case)

        elapsed = time.monotonic() - start_mono

        # Step 3: extract metrics from simulation
        initial_confidence = 0.8  # standard sandbox baseline
        if sim_result is not None:
            final_confidence = getattr(sim_result, "final_confidence", 0.8)
            confidence_drop = max(0.0, initial_confidence - final_confidence)
            gates_fired = list(getattr(sim_result, "gates_triggered", []))
            telemetry = getattr(sim_result, "telemetry_outcome", None)
            detection_latency = getattr(telemetry, "detection_latency", elapsed) if telemetry else elapsed
            recovery_observed = bool(getattr(sim_result, "execution_halted", False))
            final_risk = getattr(sim_result, "final_risk", 0.0)
            missed = list(getattr(sim_result, "gates_missed", []) if failure_case is None
                          else getattr(failure_case, "missed_gates", []))
        else:
            confidence_drop = 0.0
            gates_fired = []
            detection_latency = elapsed
            recovery_observed = False
            final_risk = 0.0
            missed = []

        regression_detected = final_risk > 0.8 and len(gates_fired) == 0

        # Step 4: score
        score = _compute_experiment_score(
            hypothesis=hypothesis,
            recovery_observed=recovery_observed,
            recovery_time_sec=detection_latency,
            confidence_drop=confidence_drop,
            gates_that_fired=gates_fired,
            gates_that_missed=missed,
            regression_detected=regression_detected,
        )

        completed_at = datetime.now(timezone.utc).isoformat()
        experiment = ResilienceExperiment(
            experiment_id=experiment_id,
            hypothesis_id=hypothesis.hypothesis_id,
            injected_failure=failure_case,
            recovery_observed=recovery_observed,
            recovery_time_sec=round(detection_latency, 4),
            confidence_drop=round(confidence_drop, 4),
            gates_that_fired=gates_fired,
            gates_that_missed=missed,
            regression_detected=regression_detected,
            score=round(score, 4),
            started_at=started_at,
            completed_at=completed_at,
        )

        with self._lock:
            capped_append(self._experiments, experiment)

        self._persist_experiment(experiment)
        self._publish_event("CHAOS_EXPERIMENT_COMPLETED", {
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "score": experiment.score,
            "recovery_observed": experiment.recovery_observed,
        })

        logger.info(
            "Chaos experiment %s completed: score=%.2f, recovery=%s",
            experiment_id, score, recovery_observed,
        )
        return experiment

    def run_suite(
        self,
        hypotheses: List[ResilienceHypothesis],
        max_experiments: int = 50,
    ) -> List[ResilienceExperiment]:
        """Run a suite of experiments, bounded by max_experiments.

        Args:
            hypotheses: List of hypotheses to test.
            max_experiments: Hard upper bound on total experiments run.

        Returns:
            List of completed :class:`ResilienceExperiment` objects.
        """
        results: List[ResilienceExperiment] = []
        for i, hypothesis in enumerate(hypotheses):
            if i >= max_experiments:
                logger.info(
                    "ChaosResilienceLoop: max_experiments=%d reached, stopping suite",
                    max_experiments,
                )
                break
            try:
                experiment = self.run_experiment(hypothesis)
                results.append(experiment)
            except Exception as exc:
                logger.warning(
                    "Chaos experiment for hypothesis %s failed: %s",
                    hypothesis.hypothesis_id, exc,
                )
        return results

    def generate_scorecard(self) -> ResilienceScorecard:
        """Produce an overall resilience scorecard from completed experiments.

        Aggregates scores by component, identifies weak spots, and generates
        human-readable recommendations.

        Returns:
            A :class:`ResilienceScorecard` summarising system resilience.
        """
        with self._lock:
            experiments = list(self._experiments)

        if not experiments:
            scorecard = ResilienceScorecard(
                overall_score=0.0,
                component_scores={},
                weakest_components=[],
                recommendations=["No experiments have been run yet."],
                experiments_run=0,
                experiments_passed=0,
            )
            with self._lock:
                capped_append(self._scorecards, scorecard)
            self._publish_event("CHAOS_SCORECARD_GENERATED", scorecard.to_dict())
            return scorecard

        # Map each experiment to its hypothesis so we can group by component
        component_experiment_scores: Dict[str, List[float]] = {}
        for exp in experiments:
            hypothesis = self._hypotheses.get(exp.hypothesis_id)
            component = hypothesis.target_component if hypothesis else "unknown"
            component_experiment_scores.setdefault(component, [])
            component_experiment_scores[component].append(exp.score)

        component_scores: Dict[str, float] = {
            comp: sum(scores) / (len(scores) or 1)
            for comp, scores in component_experiment_scores.items()
        }

        overall_score = sum(e.score for e in experiments) / (len(experiments) or 1)
        experiments_passed = sum(1 for e in experiments if e.score >= 0.7)

        weak_threshold = 0.7
        weakest_components = sorted(
            [comp for comp, sc in component_scores.items() if sc < weak_threshold],
            key=lambda c: component_scores[c],
        )

        recommendations = _build_recommendations(weakest_components, component_scores, experiments)

        scorecard = ResilienceScorecard(
            overall_score=round(overall_score, 4),
            component_scores=component_scores,
            weakest_components=weakest_components,
            recommendations=recommendations,
            experiments_run=len(experiments),
            experiments_passed=experiments_passed,
        )
        with self._lock:
            capped_append(self._scorecards, scorecard)

        self._persist_scorecard(scorecard)
        self._publish_event("CHAOS_SCORECARD_GENERATED", scorecard.to_dict())
        logger.info(
            "Chaos scorecard generated: overall=%.2f, %d/%d experiments passed",
            overall_score, experiments_passed, len(experiments),
        )
        return scorecard

    def feed_gaps_to_self_fix(self) -> List[str]:
        """Convert weak spots into Gap objects and feed them to SelfFixLoop.

        For each weakest component identified in the latest scorecard,
        a Gap is created and processed through the SelfFixLoop (plan → execute).

        Returns:
            List of gap_ids that were submitted.
        """
        if self._self_fix_loop is None:
            logger.debug("ChaosResilienceLoop: no SelfFixLoop attached; skipping gap feed")
            return []

        scorecard = self.generate_scorecard()
        if not scorecard.weakest_components:
            self._publish_event("CHAOS_GAPS_SUBMITTED", {"gap_count": 0, "gap_ids": []})
            return []

        fed_gap_ids: List[str] = []
        for component in scorecard.weakest_components:
            comp_score = scorecard.component_scores.get(component, 0.0)
            gap = _build_gap(component, comp_score)
            try:
                plan = self._self_fix_loop.plan(gap)
                self._self_fix_loop.execute(plan, gap)
                fed_gap_ids.append(gap.gap_id)
                logger.info(
                    "Chaos gap %s submitted to SelfFixLoop for component '%s' (score=%.2f)",
                    gap.gap_id, component, comp_score,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to submit chaos gap for component '%s': %s",
                    component, exc,
                )

        self._publish_event("CHAOS_GAPS_SUBMITTED", {
            "gap_count": len(fed_gap_ids),
            "gap_ids": fed_gap_ids,
        })
        return fed_gap_ids

    # ------------------------------------------------------------------
    # Built-in hypothesis library
    # ------------------------------------------------------------------

    @staticmethod
    def builtin_hypotheses() -> List[ResilienceHypothesis]:
        """Return the pre-defined hypothesis library for Murphy's subsystems.

        Covers the four canonical resilience scenarios:
        - Timeout cluster → threshold tuning
        - Skipped gate → confidence grounding check
        - False confidence inflation → detection and correction
        - Missing rollback → recovery procedure registration
        """
        return [
            ResilienceHypothesis(**{k: v for k, v in h.items()})
            for h in _BUILTIN_HYPOTHESES
        ]

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_experiments(self) -> List[Dict[str, Any]]:
        """Return all experiments as serialisable dicts."""
        with self._lock:
            return [e.to_dict() for e in self._experiments]

    def get_scorecards(self) -> List[Dict[str, Any]]:
        """Return all scorecards as serialisable dicts."""
        with self._lock:
            return [s.to_dict() for s in self._scorecards]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_failure_case(self, failure_type_str: str) -> Any:
        """Generate a synthetic FailureCase for the given failure_type string."""
        try:
            from synthetic_failure_generator.injection_pipeline import FailureInjectionPipeline
            from synthetic_failure_generator.models import FailureType

            ft = FailureType(failure_type_str)

            pipeline = self._failure_generator if self._failure_generator is not None \
                else FailureInjectionPipeline()

            base_scenario = pipeline.create_base_scenario(
                scenario_name="chaos_sandbox",
                artifact_graph={},
                interface_definitions={},
                gate_library=[],
                initial_confidence=0.8,
                initial_risk=0.1,
            )
            operator = pipeline.create_perturbation_operator(
                f"chaos_{failure_type_str}",
                ft,
                {},
            )
            failure_case = pipeline.apply_perturbation(base_scenario, operator)
            return failure_case
        except Exception as exc:
            logger.debug("Could not generate FailureCase via pipeline: %s", exc)
            return None

    def _simulate_failure(self, failure_case: Any) -> Any:
        """Run a sandboxed simulation of the given failure_case."""
        if failure_case is None:
            return None
        try:
            from synthetic_failure_generator.injection_pipeline import FailureInjectionPipeline

            pipeline = self._failure_generator if self._failure_generator is not None \
                else FailureInjectionPipeline()

            return pipeline.run_pipeline(failure_case)
        except Exception as exc:
            logger.debug("Could not simulate failure: %s", exc)
            return None

    def _persist_experiment(self, experiment: ResilienceExperiment) -> None:
        if self._pm is None:
            return
        try:
            self._pm.save_document(experiment.experiment_id, experiment.to_dict())
        except Exception as exc:
            logger.debug("Persistence skipped for experiment %s: %s", experiment.experiment_id, exc)

    def _persist_scorecard(self, scorecard: ResilienceScorecard) -> None:
        if self._pm is None:
            return
        try:
            sc_id = f"scorecard-{uuid.uuid4().hex[:8]}"
            self._pm.save_document(sc_id, scorecard.to_dict())
        except Exception as exc:
            logger.debug("Persistence skipped for scorecard: %s", exc)

    def _publish_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import Event, EventType

            et_map = {
                "CHAOS_EXPERIMENT_STARTED": EventType.CHAOS_EXPERIMENT_STARTED,
                "CHAOS_EXPERIMENT_COMPLETED": EventType.CHAOS_EXPERIMENT_COMPLETED,
                "CHAOS_SCORECARD_GENERATED": EventType.CHAOS_SCORECARD_GENERATED,
                "CHAOS_GAPS_SUBMITTED": EventType.CHAOS_GAPS_SUBMITTED,
            }
            et = et_map.get(event_name)
            if et is None:
                return
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=et,
                payload=payload,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="chaos_resilience_loop",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers (not methods — kept here to avoid coupling)
# ---------------------------------------------------------------------------

def _build_recommendations(
    weakest_components: List[str],
    component_scores: Dict[str, float],
    experiments: List[ResilienceExperiment],
) -> List[str]:
    """Build actionable recommendation strings from scorecard data."""
    recs: List[str] = []
    for comp in weakest_components:
        score = component_scores.get(comp, 0.0)
        recs.append(
            f"Component '{comp}' resilience score is {score:.2f} — "
            "review gate coverage and recovery procedure registration."
        )

    # Identify experiments with regressions
    regressed = [e for e in experiments if e.regression_detected]
    if regressed:
        recs.append(
            f"{len(regressed)} experiment(s) detected regressions — "
            "investigate gate-miss patterns and add threshold guards."
        )

    # Identify common missed gates
    all_missed: List[str] = []
    for e in experiments:
        all_missed.extend(e.gates_that_missed)
    if all_missed:
        unique_missed = list(dict.fromkeys(all_missed))[:5]
        recs.append(
            "Frequently missed gates: "
            + ", ".join(unique_missed)
            + ". Consider adding them to the mandatory gate library."
        )

    if not recs:
        recs.append("All components meet the resilience threshold. No immediate action required.")

    return recs


def _build_gap(component: str, comp_score: float) -> Any:
    """Build a SelfFixLoop Gap object for a weak component."""
    try:
        from self_fix_loop import Gap
        return Gap(
            gap_id=f"chaos-gap-{uuid.uuid4().hex[:8]}",
            description=(
                f"Chaos resilience experiment revealed weakness in '{component}' "
                f"(score={comp_score:.2f}). Review gate coverage and recovery procedures."
            ),
            source="chaos_resilience_loop",
            severity="high" if comp_score < 0.5 else "medium",
            category=component,
            context={
                "chaos_source": True,
                "component_score": comp_score,
            },
        )
    except Exception as exc:
        logger.debug("Could not build Gap object: %s", exc)
        return None
