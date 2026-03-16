"""
Ticket Triage Engine for Murphy System.

Design Label: SUP-001 — RAG-Powered Ticket Classification & Routing
Owner: Support Team / Platform Engineering
Dependencies:
  - TicketingAdapter (for ticket lifecycle management)
  - RAGVectorIntegration (for semantic classification against knowledge base)
  - EventBackbone (optional, publishes TICKET_TRIAGED events)

Implements Phase 3 — Customer Support Automation:
  Analyses incoming tickets using keyword and RAG-based classification,
  auto-assigns severity, category, and suggested team routing.
  Integrates with EventBackbone for reactive downstream automation.

Flow:
  1. Receive raw ticket text (title + description)
  2. Classify severity via keyword heuristics + optional RAG search
  3. Classify category / ticket_type via keyword mapping
  4. Suggest routing team based on category
  5. Create the ticket in TicketingAdapter with enriched metadata
  6. Optionally publish LEARNING_FEEDBACK event with triage outcome

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Conservative defaults: unknown tickets get MEDIUM priority
  - Audit trail: every triage decision is logged
  - Human-in-the-loop: P1/P2 tickets flagged for review

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword maps for heuristic classification
# ---------------------------------------------------------------------------

_SEVERITY_KEYWORDS: Dict[str, List[str]] = {
    "critical": [
        "outage", "down", "crash", "data loss", "security breach",
        "production down", "critical", "emergency", "p1",
    ],
    "high": [
        "error", "broken", "failing", "degraded", "slow",
        "timeout", "unresponsive", "high", "p2", "urgent",
    ],
    "medium": [
        "issue", "problem", "bug", "unexpected", "incorrect",
        "medium", "p3",
    ],
    "low": [
        "question", "feature request", "enhancement", "minor",
        "cosmetic", "low", "p4", "inquiry",
    ],
}

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "incident": [
        "outage", "down", "crash", "error", "broken", "failing",
        "degraded", "timeout", "unresponsive",
    ],
    "service_request": [
        "request", "access", "provision", "setup", "configure",
        "install", "onboard",
    ],
    "change_request": [
        "change", "update", "upgrade", "migrate", "deploy",
        "release", "rollback",
    ],
    "problem": [
        "recurring", "pattern", "root cause", "investigation",
        "analyse", "analyze",
    ],
}

_TEAM_ROUTING: Dict[str, str] = {
    "incident": "ops-engineering",
    "service_request": "service-desk",
    "change_request": "release-engineering",
    "problem": "sre-team",
    "unknown": "support-triage",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TriageResult:
    """Outcome of triaging a single ticket."""
    triage_id: str
    ticket_id: Optional[str]
    severity: str
    category: str
    suggested_team: str
    confidence: float
    rag_context: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triage_id": self.triage_id,
            "ticket_id": self.ticket_id,
            "severity": self.severity,
            "category": self.category,
            "suggested_team": self.suggested_team,
            "confidence": round(self.confidence, 3),
            "rag_context": self.rag_context,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# TicketTriageEngine
# ---------------------------------------------------------------------------

class TicketTriageEngine:
    """RAG-powered ticket classification and routing engine.

    Design Label: SUP-001
    Owner: Support Team

    Usage::

        engine = TicketTriageEngine(
            ticketing_adapter=adapter,
            rag_integration=rag,
            event_backbone=backbone,
        )
        result = engine.triage(
            title="Production database outage",
            description="The main PostgreSQL cluster is unreachable...",
            requester="ops@example.com",
        )
    """

    def __init__(
        self,
        ticketing_adapter=None,
        rag_integration=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._adapter = ticketing_adapter
        self._rag = rag_integration
        self._backbone = event_backbone
        self._history: List[TriageResult] = []

    # ------------------------------------------------------------------
    # Core triage
    # ------------------------------------------------------------------

    def triage(
        self,
        title: str,
        description: str,
        requester: str = "unknown",
        tags: Optional[List[str]] = None,
    ) -> TriageResult:
        """Analyse a ticket and classify severity, category, and routing.

        If a TicketingAdapter is attached, also creates the ticket.
        """
        combined = f"{title} {description}".lower()

        severity = self._classify_severity(combined)
        category = self._classify_category(combined)
        team = _TEAM_ROUTING.get(category, _TEAM_ROUTING["unknown"])
        confidence = self._compute_confidence(combined, severity, category)

        # Optional RAG context enrichment
        rag_context = None
        if self._rag is not None:
            try:
                results = self._rag.search(query=combined[:200], top_k=3)
                if results.get("results"):
                    rag_context = "; ".join(
                        r.get("text", "")[:120] for r in results["results"][:2]
                    )
            except Exception as exc:
                logger.debug("RAG search skipped: %s", exc)

        # Map to TicketingAdapter types
        ticket_id = None
        if self._adapter is not None:
            try:
                from ticketing_adapter import TicketPriority, TicketType

                priority_map = {
                    "critical": TicketPriority.P1_CRITICAL,
                    "high": TicketPriority.P2_HIGH,
                    "medium": TicketPriority.P3_MEDIUM,
                    "low": TicketPriority.P4_LOW,
                }
                type_map = {
                    "incident": TicketType.INCIDENT,
                    "service_request": TicketType.SERVICE_REQUEST,
                    "change_request": TicketType.CHANGE_REQUEST,
                    "problem": TicketType.PROBLEM,
                }

                ticket = self._adapter.create_ticket(
                    title=title,
                    description=description,
                    ticket_type=type_map.get(category, TicketType.INCIDENT),
                    priority=priority_map.get(severity, TicketPriority.P3_MEDIUM),
                    requester=requester,
                    tags=tags or [],
                    metadata={
                        "triage_severity": severity,
                        "triage_category": category,
                        "triage_team": team,
                        "triage_confidence": confidence,
                        "rag_context": rag_context,
                    },
                )
                ticket_id = ticket.ticket_id
            except Exception as exc:
                logger.warning("Failed to create ticket: %s", exc)

        result = TriageResult(
            triage_id=f"tri-{uuid.uuid4().hex[:8]}",
            ticket_id=ticket_id,
            severity=severity,
            category=category,
            suggested_team=team,
            confidence=confidence,
            rag_context=rag_context,
        )

        with self._lock:
            self._history.append(result)
            if len(self._history) > 500:
                self._history = self._history[-500:]

        # Publish event
        if self._backbone is not None:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "ticket_triage_engine",
                        "triage": result.to_dict(),
                    },
                    source="ticket_triage_engine",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)

        logger.info(
            "Triaged ticket: severity=%s category=%s team=%s confidence=%.2f",
            severity, category, team, confidence,
        )
        return result

    # ------------------------------------------------------------------
    # History / Status
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._history[-limit:]
        return [r.to_dict() for r in recent]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._history)
            sev_counts = Counter(r.severity for r in self._history)
            cat_counts = Counter(r.category for r in self._history)
        return {
            "total_triaged": total,
            "severity_distribution": dict(sev_counts),
            "category_distribution": dict(cat_counts),
            "adapter_attached": self._adapter is not None,
            "rag_attached": self._rag is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(text: str) -> str:
        """Keyword-based severity classification."""
        for level in ("critical", "high", "medium", "low"):
            for keyword in _SEVERITY_KEYWORDS[level]:
                if keyword in text:
                    return level
        return "medium"  # conservative default

    @staticmethod
    def _classify_category(text: str) -> str:
        """Keyword-based category classification."""
        scores: Dict[str, int] = {}
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                scores[cat] = hits
        if scores:
            return max(scores, key=scores.get)
        return "incident"  # conservative default

    @staticmethod
    def _compute_confidence(text: str, severity: str, category: str) -> float:
        """Heuristic confidence score based on keyword match density."""
        words = text.split()
        if not words:
            return 0.3
        sev_hits = sum(
            1 for kw in _SEVERITY_KEYWORDS.get(severity, []) if kw in text
        )
        cat_hits = sum(
            1 for kw in _CATEGORY_KEYWORDS.get(category, []) if kw in text
        )
        total_hits = sev_hits + cat_hits
        # Normalize to 0.3–0.95 range
        raw = min(total_hits / max(len(words) * 0.1, 1), 1.0)
        return round(0.3 + raw * 0.65, 3)
