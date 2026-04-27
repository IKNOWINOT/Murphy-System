"""
PATCH-130 — src/rosetta_agent.py
Murphy System — Rosetta Agent (position 9 / RosettaSoul)
The soul itself as an agent — governs all others, enforces the north star.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.rosetta")


class RosettaAgent(AgentBase):
    """
    Position 9 — Rosetta. Wise, bias: alignment.
    The soul as an agent — final arbiter of all actions against the north star.
    """

    NORTH_STAR = (
        "Murphy's Law: What can go wrong, will go wrong. "
        "Our vow: shield humanity from every failure AI can cause "
        "by anticipating it, naming it, and standing in front of it."
    )

    def __init__(self):
        super().__init__("rosetta")

    def act(self, signal: Dict) -> Dict:
        """
        Final alignment check: does this action serve the north star?
        Returns aligned=True/False with a reason.
        """
        action  = signal.get("action", "")
        domain  = signal.get("domain", "general")
        p_harm  = float(signal.get("p_harm", 0.0))

        # Hard block: physical harm above threshold
        if p_harm >= 0.65:
            return {
                "status": "blocked",
                "aligned": False,
                "reason": f"p_harm={p_harm:.2f} exceeds hard floor 0.65 — blocked per PCC",
                "north_star": self.NORTH_STAR,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Alignment check: does the action serve shielding humanity?
        action_lower = action.lower()
        anti_patterns = ["delete all", "disable auth", "bypass shield", "ignore pcc", "skip hitl"]
        for pattern in anti_patterns:
            if pattern in action_lower:
                return {
                    "status": "blocked",
                    "aligned": False,
                    "reason": f"Action matches anti-pattern '{pattern}' — misaligned with north star",
                    "north_star": self.NORTH_STAR,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "status": "aligned",
            "aligned": True,
            "action": action,
            "domain": domain,
            "north_star": self.NORTH_STAR,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def alignment_score(self, action: str) -> float:
        """Quick 0–1 alignment score for an action string."""
        action_lower = action.lower()
        shield_words  = ["shield", "protect", "prevent", "detect", "audit", "monitor", "warn", "block"]
        harm_words    = ["delete", "disable", "bypass", "ignore", "skip", "override", "expose"]
        score = 0.5
        score += 0.05 * sum(1 for w in shield_words if w in action_lower)
        score -= 0.1  * sum(1 for w in harm_words   if w in action_lower)
        return max(0.0, min(1.0, score))


_rosetta_agent: Optional[RosettaAgent] = None

def get_rosetta_agent() -> RosettaAgent:
    global _rosetta_agent
    if _rosetta_agent is None:
        _rosetta_agent = RosettaAgent()
    return _rosetta_agent
