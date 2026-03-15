"""
Probabilistic Inference Layer
Uses LOCAL small models for intent detection and hypothesis generation
NO API calls - runs entirely locally
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("probabilistic_layer")
try:
    from state_machine import Hypothesis, QuestionType
except ImportError:
    from src.state_machine import Hypothesis, QuestionType
try:
    from local_model_layer import LocalModelParser, RuleBasedFallback
except ImportError:
    from src.local_model_layer import LocalModelParser, RuleBasedFallback


class IntentParser:
    """
    Parses user intent using LOCAL small model
    Output is probabilistic and NOT trusted - will be verified
    """

    def __init__(self, model_name: Optional[str] = None, use_local: bool = True):
        """
        Initialize with local Hugging Face model

        Args:
            model_name: Name of Hugging Face model to use
                       Options: "distilgpt2" (fast), "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "microsoft/phi-2"
            use_local: If True, uses local model. If False, uses pure rule-based fallback
        """
        self.use_local = use_local

        if use_local:
            model_name = model_name or os.getenv("LOCAL_MODEL", "distilgpt2")
            try:
                self.parser = LocalModelParser(model_name)
                logger.info(f"✓ Using local model: {model_name}")
            except Exception as exc:
                logger.info(f"⚠ Failed to load model, falling back to rules: {exc}")
                self.parser = None
                self.use_local = False
        else:
            self.parser = None
            logger.info("✓ Using pure rule-based parsing (no model)")

    def infer_intent(self, prompt: str) -> Hypothesis:
        """
        Analyze user prompt and generate hypothesis
        This is probabilistic - requires verification by architecture
        """

        try:
            if self.use_local and self.parser:
                # Use local model
                hypothesis = self.parser.infer_intent(prompt)
            else:
                # Use rule-based fallback
                hypothesis = RuleBasedFallback.parse_intent(prompt)

            return hypothesis

        except Exception as exc:
            # If parsing fails, return low-confidence hypothesis
            logger.info(f"⚠ Parsing failed: {exc}, using fallback")
            return RuleBasedFallback.parse_intent(prompt)


class HypothesisGenerator:
    """
    Generates multiple hypotheses for complex queries
    Allows exploration of different interpretations
    """

    def __init__(self, intent_parser: IntentParser):
        self.parser = intent_parser

    def generate_hypotheses(self, prompt: str, num_hypotheses: int = 3) -> list[Hypothesis]:
        """
        Generate multiple interpretations of the prompt
        Useful for ambiguous queries
        """
        hypotheses = []

        # Generate primary hypothesis
        primary = self.parser.infer_intent(prompt)
        hypotheses.append(primary)

        # For now, return single hypothesis
        # Can be extended to generate alternatives
        return hypotheses

    def select_best_hypothesis(self, hypotheses: list[Hypothesis]) -> Hypothesis:
        """
        Select hypothesis with highest confidence
        """
        if not hypotheses:
            return Hypothesis(
                question_type=QuestionType.UNKNOWN,
                entities=[],
                confidence=0.0,
                unknowns=["No hypotheses generated"],
                intent="",
                parameters={}
            )

        return max(hypotheses, key=lambda h: h.confidence)
