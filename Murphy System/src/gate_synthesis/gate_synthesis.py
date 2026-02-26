"""Bridge module for tests that import from src.gate_synthesis.gate_synthesis

Provides a GateSynthesisEngine with a simplified ``synthesize_gates`` helper.
"""

import uuid
from typing import Dict, Any, List


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


__all__ = ['GateSynthesisEngine']
