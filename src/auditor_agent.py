"""
PATCH-130 — src/auditor_agent.py
Murphy System — Auditor Agent (position 5 / RosettaSoul)
Verifies outcomes, records results, flags covenant breaches.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.auditor")


class AuditorAgent(AgentBase):
    """Position 5 — Auditor. Thorough, bias: accountability."""

    def __init__(self):
        super().__init__("auditor")

    def act(self, signal: Dict) -> Dict:
        """Audit an action outcome — record it and check for covenant breaches."""
        action   = signal.get("action", "")
        outcome  = signal.get("outcome", {})
        agent_id = signal.get("acting_agent", "unknown")
        domain   = signal.get("domain", "general")

        # Record in soul audit log
        try:
            from src.rosetta_core import get_rosetta_soul
            soul = get_rosetta_soul()
            soul.record(agent_id, action, outcome)
        except Exception as exc:
            logger.debug("AuditorAgent soul.record error: %s", exc)

        # Check for covenant violations
        violations = []
        if not outcome.get("dedup_checked"):
            violations.append("dedup_before_act")
        if not outcome.get("reported"):
            violations.append("report_to_auditor")

        # Flag breaches
        if violations:
            try:
                from src.rosetta_core import get_rosetta_soul
                soul = get_rosetta_soul()
                for v in violations:
                    soul.covenant_breach(agent_id)
                    logger.warning("AuditorAgent: covenant breach [%s] by %s", v, agent_id)
            except Exception:
                pass

        return {
            "status": "audited",
            "agent_id": agent_id,
            "action": action,
            "violations": violations,
            "outcome_status": outcome.get("status", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_auditor: Optional[AuditorAgent] = None

def get_auditor_agent() -> AuditorAgent:
    global _auditor
    if _auditor is None:
        _auditor = AuditorAgent()
    return _auditor
