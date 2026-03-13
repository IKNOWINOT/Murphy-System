"""Bridge module for tests that import from src.gate_synthesis.gate_synthesis

Provides a GateSynthesisEngine with a simplified ``synthesize_gates`` helper.
"""

import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class GateSynthesisEngine:
    """Simplified gate synthesis engine for integration tests."""

    def __init__(self):
        pass

    def synthesize_gates(
        self, *, confidence: float = 1.0, murphy_index: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Synthesize gates based on confidence level and Murphy index.

        Returns fewer gates for high confidence, more for low confidence.
        """
        gates: List[Dict[str, Any]] = []

        if confidence < 0.5:
            count = max(6, int(murphy_index * 10))
        elif confidence < 0.8:
            count = max(3, int(murphy_index * 6))
        else:
            count = min(2, int(murphy_index * 3))

        for i in range(count):
            gates.append({
                "gate_id": f"gate_{uuid.uuid4().hex[:8]}",
                "gate_type": "confidence" if i % 2 == 0 else "verification",
                "blocking": confidence < 0.5,
                "threshold": 0.7,
            })

        return gates


    async def generate_gates(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Async convenience method for generating gates from a params dict."""
        params = params or {}
        confidence = params.get("confidence", 0.8)
        murphy_index = params.get("risk_level_value", 0.2)
        gates = self.synthesize_gates(confidence=confidence, murphy_index=murphy_index)
        # Add safety-specific gate if safety_critical
        if params.get("safety_critical"):
            gates.append({
                "gate_id": f"gate_{uuid.uuid4().hex[:8]}",
                "gate_type": "safety",
                "blocking": True,
                "threshold": 0.9,
            })
        return gates


__all__ = ['GateSynthesisEngine']
