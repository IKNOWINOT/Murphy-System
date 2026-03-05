"""
Campaign Orchestrator for Murphy System.

Design Label: MKT-003 — Campaign Lifecycle Management, Budget Tracking & Channel Coordination
Owner: Marketing Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable campaign storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on campaign lifecycle events)
  - ContentPipelineEngine (MKT-001, optional, for content scheduling)
  - SEOOptimisationEngine (MKT-002, optional, for content scoring)

Implements Phase 4 — Marketing & Content Automation:
  Manages marketing campaigns end-to-end: planning, budgeting,
  channel allocation, execution, and performance tracking.

Flow:
  1. Create campaign with name, budget, channels, date range
  2. Allocate budget across channels
  3. Launch campaign (status: planned → active)
  4. Track spend and performance per channel
  5. Pause / resume / complete campaigns
  6. Generate campaign performance reports

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Budget enforcement: spend cannot exceed allocated budget
  - Immutable history: completed campaigns cannot be modified
  - Bounded: configurable max campaigns
  - Audit trail: every state transition is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class CampaignStatus(str, Enum):
    """Lifecycle states for a marketing campaign."""
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class CampaignChannel:
    """Budget and performance data for a single campaign channel."""
    channel_name: str
    allocated_budget: float
    spent: float = 0.0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0

    @property
    def remaining(self) -> float:
        return self.allocated_budget - self.spent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "allocated_budget": round(self.allocated_budget, 2),
            "spent": round(self.spent, 2),
            "remaining": round(self.remaining, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
        }


@dataclass
class Campaign:
    """A marketing campaign with budget, channels, and lifecycle state."""
    campaign_id: str
    name: str
    status: CampaignStatus = CampaignStatus.PLANNED
    total_budget: float = 0.0
    channels: Dict[str, CampaignChannel] = field(default_factory=dict)
    start_date: str = ""
    end_date: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_spent(self) -> float:
        return sum(ch.spent for ch in self.channels.values())

    @property
    def budget_remaining(self) -> float:
        return self.total_budget - self.total_spent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "status": self.status.value,
            "total_budget": round(self.total_budget, 2),
            "total_spent": round(self.total_spent, 2),
            "budget_remaining": round(self.budget_remaining, 2),
            "channels": {k: v.to_dict() for k, v in self.channels.items()},
            "start_date": self.start_date,
            "end_date": self.end_date,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# CampaignOrchestrator
# ---------------------------------------------------------------------------

class CampaignOrchestrator:
    """End-to-end marketing campaign management.

    Design Label: MKT-003
    Owner: Marketing Team

    Usage::

        orchestrator = CampaignOrchestrator(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        campaign = orchestrator.create_campaign(
            name="Summer Sale",
            total_budget=5000.0,
            channels=[{"name": "email", "budget": 2000}, {"name": "social", "budget": 3000}],
            start_date="2026-06-01",
            end_date="2026-08-31",
        )
        orchestrator.launch_campaign(campaign.campaign_id)
        orchestrator.record_spend(campaign.campaign_id, "email", 150.0, impressions=5000)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_campaigns: int = 5_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._campaigns: Dict[str, Campaign] = {}
        self._max_campaigns = max_campaigns

    # ------------------------------------------------------------------
    # Campaign creation
    # ------------------------------------------------------------------

    def create_campaign(
        self,
        name: str,
        total_budget: float,
        channels: List[Dict[str, Any]],
        start_date: str = "",
        end_date: str = "",
        tags: Optional[List[str]] = None,
    ) -> Campaign:
        """Create a new campaign with channel budget allocations."""
        campaign_id = f"cmp-{uuid.uuid4().hex[:8]}"

        channel_map: Dict[str, CampaignChannel] = {}
        for ch in channels:
            ch_name = ch["name"]
            channel_map[ch_name] = CampaignChannel(
                channel_name=ch_name,
                allocated_budget=float(ch.get("budget", 0.0)),
            )

        campaign = Campaign(
            campaign_id=campaign_id,
            name=name,
            total_budget=total_budget,
            channels=channel_map,
            start_date=start_date,
            end_date=end_date,
            tags=tags or [],
        )

        with self._lock:
            if len(self._campaigns) >= self._max_campaigns:
                # Evict oldest 10 %
                evict = max(1, self._max_campaigns // 10)
                keys = list(self._campaigns.keys())[:evict]
                for k in keys:
                    del self._campaigns[k]
            self._campaigns[campaign_id] = campaign

        self._persist(campaign)
        self._publish_event(campaign, "created")
        logger.info("Created campaign %s: %s (budget=%.2f)", campaign_id, name, total_budget)
        return campaign

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def launch_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Transition campaign from planned → active."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status != CampaignStatus.PLANNED:
                logger.warning("Cannot launch campaign %s: status is %s", campaign_id, campaign.status.value)
                return None
            campaign.status = CampaignStatus.ACTIVE
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        self._publish_event(campaign, "launched")
        logger.info("Launched campaign %s", campaign_id)
        return campaign

    def pause_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Transition campaign from active → paused."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status != CampaignStatus.ACTIVE:
                logger.warning("Cannot pause campaign %s: status is %s", campaign_id, campaign.status.value)
                return None
            campaign.status = CampaignStatus.PAUSED
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        self._publish_event(campaign, "paused")
        logger.info("Paused campaign %s", campaign_id)
        return campaign

    def resume_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Transition campaign from paused → active."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status != CampaignStatus.PAUSED:
                logger.warning("Cannot resume campaign %s: status is %s", campaign_id, campaign.status.value)
                return None
            campaign.status = CampaignStatus.ACTIVE
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        self._publish_event(campaign, "resumed")
        logger.info("Resumed campaign %s", campaign_id)
        return campaign

    def complete_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Transition campaign from active/paused → completed (immutable)."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status not in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED):
                logger.warning("Cannot complete campaign %s: status is %s", campaign_id, campaign.status.value)
                return None
            campaign.status = CampaignStatus.COMPLETED
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        self._publish_event(campaign, "completed")
        logger.info("Completed campaign %s", campaign_id)
        return campaign

    def cancel_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Transition campaign from planned/paused → cancelled."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status not in (CampaignStatus.PLANNED, CampaignStatus.PAUSED):
                logger.warning("Cannot cancel campaign %s: status is %s", campaign_id, campaign.status.value)
                return None
            campaign.status = CampaignStatus.CANCELLED
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        self._publish_event(campaign, "cancelled")
        logger.info("Cancelled campaign %s", campaign_id)
        return campaign

    # ------------------------------------------------------------------
    # Spend & performance tracking
    # ------------------------------------------------------------------

    def record_spend(
        self,
        campaign_id: str,
        channel_name: str,
        amount: float,
        impressions: int = 0,
        clicks: int = 0,
        conversions: int = 0,
    ) -> Optional[Campaign]:
        """Record spend and performance metrics for a channel."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if campaign is None:
                logger.warning("Campaign %s not found", campaign_id)
                return None
            if campaign.status != CampaignStatus.ACTIVE:
                logger.warning("Cannot record spend: campaign %s is %s", campaign_id, campaign.status.value)
                return None
            channel = campaign.channels.get(channel_name)
            if channel is None:
                logger.warning("Channel %s not found in campaign %s", channel_name, campaign_id)
                return None
            if amount > channel.remaining:
                logger.warning(
                    "Spend %.2f exceeds remaining budget %.2f for channel %s",
                    amount, channel.remaining, channel_name,
                )
                return None
            channel.spent += amount
            channel.impressions += impressions
            channel.clicks += clicks
            channel.conversions += conversions
            campaign.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(campaign)
        logger.info("Recorded spend %.2f on %s for campaign %s", amount, channel_name, campaign_id)
        return campaign

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Return a single campaign as a dict."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
        if campaign is None:
            return None
        return campaign.to_dict()

    def list_campaigns(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return campaigns, optionally filtered by status."""
        with self._lock:
            campaigns = list(self._campaigns.values())
        if status:
            campaigns = [c for c in campaigns if c.status.value == status.lower()]
        return [c.to_dict() for c in campaigns[-limit:]]

    def get_performance(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Return detailed performance report for a campaign."""
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
        if campaign is None:
            return None

        total_spent = campaign.total_spent
        total_clicks = sum(ch.clicks for ch in campaign.channels.values())
        total_conversions = sum(ch.conversions for ch in campaign.channels.values())

        roi_indicators: Dict[str, float] = {}
        if total_clicks > 0:
            roi_indicators["cpc"] = round(total_spent / total_clicks, 4)
        if total_conversions > 0:
            roi_indicators["cpa"] = round(total_spent / total_conversions, 4)

        return {
            "campaign_id": campaign.campaign_id,
            "name": campaign.name,
            "total_budget": round(campaign.total_budget, 2),
            "total_spent": round(total_spent, 2),
            "budget_remaining": round(campaign.budget_remaining, 2),
            "channels": {k: v.to_dict() for k, v in campaign.channels.items()},
            "roi_indicators": roi_indicators,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return orchestrator status summary."""
        with self._lock:
            campaigns = list(self._campaigns.values())

        by_status: Dict[str, int] = defaultdict(int)
        total_budget = 0.0
        total_spent = 0.0
        for c in campaigns:
            by_status[c.status.value] += 1
            total_budget += c.total_budget
            total_spent += c.total_spent

        return {
            "total_campaigns": len(campaigns),
            "by_status": dict(by_status),
            "total_budget_allocated": round(total_budget, 2),
            "total_spent": round(total_spent, 2),
            "persistence_attached": self._pm is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, campaign: Campaign) -> None:
        """Persist campaign via PersistenceManager."""
        if self._pm is None:
            return
        try:
            self._pm.save_document(
                doc_id=campaign.campaign_id,
                document=campaign.to_dict(),
            )
        except Exception as exc:
            logger.debug("Persistence skipped: %s", exc)

    def _publish_event(self, campaign: Campaign, action: str) -> None:
        """Publish a LEARNING_FEEDBACK event with campaign summary."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "campaign_orchestrator",
                    "action": action,
                    "campaign": campaign.to_dict(),
                },
                source="campaign_orchestrator",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
