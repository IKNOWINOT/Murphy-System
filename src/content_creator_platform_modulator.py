"""
Content Creator Platform Modulator — Murphy System

Provides unified connectors for content creator and streaming platforms
including YouTube, Twitch, OnlyFans, TikTok, Patreon, Kick, and Rumble.

Capabilities per platform:
  - Content scheduling and publishing
  - Analytics and audience insights
  - Monetization tracking (subscriptions, donations, ad revenue)
  - Audience/community management
  - Live stream orchestration
  - Content moderation automation
  - Cross-platform syndication

All connectors follow the same registry/execute pattern used by
building_automation_connectors and energy_management_connectors.
"""

import enum
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlatformType(enum.Enum):
    """Platform type (Enum subclass)."""
    VIDEO = "video"
    STREAMING = "streaming"
    SUBSCRIPTION = "subscription"
    SHORT_FORM = "short_form"
    COMMUNITY = "community"


class ContentType(enum.Enum):
    """Content type (Enum subclass)."""
    VIDEO = "video"
    LIVE_STREAM = "live_stream"
    SHORT_VIDEO = "short_video"
    POST = "post"
    STORY = "story"
    PODCAST = "podcast"
    ARTICLE = "article"


class MonetizationModel(enum.Enum):
    """Monetization model (Enum subclass)."""
    AD_REVENUE = "ad_revenue"
    SUBSCRIPTIONS = "subscriptions"
    DONATIONS = "donations"
    TIPS = "tips"
    MERCHANDISE = "merchandise"
    SPONSORSHIPS = "sponsorships"
    PPV = "pay_per_view"
    AFFILIATE = "affiliate"


class ConnectorStatus(enum.Enum):
    """Connector status (Enum subclass)."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RATE_LIMITED = "rate_limited"


# ---------------------------------------------------------------------------
# Connector class
# ---------------------------------------------------------------------------

class PlatformConnector:
    """Represents a single content creator platform connector."""

    def __init__(
        self,
        connector_id: str,
        name: str,
        platform: str,
        platform_type: PlatformType,
        api_base_url: str,
        capabilities: List[str],
        content_types: List[str],
        monetization_models: List[str],
        rate_limit: Dict[str, int],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.connector_id = connector_id
        self.name = name
        self.platform = platform
        self.platform_type = platform_type
        self.api_base_url = api_base_url
        self.capabilities = list(capabilities)
        self.content_types = list(content_types)
        self.monetization_models = list(monetization_models)
        self.rate_limit = dict(rate_limit)
        self.metadata = dict(metadata) if metadata else {}
        self.status = ConnectorStatus.ACTIVE
        self.enabled = True
        self._request_count = 0
        self._error_count = 0

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an action against this platform connector."""
        self._request_count += 1
        if action not in self.capabilities:
            self._error_count += 1
            return {
                "success": False,
                "error": f"Action '{action}' not supported. Available: {self.capabilities}",
                "connector": self.connector_id,
            }
        return {
            "success": True,
            "connector": self.connector_id,
            "platform": self.platform,
            "action": action,
            "params": params or {},
            "timestamp": time.time(),
            "request_number": self._request_count,
        }

    def health_check(self) -> Dict[str, Any]:
        error_rate = self._error_count / max(self._request_count, 1)
        if not self.enabled:
            self.status = ConnectorStatus.OFFLINE
        elif error_rate > 0.5:
            self.status = ConnectorStatus.DEGRADED
        else:
            self.status = ConnectorStatus.ACTIVE
        return {
            "connector_id": self.connector_id,
            "status": self.status.value,
            "requests": self._request_count,
            "errors": self._error_count,
            "error_rate": round(error_rate, 4),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "platform": self.platform,
            "platform_type": self.platform_type.value,
            "capabilities": self.capabilities,
            "content_types": self.content_types,
            "monetization_models": self.monetization_models,
            "status": self.status.value,
            "enabled": self.enabled,
        }


# ---------------------------------------------------------------------------
# Default platform connectors
# ---------------------------------------------------------------------------

def _default_connectors() -> List[PlatformConnector]:
    """Register all built-in content creator platform connectors."""
    return [
        # YouTube
        PlatformConnector(
            connector_id="youtube",
            name="YouTube",
            platform="youtube",
            platform_type=PlatformType.VIDEO,
            api_base_url="https://www.googleapis.com/youtube/v3",
            capabilities=[
                "video_upload", "video_scheduling", "live_stream_management",
                "analytics_reporting", "audience_insights", "comment_moderation",
                "playlist_management", "channel_management", "shorts_publishing",
                "community_posts", "monetization_tracking", "ad_revenue_analytics",
                "subscriber_management", "content_id_management",
            ],
            content_types=["video", "live_stream", "short_video", "post"],
            monetization_models=["ad_revenue", "subscriptions", "merchandise", "sponsorships"],
            rate_limit={"requests_per_minute": 60, "burst_limit": 10},
            metadata={"api_version": "v3", "oauth_scopes": ["youtube.upload", "youtube.readonly"]},
        ),
        # Twitch
        PlatformConnector(
            connector_id="twitch",
            name="Twitch",
            platform="twitch",
            platform_type=PlatformType.STREAMING,
            api_base_url="https://api.twitch.tv/helix",
            capabilities=[
                "live_stream_management", "stream_scheduling", "chat_moderation",
                "clip_management", "raid_management", "channel_point_management",
                "subscriber_management", "bits_tracking", "analytics_reporting",
                "audience_insights", "vod_management", "extension_management",
                "prediction_management", "poll_management",
            ],
            content_types=["live_stream", "video"],
            monetization_models=["subscriptions", "donations", "tips", "ad_revenue"],
            rate_limit={"requests_per_minute": 800, "burst_limit": 30},
            metadata={"api_version": "helix", "auth_type": "oauth2"},
        ),
        # OnlyFans
        PlatformConnector(
            connector_id="onlyfans",
            name="OnlyFans",
            platform="onlyfans",
            platform_type=PlatformType.SUBSCRIPTION,
            api_base_url="https://onlyfans.com/api2/v2",
            capabilities=[
                "content_publishing", "content_scheduling", "subscriber_management",
                "ppv_messaging", "tip_tracking", "analytics_reporting",
                "audience_insights", "promotion_management", "vault_management",
                "mass_messaging", "price_management", "referral_tracking",
            ],
            content_types=["post", "video", "story"],
            monetization_models=["subscriptions", "tips", "pay_per_view"],
            rate_limit={"requests_per_minute": 30, "burst_limit": 5},
            metadata={"auth_type": "session_cookie", "content_policy": "creator_managed"},
        ),
        # TikTok
        PlatformConnector(
            connector_id="tiktok",
            name="TikTok",
            platform="tiktok",
            platform_type=PlatformType.SHORT_FORM,
            api_base_url="https://open.tiktokapis.com/v2",
            capabilities=[
                "video_publishing", "content_scheduling", "analytics_reporting",
                "audience_insights", "comment_management", "sound_management",
                "hashtag_analytics", "creator_marketplace", "shop_management",
                "live_stream_management", "effect_management",
            ],
            content_types=["short_video", "live_stream"],
            monetization_models=["ad_revenue", "donations", "merchandise", "affiliate"],
            rate_limit={"requests_per_minute": 100, "burst_limit": 15},
            metadata={"api_version": "v2", "auth_type": "oauth2"},
        ),
        # Patreon
        PlatformConnector(
            connector_id="patreon",
            name="Patreon",
            platform="patreon",
            platform_type=PlatformType.SUBSCRIPTION,
            api_base_url="https://www.patreon.com/api/oauth2/v2",
            capabilities=[
                "post_publishing", "tier_management", "member_management",
                "analytics_reporting", "benefit_delivery", "goal_tracking",
                "webhook_management", "campaign_management", "payout_tracking",
                "content_scheduling",
            ],
            content_types=["post", "video", "podcast", "article"],
            monetization_models=["subscriptions"],
            rate_limit={"requests_per_minute": 25, "burst_limit": 5},
            metadata={"api_version": "v2", "auth_type": "oauth2"},
        ),
        # Kick
        PlatformConnector(
            connector_id="kick",
            name="Kick",
            platform="kick",
            platform_type=PlatformType.STREAMING,
            api_base_url="https://kick.com/api/v2",
            capabilities=[
                "live_stream_management", "chat_moderation", "clip_management",
                "subscriber_management", "analytics_reporting", "vod_management",
                "channel_management", "emote_management",
            ],
            content_types=["live_stream", "video"],
            monetization_models=["subscriptions", "donations", "tips"],
            rate_limit={"requests_per_minute": 60, "burst_limit": 10},
            metadata={"auth_type": "oauth2"},
        ),
        # Rumble
        PlatformConnector(
            connector_id="rumble",
            name="Rumble",
            platform="rumble",
            platform_type=PlatformType.VIDEO,
            api_base_url="https://rumble.com/api/v0",
            capabilities=[
                "video_upload", "video_scheduling", "live_stream_management",
                "analytics_reporting", "comment_management", "channel_management",
                "monetization_tracking", "rant_management",
            ],
            content_types=["video", "live_stream"],
            monetization_models=["ad_revenue", "donations", "subscriptions"],
            rate_limit={"requests_per_minute": 30, "burst_limit": 5},
            metadata={"auth_type": "api_key"},
        ),
    ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ContentCreatorPlatformRegistry:
    """Thread-safe registry for content creator platform connectors."""

    def __init__(self):
        self._lock = threading.RLock()
        self._connectors: Dict[str, PlatformConnector] = {}
        self._action_log: List[Dict[str, Any]] = []

        # Register defaults
        for c in _default_connectors():
            self._connectors[c.connector_id] = c

    # -- Connector management -----------------------------------------------

    def register(self, connector: PlatformConnector) -> Dict[str, Any]:
        with self._lock:
            self._connectors[connector.connector_id] = connector
            return {"registered": True, "connector_id": connector.connector_id}

    def get_connector(self, connector_id: str) -> Optional[PlatformConnector]:
        with self._lock:
            return self._connectors.get(connector_id)

    def list_connectors(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_dict() for c in self._connectors.values()]

    def list_platforms(self) -> List[str]:
        with self._lock:
            return sorted(self._connectors.keys())

    def list_by_type(self, platform_type: PlatformType) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                c.to_dict() for c in self._connectors.values()
                if c.platform_type == platform_type
            ]

    # -- Execution ----------------------------------------------------------

    def execute(self, connector_id: str, action: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            connector = self._connectors.get(connector_id)
            if connector is None:
                return {"success": False, "error": f"Unknown connector: {connector_id}"}
            result = connector.execute(action, params)
            capped_append(self._action_log, {
                "connector_id": connector_id,
                "action": action,
                "success": result["success"],
                "timestamp": time.time(),
            })
            return result

    # -- Cross-platform syndication -----------------------------------------

    def syndicate_content(self, content: Dict[str, Any],
                          target_platforms: List[str]) -> Dict[str, Any]:
        """Publish content across multiple platforms simultaneously."""
        with self._lock:
            results = {}
            for platform_id in target_platforms:
                connector = self._connectors.get(platform_id)
                if connector is None:
                    results[platform_id] = {"success": False, "error": "Unknown platform"}
                    continue
                # Find the best publish action for this platform
                publish_actions = [
                    a for a in connector.capabilities
                    if "publish" in a or "upload" in a
                ]
                if publish_actions:
                    results[platform_id] = connector.execute(publish_actions[0], content)
                else:
                    results[platform_id] = {"success": False, "error": "No publish capability"}

            return {
                "success": all(r.get("success") for r in results.values()),
                "platforms": results,
                "content_id": str(uuid.uuid4())[:12],
                "timestamp": time.time(),
            }

    # -- Analytics aggregation ----------------------------------------------

    def aggregate_analytics(self, platform_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Aggregate analytics across platforms."""
        with self._lock:
            targets = platform_ids or list(self._connectors.keys())
            platform_analytics = {}
            for pid in targets:
                connector = self._connectors.get(pid)
                if connector and "analytics_reporting" in connector.capabilities:
                    platform_analytics[pid] = {
                        "available": True,
                        "platform": connector.name,
                        "capabilities": [
                            c for c in connector.capabilities if "analytics" in c or "insights" in c
                        ],
                    }
            return {
                "platforms_with_analytics": len(platform_analytics),
                "total_platforms": len(targets),
                "analytics": platform_analytics,
            }

    # -- Health / stats -----------------------------------------------------

    def health_check_all(self) -> Dict[str, Any]:
        with self._lock:
            results = {}
            for cid, connector in self._connectors.items():
                results[cid] = connector.health_check()
            active = sum(1 for r in results.values() if r["status"] == "active")
            return {
                "total": len(results),
                "active": active,
                "degraded": sum(1 for r in results.values() if r["status"] == "degraded"),
                "offline": sum(1 for r in results.values() if r["status"] == "offline"),
                "connectors": results,
            }

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            by_type = {}
            for c in self._connectors.values():
                t = c.platform_type.value
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "total_connectors": len(self._connectors),
                "enabled_connectors": sum(1 for c in self._connectors.values() if c.enabled),
                "by_platform_type": by_type,
                "action_log_entries": len(self._action_log),
                "platforms": self.list_platforms(),
            }


# ---------------------------------------------------------------------------
# Module-level status helper (matches pattern used by other modules)
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    return {
        "module": "content_creator_platform_modulator",
        "version": "1.0.0",
        "status": "operational",
        "platforms": [
            "youtube", "twitch", "onlyfans", "tiktok",
            "patreon", "kick", "rumble",
        ],
        "platform_types": [t.value for t in PlatformType],
        "content_types": [t.value for t in ContentType],
        "monetization_models": [m.value for m in MonetizationModel],
        "timestamp": time.time(),
    }
