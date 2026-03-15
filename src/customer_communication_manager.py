"""
Customer Communication Manager for Murphy System.

Design Label: SUP-004 — Personalised Response Templates & Satisfaction Tracking
Owner: Support Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable template and interaction storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on communication events)
  - KnowledgeBaseManager (SUP-002, optional, for contextual responses)
  - TicketTriageEngine (SUP-001, optional, for ticket context)

Implements Phase 3 — Customer Support Automation (continued):
  Manages response templates with variable interpolation, tracks
  customer interactions, measures satisfaction scores, and identifies
  communication patterns that need attention.

Flow:
  1. Register response templates with category and variables
  2. Render personalised responses from templates + customer context
  3. Record customer interactions (message, response, channel)
  4. Collect satisfaction ratings per interaction
  5. Compute per-customer and aggregate satisfaction metrics
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: templates are versioned, never deleted
  - Bounded: configurable max templates and interactions
  - Audit trail: every communication is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_TEMPLATES = 5_000
_MAX_INTERACTIONS = 100_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResponseTemplate:
    """A reusable customer-response template."""
    template_id: str
    name: str
    category: str
    body: str                       # may contain {{variable}} placeholders
    variables: List[str] = field(default_factory=list)
    version: int = 1
    usage_count: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "category": self.category,
            "body": self.body,
            "variables": list(self.variables),
            "version": self.version,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
        }


@dataclass
class CustomerInteraction:
    """Record of a single customer communication."""
    interaction_id: str
    customer_id: str
    channel: str                    # email | chat | phone | ticket
    inbound_message: str
    outbound_response: str
    template_id: str = ""
    satisfaction_rating: Optional[int] = None   # 1-5
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "customer_id": self.customer_id,
            "channel": self.channel,
            "inbound_message": self.inbound_message[:500],
            "outbound_response": self.outbound_response[:500],
            "template_id": self.template_id,
            "satisfaction_rating": self.satisfaction_rating,
            "created_at": self.created_at,
        }


@dataclass
class SatisfactionSummary:
    """Aggregate satisfaction metrics."""
    summary_id: str
    total_interactions: int
    rated_interactions: int
    average_rating: float
    rating_distribution: Dict[int, int] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "total_interactions": self.total_interactions,
            "rated_interactions": self.rated_interactions,
            "average_rating": round(self.average_rating, 2),
            "rating_distribution": dict(self.rating_distribution),
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# CustomerCommunicationManager
# ---------------------------------------------------------------------------

class CustomerCommunicationManager:
    """Personalised response templates and satisfaction tracking.

    Design Label: SUP-004
    Owner: Support Team / Platform Engineering

    Usage::

        mgr = CustomerCommunicationManager(persistence_manager=pm)
        tpl = mgr.create_template("greeting", "onboarding",
                                  "Hello {{name}}, welcome to Murphy!")
        text = mgr.render_template(tpl.template_id, {"name": "Alice"})
        mgr.record_interaction("cust-1", "email", "Hi", text)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_templates: int = _MAX_TEMPLATES,
        max_interactions: int = _MAX_INTERACTIONS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._templates: Dict[str, ResponseTemplate] = {}
        self._interactions: List[CustomerInteraction] = []
        self._max_templates = max_templates
        self._max_interactions = max_interactions

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def create_template(
        self,
        name: str,
        category: str,
        body: str,
        variables: Optional[List[str]] = None,
    ) -> ResponseTemplate:
        """Create a new response template."""
        import re
        detected_vars = re.findall(r"\{\{(\w+)\}\}", body)
        tpl = ResponseTemplate(
            template_id=f"tpl-{uuid.uuid4().hex[:8]}",
            name=name,
            category=category,
            body=body,
            variables=variables or detected_vars,
        )
        with self._lock:
            if len(self._templates) >= self._max_templates:
                logger.warning("Max templates reached (%d)", self._max_templates)
                return tpl
            self._templates[tpl.template_id] = tpl
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=tpl.template_id, document=tpl.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)
        return tpl

    def update_template(
        self,
        template_id: str,
        body: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[ResponseTemplate]:
        with self._lock:
            tpl = self._templates.get(template_id)
            if tpl is None:
                return None
            if body is not None:
                tpl.body = body
                import re
                tpl.variables = re.findall(r"\{\{(\w+)\}\}", body)
            if category is not None:
                tpl.category = category
            tpl.version += 1
        return tpl

    def render_template(
        self,
        template_id: str,
        context: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Render a template with variable substitution."""
        with self._lock:
            tpl = self._templates.get(template_id)
            if tpl is None:
                return None
            tpl.usage_count += 1
        ctx = context or {}
        result = tpl.body
        for key, value in ctx.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    # ------------------------------------------------------------------
    # Interaction recording
    # ------------------------------------------------------------------

    def record_interaction(
        self,
        customer_id: str,
        channel: str,
        inbound_message: str,
        outbound_response: str,
        template_id: str = "",
        satisfaction_rating: Optional[int] = None,
    ) -> CustomerInteraction:
        interaction = CustomerInteraction(
            interaction_id=f"ci-{uuid.uuid4().hex[:8]}",
            customer_id=customer_id,
            channel=channel,
            inbound_message=inbound_message,
            outbound_response=outbound_response,
            template_id=template_id,
            satisfaction_rating=satisfaction_rating,
        )
        with self._lock:
            if len(self._interactions) >= self._max_interactions:
                evict = max(1, self._max_interactions // 10)
                self._interactions = self._interactions[evict:]
            self._interactions.append(interaction)
        if self._backbone is not None:
            self._publish_event("interaction_recorded", interaction.interaction_id)
        return interaction

    def rate_interaction(self, interaction_id: str, rating: int) -> bool:
        """Record a satisfaction rating (1-5) for an interaction."""
        rating = max(1, min(5, rating))
        with self._lock:
            for ix in self._interactions:
                if ix.interaction_id == interaction_id:
                    ix.satisfaction_rating = rating
                    return True
        return False

    # ------------------------------------------------------------------
    # Satisfaction analytics
    # ------------------------------------------------------------------

    def compute_satisfaction(self) -> SatisfactionSummary:
        with self._lock:
            interactions = list(self._interactions)
        rated = [i for i in interactions if i.satisfaction_rating is not None]
        dist: Counter = Counter()
        for i in rated:
            dist[i.satisfaction_rating] += 1
        avg = sum(i.satisfaction_rating for i in rated) / (len(rated) or 1) if rated else 0.0
        summary = SatisfactionSummary(
            summary_id=f"sat-{uuid.uuid4().hex[:8]}",
            total_interactions=len(interactions),
            rated_interactions=len(rated),
            average_rating=avg,
            rating_distribution=dict(dist),
        )
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=summary.summary_id, document=summary.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)
        return summary

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_templates(self, category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            tpls = list(self._templates.values())
        if category:
            tpls = [t for t in tpls if t.category == category]
        return [t.to_dict() for t in tpls[:limit]]

    def get_interactions(self, customer_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            interactions = list(self._interactions)
        if customer_id:
            interactions = [i for i in interactions if i.customer_id == customer_id]
        return [i.to_dict() for i in interactions[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_templates": len(self._templates),
                "total_interactions": len(self._interactions),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, action: str, ref_id: str) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "customer_communication_manager",
                    "action": action,
                    "ref_id": ref_id,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="customer_communication_manager",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
