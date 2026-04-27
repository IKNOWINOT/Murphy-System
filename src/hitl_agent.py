"""
PATCH-130 — src/hitl_agent.py
Murphy System — HITL Gate Agent (position 8 / RosettaSoul)
Human-in-the-loop gate: queues high-stakes actions for human review.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.hitl")

# Stake levels that require human approval
HITL_REQUIRED_STAKES = {"high", "critical"}
HITL_THRESHOLD = 0.6  # soul hitl_threshold for this agent


class HitlAgent(AgentBase):
    """Position 8 — HITL Gate. Cautious, bias: human_oversight."""

    def __init__(self):
        super().__init__("hitl")
        self._pending: list = []

    def act(self, signal: Dict) -> Dict:
        """Decide if an action needs human review. Queue it if so."""
        stake    = signal.get("stake", "low")
        action   = signal.get("action", "")
        p_harm   = float(signal.get("p_harm", 0.0))
        auto_approve = signal.get("auto_approve", False)

        requires_hitl = (
            stake in HITL_REQUIRED_STAKES
            or p_harm >= HITL_THRESHOLD
        ) and not auto_approve

        if requires_hitl:
            item = {
                "id": f"hitl-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                "action": action,
                "stake": stake,
                "p_harm": p_harm,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            }
            self._pending.append(item)
            logger.info("HitlAgent: queued for human review — %s (stake=%s p_harm=%.2f)", action[:60], stake, p_harm)
            return {"status": "queued_for_hitl", "item": item, "pending_count": len(self._pending)}

        return {
            "status": "approved",
            "action": action,
            "stake": stake,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def pending_queue(self) -> list:
        return [i for i in self._pending if i["status"] == "pending"]

    def approve(self, item_id: str) -> bool:
        for item in self._pending:
            if item["id"] == item_id:
                item["status"] = "approved"
                return True
        return False

    def reject(self, item_id: str) -> bool:
        for item in self._pending:
            if item["id"] == item_id:
                item["status"] = "rejected"
                return True
        return False


_hitl: Optional[HitlAgent] = None

def get_hitl_agent() -> HitlAgent:
    global _hitl
    if _hitl is None:
        _hitl = HitlAgent()
    return _hitl
