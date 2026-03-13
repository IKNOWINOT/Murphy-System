"""
Control Signal Generator

Generates hard control signals based on stability state.

When ΔVₜ > 0 or S(t) < S_min:
1. Freeze agent spawning
2. Halt gate synthesis
3. Collapse to verification-only mode
4. Shrink admissible solution space
5. Require deterministic grounding

Re-expansion only after:
- ΔVₜ ≤ 0 for N consecutive cycles
- S(t) ≥ S_min + margin
- No unresolved failures
- Entropy decreasing
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

logger = logging.getLogger(__name__)


class ControlMode(Enum):
    """Control mode enumeration"""
    EMERGENCY = "emergency"      # S(t) < 0.5 - immediate freeze
    CONTRACTION = "contraction"  # S(t) < S_min - reduce activity
    NORMAL = "normal"            # S_min ≤ S(t) < S_expansion
    EXPANSION = "expansion"      # S(t) ≥ S_expansion - allow growth


@dataclass
class ControlSignal:
    """Control signal to Execution Orchestrator"""

    # Control mode
    mode: ControlMode

    # Specific controls
    allow_agent_spawn: bool
    allow_gate_synthesis: bool
    allow_planning: bool
    allow_execution: bool
    require_verification: bool
    require_deterministic: bool

    # Authority reduction
    max_authority: str  # "none", "low", "medium", "high", "full"

    # Reasoning
    reasons: List[str]

    # Metadata
    timestamp: float
    cycle_id: int

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "mode": self.mode.value,
            "allow_agent_spawn": self.allow_agent_spawn,
            "allow_gate_synthesis": self.allow_gate_synthesis,
            "allow_planning": self.allow_planning,
            "allow_execution": self.allow_execution,
            "require_verification": self.require_verification,
            "require_deterministic": self.require_deterministic,
            "max_authority": self.max_authority,
            "reasons": self.reasons,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id
        }


class ControlSignalGenerator:
    """
    Generate control signals based on stability state.

    Implements control-theoretic braking:
    - Emergency mode: Immediate freeze
    - Contraction mode: Reduce activity
    - Normal mode: Normal operation
    - Expansion mode: Allow growth
    """

    # Re-expansion criteria (as approved)
    RE_EXPANSION_WINDOW = 5  # N consecutive stable cycles
    RE_EXPANSION_MARGIN = 0.1  # S(t) ≥ S_min + margin

    def __init__(self):
        """Initialize control signal generator"""
        self.current_mode = ControlMode.NORMAL
        self.signal_history = []
        self.max_history = 1000
        self.freeze_count = 0

    def generate_signal(
        self,
        stability_score: float,
        lyapunov_stable: bool,
        entropy_decreasing: bool,
        unresolved_failures: int,
        s_min: float,
        timestamp: float,
        cycle_id: int
    ) -> ControlSignal:
        """
        Generate control signal based on stability state.

        Args:
            stability_score: Current stability score S(t)
            lyapunov_stable: Whether ΔVₜ ≤ 0
            entropy_decreasing: Whether entropy is decreasing
            unresolved_failures: Number of unresolved failures
            s_min: Minimum stability threshold
            timestamp: Current timestamp
            cycle_id: Current cycle ID

        Returns:
            ControlSignal with mode and controls
        """
        reasons = []

        # Determine control mode
        if stability_score < 0.5:
            mode = ControlMode.EMERGENCY
            reasons.append(f"Emergency: S(t) = {stability_score:.3f} < 0.5")
        elif stability_score < s_min:
            mode = ControlMode.CONTRACTION
            reasons.append(f"Contraction: S(t) = {stability_score:.3f} < {s_min}")
        elif stability_score < (s_min + 0.15):  # S_expansion = 0.85
            mode = ControlMode.NORMAL
            reasons.append(f"Normal: S(t) = {stability_score:.3f}")
        else:
            mode = ControlMode.EXPANSION
            reasons.append(f"Expansion: S(t) = {stability_score:.3f} ≥ 0.85")

        # Check Lyapunov stability
        if not lyapunov_stable:
            if mode == ControlMode.EXPANSION:
                mode = ControlMode.NORMAL
            elif mode == ControlMode.NORMAL:
                mode = ControlMode.CONTRACTION
            reasons.append("Lyapunov violation: ΔVₜ > 0")

        # Check unresolved failures
        if unresolved_failures > 0:
            if mode == ControlMode.EXPANSION:
                mode = ControlMode.NORMAL
            reasons.append(f"Unresolved failures: {unresolved_failures}")

        # Generate controls based on mode
        if mode == ControlMode.EMERGENCY:
            signal = self._generate_emergency_signal(reasons, timestamp, cycle_id)
            self.freeze_count += 1
        elif mode == ControlMode.CONTRACTION:
            signal = self._generate_contraction_signal(reasons, timestamp, cycle_id)
        elif mode == ControlMode.NORMAL:
            signal = self._generate_normal_signal(reasons, timestamp, cycle_id)
        else:  # EXPANSION
            signal = self._generate_expansion_signal(reasons, timestamp, cycle_id)

        # Update current mode
        self.current_mode = mode

        # Record in history
        self._record_history(signal)

        return signal

    def _generate_emergency_signal(
        self,
        reasons: List[str],
        timestamp: float,
        cycle_id: int
    ) -> ControlSignal:
        """Generate emergency control signal"""
        return ControlSignal(
            mode=ControlMode.EMERGENCY,
            allow_agent_spawn=False,
            allow_gate_synthesis=False,
            allow_planning=False,
            allow_execution=False,  # Freeze all execution
            require_verification=True,
            require_deterministic=True,
            max_authority="none",  # No authority
            reasons=reasons,
            timestamp=timestamp,
            cycle_id=cycle_id
        )

    def _generate_contraction_signal(
        self,
        reasons: List[str],
        timestamp: float,
        cycle_id: int
    ) -> ControlSignal:
        """Generate contraction control signal"""
        return ControlSignal(
            mode=ControlMode.CONTRACTION,
            allow_agent_spawn=False,  # Block new agents
            allow_gate_synthesis=False,  # Block new gates
            allow_planning=True,  # Allow planning
            allow_execution=True,  # Allow execution (reduced authority)
            require_verification=True,
            require_deterministic=False,
            max_authority="low",  # Reduced authority
            reasons=reasons,
            timestamp=timestamp,
            cycle_id=cycle_id
        )

    def _generate_normal_signal(
        self,
        reasons: List[str],
        timestamp: float,
        cycle_id: int
    ) -> ControlSignal:
        """Generate normal control signal"""
        return ControlSignal(
            mode=ControlMode.NORMAL,
            allow_agent_spawn=True,  # Allow agents (queued)
            allow_gate_synthesis=True,  # Allow gates (damped)
            allow_planning=True,
            allow_execution=True,
            require_verification=True,
            require_deterministic=False,
            max_authority="medium",  # Normal authority
            reasons=reasons,
            timestamp=timestamp,
            cycle_id=cycle_id
        )

    def _generate_expansion_signal(
        self,
        reasons: List[str],
        timestamp: float,
        cycle_id: int
    ) -> ControlSignal:
        """Generate expansion control signal"""
        return ControlSignal(
            mode=ControlMode.EXPANSION,
            allow_agent_spawn=True,
            allow_gate_synthesis=True,
            allow_planning=True,
            allow_execution=True,
            require_verification=False,  # Verification optional
            require_deterministic=False,
            max_authority="high",  # Higher authority allowed
            reasons=reasons,
            timestamp=timestamp,
            cycle_id=cycle_id
        )

    def check_re_expansion_criteria(
        self,
        stability_history: List[Dict],
        lyapunov_history: List[Dict],
        entropy_history: List[float],
        unresolved_failures: int,
        s_min: float
    ) -> tuple[bool, List[str]]:
        """
        Check if re-expansion criteria are satisfied.

        Criteria (all must be true):
        1. ΔVₜ ≤ 0 for N = 5 consecutive cycles
        2. S(t) ≥ S_min + 0.1 (≥ 0.8)
        3. No unresolved failures
        4. Entropy strictly decreasing or flat

        Args:
            stability_history: Recent stability scores
            lyapunov_history: Recent Lyapunov states
            entropy_history: Recent entropy values
            unresolved_failures: Number of unresolved failures
            s_min: Minimum stability threshold

        Returns:
            (criteria_met, reasons)
        """
        reasons = []
        criteria_met = True

        # Check 1: Lyapunov stability for N cycles
        if len(lyapunov_history) < self.RE_EXPANSION_WINDOW:
            criteria_met = False
            reasons.append(f"Insufficient history: {len(lyapunov_history)} < {self.RE_EXPANSION_WINDOW}")
        else:
            recent_lyapunov = lyapunov_history[-self.RE_EXPANSION_WINDOW:]
            if not all(h["is_stable"] for h in recent_lyapunov):
                criteria_met = False
                reasons.append(f"Lyapunov not stable for {self.RE_EXPANSION_WINDOW} cycles")

        # Check 2: Stability score with margin
        if stability_history:
            current_score = stability_history[-1]["score"]
            threshold = s_min + self.RE_EXPANSION_MARGIN
            if current_score < threshold:
                criteria_met = False
                reasons.append(f"S(t) = {current_score:.3f} < {threshold:.3f}")

        # Check 3: No unresolved failures
        if unresolved_failures > 0:
            criteria_met = False
            reasons.append(f"Unresolved failures: {unresolved_failures}")

        # Check 4: Entropy decreasing or flat
        if len(entropy_history) >= 2:
            recent_entropy = entropy_history[-2:]
            if recent_entropy[-1] > recent_entropy[-2]:
                criteria_met = False
                reasons.append(f"Entropy increasing: {recent_entropy[-2]:.3f} → {recent_entropy[-1]:.3f}")

        if criteria_met:
            reasons = ["All re-expansion criteria satisfied"]

        return criteria_met, reasons

    def _record_history(self, signal: ControlSignal):
        """Record control signal in history"""
        self.signal_history.append({
            "mode": signal.mode.value,
            "allow_agent_spawn": signal.allow_agent_spawn,
            "allow_gate_synthesis": signal.allow_gate_synthesis,
            "max_authority": signal.max_authority,
            "reasons": signal.reasons,
            "timestamp": signal.timestamp,
            "cycle_id": signal.cycle_id
        })

        # Trim history if needed
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]

    def get_history(self, n: int = None) -> List[Dict]:
        """
        Get control signal history.

        Args:
            n: Number of recent entries (all if None)

        Returns:
            List of history entries
        """
        if n is None:
            return self.signal_history
        return self.signal_history[-n:]

    def get_statistics(self) -> Dict:
        """
        Get control signal statistics.

        Returns:
            Dictionary with mode distribution, freeze count, etc.
        """
        if not self.signal_history:
            return {
                "total_cycles": 0,
                "emergency_count": 0,
                "contraction_count": 0,
                "normal_count": 0,
                "expansion_count": 0,
                "freeze_count": self.freeze_count
            }

        emergency = sum(1 for h in self.signal_history if h["mode"] == "emergency")
        contraction = sum(1 for h in self.signal_history if h["mode"] == "contraction")
        normal = sum(1 for h in self.signal_history if h["mode"] == "normal")
        expansion = sum(1 for h in self.signal_history if h["mode"] == "expansion")

        return {
            "total_cycles": len(self.signal_history),
            "emergency_count": emergency,
            "contraction_count": contraction,
            "normal_count": normal,
            "expansion_count": expansion,
            "freeze_count": self.freeze_count,
            "current_mode": self.current_mode.value
        }
