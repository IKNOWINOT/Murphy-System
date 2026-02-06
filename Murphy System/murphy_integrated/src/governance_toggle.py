"""
Governance Toggle - Simple policy mode switcher
"""

from __future__ import annotations

from typing import Dict


class GovernanceToggle:
    def __init__(self, initial_mode: str = "BALANCED"):
        self.current_mode = initial_mode

    def set_governance_mode(self, mode: str) -> None:
        self.current_mode = mode

    def requires_approval(self, action_type: str, risk_level: str = "medium") -> bool:
        if self.current_mode in {"HEAVY", "BALANCED"} and risk_level in {"high", "critical"}:
            return True
        if action_type in {"critical_operation", "security_change"}:
            return True
        return False
