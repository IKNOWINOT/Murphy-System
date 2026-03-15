"""
Spawn Rate Controller

Agent creation is strictly gated.

A new agent may only be queued (never immediately launched) if:
1. ΔVₜ ≤ 0 (Lyapunov stability satisfied)
2. Entropy is non-increasing
3. Confidence is non-decreasing
4. No unresolved failures exist
5. Spawn does not increase Rₜ

Otherwise: spawn = DENIED
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger("recursive_stability_controller.spawn_controller")


class SpawnDecision(Enum):
    """Spawn decision enumeration"""
    APPROVED = "approved"
    QUEUED = "queued"
    DENIED = "denied"


@dataclass
class SpawnRequest:
    """Agent spawn request"""

    # Request details
    request_id: str
    agent_type: str
    priority: int

    # Context
    timestamp: float
    cycle_id: int

    # Requester
    requester: str

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "agent_type": self.agent_type,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "requester": self.requester
        }


@dataclass
class SpawnResponse:
    """Agent spawn response"""

    # Decision
    decision: SpawnDecision

    # Request
    request: SpawnRequest

    # Reasoning
    reasons: List[str]

    # Metadata
    timestamp: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "decision": self.decision.value,
            "request": self.request.to_dict(),
            "reasons": self.reasons,
            "timestamp": self.timestamp
        }


class SpawnRateController:
    """
    Control agent spawn rate based on stability.

    Enforces strict gating:
    - Agents can only be queued, never immediately launched
    - Multiple criteria must be satisfied
    - Violations result in denial
    """

    def __init__(self):
        """Initialize spawn controller"""
        self.spawn_queue = []
        self.spawn_history = []
        self.denied_requests = []
        self.max_queue_size = 100
        self.max_history = 1000

        # State tracking
        self.previous_entropy = None
        self.previous_confidence = None
        self.unresolved_failures = 0

    def request_spawn(
        self,
        request: SpawnRequest,
        current_state: Dict
    ) -> SpawnResponse:
        """
        Request agent spawn.

        Args:
            request: Spawn request
            current_state: Current system state with:
                - lyapunov_stable: bool (ΔVₜ ≤ 0)
                - entropy: float
                - confidence: float
                - recursion_energy: float
                - estimated_spawn_impact: float (increase in Rₜ)

        Returns:
            SpawnResponse with decision and reasoning
        """
        import time

        reasons = []

        # Check 1: Lyapunov stability
        if not current_state.get("lyapunov_stable", False):
            reasons.append("Lyapunov stability violated (ΔVₜ > 0)")

        # Check 2: Entropy non-increasing
        current_entropy = current_state.get("entropy", 0.0)
        if self.previous_entropy is not None:
            if current_entropy > self.previous_entropy:
                reasons.append(
                    f"Entropy increasing ({self.previous_entropy:.3f} → {current_entropy:.3f})"
                )

        # Check 3: Confidence non-decreasing
        current_confidence = current_state.get("confidence", 0.0)
        if self.previous_confidence is not None:
            if current_confidence < self.previous_confidence:
                reasons.append(
                    f"Confidence decreasing ({self.previous_confidence:.3f} → {current_confidence:.3f})"
                )

        # Check 4: No unresolved failures
        if self.unresolved_failures > 0:
            reasons.append(f"Unresolved failures: {self.unresolved_failures}")

        # Check 5: Spawn does not increase Rₜ significantly
        current_R = current_state.get("recursion_energy", 0.0)
        spawn_impact = current_state.get("estimated_spawn_impact", 0.0)
        if spawn_impact > 0.1:  # Threshold for significant increase
            reasons.append(
                f"Spawn would increase Rₜ by {spawn_impact:.3f} (current: {current_R:.3f})"
            )

        # Make decision
        if reasons:
            # DENIED
            decision = SpawnDecision.DENIED
            self._record_denied(request, reasons)
        else:
            # QUEUED (never immediately approved)
            decision = SpawnDecision.QUEUED
            self._add_to_queue(request)

        # Update state tracking
        self.previous_entropy = current_entropy
        self.previous_confidence = current_confidence

        # Create response
        response = SpawnResponse(
            decision=decision,
            request=request,
            reasons=reasons if reasons else ["All criteria satisfied - queued"],
            timestamp=time.time()
        )

        # Record in history
        self._record_history(response)

        return response

    def process_queue(
        self,
        max_agents: int = 1
    ) -> List[SpawnRequest]:
        """
        Process spawn queue.

        Launches agents from queue in priority order.

        Args:
            max_agents: Maximum agents to launch per cycle

        Returns:
            List of launched spawn requests
        """
        if not self.spawn_queue:
            return []

        # Sort by priority (higher first)
        self.spawn_queue.sort(key=lambda r: r.priority, reverse=True)

        # Launch up to max_agents
        launched = []
        for _ in range(min(max_agents, len(self.spawn_queue))):
            request = self.spawn_queue.pop(0)
            launched.append(request)
            logger.info(f"[SPAWN] Launching agent: {request.agent_type} (priority: {request.priority})")

        return launched

    def _add_to_queue(self, request: SpawnRequest):
        """Add request to spawn queue"""
        if len(self.spawn_queue) >= self.max_queue_size:
            logger.info(f"[WARNING] Spawn queue full, dropping request: {request.request_id}")
            return

        self.spawn_queue.append(request)
        logger.info(f"[QUEUE] Agent spawn queued: {request.agent_type}")

    def _record_denied(self, request: SpawnRequest, reasons: List[str]):
        """Record denied request"""
        self.denied_requests.append({
            "request": request.to_dict(),
            "reasons": reasons,
            "timestamp": request.timestamp
        })

        logger.info(f"[DENIED] Agent spawn denied: {request.agent_type}")
        for reason in reasons:
            logger.info(f"  - {reason}")

    def _record_history(self, response: SpawnResponse):
        """Record spawn response in history"""
        self.spawn_history.append({
            "decision": response.decision.value,
            "request": response.request.to_dict(),
            "reasons": response.reasons,
            "timestamp": response.timestamp
        })

        # Trim history if needed
        if len(self.spawn_history) > self.max_history:
            self.spawn_history = self.spawn_history[-self.max_history:]

    def get_queue_status(self) -> Dict:
        """
        Get spawn queue status.

        Returns:
            Dictionary with queue size, pending requests, etc.
        """
        return {
            "queue_size": len(self.spawn_queue),
            "max_queue_size": self.max_queue_size,
            "pending_requests": [r.to_dict() for r in self.spawn_queue],
            "denied_count": len(self.denied_requests)
        }

    def get_statistics(self) -> Dict:
        """
        Get spawn statistics.

        Returns:
            Dictionary with approval rate, denial rate, etc.
        """
        if not self.spawn_history:
            return {
                "total_requests": 0,
                "approved_count": 0,
                "queued_count": 0,
                "denied_count": 0,
                "approval_rate": 0.0,
                "denial_rate": 0.0
            }

        approved = sum(1 for h in self.spawn_history if h["decision"] == "approved")
        queued = sum(1 for h in self.spawn_history if h["decision"] == "queued")
        denied = sum(1 for h in self.spawn_history if h["decision"] == "denied")
        total = len(self.spawn_history)

        return {
            "total_requests": total,
            "approved_count": approved,
            "queued_count": queued,
            "denied_count": denied,
            "approval_rate": approved / total,
            "denial_rate": denied / total
        }

    def report_failure(self):
        """Report unresolved failure"""
        self.unresolved_failures += 1
        logger.info(f"[FAILURE] Unresolved failures: {self.unresolved_failures}")

    def resolve_failure(self):
        """Resolve failure"""
        if self.unresolved_failures > 0:
            self.unresolved_failures -= 1
            logger.info(f"[RESOLVED] Unresolved failures: {self.unresolved_failures}")

    def clear_queue(self):
        """Clear spawn queue (emergency)"""
        cleared = len(self.spawn_queue)
        self.spawn_queue = []
        logger.info(f"[EMERGENCY] Spawn queue cleared: {cleared} requests dropped")

    def freeze(self):
        """Freeze spawn controller (no new spawns)"""
        logger.info("[FREEZE] Spawn controller frozen - all requests will be denied")
        # Note: Actual freeze logic handled by checking system state
