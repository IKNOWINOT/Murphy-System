"""
State Machine and Core Enums
Deterministic control flow for the chatbot
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class State(Enum):
    """System states for authority gate"""
    HALT = 0
    CLARIFY = 1
    PROCEED = 2
    VERIFY = 3
    ERROR = 4


class QuestionType(Enum):
    """Types of questions the system can handle"""
    FACTUAL_LOOKUP = "factual_lookup"
    CALCULATION = "calculation"
    COMPARISON = "comparison"
    DEFINITION = "definition"
    PROCEDURAL = "procedural"
    UNKNOWN = "unknown"


@dataclass
class Hypothesis:
    """
    Probabilistic hypothesis from LLM
    Not trusted until verified
    """
    question_type: QuestionType
    entities: list[str]
    confidence: float
    unknowns: list[str]
    intent: str
    parameters: dict

    def is_confident(self, threshold: float = 0.80) -> bool:
        """Check if confidence exceeds threshold"""
        return self.confidence >= threshold

    def has_unknowns(self) -> bool:
        """Check if there are unresolved unknowns"""
        return len(self.unknowns) > 0


@dataclass
class VerifiedFacts:
    """
    Deterministically verified information
    This is the source of truth
    """
    entity: str
    facts: dict
    sources: list[str]
    verified: bool
    verification_method: str
    timestamp: str

    def is_valid(self) -> bool:
        """Check if facts are verified and non-empty"""
        return self.verified and bool(self.facts)


@dataclass
class SystemResponse:
    """
    Final system response with metadata
    """
    state: State
    message: str
    facts: Optional[VerifiedFacts]
    confidence: float
    reasoning: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "state": self.state.name,
            "message": self.message,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "verified": self.facts.verified if self.facts else False
        }
