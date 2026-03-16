"""
Response Composer
Controlled generation within verified bounds using templates
NO LLM calls - pure template-based responses
"""

import logging
import os
from typing import Optional

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
