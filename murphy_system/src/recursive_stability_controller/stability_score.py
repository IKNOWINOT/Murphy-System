"""
Stability Score Calculator

Computes the primary stability score S(t):

    S(t) = 1 / (1 + Rₜ)

Properties:
- S(t) ∈ (0, 1]
- Higher = safer
- Strictly decreasing in Rₜ

All decisions are made using S(t), never raw Rₜ.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StabilityScore:
    """Stability score with metadata"""

    # Primary stability score
    score: float  # S(t) ∈ (0, 1]

    # Underlying recursion energy
    recursion_energy: float  # Rₜ ≥ 0

    # Metadata
    timestamp: float
    cycle_id: int

    # Threshold comparison
    is_stable: bool  # S(t) ≥ S_min

    def validate(self) -> bool:
        """Validate stability score"""
        if not (0.0 < self.score <= 1.0):
            return False
        if self.recursion_energy < 0.0:
            return False
        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "score": self.score,
            "recursion_energy": self.recursion_energy,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "is_stable": self.is_stable
        }


class StabilityScoreCalculator:
    """
    Calculate stability score from recursion energy.

    The stability score is the only externally actionable metric.
    All control decisions are based on S(t), not Rₜ.
    """

    # Stability threshold (as approved)
    S_MIN = 0.7

    # Expansion threshold
    S_EXPANSION = 0.85

    def __init__(self, s_min: float = None):
        """
        Initialize calculator.

        Args:
            s_min: Minimum stability threshold (uses default if None)
        """
        self.s_min = s_min or self.S_MIN

        # Validate threshold
        if not (0.0 < self.s_min < 1.0):
            raise ValueError(f"Invalid s_min: {self.s_min}, must be in (0, 1)")

        # History
        self.history = []
        self.max_history = 1000

    def calculate(
        self,
        recursion_energy: float,
        timestamp: float,
        cycle_id: int
    ) -> StabilityScore:
        """
        Calculate stability score from recursion energy.

        Formula:
            S(t) = 1 / (1 + Rₜ)

        Args:
            recursion_energy: Recursion energy Rₜ
            timestamp: Current timestamp
            cycle_id: Current cycle ID

        Returns:
            StabilityScore object
        """
        # Ensure non-negative
        R_t = max(0.0, recursion_energy)

        # Calculate stability score
        S_t = 1.0 / (1.0 + R_t)

        # Check if stable
        is_stable = S_t >= self.s_min

        # Create stability score
        score = StabilityScore(
            score=S_t,
            recursion_energy=R_t,
            timestamp=timestamp,
            cycle_id=cycle_id,
            is_stable=is_stable
        )

        # Record in history
        self._record_history(score)

        return score

    def get_stability_level(self, score: float) -> str:
        """
        Get stability level from score.

        Levels:
        - "critical": S(t) < 0.5
        - "unstable": 0.5 ≤ S(t) < S_min
        - "stable": S_min ≤ S(t) < S_expansion
        - "highly_stable": S(t) ≥ S_expansion

        Args:
            score: Stability score

        Returns:
            Stability level string
        """
        if score < 0.5:
            return "critical"
        elif score < self.s_min:
            return "unstable"
        elif score < self.S_EXPANSION:
            return "stable"
        else:
            return "highly_stable"

    def get_control_mode(self, score: float) -> str:
        """
        Get control mode from stability score.

        Modes:
        - "emergency": S(t) < 0.5 - immediate freeze
        - "contraction": S(t) < S_min - reduce activity
        - "normal": S_min ≤ S(t) < S_expansion - normal operation
        - "expansion": S(t) ≥ S_expansion - allow growth

        Args:
            score: Stability score

        Returns:
            Control mode string
        """
        if score < 0.5:
            return "emergency"
        elif score < self.s_min:
            return "contraction"
        elif score < self.S_EXPANSION:
            return "normal"
        else:
            return "expansion"

    def _record_history(self, score: StabilityScore):
        """Record stability score in history"""
        self.history.append({
            "cycle_id": score.cycle_id,
            "timestamp": score.timestamp,
            "score": score.score,
            "recursion_energy": score.recursion_energy,
            "is_stable": score.is_stable
        })

        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, n: int = None) -> List[Dict]:
        """
        Get stability score history.

        Args:
            n: Number of recent entries (all if None)

        Returns:
            List of history entries
        """
        if n is None:
            return self.history
        return self.history[-n:]

    def get_statistics(self) -> Dict:
        """
        Get statistics on stability scores.

        Returns:
            Dictionary with mean, std, min, max, trend, stability_rate
        """
        if not self.history:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "trend": 0.0,
                "stability_rate": 0.0,
                "count": 0
            }

        scores = [h["score"] for h in self.history]
        stable_count = sum(1 for h in self.history if h["is_stable"])

        # Compute trend (linear regression slope)
        if len(scores) >= 3:
            x = np.arange(len(scores))
            trend = np.polyfit(x, scores, 1)[0]
        else:
            trend = 0.0

        return {
            "mean": np.mean(scores),
            "std": np.std(scores),
            "min": np.min(scores),
            "max": np.max(scores),
            "trend": trend,
            "stability_rate": stable_count / (len(self.history) or 1),
            "count": len(self.history)
        }

    def check_stability_window(self, window_size: int = 5) -> bool:
        """
        Check if system has been stable for a window of cycles.

        Used for re-expansion criteria.

        Args:
            window_size: Number of consecutive cycles to check

        Returns:
            True if stable for entire window, False otherwise
        """
        if len(self.history) < window_size:
            return False

        recent = self.history[-window_size:]
        return all(h["is_stable"] for h in recent)

    def get_recent_trend(self, window_size: int = 10) -> str:
        """
        Get recent stability trend.

        Args:
            window_size: Number of recent cycles to analyze

        Returns:
            "improving", "stable", or "degrading"
        """
        if len(self.history) < window_size:
            return "stable"

        recent = self.history[-window_size:]
        scores = [h["score"] for h in recent]

        # Compute trend
        x = np.arange(len(scores))
        trend = np.polyfit(x, scores, 1)[0]

        if trend > 0.01:
            return "improving"
        elif trend < -0.01:
            return "degrading"
        else:
            return "stable"
