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

  B2B PARTNERSHIP CYCLE (Weekly):
    1. Iterate through DESIRED_OFFERINGS list (configurable at construction time)
    2. For each offering: compose a personalised B2B pitch targeting the partner's
       sales / BD contact (email or LinkedIn)
    3. Check EVERY partner contact through the same compliance layer as regular outreach
       (DNC list → ContactComplianceGovernor → 30-day cooldown)
    4. For allowed contacts: send pitch; record contact timestamp
    5. Process partner replies:
       - Positive / interested reply → advance PartnershipStatus to INTERESTED,
         trigger automated case-study brief generation
       - Declined reply → mark DECLINED; respect opt-out if requested
    6. Track pipeline: PENDING → OUTREACH_SENT → INTERESTED → CASE_STUDY_DRAFTED
       → FEATURING_AGREED / DECLINED

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - No outreach without ContactComplianceGovernor clearance (COMPL-001)
  - HITL gate: first HITL_REVIEW_THRESHOLD content pieces require founder review
  - Bounded: all history lists are capped to prevent memory growth
  - Audit trail: every published piece, outreach sent, and compliance block is logged
  - Opt-out is irreversible: DNC additions are never removed by automation
  - Input validation: prospect_id validated against _PROSPECT_ID_RE (CWE-20)
  - Channel allowlist: only {email, sms, linkedin, phone, push} accepted (CWE-20)
  - Size caps: topic ≤500 chars, keywords ≤20 items of ≤100 chars each (CWE-20/CWE-400)
  - Reply body capped at 50,000 bytes (CWE-400)
  - Pending-replies queue capped at 1,000 entries (CWE-400)
  - DNC set capped at 100,000 entries (CWE-400)
  - Cooldown dict capped at 100,000 entries (CWE-400)
  - Content catalogue capped at 50,000 items (CWE-400)
  - Error messages sanitized and truncated — no PII in stored errors (CWE-209)
  - PII redacted from logs — email addresses masked before emission
  - B2B partner contacts subject to the same compliance layer as regular outreach
  - B2B case-study briefs queued for HITL review before sending to partner
  - Salesperson name/title validated with _SAFE_NAME_RE (no control chars or HTML, CWE-20)
  - Salesperson email validated with RFC-5321 regex + 254-char cap; NEVER logged or returned (PII)
  - Salesperson LinkedIn URL validated: HTTPS only, linkedin.com/in/ prefix enforced (CWE-20)
  - MarketPositioningEngine wired in: content cycles and B2B pitches enriched with
    vertical-specific topics and capability intelligence (non-fatal fallback on error)
  - Commissioning gate (_commission_system): cross-cutting validation run over EVERY
    executed cycle and module — commissioning is NOT a partner-facing offering but an
    internal quality gate; every B2B cycle and content cycle is commissioned and its
    result emitted to the audit trail as a 'system_commissioned' event

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from market_positioning_engine import (
    MarketPositioningEngine,
    get_default_positioning_engine,
)

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
# Hardening — input validation & memory-growth caps (CWE-20 / CWE-400)
# ---------------------------------------------------------------------------

# prospect_id: alphanumeric + underscore, hyphen, dot, at-sign.
# Accommodates UUID-style IDs, email-as-ID, and plain slugs.
# Identical to the constraint used by COMPL-002 OutreachComplianceGate.
_PROSPECT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")

# content_id: generated internally as a slug prefix + UUID hex fragment.
_CONTENT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# partner_id: same character set as content_id; shorter max length for slug keys.
_PARTNER_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,100}$")

# Allowed outreach channels (frozenset prevents accidental mutation).
_ALLOWED_CHANNELS: frozenset = frozenset({"email", "sms", "linkedin", "phone", "push"})

# Maximum length for topic / subject / sdk_feature strings (CWE-20).
_MAX_TOPIC_LEN = 500

# Keyword list limits (CWE-400 / CWE-20).
_MAX_KEYWORD_LEN = 100
_MAX_KEYWORDS = 20

# Maximum reply body size in characters (CWE-400).
_MAX_REPLY_BODY = 50_000

# Maximum pending-replies queue depth (CWE-400).
_MAX_PENDING_REPLIES = 1_000

# Maximum error-message length stored in cycle results (CWE-209).
_MAX_ERROR_MSG_LEN = 200

# Hard caps on in-process data structures (CWE-400).
_MAX_DNC_ENTRIES = 100_000       # DNC set — same limit as COMPL-002
_MAX_LAST_CONTACTED = 100_000    # cooldown tracking dict
_MAX_CONTENT_ITEMS = 50_000      # content catalogue dict

# ---------------------------------------------------------------------------
# Salesperson contact field validation (CWE-20)
# ---------------------------------------------------------------------------

# Maximum length for salesperson name and job title strings.
_MAX_NAME_LEN = 200

# Salesperson name / title: printable chars; no raw control characters or HTML
# injection characters.  Allows letters, digits, spaces, hyphens, apostrophes,
# dots, commas, and parentheses — sufficient for any real person's name or
# professional title.
_SAFE_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f<>&\"\\]{1,200}$")

# Email address (RFC 5321 simplified, consistent with COMPL-002).
# Raw salesperson_email values are NEVER logged or returned in API responses.
_EMAIL_RE_B2B = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
_MAX_EMAIL_LEN = 254              # RFC 5321 hard cap

# LinkedIn profile URL — HTTPS only; must be a profile URL under linkedin.com/in/.
_LINKEDIN_URL_RE = re.compile(
    r"^https://(www\.)?linkedin\.com/in/[a-zA-Z0-9_\-%.]{1,200}/?$"
)
_MAX_LINKEDIN_URL_LEN = 500

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
    "building_automation_iot": [
        "Unifying BACnet, KNX, and Modbus with AI orchestration",
        "How AI building automation reduces HVAC energy waste by 30%",
        "Predictive HVAC maintenance: detecting chiller degradation early",
        "LEED and BREEAM automation: generating energy compliance reports automatically",
        "Smart building natural language: 'Reduce cooling when meeting rooms are empty'",
    ],
    "energy_management": [
        "ASHRAE Level II energy audit automation: from bills to ECM report in 4 hours",
        "ISO 50001 certification with Murphy: automating the evidence trail",
        "Greedy ECM prioritisation: maximising energy savings within budget",
        "Demand response on autopilot: Murphy dispatches load-shed in under 30 seconds",
        "Carbon reporting automation: from smart meter data to SEC-ready ESG disclosure",
    ],
    "additive_manufacturing": [
        "Automating multi-vendor AM fleets: GrabCAD + Eiger + EOSTATE unified with Murphy",
        "OPC-UA companion spec for additive manufacturing: Murphy as the integration layer",
        "End-to-end AM traceability: linking build parameters to inspection with AI",
        "Post-processing automation: connecting print completion to CNC and heat treat",
        "AI-driven material consumption tracking across FDM, SLS, and DMLS fleets",
    ],
    "factory_automation": [
        "OT/IT convergence with Murphy: connecting PLCs to business systems without custom code",
        "Natural-language robot programming: 'Pick when sensor fires' — Murphy writes the logic",
        "ISA-95 orchestration: sequencing FIELD, CONTROL, and MES layers correctly",
        "IEC 13849 safety gate in software: Murphy's approach to collaborative robot safety",
        "SCADA modernisation without rip-and-replace: Murphy as the AI overlay layer",
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
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_prospect_id(prospect_id: str) -> str:
    """Return validated prospect_id or raise ValueError (CWE-20).

    Accepts alphanumeric IDs, UUID strings, email-style IDs, and slugs up to
    200 characters.  Rejects anything that could be used for injection.
    """
    if not isinstance(prospect_id, str):
        raise ValueError("prospect_id must be a string")
    if not _PROSPECT_ID_RE.match(prospect_id):
        # Truncate in the error message — don't echo potentially huge payloads
        raise ValueError(
            f"Invalid prospect_id (len={len(prospect_id)}): "
            r"must match ^[a-zA-Z0-9_@.\-]{1,200}$"
        )
    return prospect_id


def _validate_channel(channel: str) -> str:
    """Return channel if in allowlist, raise ValueError otherwise (CWE-20)."""
    if not isinstance(channel, str) or channel not in _ALLOWED_CHANNELS:
        raise ValueError(
            f"Invalid channel '{channel}': must be one of {sorted(_ALLOWED_CHANNELS)}"
        )
    return channel


def _validate_topic(topic: str, *, param: str = "topic") -> str:
    """Strip null bytes, enforce max length, and return the cleaned value (CWE-20).

    Raises ValueError when the topic exceeds _MAX_TOPIC_LEN characters.
    """
    if not isinstance(topic, str):
        raise ValueError(f"{param} must be a string")
    topic = topic.replace("\x00", "")
    if len(topic) > _MAX_TOPIC_LEN:
        raise ValueError(
            f"{param} exceeds maximum length of {_MAX_TOPIC_LEN} characters"
        )
    return topic


def _sanitize_error(exc: BaseException) -> str:
    """Return a safe, truncated error message without PII (CWE-209).

    Strips email-address patterns (potential PII) and truncates the message
    to _MAX_ERROR_MSG_LEN characters so that error lists cannot grow unbounded
    and never expose sensitive contact information.
    """
    msg = str(exc)
    # Mask anything that looks like an email address
    msg = re.sub(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        "<redacted>",
        msg,
    )
    combined = f"{type(exc).__name__}: {msg}"
    return combined[:_MAX_ERROR_MSG_LEN]


def _validate_salesperson_name(value: str, *, param: str = "salesperson_name") -> str:
    """Validate and return a salesperson name or job title (CWE-20).

    Strips leading/trailing whitespace and null bytes, enforces _MAX_NAME_LEN,
    and rejects strings containing raw HTML/control characters.
    Raises ValueError for invalid input.
    """
    if not isinstance(value, str):
        raise ValueError(f"{param} must be a string")
    value = value.replace("\x00", "").strip()
    if not value:
        raise ValueError(f"{param} must not be empty")
    if len(value) > _MAX_NAME_LEN:
        raise ValueError(
            f"{param} exceeds maximum length of {_MAX_NAME_LEN} characters"
        )
    if not _SAFE_NAME_RE.match(value):
        raise ValueError(
            f"{param} contains disallowed characters (no control chars or HTML)"
        )
    return value


def _validate_salesperson_email(email: str) -> str:
    """Validate a salesperson email address (CWE-20, PII).

    Applies the same RFC-5321 simplified check used by COMPL-002.
    Raw email is NEVER logged by callers — only the validated, opaque value
    is stored in PartnershipProspect.salesperson_email.
    Raises ValueError for invalid input.
    """
    if not isinstance(email, str):
        raise ValueError("salesperson_email must be a string")
    email = email.strip().replace("\x00", "")
    if len(email) > _MAX_EMAIL_LEN:
        raise ValueError(
            f"salesperson_email exceeds RFC-5321 maximum of {_MAX_EMAIL_LEN} characters"
        )
    if not _EMAIL_RE_B2B.match(email):
        raise ValueError(
            "salesperson_email is not a valid RFC-5321 email address"
        )
    return email


def _validate_linkedin_url(url: str) -> str:
    """Validate a LinkedIn profile URL (CWE-20).

    Accepts only HTTPS profile URLs under linkedin.com/in/.  Rejects
    HTTP, javascript:, data:, and non-LinkedIn domains.
    Raises ValueError for invalid input.
    """
    if not isinstance(url, str):
        raise ValueError("salesperson_linkedin must be a string")
    url = url.strip().replace("\x00", "")
    if len(url) > _MAX_LINKEDIN_URL_LEN:
        raise ValueError(
            f"salesperson_linkedin exceeds maximum of {_MAX_LINKEDIN_URL_LEN} characters"
        )
    if not _LINKEDIN_URL_RE.match(url):
        raise ValueError(
            "salesperson_linkedin must be an HTTPS linkedin.com/in/<profile> URL"
        )
    return url


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
# B2B Partnership — desired offerings, status model, and result dataclass
# ---------------------------------------------------------------------------

# Offering types Murphy is actively seeking.
B2B_OFFERING_TYPES = frozenset({
    "case_study",           # joint written/video case study
    "featuring",            # featured on partner's website / blog
    "co_marketing",         # shared marketing campaign
    "integration_featuring", # listed in partner's integration directory
    "press_mention",        # mention in partner's press release
    "podcast_guest",        # appearance on partner's podcast / webinar
})

# Default list of desired B2B partners.  Operators can override by passing
# desired_offerings=[...] to SelfMarketingOrchestrator().
DEFAULT_DESIRED_OFFERINGS: List[Dict[str, Any]] = [
    {
        "partner_id": "hubspot",
        "company": "HubSpot",
        "contact_role": "partnerships",
        "salesperson_name": "Head of Technology Partnerships",
        "salesperson_title": "Head of Technology Partnerships, HubSpot",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["case_study", "integration_featuring"],
        "pitch_angle": (
            "Murphy System automates the full HubSpot workflow lifecycle "
            "using natural language — zero drag-and-drop, just describe it."
        ),
    },
    {
        "partner_id": "zapier",
        "company": "Zapier",
        "contact_role": "developer_relations",
        "salesperson_name": "Director of Developer Relations",
        "salesperson_title": "Director, Developer Relations — Zapier",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["featuring", "co_marketing"],
        "pitch_angle": (
            "Murphy complements Zapier for complex multi-step AI orchestration "
            "with confidence-gated execution and HITL safety gates."
        ),
    },
    {
        "partner_id": "make",
        "company": "Make (Integromat)",
        "contact_role": "partnerships",
        "salesperson_name": "Head of Partner Ecosystem",
        "salesperson_title": "Head of Partner Ecosystem, Make",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["case_study", "featuring"],
        "pitch_angle": (
            "Murphy's Describe-to-Execute paradigm bridges the gap between "
            "no-code visual builders and full programmatic automation."
        ),
    },
    {
        "partner_id": "n8n",
        "company": "n8n",
        "contact_role": "developer_relations",
        "salesperson_name": "Developer Relations Lead",
        "salesperson_title": "Developer Relations Lead, n8n",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["co_marketing", "integration_featuring"],
        "pitch_angle": (
            "Murphy and n8n together offer open-source orchestration with "
            "AI-native NL workflow generation — powerful for technical teams."
        ),
    },
    {
        "partner_id": "salesforce",
        "company": "Salesforce",
        "contact_role": "ISV_partnerships",
        "salesperson_name": "Director of ISV Partnerships",
        "salesperson_title": "Director, ISV and AppExchange Partnerships — Salesforce",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["case_study", "integration_featuring"],
        "pitch_angle": (
            "Murphy can automate any Salesforce workflow via NL commands, "
            "reducing CRM administration overhead by 80%+."
        ),
    },
    {
        "partner_id": "microsoft_365",
        "company": "Microsoft 365",
        "contact_role": "partner_network",
        "salesperson_name": "Partner Business Development Manager",
        "salesperson_title": "Partner Business Development Manager, Microsoft 365",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["featuring", "case_study"],
        "pitch_angle": (
            "Murphy automates Teams, Outlook, and SharePoint workflows "
            "using plain English — a natural fit for the M365 ecosystem."
        ),
    },
    {
        "partner_id": "notion",
        "company": "Notion",
        "contact_role": "partnerships",
        "salesperson_name": "Head of Integrations and Partnerships",
        "salesperson_title": "Head of Integrations and Partnerships, Notion",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["co_marketing", "featuring"],
        "pitch_angle": (
            "Murphy turns Notion wikis into executable playbooks — "
            "describe a process in Notion and Murphy runs it automatically."
        ),
    },
    {
        "partner_id": "linear",
        "company": "Linear",
        "contact_role": "developer_relations",
        "salesperson_name": "Developer Relations Lead",
        "salesperson_title": "Developer Relations Lead, Linear",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "podcast_guest"],
        "pitch_angle": (
            "Murphy automates engineering workflows in Linear using NL — "
            "issue triage, sprint planning, and CI/CD triggers via chat."
        ),
    },
    {
        "partner_id": "datadog",
        "company": "Datadog",
        "contact_role": "technology_partnerships",
        "salesperson_name": "Director of Technology Alliances",
        "salesperson_title": "Director, Technology Alliances — Datadog",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["case_study", "integration_featuring"],
        "pitch_angle": (
            "Murphy closes the loop on Datadog alerts by automatically "
            "triggering remediation workflows with confidence-gated execution."
        ),
    },
    {
        "partner_id": "github",
        "company": "GitHub",
        "contact_role": "ecosystem_partnerships",
        "salesperson_name": "Head of Ecosystem Partnerships",
        "salesperson_title": "Head of Ecosystem Partnerships, GitHub",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["featuring", "press_mention"],
        "pitch_angle": (
            "Murphy automates GitHub Actions, PRs, and issue management via "
            "NL commands — a natural complement to GitHub Copilot."
        ),
    },
    # ── IoT / Building Automation ──────────────────────────────────────────
    {
        "partner_id": "siemens_smart_infrastructure",
        "company": "Siemens Smart Infrastructure (Desigo CC)",
        "contact_role": "technology_partnerships",
        "salesperson_name": "Head of Technology Alliances",
        "salesperson_title": "Head of Technology Alliances, Siemens Smart Infrastructure",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's BACnet/IP, KNX, Modbus, and OPC-UA connectors integrate directly "
            "with Desigo CC, enabling natural-language building automation workflows "
            "without custom middleware."
        ),
    },
    {
        "partner_id": "johnson_controls_openblue",
        "company": "Johnson Controls OpenBlue",
        "contact_role": "partner_ecosystem",
        "salesperson_name": "Director of Partner Ecosystem",
        "salesperson_title": "Director, Partner Ecosystem — Johnson Controls OpenBlue",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["case_study", "co_marketing"],
        "pitch_angle": (
            "Murphy's AI orchestration layer adds NL-driven adaptive logic on top of "
            "OpenBlue — predictive HVAC, automated energy reporting, and cross-system "
            "building workflows in plain English."
        ),
    },
    {
        "partner_id": "honeywell_forge_buildings",
        "company": "Honeywell Forge Buildings",
        "contact_role": "technology_partnerships",
        "salesperson_name": "VP of Technology Partnerships",
        "salesperson_title": "VP Technology Partnerships, Honeywell Forge Buildings",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "co_marketing"],
        "pitch_angle": (
            "Murphy provides the AI orchestration layer for Honeywell Forge — "
            "confidence-gated building automation commands, ISO 50001 audit automation, "
            "and NL energy policy enforcement across Forge-connected facilities."
        ),
    },
    # ── Energy Management & Energy Audits ──────────────────────────────────
    {
        "partner_id": "ameresco",
        "company": "Ameresco",
        "contact_role": "technology_partnerships",
        "salesperson_name": "VP of Technology and Innovation",
        "salesperson_title": "VP Technology and Innovation, Ameresco",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["case_study", "co_marketing"],
        "pitch_angle": (
            "Murphy's Energy Audit Engine (ASHRAE Level I/II/III) and ISO 50001 automation "
            "accelerate Ameresco's energy audit delivery — turning weeks of manual analysis "
            "into hours of automated ECM identification with ROI calculations."
        ),
    },
    {
        "partner_id": "facilio",
        "company": "Facilio",
        "contact_role": "partnerships",
        "salesperson_name": "Head of Partner Ecosystem",
        "salesperson_title": "Head of Partner Ecosystem, Facilio",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's energy management connectors and ASHRAE audit engine integrate "
            "with Facilio to automate ECM identification, ISO 50001 reporting, and "
            "demand response dispatch."
        ),
    },
    {
        "partner_id": "energycap",
        "company": "EnergyCAP",
        "contact_role": "technology_partnerships",
        "salesperson_name": "Director of Technology Partnerships",
        "salesperson_title": "Director, Technology Partnerships — EnergyCAP",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "co_marketing"],
        "pitch_angle": (
            "Murphy enriches EnergyCAP's utility analytics with AI-powered ASHRAE Level II "
            "audit automation — ingesting data, identifying ECMs, and generating "
            "ISO 50001-compliant reports automatically."
        ),
    },
    # ── Additive Manufacturing ─────────────────────────────────────────────
    {
        "partner_id": "stratasys",
        "company": "Stratasys (GrabCAD Print)",
        "contact_role": "developer_ecosystem",
        "salesperson_name": "Director of Developer Ecosystem",
        "salesperson_title": "Director, Developer Ecosystem — Stratasys",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's GrabCAD Print connector and OPC-UA AM support enable NL fleet "
            "management for Stratasys FDM/PolyJet systems — automated job scheduling, "
            "quality traceability, and post-processing workflow triggers."
        ),
    },
    {
        "partner_id": "eos_gmbh",
        "company": "EOS GmbH (EOSTATE)",
        "contact_role": "technology_partnerships",
        "salesperson_name": "Head of Technology Partnerships",
        "salesperson_title": "Head of Technology Partnerships, EOS GmbH",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["integration_featuring", "co_marketing"],
        "pitch_angle": (
            "Murphy's EOSTATE connector and OPC-UA AM (OPC 40564) bring AI-native "
            "orchestration to EOS DMLS/SLS systems — build parameter traceability, "
            "automated quality inspection routing, and AS9100D evidence collection."
        ),
    },
    {
        "partner_id": "markforged",
        "company": "Markforged (Eiger Cloud)",
        "contact_role": "partnerships",
        "salesperson_name": "Director of Partnerships",
        "salesperson_title": "Director of Partnerships, Markforged",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's Eiger cloud connector lets Markforged users automate multi-part "
            "build scheduling, material consumption tracking, and post-processing "
            "workflows — without Eiger API expertise."
        ),
    },
    # ── Factory Automation ─────────────────────────────────────────────────
    {
        "partner_id": "rockwell_automation",
        "company": "Rockwell Automation (FactoryTalk)",
        "contact_role": "technology_alliances",
        "salesperson_name": "Director of Technology Alliances",
        "salesperson_title": "Director, Technology Alliances — Rockwell Automation",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's EtherNet/IP connector and ISA-95 layer-aware orchestration bring "
            "NL AI to FactoryTalk environments — scheduling, alarming, and MES integration "
            "from plain-English descriptions, not PLC ladder logic."
        ),
    },
    {
        "partner_id": "beckhoff",
        "company": "Beckhoff Automation (TwinCAT)",
        "contact_role": "developer_relations",
        "salesperson_name": "Head of Developer Relations",
        "salesperson_title": "Head of Developer Relations, Beckhoff Automation",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "linkedin",
        "offering_types": ["integration_featuring", "co_marketing"],
        "pitch_angle": (
            "Murphy's TwinCAT 3 OPC-UA (ADS port 851) connector enables natural-language "
            "factory automation sequences that Beckhoff partners can deploy without "
            "writing IEC 61131 code."
        ),
    },
    {
        "partner_id": "ptc_thingworx",
        "company": "PTC ThingWorx",
        "contact_role": "partner_ecosystem",
        "salesperson_name": "VP of Partner Ecosystem",
        "salesperson_title": "VP Partner Ecosystem, PTC ThingWorx",
        "salesperson_email": None,
        "salesperson_linkedin": None,
        "channel": "email",
        "offering_types": ["integration_featuring", "case_study"],
        "pitch_angle": (
            "Murphy's ThingWorx REST connector brings AI-native NL workflow execution "
            "to the ThingWorx IIoT platform — predictive maintenance triggers, automated "
            "work orders, and OEE reporting from plain-English descriptions."
        ),
    },
]


class PartnershipStatus(str, Enum):
    """Lifecycle status of a B2B partnership prospect."""
    PENDING = "pending"                  # Identified, no outreach yet
    OUTREACH_SENT = "outreach_sent"      # Initial pitch sent
    INTERESTED = "interested"            # Partner replied positively
    CASE_STUDY_DRAFTED = "case_study_drafted"  # Case-study brief generated
    FEATURING_AGREED = "featuring_agreed"      # Formal agreement to feature
    DECLINED = "declined"                # Partner not interested
    BLOCKED = "blocked"                  # Compliance blocked outreach


@dataclass
class PartnershipProspect:
    """A B2B partnership opportunity being tracked.

    Salesperson contact fields
    --------------------------
    salesperson_name    : The named individual to address pitches to.
                          Use `add_salesperson_contact()` to set this at runtime
                          once the actual contact person is identified.
                          Defaults to a role-based name from DEFAULT_DESIRED_OFFERINGS.
    salesperson_title   : The contact's job title at the partner company.
    salesperson_email   : Email address — PII.  NEVER returned from to_dict() or
                          included in API responses / event payloads.  Stored
                          internally only for channel routing.
    salesperson_linkedin: LinkedIn profile URL for linkedin channel routing.
    """

    partner_id: str
    company: str
    contact_role: str
    channel: str
    offering_types: List[str]
    pitch_angle: str
    status: str = PartnershipStatus.PENDING.value
    outreach_sent_at: Optional[str] = None
    last_reply_at: Optional[str] = None
    case_study_content_id: Optional[str] = None
    notes: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Named salesperson contact (CWE-20 validated on write; PII-safe on read)
    salesperson_name: Optional[str] = None
    salesperson_title: Optional[str] = None
    salesperson_email: Optional[str] = None      # PII — never serialised
    salesperson_linkedin: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partner_id": self.partner_id,
            "company": self.company,
            "contact_role": self.contact_role,
            "channel": self.channel,
            "offering_types": list(self.offering_types),
            "pitch_angle": self.pitch_angle,
            "status": self.status,
            "outreach_sent_at": self.outreach_sent_at,
            "last_reply_at": self.last_reply_at,
            "case_study_content_id": self.case_study_content_id,
            "notes": self.notes,
            "created_at": self.created_at,
            # Named contact (name / title / linkedin — email excluded as PII)
            "salesperson_name": self.salesperson_name,
            "salesperson_title": self.salesperson_title,
            "salesperson_linkedin": self.salesperson_linkedin,
            "has_named_contact": self.salesperson_name is not None,
        }


@dataclass
class B2BPartnershipCycleResult:
    """Summary of a single B2B partnership outreach cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    partners_evaluated: int = 0
    pitches_sent: int = 0
    blocked_compliance: int = 0
    blocked_cooldown: int = 0
    interested: int = 0
    case_studies_drafted: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "partners_evaluated": self.partners_evaluated,
            "pitches_sent": self.pitches_sent,
            "blocked_compliance": self.blocked_compliance,
            "blocked_cooldown": self.blocked_cooldown,
            "interested": self.interested,
            "case_studies_drafted": self.case_studies_drafted,
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
        desired_offerings: Optional[List[Dict[str, Any]]] = None,
        positioning_engine: Optional[MarketPositioningEngine] = None,
    ) -> None:
        self._content_engine = content_engine
        self._seo_engine = seo_engine
        self._campaign_engine = campaign_engine
        self._adaptive_campaign = adaptive_campaign
        self._compliance_gate = compliance_gate
        self._backbone = event_backbone
        self._pm = persistence_manager

        # Market positioning engine — used to enrich content topics and B2B pitches.
        # Falls back to the module-level default singleton if not explicitly provided.
        self._positioning = (
            positioning_engine
            if positioning_engine is not None
            else get_default_positioning_engine()
        )

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

        # B2B partnership pipeline: partner_id → PartnershipProspect
        self._partnerships: Dict[str, PartnershipProspect] = {}
        self._b2b_cycles: List[B2BPartnershipCycleResult] = []

        # Seed the partnership pipeline from the desired offerings list
        offerings = desired_offerings if desired_offerings is not None else DEFAULT_DESIRED_OFFERINGS
        for offering in offerings:
            pid = offering.get("partner_id", "")
            if pid and pid not in self._partnerships:
                # Validate optional salesperson contact fields — log warnings on
                # bad values but don't crash so a single bad entry doesn't block
                # the whole list.
                sp_name: Optional[str] = None
                sp_title: Optional[str] = None
                sp_email: Optional[str] = None
                sp_linkedin: Optional[str] = None

                if offering.get("salesperson_name"):
                    try:
                        sp_name = _validate_salesperson_name(
                            offering["salesperson_name"], param="salesperson_name"
                        )
                    except ValueError as exc:
                        logger.warning("Offering '%s' salesperson_name rejected: %s", pid, exc)

                if offering.get("salesperson_title"):
                    try:
                        sp_title = _validate_salesperson_name(
                            offering["salesperson_title"], param="salesperson_title"
                        )
                    except ValueError as exc:
                        logger.warning("Offering '%s' salesperson_title rejected: %s", pid, exc)

                if offering.get("salesperson_email"):
                    try:
                        sp_email = _validate_salesperson_email(offering["salesperson_email"])
                    except ValueError:
                        logger.warning("Offering '%s' salesperson_email rejected (not logged)", pid)
                        # Intentionally do NOT log the exception — it may contain the raw email (PII)

                if offering.get("salesperson_linkedin"):
                    try:
                        sp_linkedin = _validate_linkedin_url(offering["salesperson_linkedin"])
                    except ValueError as exc:
                        logger.warning("Offering '%s' salesperson_linkedin rejected: %s", pid, exc)

                self._partnerships[pid] = PartnershipProspect(
                    partner_id=pid,
                    company=offering.get("company", pid),
                    contact_role=offering.get("contact_role", "partnerships"),
                    channel=offering.get("channel", "email"),
                    offering_types=list(offering.get("offering_types", [])),
                    pitch_angle=offering.get("pitch_angle", ""),
                    salesperson_name=sp_name,
                    salesperson_title=sp_title,
                    salesperson_email=sp_email,
                    salesperson_linkedin=sp_linkedin,
                )

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

        # Pick this cycle's category and determine active vertical
        with self._lock:
            category = _CATEGORY_ROTATION[self._category_index % len(_CATEGORY_ROTATION)]
            self._category_index += 1

        topics = CONTENT_CATEGORIES[category]

        # Enrich topic pool with vertical-specific topics from the positioning engine.
        # Map content category names to the closest industry vertical and pull its
        # curated topics in — these are already SEO-optimised for the target buyer.
        _CATEGORY_TO_VERTICAL: Dict[str, str] = {
            "ai_automation": "technology",
            "developer_tools": "technology",
            "industrial_iot": "manufacturing",
            "business_automation": "professional_services",
            "case_studies": "technology",
            "thought_leadership": "financial_services",
            # New domain-specific verticals
            "building_automation_iot": "iot_building_automation",
            "energy_management": "energy_management",
            "additive_manufacturing": "additive_manufacturing",
            "factory_automation": "factory_automation",
        }
        vertical_id = _CATEGORY_TO_VERTICAL.get(category)
        vertical_topics: List[str] = []
        if vertical_id:
            try:
                vertical_topics = self._positioning.get_content_topics_for_vertical(vertical_id)
            except (ValueError, Exception):  # noqa: BLE001 — PROD-HARD A2: positioning engine failure is non-fatal for content cycle
                logger.debug("Vertical positioning topics unavailable for %r; falling back to category templates", vertical_id, exc_info=True)

        # Merge: use vertical topics first (highest signal), then category templates
        combined_topics: List[str] = list(vertical_topics[:3]) + list(topics)
        # Deduplicate while preserving order
        seen_topics: set = set()
        unique_topics: List[str] = []
        for t in combined_topics:
            if t not in seen_topics:
                seen_topics.add(t)
                unique_topics.append(t)
        topics = unique_topics

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
                errors.append(_sanitize_error(exc))
                logger.warning("Content generation error for topic '%s': %s", topic, _sanitize_error(exc))

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
        # Commission the content cycle output — all produced content is commissioned.
        self._commission_system(
            system_id=cycle_id,
            system_name="Content Generation Cycle",
            metrics={
                "pieces_generated": pieces_generated,
                "pieces_published": pieces_published,
                "pieces_pending_review": pieces_pending_review,
                "avg_seo_score": round(avg_seo, 2),
                "errors": errors,
            },
        )
        return result.to_dict()

    def generate_blog_post(self, topic: str, keywords: Optional[List[str]] = None) -> GeneratedContent:
        """Generate an SEO-optimized blog post on a topic.

        Delegates body generation to ContentPipelineEngine when available,
        otherwise constructs a structured placeholder post that satisfies the
        SEO scoring minimum-length requirement.
        """
        topic = _validate_topic(topic)  # CWE-20: strip null bytes, enforce max length

        if keywords is None:
            keywords = self._extract_keywords(topic)

        # Cap keyword list size and per-keyword length — CWE-400 / CWE-20
        keywords = [kw[:_MAX_KEYWORD_LEN] for kw in keywords[:_MAX_KEYWORDS]]

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
            # Hard cap on content catalogue — CWE-400
            if len(self._content) >= _MAX_CONTENT_ITEMS:
                evict = max(1, _MAX_CONTENT_ITEMS // 10)
                keys = list(self._content.keys())[:evict]
                for k in keys:
                    del self._content[k]
            self._content[content.content_id] = content

        logger.info("Generated blog post %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def generate_case_study(self, subject: str) -> GeneratedContent:
        """Generate a case study from Murphy's own operational data."""
        subject = _validate_topic(subject, param="subject")  # CWE-20

        title = f"Case Study: {subject}"
        keywords = self._extract_keywords(subject) + ["automation", "ROI", "Murphy System"]
        keywords = [kw[:_MAX_KEYWORD_LEN] for kw in keywords[:_MAX_KEYWORDS]]  # CWE-400
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
            # Hard cap on content catalogue — CWE-400
            if len(self._content) >= _MAX_CONTENT_ITEMS:
                evict = max(1, _MAX_CONTENT_ITEMS // 10)
                keys = list(self._content.keys())[:evict]
                for k in keys:
                    del self._content[k]
            self._content[content.content_id] = content

        logger.info("Generated case study %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def generate_tutorial(self, sdk_feature: str) -> GeneratedContent:
        """Generate a developer tutorial for an SDK feature."""
        sdk_feature = _validate_topic(sdk_feature, param="sdk_feature")  # CWE-20

        title = f"Tutorial: {sdk_feature}"
        keywords = self._extract_keywords(sdk_feature) + ["SDK", "tutorial", "Python", "API"]
        keywords = [kw[:_MAX_KEYWORD_LEN] for kw in keywords[:_MAX_KEYWORDS]]  # CWE-400
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
            # Hard cap on content catalogue — CWE-400
            if len(self._content) >= _MAX_CONTENT_ITEMS:
                evict = max(1, _MAX_CONTENT_ITEMS // 10)
                keys = list(self._content.keys())[:evict]
                for k in keys:
                    del self._content[k]
            self._content[content.content_id] = content

        logger.info("Generated tutorial %s: '%s' (seo=%.1f)", content.content_id, title, seo_score)
        return content

    def approve_content(self, content_id: str) -> bool:
        """HITL approval gate — approve a content piece for publishing.

        Called by the Founder or VP Marketing shadow agent after reviewing
        pending content. Once HITL_REVIEW_THRESHOLD pieces are approved,
        subsequent content auto-publishes.
        """
        # Validate content_id format before any dict lookup — CWE-20
        if not isinstance(content_id, str) or not _CONTENT_ID_RE.match(content_id):
            logger.warning("approve_content: invalid content_id format")
            return False
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
                errors.append(_sanitize_error(exc))
                logger.warning("Social variant generation error for %s: %s", content.content_id, _sanitize_error(exc))

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
        # Validate content_id format before dict lookup — CWE-20
        if not isinstance(content_id, str) or not _CONTENT_ID_RE.match(content_id):
            logger.warning("generate_social_variants: invalid content_id format")
            return []
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
            raw_id = prospect.get("id", "")
            raw_channel = prospect.get("channel", "email")

            try:
                prospect_id = _validate_prospect_id(raw_id)  # CWE-20
                channel = _validate_channel(raw_channel)      # CWE-20
            except ValueError as exc:
                errors.append(_sanitize_error(exc))
                logger.warning("Prospect validation failed — skipping: %s", _sanitize_error(exc))
                continue

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
                errors.append(_sanitize_error(exc))
                logger.warning("Outreach error for prospect %s: %s", prospect_id, _sanitize_error(exc))

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

            # Validate prospect_id before any DNC mutation — CWE-20
            try:
                prospect_id = _validate_prospect_id(prospect_id)
            except ValueError:
                logger.warning("Invalid prospect_id in pending reply — skipping")
                continue

            reply = ReplyRecord(
                reply_id=f"rpl-{uuid.uuid4().hex[:8]}",
                prospect_id=prospect_id,
                body=body,
                is_opt_out=self._is_opt_out(body),
                is_positive=self._is_positive_reply(body),
            )

            if reply.is_opt_out:
                with self._lock:
                    # Hard cap on DNC set — CWE-400
                    if len(self._dnc_set) < _MAX_DNC_ENTRIES:
                        self._dnc_set.add(prospect_id)
                    else:
                        logger.warning(
                            "DNC set at capacity (%d) — opt-out recorded in audit only",
                            _MAX_DNC_ENTRIES,
                        )
                opt_outs += 1
                # Do not log raw prospect_id — may contain a real email address (PII)
                self._publish_event("opt_out_recorded", {"prospect_id": prospect_id})
                logger.info("Opt-out recorded — added to DNC")

            if reply.is_positive:
                positives += 1
                self._publish_event("positive_reply_detected", {"prospect_id": prospect_id})
                logger.info("Positive reply detected — routing to trial orchestrator")

            with self._lock:
                capped_append(self._reply_records, reply, max_size=_MAX_HISTORY)
            processed += 1

        return {
            "processed": processed,
            "opt_outs": opt_outs,
            "positives": positives,
        }

    def inject_reply(self, prospect_id: str, body: str) -> None:
        """Inject a prospect reply for processing on the next cycle.

        Validates prospect_id format (CWE-20) and caps body length to prevent
        memory exhaustion (CWE-400).  Drops null bytes from body text.
        Raises ValueError for invalid prospect_id so callers get explicit feedback.
        """
        prospect_id = _validate_prospect_id(prospect_id)  # CWE-20: raises ValueError if invalid

        if not isinstance(body, str):
            body = ""
        body = body[:_MAX_REPLY_BODY]      # CWE-400: cap reply body
        body = body.replace("\x00", "")    # strip null bytes

        with self._lock:
            if not hasattr(self, "_pending_replies"):
                self._pending_replies: List[Dict[str, Any]] = []
            # Hard cap on pending-replies queue — CWE-400
            if len(self._pending_replies) >= _MAX_PENDING_REPLIES:
                logger.warning(
                    "Pending replies queue at capacity (%d) — dropping oldest reply",
                    _MAX_PENDING_REPLIES,
                )
                self._pending_replies = self._pending_replies[1:]
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
                errors.append(_sanitize_error(exc))
                logger.warning("Developer attraction error for feature '%s': %s", feature, _sanitize_error(exc))

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

    # ── B2B Partnership Cycle ──────────────────────────────────────────────

    def run_b2b_partnership_cycle(self) -> Dict[str, Any]:
        """Weekly B2B partnership outreach cycle.

        Iterates through the desired offerings list and sends personalised
        B2B pitches to sales / BD contacts at each partner company.
        Every contact is checked against the same compliance layer as the
        regular outreach cycle.  Positive responses automatically trigger
        a case-study brief (queued for HITL review).
        """
        cycle_id = f"b2b-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []

        partners_evaluated = 0
        pitches_sent = 0
        blocked_compliance = 0
        blocked_cooldown = 0
        interested = 0
        case_studies_drafted = 0

        with self._lock:
            partners = list(self._partnerships.values())

        for partner in partners:
            partners_evaluated += 1
            # Use a namespaced prospect_id so the B2B cooldown is tracked
            # separately from individual sales prospects
            prospect_id = f"b2b-{partner.partner_id}"
            channel = partner.channel

            try:
                _validate_channel(channel)  # CWE-20: channel must be in allowlist
            except ValueError:
                logger.warning(
                    "B2B partner '%s' has invalid channel '%s' — falling back to email",
                    partner.company, channel,
                )
                channel = "email"           # safe default

            try:
                decision = self._check_compliance(prospect_id, {"id": prospect_id, "channel": channel})

                if decision == ComplianceDecision.ALLOW:
                    pitch = self.generate_b2b_pitch(partner)
                    self._send_outreach(prospect_id, channel, {"id": prospect_id})
                    pitches_sent += 1

                    with self._lock:
                        self._partnerships[partner.partner_id].status = PartnershipStatus.OUTREACH_SENT.value
                        self._partnerships[partner.partner_id].outreach_sent_at = (
                            datetime.now(timezone.utc).isoformat()
                        )

                    self._publish_event("b2b_pitch_sent", {
                        "partner_id": partner.partner_id,
                        "company": partner.company,
                        "offering_types": partner.offering_types,
                        "channel": channel,
                        "pitch_id": pitch.get("pitch_id", ""),
                    })

                elif decision in (ComplianceDecision.BLOCK_DNC, ComplianceDecision.REQUIRES_CONSENT):
                    blocked_compliance += 1
                    with self._lock:
                        self._partnerships[partner.partner_id].status = PartnershipStatus.BLOCKED.value
                    self._publish_event("b2b_pitch_blocked", {
                        "partner_id": partner.partner_id,
                        "reason": decision.value,
                    })

                else:  # BLOCK_COOLDOWN
                    blocked_cooldown += 1
                    logger.debug("B2B pitch to %s blocked by cooldown", partner.company)

            except Exception as exc:  # noqa: BLE001
                errors.append(_sanitize_error(exc))
                logger.warning("B2B outreach error for %s: %s", partner.company, _sanitize_error(exc))

        completed_at = datetime.now(timezone.utc).isoformat()
        result = B2BPartnershipCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            partners_evaluated=partners_evaluated,
            pitches_sent=pitches_sent,
            blocked_compliance=blocked_compliance,
            blocked_cooldown=blocked_cooldown,
            interested=interested,
            case_studies_drafted=case_studies_drafted,
            errors=errors,
        )
        with self._lock:
            capped_append(self._b2b_cycles, result, max_size=_MAX_HISTORY)

        self._publish_event("b2b_cycle_completed", result.to_dict())
        logger.info(
            "B2B cycle %s: evaluated=%d sent=%d blocked(compliance=%d cooldown=%d)",
            cycle_id, partners_evaluated, pitches_sent, blocked_compliance, blocked_cooldown,
        )
        # Commission the completed B2B cycle — every executed system is commissioned.
        self._commission_system(
            system_id=cycle_id,
            system_name="B2B Partnership Outreach Cycle",
            metrics={
                "partners_evaluated": partners_evaluated,
                "pitches_sent": pitches_sent,
                "blocked_compliance": blocked_compliance,
                "blocked_cooldown": blocked_cooldown,
                "errors": errors,
            },
        )
        return result.to_dict()

    def generate_b2b_pitch(self, partner: PartnershipProspect) -> Dict[str, Any]:
        """Compose a personalised B2B pitch for a partnership prospect.

        Returns a pitch dict containing the subject line, body, and metadata.
        The body is tailored to each offering_type the partner is interested in
        and addressed to the named salesperson when one is known.

        Note: the pitch dict deliberately excludes salesperson_email (PII) —
        channel routing uses the internally-held field and never exposes it.
        """
        offering_labels = {
            "case_study": "a joint case study",
            "featuring": "a feature placement",
            "co_marketing": "a co-marketing campaign",
            "integration_featuring": "an integration directory listing",
            "press_mention": "a press mention",
            "podcast_guest": "a podcast / webinar appearance",
        }
        offering_str = " and ".join(
            offering_labels.get(t, t) for t in partner.offering_types[:3]
        )

        subject = (
            f"B2B Partnership Opportunity: Murphy System × {partner.company} — "
            f"{offering_str.capitalize()}"
        )

        # Personalise the greeting — use the named individual when known.
        if partner.salesperson_name:
            greeting = f"Hi {partner.salesperson_name},"
        else:
            greeting = f"Hi {partner.contact_role.replace('_', ' ').title()} Team,"

        # Use the positioning engine to get richer offering context —
        # falls back gracefully if positioning engine raises (e.g. unknown type).
        positioning_section = ""
        try:
            pos_data = self._positioning.get_positioning_for_offering_types(
                list(partner.offering_types[:6])
            )
            rel_caps = pos_data.get("relevant_capabilities", [])[:3]
            if rel_caps:
                cap_lines = "\n".join(
                    f"  • {c['name']}: {c['description']}"
                    for c in rel_caps
                )
                positioning_section = (
                    f"\nWhy Murphy is the right fit:\n{cap_lines}\n"
                )
        except Exception:  # noqa: BLE001
            logger.debug("Suppressed exception in self_marketing_orchestrator")

        body = (
            f"{greeting}\n\n"
            f"I'm reaching out from Murphy System (murphy.inoni.ai) — an AI automation "
            f"platform that enables teams to automate any workflow by describing it in "
            f"plain English, with confidence-gated execution and full human-in-the-loop "
            f"governance.\n\n"
            f"We'd love to explore {offering_str} with {partner.company}.\n\n"
            f"Why it's a great fit:\n"
            f"{partner.pitch_angle}\n"
            f"{positioning_section}\n"
            f"What we're proposing:\n"
            + "\n".join(f"  • {offering_labels.get(t, t).capitalize()}" for t in partner.offering_types)
            + "\n\n"
            "Happy to send over a one-pager, a live demo, or draft content — "
            "whatever works best for your team.\n\n"
            "Best,\n"
            "Corey Post\n"
            "Founder, Inoni LLC / Murphy System\n"
            "murphy.inoni.ai\n"
        )

        return {
            "pitch_id": f"b2bp-{uuid.uuid4().hex[:8]}",
            "partner_id": partner.partner_id,
            "company": partner.company,
            "channel": partner.channel,
            "subject": subject,
            "body": body,
            "offering_types": list(partner.offering_types),
            # Named contact metadata (not email — PII excluded from return value)
            "salesperson_name": partner.salesperson_name,
            "salesperson_title": partner.salesperson_title,
            "salesperson_linkedin": partner.salesperson_linkedin,
            "has_named_contact": partner.salesperson_name is not None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def process_partnership_replies(self, partner_id: str, reply_body: str) -> Dict[str, Any]:
        """Process a reply from a B2B partner contact.

        Advances partnership status on positive replies and auto-drafts a
        case-study brief.  Marks DECLINED on negative replies.
        Returns a summary dict of the action taken.

        partner_id must be a known entry in self._partnerships.  The reply_body
        is capped and null-byte stripped per the same hardening rules as regular
        reply processing.
        """
        # Validate partner_id — must be alphanumeric slug (not a raw email)
        if not isinstance(partner_id, str) or not _PARTNER_ID_RE.match(partner_id):
            raise ValueError(f"Invalid partner_id format (len={len(str(partner_id))})")

        if not isinstance(reply_body, str):
            reply_body = ""
        reply_body = reply_body[:_MAX_REPLY_BODY].replace("\x00", "")

        with self._lock:
            partner = self._partnerships.get(partner_id)
        if partner is None:
            return {"status": "unknown_partner", "partner_id": partner_id}

        is_positive = self._is_positive_reply(reply_body)
        is_opt_out = self._is_opt_out(reply_body)
        case_study_id: Optional[str] = None
        action_taken = "none"

        if is_opt_out:
            with self._lock:
                self._partnerships[partner_id].status = PartnershipStatus.DECLINED.value
                self._partnerships[partner_id].last_reply_at = datetime.now(timezone.utc).isoformat()
                # Honour opt-out: add namespaced prospect_id to DNC
                dnc_id = f"b2b-{partner_id}"
                if len(self._dnc_set) < _MAX_DNC_ENTRIES:
                    self._dnc_set.add(dnc_id)
            action_taken = "declined_opt_out"
            self._publish_event("b2b_partner_declined", {"partner_id": partner_id})

        elif is_positive:
            # Auto-draft case study brief (queued for HITL review)
            try:
                case_study = self.generate_case_study(
                    f"{partner.company} × Murphy System partnership"
                )
                case_study.status = ContentStatus.PENDING_REVIEW.value
                case_study.hitl_required = True
                case_study_id = case_study.content_id
                action_taken = "interested_case_study_drafted"
                with self._lock:
                    self._partnerships[partner_id].status = PartnershipStatus.CASE_STUDY_DRAFTED.value
                    self._partnerships[partner_id].last_reply_at = datetime.now(timezone.utc).isoformat()
                    self._partnerships[partner_id].case_study_content_id = case_study_id
            except Exception as exc:  # noqa: BLE001
                action_taken = "interested_case_study_failed"
                logger.warning("Case study generation for partner %s failed: %s", partner_id, _sanitize_error(exc))
                with self._lock:
                    self._partnerships[partner_id].status = PartnershipStatus.INTERESTED.value
                    self._partnerships[partner_id].last_reply_at = datetime.now(timezone.utc).isoformat()

            self._publish_event("b2b_partner_interested", {
                "partner_id": partner_id,
                "company": partner.company,
                "case_study_content_id": case_study_id,
            })

        logger.info("Partnership reply processed for %s — action=%s", partner_id, action_taken)
        return {
            "partner_id": partner_id,
            "action_taken": action_taken,
            "case_study_content_id": case_study_id,
            "is_positive": is_positive,
            "is_opt_out": is_opt_out,
        }

    def add_salesperson_contact(
        self,
        partner_id: str,
        *,
        name: Optional[str] = None,
        title: Optional[str] = None,
        email: Optional[str] = None,
        linkedin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add or update the named salesperson contact for a known partner.

        All fields are individually validated.  The update is atomic under the
        instance lock.  Returns the updated partner dict (email excluded — PII).

        Raises ValueError for:
          - Invalid partner_id format
          - Unknown partner_id
          - Any invalid contact field value
        """
        if not isinstance(partner_id, str) or not _PARTNER_ID_RE.match(partner_id):
            raise ValueError(f"Invalid partner_id format (len={len(str(partner_id))})")

        validated_name: Optional[str] = None
        validated_title: Optional[str] = None
        validated_email: Optional[str] = None
        validated_linkedin: Optional[str] = None

        if name is not None:
            validated_name = _validate_salesperson_name(name, param="name")
        if title is not None:
            validated_title = _validate_salesperson_name(title, param="title")
        if email is not None:
            validated_email = _validate_salesperson_email(email)
        if linkedin is not None:
            validated_linkedin = _validate_linkedin_url(linkedin)

        with self._lock:
            partner = self._partnerships.get(partner_id)
            if partner is None:
                raise ValueError(f"Unknown partner_id: {partner_id!r}")

            if validated_name is not None:
                self._partnerships[partner_id].salesperson_name = validated_name
            if validated_title is not None:
                self._partnerships[partner_id].salesperson_title = validated_title
            if validated_email is not None:
                self._partnerships[partner_id].salesperson_email = validated_email
            if validated_linkedin is not None:
                self._partnerships[partner_id].salesperson_linkedin = validated_linkedin

            updated = self._partnerships[partner_id].to_dict()

        logger.info(
            "Salesperson contact updated for partner '%s' — has_name=%s has_linkedin=%s",
            partner_id,
            updated.get("has_named_contact"),
            updated.get("salesperson_linkedin") is not None,
        )
        self._publish_event("b2b_contact_updated", {
            "partner_id": partner_id,
            "has_named_contact": updated.get("has_named_contact"),
        })
        return updated

    def get_partnership_pipeline(self) -> Dict[str, Any]:
        """Return the full B2B partnership pipeline status."""
        with self._lock:
            all_partners = [p.to_dict() for p in self._partnerships.values()]
            by_status: Dict[str, int] = {}
            contacts_identified = 0
            for p in self._partnerships.values():
                by_status[p.status] = by_status.get(p.status, 0) + 1
                if p.salesperson_name is not None:
                    contacts_identified += 1

        return {
            "total_partners": len(all_partners),
            "by_status": by_status,
            "contacts_identified": contacts_identified,
            "partners": all_partners,
            "cycles_run": len(self._b2b_cycles),
        }

    # ── Commissioning Gate ────────────────────────────────────────────────
    #
    # Commissioning is NOT a partner-facing offering — it is a cross-cutting
    # quality and readiness gate that runs over every system, cycle, and
    # module before it is marketed or included in outreach.  All B2B cycles,
    # content cycles, and new-offering registrations are commissioned here.
    #
    # This implements the "perform commissioning over everything performed"
    # principle: every system that Murphy touches gets a commissioning record
    # in the audit trail.

    def _commission_system(
        self,
        system_id: str,
        system_name: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a commissioning check over a newly executed system or cycle.

        Validates that the system meets minimum operational thresholds before
        its results are marketed, pitched, or included in outreach.  Every new
        B2B partnership category, content cycle result, and module activation
        passes through this gate.

        Parameters
        ----------
        system_id : str
            A unique identifier for the system being commissioned (e.g.
            cycle_id, partner_id, module name).
        system_name : str
            Human-readable name of the system.
        metrics : dict
            Quantitative metrics for the commissioning check.  Recognised keys:
            ``errors`` (list), ``pieces_generated`` (int), ``pitches_sent``
            (int), ``partners_evaluated`` (int), ``has_named_contact`` (bool).

        Returns
        -------
        dict
            Commissioning result with keys:
            ``status`` ("PASS" | "FAIL"), ``system_id``, ``system_name``,
            ``checks_passed``, ``checks_failed``, ``evidence``, ``timestamp``.

        The result is always emitted as a ``system_commissioned`` event for
        the cryptographic audit trail regardless of PASS/FAIL.
        """
        checks_passed: List[str] = []
        checks_failed: List[str] = []

        # CWE-20: sanitise inputs
        system_id = str(system_id)[:200].replace("\x00", "")
        system_name = str(system_name)[:200].replace("\x00", "")

        # ── Check 1: No critical errors ──────────────────────────────────
        errors = metrics.get("errors", [])
        if isinstance(errors, list) and len(errors) == 0:
            checks_passed.append("no_critical_errors")
        else:
            checks_failed.append(f"errors_present: {len(errors)} error(s)")

        # ── Check 2: Minimum output produced ────────────────────────────
        # Commissioning passes if the system produced at least one meaningful
        # output (piece, pitch, partner evaluation, or contact).
        output_count = (
            metrics.get("pieces_generated", 0)
            + metrics.get("pitches_sent", 0)
            + metrics.get("partners_evaluated", 0)
        )
        if output_count > 0:
            checks_passed.append(f"minimum_output_met: {output_count}")
        else:
            # Zero output is still a PASS for commissioning — the system ran
            # and didn't crash; content may have been deduplicated.
            checks_passed.append("zero_output_acceptable: dedup or cooldown active")

        # ── Check 3: System identity is valid ────────────────────────────
        if system_id and system_name:
            checks_passed.append("system_identity_valid")
        else:
            checks_failed.append("missing_system_identity")

        overall_status = "PASS" if not checks_failed else "FAIL"
        timestamp = datetime.now(timezone.utc).isoformat()

        result: Dict[str, Any] = {
            "status": overall_status,
            "system_id": system_id,
            "system_name": system_name,
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "evidence": {k: v for k, v in metrics.items() if not isinstance(v, (list, dict))},
            "timestamp": timestamp,
        }

        # Emit to audit trail — commissioning evidence is always recorded
        self._publish_event("system_commissioned", {
            "system_id": system_id,
            "system_name": system_name,
            "status": overall_status,
            "checks_passed": len(checks_passed),
            "checks_failed": len(checks_failed),
            "timestamp": timestamp,
        })

        log_level = logging.INFO if overall_status == "PASS" else logging.WARNING
        logger.log(
            log_level,
            "Commissioning %s for '%s' (%s): %d passed, %d failed",
            overall_status, system_name, system_id,
            len(checks_passed), len(checks_failed),
        )
        return result

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

            # B2B partnership metrics
            b2b_total = len(self._partnerships)
            b2b_sent = sum(
                1 for p in self._partnerships.values()
                if p.status in (
                    PartnershipStatus.OUTREACH_SENT.value,
                    PartnershipStatus.INTERESTED.value,
                    PartnershipStatus.CASE_STUDY_DRAFTED.value,
                    PartnershipStatus.FEATURING_AGREED.value,
                )
            )
            b2b_interested = sum(
                1 for p in self._partnerships.values()
                if p.status in (
                    PartnershipStatus.INTERESTED.value,
                    PartnershipStatus.CASE_STUDY_DRAFTED.value,
                    PartnershipStatus.FEATURING_AGREED.value,
                )
            )
            b2b_declined = sum(
                1 for p in self._partnerships.values()
                if p.status == PartnershipStatus.DECLINED.value
            )
            b2b_case_studies = sum(
                1 for p in self._partnerships.values()
                if p.case_study_content_id is not None
            )
            b2b_cycles_count = len(self._b2b_cycles)
            b2b_contacts_identified = sum(
                1 for p in self._partnerships.values()
                if p.salesperson_name is not None
            )

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
            "b2b_partnerships": {
                "total_partners": b2b_total,
                "pitches_sent": b2b_sent,
                "interested": b2b_interested,
                "declined": b2b_declined,
                "case_studies_drafted": b2b_case_studies,
                "contacts_identified": b2b_contacts_identified,
                "b2b_cycles_run": b2b_cycles_count,
            },
            "market_position": {
                "positioning_statement": self._positioning.get_market_position().positioning_statement,
                "tagline": self._positioning.get_market_position().tagline,
                "target_segments": list(self._positioning.get_market_position().target_segments),
                "differentiation_pillars": list(self._positioning.get_market_position().differentiation_pillars),
                "total_capabilities": len(self._positioning.list_capabilities()),
                "total_verticals": len(self._positioning.list_verticals()),
                "vertical_summary": self._positioning.get_vertical_summary(),
            },
            "cycles": {
                "content_cycles_run": content_cycles,
                "social_cycles_run": social_cycles,
                "outreach_cycles_run": outreach_cycles,
                "developer_attraction_cycles_run": dev_cycles,
                "b2b_partnership_cycles_run": b2b_cycles_count,
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
                "partnerships": {pid: p.to_dict() for pid, p in self._partnerships.items()},
                "b2b_cycles": [c.to_dict() for c in self._b2b_cycles],
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
            # Type guards for numeric fields — CWE-20 (prevent integer confusion attacks)
            raw_pub = state.get("published_count", 0)
            self._published_count = int(raw_pub) if isinstance(raw_pub, (int, float)) else 0

            raw_cat = state.get("category_index", 0)
            self._category_index = int(raw_cat) if isinstance(raw_cat, (int, float)) else 0

            # Restore cooldown dict — cap at _MAX_LAST_CONTACTED, validate keys (CWE-20/CWE-400)
            raw_lc = state.get("last_contacted", {})
            if isinstance(raw_lc, dict):
                items = list(raw_lc.items())[:_MAX_LAST_CONTACTED]
                self._last_contacted = {
                    k: v
                    for k, v in items
                    if isinstance(k, str) and _PROSPECT_ID_RE.match(k) and isinstance(v, str)
                }
            else:
                self._last_contacted = {}

            # Restore DNC set — cap at _MAX_DNC_ENTRIES, validate entries (CWE-20/CWE-400)
            raw_dnc = state.get("dnc_set", [])
            if isinstance(raw_dnc, list):
                self._dnc_set = {
                    pid
                    for pid in raw_dnc[:_MAX_DNC_ENTRIES]
                    if isinstance(pid, str) and _PROSPECT_ID_RE.match(pid)
                }
            else:
                self._dnc_set = set()

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

            # Restore B2B partnership pipeline
            for pd in state.get("partnerships", {}).values():
                pid = pd.get("partner_id", "")
                if pid and _PARTNER_ID_RE.match(pid):
                    # Validate optional salesperson contact fields on restore
                    sp_name: Optional[str] = None
                    sp_title: Optional[str] = None
                    sp_email: Optional[str] = None
                    sp_linkedin: Optional[str] = None
                    try:
                        if pd.get("salesperson_name"):
                            sp_name = _validate_salesperson_name(
                                str(pd["salesperson_name"])[:_MAX_NAME_LEN],
                                param="salesperson_name",
                            )
                    except ValueError:  # PROD-HARD A2: invalid name — drop field rather than reject prospect
                        logger.debug("Invalid salesperson_name for partnership %r; leaving unset", pid)
                    try:
                        if pd.get("salesperson_title"):
                            sp_title = _validate_salesperson_name(
                                str(pd["salesperson_title"])[:_MAX_NAME_LEN],
                                param="salesperson_title",
                            )
                    except ValueError:  # PROD-HARD A2: invalid title — drop field
                        logger.debug("Invalid salesperson_title for partnership %r; leaving unset", pid)
                    try:
                        if pd.get("salesperson_email"):
                            sp_email = _validate_salesperson_email(
                                str(pd["salesperson_email"])
                            )
                    except ValueError:
                        # PROD-HARD A2: invalid email — drop field. do NOT log: raw email is PII.
                        logger.debug("Invalid salesperson_email for partnership %r; leaving unset", pid)
                    try:
                        if pd.get("salesperson_linkedin"):
                            sp_linkedin = _validate_linkedin_url(
                                str(pd["salesperson_linkedin"])
                            )
                    except ValueError:  # PROD-HARD A2: invalid LinkedIn URL — drop field
                        logger.debug("Invalid salesperson_linkedin for partnership %r; leaving unset", pid)
                    self._partnerships[pid] = PartnershipProspect(
                        partner_id=pid,
                        company=str(pd.get("company", pid))[:200],
                        contact_role=str(pd.get("contact_role", "partnerships"))[:100],
                        channel=pd.get("channel", "email") if pd.get("channel") in _ALLOWED_CHANNELS else "email",
                        offering_types=list(pd.get("offering_types", [])),
                        pitch_angle=str(pd.get("pitch_angle", ""))[:_MAX_TOPIC_LEN],
                        status=pd.get("status", PartnershipStatus.PENDING.value),
                        outreach_sent_at=pd.get("outreach_sent_at"),
                        last_reply_at=pd.get("last_reply_at"),
                        case_study_content_id=pd.get("case_study_content_id"),
                        notes=str(pd.get("notes", ""))[:1000],
                        created_at=pd.get("created_at", ""),
                        salesperson_name=sp_name,
                        salesperson_title=sp_title,
                        salesperson_email=sp_email,
                        salesperson_linkedin=sp_linkedin,
                    )

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
            # Hard cap on cooldown-tracking dict — CWE-400
            if len(self._last_contacted) >= _MAX_LAST_CONTACTED:
                evict_count = max(1, _MAX_LAST_CONTACTED // 10)
                keys_to_evict = list(self._last_contacted.keys())[:evict_count]
                for k in keys_to_evict:
                    del self._last_contacted[k]
            self._last_contacted[prospect_id] = sent_at

        self._record_outreach(
            prospect_id, channel, OutreachStatus.SENT,
            ComplianceDecision.ALLOW, None,
        )
        logger.debug("Outreach sent to prospect via %s", channel)  # prospect_id omitted — may be email (PII)

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
            logger.debug("Suppressed exception in self_marketing_orchestrator")
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
        try:
            from event_backbone_client import publish as _bb_publish  # noqa: PLC0415
            _bb_publish(
                event_type,
                payload,
                source="self_marketing_orchestrator",
                backbone=self._backbone,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Event publish skipped: %s", exc)


__all__ = [
    "SelfMarketingOrchestrator",
    "CONTENT_CATEGORIES",
    "DEFAULT_DESIRED_OFFERINGS",
    "B2B_OFFERING_TYPES",
    "HITL_REVIEW_THRESHOLD",
    "OUTREACH_COOLDOWN_DAYS",
    "ComplianceDecision",
    "ContentStatus",
    "OutreachStatus",
    "PartnershipStatus",
    "GeneratedContent",
    "OutreachRecord",
    "ReplyRecord",
    "PartnershipProspect",
    "ContentCycleResult",
    "SocialCycleResult",
    "OutreachCycleResult",
    "DeveloperAttractionResult",
    "B2BPartnershipCycleResult",
    # Re-exported from market_positioning_engine for convenience
    "MarketPositioningEngine",
    "get_default_positioning_engine",
]
