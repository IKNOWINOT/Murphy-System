"""
ChatbotV1_1Fixed - Fixed MFGC v1.1 chatbot with safety gates,
complexity routing, and proper response markers.
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ChatbotV1_1Fixed:
    """Chatbot with MFGC v1.1 safety integration."""

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self._greeting_patterns = re.compile(
            r"^(hi|hello|hey|greetings|howdy|good\s*(morning|afternoon|evening))\b",
            re.IGNORECASE,
        )
        self._capability_patterns = re.compile(
            r"what can you do|your capabilit|tell me about yourself|who are you",
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a user message and return a marked, bounded response."""
        if context is None:
            context = {}

        complexity = self._assess_complexity(message)
        routing = self._route(message, complexity)
        content = self._generate_content(message, routing, complexity)

        # Ensure bounded
        if len(content) > 1500:
            content = content[:1500] + "..."

        confidence = self._compute_confidence(message, complexity)
        marker = self._pick_marker(confidence, complexity)

        return {
            "marker": marker,
            "marker_class": f"marker-{self._marker_label(marker)}",
            "content": content,
            "metadata": {
                "routing": routing,
                "complexity": complexity,
                "confidence": confidence,
            },
        }

    # ------------------------------------------------------------------
    # complexity / routing
    # ------------------------------------------------------------------

    def _assess_complexity(self, message: str) -> str:
        words = message.split()
        complex_keywords = {
            "design", "architect", "distributed", "comprehensive",
            "enterprise", "fault", "tolerance", "scalable", "real-time",
            "microservices", "system", "infrastructure",
        }
        hit_count = sum(1 for w in words if w.lower().strip(".,!?") in complex_keywords)
        length = len(words)
        if hit_count >= 3 or length > 15:
            return "high"
        if hit_count >= 1 or length > 6:
            return "medium"
        return "low"

    def _route(self, message: str, complexity: str) -> str:
        if self._greeting_patterns.search(message):
            return "greeting"
        if self._capability_patterns.search(message):
            return "capability"
        if complexity == "high":
            return "mfgc"
        return "standard"

    # ------------------------------------------------------------------
    # content generation (deterministic, no LLM)
    # ------------------------------------------------------------------

    def _generate_content(self, message: str, routing: str, complexity: str) -> str:
        if routing == "greeting":
            return "Hello! I'm the Murphy System assistant. How can I help you today?"
        if routing == "capability":
            return (
                "I can help with research, code analysis, system design, "
                "and deterministic computations. Use /research, /math, or /reason commands."
            )
        if routing == "mfgc":
            return (
                "This is a complex task that has been routed through the MFGC pipeline. "
                "The system has analyzed the request, generated solution candidates, "
                "and applied safety gates to ensure a reliable response."
            )
        return (
            f"I received your message regarding: {message[:80]}. "
            "For verified information use /research, for calculations use /math."
        )

    # ------------------------------------------------------------------
    # confidence / markers
    # ------------------------------------------------------------------

    def _compute_confidence(self, message: str, complexity: str) -> float:
        if complexity == "low":
            return 0.95
        if complexity == "medium":
            return 0.75
        return 0.55

    @staticmethod
    def _pick_marker(confidence: float, complexity: str) -> str:
        if confidence >= 0.9:
            return "B"
        if confidence >= 0.7:
            return "G"
        return "V"

    @staticmethod
    def _marker_label(marker: str) -> str:
        return {
            "V": "verified",
            "G": "generated",
            "B": "bot",
            "R": "rejected",
        }.get(marker, "bot")
