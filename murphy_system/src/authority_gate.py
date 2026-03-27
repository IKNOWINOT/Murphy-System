"""
Authority Gate - The Murphy Defense
Deterministic control logic that decides whether to proceed
"""

try:
    from state_machine import Hypothesis, QuestionType, State, VerifiedFacts
except ImportError:
    from src.state_machine import Hypothesis, QuestionType, State, VerifiedFacts
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class InvariantChecker:
    """
    Checks system invariants before allowing action
    This is where Murphy's Law is defeated
    """

    def __init__(
        self,
        min_confidence: float = 0.80,
        require_verification: bool = True
    ):
        self.min_confidence = min_confidence
        self.require_verification = require_verification

    def check(self, hypothesis: Hypothesis, facts: VerifiedFacts) -> Tuple[bool, list[str]]:
        """
        Check all invariants
        Returns (passed, list of violations)
        """
        violations = []

        # Invariant 1: Facts must be verified
        if self.require_verification and not facts.verified:
            violations.append("Facts not verified from external source")

        # Invariant 2: Confidence must exceed threshold
        if hypothesis.confidence < self.min_confidence:
            violations.append(
                f"Confidence {hypothesis.confidence:.2f} below threshold {self.min_confidence}"
            )

        # Invariant 3: No unresolved unknowns
        if hypothesis.has_unknowns():
            violations.append(
                f"Unresolved unknowns: {', '.join(hypothesis.unknowns)}"
            )

        # Invariant 4: Facts must be non-empty
        if not facts.facts:
            violations.append("No facts retrieved")

        # Invariant 5: Entity must match
        if facts.entity and hypothesis.entities:
            # Check if any hypothesis entity matches verified entity
            entity_match = any(
                entity.lower() in facts.entity.lower() or
                facts.entity.lower() in entity.lower()
                for entity in hypothesis.entities
            )
            if not entity_match:
                violations.append(
                    f"Entity mismatch: hypothesis={hypothesis.entities}, verified={facts.entity}"
                )

        passed = len(violations) == 0
        return passed, violations


class AuthorityGate:
    """
    The control gate that decides system state

    Law: If uncertainty propagates into authority, failure probability → 1
    Defense: If authority is gated by deterministic verification, failure is bounded
    """

    def __init__(
        self,
        min_confidence: float = 0.80,
        strict_mode: bool = True
    ):
        self.invariant_checker = InvariantChecker(
            min_confidence=min_confidence,
            require_verification=strict_mode
        )
        self.strict_mode = strict_mode

    def evaluate(
        self,
        hypothesis: Hypothesis,
        facts: VerifiedFacts
    ) -> Tuple[State, str]:
        """
        Evaluate whether to proceed, clarify, or halt

        Returns: (State, reasoning)
        """

        # Check if facts exist at all
        if facts is None:
            return State.CLARIFY, "No verification attempted"

        # Run invariant checks
        passed, violations = self.invariant_checker.check(hypothesis, facts)

        if passed:
            logger.info("All invariants passed - PROCEED")
            return State.PROCEED, "All invariants satisfied"

        # Analyze violations to determine state
        reasoning = "; ".join(violations)

        # Critical failures → HALT
        if "Facts not verified" in reasoning and self.strict_mode:
            logger.warning(f"HALT: {reasoning}")
            return State.HALT, reasoning

        # Resolvable issues → CLARIFY
        if any(keyword in reasoning for keyword in ["Confidence", "unknowns", "mismatch"]):
            logger.info(f"CLARIFY: {reasoning}")
            return State.CLARIFY, reasoning

        # Default to CLARIFY for safety
        logger.info(f"CLARIFY (default): {reasoning}")
        return State.CLARIFY, reasoning

    def can_proceed_with_partial(self, hypothesis: Hypothesis, facts: VerifiedFacts) -> bool:
        """
        Check if we can proceed with partial information
        Used for less critical queries
        """
        if not self.strict_mode:
            # In non-strict mode, allow proceeding with lower confidence
            return hypothesis.confidence > 0.6 and facts.verified

        return False


class MurphyDefense:
    """
    Formalized Murphy's Law defense mechanisms
    """

    @staticmethod
    def bound_uncertainty(hypothesis: Hypothesis) -> Hypothesis:
        """
        Explicitly bound uncertainty in hypothesis
        """
        # Cap confidence at reasonable maximum
        if hypothesis.confidence > 0.95:
            hypothesis.confidence = 0.95

        # Ensure unknowns are explicit
        if hypothesis.question_type == QuestionType.UNKNOWN:
            if "question type unclear" not in hypothesis.unknowns:
                hypothesis.unknowns.append("question type unclear")

        return hypothesis

    @staticmethod
    def verify_before_action(facts: VerifiedFacts) -> bool:
        """
        Ensure facts are verified before any action
        """
        return facts.verified and bool(facts.facts)

    @staticmethod
    def fail_safe(state: State) -> State:
        """
        If in doubt, fail to safe state (CLARIFY)
        """
        if state == State.ERROR:
            return State.CLARIFY
        return state

    @staticmethod
    def log_decision_trail(
        hypothesis: Hypothesis,
        facts: VerifiedFacts,
        state: State,
        reasoning: str
    ):
        """
        Log complete decision trail for auditability
        """
        logger.info("=== DECISION TRAIL ===")
        logger.info(f"Hypothesis: {hypothesis.intent}")
        logger.info(f"Confidence: {hypothesis.confidence:.2f}")
        logger.info(f"Verified: {facts.verified}")
        logger.info(f"State: {state.name}")
        logger.info(f"Reasoning: {reasoning}")
        logger.info("=====================")
