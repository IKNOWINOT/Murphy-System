"""
Content Pipeline Engine for Murphy System.

Design Label: MKT-001 — Automated Content Generation, Scheduling & Multi-Channel Publish
Owner: Marketing Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable content storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on content lifecycle events)
  - RAGVectorIntegration (optional, for topic research and keyword extraction)

Implements Phase 4 — Marketing & Content Automation:
  Manages the full content lifecycle: ideation, drafting, review,
  scheduling, and multi-channel publication. Supports blog posts,
  social media posts, email newsletters, and marketing copy.

Flow:
  1. Create content brief (topic, content_type, target_channels)
  2. Generate draft from brief (template-based or description)
  3. Review and approve content (manual or auto for low-risk)
  4. Schedule publication with target date/time
  5. Publish to configured channels
  6. Track performance metrics per content piece

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Immutable history: published content cannot be modified
  - Bounded: configurable max content items to prevent memory issues
  - Audit trail: every lifecycle transition is logged
  - Human-in-the-loop: all content requires review before publish

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

_VALID_CONTENT_TYPES = {"blog", "social", "email", "copy"}
_VALID_TONES = {"professional", "casual", "technical"}
_VALID_STATUSES = {"draft", "review", "approved", "scheduled", "published", "archived"}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContentBrief:
    """A content brief capturing the intent and scope of a content piece."""
    brief_id: str
    topic: str
    content_type: str          # blog, social, email, copy
    target_channels: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    tone: str = "professional"  # professional, casual, technical
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "topic": self.topic,
            "content_type": self.content_type,
            "target_channels": list(self.target_channels),
            "keywords": list(self.keywords),
            "tone": self.tone,
            "created_at": self.created_at,
        }


@dataclass
class ContentItem:
    """A content piece moving through the lifecycle pipeline."""
    item_id: str
    brief_id: str
    content_type: str
    title: str
    body: str
    status: str = "draft"      # draft → review → approved → scheduled → published → archived
    channel: str = "blog"
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "brief_id": self.brief_id,
            "content_type": self.content_type,
            "title": self.title,
            "body": self.body,
            "status": self.status,
            "channel": self.channel,
            "scheduled_at": self.scheduled_at,
            "published_at": self.published_at,
            "performance_metrics": dict(self.performance_metrics),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# ContentPipelineEngine
# ---------------------------------------------------------------------------

class ContentPipelineEngine:
    """Automated content lifecycle management and multi-channel publication.

    Design Label: MKT-001
    Owner: Marketing Team

    Usage::

        engine = ContentPipelineEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        brief = engine.create_brief(
            topic="Q3 Product Update",
            content_type="blog",
            target_channels=["blog", "twitter"],
        )
        draft = engine.create_draft(brief.brief_id, "Q3 Update", "Full body...")
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        engine.publish_content(draft.item_id)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_briefs: int = 10_000,
        max_content: int = 50_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._briefs: Dict[str, ContentBrief] = {}
        self._content: Dict[str, ContentItem] = {}
        self._max_briefs = max_briefs
        self._max_content = max_content

    # ------------------------------------------------------------------
    # Brief management
    # ------------------------------------------------------------------

    def create_brief(
        self,
        topic: str,
        content_type: str,
        target_channels: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        tone: str = "professional",
    ) -> ContentBrief:
        """Create a content brief. Returns the created brief."""
        content_type = content_type.lower()
        if content_type not in _VALID_CONTENT_TYPES:
            raise ValueError(
                f"Invalid content_type '{content_type}'. Must be one of {_VALID_CONTENT_TYPES}"
            )
        tone = tone.lower()
        if tone not in _VALID_TONES:
            raise ValueError(
                f"Invalid tone '{tone}'. Must be one of {_VALID_TONES}"
            )

        brief = ContentBrief(
            brief_id=f"brief-{uuid.uuid4().hex[:8]}",
            topic=topic,
            content_type=content_type,
            target_channels=target_channels or [],
            keywords=keywords or [],
            tone=tone,
        )
        with self._lock:
            if len(self._briefs) >= self._max_briefs:
                # Evict oldest 10 %
                evict = max(1, self._max_briefs // 10)
                keys = list(self._briefs.keys())[:evict]
                for k in keys:
                    del self._briefs[k]
            self._briefs[brief.brief_id] = brief

        logger.info("Created content brief %s: %s (%s)", brief.brief_id, topic, content_type)
        return brief

    # ------------------------------------------------------------------
    # Draft creation
    # ------------------------------------------------------------------

    def create_draft(
        self,
        brief_id: str,
        title: str,
        body: str,
        channel: str = "blog",
    ) -> ContentItem:
        """Create a content draft from an existing brief."""
        with self._lock:
            brief = self._briefs.get(brief_id)
        if brief is None:
            raise ValueError(f"Brief '{brief_id}' not found")

        item = ContentItem(
            item_id=f"cnt-{uuid.uuid4().hex[:8]}",
            brief_id=brief_id,
            content_type=brief.content_type,
            title=title,
            body=body,
            status="draft",
            channel=channel,
        )
        with self._lock:
            if len(self._content) >= self._max_content:
                evict = max(1, self._max_content // 10)
                keys = list(self._content.keys())[:evict]
                for k in keys:
                    del self._content[k]
            self._content[item.item_id] = item

        self._persist(item)
        self._publish_event(item, "draft_created")
        logger.info("Created draft %s for brief %s", item.item_id, brief_id)
        return item

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def submit_for_review(self, item_id: str) -> ContentItem:
        """Transition content from draft to review."""
        with self._lock:
            item = self._content.get(item_id)
            if item is None:
                raise ValueError(f"Content item '{item_id}' not found")
            if item.status != "draft":
                raise ValueError(
                    f"Cannot submit for review: item '{item_id}' is '{item.status}', expected 'draft'"
                )
            item.status = "review"
            item.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(item)
        self._publish_event(item, "submitted_for_review")
        logger.info("Content %s submitted for review", item_id)
        return item

    def approve_content(self, item_id: str) -> ContentItem:
        """Approve content after review."""
        with self._lock:
            item = self._content.get(item_id)
            if item is None:
                raise ValueError(f"Content item '{item_id}' not found")
            if item.status != "review":
                raise ValueError(
                    f"Cannot approve: item '{item_id}' is '{item.status}', expected 'review'"
                )
            item.status = "approved"
            item.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(item)
        self._publish_event(item, "approved")
        logger.info("Content %s approved", item_id)
        return item

    def schedule_content(self, item_id: str, scheduled_at: str) -> ContentItem:
        """Schedule approved content for future publication."""
        with self._lock:
            item = self._content.get(item_id)
            if item is None:
                raise ValueError(f"Content item '{item_id}' not found")
            if item.status != "approved":
                raise ValueError(
                    f"Cannot schedule: item '{item_id}' is '{item.status}', expected 'approved'"
                )
            item.status = "scheduled"
            item.scheduled_at = scheduled_at
            item.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(item)
        self._publish_event(item, "scheduled")
        logger.info("Content %s scheduled for %s", item_id, scheduled_at)
        return item

    def publish_content(self, item_id: str) -> ContentItem:
        """Publish content to its target channel."""
        with self._lock:
            item = self._content.get(item_id)
            if item is None:
                raise ValueError(f"Content item '{item_id}' not found")
            if item.status not in ("scheduled", "approved"):
                raise ValueError(
                    f"Cannot publish: item '{item_id}' is '{item.status}', "
                    "expected 'scheduled' or 'approved'"
                )
            item.status = "published"
            item.published_at = datetime.now(timezone.utc).isoformat()
            item.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(item)
        self._publish_event(item, "published")
        logger.info("Content %s published to %s", item_id, item.channel)
        return item

    # ------------------------------------------------------------------
    # Metrics tracking
    # ------------------------------------------------------------------

    def record_metrics(
        self,
        item_id: str,
        views: int = 0,
        clicks: int = 0,
        shares: int = 0,
        conversions: int = 0,
    ) -> ContentItem:
        """Record performance metrics for a published content item."""
        with self._lock:
            item = self._content.get(item_id)
            if item is None:
                raise ValueError(f"Content item '{item_id}' not found")
            item.performance_metrics["views"] = (
                item.performance_metrics.get("views", 0) + views
            )
            item.performance_metrics["clicks"] = (
                item.performance_metrics.get("clicks", 0) + clicks
            )
            item.performance_metrics["shares"] = (
                item.performance_metrics.get("shares", 0) + shares
            )
            item.performance_metrics["conversions"] = (
                item.performance_metrics.get("conversions", 0) + conversions
            )
            item.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(item)
        self._publish_event(item, "metrics_recorded")
        logger.info("Recorded metrics for content %s", item_id)
        return item

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_content(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Return a single content item as dict, or None if not found."""
        with self._lock:
            item = self._content.get(item_id)
        if item is None:
            return None
        return item.to_dict()

    def list_content(
        self,
        status: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return content items, optionally filtered by status or type."""
        with self._lock:
            items = list(self._content.values())
        if status:
            items = [i for i in items if i.status == status.lower()]
        if content_type:
            items = [i for i in items if i.content_type == content_type.lower()]
        return [i.to_dict() for i in items[-limit:]]

    def get_briefs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent content briefs."""
        with self._lock:
            briefs = list(self._briefs.values())
        return [b.to_dict() for b in briefs[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            items = list(self._content.values())
            by_status: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for item in items:
                by_status[item.status] = by_status.get(item.status, 0) + 1
                by_type[item.content_type] = by_type.get(item.content_type, 0) + 1
            return {
                "total_briefs": len(self._briefs),
                "total_content": len(self._content),
                "by_status": by_status,
                "by_type": by_type,
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, item: ContentItem) -> None:
        """Persist a content item via PersistenceManager if available."""
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=item.item_id,
                    document=item.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

    def _publish_event(self, item: ContentItem, action: str) -> None:
        """Publish a LEARNING_FEEDBACK event with content lifecycle data."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "content_pipeline_engine",
                    "action": action,
                    "item_id": item.item_id,
                    "brief_id": item.brief_id,
                    "content_type": item.content_type,
                    "status": item.status,
                    "channel": item.channel,
                    "title": item.title,
                },
                source="content_pipeline_engine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
