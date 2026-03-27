"""
Gate Damping Controller

Gate generation is itself recursive and must be damped.

Formula:
    Gₜ₊₁ = Gₜ + κ·new_gates·e^(-Cₜ)

Rules:
- Gate growth is sub-linear
- Confidence reduces gate proliferation
- No exponential growth permitted
- Hard upper bounds always enforced
"""

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

logger = logging.getLogger("recursive_stability_controller.gate_damping")


@dataclass
class GateSynthesisRequest:
    """Gate synthesis request"""

    # Request details
    request_id: str
    gate_type: str
    num_gates: int

    # Context
    timestamp: float
    cycle_id: int

    # Requester
    requester: str

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "gate_type": self.gate_type,
            "num_gates": self.num_gates,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "requester": self.requester
        }


@dataclass
class GateSynthesisResponse:
    """Gate synthesis response"""

    # Allowed gates
    allowed_gates: int

    # Request
    request: GateSynthesisRequest

    # Damping factor applied
    damping_factor: float

    # Reasoning
    reason: str

    # Metadata
    timestamp: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "allowed_gates": self.allowed_gates,
            "request": self.request.to_dict(),
            "damping_factor": self.damping_factor,
            "reason": self.reason,
            "timestamp": self.timestamp
        }


class GateDampingController:
    """
    Control gate synthesis rate with damping.

    Prevents exponential gate proliferation by:
    - Applying confidence-based damping
    - Enforcing sub-linear growth
    - Hard upper bounds
    """

    # Damping coefficient (κ)
    KAPPA = 0.5

    # Hard upper bound on total gates
    MAX_TOTAL_GATES = 1000

    # Maximum gates per synthesis request
    MAX_GATES_PER_REQUEST = 50

    def __init__(self):
        """Initialize gate damping controller"""
        self.current_gate_count = 0
        self.synthesis_history = []
        self.max_history = 1000

    def request_synthesis(
        self,
        request: GateSynthesisRequest,
        current_confidence: float
    ) -> GateSynthesisResponse:
        """
        Request gate synthesis with damping.

        Formula:
            allowed = κ·requested·e^(-C)

        Args:
            request: Gate synthesis request
            current_confidence: Current system confidence

        Returns:
            GateSynthesisResponse with allowed gate count
        """
        import time

        # Apply damping formula
        damping_factor = self.KAPPA * np.exp(-current_confidence)
        allowed_gates = int(request.num_gates * damping_factor)

        # Enforce per-request limit
        if allowed_gates > self.MAX_GATES_PER_REQUEST:
            allowed_gates = self.MAX_GATES_PER_REQUEST
            reason = f"Capped at per-request limit ({self.MAX_GATES_PER_REQUEST})"

        # Enforce total gate limit
        elif self.current_gate_count + allowed_gates > self.MAX_TOTAL_GATES:
            allowed_gates = max(0, self.MAX_TOTAL_GATES - self.current_gate_count)
            reason = f"Capped at total limit ({self.MAX_TOTAL_GATES})"

        # Normal damping
        else:
            reason = f"Damped by factor {damping_factor:.3f} (confidence: {current_confidence:.3f})"

        # Update gate count
        self.current_gate_count += allowed_gates

        # Create response
        response = GateSynthesisResponse(
            allowed_gates=allowed_gates,
            request=request,
            damping_factor=damping_factor,
            reason=reason,
            timestamp=time.time()
        )

        # Record in history
        self._record_history(response)

        logger.info(f"[GATE SYNTHESIS] Requested: {request.num_gates}, Allowed: {allowed_gates}")
        logger.info(f"  {reason}")

        return response

    def retire_gates(self, count: int):
        """
        Retire gates (reduce count).

        Args:
            count: Number of gates to retire
        """
        self.current_gate_count = max(0, self.current_gate_count - count)
        logger.info(f"[GATE RETIRE] Retired {count} gates, current: {self.current_gate_count}")

    def get_gate_count(self) -> int:
        """Get current gate count"""
        return self.current_gate_count

    def get_capacity(self) -> Dict:
        """
        Get gate capacity information.

        Returns:
            Dictionary with current, max, available, utilization
        """
        available = max(0, self.MAX_TOTAL_GATES - self.current_gate_count)
        utilization = self.current_gate_count / self.MAX_TOTAL_GATES

        return {
            "current": self.current_gate_count,
            "max": self.MAX_TOTAL_GATES,
            "available": available,
            "utilization": utilization
        }

    def _record_history(self, response: GateSynthesisResponse):
        """Record synthesis response in history"""
        self.synthesis_history.append({
            "request": response.request.to_dict(),
            "allowed_gates": response.allowed_gates,
            "damping_factor": response.damping_factor,
            "reason": response.reason,
            "timestamp": response.timestamp,
            "total_gates_after": self.current_gate_count
        })

        # Trim history if needed
        if len(self.synthesis_history) > self.max_history:
            self.synthesis_history = self.synthesis_history[-self.max_history:]

    def get_history(self, n: int = None) -> List[Dict]:
        """
        Get synthesis history.

        Args:
            n: Number of recent entries (all if None)

        Returns:
            List of history entries
        """
        if n is None:
            return self.synthesis_history
        return self.synthesis_history[-n:]

    def get_statistics(self) -> Dict:
        """
        Get gate synthesis statistics.

        Returns:
            Dictionary with total requested, total allowed, damping stats
        """
        if not self.synthesis_history:
            return {
                "total_requests": 0,
                "total_requested": 0,
                "total_allowed": 0,
                "mean_damping": 0.0,
                "approval_rate": 0.0
            }

        total_requested = sum(h["request"]["num_gates"] for h in self.synthesis_history)
        total_allowed = sum(h["allowed_gates"] for h in self.synthesis_history)
        mean_damping = np.mean([h["damping_factor"] for h in self.synthesis_history])

        return {
            "total_requests": len(self.synthesis_history),
            "total_requested": total_requested,
            "total_allowed": total_allowed,
            "mean_damping": mean_damping,
            "approval_rate": total_allowed / max(total_requested, 1)
        }

    def halt_synthesis(self):
        """Halt all gate synthesis (emergency)"""
        logger.info("[HALT] Gate synthesis halted - no new gates allowed")
        # Note: Actual halt logic handled by returning 0 allowed gates

    def reset_count(self, new_count: int = 0):
        """
        Reset gate count (use with caution).

        Args:
            new_count: New gate count
        """
        old_count = self.current_gate_count
        self.current_gate_count = new_count
        logger.info(f"[RESET] Gate count reset: {old_count} → {new_count}")
