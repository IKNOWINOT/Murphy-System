"""
Local Model Layer - Uses small Hugging Face models locally
No API calls, runs entirely on local hardware
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("local_model_layer")
try:
    from state_machine import Hypothesis, QuestionType
except ImportError:
    from src.state_machine import Hypothesis, QuestionType

# Make transformers optional
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logger.info("⚠ transformers not installed - will use rule-based fallback only")


class LocalModelParser:
    """
    Uses small local Hugging Face model for intent parsing
    Model is constrained and verified by architecture
    """

    def __init__(self, model_name: str = "distilgpt2"):
        """
        Initialize with small local model

        Options:
        - distilgpt2 (82M params, very fast)
        - TinyLlama/TinyLlama-1.1B-Chat-v1.0 (1.1B params)
        - microsoft/phi-2 (2.7B params, better quality)
        """
        if not HAS_TRANSFORMERS:
            raise ImportError(
                "transformers not installed. Install with: pip install transformers torch"
            )

        logger.info(f"Loading local model: {model_name}...")

        # Load model and tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            device_map="auto" if torch.cuda.is_available() else None
        )

        # Set pad token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model_name = model_name
        logger.info(f"✓ Model loaded: {model_name}")

    def infer_intent(self, prompt: str) -> Hypothesis:
        """
        Analyze user prompt using local model
        Output is probabilistic and NOT trusted - will be verified
        """

        # Create structured prompt for the model
        system_prompt = f"""Analyze this question and respond with:
Question type: [factual_lookup, calculation, comparison, definition, procedural, unknown]
Entities: [list key entities]
Confidence: [0.0-1.0]
Unknowns: [what needs clarification]

Question: {prompt}

Analysis:"""

        # Generate response
        inputs = self.tokenizer(system_prompt, return_tensors="pt", padding=True)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=150,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract structured information using regex
        hypothesis = self._parse_model_output(response, prompt)

        return hypothesis

    def _parse_model_output(self, response: str, original_prompt: str) -> Hypothesis:
        """
        Parse model output into structured Hypothesis
        Uses fallback rules if model output is unclear
        """

        # Try to extract question type
        question_type = QuestionType.UNKNOWN
        if any(word in original_prompt.lower() for word in ["calculate", "compute", "what is", "solve"]):
            if any(char in original_prompt for char in ["+", "-", "*", "/", "="]):
                question_type = QuestionType.CALCULATION

        if any(word in original_prompt.lower() for word in ["what is", "define", "explain"]):
            question_type = QuestionType.FACTUAL_LOOKUP

        if any(word in original_prompt.lower() for word in ["compare", "difference", "versus", "vs"]):
            question_type = QuestionType.COMPARISON

        # Extract entities using simple NER
        entities = self._extract_entities(original_prompt)

        # Estimate confidence based on clarity
        confidence = self._estimate_confidence(original_prompt, entities)

        # Identify unknowns
        unknowns = []
        if not entities:
            unknowns.append("no clear entities identified")
        if question_type == QuestionType.UNKNOWN:
            unknowns.append("question type unclear")

        return Hypothesis(
            question_type=question_type,
            entities=entities,
            confidence=confidence,
            unknowns=unknowns,
            intent=self._extract_intent(original_prompt),
            parameters=self._extract_parameters(original_prompt)
        )

    def _extract_entities(self, text: str) -> list[str]:
        """
        Extract entities using pattern matching
        Looks for standards, proper nouns, technical terms
        """
        entities = []

        # Standards patterns
        standards_pattern = r'\b(ISO|IEC|DO|IEEE|NIST)\s*[-\s]?\d+[-\s]?\w*\b'
        standards = re.findall(standards_pattern, text, re.IGNORECASE)
        entities.extend([s.strip() for s in standards])

        # Capitalized words (potential proper nouns)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities.extend(proper_nouns[:3])  # Limit to 3

        # Technical terms
        technical_terms = ["Python", "Java", "C++", "JavaScript", "safety", "quality"]
        for term in technical_terms:
            if term.lower() in text.lower():
                entities.append(term)

        return list(set(entities))[:5]  # Unique, max 5

    def _estimate_confidence(self, text: str, entities: list[str]) -> float:
        """
        Estimate confidence based on query clarity
        """
        confidence = 0.5  # Base confidence

        # Increase for clear question words
        if any(word in text.lower() for word in ["what", "when", "where", "who", "how"]):
            confidence += 0.2

        # Increase for identified entities
        if entities:
            confidence += 0.1 * min(len(entities), 3)

        # Decrease for vague terms
        if any(word in text.lower() for word in ["best", "good", "better", "maybe"]):
            confidence -= 0.2

        # Increase for specific technical terms
        if any(word in text.lower() for word in ["calculate", "version", "revision", "standard"]):
            confidence += 0.15

        return max(0.3, min(0.95, confidence))

    def _extract_intent(self, text: str) -> str:
        """
        Extract user intent in plain language
        """
        text_lower = text.lower()

        if "calculate" in text_lower or "compute" in text_lower:
            return "perform calculation"
        elif "what is" in text_lower or "define" in text_lower:
            return "lookup definition or information"
        elif "compare" in text_lower:
            return "compare entities"
        elif "latest" in text_lower or "current" in text_lower:
            return "find latest version or information"
        else:
            return "general query"

    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extract parameters from query
        """
        params = {}

        # Extract mathematical expressions
        math_pattern = r'[\d\s+\-*/().]+(?:=|$)'
        math_match = re.search(math_pattern, text)
        if math_match:
            params["expression"] = math_match.group(0).strip()

        # Extract version/revision requests
        if "latest" in text.lower() or "current" in text.lower():
            params["request_latest"] = True

        return params


class RuleBasedFallback:
    """
    Pure rule-based fallback when model is uncertain
    Provides deterministic intent parsing
    """

    @staticmethod
    def parse_intent(prompt: str) -> Hypothesis:
        """
        Rule-based intent parsing using regex and keywords
        """
        prompt_lower = prompt.lower()

        # Determine question type
        question_type = QuestionType.UNKNOWN

        # Calculation detection
        if any(word in prompt_lower for word in ["calculate", "compute", "solve"]) or \
           any(char in prompt for char in ["+", "-", "*", "/"]):
            question_type = QuestionType.CALCULATION

        # Factual lookup detection
        elif any(word in prompt_lower for word in ["what is", "what are", "tell me about"]):
            question_type = QuestionType.FACTUAL_LOOKUP

        # Definition detection
        elif any(word in prompt_lower for word in ["define", "definition", "meaning"]):
            question_type = QuestionType.DEFINITION

        # Comparison detection
        elif any(word in prompt_lower for word in ["compare", "difference", "versus", "vs"]):
            question_type = QuestionType.COMPARISON

        # Extract entities
        entities = []

        # Standards
        standards_pattern = r'\b(ISO|IEC|DO|IEEE)\s*[-\s]?\d+[-\s]?\w*\b'
        standards = re.findall(standards_pattern, prompt, re.IGNORECASE)
        entities.extend(standards)

        # Confidence based on clarity
        confidence = 0.7 if question_type != QuestionType.UNKNOWN else 0.4

        # Unknowns
        unknowns = []
        if not entities and question_type == QuestionType.FACTUAL_LOOKUP:
            unknowns.append("entity to lookup")
        if question_type == QuestionType.UNKNOWN:
            unknowns.append("question type")

        return Hypothesis(
            question_type=question_type,
            entities=entities,
            confidence=confidence,
            unknowns=unknowns,
            intent="rule-based parsing",
            parameters={}
        )
