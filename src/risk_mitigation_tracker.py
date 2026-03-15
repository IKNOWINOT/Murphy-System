"""
Risk Mitigation Tracker for Murphy System.

Design Label: SAF-005 — Technical, Operational & Business Risk Tracking
Owner: Strategy Team / Security Team
Dependencies:
  - PersistenceManager (for durable risk register)
  - EventBackbone (publishes LEARNING_FEEDBACK on risk status changes)

Implements Plan §8 — Risk Mitigation:
  Maintains a risk register with technical, operational, and business
  risks.  Each risk has likelihood, impact, a mitigation plan, current
  status, and a scheduled review date.  Supports risk addition, status
  update, review scheduling, and summary reporting.

Flow:
  1. Register risks with category, likelihood, impact, mitigation plan
  2. Update risk status (open → mitigating → mitigated → accepted → closed)
  3. Schedule and track review dates
  4. Generate RiskSummary with counts per category and status
  5. Persist risk register and publish status change events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: configurable max risks and reviews
  - Audit trail: every status change is logged
  - Non-destructive: risks are never deleted, only status-changed

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RISKS = 1_000
_MAX_STATUS_HISTORY = 10_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RiskCategory(str, Enum):
    """Risk category (str subclass)."""
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    BUSINESS = "business"


class RiskStatus(str, Enum):
    """Risk status (str subclass)."""
    OPEN = "open"
    MITIGATING = "mitigating"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class Likelihood(str, Enum):
    """Likelihood (str subclass)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Impact(str, Enum):
    """Impact (str subclass)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_LIKELIHOOD_SCORE = {Likelihood.LOW: 1, Likelihood.MEDIUM: 2, Likelihood.HIGH: 3}
_IMPACT_SCORE = {Impact.LOW: 1, Impact.MEDIUM: 2, Impact.HIGH: 3}


@dataclass
class Risk:
    """A single tracked risk."""
    risk_id: str
    title: str
    category: RiskCategory
    likelihood: Likelihood
    impact: Impact
    mitigation_plan: str
    status: RiskStatus = RiskStatus.OPEN
    owner: str = ""
    review_date: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def risk_score(self) -> int:
        return _LIKELIHOOD_SCORE.get(self.likelihood, 0) * _IMPACT_SCORE.get(self.impact, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "title": self.title,
            "category": self.category.value,
            "likelihood": self.likelihood.value,
            "impact": self.impact.value,
            "risk_score": self.risk_score,
            "mitigation_plan": self.mitigation_plan,
            "status": self.status.value,
            "owner": self.owner,
            "review_date": self.review_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class StatusChange:
    """Record of a risk status transition."""
    change_id: str
    risk_id: str
    from_status: str
    to_status: str
    reason: str = ""
    changed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "risk_id": self.risk_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "changed_at": self.changed_at,
        }


@dataclass
class RiskSummary:
    """Aggregate summary of the risk register."""
    summary_id: str
    total_risks: int
    by_category: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    by_likelihood: Dict[str, int] = field(default_factory=dict)
    by_impact: Dict[str, int] = field(default_factory=dict)
    avg_risk_score: float = 0.0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "total_risks": self.total_risks,
            "by_category": self.by_category,
            "by_status": self.by_status,
            "by_likelihood": self.by_likelihood,
            "by_impact": self.by_impact,
            "avg_risk_score": round(self.avg_risk_score, 2),
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Default risks from Plan Part 8
# ---------------------------------------------------------------------------

def _default_risks() -> List[Risk]:
    return [
        Risk("risk-code-gen", "Autonomous Code Generation Errors",
             RiskCategory.TECHNICAL, Likelihood.MEDIUM, Impact.HIGH,
             "Sandboxed environments, human approval, comprehensive testing, rollback"),
        Risk("risk-gate-fail", "Confidence Gate Failures",
             RiskCategory.TECHNICAL, Likelihood.LOW, Impact.HIGH,
             "Fallback mechanisms, dynamic thresholds, human override"),
        Risk("risk-resource", "Resource Exhaustion",
             RiskCategory.TECHNICAL, Likelihood.MEDIUM, Impact.MEDIUM,
             "Resource limits, monitoring, auto-scaling, cost controls"),
        Risk("risk-resistance", "Human Resistance to Automation",
             RiskCategory.OPERATIONAL, Likelihood.HIGH, Impact.MEDIUM,
             "Stakeholder engagement, training, value demonstration, gradual rollout"),
        Risk("risk-compliance", "Compliance Violations",
             RiskCategory.OPERATIONAL, Likelihood.LOW, Impact.HIGH,
             "Compliance controls, regular audits, legal review, documentation"),
        Risk("risk-vendor", "Vendor Dependencies",
             RiskCategory.OPERATIONAL, Likelihood.MEDIUM, Impact.MEDIUM,
             "Diversify vendors, implement fallbacks, monitor vendor health"),
        Risk("risk-market", "Market Changes",
             RiskCategory.BUSINESS, Likelihood.HIGH, Impact.HIGH,
             "Monitor trends, flexible architecture, rapid iteration, customer feedback"),
        Risk("risk-competition", "Competition",
             RiskCategory.BUSINESS, Likelihood.HIGH, Impact.HIGH,
             "Continuous innovation, differentiation, customer loyalty, partnerships"),
        Risk("risk-downturn", "Economic Downturn",
             RiskCategory.BUSINESS, Likelihood.MEDIUM, Impact.HIGH,
             "Cost controls, diversified revenue, cash reserves, flexible operations"),
    ]


# ---------------------------------------------------------------------------
# RiskMitigationTracker
# ---------------------------------------------------------------------------

class RiskMitigationTracker:
    """Technical, operational, and business risk tracking.

    Design Label: SAF-005
    Owner: Strategy Team / Security Team

    Usage::

        tracker = RiskMitigationTracker()
        tracker.update_status("risk-code-gen", RiskStatus.MITIGATING, "Started sandbox impl")
        summary = tracker.summarize()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        initial_risks: Optional[List[Risk]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._risks: Dict[str, Risk] = {}
        self._history: List[StatusChange] = []

        for risk in (initial_risks or _default_risks()):
            self._risks[risk.risk_id] = risk

    # ------------------------------------------------------------------
    # Risk management
    # ------------------------------------------------------------------

    def add_risk(self, risk: Risk) -> None:
        with self._lock:
            if len(self._risks) >= _MAX_RISKS:
                logger.warning("Risk register full, cannot add %s", risk.risk_id)
                return
            self._risks[risk.risk_id] = risk

    def get_risk(self, risk_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            risk = self._risks.get(risk_id)
            return risk.to_dict() if risk else None

    def list_risks(self, category: Optional[RiskCategory] = None,
                   status: Optional[RiskStatus] = None) -> List[Dict[str, Any]]:
        with self._lock:
            filtered = list(self._risks.values())
            if category:
                filtered = [r for r in filtered if r.category == category]
            if status:
                filtered = [r for r in filtered if r.status == status]
            return [r.to_dict() for r in filtered]

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def update_status(self, risk_id: str, new_status: RiskStatus,
                      reason: str = "") -> Optional[StatusChange]:
        with self._lock:
            risk = self._risks.get(risk_id)
            if risk is None:
                return None
            old = risk.status
            risk.status = new_status
            risk.updated_at = datetime.now(timezone.utc).isoformat()

            change = StatusChange(
                change_id=f"sc-{uuid.uuid4().hex[:8]}",
                risk_id=risk_id,
                from_status=old.value,
                to_status=new_status.value,
                reason=reason,
            )
            if len(self._history) >= _MAX_STATUS_HISTORY:
                self._history = self._history[_MAX_STATUS_HISTORY // 10:]
            self._history.append(change)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=change.change_id, document=change.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(change)

        logger.info("Risk %s: %s → %s (%s)", risk_id, old.value, new_status.value, reason)
        return change

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summarize(self) -> RiskSummary:
        with self._lock:
            risks = list(self._risks.values())

        cat_counts = Counter(r.category.value for r in risks)
        status_counts = Counter(r.status.value for r in risks)
        likelihood_counts = Counter(r.likelihood.value for r in risks)
        impact_counts = Counter(r.impact.value for r in risks)
        avg_score = sum(r.risk_score for r in risks) / (len(risks) or 1) if risks else 0.0

        summary = RiskSummary(
            summary_id=f"rs-{uuid.uuid4().hex[:8]}",
            total_risks=len(risks),
            by_category=dict(cat_counts),
            by_status=dict(status_counts),
            by_likelihood=dict(likelihood_counts),
            by_impact=dict(impact_counts),
            avg_risk_score=avg_score,
        )

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=summary.summary_id, document=summary.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        return summary

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self, risk_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            filtered = self._history
            if risk_id:
                filtered = [h for h in filtered if h.risk_id == risk_id]
            return [h.to_dict() for h in filtered[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_risks": len(self._risks),
                "total_status_changes": len(self._history),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, change: StatusChange) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "risk_mitigation_tracker",
                    "action": "risk_status_changed",
                    "change_id": change.change_id,
                    "risk_id": change.risk_id,
                    "from_status": change.from_status,
                    "to_status": change.to_status,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="risk_mitigation_tracker",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
