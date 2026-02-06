"""
Enhanced Chatbot with MFGC routing
"""

from __future__ import annotations

from typing import Dict, Any, Tuple

from domain_swarms import DomainDetector
from mfgc_metrics import MFGCMetricsCollector


class ComplexityAnalyzer:
    """Simple heuristic complexity analyzer."""

    def analyze(self, message: str, context: Dict[str, Any]) -> Tuple[str, float]:
        lowered = message.lower()
        if any(token in lowered for token in ["design", "architecture", "comprehensive", "microservices"]):
            return "high", 0.85
        if len(lowered.split()) > 8:
            return "medium", 0.65
        return "low", 0.55


class EnhancedChatbotMFGC:
    """Routes requests based on complexity and domain."""

    def __init__(self):
        self.analyzer = ComplexityAnalyzer()
        self.detector = DomainDetector()
        self.metrics = MFGCMetricsCollector()

    def process_message(self, message: str) -> Dict[str, Any]:
        complexity, confidence = self.analyzer.analyze(message, {})
        domain = self.detector.detect_domain(message, {})
        marker = "V" if complexity == "high" else ("G" if complexity == "medium" else "B")

        return {
            "marker": marker,
            "marker_class": f"marker-{marker}",
            "content": "Request routed via Murphy MFGC pipeline.",
            "metadata": {
                "intent": "mfgc" if complexity == "high" else "standard",
                "complexity": complexity,
                "domain": domain,
                "confidence": confidence,
            },
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "standard_flow": True,
            "mfgc_flow": True,
            "markers": ["V", "G", "B", "R"],
        }
