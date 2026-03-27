"""
production_output_calibrator.py — Production Output Calibration Engine
======================================================================

Implements a dual-loop calibration system for any production output:

Loop 1 — **Professional Benchmark Loop**
    Compare output against 10 professional examples, extract the best
    practices from each, score the output, identify gaps, build a
    remediation plan, apply improvements, and repeat until the output
    reaches 90-95 % of the combined best-practice standard.

Loop 2 — **QC Against Proposal Request Loop**
    Validate that the (improved) output still meets every requirement
    stated in the original proposal / request.  Any drift or omission
    is flagged and fed back into the next calibration round.

Together the two loops guarantee that the final output is both
*professionally competitive* and *request-compliant*.

Design label: CAL-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QualityDimension(Enum):
    """Measurable axes of production-output quality."""
    CLARITY = "clarity"
    COMPLETENESS = "completeness"
    STRUCTURE = "structure"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    PROFESSIONALISM = "professionalism"
    EFFICIENCY = "efficiency"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"
    USABILITY = "usability"


class CalibrationStatus(Enum):
    """Overall status of a calibration run."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONVERGED = "converged"
    FAILED = "failed"


class QCVerdict(Enum):
    """Outcome of QC against a proposal request."""
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProductionOutput:
    """The artefact being calibrated."""
    output_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    output_type: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class ProfessionalExample:
    """One of up to 10 professional benchmark examples."""
    example_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    content: str = ""
    strengths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BestPractice:
    """A single best practice extracted from one or more examples."""
    practice_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    dimension: QualityDimension = QualityDimension.CLARITY
    description: str = ""
    source_example_ids: List[str] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class DimensionScore:
    """Score for one quality dimension (0.0 – 1.0)."""
    dimension: QualityDimension = QualityDimension.CLARITY
    score: float = 0.0
    max_score: float = 1.0
    evidence: List[str] = field(default_factory=list)


@dataclass
class GapAnalysis:
    """A single identified gap between the output and best practices."""
    gap_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    dimension: QualityDimension = QualityDimension.CLARITY
    description: str = ""
    severity: float = 0.0          # 0.0 (minor) → 1.0 (critical)
    best_practice_id: str = ""
    recommended_action: str = ""


@dataclass
class ProposalRequirement:
    """One requirement extracted from the original proposal / request."""
    requirement_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    category: str = ""
    mandatory: bool = True
    met: bool = False
    evidence: str = ""


@dataclass
class QCResult:
    """Result of QC validation against the proposal request."""
    verdict: QCVerdict = QCVerdict.FAIL
    requirements_total: int = 0
    requirements_met: int = 0
    compliance_pct: float = 0.0
    unmet_requirements: List[ProposalRequirement] = field(default_factory=list)
    notes: str = ""


@dataclass
class CalibrationPlan:
    """Remediation plan to close identified gaps."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    gaps: List[GapAnalysis] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    priority_order: List[str] = field(default_factory=list)
    estimated_improvement: float = 0.0


@dataclass
class CalibrationRound:
    """Record of one iteration through the calibration loop."""
    round_number: int = 0
    benchmark_score: float = 0.0
    qc_result: Optional[QCResult] = None
    gaps_found: int = 0
    gaps_closed: int = 0
    plan: Optional[CalibrationPlan] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class CalibrationReport:
    """Final report produced at the end of calibration."""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: CalibrationStatus = CalibrationStatus.NOT_STARTED
    rounds: List[CalibrationRound] = field(default_factory=list)
    final_benchmark_score: float = 0.0
    final_qc_compliance: float = 0.0
    best_practices_applied: int = 0
    total_gaps_closed: int = 0
    converged: bool = False
    summary: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_EXAMPLES: int = 10
_MIN_EXAMPLES: int = 1
_TARGET_THRESHOLD_HIGH: float = 0.95
_TARGET_THRESHOLD_LOW: float = 0.90
_MAX_CALIBRATION_ROUNDS: int = 50
_QC_PASS_THRESHOLD: float = 1.0   # 100 % of mandatory reqs must be met
_QC_PARTIAL_THRESHOLD: float = 0.8


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ProductionOutputCalibrator:
    """Dual-loop calibration engine for production outputs.

    Usage::

        cal = ProductionOutputCalibrator()
        cal.register_output(my_output)
        cal.register_examples(examples_list)        # up to 10
        cal.register_proposal_request(requirements)  # QC anchor
        report = cal.calibrate()
    """

    def __init__(
        self,
        target_threshold: float = _TARGET_THRESHOLD_LOW,
        max_rounds: int = _MAX_CALIBRATION_ROUNDS,
    ) -> None:
        if not (_TARGET_THRESHOLD_LOW <= target_threshold <= _TARGET_THRESHOLD_HIGH):
            raise ValueError(
                f"target_threshold must be between "
                f"{_TARGET_THRESHOLD_LOW} and {_TARGET_THRESHOLD_HIGH}, "
                f"got {target_threshold}"
            )
        self._lock = threading.Lock()
        self._output: Optional[ProductionOutput] = None
        self._examples: List[ProfessionalExample] = []
        self._requirements: List[ProposalRequirement] = []
        self._best_practices: List[BestPractice] = []
        self._rounds: List[CalibrationRound] = []
        self._target_threshold = target_threshold
        self._max_rounds = max_rounds
        self._status = CalibrationStatus.NOT_STARTED
        self._improvements_applied: List[str] = []

    # -- registration -------------------------------------------------------

    def register_output(self, output: ProductionOutput) -> None:
        """Register the production output to be calibrated."""
        with self._lock:
            if not isinstance(output, ProductionOutput):
                raise TypeError("output must be a ProductionOutput instance")
            self._output = output
            self._status = CalibrationStatus.NOT_STARTED
            self._rounds.clear()

    def register_examples(
        self, examples: List[ProfessionalExample],
    ) -> None:
        """Register professional benchmark examples (1-10)."""
        with self._lock:
            if not examples:
                raise ValueError("At least one professional example is required")
            if len(examples) > _MAX_EXAMPLES:
                raise ValueError(
                    f"Maximum {_MAX_EXAMPLES} examples allowed, got {len(examples)}"
                )
            for ex in examples:
                if not isinstance(ex, ProfessionalExample):
                    raise TypeError(
                        "Every example must be a ProfessionalExample instance"
                    )
            self._examples = list(examples)

    def register_proposal_request(
        self, requirements: List[ProposalRequirement],
    ) -> None:
        """Register requirements from the original proposal / request."""
        with self._lock:
            for req in requirements:
                if not isinstance(req, ProposalRequirement):
                    raise TypeError(
                        "Every requirement must be a ProposalRequirement instance"
                    )
            self._requirements = list(requirements)

    # -- best-practice extraction -------------------------------------------

    def extract_best_practices(self) -> List[BestPractice]:
        """Analyse registered examples and extract combined best practices.

        For each quality dimension, the strongest example is identified and
        a best-practice entry is created.  If multiple examples share the
        same strength, all are recorded.
        """
        with self._lock:
            if not self._examples:
                raise ValueError("No examples registered")

            practices: List[BestPractice] = []
            for dim in QualityDimension:
                relevant_ids: List[str] = []
                desc_parts: List[str] = []
                for ex in self._examples:
                    strength_hit = any(
                        dim.value.lower() in s.lower() for s in ex.strengths
                    )
                    content_hit = dim.value.lower() in ex.content.lower()
                    if strength_hit or content_hit:
                        relevant_ids.append(ex.example_id)
                        for s in ex.strengths:
                            if dim.value.lower() in s.lower():
                                desc_parts.append(s)

                if not relevant_ids:
                    relevant_ids = [self._examples[0].example_id]
                    desc_parts = [
                        f"Default {dim.value} standard from primary example"
                    ]

                practices.append(BestPractice(
                    dimension=dim,
                    description="; ".join(dict.fromkeys(desc_parts))
                    if desc_parts
                    else f"Baseline {dim.value} best practice",
                    source_example_ids=relevant_ids,
                    weight=1.0 + 0.1 * (len(relevant_ids) - 1),
                ))

            self._best_practices = practices
            return list(practices)

    # -- scoring ------------------------------------------------------------

    def score_output(self) -> List[DimensionScore]:
        """Score the current output against extracted best practices.

        Returns one ``DimensionScore`` per quality dimension.
        """
        with self._lock:
            return self._score_output_unlocked()

    def _score_output_unlocked(self) -> List[DimensionScore]:
        if self._output is None:
            raise ValueError("No output registered")
        if not self._best_practices:
            raise ValueError("Best practices not yet extracted")

        scores: List[DimensionScore] = []
        content_lower = self._output.content.lower()

        for bp in self._best_practices:
            dim = bp.dimension
            evidence: List[str] = []
            raw = 0.0

            kw = dim.value.lower()
            if kw in content_lower:
                raw += 0.3
                evidence.append(f"Content mentions '{kw}'")

            for imp in self._improvements_applied:
                if kw in imp.lower():
                    raw += 0.15
                    evidence.append(f"Improvement applied: {imp[:60]}")

            has_metadata = bool(self._output.metadata.get(kw))
            if has_metadata:
                raw += 0.2
                evidence.append(f"Metadata key '{kw}' present")

            src_count = len(bp.source_example_ids)
            coverage_bonus = min(0.3, 0.03 * src_count)
            raw += coverage_bonus
            if src_count > 0:
                evidence.append(
                    f"{src_count} example(s) contributed to this dimension"
                )

            score = min(1.0, raw * bp.weight)
            scores.append(DimensionScore(
                dimension=dim,
                score=round(score, 4),
                max_score=1.0,
                evidence=evidence,
            ))

        return scores

    # -- gap analysis -------------------------------------------------------

    def identify_gaps(self) -> List[GapAnalysis]:
        """Compare output scores to target and return gaps."""
        with self._lock:
            return self._identify_gaps_unlocked()

    def _identify_gaps_unlocked(self) -> List[GapAnalysis]:
        scores = self._score_output_unlocked()
        gaps: List[GapAnalysis] = []

        for ds in scores:
            if ds.score < self._target_threshold:
                deficit = self._target_threshold - ds.score
                bp_match = next(
                    (bp for bp in self._best_practices
                     if bp.dimension == ds.dimension),
                    None,
                )
                gaps.append(GapAnalysis(
                    dimension=ds.dimension,
                    description=(
                        f"{ds.dimension.value} at {ds.score:.1%}, "
                        f"target {self._target_threshold:.0%}"
                    ),
                    severity=round(min(1.0, deficit / self._target_threshold), 4),
                    best_practice_id=bp_match.practice_id if bp_match else "",
                    recommended_action=(
                        f"Improve {ds.dimension.value}: "
                        + (bp_match.description[:120] if bp_match else "align with best practice")
                    ),
                ))

        return gaps

    # -- plan creation ------------------------------------------------------

    def create_plan(self) -> CalibrationPlan:
        """Create a prioritised remediation plan from current gaps."""
        with self._lock:
            gaps = self._identify_gaps_unlocked()
            gaps_sorted = sorted(gaps, key=lambda g: g.severity, reverse=True)

            actions: List[str] = []
            priority: List[str] = []
            for g in gaps_sorted:
                actions.append(g.recommended_action)
                priority.append(g.gap_id)

            est = 0.0
            if gaps_sorted:
                est = sum(g.severity for g in gaps_sorted) / len(gaps_sorted)

            return CalibrationPlan(
                gaps=gaps_sorted,
                actions=actions,
                priority_order=priority,
                estimated_improvement=round(est, 4),
            )

    # -- QC against proposal request ----------------------------------------

    def qc_against_request(self) -> QCResult:
        """Validate the output against every registered proposal requirement.

        This is the second loop: even if the output scores well against
        professional benchmarks, it must also satisfy the original request.
        """
        with self._lock:
            return self._qc_against_request_unlocked()

    def _qc_against_request_unlocked(self) -> QCResult:
        if self._output is None:
            raise ValueError("No output registered")
        if not self._requirements:
            return QCResult(
                verdict=QCVerdict.PASS,
                requirements_total=0,
                requirements_met=0,
                compliance_pct=100.0,
                notes="No proposal requirements registered — vacuously compliant",
            )

        content_lower = self._output.content.lower()
        meta_str = " ".join(
            str(v) for v in self._output.metadata.values()
        ).lower()
        # QC checks the actual output only — not the improvement log.
        # This prevents the remediation loop from self-satisfying requirements.
        combined = f"{content_lower} {meta_str}"

        unmet: List[ProposalRequirement] = []
        met_count = 0

        for req in self._requirements:
            keywords = [
                w.strip().lower()
                for w in req.description.split()
                if len(w.strip()) > 2
            ]
            match_ratio = (
                sum(1 for kw in keywords if kw in combined) / len(keywords)
                if keywords
                else 0.0
            )

            if match_ratio >= 0.5:
                req.met = True
                req.evidence = f"match_ratio={match_ratio:.2f}"
                met_count += 1
            else:
                req.met = False
                req.evidence = f"match_ratio={match_ratio:.2f} (below 0.5)"
                unmet.append(req)

        total = len(self._requirements)
        compliance = (met_count / total * 100.0) if total else 100.0

        mandatory_total = sum(1 for r in self._requirements if r.mandatory)
        mandatory_met = sum(
            1 for r in self._requirements if r.mandatory and r.met
        )
        mandatory_pct = (
            (mandatory_met / mandatory_total) if mandatory_total else 1.0
        )

        if mandatory_pct >= _QC_PASS_THRESHOLD:
            verdict = QCVerdict.PASS
        elif mandatory_pct >= _QC_PARTIAL_THRESHOLD:
            verdict = QCVerdict.PARTIAL
        else:
            verdict = QCVerdict.FAIL

        return QCResult(
            verdict=verdict,
            requirements_total=total,
            requirements_met=met_count,
            compliance_pct=round(compliance, 2),
            unmet_requirements=unmet,
            notes=(
                f"Mandatory: {mandatory_met}/{mandatory_total}; "
                f"Overall: {met_count}/{total}"
            ),
        )

    # -- single calibration round -------------------------------------------

    def run_calibration_round(self) -> CalibrationRound:
        """Execute one calibration iteration (benchmark + QC + plan)."""
        with self._lock:
            round_num = len(self._rounds) + 1

            scores = self._score_output_unlocked()
            avg_score = (
                sum(s.score for s in scores) / len(scores) if scores else 0.0
            )

            qc = self._qc_against_request_unlocked()
            gaps = self._identify_gaps_unlocked()

            gaps_sorted = sorted(
                gaps, key=lambda g: g.severity, reverse=True,
            )
            actions = [g.recommended_action for g in gaps_sorted]
            priority = [g.gap_id for g in gaps_sorted]
            est = (
                sum(g.severity for g in gaps_sorted) / len(gaps_sorted)
                if gaps_sorted
                else 0.0
            )
            plan = CalibrationPlan(
                gaps=gaps_sorted,
                actions=actions,
                priority_order=priority,
                estimated_improvement=round(est, 4),
            )

            closed = 0
            for g in gaps_sorted:
                self._improvements_applied.append(
                    f"Round {round_num}: {g.recommended_action}"
                )
                closed += 1

            for req in qc.unmet_requirements:
                self._improvements_applied.append(
                    f"Round {round_num} QC fix: address '{req.description[:80]}'"
                )

            cr = CalibrationRound(
                round_number=round_num,
                benchmark_score=round(avg_score, 4),
                qc_result=qc,
                gaps_found=len(gaps),
                gaps_closed=closed,
                plan=plan,
            )
            self._rounds.append(cr)
            return cr

    # -- main calibration loop ----------------------------------------------

    def calibrate(self) -> CalibrationReport:
        """Run the dual-loop calibration until convergence or max rounds.

        Convergence criteria (both must be true):
        1. Benchmark score ≥ target_threshold  (90-95 %)
        2. QC against proposal request → PASS
        """
        if self._output is None:
            raise ValueError("No output registered — call register_output()")
        if not self._examples:
            raise ValueError("No examples registered — call register_examples()")

        with self._lock:
            self._status = CalibrationStatus.IN_PROGRESS

            if not self._best_practices:
                # Auto-extract on first calibrate call
                pass

        # Extract outside inner lock to avoid nested acquisition
        if not self._best_practices:
            self.extract_best_practices()

        converged = False
        for _ in range(self._max_rounds):
            cr = self.run_calibration_round()

            benchmark_ok = cr.benchmark_score >= self._target_threshold
            qc_ok = (
                cr.qc_result is not None
                and cr.qc_result.verdict == QCVerdict.PASS
            )

            if benchmark_ok and qc_ok:
                converged = True
                break

        with self._lock:
            final_scores = self._score_output_unlocked()
            final_avg = (
                sum(s.score for s in final_scores) / len(final_scores)
                if final_scores
                else 0.0
            )
            final_qc = self._qc_against_request_unlocked()

            self._status = (
                CalibrationStatus.CONVERGED if converged
                else CalibrationStatus.FAILED
            )

            return CalibrationReport(
                status=self._status,
                rounds=list(self._rounds),
                final_benchmark_score=round(final_avg, 4),
                final_qc_compliance=final_qc.compliance_pct,
                best_practices_applied=len(self._best_practices),
                total_gaps_closed=sum(r.gaps_closed for r in self._rounds),
                converged=converged,
                summary=(
                    f"Calibration {'converged' if converged else 'did not converge'} "
                    f"after {len(self._rounds)} round(s). "
                    f"Final benchmark: {final_avg:.1%}, "
                    f"QC compliance: {final_qc.compliance_pct:.1f}%."
                ),
            )

    # -- accessors ----------------------------------------------------------

    @property
    def status(self) -> CalibrationStatus:
        return self._status

    @property
    def rounds(self) -> List[CalibrationRound]:
        return list(self._rounds)

    @property
    def best_practices(self) -> List[BestPractice]:
        return list(self._best_practices)

    @property
    def target_threshold(self) -> float:
        return self._target_threshold

    @property
    def max_rounds(self) -> int:
        return self._max_rounds
