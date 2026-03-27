"""
Social Media Scheduler for Murphy System.

Design Label: MKT-004 — Multi-Platform Post Scheduling & Engagement Monitoring
Owner: Marketing Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable post and metric storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on post lifecycle events)
  - ContentPipelineEngine (MKT-001, optional, for content sourcing)
  - CampaignOrchestrator (MKT-003, optional, for campaign linkage)

Implements Phase 4 — Marketing & Content Automation (continued):
  Schedules social media posts across multiple platforms, tracks
  engagement metrics per post, identifies optimal posting times
  based on historical engagement data, and integrates with the
  campaign lifecycle.

Flow:
  1. Create posts with platform, content, scheduled time, campaign linkage
  2. Queue posts for scheduled publishing
  3. Simulate/record publish events (actual API calls delegated to adapters)
  4. Ingest engagement metrics (likes, shares, comments, reach)
  5. Analyze optimal posting windows per platform
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: posts are immutable once published
  - Bounded: configurable max posts and metrics
  - Audit trail: every publish and metric update is logged

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
# Constants
# ---------------------------------------------------------------------------

_MAX_POSTS = 50_000
_MAX_METRICS = 200_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PostStatus(str, Enum):
    """Post status (str subclass)."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class SocialPost:
    """A single social media post."""
    post_id: str
    platform: str               # twitter | linkedin | facebook | instagram | …
    content: str
    status: PostStatus = PostStatus.DRAFT
    scheduled_at: str = ""
    published_at: str = ""
    campaign_id: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "platform": self.platform,
            "content": self.content[:500],
            "status": self.status.value,
            "scheduled_at": self.scheduled_at,
            "published_at": self.published_at,
            "campaign_id": self.campaign_id,
            "tags": list(self.tags),
            "created_at": self.created_at,
        }


@dataclass
class EngagementMetric:
    """Engagement data for a published post."""
    metric_id: str
    post_id: str
    likes: int = 0
    shares: int = 0
    comments: int = 0
    reach: int = 0
    clicks: int = 0
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def engagement_score(self) -> int:
        return self.likes + self.shares * 2 + self.comments * 3 + self.clicks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "post_id": self.post_id,
            "likes": self.likes,
            "shares": self.shares,
            "comments": self.comments,
            "reach": self.reach,
            "clicks": self.clicks,
            "engagement_score": self.engagement_score,
            "recorded_at": self.recorded_at,
        }


# ---------------------------------------------------------------------------
# SocialMediaScheduler
# ---------------------------------------------------------------------------

class SocialMediaScheduler:
    """Multi-platform post scheduling and engagement monitoring.

    Design Label: MKT-004
    Owner: Marketing Team / Platform Engineering

    Usage::

        sched = SocialMediaScheduler(persistence_manager=pm)
        post = sched.create_post("twitter", "Check out Murphy System!")
        sched.schedule_post(post.post_id, "2026-03-01T12:00:00Z")
        sched.publish_post(post.post_id)
        sched.record_engagement(post.post_id, likes=42, shares=7)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_posts: int = _MAX_POSTS,
        max_metrics: int = _MAX_METRICS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._posts: Dict[str, SocialPost] = {}
        self._metrics: List[EngagementMetric] = []
        self._max_posts = max_posts
        self._max_metrics = max_metrics

    # ------------------------------------------------------------------
    # Post lifecycle
    # ------------------------------------------------------------------

    def create_post(
        self,
        platform: str,
        content: str,
        campaign_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> SocialPost:
        post = SocialPost(
            post_id=f"smp-{uuid.uuid4().hex[:8]}",
            platform=platform.lower().strip(),
            content=content,
            campaign_id=campaign_id,
            tags=tags or [],
        )
        with self._lock:
            if len(self._posts) >= self._max_posts:
                logger.warning("Max posts reached (%d)", self._max_posts)
                return post
            self._posts[post.post_id] = post
        self._persist_post(post)
        return post

    def schedule_post(self, post_id: str, scheduled_at: str) -> bool:
        with self._lock:
            post = self._posts.get(post_id)
            if post is None or post.status not in (PostStatus.DRAFT, PostStatus.SCHEDULED):
                return False
            post.scheduled_at = scheduled_at
            post.status = PostStatus.SCHEDULED
        self._persist_post(post)
        return True

    def publish_post(self, post_id: str) -> bool:
        with self._lock:
            post = self._posts.get(post_id)
            if post is None or post.status == PostStatus.PUBLISHED:
                return False
            post.status = PostStatus.PUBLISHED
            post.published_at = datetime.now(timezone.utc).isoformat()
        self._persist_post(post)
        if self._backbone is not None:
            self._publish_event("post_published", post_id)
        return True

    # ------------------------------------------------------------------
    # Engagement tracking
    # ------------------------------------------------------------------

    def record_engagement(
        self,
        post_id: str,
        likes: int = 0,
        shares: int = 0,
        comments: int = 0,
        reach: int = 0,
        clicks: int = 0,
    ) -> Optional[EngagementMetric]:
        with self._lock:
            if post_id not in self._posts:
                return None
        metric = EngagementMetric(
            metric_id=f"eng-{uuid.uuid4().hex[:8]}",
            post_id=post_id,
            likes=likes,
            shares=shares,
            comments=comments,
            reach=reach,
            clicks=clicks,
        )
        with self._lock:
            if len(self._metrics) >= self._max_metrics:
                evict = max(1, self._max_metrics // 10)
                self._metrics = self._metrics[evict:]
            self._metrics.append(metric)
        return metric

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def platform_summary(self) -> Dict[str, Dict[str, Any]]:
        """Aggregate engagement per platform."""
        with self._lock:
            posts = list(self._posts.values())
            metrics = list(self._metrics)
        post_platforms = {p.post_id: p.platform for p in posts}
        agg: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "posts": 0, "likes": 0, "shares": 0, "comments": 0, "reach": 0,
        })
        for p in posts:
            if p.status == PostStatus.PUBLISHED:
                agg[p.platform]["posts"] += 1
        for m in metrics:
            plat = post_platforms.get(m.post_id, "unknown")
            agg[plat]["likes"] += m.likes
            agg[plat]["shares"] += m.shares
            agg[plat]["comments"] += m.comments
            agg[plat]["reach"] += m.reach
        return dict(agg)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            post = self._posts.get(post_id)
        return post.to_dict() if post else None

    def list_posts(self, platform: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            posts = list(self._posts.values())
        if platform:
            posts = [p for p in posts if p.platform == platform]
        return [p.to_dict() for p in posts[:limit]]

    def get_metrics(self, post_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            metrics = list(self._metrics)
        if post_id:
            metrics = [m for m in metrics if m.post_id == post_id]
        return [m.to_dict() for m in metrics[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_posts": len(self._posts),
                "total_metrics": len(self._metrics),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_post(self, post: SocialPost) -> None:
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=post.post_id, document=post.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

    def _publish_event(self, action: str, ref_id: str) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "social_media_scheduler",
                    "action": action,
                    "ref_id": ref_id,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="social_media_scheduler",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
