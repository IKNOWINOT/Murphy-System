"""
Chatbot v1.1 Fixed - Deterministic Safe Responses
"""

from __future__ import annotations

from typing import Dict, Any
from safe_llm_wrapper import SafeLLMWrapper, VerificationStatus


class ChatbotV1_1Fixed:
    """
    Minimal deterministic chatbot used by test suites.
    """

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self.wrapper = SafeLLMWrapper(None)

    def process_message(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        complexity = self._classify_complexity(message)
        marker = self._select_marker(complexity)
        content = self._generate_content(message, complexity)

        return {
            "marker": marker,
            "marker_class": f"marker-{marker}",
            "content": content,
            "metadata": {
                "routing": "mfgc" if complexity == "high" else "standard",
                "complexity": complexity,
                "confidence": 0.9 if complexity != "high" else 0.85,
            },
        }

    def _classify_complexity(self, message: str) -> str:
        message_lower = message.lower()
        if any(token in message_lower for token in ["design", "architecture", "distributed", "system"]):
            return "high"
        if len(message_lower.split()) > 6:
            return "medium"
        return "low"

    def _select_marker(self, complexity: str) -> str:
        if complexity == "high":
            return VerificationStatus.VERIFIED.value
        if complexity == "medium":
            return VerificationStatus.GENERATED.value
        return VerificationStatus.BOUNDED.value

    def _generate_content(self, message: str, complexity: str) -> str:
        if complexity == "high":
            return "High-complexity request acknowledged with deterministic guardrails."
        if complexity == "medium":
            return "Here is a concise response aligned to the request."
        return "Hello! Murphy System ready."
