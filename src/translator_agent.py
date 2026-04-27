"""
PATCH-130 — src/translator_agent.py
Murphy System — Translator Agent (position 2 / RosettaSoul)
Converts raw signals into structured intent + domain classification.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.translator")


class TranslatorAgent(AgentBase):
    """Position 2 — Translator. Precise, bias: fidelity."""

    DOMAIN_KEYWORDS = {
        "exec_admin":  ["email", "meeting", "schedule", "brief", "report", "approve"],
        "prod_ops":    ["deploy", "health", "incident", "error", "latency", "crash", "alert"],
        "compliance":  ["audit", "regulation", "policy", "gdpr", "hipaa", "sox", "risk"],
        "finance":     ["invoice", "payment", "revenue", "cost", "budget", "billing"],
        "tech":        ["code", "api", "database", "llm", "model", "patch", "debug"],
        "geopolitics": ["war", "conflict", "election", "sanction", "trade", "government"],
    }

    def __init__(self):
        super().__init__("translator")

    def act(self, signal: Dict) -> Dict:
        """Classify a signal into domain + urgency + intent."""
        raw = str(signal.get("raw_payload", signal.get("intent_hint", "")))
        raw_lower = raw.lower()

        # Domain classification
        domain_scores: Dict[str, int] = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in raw_lower)
            if score:
                domain_scores[domain] = score
        best_domain = max(domain_scores, key=domain_scores.get) if domain_scores else "general"

        # Urgency heuristic
        urgency = "low"
        if any(w in raw_lower for w in ("urgent", "critical", "alert", "crash", "down", "error")):
            urgency = "high"
        elif any(w in raw_lower for w in ("today", "asap", "now", "immediate")):
            urgency = "medium"

        return {
            "status": "translated",
            "domain": best_domain,
            "urgency": urgency,
            "intent_hint": raw[:120],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_translator: Optional[TranslatorAgent] = None

def get_translator_agent() -> TranslatorAgent:
    global _translator
    if _translator is None:
        _translator = TranslatorAgent()
    return _translator
