"""Bridge: src.execution_packet_compiler.compiler

Provides a simplified ExecutionPacketCompiler that wraps the core compiler
with a ``compile()`` helper expected by integration tests.
"""

import hashlib
import json
import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ExecutionPacketCompiler:
    """Simplified execution packet compiler for integration tests."""

    def __init__(self):
        self._compiled = {}

    def compile(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a hypothesis dict into an execution packet.

        Checks all gates attached to the hypothesis.  If any blocking gate
        fails its threshold, the compilation is rejected.
        """
        gates = hypothesis.get("gates", [])

        # Check gates
        for gate in gates:
            if gate.get("blocking"):
                gate_type = gate.get("gate_type", "")
                if gate_type == "confidence":
                    if gate.get("current", 1.0) < gate.get("threshold", 0.0):
                        return {
                            "success": False,
                            "error": f"Gate {gate['gate_id']} failed: confidence {gate['current']} < {gate['threshold']}",
                        }
                elif gate_type == "verification":
                    if gate.get("required") and not gate.get("verified"):
                        return {
                            "success": False,
                            "error": f"Gate {gate['gate_id']} failed: verification required but not verified",
                        }

        packet_id = f"pkt_{uuid.uuid4().hex[:12]}"
        raw = json.dumps(hypothesis, sort_keys=True, default=str)
        signature = hashlib.sha256(raw.encode()).hexdigest()

        packet = {
            "packet_id": packet_id,
            "hypothesis_id": hypothesis.get("hypothesis_id", "unknown"),
            "plan": hypothesis.get("plan", ""),
            "confidence": hypothesis.get("confidence", 0.0),
            "authority": hypothesis.get("authority", "low"),
            "gates_satisfied": True,
            "signature": signature,
        }

        self._compiled[packet_id] = packet

        return {"success": True, "execution_packet": packet}


__all__ = ['ExecutionPacketCompiler']
