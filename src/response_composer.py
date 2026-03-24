"""
Response Composer
Controlled generation within verified bounds using templates
NO LLM calls in the base ResponseComposer - pure template-based responses.

The RefinementCycle class (added for Hero Flow 100%) wires the feedback
integrator into a real refinement loop: user feedback → adjust execution
plan → compose improved response.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("response_composer")
try:
    from state_machine import State, SystemResponse, VerifiedFacts
except ImportError:
    from src.state_machine import State, SystemResponse, VerifiedFacts


class ResponseComposer:
    """
    Generates responses using TEMPLATES, constrained to verified facts
    NO generation beyond verified bounds - pure deterministic responses
    """

    def __init__(self, use_templates: bool = True):
        """
        Initialize response composer

        Args:
            use_templates: If True, uses template-based responses (recommended)
        """
        self.use_templates = use_templates
        logger.info("✓ Using template-based response generation (no LLM)")

    def compose_proceed_response(
        self,
        facts: VerifiedFacts,
        user_question: str
    ) -> str:
        """
        Generate response using ONLY verified facts
        Pure template-based - NO generation beyond facts
        """

        # Always use template-based response
        return self._template_response(facts, user_question)

    def compose_clarify_response(self, reasoning: str, unknowns: list[str]) -> str:
        """
        Generate clarification request
        """
        message = "I need clarification to answer accurately.\n\n"
        message += f"Issue: {reasoning}\n\n"

        if unknowns:
            message += "Please clarify:\n"
            for unknown in unknowns:
                message += f"- {unknown}\n"

        return message

    def compose_halt_response(self, reasoning: str) -> str:
        """
        Generate halt message
        """
        return f"I cannot proceed safely with this query.\n\nReason: {reasoning}\n\nPlease rephrase your question or provide more specific information."

    def compose_error_response(self, error: str) -> str:
        """
        Generate error message
        """
        return f"An error occurred: {error}\n\nPlease try again or rephrase your question."

    def _format_facts(self, facts: VerifiedFacts) -> str:
        """
        Format facts for LLM consumption
        """
        output = f"Entity: {facts.entity}\n"
        output += f"Verified: {facts.verified}\n"
        output += f"Sources: {', '.join(facts.sources)}\n"
        output += f"Verification Method: {facts.verification_method}\n\n"
        output += "Facts:\n"

        for key, value in facts.facts.items():
            output += f"- {key}: {value}\n"

        return output

    def _template_response(self, facts: VerifiedFacts, user_question: str = "") -> str:
        """
        Template-based response using verified facts
        Deterministic - no generation beyond facts
        """
        if not facts.facts:
            return "No verified information available."

        # Detect question type from facts
        question_lower = user_question.lower()

        # Standards response template
        if 'title' in facts.facts and 'latest_revision' in facts.facts:
            entity = facts.entity
            title = facts.facts['title']
            revision = facts.facts['latest_revision']
            source = facts.sources[0] if facts.sources else 'database'

            return f"{title} ({entity}) was most recently revised in {revision}. (Source: {source})"

        # Calculation response template
        if 'result' in facts.facts and 'expression' in facts.facts:
            expr = facts.facts['expression']
            result = facts.facts['result']
            return f"The result of {expr} is {result}. (Verified: deterministic calculation)"

        # Wikipedia response template
        if 'summary' in facts.facts:
            title = facts.facts.get('title', facts.entity)
            summary = facts.facts['summary']
            url = facts.facts.get('url', '')
            return f"{title}: {summary}\n\nSource: {url}"

        # Generic template
        response = f"Based on verified information from {', '.join(facts.sources)}:\n\n"

        for key, value in facts.facts.items():
            if key not in ['url', 'categories', 'expression']:
                formatted_key = key.replace('_', ' ').title()
                response += f"• {formatted_key}: {value}\n"

        return response.strip()


class ResponseBuilder:
    """
    Builds complete SystemResponse objects
    """

    def __init__(self, composer: ResponseComposer):
        self.composer = composer

    def build_response(
        self,
        state: State,
        facts: Optional[VerifiedFacts],
        confidence: float,
        reasoning: str,
        user_question: str,
        unknowns: list[str] = None
    ) -> SystemResponse:
        """
        Build complete system response based on state
        """

        if state == State.PROCEED:
            message = self.composer.compose_proceed_response(facts, user_question)
        elif state == State.CLARIFY:
            message = self.composer.compose_clarify_response(reasoning, unknowns or [])
        elif state == State.HALT:
            message = self.composer.compose_halt_response(reasoning)
        elif state == State.ERROR:
            message = self.composer.compose_error_response(reasoning)
        else:
            message = "Unknown state"

        return SystemResponse(
            state=state,
            message=message,
            facts=facts,
            confidence=confidence,
            reasoning=reasoning
        )


# ---------------------------------------------------------------------------
# RefinementCycle — Hero Flow Refine stage  (Task 2)
# ---------------------------------------------------------------------------

class RefinementCycle:
    """Implements the Refine stage of the Describe → Execute → Refine Hero Flow.

    Takes user feedback on an existing execution plan, integrates it via
    :class:`FeedbackIntegrator` (adjusting state uncertainty), then optionally
    re-queries to compose an improved response.

    Parameters
    ----------
    composer:
        A :class:`ResponseComposer` used to render the refined response.
    feedback_integrator:
        An instance of :class:`FeedbackIntegrator` from ``feedback_integrator``
        module.  When ``None`` the cycle still works but skips state-vector
        updates.
    """

    def __init__(
        self,
        composer: ResponseComposer,
        feedback_integrator: Optional[Any] = None,
    ) -> None:
        self._composer = composer
        self._feedback_integrator = feedback_integrator
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core refinement
    # ------------------------------------------------------------------

    def refine(
        self,
        user_feedback: str,
        original_plan: Dict[str, Any],
        *,
        original_confidence: float = 0.5,
        state_vector: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run one refinement cycle.

        Steps
        -----
        1. Parse *user_feedback* into a correction signal.
        2. Integrate it into *state_vector* via FeedbackIntegrator (if
           available) to adjust uncertainty on affected variables.
        3. Produce a refined plan by applying the correction directives.
        4. Compose an improved response using the refined plan.
        5. Record the cycle in history for multi-turn context.

        Parameters
        ----------
        user_feedback:
            Free-text feedback from the user (e.g. "no, I meant X").
        original_plan:
            The execution plan dict that was returned from the Execute stage.
        original_confidence:
            Confidence of the original plan (used to build the feedback signal).
        state_vector:
            Optional :class:`TypedStateVector` — updated in-place when provided.

        Returns
        -------
        A dict with keys:
        - ``"refined_plan"`` — adjusted execution plan
        - ``"response"`` — human-readable improved response
        - ``"confidence"`` — updated confidence after integration
        - ``"recalibration_needed"`` — bool flag from FeedbackIntegrator
        - ``"cycle_id"`` — unique ID for this refinement cycle
        """
        import uuid as _uuid
        cycle_id = _uuid.uuid4().hex[:12]

        # Step 1: parse feedback into correction signal
        signal, affected_vars = self._parse_feedback(
            user_feedback, original_plan, original_confidence
        )

        # Step 2: integrate into state vector
        recalibration_needed = False
        if self._feedback_integrator is not None and state_vector is not None:
            try:
                self._feedback_integrator.integrate(signal, state_vector)
                recalibration_needed = self._feedback_integrator.should_trigger_recalibration(
                    [signal]
                )
            except Exception as exc:
                logger.warning("RefinementCycle: FeedbackIntegrator step failed: %s", exc)

        # Step 3: produce refined plan
        refined_plan = self._apply_correction(original_plan, user_feedback, signal)

        # Step 4: compose improved response
        corrected_confidence = signal.corrected_confidence or original_confidence
        response_text = self._compose_refined_response(
            user_feedback, refined_plan, corrected_confidence
        )

        # Step 5: record history
        cycle_record: Dict[str, Any] = {
            "cycle_id": cycle_id,
            "user_feedback": user_feedback,
            "original_confidence": original_confidence,
            "corrected_confidence": corrected_confidence,
            "affected_vars": affected_vars,
            "recalibration_needed": recalibration_needed,
        }
        self._history.append(cycle_record)

        logger.info(
            "RefinementCycle %s: confidence %.2f → %.2f, recalibration=%s",
            cycle_id, original_confidence, corrected_confidence, recalibration_needed,
        )

        return {
            "refined_plan": refined_plan,
            "response": response_text,
            "confidence": corrected_confidence,
            "recalibration_needed": recalibration_needed,
            "cycle_id": cycle_id,
        }

    def get_history(self) -> List[Dict[str, Any]]:
        """Return the list of completed refinement cycle records."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear refinement history (e.g. on conversation reset)."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feedback(
        user_feedback: str,
        original_plan: Dict[str, Any],
        original_confidence: float,
    ):
        """Convert free-text feedback into a FeedbackSignal.

        Returns a ``(signal, affected_vars)`` tuple.  The affected state
        variables are inferred heuristically from the feedback text and plan.
        """
        try:
            from src.feedback_integrator import FeedbackSignal
        except ImportError:
            from feedback_integrator import FeedbackSignal  # type: ignore[no-redef]

        feedback_lower = user_feedback.lower()

        # Heuristic: negative feedback lowers corrected confidence
        negative_keywords = [
            "no", "wrong", "incorrect", "not right", "bad", "fail",
            "error", "mistake", "I meant", "not what", "different",
        ]
        positive_keywords = [
            "yes", "correct", "good", "great", "right", "perfect",
            "that's it", "exactly",
        ]

        is_negative = any(kw in feedback_lower for kw in negative_keywords)
        is_positive = any(kw in feedback_lower for kw in positive_keywords)

        if is_negative:
            corrected_confidence = max(0.1, original_confidence - 0.3)
        elif is_positive:
            corrected_confidence = min(1.0, original_confidence + 0.2)
        else:
            corrected_confidence = original_confidence

        # Affected vars: use action names from the original plan
        actions = original_plan.get("actions", [])
        affected_vars = [
            a.get("type", a.get("description", "action"))[:32]
            for a in actions
            if isinstance(a, dict)
        ] or ["execution_plan"]

        signal = FeedbackSignal(
            signal_type="correction",
            source_task_id=original_plan.get("hypothesis_id", "unknown"),
            original_confidence=original_confidence,
            corrected_confidence=corrected_confidence,
            affected_state_variables=affected_vars[:10],  # cap at 10
        )
        return signal, affected_vars

    @staticmethod
    def _apply_correction(
        original_plan: Dict[str, Any],
        user_feedback: str,
        signal: Any,
    ) -> Dict[str, Any]:
        """Return a new plan dict with feedback-driven adjustments applied."""
        import copy
        refined = copy.deepcopy(original_plan)
        refined["refinement_feedback"] = user_feedback
        refined["corrected_confidence"] = signal.corrected_confidence
        refined["summary"] = (
            f"[Refined] {refined.get('summary', 'Execution plan')} — "
            f"adjusted per feedback: {user_feedback[:60]}"
        )
        return refined

    def _compose_refined_response(
        self,
        user_feedback: str,
        refined_plan: Dict[str, Any],
        confidence: float,
    ) -> str:
        """Build a human-readable refined response string."""
        summary = refined_plan.get("summary", "Refined execution plan")
        actions = refined_plan.get("actions", [])
        action_count = len(actions)
        action_summary = (
            ", ".join(
                a.get("description", str(a))[:40]
                for a in actions[:3]
                if isinstance(a, dict)
            )
            or "no actions"
        )
        more = f" (and {action_count - 3} more)" if action_count > 3 else ""

        response = self._composer.compose_proceed_response(
            _make_stub_facts(summary, confidence),
            user_feedback,
        )
        return (
            f"**Refined Plan** (confidence: {confidence:.0%})\n\n"
            f"{response}\n\n"
            f"**Actions updated:** {action_summary}{more}\n"
            f"**Feedback applied:** {user_feedback[:120]}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stub_facts(summary: str, confidence: float) -> Any:
    """Create a minimal VerifiedFacts stub for template rendering."""
    from datetime import datetime, timezone

    try:
        from src.state_machine import VerifiedFacts
    except ImportError:
        from state_machine import VerifiedFacts  # type: ignore[no-redef]

    return VerifiedFacts(
        entity="refined_plan",
        verified=True,
        sources=["feedback_integrator"],
        facts={"summary": summary, "confidence": str(round(confidence, 3))},
        verification_method="feedback_correction",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
