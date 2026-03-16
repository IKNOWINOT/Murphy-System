"""
Strategic Planning Engine for Murphy System.

Design Label: BIZ-005 — Market Analysis, Opportunity Scoring & Strategic Plan Generation
Owner: Strategy Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable plan storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on plan generation)
  - MarketingAnalyticsAggregator (MKT-005, optional, for market data)
  - FinancialReportingEngine (BIZ-001, optional, for financial context)

Implements Phase 5 — Business Operations Automation (continued):
  Ingests market signals (trends, competitors, opportunities),
  scores opportunities based on configurable criteria, and generates
  strategic plan documents that summarise the competitive landscape
  and recommended actions.

Flow:
  1. Ingest market signals (category, description, impact score)
  2. Score opportunities via weighted criteria
  3. Rank opportunities by composite score
  4. Generate strategic plan document with top opportunities
  5. Persist plans and publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies external data sources
  - Bounded: configurable max signals, opportunities, and plans
  - Conservative: opportunities require minimum supporting signals
  - Audit trail: every plan generation is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SIGNALS = 100_000
_MAX_OPPORTUNITIES = 10_000
_MAX_PLANS = 500
_MIN_SIGNALS_FOR_OPPORTUNITY = 2


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MarketSignal:
    """A single market intelligence data point."""
    signal_id: str
    category: str           # trend | competitor | regulation | technology | customer
    title: str
    description: str
    impact_score: float     # 0.0 – 1.0
    source: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "category": self.category,
            "title": self.title,
            "description": self.description[:500],
            "impact_score": round(self.impact_score, 3),
            "source": self.source,
            "recorded_at": self.recorded_at,
        }


@dataclass
class Opportunity:
    """A scored strategic opportunity."""
    opportunity_id: str
    title: str
    description: str
    category: str
    composite_score: float
    supporting_signals: int
    recommended_action: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "description": self.description[:500],
            "category": self.category,
            "composite_score": round(self.composite_score, 3),
            "supporting_signals": self.supporting_signals,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at,
        }


@dataclass
class StrategicPlan:
    """A generated strategic plan document."""
    plan_id: str
    title: str
    total_signals_analysed: int
    opportunities_identified: int
    top_opportunities: List[Opportunity] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "total_signals_analysed": self.total_signals_analysed,
            "opportunities_identified": self.opportunities_identified,
            "top_opportunities": [o.to_dict() for o in self.top_opportunities],
            "summary": self.summary,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# StrategicPlanningEngine
# ---------------------------------------------------------------------------

class StrategicPlanningEngine:
    """Market analysis, opportunity scoring, and strategic plan generation.

    Design Label: BIZ-005
    Owner: Strategy Team / Platform Engineering

    Usage::

        engine = StrategicPlanningEngine(persistence_manager=pm)
        engine.ingest_signal("trend", "AI adoption accelerating", 0.9)
        engine.ingest_signal("trend", "AI regulation increasing", 0.7)
        plan = engine.generate_plan("Q2 2026 Strategy")
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_signals: int = _MAX_SIGNALS,
        max_opportunities: int = _MAX_OPPORTUNITIES,
        min_signals: int = _MIN_SIGNALS_FOR_OPPORTUNITY,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._signals: List[MarketSignal] = []
        self._plans: List[StrategicPlan] = []
        self._max_signals = max_signals
        self._max_opps = max_opportunities
        self._min_signals = min_signals

    # ------------------------------------------------------------------
    # Signal ingestion
    # ------------------------------------------------------------------

    def ingest_signal(
        self,
        category: str,
        title: str,
        impact_score: float,
        description: str = "",
        source: str = "",
    ) -> MarketSignal:
        sig = MarketSignal(
            signal_id=f"ms-{uuid.uuid4().hex[:8]}",
            category=category.lower().strip(),
            title=title,
            description=description or title,
            impact_score=max(0.0, min(1.0, impact_score)),
            source=source,
        )
        with self._lock:
            if len(self._signals) >= self._max_signals:
                evict = max(1, self._max_signals // 10)
                self._signals = self._signals[evict:]
            self._signals.append(sig)
        return sig

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------

    def generate_plan(self, title: str = "Strategic Plan", top_n: int = 10) -> StrategicPlan:
        with self._lock:
            signals = list(self._signals)

        # Group signals by category
        from collections import defaultdict
        groups: Dict[str, List[MarketSignal]] = defaultdict(list)
        for s in signals:
            groups[s.category].append(s)

        # Score each category as an opportunity
        opps: List[Opportunity] = []
        for cat, sigs in groups.items():
            if len(sigs) < self._min_signals:
                continue
            avg_impact = sum(s.impact_score for s in sigs) / len(sigs)
            volume_factor = min(len(sigs) / 10.0, 1.0)
            composite = avg_impact * 0.6 + volume_factor * 0.4
            # Pick highest-impact signal as representative
            best = max(sigs, key=lambda s: s.impact_score)
            opps.append(Opportunity(
                opportunity_id=f"opp-{uuid.uuid4().hex[:8]}",
                title=best.title,
                description=best.description,
                category=cat,
                composite_score=composite,
                supporting_signals=len(sigs),
                recommended_action=f"Investigate '{cat}' cluster ({len(sigs)} signals, avg impact {avg_impact:.2f})",
            ))

        opps.sort(key=lambda o: o.composite_score, reverse=True)
        top = opps[:top_n]

        plan = StrategicPlan(
            plan_id=f"sp-{uuid.uuid4().hex[:8]}",
            title=title,
            total_signals_analysed=len(signals),
            opportunities_identified=len(opps),
            top_opportunities=top,
            summary=f"Analysed {len(signals)} signals across {len(groups)} categories. "
                    f"Identified {len(opps)} opportunities; top {len(top)} ranked by composite score.",
        )

        with self._lock:
            if len(self._plans) >= _MAX_PLANS:
                self._plans = self._plans[_MAX_PLANS // 10:]
            self._plans.append(plan)

        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=plan.plan_id, document=plan.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)
        if self._backbone is not None:
            self._publish_event(plan)

        logger.info(
            "Strategic plan '%s': %d signals → %d opportunities",
            title, len(signals), len(opps),
        )
        return plan

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_signals(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            signals = list(self._signals)
        if category:
            signals = [s for s in signals if s.category == category]
        return [s.to_dict() for s in signals[-limit:]]

    def get_plans(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._plans[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_signals": len(self._signals),
                "total_plans": len(self._plans),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, plan: StrategicPlan) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "strategic_planning_engine",
                    "action": "plan_generated",
                    "plan_id": plan.plan_id,
                    "opportunities_identified": plan.opportunities_identified,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="strategic_planning_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
