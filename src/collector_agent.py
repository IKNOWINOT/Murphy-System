"""
PATCH-130 — src/collector_agent.py
Murphy System — Collector Agent (position 1 / RosettaSoul)
Gathers signals from the world: feeds, APIs, webhooks.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.collector")


class CollectorAgent(AgentBase):
    """Position 1 — Collector. Observant, bias: completeness."""

    def __init__(self):
        super().__init__("collector")

    def act(self, signal: Dict) -> Dict:
        """Ingest incoming signals into the corpus and signal store."""
        try:
            from src.signal_collector import get_collector
            result = get_collector().ingest(
                signal_type=signal.get("signal_type", "ambient"),
                source=signal.get("source", "unknown"),
                payload=signal.get("raw_payload", {}),
                domain=signal.get("domain", "general"),
                urgency=signal.get("urgency", "low"),
                intent_hint=signal.get("intent_hint", ""),
            )
            # Also push into world corpus if domain is news/tech
            domain = signal.get("domain", "")
            if domain in ("tech", "geopolitics", "finance"):
                try:
                    from src.world_corpus import get_world_corpus
                    get_world_corpus().collect_all()
                except Exception as exc:
                    logger.debug("CollectorAgent world_corpus refresh: %s", exc)
            return {"status": "collected", "signal_id": result, "timestamp": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            logger.warning("CollectorAgent.act error: %s", exc)
            return {"status": "error", "error": str(exc)}


_collector: Optional[CollectorAgent] = None

def get_collector_agent() -> CollectorAgent:
    global _collector
    if _collector is None:
        _collector = CollectorAgent()
    return _collector
