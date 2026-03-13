"""
Lyapunov Monitor

Enforces Lyapunov stability guarantee:

    ΔVₜ = Vₜ₊₁ - Vₜ ≤ 0

Where:
    Vₜ = Rₜ²

Interpretation:
- Instability must not grow across cycles
- If violated → automatic contraction
- No exception paths

This applies even if S(t) is still above threshold.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger("recursive_stability_controller.lyapunov_monitor")


@dataclass
class LyapunovState:
    """Lyapunov function state"""

    # Lyapunov function value
    V_t: float  # Vₜ = Rₜ²

    # Underlying recursion energy
    R_t: float

    # Change in Lyapunov function
    delta_V: Optional[float]  # ΔVₜ = Vₜ - Vₜ₋₁

    # Metadata
    timestamp: float
    cycle_id: int

    # Stability check
    is_stable: bool  # ΔVₜ ≤ 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "V_t": self.V_t,
            "R_t": self.R_t,
            "delta_V": self.delta_V,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "is_stable": self.is_stable
        }


@dataclass
class LyapunovViolation:
    """Lyapunov stability violation"""

    # Violation details
    cycle_id: int
    timestamp: float
    delta_V: float  # ΔVₜ > 0
    V_current: float
    V_previous: float

    # Severity
    severity: str  # "minor", "moderate", "severe"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "delta_V": self.delta_V,
            "V_current": self.V_current,
            "V_previous": self.V_previous,
            "severity": self.severity
        }


class LyapunovMonitor:
    """
    Monitor Lyapunov stability guarantee.

    Ensures that instability (measured by Vₜ = Rₜ²) does not grow
    across control cycles.

    This is a HARD CONSTRAINT - violations trigger automatic contraction.
    """

    def __init__(self):
        """Initialize Lyapunov monitor"""
        self.history = []
        self.violations = []
        self.max_history = 1000
        self.previous_V = None
        self.consecutive_violations = 0

    def update(
        self,
        recursion_energy: float,
        timestamp: float,
        cycle_id: int
    ) -> LyapunovState:
        """
        Update Lyapunov monitor with new recursion energy.

        Args:
            recursion_energy: Current recursion energy Rₜ
            timestamp: Current timestamp
            cycle_id: Current cycle ID

        Returns:
            LyapunovState with stability check
        """
        # Compute Lyapunov function
        V_t = recursion_energy ** 2

        # Compute change in Lyapunov function
        if self.previous_V is not None:
            delta_V = V_t - self.previous_V
            is_stable = delta_V <= 0

            # Check for violation
            if delta_V > 0:
                self._record_violation(
                    cycle_id, timestamp, delta_V, V_t, self.previous_V
                )
                self.consecutive_violations += 1
            else:
                self.consecutive_violations = 0
        else:
            # First cycle - no previous value
            delta_V = None
            is_stable = True

        # Create Lyapunov state
        state = LyapunovState(
            V_t=V_t,
            R_t=recursion_energy,
            delta_V=delta_V,
            timestamp=timestamp,
            cycle_id=cycle_id,
            is_stable=is_stable
        )

        # Record in history
        self._record_history(state)

        # Update previous value
        self.previous_V = V_t

        return state

    def check_stability(self) -> bool:
        """
        Check if Lyapunov stability is satisfied.

        Returns:
            True if ΔVₜ ≤ 0, False otherwise
        """
        if not self.history:
            return True

        latest = self.history[-1]
        return latest["is_stable"]

    def get_consecutive_violations(self) -> int:
        """
        Get number of consecutive Lyapunov violations.

        Returns:
            Number of consecutive violations
        """
        return self.consecutive_violations

    def _record_violation(
        self,
        cycle_id: int,
        timestamp: float,
        delta_V: float,
        V_current: float,
        V_previous: float
    ):
        """Record Lyapunov violation"""
        # Determine severity
        if delta_V < 0.01:
            severity = "minor"
        elif delta_V < 0.1:
            severity = "moderate"
        else:
            severity = "severe"

        violation = LyapunovViolation(
            cycle_id=cycle_id,
            timestamp=timestamp,
            delta_V=delta_V,
            V_current=V_current,
            V_previous=V_previous,
            severity=severity
        )

        self.violations.append(violation)

        logger.info(f"[VIOLATION] Lyapunov stability violated at cycle {cycle_id}")
        logger.info(f"  ΔVₜ = {delta_V:.6f} > 0 (severity: {severity})")
        logger.info(f"  Vₜ = {V_current:.6f}, Vₜ₋₁ = {V_previous:.6f}")

    def _record_history(self, state: LyapunovState):
        """Record Lyapunov state in history"""
        self.history.append({
            "cycle_id": state.cycle_id,
            "timestamp": state.timestamp,
            "V_t": state.V_t,
            "R_t": state.R_t,
            "delta_V": state.delta_V,
            "is_stable": state.is_stable
        })

        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, n: int = None) -> List[Dict]:
        """
        Get Lyapunov history.

        Args:
            n: Number of recent entries (all if None)

        Returns:
            List of history entries
        """
        if n is None:
            return self.history
        return self.history[-n:]

    def get_violations(self, n: int = None) -> List[LyapunovViolation]:
        """
        Get Lyapunov violations.

        Args:
            n: Number of recent violations (all if None)

        Returns:
            List of violations
        """
        if n is None:
            return self.violations
        return self.violations[-n:]

    def get_statistics(self) -> Dict:
        """
        Get statistics on Lyapunov function.

        Returns:
            Dictionary with mean, std, min, max, violation_rate
        """
        if not self.history:
            return {
                "mean_V": 0.0,
                "std_V": 0.0,
                "min_V": 0.0,
                "max_V": 0.0,
                "mean_delta_V": 0.0,
                "violation_rate": 0.0,
                "violation_count": 0,
                "consecutive_violations": 0,
                "count": 0
            }

        V_values = [h["V_t"] for h in self.history]
        delta_V_values = [h["delta_V"] for h in self.history if h["delta_V"] is not None]
        violation_count = sum(1 for h in self.history if not h["is_stable"])

        return {
            "mean_V": np.mean(V_values),
            "std_V": np.std(V_values),
            "min_V": np.min(V_values),
            "max_V": np.max(V_values),
            "mean_delta_V": np.mean(delta_V_values) if delta_V_values else 0.0,
            "violation_rate": violation_count / (len(self.history) or 1),
            "violation_count": violation_count,
            "consecutive_violations": self.consecutive_violations,
            "count": len(self.history)
        }

    def check_stability_window(self, window_size: int = 5) -> bool:
        """
        Check if Lyapunov stability has been satisfied for a window.

        Used for re-expansion criteria: ΔVₜ ≤ 0 for N consecutive cycles.

        Args:
            window_size: Number of consecutive cycles (N)

        Returns:
            True if stable for entire window, False otherwise
        """
        if len(self.history) < window_size:
            return False

        recent = self.history[-window_size:]
        return all(h["is_stable"] for h in recent)

    def reset(self):
        """Reset monitor (use with caution)"""
        self.previous_V = None
        self.consecutive_violations = 0
        logger.info("[INFO] Lyapunov monitor reset")
