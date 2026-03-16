"""
Runtime Risk Monitor
====================

Continuously monitors risk during execution and triggers automatic pause.

Monitoring:
- Runtime risk calculation (base + accumulated)
- Threshold checking (risk and confidence)
- Automatic pause logic (on threshold breach)
- Control plane notification (alert on issues)

Design Principle: Continuous safety monitoring with automatic intervention
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("execution_orchestrator.risk_monitor")

from .models import RuntimeRisk, SafetyState, StepResult, StopCondition, StopReason


class RuntimeRiskMonitor:
    """
    Monitors risk during execution

    Enforces:
    - Risk threshold limits
    - Confidence threshold limits
    - Automatic pause on breach
    - Control plane notifications
    """

    def __init__(
        self,
        risk_threshold: float = 0.3,
        confidence_threshold: float = 0.7
    ):
        self.risk_threshold = risk_threshold
        self.confidence_threshold = confidence_threshold
        self.safety_states: Dict[str, SafetyState] = {}
        self.runtime_risks: Dict[str, RuntimeRisk] = {}
        self.pause_callbacks: List[Callable] = []

    def initialize_monitoring(
        self,
        packet_id: str,
        base_risk: float,
        initial_confidence: float
    ):
        """
        Initialize monitoring for packet execution

        Args:
            packet_id: Packet being executed
            base_risk: Base risk from packet compilation
            initial_confidence: Initial confidence score
        """
        # Initialize runtime risk
        self.runtime_risks[packet_id] = RuntimeRisk(
            base_risk=base_risk,
            accumulated_risk=0.0
        )

        # Initialize safety state
        self.safety_states[packet_id] = SafetyState(
            current_risk=base_risk,
            risk_threshold=self.risk_threshold,
            current_confidence=initial_confidence,
            confidence_threshold=self.confidence_threshold
        )

    def update_after_step(
        self,
        packet_id: str,
        step_result: StepResult,
        new_confidence: float
    ) -> SafetyState:
        """
        Update monitoring after step execution

        Args:
            packet_id: Packet being executed
            step_result: Result of step execution
            new_confidence: Updated confidence score

        Returns:
            Updated safety state
        """
        # Get runtime risk
        runtime_risk = self.runtime_risks.get(packet_id)
        if not runtime_risk:
            raise ValueError(f"No runtime risk initialized for packet {packet_id}")

        # Add step risk
        runtime_risk.add_step_risk(step_result.risk_delta)

        # Get safety state
        safety_state = self.safety_states.get(packet_id)
        if not safety_state:
            raise ValueError(f"No safety state initialized for packet {packet_id}")

        # Update safety state
        safety_state.current_risk = runtime_risk.get_total_risk()
        safety_state.current_confidence = new_confidence

        # Check for stop conditions
        self._check_stop_conditions(packet_id, safety_state)

        # Check overall safety
        safety_state.check_safety()

        return safety_state

    def check_safety(self, packet_id: str) -> bool:
        """
        Check if execution is still safe

        Args:
            packet_id: Packet being executed

        Returns:
            True if safe to continue, False otherwise
        """
        safety_state = self.safety_states.get(packet_id)
        if not safety_state:
            return False

        return safety_state.is_safe

    def get_stop_conditions(self, packet_id: str) -> List[StopCondition]:
        """Get all stop conditions for packet"""
        safety_state = self.safety_states.get(packet_id)
        if not safety_state:
            return []

        return safety_state.stop_conditions

    def should_pause(self, packet_id: str) -> bool:
        """Check if execution should be paused"""
        return not self.check_safety(packet_id)

    def get_runtime_risk(self, packet_id: str) -> Optional[RuntimeRisk]:
        """Get runtime risk for packet"""
        return self.runtime_risks.get(packet_id)

    def get_safety_state(self, packet_id: str) -> Optional[SafetyState]:
        """Get safety state for packet"""
        return self.safety_states.get(packet_id)

    def register_pause_callback(self, callback: Callable[[str, List[StopCondition]], None]):
        """
        Register callback to be called when execution should pause

        Args:
            callback: Function to call with (packet_id, stop_conditions)
        """
        self.pause_callbacks.append(callback)

    def _check_stop_conditions(self, packet_id: str, safety_state: SafetyState):
        """Check for stop conditions and add to safety state"""
        # Check risk threshold
        if safety_state.current_risk > safety_state.risk_threshold:
            condition = StopCondition(
                reason=StopReason.RISK_THRESHOLD,
                severity='critical',
                message=f"Risk threshold breached: {safety_state.current_risk:.3f} > {safety_state.risk_threshold:.3f}",
                timestamp=datetime.now(timezone.utc),
                requires_rollback=True
            )
            safety_state.stop_conditions.append(condition)
            self._notify_pause(packet_id, [condition])

        # Check confidence threshold
        if safety_state.current_confidence < safety_state.confidence_threshold:
            condition = StopCondition(
                reason=StopReason.CONFIDENCE_DROP,
                severity='critical',
                message=f"Confidence below threshold: {safety_state.current_confidence:.3f} < {safety_state.confidence_threshold:.3f}",
                timestamp=datetime.now(timezone.utc),
                requires_rollback=True
            )
            safety_state.stop_conditions.append(condition)
            self._notify_pause(packet_id, [condition])

    def _notify_pause(self, packet_id: str, conditions: List[StopCondition]):
        """Notify all pause callbacks"""
        for callback in self.pause_callbacks:
            try:
                callback(packet_id, conditions)
            except Exception as exc:
                logger.info(f"Error notifying pause callback: {exc}")

    def calculate_risk_projection(self, packet_id: str, remaining_steps: int) -> float:
        """
        Calculate projected final risk

        Args:
            packet_id: Packet being executed
            remaining_steps: Number of steps remaining

        Returns:
            Projected final risk score
        """
        runtime_risk = self.runtime_risks.get(packet_id)
        if not runtime_risk:
            return 0.0

        # Use average risk delta to project
        if len(runtime_risk.risk_deltas) > 0:
            avg_delta = sum(runtime_risk.risk_deltas) / len(runtime_risk.risk_deltas)
            projected_additional_risk = avg_delta * remaining_steps
            return runtime_risk.get_total_risk() + projected_additional_risk

        return runtime_risk.get_total_risk()

    def get_risk_trend(self, packet_id: str) -> str:
        """
        Get risk trend (increasing, decreasing, stable)

        Args:
            packet_id: Packet being executed

        Returns:
            Trend description
        """
        runtime_risk = self.runtime_risks.get(packet_id)
        if not runtime_risk or len(runtime_risk.risk_deltas) < 2:
            return 'stable'

        # Look at last few deltas
        recent_deltas = runtime_risk.risk_deltas[-5:]
        avg_delta = sum(recent_deltas) / (len(recent_deltas) or 1)

        if avg_delta > 0.01:
            return 'increasing'
        elif avg_delta < -0.01:
            return 'decreasing'
        else:
            return 'stable'

    def get_monitoring_summary(self, packet_id: str) -> Dict:
        """
        Get monitoring summary for packet

        Returns:
            Dictionary with monitoring metrics
        """
        runtime_risk = self.runtime_risks.get(packet_id)
        safety_state = self.safety_states.get(packet_id)

        if not runtime_risk or not safety_state:
            return {}

        return {
            'packet_id': packet_id,
            'runtime_risk': runtime_risk.to_dict(),
            'safety_state': safety_state.to_dict(),
            'is_safe': safety_state.is_safe,
            'should_pause': not safety_state.is_safe,
            'risk_trend': self.get_risk_trend(packet_id),
            'stop_conditions': [c.to_dict() for c in safety_state.stop_conditions]
        }

    def reset_monitoring(self, packet_id: str):
        """Reset monitoring for packet"""
        if packet_id in self.runtime_risks:
            del self.runtime_risks[packet_id]
        if packet_id in self.safety_states:
            del self.safety_states[packet_id]
