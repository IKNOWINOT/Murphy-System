"""
Social Media Moderation — Connector adapters and moderation automation
for primary social media platforms.

Provides unified content moderation across Facebook/Meta, Instagram,
Twitter/X, YouTube, TikTok, Reddit, LinkedIn, and Discord with
auto-moderation rules, content classification, queue management,
cross-platform policy enforcement, analytics, and appeal handling.
"""

import hashlib
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
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

class PlatformType(Enum):
    """Platform type (Enum subclass)."""
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    REDDIT = "reddit"
    LINKEDIN = "linkedin"
    DISCORD = "discord"


class ContentVerdict(Enum):
    """Content verdict (Enum subclass)."""
    SAFE = "safe"
    WARNING = "warning"
    VIOLATION = "violation"


class ViolationCategory(Enum):
    """Violation category (Enum subclass)."""
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    ADULT_CONTENT = "adult_content"
    MISINFORMATION = "misinformation"
    COPYRIGHT = "copyright"


class ModerationAction(Enum):
    """Moderation action (Enum subclass)."""
    APPROVE = "approve"
    REJECT = "reject"
    FLAG = "flag"
    ESCALATE = "escalate"
    MUTE = "mute"
    BAN = "ban"


class QueuePriority(Enum):
    """Queue priority (Enum subclass)."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AppealStatus(Enum):
    """Appeal status (Enum subclass)."""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"


class ConnectorHealth(Enum):
    """Connector health (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class AuthType(Enum):
    """Auth type (Enum subclass)."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    TOKEN = "token"
    NONE = "none"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RateLimitConfig:
    """Rate limit config."""
    max_requests: int = 100
    window_seconds: int = 60
    burst_limit: int = 10


@dataclass
class AuthConfig:
    """Auth config."""
    auth_type: AuthType = AuthType.OAUTH2
    credentials: Dict[str, str] = field(default_factory=dict)
    scopes: List[str] = field(default_factory=list)


@dataclass
class ModerationRule:
    """Moderation rule."""
    rule_id: str = ""
    name: str = ""
    platform: Optional[PlatformType] = None
    keywords: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    min_reputation_score: float = 0.0
    rate_limit_posts: int = 0
    action: ModerationAction = ModerationAction.FLAG
    enabled: bool = True


@dataclass
class QueueItem:
    """Queue item."""
    item_id: str = ""
    content_id: str = ""
    platform: PlatformType = PlatformType.FACEBOOK
    content_text: str = ""
    author_id: str = ""
    priority: QueuePriority = QueuePriority.MEDIUM
    verdict: ContentVerdict = ContentVerdict.SAFE
    categories: List[ViolationCategory] = field(default_factory=list)
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)
    status: str = "pending"


@dataclass
class Appeal:
    """Appeal."""
    appeal_id: str = ""
    content_id: str = ""
    platform: PlatformType = PlatformType.FACEBOOK
    appellant_id: str = ""
    reason: str = ""
    original_action: ModerationAction = ModerationAction.REJECT
    status: AppealStatus = AppealStatus.PENDING
    reviewer_id: str = ""
    outcome_notes: str = ""
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0


# ---------------------------------------------------------------------------
# Platform Connector
# ---------------------------------------------------------------------------

class PlatformConnector:
    """Adapter interface for a single social media platform."""

    def __init__(self, name: str, platform_type: PlatformType,
                 auth_config: Optional[AuthConfig] = None,
                 rate_limit: Optional[RateLimitConfig] = None,
                 capabilities: Optional[List[str]] = None):
        self.name = name
        self.platform_type = platform_type
        self.auth_config = auth_config or AuthConfig()
        self.rate_limit = rate_limit or RateLimitConfig()
        self.capabilities = capabilities or []
        self._lock = threading.RLock()
        self._health = ConnectorHealth.UNKNOWN
        self._enabled = True
        self._request_count = 0
        self._window_start = time.time()
        self._window_requests = 0
        self._content_queue: List[Dict[str, Any]] = []
        self._moderation_log: List[Dict[str, Any]] = []

    # -- rate limiting -------------------------------------------------------

    def _check_rate_limit(self) -> bool:
        now = time.time()
        with self._lock:
            if now - self._window_start >= self.rate_limit.window_seconds:
                self._window_start = now
                self._window_requests = 0
            if self._window_requests >= self.rate_limit.max_requests:
                return False
            self._window_requests += 1
            self._request_count += 1
            return True

    # -- public interface ----------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        with self._lock:
            if not self._enabled:
                self._health = ConnectorHealth.DISABLED
            else:
                self._health = ConnectorHealth.HEALTHY
            return {
                "platform": self.platform_type.value,
                "name": self.name,
                "health": self._health.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
            }

    def moderate_content(self, content_id: str, content_text: str,
                         author_id: str = "",
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            if not self._enabled:
                return {"error": "connector_disabled", "platform": self.platform_type.value}
            if not self._check_rate_limit():
                return {"error": "rate_limited", "platform": self.platform_type.value}
            entry = {
                "content_id": content_id,
                "platform": self.platform_type.value,
                "author_id": author_id,
                "content_text": content_text,
                "moderated_at": time.time(),
                "status": "moderated",
                "metadata": metadata or {},
            }
            capped_append(self._moderation_log, entry)
            return entry

    def get_content_queue(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._content_queue)

    def add_to_queue(self, item: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            item.setdefault("queued_at", time.time())
            capped_append(self._content_queue, item)
            return {"queued": True, "platform": self.platform_type.value, "item": item}

    def disable(self) -> Dict[str, Any]:
        with self._lock:
            self._enabled = False
            self._health = ConnectorHealth.DISABLED
            return {"platform": self.platform_type.value, "enabled": False}

    def enable(self) -> Dict[str, Any]:
        with self._lock:
            self._enabled = True
            self._health = ConnectorHealth.UNKNOWN
            return {"platform": self.platform_type.value, "enabled": True}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "platform": self.platform_type.value,
                "auth_type": self.auth_config.auth_type.value,
                "rate_limit_max": self.rate_limit.max_requests,
                "capabilities": self.capabilities,
                "health": self._health.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "queue_size": len(self._content_queue),
            }


# ---------------------------------------------------------------------------
# Content Classifier
# ---------------------------------------------------------------------------

class ContentClassifier:
    """Classify content as safe / warning / violation."""

    # Simple keyword lists used for adapter-level heuristic classification.
    _CATEGORY_KEYWORDS: Dict[ViolationCategory, List[str]] = {
        ViolationCategory.SPAM: ["buy now", "free money", "click here", "act now", "limited offer"],
        ViolationCategory.HARASSMENT: ["threat", "stalk", "bully", "intimidate"],
        ViolationCategory.HATE_SPEECH: ["hate", "slur", "bigot", "racist"],
        ViolationCategory.VIOLENCE: ["kill", "attack", "bomb", "weapon", "shoot"],
        ViolationCategory.ADULT_CONTENT: ["explicit", "nsfw", "xxx", "adult only"],
        ViolationCategory.MISINFORMATION: ["fake news", "hoax", "conspiracy", "debunked"],
        ViolationCategory.COPYRIGHT: ["pirated", "cracked", "illegal download", "torrent"],
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []

    def classify(self, content_text: str,
                 context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            text_lower = content_text.lower()
            matched: List[str] = []
            confidence = 0.0
            for cat, keywords in self._CATEGORY_KEYWORDS.items():
                for kw in keywords:
                    if kw in text_lower:
                        matched.append(cat.value)
                        confidence = max(confidence, 0.75)
                        break

            if not matched:
                verdict = ContentVerdict.SAFE.value
                confidence = 0.95
            elif len(matched) >= 2:
                verdict = ContentVerdict.VIOLATION.value
                confidence = min(confidence + 0.15, 1.0)
            else:
                verdict = ContentVerdict.WARNING.value

            result = {
                "verdict": verdict,
                "categories": matched,
                "confidence": round(confidence, 4),
                "content_length": len(content_text),
                "classified_at": time.time(),
                "context": context or {},
            }
            capped_append(self._history, result)
            return result

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)


# ---------------------------------------------------------------------------
# Auto-Moderation Rules Engine
# ---------------------------------------------------------------------------

class AutoModerationEngine:
    """Define and evaluate moderation rules per platform."""

    def __init__(self):
        self._lock = threading.RLock()
        self._rules: Dict[str, ModerationRule] = {}

    def add_rule(self, rule: ModerationRule) -> Dict[str, Any]:
        with self._lock:
            if not rule.rule_id:
                rule.rule_id = uuid.uuid4().hex[:12]
            self._rules[rule.rule_id] = rule
            return {"added": True, "rule_id": rule.rule_id, "name": rule.name}

    def remove_rule(self, rule_id: str) -> Dict[str, Any]:
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return {"removed": True, "rule_id": rule_id}
            return {"removed": False, "error": "rule_not_found"}

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._rules.get(rule_id)
            if not r:
                return None
            return self._rule_to_dict(r)

    def list_rules(self, platform: Optional[PlatformType] = None) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for r in self._rules.values():
                if platform and r.platform and r.platform != platform:
                    continue
                out.append(self._rule_to_dict(r))
            return out

    def evaluate(self, content_text: str, author_reputation: float = 1.0,
                 platform: Optional[PlatformType] = None) -> Dict[str, Any]:
        """Evaluate content against all matching rules."""
        with self._lock:
            triggered: List[Dict[str, Any]] = []
            text_lower = content_text.lower()
            for r in self._rules.values():
                if not r.enabled:
                    continue
                if platform and r.platform and r.platform != platform:
                    continue
                hit = False
                # keyword check
                for kw in r.keywords:
                    if kw.lower() in text_lower:
                        hit = True
                        break
                # regex check
                if not hit:
                    for pat in r.regex_patterns:
                        if re.search(pat, content_text, re.IGNORECASE):
                            hit = True
                            break
                # reputation check
                if r.min_reputation_score > 0 and author_reputation < r.min_reputation_score:
                    hit = True
                if hit:
                    triggered.append(self._rule_to_dict(r))

            worst_action = ModerationAction.APPROVE.value
            if triggered:
                action_priority = {
                    ModerationAction.APPROVE.value: 0,
                    ModerationAction.FLAG.value: 1,
                    ModerationAction.MUTE.value: 2,
                    ModerationAction.ESCALATE.value: 3,
                    ModerationAction.REJECT.value: 4,
                    ModerationAction.BAN.value: 5,
                }
                worst_action = max(
                    (t["action"] for t in triggered),
                    key=lambda a: action_priority.get(a, 0),
                )

            return {
                "triggered_rules": triggered,
                "recommended_action": worst_action,
                "rules_evaluated": len(self._rules),
            }

    @staticmethod
    def _rule_to_dict(r: ModerationRule) -> Dict[str, Any]:
        return {
            "rule_id": r.rule_id,
            "name": r.name,
            "platform": r.platform.value if r.platform else None,
            "keywords": r.keywords,
            "regex_patterns": r.regex_patterns,
            "min_reputation_score": r.min_reputation_score,
            "rate_limit_posts": r.rate_limit_posts,
            "action": r.action.value,
            "enabled": r.enabled,
        }


# ---------------------------------------------------------------------------
# Moderation Queue Manager
# ---------------------------------------------------------------------------

class ModerationQueueManager:
    """Priority queue for human review with auto-approve/reject."""

    def __init__(self, auto_approve_threshold: float = 0.9,
                 auto_reject_threshold: float = 0.85):
        self._lock = threading.RLock()
        self._queue: List[QueueItem] = []
        self._processed: List[Dict[str, Any]] = []
        self.auto_approve_threshold = auto_approve_threshold
        self.auto_reject_threshold = auto_reject_threshold

    def enqueue(self, item: QueueItem) -> Dict[str, Any]:
        with self._lock:
            if not item.item_id:
                item.item_id = uuid.uuid4().hex[:12]

            # Auto-approve safe content with high confidence
            if (item.verdict == ContentVerdict.SAFE
                    and item.confidence >= self.auto_approve_threshold):
                record = self._to_dict(item)
                record["auto_action"] = ModerationAction.APPROVE.value
                record["status"] = "auto_approved"
                capped_append(self._processed, record)
                return record

            # Auto-reject clear violations with high confidence
            if (item.verdict == ContentVerdict.VIOLATION
                    and item.confidence >= self.auto_reject_threshold):
                record = self._to_dict(item)
                record["auto_action"] = ModerationAction.REJECT.value
                record["status"] = "auto_rejected"
                capped_append(self._processed, record)
                return record

            # Otherwise queue for human review
            capped_append(self._queue, item)
            record = self._to_dict(item)
            record["status"] = "queued"
            return record

    def get_queue(self, platform: Optional[PlatformType] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = self._queue
            if platform:
                items = [i for i in items if i.platform == platform]
            # Sort by priority descending
            items = sorted(items, key=lambda i: i.priority.value, reverse=True)
            return [self._to_dict(i) for i in items]

    def process_item(self, item_id: str, action: ModerationAction,
                     reviewer_id: str = "") -> Dict[str, Any]:
        with self._lock:
            for idx, item in enumerate(self._queue):
                if item.item_id == item_id:
                    record = self._to_dict(item)
                    record["action"] = action.value
                    record["reviewer_id"] = reviewer_id
                    record["processed_at"] = time.time()
                    record["status"] = "processed"
                    capped_append(self._processed, record)
                    self._queue.pop(idx)
                    return record
            return {"error": "item_not_found", "item_id": item_id}

    def get_processed(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._processed)

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    @staticmethod
    def _to_dict(item: QueueItem) -> Dict[str, Any]:
        return {
            "item_id": item.item_id,
            "content_id": item.content_id,
            "platform": item.platform.value,
            "content_text": item.content_text,
            "author_id": item.author_id,
            "priority": item.priority.name,
            "verdict": item.verdict.value,
            "categories": [c.value for c in item.categories],
            "confidence": item.confidence,
            "created_at": item.created_at,
        }


# ---------------------------------------------------------------------------
# Cross-Platform Policy Enforcer
# ---------------------------------------------------------------------------

class CrossPlatformPolicyEnforcer:
    """Unified moderation policy applied across all platforms."""

    def __init__(self):
        self._lock = threading.RLock()
        self._global_policy: Dict[str, Any] = {
            "blocked_categories": [],
            "min_author_age_days": 0,
            "max_links_per_post": 5,
            "require_verification": False,
        }
        self._platform_overrides: Dict[str, Dict[str, Any]] = {}

    def set_global_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._global_policy.update(policy)
            return {"updated": True, "policy": dict(self._global_policy)}

    def get_global_policy(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._global_policy)

    def set_platform_override(self, platform: PlatformType,
                              overrides: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._platform_overrides[platform.value] = overrides
            return {"platform": platform.value, "overrides": overrides}

    def get_effective_policy(self, platform: PlatformType) -> Dict[str, Any]:
        with self._lock:
            policy = dict(self._global_policy)
            override = self._platform_overrides.get(platform.value, {})
            policy.update(override)
            policy["platform"] = platform.value
            return policy

    def enforce(self, content_text: str, platform: PlatformType,
                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            policy = self.get_effective_policy(platform)
            violations: List[str] = []
            meta = metadata or {}

            # Check blocked categories
            categories = meta.get("categories", [])
            blocked = policy.get("blocked_categories", [])
            for cat in categories:
                if cat in blocked:
                    violations.append(f"blocked_category:{cat}")

            # Check link count
            link_count = content_text.lower().count("http")
            max_links = policy.get("max_links_per_post", 5)
            if link_count > max_links:
                violations.append("too_many_links")

            # Check author age
            author_age = meta.get("author_age_days", 999)
            min_age = policy.get("min_author_age_days", 0)
            if author_age < min_age:
                violations.append("account_too_new")

            compliant = len(violations) == 0
            return {
                "compliant": compliant,
                "violations": violations,
                "platform": platform.value,
                "policy_applied": policy,
            }


# ---------------------------------------------------------------------------
# Moderation Analytics
# ---------------------------------------------------------------------------

class ModerationAnalytics:
    """Track moderation actions, false positives, response times, trends."""

    def __init__(self):
        self._lock = threading.RLock()
        self._actions: List[Dict[str, Any]] = []

    def record_action(self, platform: PlatformType, action: ModerationAction,
                      category: Optional[ViolationCategory] = None,
                      response_time_ms: float = 0.0,
                      is_false_positive: bool = False) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "platform": platform.value,
                "action": action.value,
                "category": category.value if category else None,
                "response_time_ms": response_time_ms,
                "is_false_positive": is_false_positive,
                "recorded_at": time.time(),
            }
            capped_append(self._actions, entry)
            return entry

    def get_summary(self, platform: Optional[PlatformType] = None) -> Dict[str, Any]:
        with self._lock:
            actions = self._actions
            if platform:
                actions = [a for a in actions if a["platform"] == platform.value]

            total = len(actions)
            if total == 0:
                return {
                    "total_actions": 0,
                    "false_positive_rate": 0.0,
                    "avg_response_time_ms": 0.0,
                    "actions_by_type": {},
                    "violations_by_category": {},
                }

            fp_count = sum(1 for a in actions if a["is_false_positive"])
            avg_rt = sum(a["response_time_ms"] for a in actions) / total

            by_type: Dict[str, int] = {}
            by_cat: Dict[str, int] = {}
            for a in actions:
                by_type[a["action"]] = by_type.get(a["action"], 0) + 1
                if a["category"]:
                    by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1

            return {
                "total_actions": total,
                "false_positive_rate": round(fp_count / total, 4),
                "avg_response_time_ms": round(avg_rt, 2),
                "actions_by_type": by_type,
                "violations_by_category": by_cat,
            }

    def get_platform_breakdown(self) -> Dict[str, Any]:
        with self._lock:
            breakdown: Dict[str, int] = {}
            for a in self._actions:
                p = a["platform"]
                breakdown[p] = breakdown.get(p, 0) + 1
            return {"platforms": breakdown, "total": len(self._actions)}

    def get_trend(self, platform: Optional[PlatformType] = None,
                  category: Optional[ViolationCategory] = None) -> List[Dict[str, Any]]:
        with self._lock:
            filtered = self._actions
            if platform:
                filtered = [a for a in filtered if a["platform"] == platform.value]
            if category:
                filtered = [a for a in filtered if a["category"] == category.value]
            return list(filtered)


# ---------------------------------------------------------------------------
# Appeal Handler
# ---------------------------------------------------------------------------

class AppealHandler:
    """Process content appeals, escalate, track outcomes."""

    def __init__(self):
        self._lock = threading.RLock()
        self._appeals: Dict[str, Appeal] = {}

    def submit_appeal(self, content_id: str, platform: PlatformType,
                      appellant_id: str, reason: str,
                      original_action: ModerationAction = ModerationAction.REJECT) -> Dict[str, Any]:
        with self._lock:
            appeal_id = uuid.uuid4().hex[:12]
            appeal = Appeal(
                appeal_id=appeal_id,
                content_id=content_id,
                platform=platform,
                appellant_id=appellant_id,
                reason=reason,
                original_action=original_action,
            )
            self._appeals[appeal_id] = appeal
            return self._to_dict(appeal)

    def review_appeal(self, appeal_id: str, reviewer_id: str,
                      approved: bool,
                      notes: str = "") -> Dict[str, Any]:
        with self._lock:
            appeal = self._appeals.get(appeal_id)
            if not appeal:
                return {"error": "appeal_not_found", "appeal_id": appeal_id}
            appeal.reviewer_id = reviewer_id
            appeal.outcome_notes = notes
            appeal.resolved_at = time.time()
            appeal.status = AppealStatus.APPROVED if approved else AppealStatus.DENIED
            return self._to_dict(appeal)

    def escalate_appeal(self, appeal_id: str) -> Dict[str, Any]:
        with self._lock:
            appeal = self._appeals.get(appeal_id)
            if not appeal:
                return {"error": "appeal_not_found", "appeal_id": appeal_id}
            appeal.status = AppealStatus.ESCALATED
            return self._to_dict(appeal)

    def get_appeal(self, appeal_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            appeal = self._appeals.get(appeal_id)
            if not appeal:
                return None
            return self._to_dict(appeal)

    def list_appeals(self, status: Optional[AppealStatus] = None,
                     platform: Optional[PlatformType] = None) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for a in self._appeals.values():
                if status and a.status != status:
                    continue
                if platform and a.platform != platform:
                    continue
                out.append(self._to_dict(a))
            return out

    def get_outcomes_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._appeals)
            by_status: Dict[str, int] = {}
            for a in self._appeals.values():
                s = a.status.value
                by_status[s] = by_status.get(s, 0) + 1
            return {"total_appeals": total, "by_status": by_status}

    @staticmethod
    def _to_dict(a: Appeal) -> Dict[str, Any]:
        return {
            "appeal_id": a.appeal_id,
            "content_id": a.content_id,
            "platform": a.platform.value,
            "appellant_id": a.appellant_id,
            "reason": a.reason,
            "original_action": a.original_action.value,
            "status": a.status.value,
            "reviewer_id": a.reviewer_id,
            "outcome_notes": a.outcome_notes,
            "created_at": a.created_at,
            "resolved_at": a.resolved_at,
        }


# ---------------------------------------------------------------------------
# Platform Connector Registry  (top-level facade)
# ---------------------------------------------------------------------------

# Default capabilities per platform
_PLATFORM_CAPABILITIES: Dict[PlatformType, List[str]] = {
    PlatformType.FACEBOOK: [
        "post_moderation", "comment_filtering", "page_management", "ad_review",
    ],
    PlatformType.INSTAGRAM: [
        "comment_moderation", "story_review", "hashtag_monitoring", "dm_filtering",
    ],
    PlatformType.TWITTER: [
        "tweet_moderation", "reply_filtering", "trend_monitoring", "bot_detection",
    ],
    PlatformType.YOUTUBE: [
        "comment_moderation", "video_review_queue", "live_chat_filtering",
        "community_guidelines",
    ],
    PlatformType.TIKTOK: [
        "comment_moderation", "duet_stitch_review", "sound_monitoring",
    ],
    PlatformType.REDDIT: [
        "post_comment_moderation", "subreddit_rule_enforcement", "spam_detection",
    ],
    PlatformType.LINKEDIN: [
        "post_moderation", "comment_filtering", "professional_content_standards",
    ],
    PlatformType.DISCORD: [
        "message_moderation", "channel_management", "role_based_filtering",
    ],
}


class SocialMediaModerationSystem:
    """Top-level orchestrator unifying all platform connectors and
    moderation capabilities."""

    def __init__(self):
        self._lock = threading.RLock()
        self.connectors: Dict[str, PlatformConnector] = {}
        self.classifier = ContentClassifier()
        self.rules_engine = AutoModerationEngine()
        self.queue_manager = ModerationQueueManager()
        self.policy_enforcer = CrossPlatformPolicyEnforcer()
        self.analytics = ModerationAnalytics()
        self.appeal_handler = AppealHandler()
        self._register_default_connectors()

    # -- bootstrap -----------------------------------------------------------

    def _register_default_connectors(self):
        for pt in PlatformType:
            caps = _PLATFORM_CAPABILITIES.get(pt, [])
            connector = PlatformConnector(
                name=f"{pt.value}_connector",
                platform_type=pt,
                capabilities=caps,
            )
            self.connectors[pt.value] = connector

    # -- connector management ------------------------------------------------

    def get_connector(self, platform: PlatformType) -> Optional[PlatformConnector]:
        with self._lock:
            return self.connectors.get(platform.value)

    def list_connectors(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.status() for c in self.connectors.values()]

    # -- unified moderation pipeline -----------------------------------------

    def moderate(self, content_text: str, platform: PlatformType,
                 content_id: str = "", author_id: str = "",
                 metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run content through classify → rules → policy → queue pipeline."""
        if not content_id:
            content_id = hashlib.sha256(content_text.encode()).hexdigest()[:16]

        start = time.time()

        # 1. Classify
        classification = self.classifier.classify(content_text)

        # 2. Rules engine
        rules_result = self.rules_engine.evaluate(content_text, platform=platform)

        # 3. Policy enforcement
        meta = metadata or {}
        meta["categories"] = classification["categories"]
        policy_result = self.policy_enforcer.enforce(content_text, platform, meta)

        # Determine verdict & priority
        verdict = ContentVerdict(classification["verdict"])
        priority = QueuePriority.MEDIUM
        if verdict == ContentVerdict.VIOLATION:
            priority = QueuePriority.CRITICAL
        elif verdict == ContentVerdict.WARNING:
            priority = QueuePriority.HIGH

        # 4. Enqueue
        q_item = QueueItem(
            content_id=content_id,
            platform=platform,
            content_text=content_text,
            author_id=author_id,
            priority=priority,
            verdict=verdict,
            categories=[ViolationCategory(c) for c in classification["categories"]],
            confidence=classification["confidence"],
        )
        queue_result = self.queue_manager.enqueue(q_item)

        # 5. Analytics
        action = ModerationAction.FLAG
        cat = None
        if classification["categories"]:
            cat = ViolationCategory(classification["categories"][0])
        elapsed = (time.time() - start) * 1000
        self.analytics.record_action(platform, action, category=cat,
                                     response_time_ms=elapsed)

        # 6. Connector log
        connector = self.get_connector(platform)
        if connector:
            connector.moderate_content(content_id, content_text, author_id)

        return {
            "content_id": content_id,
            "platform": platform.value,
            "classification": classification,
            "rules": rules_result,
            "policy": policy_result,
            "queue": queue_result,
        }

    # -- status --------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connectors": len(self.connectors),
                "connector_details": self.list_connectors(),
                "queue_size": self.queue_manager.queue_size(),
                "rules_count": len(self.rules_engine._rules),
                "analytics_summary": self.analytics.get_summary(),
                "appeals_summary": self.appeal_handler.get_outcomes_summary(),
            }
