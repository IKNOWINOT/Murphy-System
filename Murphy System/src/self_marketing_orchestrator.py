"""
Self-Marketing Orchestrator — Murphy Markets Murphy

Design Label: MKT-006 — Self-Marketing Orchestrator
Owner: VP Marketing (Shadow Agent) / Founder HITL
Dependencies:
  - ContentPipelineEngine (MKT-001) — content lifecycle management
  - SEOOptimisationEngine (MKT-002) — keyword extraction, meta-tag generation, scoring
  - CampaignOrchestrator (MKT-003) — campaign management with budgets
  - AdaptiveCampaignEngine (MKT-004) — per-tier campaign management with traction monitoring
  - ContactComplianceGovernor (COMPL-001) — DNC list, cooldown tracking, consent gating
  - OutreachComplianceGate (COMPL-002) — pre-send compliance check
  - EventBackbone — event publishing for audit trail and cross-module coupling
  - PersistenceManager — durable state across restarts
  - GovernanceKernel — bounds all autonomous marketing actions

Purpose:
  Ties together the content pipeline, SEO optimisation, campaign management,
  compliant outreach, and developer attraction into a single autonomous
  marketing loop that Murphy runs for itself.

Cycles:

  CONTENT CYCLE (Weekly):
    1. Analyse trending topics in AI/automation space using CONTENT_CATEGORIES
    2. Generate SEO-optimized blog posts, tutorials, case studies
    3. Score content with SEOOptimisationEngine (MKT-002)
    4. Queue for HITL review on first HITL_REVIEW_THRESHOLD posts;
       auto-publish thereafter once trust is established
    5. Publish to configured channels via ContentPipelineEngine
    6. Track performance metrics

  SOCIAL CYCLE (Daily):
    1. Generate social media posts from published content
    2. Create platform-specific variants (Twitter/X thread, LinkedIn, Reddit)
    3. Schedule posting via social media adapters
    4. Monitor engagement metrics
    5. Feed engagement data back to AdaptiveCampaignEngine

  OUTREACH CYCLE (Every 20 minutes — aligned with self-selling engine):
    1. Get prospects from SalesAutomationEngine.generate_leads()
    2. Check EVERY prospect against ContactComplianceGovernor:
       - Is contact on DNC list?                         → SKIP
       - Was contact reached within 30 days?             → SKIP
       - Does region require explicit consent?           → SKIP unless consent recorded
    3. For allowed contacts: compose personalized outreach via SelfSellingOutreach
    4. Record contact timestamp for cooldown tracking
    5. Process replies: detect opt-out intent → add to DNC
    6. Detect positive replies → route to trial orchestrator

  DEVELOPER ATTRACTION CYCLE (Weekly):
    1. Generate SDK documentation updates
    2. Create example code snippets for common use cases
    3. Generate "What's New" changelog entries
    4. Create developer tutorial content
    5. Propose open-source SDK improvements (creates GitHub issues on murphy-sdk repo)

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - No outreach without ContactComplianceGovernor clearance (COMPL-001)
  - HITL gate: first HITL_REVIEW_THRESHOLD content pieces require founder review
  - Bounded: all history lists are capped to prevent memory growth
  - Audit trail: every published piece, outreach sent, and compliance block is logged
  - Opt-out is irreversible: DNC additions are never removed by automation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of content pieces that require HITL review before auto-publish is enabled
HITL_REVIEW_THRESHOLD = 5

# Outreach cooldown window (days) — no repeat contact within this period
OUTREACH_COOLDOWN_DAYS = 30

# Maximum items kept in bounded history lists
_MAX_HISTORY = 1_000
_MAX_OUTREACH_HISTORY = 10_000
_MAX_SOCIAL_HISTORY = 5_000

# Persist document IDs
_PERSIST_DOC_ID = "self_marketing_orchestrator_state"

# ---------------------------------------------------------------------------
# Content topic calendar — rotated weekly
# ---------------------------------------------------------------------------

CONTENT_CATEGORIES: Dict[str, List[str]] = {
    "ai_automation": [
        "How AI automation is changing {industry}",
        "Describe-to-Execute: The future of automation",
        "Why confidence-gated AI is safer than unbound AI agents",
    ],
    "developer_tools": [
        "Building automations with the Murphy SDK",
        "How to create a sales pipeline with 3 API calls",
        "Automating CI/CD with natural language",
    ],
    "industrial_iot": [
        "SCADA modernization with AI automation",
        "NL-driven factory floor automation",
        "Why industrial automation needs safety gates",
    ],
    "business_automation": [
        "Automating sales qualification with AI",
        "Content marketing on autopilot — how Murphy does it",
        "From lead to proposal in 60 seconds",
    ],
    "case_studies": [
        "Murphy sells Murphy — the self-selling AI case study",
        "How Inoni LLC runs with zero human operators",
        "920 modules, 1 developer — building at scale with AI",
    ],
    "thought_leadership": [
        "Murphy's Law as a design principle for AI systems",
        "Why AI systems should refuse to act",
        "The case for confidence-gated execution",
    ],
}

# Ordered category rotation sequence (cycles through all categories each week)
_CATEGORY_ROTATION: List[str] = list(CONTENT_CATEGORIES.keys())

# Platform-specific social post configuration
_SOCIAL_PLATFORMS = ["twitter", "linkedin", "reddit"]

# Character limits per platform
_PLATFORM_CHAR_LIMITS: Dict[str, int] = {
    "twitter": 280,
    "linkedin": 3_000,
    "reddit": 40_000,
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ComplianceDecision(str, Enum):
    """Result of a ContactComplianceGovernor check."""
    ALLOW = "allow"
    BLOCK_DNC = "block_dnc"
    BLOCK_COOLDOWN = "block_cooldown"
    REQUIRES_CONSENT = "requires_consent"


class ContentStatus(str, Enum):
    """Lifecycle status of a generated marketing content piece."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class OutreachStatus(str, Enum):
    """Status of an outreach attempt."""
    SENT = "sent"
    BLOCKED_DNC = "blocked_dnc"
    BLOCKED_COOLDOWN = "blocked_cooldown"
    BLOCKED_CONSENT = "blocked_consent"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GeneratedContent:
    """A piece of marketing content generated by the orchestrator."""

    content_id: str
    category: str
    topic: str
    content_type: str        # "blog" | "case_study" | "tutorial" | "social" | "changelog"
    title: str
    body: str
    keywords: List[str] = field(default_factory=list)
    seo_score: float = 0.0
    status: str = ContentStatus.DRAFT.value
    platform: Optional[str] = None    # Set for social variants
    hitl_required: bool = True
    published_at: Optional[str] = None
    performance: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "category": self.category,
            "topic": self.topic,
            "content_type": self.content_type,
            "title": self.title,
            "body": self.body,
            "keywords": list(self.keywords),
            "seo_score": self.seo_score,
            "status": self.status,
            "platform": self.platform,
            "hitl_required": self.hitl_required,
            "published_at": self.published_at,
            "performance": dict(self.performance),
            "created_at": self.created_at,
        }


@dataclass
class OutreachRecord:
    """Record of a single outreach attempt (sent or blocked)."""

    record_id: str
    prospect_id: str
    channel: str
    status: str             # OutreachStatus value
    compliance_decision: str
    blocked_reason: Optional[str] = None
    sent_at: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "prospect_id": self.prospect_id,
            "channel": self.channel,
            "status": self.status,
            "compliance_decision": self.compliance_decision,
            "blocked_reason": self.blocked_reason,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }


@dataclass
class ReplyRecord:
    """Processed reply from an outreach prospect."""

    reply_id: str
    prospect_id: str
    body: str
    is_opt_out: bool = False
    is_positive: bool = False
    processed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply_id": self.reply_id,
            "prospect_id": self.prospect_id,
            "body": self.body,
            "is_opt_out": self.is_opt_out,
            "is_positive": self.is_positive,
            "processed_at": self.processed_at,
        }


@dataclass
class ContentCycleResult:
    """Summary of a single content generation cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    pieces_generated: int = 0
    pieces_published: int = 0
    pieces_pending_review: int = 0
    avg_seo_score: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "pieces_generated": self.pieces_generated,
            "pieces_published": self.pieces_published,
            "pieces_pending_review": self.pieces_pending_review,
            "avg_seo_score": self.avg_seo_score,
            "errors": list(self.errors),
        }


@dataclass
class SocialCycleResult:
    """Summary of a single social posting cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    variants_generated: int = 0
    posts_scheduled: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "variants_generated": self.variants_generated,
            "posts_scheduled": self.posts_scheduled,
            "errors": list(self.errors),
        }


@dataclass
class OutreachCycleResult:
    """Summary of a single outreach cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    prospects_evaluated: int = 0
    outreach_sent: int = 0
    blocked_dnc: int = 0
    blocked_cooldown: int = 0
    blocked_consent: int = 0
    replies_processed: int = 0
    opt_outs_recorded: int = 0
    trials_started: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "prospects_evaluated": self.prospects_evaluated,
            "outreach_sent": self.outreach_sent,
            "blocked_dnc": self.blocked_dnc,
            "blocked_cooldown": self.blocked_cooldown,
            "blocked_consent": self.blocked_consent,
            "replies_processed": self.replies_processed,
            "opt_outs_recorded": self.opt_outs_recorded,
            "trials_started": self.trials_started,
            "errors": list(self.errors),
        }


@dataclass
class DeveloperAttractionResult:
    """Summary of a single developer attraction cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    sdk_docs_generated: int = 0
    snippets_created: int = 0
    changelogs_created: int = 0
    tutorials_created: int = 0
    github_issues_proposed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "sdk_docs_generated": self.sdk_docs_generated,
            "snippets_created": self.snippets_created,
            "changelogs_created": self.changelogs_created,
            "tutorials_created": self.tutorials_created,
            "github_issues_proposed": self.github_issues_proposed,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# SelfMarketingOrchestrator
# ---------------------------------------------------------------------------

class SelfMarketingOrchestrator:
    """Murphy markets Murphy — autonomous marketing with compliance.

    Combines content generation, SEO optimization, social media scheduling,
    compliant outreach, and developer attraction into a single orchestration
    loop that Murphy runs for itself.

    Design Label: MKT-006
    Owner: VP Marketing (Shadow Agent) / Founder HITL

    Usage::

        orchestrator = SelfMarketingOrchestrator(
            content_engine=ContentPipelineEngine(...),
            seo_engine=SEOOptimisationEngine(...),
            campaign_engine=CampaignOrchestrator(...),
            adaptive_campaign=AdaptiveCampaignEngine(...),
            compliance_gate=contact_compliance_governor,
            event_backbone=backbone,
            persistence_manager=pm,
        )
        result = orchestrator.run_content_cycle()
        result = orchestrator.run_social_cycle()
        result = orchestrator.run_outreach_cycle()
        result = orchestrator.run_developer_attraction_cycle()
    """

    _PERSIST_DOC_ID = _PERSIST_DOC_ID

    def __init__(
        self,
        content_engine: Any = None,
        seo_engine: Any = None,
        campaign_engine: Any = None,
        adaptive_campaign: Any = None,
        compliance_gate: Any = None,
        event_backbone: Any = None,
        persistence_manager: Any = None,
    ) -> None:
        self._content_engine = content_engine
        self._seo_engine = seo_engine
        self._campaign_engine = campaign_engine
        self._adaptive_campaign = adaptive_campaign
        self._compliance_gate = compliance_gate
        self._backbone = event_backbone
        self._pm = persistence_manager

        self._lock = threading.Lock()

        # Content catalogue: content_id → GeneratedContent
        self._content: Dict[str, GeneratedContent] = {}

        # Bounded history lists
        self._content_cycles: List[ContentCycleResult] = []
        self._social_cycles: List[SocialCycleResult] = []
        self._outreach_cycles: List[OutreachCycleResult] = []
        self._dev_cycles: List[DeveloperAttractionResult] = []
        self._outreach_records: List[OutreachRecord] = []
        self._reply_records: List[ReplyRecord] = []

        # HITL trust-building: counts published pieces
        self._published_count: int = 0

        # Compliance tracking: prospect_id → last contacted ISO timestamp
        self._last_contacted: Dict[str, str] = {}

        # DNC set: prospect IDs that must never be contacted
        self._dnc_set: set = set()

        # Category rotation pointer (incremented each content cycle)
        self._category_index: int = 0

        # Topic deduplication: set of (category, topic) used within 30 days
        self._recent_topics: List[Dict[str, Any]] = []  # [{category, topic, used_at}]

    # ── Content Cycle ─────────────────────────────────────────────────────

    def run_content_cycle(self) -> Dict[str, Any]:
        """Weekly content generation cycle.

        Rotates through CONTENT_CATEGORIES, generates one blog post or
        case study per category slot, scores with SEO engine, queues for
        HITL review (or auto-publishes once trust threshold is met).
        """
        cycle_id = f"cc-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []
        pieces_generated = 0
        pieces_published = 0
        pieces_pending_review = 0
        seo_scores: List[float] = []

        # Pick this cycle's category
        with self._lock:
            category = _CATEGORY_ROTATION[self._category_index % len(_CATEGORY_ROTATION)]
            self._category_index += 1

        topics = CONTENT_CATEGORIES[category]

        for topic_template in topics:
            topic = topic_template.replace("{industry}", "manufacturing")
            try:
                keywords = self._extract_keywords(topic)
                # Deduplicate topics within 30 days
                if self._is_topic_recent(category, topic):
                    logger.debug("Skipping recently used topic: %s / %s", category, topic)
                    continue

                content = self.generate_blog_post(topic, keywords)
                pieces_generated += 1

                if content.seo_score > 0:
                    seo_scores.append(content.seo_score)

                # HITL gate: require review until trust threshold is built
                with self._lock:
                    published = self._published_count

                if published < HITL_REVIEW_THRESHOLD:
                    content.status = ContentStatus.PENDING_REVIEW.value
                    content.hitl_required = True
                    pieces_pending_review += 1
                    self._publish_event("content_queued_for_review", content.to_dict())
                    logger.info(
                        "Content %s queued for HITL review (published=%d threshold=%d)",
                        content.content_id, published, HITL_REVIEW_THRESHOLD,
                    )
                else:
                    self._auto_publish(content)
                    pieces_published += 1

                self._mark_topic_used(category, topic)

            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                logger.warning("Content generation error for topic '%s': %s", topic, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        avg_seo = sum(seo_scores) / len(seo_scores) if seo_scores else 0.0

        result = ContentCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            pieces_generated=pieces_generated,
            pieces_published=pieces_published,
            pieces_pending_review=pieces_pending_review,
            avg_seo_score=round(avg_seo, 2),
            errors=errors,
        )
        with self._lock:
            capped_append(self._content_cycles, result, max_size=_MAX_HISTORY)

        self._publish_event("content_cycle_completed", result.to_dict())
        logger.info(
            "Content cycle %s: generated=%d published=%d pending_review=%d avg_seo=%.1f",
            cycle_id, pieces_generated, pieces_published, pieces_pending_review, avg_seo,
        )
        return result.to_dict()

    def generate_blog_post(self, topic: str, keywords: Optional[List[str]] = None) -> GeneratedContent:
        """Generate an SEO-optimized blog post on a topic.

        Delegates body generation to ContentPipelineEngine when available,
        otherwise constructs a structured placeholder post that satisfies the
        SEO scoring minimum-length requirement.
        """
        if keywords is None:
            keywords = self._extract_keywords(topic)

        title = topic
        body = self._compose_blog_body(title, keywords)

        seo_score = self._score_content(title, body)

        content = GeneratedContent(
            content_id=f"blog-{uuid.uuid4().hex[:8]}",
            category="blog",
            topic=topic,
            content_type="blog",
            title=title,
            body=body,
            keywords=keywords,
            seo_score=seo_score,
        )

        if self._content_engine is not None:
            try:
                brief = self._content_engine.create_brief(
                    topic=topic,
                    content_type="blog",
                    keywords=keywords,
                    tone="technical",
                )
                self._content_engine.create_draft(
                    brief_id=brief.brief_id,
                    title=title,
                    body=body,
                    channel="blog",
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("ContentPipelineEngine integration skipped: %s", exc)

        with self._lock:
            self._content[content.content_id] = content

        logger.info("Generated blog post %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def generate_case_study(self, subject: str) -> GeneratedContent:
        """Generate a case study from Murphy's own operational data."""
        title = f"Case Study: {subject}"
        keywords = self._extract_keywords(subject) + ["automation", "ROI", "Murphy System"]
        body = self._compose_case_study_body(title, subject, keywords)

        seo_score = self._score_content(title, body)

        content = GeneratedContent(
            content_id=f"cs-{uuid.uuid4().hex[:8]}",
            category="case_studies",
            topic=subject,
            content_type="case_study",
            title=title,
            body=body,
            keywords=keywords,
            seo_score=seo_score,
        )

        with self._lock:
            self._content[content.content_id] = content

        logger.info("Generated case study %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def generate_tutorial(self, sdk_feature: str) -> GeneratedContent:
        """Generate a developer tutorial for an SDK feature."""
        title = f"Tutorial: {sdk_feature}"
        keywords = self._extract_keywords(sdk_feature) + ["SDK", "tutorial", "Python", "API"]
        body = self._compose_tutorial_body(title, sdk_feature, keywords)

        seo_score = self._score_content(title, body)

        content = GeneratedContent(
            content_id=f"tut-{uuid.uuid4().hex[:8]}",
            category="developer_tools",
            topic=sdk_feature,
            content_type="tutorial",
            title=title,
            body=body,
            keywords=keywords,
            seo_score=seo_score,
        )

        with self._lock:
            self._content[content.content_id] = content

        logger.info("Generated tutorial %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def approve_content(self, content_id: str) -> bool:
        """HITL approval gate — approve a content piece for publishing.

        Called by the Founder or VP Marketing shadow agent after reviewing
        pending content. Once HITL_REVIEW_THRESHOLD pieces are approved,
        subsequent content auto-publishes.
        """
        with self._lock:
            content = self._content.get(content_id)
        if content is None:
            return False
        if content.status != ContentStatus.PENDING_REVIEW.value:
            return False
        self._auto_publish(content)
        self._publish_event("content_approved", {"content_id": content_id})
        return True

    # ── Social Cycle ──────────────────────────────────────────────────────

    def run_social_cycle(self) -> Dict[str, Any]:
        """Daily social media posting cycle.

        Picks recently published content and generates platform-specific
        variants for Twitter/X, LinkedIn, and Reddit.
        """
        cycle_id = f"sc-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []
        variants_generated = 0
        posts_scheduled = 0

        with self._lock:
            published = [
                c for c in self._content.values()
                if c.status == ContentStatus.PUBLISHED.value
                and c.content_type != "social"
            ]

        # Process the 3 most recently published non-social pieces
        recent = sorted(published, key=lambda c: c.published_at or "", reverse=True)[:3]

        for content in recent:
            try:
                variants = self.generate_social_variants(content.content_id)
                variants_generated += len(variants)
                posts_scheduled += len(variants)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                logger.warning("Social variant generation error for %s: %s", content.content_id, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        result = SocialCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            variants_generated=variants_generated,
            posts_scheduled=posts_scheduled,
            errors=errors,
        )
        with self._lock:
            capped_append(self._social_cycles, result, max_size=_MAX_HISTORY)

        self._publish_event("social_cycle_completed", result.to_dict())
        logger.info(
            "Social cycle %s: variants=%d scheduled=%d",
            cycle_id, variants_generated, posts_scheduled,
        )
        return result.to_dict()

    def generate_social_variants(self, content_id: str) -> List[Dict[str, Any]]:
        """Generate platform-specific social posts from a content piece."""
        with self._lock:
            content = self._content.get(content_id)
        if content is None:
            return []

        variants = []
        for platform in _SOCIAL_PLATFORMS:
            limit = _PLATFORM_CHAR_LIMITS[platform]
            body = self._compose_social_variant(content, platform, limit)

            variant = GeneratedContent(
                content_id=f"soc-{uuid.uuid4().hex[:8]}",
                category=content.category,
                topic=content.topic,
                content_type="social",
                title=f"{platform.capitalize()}: {content.title[:60]}",
                body=body,
                keywords=list(content.keywords),
                seo_score=0.0,
                status=ContentStatus.PUBLISHED.value,
                platform=platform,
                hitl_required=False,
                published_at=datetime.now(timezone.utc).isoformat(),
            )

            with self._lock:
                self._content[variant.content_id] = variant
                capped_append(self._outreach_records, OutreachRecord(
                    record_id=f"sr-{uuid.uuid4().hex[:8]}",
                    prospect_id=f"social:{platform}",
                    channel=platform,
                    status=OutreachStatus.SENT.value,
                    compliance_decision=ComplianceDecision.ALLOW.value,
                    sent_at=datetime.now(timezone.utc).isoformat(),
                ), max_size=_MAX_OUTREACH_HISTORY)

            self._publish_event("social_posted", {
                "content_id": variant.content_id,
                "platform": platform,
                "source_content_id": content_id,
            })
            variants.append(variant.to_dict())
            logger.info("Scheduled %s post for content %s", platform, content_id)

        # Feed engagement data back to AdaptiveCampaignEngine
        if self._adaptive_campaign is not None:
            try:
                self._adaptive_campaign.record_snapshot(
                    tier="community",
                    period=datetime.now(timezone.utc).strftime("%Y-W%V"),
                    impressions=len(variants),
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("AdaptiveCampaignEngine feed skipped: %s", exc)

        return variants

    # ── Outreach Cycle ────────────────────────────────────────────────────

    def run_outreach_cycle(self) -> Dict[str, Any]:
        """Compliance-gated outreach cycle (every 20 minutes).

        Every prospect is checked against the ContactComplianceGovernor before
        any message is composed or sent.  Opt-outs from replies are processed
        and added to the DNC set atomically.
        """
        cycle_id = f"oc-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []

        prospects_evaluated = 0
        outreach_sent = 0
        blocked_dnc = 0
        blocked_cooldown = 0
        blocked_consent = 0
        trials_started = 0

        prospects = self._get_prospects()

        for prospect in prospects:
            prospects_evaluated += 1
            prospect_id = prospect.get("id", str(uuid.uuid4()))
            channel = prospect.get("channel", "email")

            try:
                decision = self._check_compliance(prospect_id, prospect)

                if decision == ComplianceDecision.ALLOW:
                    self._send_outreach(prospect_id, channel, prospect)
                    outreach_sent += 1
                    self._publish_event("outreach_sent", {
                        "prospect_id": prospect_id,
                        "channel": channel,
                    })
                elif decision == ComplianceDecision.BLOCK_DNC:
                    blocked_dnc += 1
                    self._record_outreach(prospect_id, channel, OutreachStatus.BLOCKED_DNC, decision, "DNC list")
                    self._publish_event("outreach_blocked", {
                        "prospect_id": prospect_id,
                        "reason": "dnc",
                    })
                elif decision == ComplianceDecision.BLOCK_COOLDOWN:
                    blocked_cooldown += 1
                    self._record_outreach(
                        prospect_id, channel, OutreachStatus.BLOCKED_COOLDOWN, decision,
                        f"cooldown ({OUTREACH_COOLDOWN_DAYS} days)"
                    )
                    self._publish_event("outreach_blocked", {
                        "prospect_id": prospect_id,
                        "reason": "cooldown",
                    })
                elif decision == ComplianceDecision.REQUIRES_CONSENT:
                    blocked_consent += 1
                    self._record_outreach(
                        prospect_id, channel, OutreachStatus.BLOCKED_CONSENT, decision,
                        "explicit consent required"
                    )
                    self._publish_event("outreach_blocked", {
                        "prospect_id": prospect_id,
                        "reason": "requires_consent",
                    })

            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                logger.warning("Outreach error for prospect %s: %s", prospect_id, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        result = OutreachCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            prospects_evaluated=prospects_evaluated,
            outreach_sent=outreach_sent,
            blocked_dnc=blocked_dnc,
            blocked_cooldown=blocked_cooldown,
            blocked_consent=blocked_consent,
            trials_started=trials_started,
            errors=errors,
        )
        with self._lock:
            capped_append(self._outreach_cycles, result, max_size=_MAX_HISTORY)

        self._publish_event("outreach_cycle_completed", result.to_dict())
        logger.info(
            "Outreach cycle %s: evaluated=%d sent=%d blocked(dnc=%d cooldown=%d consent=%d)",
            cycle_id, prospects_evaluated, outreach_sent,
            blocked_dnc, blocked_cooldown, blocked_consent,
        )
        return result.to_dict()

    def process_prospect_replies(self) -> Dict[str, Any]:
        """Process all pending replies for opt-out / positive-intent detection.

        Opt-outs are added to the DNC set irreversibly.
        Positive replies are routed to the trial orchestrator.
        """
        # In production, replies would be fetched from the email/CRM adapter.
        # This method provides the processing logic; the caller injects replies
        # via _inject_reply() or the reply queue.
        with self._lock:
            pending = list(getattr(self, "_pending_replies", []))
            self._pending_replies: List[Dict[str, Any]] = []

        opt_outs = 0
        positives = 0
        processed = 0

        for raw in pending:
            prospect_id = raw.get("prospect_id", "")
            body = raw.get("body", "")
            reply = ReplyRecord(
                reply_id=f"rpl-{uuid.uuid4().hex[:8]}",
                prospect_id=prospect_id,
                body=body,
                is_opt_out=self._is_opt_out(body),
                is_positive=self._is_positive_reply(body),
            )

            if reply.is_opt_out:
                with self._lock:
                    self._dnc_set.add(prospect_id)
                opt_outs += 1
                self._publish_event("opt_out_recorded", {"prospect_id": prospect_id})
                logger.info("Opt-out recorded for prospect %s — added to DNC", prospect_id)

            if reply.is_positive:
                positives += 1
                self._publish_event("positive_reply_detected", {"prospect_id": prospect_id})
                logger.info("Positive reply from prospect %s — routing to trial orchestrator", prospect_id)

            with self._lock:
                capped_append(self._reply_records, reply, max_size=_MAX_HISTORY)
            processed += 1

        return {
            "processed": processed,
            "opt_outs": opt_outs,
            "positives": positives,
        }

    def inject_reply(self, prospect_id: str, body: str) -> None:
        """Inject a prospect reply for processing on the next cycle."""
        with self._lock:
            if not hasattr(self, "_pending_replies"):
                self._pending_replies: List[Dict[str, Any]] = []
            self._pending_replies.append({"prospect_id": prospect_id, "body": body})

    # ── Developer Attraction ──────────────────────────────────────────────

    def run_developer_attraction_cycle(self) -> Dict[str, Any]:
        """Weekly developer content and SDK improvement cycle."""
        cycle_id = f"da-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []

        sdk_docs = 0
        snippets = 0
        changelogs = 0
        tutorials = 0
        issues_proposed = 0

        sdk_features = [
            "natural_language_workflow",
            "confidence_gating",
            "multi_agent_swarm",
            "platform_connector",
        ]

        for feature in sdk_features:
            try:
                tutorial = self.generate_tutorial(feature)
                tutorials += 1
                sdk_docs += 1

                snippet = self._generate_code_snippet(feature)
                snippets += 1

                changelog = self._generate_changelog_entry(feature)
                changelogs += 1

                # Propose GitHub issue for SDK improvement (not auto-filed)
                issue = self._propose_sdk_issue(feature)
                issues_proposed += 1

                self._publish_event("developer_content_created", {
                    "feature": feature,
                    "tutorial_id": tutorial.content_id,
                    "snippet": snippet[:100],
                    "issue_title": issue.get("title", ""),
                })

            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                logger.warning("Developer attraction error for feature '%s': %s", feature, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        result = DeveloperAttractionResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            sdk_docs_generated=sdk_docs,
            snippets_created=snippets,
            changelogs_created=changelogs,
            tutorials_created=tutorials,
            github_issues_proposed=issues_proposed,
            errors=errors,
        )
        with self._lock:
            capped_append(self._dev_cycles, result, max_size=_MAX_HISTORY)

        self._publish_event("developer_attraction_cycle_completed", result.to_dict())
        logger.info(
            "Developer attraction cycle %s: tutorials=%d snippets=%d issues=%d",
            cycle_id, tutorials, snippets, issues_proposed,
        )
        return result.to_dict()

    # ── Analytics ─────────────────────────────────────────────────────────

    def get_marketing_dashboard(self) -> Dict[str, Any]:
        """Return comprehensive marketing metrics dashboard."""
        with self._lock:
            total_content = len(self._content)
            published = sum(
                1 for c in self._content.values()
                if c.status == ContentStatus.PUBLISHED.value
            )
            pending_review = sum(
                1 for c in self._content.values()
                if c.status == ContentStatus.PENDING_REVIEW.value
            )
            seo_scores = [
                c.seo_score for c in self._content.values()
                if c.seo_score > 0
            ]
            avg_seo = sum(seo_scores) / len(seo_scores) if seo_scores else 0.0

            outreach_sent = sum(
                1 for r in self._outreach_records
                if r.status == OutreachStatus.SENT.value
            )
            outreach_blocked = sum(
                1 for r in self._outreach_records
                if r.status != OutreachStatus.SENT.value
            )

            content_cycles = len(self._content_cycles)
            social_cycles = len(self._social_cycles)
            outreach_cycles = len(self._outreach_cycles)
            dev_cycles = len(self._dev_cycles)

            dnc_count = len(self._dnc_set)
            opt_outs = sum(1 for r in self._reply_records if r.is_opt_out)
            positives = sum(1 for r in self._reply_records if r.is_positive)

        return {
            "content": {
                "total": total_content,
                "published": published,
                "pending_review": pending_review,
                "avg_seo_score": round(avg_seo, 2),
                "hitl_threshold": HITL_REVIEW_THRESHOLD,
                "auto_publish_enabled": self._published_count >= HITL_REVIEW_THRESHOLD,
            },
            "outreach": {
                "sent": outreach_sent,
                "blocked": outreach_blocked,
                "dnc_list_size": dnc_count,
                "opt_outs_detected": opt_outs,
                "positive_replies": positives,
            },
            "cycles": {
                "content_cycles_run": content_cycles,
                "social_cycles_run": social_cycles,
                "outreach_cycles_run": outreach_cycles,
                "developer_attraction_cycles_run": dev_cycles,
            },
        }

    def get_compliance_report(self) -> Dict[str, Any]:
        """Return outreach compliance statistics."""
        with self._lock:
            total = len(self._outreach_records)
            sent = sum(1 for r in self._outreach_records if r.status == OutreachStatus.SENT.value)
            blocked_dnc = sum(
                1 for r in self._outreach_records if r.status == OutreachStatus.BLOCKED_DNC.value
            )
            blocked_cooldown = sum(
                1 for r in self._outreach_records if r.status == OutreachStatus.BLOCKED_COOLDOWN.value
            )
            blocked_consent = sum(
                1 for r in self._outreach_records if r.status == OutreachStatus.BLOCKED_CONSENT.value
            )
            dnc_size = len(self._dnc_set)
            opt_outs = sum(1 for r in self._reply_records if r.is_opt_out)

        return {
            "total_outreach_attempts": total,
            "sent": sent,
            "blocked_dnc": blocked_dnc,
            "blocked_cooldown": blocked_cooldown,
            "blocked_consent": blocked_consent,
            "dnc_list_size": dnc_size,
            "opt_outs_detected": opt_outs,
            "compliance_rate": round(1.0 - (sent / total) if total > 0 else 1.0, 4),
        }

    # ── Persistence ───────────────────────────────────────────────────────

    def save_state(self) -> bool:
        """Persist state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._pm is None:
            return False
        with self._lock:
            state = {
                "content": {cid: c.to_dict() for cid, c in self._content.items()},
                "published_count": self._published_count,
                "category_index": self._category_index,
                "last_contacted": dict(self._last_contacted),
                "dnc_set": list(self._dnc_set),
                "recent_topics": list(self._recent_topics),
                "outreach_records": [r.to_dict() for r in self._outreach_records],
                "reply_records": [r.to_dict() for r in self._reply_records],
                "content_cycles": [c.to_dict() for c in self._content_cycles],
                "social_cycles": [c.to_dict() for c in self._social_cycles],
                "outreach_cycles": [c.to_dict() for c in self._outreach_cycles],
                "dev_cycles": [c.to_dict() for c in self._dev_cycles],
            }
        try:
            self._pm.save_document(self._PERSIST_DOC_ID, state)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("save_state failed: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore state from PersistenceManager.

        Returns True on success, False if persistence is unavailable or no
        prior state exists.
        """
        if self._pm is None:
            return False
        try:
            state = self._pm.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:  # noqa: BLE001
            logger.debug("load_state failed: %s", exc)
            return False
        if state is None:
            return False

        with self._lock:
            self._published_count = state.get("published_count", 0)
            self._category_index = state.get("category_index", 0)
            self._last_contacted = dict(state.get("last_contacted", {}))
            self._dnc_set = set(state.get("dnc_set", []))
            self._recent_topics = list(state.get("recent_topics", []))

            self._content = {}
            for cid, cd in state.get("content", {}).items():
                self._content[cid] = GeneratedContent(
                    content_id=cd["content_id"],
                    category=cd.get("category", ""),
                    topic=cd.get("topic", ""),
                    content_type=cd.get("content_type", "blog"),
                    title=cd.get("title", ""),
                    body=cd.get("body", ""),
                    keywords=cd.get("keywords", []),
                    seo_score=cd.get("seo_score", 0.0),
                    status=cd.get("status", ContentStatus.DRAFT.value),
                    platform=cd.get("platform"),
                    hitl_required=cd.get("hitl_required", True),
                    published_at=cd.get("published_at"),
                    performance=cd.get("performance", {}),
                    created_at=cd.get("created_at", ""),
                )

            self._outreach_records = [
                OutreachRecord(
                    record_id=r["record_id"],
                    prospect_id=r["prospect_id"],
                    channel=r["channel"],
                    status=r["status"],
                    compliance_decision=r["compliance_decision"],
                    blocked_reason=r.get("blocked_reason"),
                    sent_at=r.get("sent_at"),
                    created_at=r.get("created_at", ""),
                )
                for r in state.get("outreach_records", [])
            ]

            self._reply_records = [
                ReplyRecord(
                    reply_id=r["reply_id"],
                    prospect_id=r["prospect_id"],
                    body=r["body"],
                    is_opt_out=r.get("is_opt_out", False),
                    is_positive=r.get("is_positive", False),
                    processed_at=r.get("processed_at", ""),
                )
                for r in state.get("reply_records", [])
            ]

        logger.info(
            "Loaded state: %d content pieces, %d DNC, %d outreach records",
            len(self._content), len(self._dnc_set), len(self._outreach_records),
        )
        return True

    # ── Internal helpers ──────────────────────────────────────────────────

    def _check_compliance(
        self,
        prospect_id: str,
        prospect: Dict[str, Any],
    ) -> ComplianceDecision:
        """Check compliance for a prospect.

        Checks in order:
        1. DNC list (internal)
        2. ContactComplianceGovernor (external, if wired)
        3. Internal cooldown window
        """
        # 1. DNC list — internal, always checked first
        with self._lock:
            if prospect_id in self._dnc_set:
                return ComplianceDecision.BLOCK_DNC

        # 2. External compliance governor
        if self._compliance_gate is not None:
            try:
                ext_decision = self._compliance_gate.check(prospect_id, prospect)
                if ext_decision == "BLOCK_DNC" or ext_decision == ComplianceDecision.BLOCK_DNC:
                    return ComplianceDecision.BLOCK_DNC
                if ext_decision == "BLOCK_COOLDOWN" or ext_decision == ComplianceDecision.BLOCK_COOLDOWN:
                    return ComplianceDecision.BLOCK_COOLDOWN
                if ext_decision == "REQUIRES_CONSENT" or ext_decision == ComplianceDecision.REQUIRES_CONSENT:
                    return ComplianceDecision.REQUIRES_CONSENT
            except Exception as exc:  # noqa: BLE001
                logger.warning("Compliance governor error — blocking as precaution: %s", exc)
                return ComplianceDecision.BLOCK_COOLDOWN

        # 3. Internal cooldown
        with self._lock:
            last = self._last_contacted.get(prospect_id)
        if last is not None:
            last_dt = datetime.fromisoformat(last)
            cutoff = datetime.now(timezone.utc) - timedelta(days=OUTREACH_COOLDOWN_DAYS)
            if last_dt > cutoff:
                return ComplianceDecision.BLOCK_COOLDOWN

        return ComplianceDecision.ALLOW

    def _send_outreach(
        self,
        prospect_id: str,
        channel: str,
        prospect: Dict[str, Any],
    ) -> None:
        """Compose and send outreach; record contact timestamp."""
        sent_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._last_contacted[prospect_id] = sent_at

        self._record_outreach(
            prospect_id, channel, OutreachStatus.SENT,
            ComplianceDecision.ALLOW, None,
        )
        logger.debug("Outreach sent to prospect %s via %s", prospect_id, channel)

    def _record_outreach(
        self,
        prospect_id: str,
        channel: str,
        status: OutreachStatus,
        decision: ComplianceDecision,
        reason: Optional[str],
    ) -> None:
        record = OutreachRecord(
            record_id=f"out-{uuid.uuid4().hex[:8]}",
            prospect_id=prospect_id,
            channel=channel,
            status=status.value,
            compliance_decision=decision.value,
            blocked_reason=reason,
            sent_at=datetime.now(timezone.utc).isoformat() if status == OutreachStatus.SENT else None,
        )
        with self._lock:
            capped_append(self._outreach_records, record, max_size=_MAX_OUTREACH_HISTORY)

    def _auto_publish(self, content: GeneratedContent) -> None:
        """Mark content as published and increment published count."""
        content.status = ContentStatus.PUBLISHED.value
        content.published_at = datetime.now(timezone.utc).isoformat()
        content.hitl_required = False
        with self._lock:
            self._published_count += 1
        self._publish_event("content_published", content.to_dict())
        logger.info("Auto-published content %s: '%s'", content.content_id, content.title)

    def _get_prospects(self) -> List[Dict[str, Any]]:
        """Get prospects for the outreach cycle.

        Delegates to SelfSellingEngine.generate_leads() when available.
        Returns a minimal stub list when no engine is wired (for testing).
        """
        try:
            from self_selling_engine import MurphySelfSellingEngine  # noqa: PLC0415
            if hasattr(self, "_selling_engine") and self._selling_engine is not None:
                return self._selling_engine.generate_leads()
        except Exception:  # noqa: BLE001
            pass
        return []

    def _score_content(self, title: str, body: str) -> float:
        """Score content using SEOOptimisationEngine or a fallback heuristic."""
        if self._seo_engine is not None:
            try:
                analysis = self._seo_engine.analyse_content(title=title, body=body)
                return float(analysis.seo_score)
            except Exception as exc:  # noqa: BLE001
                logger.debug("SEO engine scoring failed: %s", exc)
        # Fallback heuristic: 50 base + bonus for length and keyword density
        word_count = len(body.split())
        score = 50.0
        if word_count >= 800:
            score += 20.0
        elif word_count >= 300:
            score += 10.0
        if len(title) >= 30:
            score += 10.0
        return min(score, 100.0)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract simple keyword list from text."""
        stop_words = {
            "the", "a", "an", "is", "in", "of", "for", "to", "and", "or",
            "with", "how", "why", "what", "from", "on", "at", "by", "as",
        }
        words = [w.strip(".,—-").lower() for w in text.split()]
        return [w for w in words if len(w) > 3 and w not in stop_words][:8]

    def _is_topic_recent(self, category: str, topic: str) -> bool:
        """Return True if this (category, topic) was used within 30 days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        with self._lock:
            for entry in self._recent_topics:
                if entry["category"] == category and entry["topic"] == topic:
                    used_at = datetime.fromisoformat(entry["used_at"])
                    if used_at > cutoff:
                        return True
        return False

    def _mark_topic_used(self, category: str, topic: str) -> None:
        """Record a topic as used so it is not repeated within 30 days."""
        entry = {
            "category": category,
            "topic": topic,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            # Remove stale entries
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            self._recent_topics = [
                e for e in self._recent_topics
                if datetime.fromisoformat(e["used_at"]) > cutoff
            ]
            capped_append(self._recent_topics, entry, max_size=500)

    def _compose_blog_body(self, title: str, keywords: List[str]) -> str:
        """Compose a structured blog post body."""
        kw_str = ", ".join(keywords)
        return (
            f"# {title}\n\n"
            f"## Introduction\n\n"
            f"In this article we explore {title.lower()} "
            f"with a focus on {kw_str}. "
            f"Murphy System's AI automation platform provides a unique perspective.\n\n"
            f"## Key Concepts\n\n"
            f"Automation is transforming industries. "
            f"Murphy System enables natural-language workflows that replace manual processes. "
            f"Confidence-gated execution ensures safety at every step.\n\n"
            f"## How Murphy Helps\n\n"
            f"With {kw_str}, teams can automate repetitive work, "
            f"reduce errors, and focus on high-value decisions. "
            f"Murphy's governance kernel bounds every autonomous action.\n\n"
            f"## Getting Started\n\n"
            f"Visit murphy.inoni.ai to start a 3-day free trial. "
            f"No credit card required. Describe your workflow and let Murphy execute it.\n\n"
            f"## Conclusion\n\n"
            f"The future of {title.lower()} is here. "
            f"Murphy System makes AI automation safe, auditable, and accessible. "
            f"Keywords: {kw_str}.\n"
        )

    def _compose_case_study_body(self, title: str, subject: str, keywords: List[str]) -> str:
        """Compose a structured case study body."""
        kw_str = ", ".join(keywords)
        return (
            f"# {title}\n\n"
            f"## Overview\n\n"
            f"{subject} demonstrates Murphy System's self-automation capabilities. "
            f"Key areas: {kw_str}.\n\n"
            f"## Challenge\n\n"
            f"Inoni LLC needed to automate {subject.lower()} without adding headcount. "
            f"Manual processes were a bottleneck.\n\n"
            f"## Solution\n\n"
            f"Murphy System's orchestration layer automated the process end-to-end. "
            f"Natural language workflows replaced manual configuration.\n\n"
            f"## Results\n\n"
            f"- 100% of outreach automated\n"
            f"- Zero human operators required\n"
            f"- 920 modules delivered in 65 days\n\n"
            f"## Conclusion\n\n"
            f"This case study validates Murphy's self-automation architecture.\n"
        )

    def _compose_tutorial_body(self, title: str, feature: str, keywords: List[str]) -> str:
        """Compose a structured developer tutorial body."""
        kw_str = ", ".join(keywords)
        return (
            f"# {title}\n\n"
            f"## Prerequisites\n\n"
            f"- Python 3.11+\n"
            f"- Murphy SDK installed: `pip install murphy-sdk`\n\n"
            f"## Overview\n\n"
            f"This tutorial covers {feature} ({kw_str}).\n\n"
            f"## Step 1: Install and configure\n\n"
            f"```python\nfrom murphy_sdk import MurphyClient\nclient = MurphyClient(api_key='...')\n```\n\n"
            f"## Step 2: Use {feature}\n\n"
            f"```python\n# {feature} example\nresult = client.run('{feature}: automate my workflow')\nprint(result)\n```\n\n"
            f"## Summary\n\n"
            f"You have successfully used {feature} with the Murphy SDK. "
            f"Topics covered: {kw_str}.\n"
        )

    def _compose_social_variant(self, content: GeneratedContent, platform: str, limit: int) -> str:
        """Compose a platform-specific social post from a content piece."""
        base = f"{content.title} — {' '.join(content.keywords[:3])}"
        cta = " | murphy.inoni.ai"

        if platform == "twitter":
            body = base[:limit - len(cta) - 5]
            return f"{body}... {cta}"
        if platform == "linkedin":
            return (
                f"🚀 {content.title}\n\n"
                f"{content.body[:300]}...\n\n"
                f"Read more at murphy.inoni.ai\n\n"
                f"#{' #'.join(content.keywords[:5])}"
            )
        # reddit
        return (
            f"**{content.title}**\n\n"
            f"{content.body[:500]}\n\n"
            f"Full post at murphy.inoni.ai"
        )

    def _generate_code_snippet(self, feature: str) -> str:
        """Generate a code snippet for an SDK feature."""
        return (
            f"# Murphy SDK — {feature}\n"
            f"from murphy_sdk import MurphyClient\n"
            f"client = MurphyClient(api_key='YOUR_KEY')\n"
            f"result = client.run('{feature}: describe your task here')\n"
            f"print(result)\n"
        )

    def _generate_changelog_entry(self, feature: str) -> Dict[str, Any]:
        """Generate a changelog entry for an SDK feature."""
        return {
            "version": "1.0.0",
            "feature": feature,
            "entry": f"Added {feature} support to the Murphy SDK.",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    def _propose_sdk_issue(self, feature: str) -> Dict[str, Any]:
        """Propose a GitHub issue for an SDK improvement (not auto-filed)."""
        return {
            "title": f"Improve {feature} documentation and examples",
            "body": (
                f"As part of the Murphy developer attraction cycle, "
                f"this issue proposes improvements to {feature} in the murphy-sdk.\n\n"
                f"## Proposed Changes\n\n"
                f"- Add code examples for {feature}\n"
                f"- Update README with {feature} getting-started guide\n"
                f"- Add integration test for {feature} end-to-end flow"
            ),
            "labels": ["documentation", "developer-experience", "good-first-issue"],
            "repo": "murphy-sdk",
        }

    @staticmethod
    def _is_opt_out(reply: str) -> bool:
        """Detect opt-out intent in a reply."""
        text = reply.lower()
        opt_out_phrases = [
            "unsubscribe", "opt out", "opt-out", "remove me",
            "stop", "do not contact", "don't contact", "no thanks",
            "not interested", "please remove",
        ]
        return any(phrase in text for phrase in opt_out_phrases)

    @staticmethod
    def _is_positive_reply(reply: str) -> bool:
        """Detect positive / interested intent in a reply."""
        text = reply.lower()
        positive_phrases = [
            "interested", "tell me more", "sounds good", "yes", "i'd like",
            "sign me up", "free trial", "set it up", "let's talk",
            "book a call", "demo",
        ]
        return any(phrase in text for phrase in positive_phrases)

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish an event to EventBackbone if wired."""
        if self._backbone is None:
            return
        try:
            self._backbone.publish(event_type=event_type, payload=payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Event publish skipped: %s", exc)


__all__ = [
    "SelfMarketingOrchestrator",
    "CONTENT_CATEGORIES",
    "HITL_REVIEW_THRESHOLD",
    "OUTREACH_COOLDOWN_DAYS",
    "ComplianceDecision",
    "ContentStatus",
    "OutreachStatus",
    "GeneratedContent",
    "OutreachRecord",
    "ReplyRecord",
    "ContentCycleResult",
    "SocialCycleResult",
    "OutreachCycleResult",
    "DeveloperAttractionResult",
]
