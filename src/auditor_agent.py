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
        # PATCH-179: Skip breach counting for unidentified signals (agent_id="unknown")
        # and for internal housekeeping jobs that don't participate in dedup protocol.
        _SKIP_DEDUP_CHECK = {"heartbeat", "signal_drain", "corpus_collect", "health_watchdog", "unknown"}
        violations = []
        if agent_id not in _SKIP_DEDUP_CHECK and not outcome.get("dedup_checked"):
            violations.append("dedup_before_act")
        # report_to_auditor only applies to autonomous actions, not self-audit calls
        if agent_id not in _SKIP_DEDUP_CHECK and not outcome.get("reported") and outcome.get("autonomous"):
            violations.append("report_to_auditor")

        # Flag breaches — never count against "unknown" (signal has no valid owner)
        if violations and agent_id not in ("unknown", "", None):
            try:
                from src.rosetta_core import get_rosetta_soul
                soul = get_rosetta_soul()
                for v in violations:
                    soul.covenant_breach(agent_id)
                    logger.warning("AuditorAgent: covenant breach [%s] by %s", v, agent_id)
            except Exception:
                pass
        elif agent_id in ("unknown", "", None) and violations:
            logger.debug("AuditorAgent: signal with unknown agent_id — breach not counted (fix signal source)")

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
