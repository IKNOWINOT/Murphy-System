"""
Governance Toggle - Controls governance enforcement mode for the Murphy System.
"""

from typing import Optional


class GovernanceToggle:
    """
    Manages governance modes that control how much human oversight
    is required for system operations.
    """

    VALID_MODES = {"HEAVY", "BALANCED", "LIGHT", "AUTONOMOUS"}

    def __init__(self, initial_mode: str = "BALANCED"):
        if initial_mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode: {initial_mode}. Must be one of {self.VALID_MODES}")
        self._current_mode = initial_mode

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def set_governance_mode(self, mode: str) -> None:
        """Switch to a different governance mode."""
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {self.VALID_MODES}")
        self._current_mode = mode

    def requires_approval(self, action_type: str = "default", risk_level: str = "low") -> bool:
        """Determine whether an action requires human approval under the current mode."""
        if self._current_mode == "HEAVY":
            return True
        if self._current_mode == "BALANCED":
            return risk_level in ("high", "critical") or action_type in ("critical_operation",)
        if self._current_mode == "LIGHT":
            return risk_level == "critical"
        # AUTONOMOUS
        return False
