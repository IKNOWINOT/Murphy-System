"""
Enhanced Chatbot with MFGC Integration.
Routes messages through complexity analysis and MFGC pipeline when needed.
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple

from domain_swarms import DomainDetector
from mfgc_core import MFGCController

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """Analyzes message complexity to determine routing."""

    _COMPLEX_KEYWORDS = {
        "design", "architect", "comprehensive", "enterprise", "scalable",
        "distributed", "microservices", "infrastructure", "system",
        "strategy", "integration", "deployment", "fault", "tolerance",
    }

    def analyze(self, message: str, context: Dict[str, Any]) -> Tuple[str, float]:
        """Return (complexity_level, confidence)."""
        words = [w.lower().strip(".,!?") for w in message.split()]
        hits = sum(1 for w in words if w in self._COMPLEX_KEYWORDS)
        length = len(words)

        if hits >= 3 or length > 20:
            return "high", 0.9
        if hits >= 1 or length > 8:
            return "medium", 0.75
        return "low", 0.95


class EnhancedChatbotMFGC:
    """Chatbot that routes complex tasks through the MFGC pipeline."""

    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.domain_detector = DomainDetector()
        self.mfgc_controller = MFGCController()

        self._greeting_re = re.compile(
            r"^(hi|hello|hey|greetings)\b", re.IGNORECASE
        )
        self._capability_re = re.compile(
            r"what can you do|your capabilit", re.IGNORECASE
        )
        self._code_re = re.compile(
            r"write|code|function|implement|program|script", re.IGNORECASE
        )

    def process_message(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if context is None:
            context = {}

        complexity, conf = self.complexity_analyzer.analyze(message, context)

        if complexity == "high":
            return self._mfgc_flow(message, context, complexity, conf)
        return self._standard_flow(message, context, complexity, conf)

    # ------------------------------------------------------------------
    # standard (non-MFGC) flow
    # ------------------------------------------------------------------

    def _standard_flow(
        self, message: str, context: Dict, complexity: str, conf: float
    ) -> Dict[str, Any]:
        if self._greeting_re.search(message):
            return self._make_response(
                "Hello! How can I help you today?",
                marker="B",
                metadata={"intent": "greeting", "complexity": complexity, "confidence": conf},
            )
        if self._capability_re.search(message):
            return self._make_response(
                "I can help with research, code, design, and analysis.",
                marker="B",
                metadata={"intent": "capability", "complexity": complexity, "confidence": conf},
            )
        if self._code_re.search(message):
            return self._make_response(
                self._generate_code_response(message),
                marker="G",
                metadata={"intent": "code", "complexity": complexity, "confidence": conf},
            )
        return self._make_response(
            f"I received your request: {message[:100]}. "
            "Use /research or /math for verified results.",
            marker="B",
            metadata={"intent": "general", "complexity": complexity, "confidence": conf},
        )

    # ------------------------------------------------------------------
    # MFGC flow for complex tasks
    # ------------------------------------------------------------------

    def _mfgc_flow(
        self, message: str, context: Dict, complexity: str, conf: float
    ) -> Dict[str, Any]:
        domain = self.domain_detector.detect_domain(message, context)
        state = self.mfgc_controller.execute(message, context)
        summary = self.mfgc_controller.get_summary(state)

        content = (
            f"MFGC Analysis Complete ({summary['phases_completed']} phases).\n"
            f"Confidence: {summary['final_confidence']:.2f} | "
            f"Murphy Index: {summary['final_murphy_index']:.4f}\n"
            f"Gates: {summary['total_gates']}"
        )

        return self._make_response(
            content,
            marker="V",
            metadata={
                "intent": "mfgc",
                "complexity": complexity,
                "confidence": summary["final_confidence"],
                "domain": domain,
                "phases_completed": summary["phases_completed"],
                "final_confidence": summary["final_confidence"],
                "murphy_index": summary["final_murphy_index"],
                "total_gates": summary["total_gates"],
            },
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_code_response(message: str) -> str:
        return (
            "Here is a code outline for your request. "
            "Please verify the implementation before use."
        )

    @staticmethod
    def _make_response(
        content: str, marker: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        label_map = {"V": "verified", "G": "generated", "B": "bot", "R": "rejected"}
        return {
            "content": content,
            "marker": marker,
            "marker_class": f"marker-{label_map.get(marker, 'bot')}",
            "metadata": metadata,
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "standard_flow": ["greeting", "capability", "code", "general"],
            "mfgc_flow": ["complex_design", "architecture", "strategy"],
            "markers": ["V", "G", "B", "R"],
        }
