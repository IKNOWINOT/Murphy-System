"""
Semantics Boundary Controller for Murphy System Runtime

Runtime orchestration wrappers for semantics boundary control-loop
integration (Section 12 Step 6.8), providing:
- Belief-state hypothesis management with Bayesian prior/posterior updates
- Expected loss and CVaR risk assessment for decision-making under uncertainty
- RVoI-driven clarifying question generation and ranking
- Invariance commutativity checks for safety verification
- Verification-feedback loops with failure routing to planning
- Thread-safe in-memory persistence
"""

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
# Enums
# ---------------------------------------------------------------------------

class VerificationOutcomeStatus(str, Enum):
    """Possible outcomes for a verification check."""
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class EvidenceDirection(str, Enum):
    """Direction of evidence relative to a hypothesis."""
    SUPPORTING = "supporting"
    OPPOSING = "opposing"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BeliefState:
    """Tracked belief state for a single hypothesis."""
    hypothesis_id: str
    description: str
    prior: float
    posterior: float
    evidence_count: int = 0
    confidence: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskAssessment:
    """Result of a loss/risk computation."""
    scenario_id: str
    expected_loss: float
    cvar_95: float
    cvar_99: float
    samples: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ClarifyingQuestion:
    """An RVoI-driven clarifying question."""
    question_id: str
    question: str
    target_hypothesis: str
    estimated_info_gain: float
    asked: bool = False
    answered: bool = False
    answer: Optional[str] = None


@dataclass
class InvarianceCheck:
    """Record of an invariance/commutativity check between two operations."""
    check_id: str
    operation_a: str
    operation_b: str
    commutative: Optional[bool] = None
    verified: bool = False
    discrepancy: float = 0.0


@dataclass
class VerificationOutcome:
    """Outcome of a single verification run."""
    verification_id: str
    task_id: str
    outcome: VerificationOutcomeStatus
    details: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    feedback_routed: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp *value* between *lo* and *hi*."""
    return max(lo, min(hi, value))


def _bayesian_update(prior: float, likelihood_ratio: float) -> float:
    """Apply a single Bayesian update given a likelihood ratio."""
    if prior <= 0.0 or prior >= 1.0:
        return _clamp(prior)
    posterior_odds = (prior / (1.0 - prior)) * likelihood_ratio
    posterior = posterior_odds / (1.0 + posterior_odds)
    return _clamp(posterior)


def _confidence_from_evidence(evidence_count: int, prior: float, posterior: float) -> float:
    """Heuristic confidence score combining evidence volume and belief shift."""
    volume_factor = 1.0 - math.exp(-0.3 * evidence_count)
    shift_factor = abs(posterior - 0.5) * 2.0
    return _clamp(0.4 * volume_factor + 0.6 * shift_factor)


def _compute_cvar(sorted_values: List[float], alpha: float) -> float:
    """Compute CVaR (expected shortfall) at level *alpha* from sorted losses."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    cutoff = max(1, int(math.ceil(n * alpha)))
    tail = sorted_values[-cutoff:]
    return sum(tail) / (len(tail) or 1)


# ---------------------------------------------------------------------------
# Question templates for RVoI generation
# ---------------------------------------------------------------------------

_QUESTION_TEMPLATES: List[str] = [
    "What additional evidence would confirm or refute '{hypothesis}'?",
    "Are there known failure modes related to '{hypothesis}'?",
    "What is the expected impact if '{hypothesis}' is false?",
    "Can '{hypothesis}' be independently verified?",
    "What assumptions does '{hypothesis}' depend on?",
]


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------

class SemanticsBoundaryController:
    """Orchestrates semantics boundary control-loop integration.

    Ties together belief-state tracking, loss/risk computation,
    RVoI-driven clarification, invariance checks, and verification
    feedback loops for the Murphy System runtime.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._beliefs: Dict[str, BeliefState] = {}
        self._risk_assessments: Dict[str, RiskAssessment] = {}
        self._questions: Dict[str, ClarifyingQuestion] = {}
        self._invariance_checks: Dict[str, InvarianceCheck] = {}
        self._verifications: List[VerificationOutcome] = []
        logger.info("SemanticsBoundaryController initialised")

    # --- Belief-state hypothesis management --------------------------------

    def create_hypothesis(self, description: str, prior: float = 0.5) -> BeliefState:
        """Create a new belief-state hypothesis with the given prior."""
        prior = _clamp(prior)
        hypothesis_id = str(uuid.uuid4())
        belief = BeliefState(
            hypothesis_id=hypothesis_id,
            description=description,
            prior=prior,
            posterior=prior,
            confidence=_confidence_from_evidence(0, prior, prior),
        )
        with self._lock:
            self._beliefs[hypothesis_id] = belief
        logger.info("Created hypothesis %s: %s (prior=%.3f)", hypothesis_id, description, prior)
        return belief

    def update_belief(
        self,
        hypothesis_id: str,
        evidence_strength: float,
        evidence_direction: str,
    ) -> BeliefState:
        """Apply a Bayesian update to an existing hypothesis.

        *evidence_strength* is a positive float indicating strength (0–∞).
        *evidence_direction* should be one of 'supporting', 'opposing', or 'neutral'.
        """
        direction = EvidenceDirection(evidence_direction)
        with self._lock:
            belief = self._beliefs.get(hypothesis_id)
            if belief is None:
                raise KeyError(f"Unknown hypothesis_id: {hypothesis_id}")

            lr = max(evidence_strength, 1e-12)
            if direction == EvidenceDirection.OPPOSING:
                lr = 1.0 / lr if lr != 0 else 1e12
            elif direction == EvidenceDirection.NEUTRAL:
                lr = 1.0

            belief.posterior = _bayesian_update(belief.posterior, lr)
            belief.evidence_count += 1
            belief.confidence = _confidence_from_evidence(
                belief.evidence_count, belief.prior, belief.posterior,
            )
            belief.last_updated = datetime.now(timezone.utc)

        logger.debug(
            "Updated hypothesis %s: posterior=%.4f confidence=%.4f",
            hypothesis_id, belief.posterior, belief.confidence,
        )
        return belief

    def get_belief_summary(self) -> Dict[str, Any]:
        """Return a summary of all tracked belief states."""
        with self._lock:
            beliefs = list(self._beliefs.values())
        return {
            "total_hypotheses": len(beliefs),
            "hypotheses": [
                {
                    "hypothesis_id": b.hypothesis_id,
                    "description": b.description,
                    "prior": b.prior,
                    "posterior": b.posterior,
                    "evidence_count": b.evidence_count,
                    "confidence": b.confidence,
                }
                for b in beliefs
            ],
        }

    # --- Loss / risk selection ---------------------------------------------

    def compute_expected_loss(
        self,
        scenario_id: str,
        probabilities: List[float],
        losses: List[float],
    ) -> RiskAssessment:
        """Compute expected loss for a scenario given parallel probability/loss vectors."""
        if len(probabilities) != len(losses):
            raise ValueError("probabilities and losses must have the same length")

        expected_loss = sum(p * l for p, l in zip(probabilities, losses))
        sorted_losses = sorted(losses)
        cvar_95 = _compute_cvar(sorted_losses, 0.05)
        cvar_99 = _compute_cvar(sorted_losses, 0.01)

        assessment = RiskAssessment(
            scenario_id=scenario_id,
            expected_loss=expected_loss,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            samples=len(losses),
        )
        with self._lock:
            self._risk_assessments[scenario_id] = assessment
        logger.info(
            "Risk assessment %s: E[loss]=%.4f CVaR95=%.4f CVaR99=%.4f",
            scenario_id, expected_loss, cvar_95, cvar_99,
        )
        return assessment

    def compute_cvar(
        self,
        scenario_id: str,
        values: List[float],
        alpha: float = 0.05,
    ) -> RiskAssessment:
        """Compute CVaR at the given alpha level from raw loss values."""
        if not values:
            raise ValueError("values must be non-empty")
        alpha = _clamp(alpha, 1e-6, 1.0)
        sorted_vals = sorted(values)
        expected_loss = sum(values) / len(values)
        cvar_95 = _compute_cvar(sorted_vals, 0.05)
        cvar_99 = _compute_cvar(sorted_vals, 0.01)

        assessment = RiskAssessment(
            scenario_id=scenario_id,
            expected_loss=expected_loss,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            samples=len(values),
        )
        with self._lock:
            self._risk_assessments[scenario_id] = assessment
        logger.info(
            "CVaR assessment %s (alpha=%.3f): E[loss]=%.4f CVaR95=%.4f CVaR99=%.4f",
            scenario_id, alpha, expected_loss, cvar_95, cvar_99,
        )
        return assessment

    # --- RVoI-driven clarifying questions ----------------------------------

    def generate_questions(
        self,
        task_description: str,
        hypotheses: Optional[List[str]] = None,
        max_questions: int = 5,
    ) -> List[ClarifyingQuestion]:
        """Generate ranked clarifying questions driven by RVoI heuristics."""
        with self._lock:
            if hypotheses is None:
                target_beliefs = list(self._beliefs.values())
            else:
                target_beliefs = [
                    self._beliefs[h] for h in hypotheses if h in self._beliefs
                ]

        generated: List[ClarifyingQuestion] = []
        for belief in target_beliefs:
            uncertainty = 1.0 - abs(belief.posterior - 0.5) * 2.0
            for template in _QUESTION_TEMPLATES:
                info_gain = uncertainty * (1.0 / (1.0 + belief.evidence_count))
                question = ClarifyingQuestion(
                    question_id=str(uuid.uuid4()),
                    question=template.format(hypothesis=belief.description),
                    target_hypothesis=belief.hypothesis_id,
                    estimated_info_gain=round(info_gain, 6),
                    asked=True,
                )
                generated.append(question)

        generated.sort(key=lambda q: q.estimated_info_gain, reverse=True)
        generated = generated[:max_questions]

        with self._lock:
            for q in generated:
                self._questions[q.question_id] = q

        logger.info("Generated %d clarifying questions for task: %s", len(generated), task_description)
        return generated

    def answer_question(self, question_id: str, answer: str) -> ClarifyingQuestion:
        """Record an answer for a previously generated clarifying question."""
        with self._lock:
            question = self._questions.get(question_id)
            if question is None:
                raise KeyError(f"Unknown question_id: {question_id}")
            question.answered = True
            question.answer = answer
        logger.debug("Answered question %s", question_id)
        return question

    def get_rvoi_rankings(self) -> List[Dict[str, Any]]:
        """Return unanswered questions ranked by estimated information gain."""
        with self._lock:
            unanswered = [
                q for q in self._questions.values() if not q.answered
            ]
        unanswered.sort(key=lambda q: q.estimated_info_gain, reverse=True)
        return [
            {
                "question_id": q.question_id,
                "question": q.question,
                "target_hypothesis": q.target_hypothesis,
                "estimated_info_gain": q.estimated_info_gain,
            }
            for q in unanswered
        ]

    # --- Invariance commutativity checks -----------------------------------

    def register_invariance_check(
        self,
        operation_a: str,
        operation_b: str,
    ) -> InvarianceCheck:
        """Register a pair of operations for commutativity verification."""
        check_id = str(uuid.uuid4())
        check = InvarianceCheck(
            check_id=check_id,
            operation_a=operation_a,
            operation_b=operation_b,
        )
        with self._lock:
            self._invariance_checks[check_id] = check
        logger.info("Registered invariance check %s: %s <-> %s", check_id, operation_a, operation_b)
        return check

    def verify_invariance(
        self,
        check_id: str,
        result_a: Any,
        result_b: Any,
        tolerance: float = 1e-9,
    ) -> InvarianceCheck:
        """Verify whether two operation results are equivalent within tolerance."""
        with self._lock:
            check = self._invariance_checks.get(check_id)
            if check is None:
                raise KeyError(f"Unknown check_id: {check_id}")

            try:
                diff = abs(float(result_a) - float(result_b))
                commutative = diff <= tolerance
                check.discrepancy = diff
            except (TypeError, ValueError):
                commutative = result_a == result_b
                check.discrepancy = 0.0 if commutative else 1.0

            check.commutative = commutative
            check.verified = True

        logger.info(
            "Invariance check %s: commutative=%s discrepancy=%.12f",
            check_id, commutative, check.discrepancy,
        )
        return check

    # --- Verification-feedback loops ---------------------------------------

    def record_verification(
        self,
        task_id: str,
        outcome: str,
        details: str = "",
    ) -> VerificationOutcome:
        """Record the outcome of a verification run."""
        status = VerificationOutcomeStatus(outcome)
        verification = VerificationOutcome(
            verification_id=str(uuid.uuid4()),
            task_id=task_id,
            outcome=status,
            details=details,
        )
        with self._lock:
            capped_append(self._verifications, verification)
        logger.info("Recorded verification %s for task %s: %s", verification.verification_id, task_id, outcome)
        return verification

    def route_failures_to_planning(self) -> List[Dict[str, Any]]:
        """Collect un-routed failures and mark them as routed.

        Returns a list of feedback items suitable for a planning subsystem.
        """
        routed: List[Dict[str, Any]] = []
        with self._lock:
            for v in self._verifications:
                if v.outcome == VerificationOutcomeStatus.FAIL and not v.feedback_routed:
                    v.feedback_routed = True
                    routed.append({
                        "verification_id": v.verification_id,
                        "task_id": v.task_id,
                        "outcome": v.outcome.value,
                        "details": v.details,
                        "timestamp": v.timestamp.isoformat(),
                        "suggestion": f"Re-plan task {v.task_id}: {v.details}" if v.details else f"Re-plan task {v.task_id}",
                    })
        logger.info("Routed %d failure(s) to planning", len(routed))
        return routed

    def get_verification_history(
        self,
        task_id: Optional[str] = None,
    ) -> List[VerificationOutcome]:
        """Return verification history, optionally filtered by task_id."""
        with self._lock:
            if task_id is not None:
                return [v for v in self._verifications if v.task_id == task_id]
            return list(self._verifications)

    # --- Status ------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return an operational summary of the controller."""
        with self._lock:
            total_hypotheses = len(self._beliefs)
            total_risk_assessments = len(self._risk_assessments)
            total_questions = len(self._questions)
            answered_questions = sum(1 for q in self._questions.values() if q.answered)
            total_invariance_checks = len(self._invariance_checks)
            verified_invariance = sum(1 for c in self._invariance_checks.values() if c.verified)
            commutative_count = sum(
                1 for c in self._invariance_checks.values() if c.commutative is True
            )
            total_verifications = len(self._verifications)
            pass_count = sum(
                1 for v in self._verifications if v.outcome == VerificationOutcomeStatus.PASS
            )
            fail_count = sum(
                1 for v in self._verifications if v.outcome == VerificationOutcomeStatus.FAIL
            )
            inconclusive_count = sum(
                1 for v in self._verifications if v.outcome == VerificationOutcomeStatus.INCONCLUSIVE
            )
            unrouted_failures = sum(
                1 for v in self._verifications
                if v.outcome == VerificationOutcomeStatus.FAIL and not v.feedback_routed
            )

        return {
            "total_hypotheses": total_hypotheses,
            "total_risk_assessments": total_risk_assessments,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "total_invariance_checks": total_invariance_checks,
            "verified_invariance": verified_invariance,
            "commutative_count": commutative_count,
            "total_verifications": total_verifications,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "inconclusive_count": inconclusive_count,
            "unrouted_failures": unrouted_failures,
            "controller_operational": True,
        }

    # --- Order Sensitivity Verification (Permutation Calibration) ----------

    def check_order_invariance(
        self,
        domain: str,
        ordering_a: List[str],
        result_a: float,
        ordering_b: List[str],
        result_b: float,
        tolerance: float = 0.05,
    ) -> Dict[str, Any]:
        """Check if results are invariant to ordering changes.

        This implements spec Section 3.7: Test whether outputs are invariant
        or order-sensitive, distinguish real signal from sequencing artifacts.

        Args:
            domain: Domain being tested
            ordering_a: First ordering sequence
            result_a: Result from first ordering
            ordering_b: Second ordering sequence
            result_b: Result from second ordering
            tolerance: Acceptable difference threshold

        Returns:
            Analysis result with invariance classification
        """
        difference = abs(result_a - result_b)
        is_invariant = difference <= tolerance

        # Classify the relationship
        if is_invariant:
            classification = "invariant"
            signal = "none"
        elif difference <= tolerance * 2:
            classification = "weakly_sensitive"
            signal = "possible_artifact"
        elif difference <= tolerance * 5:
            classification = "moderately_sensitive"
            signal = "likely_real"
        else:
            classification = "highly_sensitive"
            signal = "strong_path_dependence"

        # Register as invariance check
        check_id = str(uuid.uuid4())
        check = InvarianceCheck(
            check_id=check_id,
            operation_a=str(ordering_a),
            operation_b=str(ordering_b),
            commutative=is_invariant,
            verified=True,
            discrepancy=difference,
        )

        with self._lock:
            self._invariance_checks[check_id] = check

        logger.info(
            "Order invariance check for domain '%s': %s (diff=%.4f, tolerance=%.4f)",
            domain, classification, difference, tolerance
        )

        return {
            "check_id": check_id,
            "domain": domain,
            "ordering_a": ordering_a,
            "ordering_b": ordering_b,
            "result_a": result_a,
            "result_b": result_b,
            "difference": round(difference, 6),
            "tolerance": tolerance,
            "is_invariant": is_invariant,
            "classification": classification,
            "signal_type": signal,
            "recommendation": "no_action" if is_invariant else "investigate_ordering",
        }

    def classify_domain_sensitivity(
        self,
        domain: str,
        observations: List[Dict[str, Any]],
        min_samples: int = 10,
    ) -> Dict[str, Any]:
        """Classify domain as stable, sensitive, or fragile.

        This implements spec Section 3.7: Classify results as stable,
        sensitive, or fragile for belief-state stability checks.

        Args:
            domain: Domain to classify
            observations: List of {ordering, result} dicts
            min_samples: Minimum samples needed

        Returns:
            Classification result with recommendations
        """
        if len(observations) < min_samples:
            return {
                "status": "insufficient_data",
                "domain": domain,
                "samples": len(observations),
                "required": min_samples,
            }

        results = [o.get("result", 0.0) for o in observations]

        # Calculate statistics
        mean_result = sum(results) / len(results)
        variance = sum((r - mean_result) ** 2 for r in results) / (len(results) - 1)
        std_dev = variance ** 0.5

        # Calculate coefficient of variation
        cv = std_dev / abs(mean_result) if mean_result != 0 else 0.0

        # Classify based on variability
        if cv < 0.05:
            classification = "stable"
            overfitting_risk = "low"
            recommendation = "order_invariant"
        elif cv < 0.15:
            classification = "sensitive"
            overfitting_risk = "moderate"
            recommendation = "monitor_ordering"
        elif cv < 0.3:
            classification = "fragile"
            overfitting_risk = "high"
            recommendation = "carefully_select_ordering"
        else:
            classification = "highly_fragile"
            overfitting_risk = "critical"
            recommendation = "review_fundamental_approach"

        # Create hypothesis for tracking
        hypothesis_desc = f"Domain '{domain}' is order-{classification}"
        hypothesis = self.create_hypothesis(hypothesis_desc, prior=0.5)

        # Update belief based on variance
        if cv < 0.1:
            self.update_belief(hypothesis.hypothesis_id, 2.0, "supporting")
        elif cv > 0.2:
            self.update_belief(hypothesis.hypothesis_id, 0.5, "opposing")

        return {
            "status": "ok",
            "domain": domain,
            "samples": len(observations),
            "mean_result": round(mean_result, 4),
            "std_deviation": round(std_dev, 4),
            "coefficient_of_variation": round(cv, 4),
            "classification": classification,
            "overfitting_risk": overfitting_risk,
            "recommendation": recommendation,
            "hypothesis_id": hypothesis.hypothesis_id,
        }

    def get_order_invariance_summary(self) -> Dict[str, Any]:
        """Get summary of order invariance checks.

        Returns:
            Summary statistics for order invariance verification
        """
        with self._lock:
            checks = list(self._invariance_checks.values())

        if not checks:
            return {
                "total_checks": 0,
                "invariant_count": 0,
                "sensitive_count": 0,
                "invariance_rate": 0.0,
            }

        verified = [c for c in checks if c.verified]
        invariant = [c for c in verified if c.commutative]
        sensitive = [c for c in verified if not c.commutative]

        avg_discrepancy = (
            sum(c.discrepancy for c in verified) / len(verified)
            if verified else 0.0
        )

        return {
            "total_checks": len(checks),
            "verified_checks": len(verified),
            "invariant_count": len(invariant),
            "sensitive_count": len(sensitive),
            "invariance_rate": round(len(invariant) / len(verified), 4) if verified else 0.0,
            "average_discrepancy": round(avg_discrepancy, 6),
        }
