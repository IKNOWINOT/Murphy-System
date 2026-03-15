"""
Stability Controller Implementation

Implements stability monitoring and refusal semantics including:
- Stability definition and convergence measurement
- Retry policy enforcement
- Refusal handling as valid state
- System invariant enforcement
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class ExecutionOutcome(Enum):
    """Execution outcome classification"""
    SUCCESS_COMPLETED = "SUCCESS_COMPLETED"
    SUCCESS_REFUSED = "SUCCESS_REFUSED"
    SUCCESS_PARTIAL = "SUCCESS_PARTIAL"
    FAILURE_TIMEOUT = "FAILURE_TIMEOUT"
    FAILURE_RESOURCE_CONSTRAINT = "FAILURE_RESOURCE_CONSTRAINT"
    FAILURE_DEPENDENCY = "FAILURE_DEPENDENCY"
    FAILURE_VALIDATION = "FAILURE_VALIDATION"
    ERROR_SYSTEM = "ERROR_SYSTEM"
    ERROR_AGENT = "ERROR_AGENT"
    ERROR_UNKNOWN = "ERROR_UNKNOWN"


@dataclass
class StabilityMetrics:
    """Stability measurement for agents"""

    divergence_threshold: float = 0.1
    stability_window_ms: int = 300000  # 5 minutes
    convergence_threshold: float = 0.05
    max_instability_duration: int = 60000  # 1 minute

    def is_stable(self, agent_state: Dict, history: List[Dict]) -> bool:
        """Determine if agent is operating within stability bounds"""
        if len(history) < 2:
            return True

        # Calculate state change rate
        recent_states = history[-10:]  # Last 10 states
        state_changes = []

        for i in range(1, len(recent_states)):
            try:
                prev_state = recent_states[i-1].get('state_hash', '')
                curr_state = recent_states[i].get('state_hash', '')
                if prev_state != curr_state:
                    state_changes.append(1)
                else:
                    state_changes.append(0)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                state_changes.append(0)

        max_change_rate = max(state_changes) if state_changes else 0

        return max_change_rate <= self.divergence_threshold

    def calculate_stability_score(self, agent_state: Dict, history: List[Dict]) -> float:
        """Generate continuous stability score (0.0-1.0)"""
        if self.is_stable(agent_state, history):
            return 1.0

        # Calculate penalties for violations
        penalties = []

        if not self.is_stable(agent_state, history):
            penalties.append(0.3)

        return max(0.0, 1.0 - sum(penalties))


class RefusalHandler:
    """Handles refusal as a valid execution state"""

    VALID_REFUSAL_REASONS = [
        "SAFETY_CONSTRAINT_VIOLATION",
        "INSUFFICIENT_GOVERNANCE_ARTIFACTS",
        "AUTHORITY_EXCEEDED",
        "DEPENDENCY_UNAVAILABLE",
        "REGULATORY_PROHIBITION",
        "ETHICAL_BOUNDARY_VIOLATION"
    ]

    def handle_refusal(self, refusing_agent: Dict, refusal_reason: str) -> Dict:
        """Treat refusal as valid terminal state"""

        if not self.is_valid_refusal(refusal_reason):
            return {
                "outcome": ExecutionOutcome.ERROR_AGENT,
                "reason": "Invalid refusal reason"
            }

        # Record refusal as success for scheduling
        outcome_record = {
            "agent_id": refusing_agent.get("agent_id"),
            "outcome": ExecutionOutcome.SUCCESS_REFUSED,
            "termination_reason": refusal_reason,
            "completion_time": datetime.now(timezone.utc).isoformat()
        }

        return outcome_record

    def is_valid_refusal(self, refusal_reason: str) -> bool:
        """Validate refusal meets system criteria"""
        return refusal_reason in self.VALID_REFUSAL_REASONS


class RetryController:
    """Controls retry policy for agents"""

    def __init__(self, max_retries: int = 3, min_backoff_ms: int = 1000):
        self.max_retries = max_retries
        self.min_backoff_ms = min_backoff_ms

    def can_retry(self, agent_state: Dict, retry_count: int, previous_state: str, current_state: str) -> bool:
        """Check if retry is permitted"""

        if retry_count >= self.max_retries:
            return False

        if previous_state == current_state:
            return False  # No state change

        return True

    def should_stop_retry(self, agent_state: Dict, retry_count: int, divergence_detected: bool) -> bool:
        """Check if retries must stop"""

        if retry_count >= self.max_retries:
            return True

        if divergence_detected:
            return True

        return False


class SystemInvariantChecker:
    """Enforces system invariants to prevent unsafe behavior"""

    def check_invariants(self, agents: List[Dict], system_resources: Dict) -> List[str]:
        """Check all system invariants"""
        violations = []

        # Check total resource allocation
        total_cpu = sum(agent.get("cpu_allocated", 0) for agent in agents)
        total_memory = sum(agent.get("memory_allocated", 0) for agent in agents)

        if total_cpu > system_resources.get("max_cpu", 0) * 0.9:
            violations.append("Total CPU allocation exceeds 90% of capacity")

        if total_memory > system_resources.get("max_memory", 0) * 0.9:
            violations.append("Total memory allocation exceeds 90% of capacity")

        # Check for circular dependencies
        violations.extend(self._check_circular_dependencies(agents))

        # Check authority monotonicity
        violations.extend(self._check_authority_monotonicity(agents))

        return violations

    def _check_circular_dependencies(self, agents: List[Dict]) -> List[str]:
        """Check for circular dependencies in agent execution graph"""
        violations = []

        # Simple cycle detection
        for agent in agents:
            dependencies = agent.get("dependencies", [])
            for dep_id in dependencies:
                dep_agent = next((a for a in agents if a.get("agent_id") == dep_id), None)
                if dep_agent and agent.get("agent_id") in dep_agent.get("dependencies", []):
                    violations.append(f"Circular dependency detected: {agent.get('agent_id')} <-> {dep_id}")

        return violations

    def _check_authority_monotonicity(self, agents: List[Dict]) -> List[str]:
        """Check authority doesn't increase without escalation"""
        violations = []

        for agent in agents:
            current_authority = agent.get("authority_band", "NONE")
            previous_authority = agent.get("previous_authority", current_authority)

            if current_authority > previous_authority and not agent.get("escalation_granted", False):
                violations.append(f"Authority increase without escalation: {agent.get('agent_id')}")

        return violations


class StabilityController:
    """Main stability controller for governed autonomous system"""

    def __init__(self):
        self.metrics = StabilityMetrics()
        self.refusal_handler = RefusalHandler()
        self.retry_controller = RetryController()
        self.invariant_checker = SystemInvariantChecker()

    def evaluate_agent_stability(self, agent_state: Dict, history: List[Dict]) -> Dict:
        """Comprehensive stability evaluation"""

        stability_score = self.metrics.calculate_stability_score(agent_state, history)
        is_stable = self.metrics.is_stable(agent_state, history)

        return {
            "stability_score": stability_score,
            "is_stable": is_stable,
            "can_continue": is_stable or self._can_continue_unstable(agent_state),
            "recommendation": self._get_stability_recommendation(stability_score)
        }

    def _can_continue_unstable(self, agent_state: Dict) -> bool:
        """Check if unstable agent can continue"""
        return (
            agent_state.get("escalation_granted", False) and
            agent_state.get("stability_duration", 0) < 60000  # 1 minute max unstable
        )

    def _get_stability_recommendation(self, stability_score: float) -> str:
        """Get recommendation based on stability score"""
        if stability_score >= 0.8:
            return "CONTINUE"
        elif stability_score >= 0.5:
            return "MONITOR"
        elif stability_score >= 0.2:
            return "REDUCE_AUTHORITY"
        else:
            return "TERMINATE"
