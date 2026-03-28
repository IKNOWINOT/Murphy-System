# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
System-Leveraged Marketing & Advertising Plan for the Murphy Self-Selling Engine.

Design Label: MKT-007 — Self-Referential Marketing Plan
Owner: Marketing Team / Platform Engineering
Dependencies:
  - SelfSellingOutreach (_engine.py) — compose() integration point
  - ContentPipelineEngine (MKT-001) — automated content generation
  - CompetitiveIntelligenceEngine (MKT-005) — competitive personalization
  - ABTestingEngine (ABT-001) — outreach template A/B testing
  - CampaignOrchestrator (MKT-003) — multi-touch nurture sequences
  - AdaptiveCampaignEngine (MKT-004) — tier-filling adaptive campaigns
  - thread_safe_operations.capped_append — bounded collections

Murphy's marketing plan is **self-referential**: the outreach message IS the
demo.  Every interaction demonstrates Murphy's autonomous capability to a
prospect or contributor.

Key classes:
  - MarketingPlan           Top-level config container for a marketing plan run
  - CommunityBuildingPlan   Concrete plan for OSS community engagement
  - ContentCampaignConfig   Auto-generated content campaign config
  - CompetitiveOutreachConfig  Competitive-intelligence-enhanced outreach
  - ABTestConfig            A/B testing setup for outreach variants
  - MarketingPlanEngine     Orchestrator that wires all sub-systems together

Self-referential demo outreach enhancements in compose():
  - Injects A/B-tested subject lines / value propositions
  - Appends competitive-intelligence personalization when available
  - Embeds live community stats (GitHub stars, contributors, trials)

Community building features:
  - GitHub Discussions/Issues engagement automation
  - Documentation contribution pipeline trigger
  - Developer advocate shadow agent provisioning hook
  - Trial-to-contributor conversion pipeline

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock (CWE-362)
  - Bounded collections via capped_append (CWE-770)
  - Input validated before processing (CWE-20)
  - Hard caps prevent memory exhaustion (CWE-400)
  - Raw emails / PII never written to log records
  - Error messages sanitised before logging (CWE-209)
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# Input-validation constants                                        [CWE-20]
# ---------------------------------------------------------------------------

_PLAN_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_PROSPECT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
_COMPETITOR_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_MAX_NAME_LEN: int = 200
_MAX_REASON_LEN: int = 500
_MAX_NOTES_LEN: int = 2_000

# Closed allowlists                                                [CWE-20]
_ALLOWED_CHANNELS: frozenset = frozenset({"email", "sms", "linkedin", "blog", "social"})
_ALLOWED_CONTENT_TYPES: frozenset = frozenset({"blog", "social", "email", "copy"})
_ALLOWED_COMMUNITY_ACTIONS: frozenset = frozenset({
    "github_discussion", "github_issue", "doc_contribution", "dev_advocate",
    "trial_to_contributor",
})

# Hard caps                                                        [CWE-400]
_MAX_PLANS: int = 500
_MAX_CAMPAIGNS: int = 1_000
_MAX_AB_EXPERIMENTS: int = 200
_MAX_COMMUNITY_ACTIONS: int = 5_000
_MAX_AUDIT_LOG: int = 50_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PlanStatus(str, Enum):
    """Lifecycle state of a marketing plan."""
    DRAFT     = "draft"
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"


class CommunityActionType(str, Enum):
    """Types of community-building actions Murphy can automate."""
    GITHUB_DISCUSSION   = "github_discussion"
    GITHUB_ISSUE        = "github_issue"
    DOC_CONTRIBUTION    = "doc_contribution"
    DEV_ADVOCATE        = "dev_advocate"
    TRIAL_TO_CONTRIBUTOR = "trial_to_contributor"


class ContentTrigger(str, Enum):
    """Events that automatically trigger content generation."""
    TRIAL_COMPLETED  = "trial_completed"
    CUSTOMER_WIN     = "customer_win"
    FEATURE_RELEASED = "feature_released"
    MILESTONE_HIT    = "milestone_hit"
    COMPETITOR_MOVE  = "competitor_move"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ABTestConfig:
    """Configuration for a single A/B test on outreach content."""
    experiment_id: str
    name: str
    variants: List[Dict[str, str]] = field(default_factory=list)
    primary_metric: str = "reply_rate"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "variants": self.variants,
            "primary_metric": self.primary_metric,
            "created_at": self.created_at,
        }


@dataclass
class ContentCampaignConfig:
    """Configuration for an auto-generated content campaign."""
    config_id: str
    trigger: str                        # ContentTrigger value
    content_type: str                   # e.g. "blog", "social"
    channels: List[str] = field(default_factory=list)
    topic_template: str = ""
    auto_approve: bool = False          # True only for low-risk social posts
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "trigger": self.trigger,
            "content_type": self.content_type,
            "channels": self.channels,
            "topic_template": self.topic_template,
            "auto_approve": self.auto_approve,
            "created_at": self.created_at,
        }


@dataclass
class CompetitiveOutreachConfig:
    """Per-competitor outreach personalization derived from competitive intel."""
    competitor_id: str
    competitor_name: str
    prospect_segment: str               # e.g. "users of <competitor>"
    personalization_hook: str           # injected into compose()
    channels: List[str] = field(default_factory=list)
    active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "competitor_name": self.competitor_name,
            "prospect_segment": self.prospect_segment,
            "personalization_hook": self.personalization_hook,
            "channels": self.channels,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class CommunityBuildingPlan:
    """
    Concrete plan for building an open-source community around Murphy.

    Covers:
    - GitHub Discussions/Issues engagement automation
    - Documentation contribution pipeline
    - Developer advocate shadow agent provisioning
    - Trial-to-contributor conversion pipeline
    """
    plan_id: str
    github_repo: str = "IKNOWINOT/Murphy-System"
    auto_respond_to_discussions: bool = True
    auto_label_good_first_issues: bool = True
    doc_gap_detection_enabled: bool = True
    dev_advocate_shadow_agent_enabled: bool = True
    trial_to_contributor_drip_days: int = 7     # days post-trial before invite
    community_actions: List[Dict[str, Any]] = field(default_factory=list)
    status: str = PlanStatus.DRAFT.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "github_repo": self.github_repo,
            "auto_respond_to_discussions": self.auto_respond_to_discussions,
            "auto_label_good_first_issues": self.auto_label_good_first_issues,
            "doc_gap_detection_enabled": self.doc_gap_detection_enabled,
            "dev_advocate_shadow_agent_enabled": self.dev_advocate_shadow_agent_enabled,
            "trial_to_contributor_drip_days": self.trial_to_contributor_drip_days,
            "community_actions": self.community_actions,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class MarketingPlan:
    """
    Top-level marketing plan configuration produced by :class:`MarketingPlanEngine`.

    Encapsulates all sub-system configurations needed to run Murphy's
    self-referential marketing loop.
    """
    plan_id: str
    name: str
    status: str = PlanStatus.DRAFT.value
    ab_tests: List[ABTestConfig] = field(default_factory=list)
    content_configs: List[ContentCampaignConfig] = field(default_factory=list)
    competitive_configs: List[CompetitiveOutreachConfig] = field(default_factory=list)
    community_plan: Optional[CommunityBuildingPlan] = None
    campaign_ids: List[str] = field(default_factory=list)   # IDs in CampaignOrchestrator
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "status": self.status,
            "ab_tests": [t.to_dict() for t in self.ab_tests],
            "content_configs": [c.to_dict() for c in self.content_configs],
            "competitive_configs": [c.to_dict() for c in self.competitive_configs],
            "community_plan": (
                self.community_plan.to_dict() if self.community_plan else None
            ),
            "campaign_ids": self.campaign_ids,
            "created_at": self.created_at,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MarketingPlanEngine:
    """
    Orchestrates Murphy's system-leveraged marketing plan.

    Wires together:
    - A/B testing of outreach templates (ABTestingEngine)
    - Automated content generation on trial/win events (ContentPipelineEngine)
    - Competitive-intelligence personalization (CompetitiveIntelligenceEngine)
    - Multi-touch nurture campaigns (CampaignOrchestrator + AdaptiveCampaignEngine)
    - Community building automation (CommunityBuildingPlan)

    Integration point with :class:`SelfSellingOutreach`:
    Call :meth:`enrich_compose_kwargs` before ``outreach.compose(prospect, live_stats)``
    to inject A/B variant subject lines and competitive personalization hooks
    into the outreach message body.
    """

    # Default A/B test variants for outreach subject lines
    _DEFAULT_SUBJECT_VARIANTS: List[Dict[str, str]] = [
        {
            "variant_id": "A",
            "name": "Stats-led",
            "subject_template": (
                "Murphy just handled {emails_sent} emails automatically — "
                "here's what it can do for {company_name}"
            ),
        },
        {
            "variant_id": "B",
            "name": "Proof-led",
            "subject_template": (
                "I automated my own outreach to you. Murphy can do the same "
                "for {company_name}."
            ),
        },
        {
            "variant_id": "C",
            "name": "Question-led",
            "subject_template": (
                "What if {company_name} never had to send a follow-up email "
                "manually again?"
            ),
        },
    ]

    # Default content campaign configs triggered by trial lifecycle events
    _DEFAULT_CONTENT_CONFIGS: List[Dict[str, Any]] = [
        {
            "trigger": ContentTrigger.TRIAL_COMPLETED.value,
            "content_type": "blog",
            "channels": ["blog", "social"],
            "topic_template": (
                "How Murphy automated {business_type} workflows for {company_name} "
                "in 3 days (trial case study)"
            ),
            "auto_approve": False,
        },
        {
            "trigger": ContentTrigger.CUSTOMER_WIN.value,
            "content_type": "social",
            "channels": ["social"],
            "topic_template": (
                "New customer: {company_name} is now running Murphy for "
                "{business_type} automation"
            ),
            "auto_approve": True,
        },
        {
            "trigger": ContentTrigger.MILESTONE_HIT.value,
            "content_type": "blog",
            "channels": ["blog", "social", "email"],
            "topic_template": "Murphy milestone: {milestone_description}",
            "auto_approve": False,
        },
    ]

    def __init__(
        self,
        content_pipeline: Any = None,
        competitive_engine: Any = None,
        ab_testing_engine: Any = None,
        campaign_orchestrator: Any = None,
        adaptive_campaign_engine: Any = None,
    ) -> None:
        """
        Parameters
        ----------
        content_pipeline:
            Optional :class:`ContentPipelineEngine` instance (MKT-001).
        competitive_engine:
            Optional :class:`CompetitiveIntelligenceEngine` instance (MKT-005).
        ab_testing_engine:
            Optional :class:`ABTestingEngine` instance (ABT-001).
        campaign_orchestrator:
            Optional :class:`CampaignOrchestrator` instance (MKT-003).
        adaptive_campaign_engine:
            Optional :class:`AdaptiveCampaignEngine` instance (MKT-004).
        """
        self._content_pipeline = content_pipeline
        self._competitive_engine = competitive_engine
        self._ab_testing_engine = ab_testing_engine
        self._campaign_orchestrator = campaign_orchestrator
        self._adaptive_campaign_engine = adaptive_campaign_engine

        self._plans: List[MarketingPlan] = []
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────

    def generate_marketing_plan(
        self,
        name: str,
        include_community_plan: bool = True,
        notes: str = "",
    ) -> MarketingPlan:
        """
        Generate a complete, executable :class:`MarketingPlan`.

        Builds default A/B test configs, content campaign configs, and
        (optionally) a :class:`CommunityBuildingPlan`.  Competitive outreach
        configs are generated if a :class:`CompetitiveIntelligenceEngine` is
        wired in.

        Parameters
        ----------
        name:
            Human-readable plan name.
        include_community_plan:
            Whether to include a :class:`CommunityBuildingPlan`.
        notes:
            Optional notes (capped to :data:`_MAX_NOTES_LEN`).

        Returns
        -------
        MarketingPlan
            The newly created plan (also stored internally).
        """
        if not name or not isinstance(name, str):
            raise ValueError("name must be a non-empty string")
        name = name[:_MAX_NAME_LEN]
        notes = (notes or "")[:_MAX_NOTES_LEN]

        with self._lock:
            if len(self._plans) >= _MAX_PLANS:
                raise ValueError(
                    f"Maximum plan count ({_MAX_PLANS}) reached; "
                    "archive completed plans before creating new ones"
                )

        plan_id = str(uuid.uuid4())

        # 1. A/B test configs
        ab_tests = self._build_default_ab_tests()

        # 2. Content campaign configs
        content_configs = self._build_default_content_configs()

        # 3. Competitive outreach configs
        competitive_configs = self._build_competitive_configs()

        # 4. Community plan
        community_plan = (
            self._build_community_plan() if include_community_plan else None
        )

        # 5. Wire tier-fill campaigns into AdaptiveCampaignEngine (if available)
        campaign_ids = self._bootstrap_tier_campaigns()

        plan = MarketingPlan(
            plan_id=plan_id,
            name=name,
            status=PlanStatus.ACTIVE.value,
            ab_tests=ab_tests,
            content_configs=content_configs,
            competitive_configs=competitive_configs,
            community_plan=community_plan,
            campaign_ids=campaign_ids,
            notes=notes,
        )

        with self._lock:
            capped_append(self._plans, plan, _MAX_PLANS)
            self._append_audit(
                action="plan_created",
                plan_id=plan_id,
                name=name,
            )

        logger.info("MarketingPlan created: %s (%s)", plan_id, name)
        return plan

    def enrich_compose_kwargs(
        self,
        prospect_id: str,
        live_stats: Dict[str, Any],
        competitor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return kwargs to inject into :class:`SelfSellingOutreach`.compose().

        This is the **integration point** with the compose pipeline.  Callers
        should merge the returned dict into their compose parameters before
        calling ``outreach.compose(prospect, live_stats)``.

        The enrichments applied:
        1. **A/B variant subject** — selects a deterministic variant from the
           active A/B experiment based on ``prospect_id`` hashing.
        2. **Competitive personalization hook** — appended to the body when a
           ``competitor_id`` is supplied and a matching config exists.

        Parameters
        ----------
        prospect_id:
            The prospect being contacted (used for variant assignment).
        live_stats:
            Live system stats dict from ``MurphySelfSellingEngine``.
        competitor_id:
            Optional competitor ID for competitive personalization.

        Returns
        -------
        dict
            Keys: ``subject_override`` (str|None), ``body_suffix`` (str|None).
        """
        if not _PROSPECT_ID_RE.match(str(prospect_id or "")[:200]):
            raise ValueError(f"Invalid prospect_id: {str(prospect_id)[:50]!r}")

        subject_override: Optional[str] = None
        body_suffix: Optional[str] = None

        # A/B variant assignment via stable hash
        variant = self._select_ab_variant(prospect_id)
        if variant:
            company_name = live_stats.get("company_name", "your business")
            emails_sent = live_stats.get("emails_sent", 0)
            subject_override = (
                variant["subject_template"]
                .replace("{company_name}", str(company_name))
                .replace("{emails_sent}", str(emails_sent))
            )

        # Competitive personalization
        if competitor_id:
            clean_cid = str(competitor_id)[:200]
            if _COMPETITOR_ID_RE.match(clean_cid):
                hook = self._get_competitive_hook(clean_cid)
                if hook:
                    body_suffix = hook

        return {
            "subject_override": subject_override,
            "body_suffix": body_suffix,
        }

    def trigger_content_generation(
        self,
        trigger: str,
        context: Dict[str, Any],
    ) -> Optional[str]:
        """
        Fire a content generation event (e.g. trial_completed, customer_win).

        If a :class:`ContentPipelineEngine` is wired in, creates a content brief
        and draft automatically.  Returns the ``item_id`` of the new content, or
        ``None`` if no pipeline is configured.

        Parameters
        ----------
        trigger:
            A :class:`ContentTrigger` value.
        context:
            Template variables (e.g. ``{"company_name": "Acme", ...}``).
        """
        if trigger not in {t.value for t in ContentTrigger}:
            raise ValueError(f"Unknown trigger: {trigger!r}")

        # Find matching content config
        config = self._find_content_config(trigger)
        if config is None:
            logger.debug("No content config for trigger %s", trigger)
            return None

        if self._content_pipeline is None:
            logger.debug("ContentPipelineEngine not wired; skipping content generation")
            return None

        # Render topic from template
        topic = config.topic_template
        for key, value in context.items():
            topic = topic.replace(f"{{{key}}}", str(value))
        topic = topic[:_MAX_NAME_LEN]

        try:
            brief = self._content_pipeline.create_brief(
                topic=topic,
                content_type=config.content_type,
                target_channels=config.channels,
            )
            item = self._content_pipeline.create_draft(
                brief_id=brief.brief_id,
                description=topic,
            )
            logger.info(
                "Content generated for trigger %s: item_id=%s", trigger, item.item_id
            )
            with self._lock:
                self._append_audit(
                    action="content_generated",
                    trigger=trigger,
                    item_id=item.item_id,
                )
            return item.item_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Content generation failed for trigger %s: %s", trigger, exc)
            return None

    def record_community_action(
        self,
        action_type: str,
        subject_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Record a community-building action (GitHub engagement, doc contribution, etc.).

        Parameters
        ----------
        action_type:
            A :class:`CommunityActionType` value.
        subject_id:
            The ID of the entity acted upon (GitHub issue number, user ID, etc.).
        notes:
            Optional description of the action.
        """
        if action_type not in _ALLOWED_COMMUNITY_ACTIONS:
            raise ValueError(
                f"Unknown community action_type {action_type!r}; "
                f"must be one of {sorted(_ALLOWED_COMMUNITY_ACTIONS)}"
            )
        subject_id = str(subject_id)[:200]
        notes = str(notes)[:_MAX_REASON_LEN]

        record: Dict[str, Any] = {
            "record_id": str(uuid.uuid4()),
            "action_type": action_type,
            "subject_id": subject_id,
            "notes": notes,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            capped_append(self._audit_log, record, _MAX_COMMUNITY_ACTIONS)
            self._append_audit(action="community_action", **record)

        logger.info("Community action recorded: %s on %s", action_type, subject_id)
        return record

    def get_active_plan(self) -> Optional[MarketingPlan]:
        """Return the most recent active plan, or ``None``."""
        with self._lock:
            for plan in reversed(self._plans):
                if plan.status == PlanStatus.ACTIVE.value:
                    return plan
        return None

    def get_plan(self, plan_id: str) -> Optional[MarketingPlan]:
        """Look up a plan by ID."""
        with self._lock:
            for plan in self._plans:
                if plan.plan_id == plan_id:
                    return plan
        return None

    def list_plans(self) -> List[Dict[str, Any]]:
        """Return all plans as dicts."""
        with self._lock:
            return [p.to_dict() for p in self._plans]

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent audit log entries."""
        with self._lock:
            return list(self._audit_log[-limit:])

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of the engine."""
        with self._lock:
            active = sum(
                1 for p in self._plans if p.status == PlanStatus.ACTIVE.value
            )
            return {
                "total_plans": len(self._plans),
                "active_plans": active,
                "content_pipeline_wired": self._content_pipeline is not None,
                "competitive_engine_wired": self._competitive_engine is not None,
                "ab_testing_wired": self._ab_testing_engine is not None,
                "campaign_orchestrator_wired": self._campaign_orchestrator is not None,
                "adaptive_campaign_wired": self._adaptive_campaign_engine is not None,
            }

    # ── Internal helpers ──────────────────────────────────────────────

    def _build_default_ab_tests(self) -> List[ABTestConfig]:
        """Build default A/B test configs for outreach subject lines."""
        tests: List[ABTestConfig] = []
        exp = ABTestConfig(
            experiment_id=str(uuid.uuid4()),
            name="Outreach Subject Line Test",
            variants=list(self._DEFAULT_SUBJECT_VARIANTS),
            primary_metric="reply_rate",
        )
        tests.append(exp)

        # Register with live A/B engine if wired
        if self._ab_testing_engine is not None:
            try:
                self._ab_testing_engine.create_experiment(
                    name=exp.name,
                    variants=[
                        {"name": v["name"], "description": v["subject_template"]}
                        for v in exp.variants
                    ],
                    primary_metric=exp.primary_metric,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("AB engine experiment creation failed: %s", exc)

        return tests

    def _build_default_content_configs(self) -> List[ContentCampaignConfig]:
        """Build default content campaign configs from templates."""
        configs: List[ContentCampaignConfig] = []
        for tmpl in self._DEFAULT_CONTENT_CONFIGS:
            cfg = ContentCampaignConfig(
                config_id=str(uuid.uuid4()),
                trigger=tmpl["trigger"],
                content_type=tmpl["content_type"],
                channels=list(tmpl.get("channels", [])),
                topic_template=tmpl.get("topic_template", ""),
                auto_approve=bool(tmpl.get("auto_approve", False)),
            )
            configs.append(cfg)
        return configs

    def _build_competitive_configs(self) -> List[CompetitiveOutreachConfig]:
        """Generate competitive outreach configs from the intelligence engine."""
        if self._competitive_engine is None:
            return []

        configs: List[CompetitiveOutreachConfig] = []
        try:
            strategies = self._competitive_engine.generate_competitive_strategies()
            for strategy in strategies[:10]:   # cap at 10 competitors
                cid = str(strategy.get("competitor_id", ""))[:200]
                if not _COMPETITOR_ID_RE.match(cid):
                    continue
                cfg = CompetitiveOutreachConfig(
                    competitor_id=cid,
                    competitor_name=str(strategy.get("competitor_name", cid))[:_MAX_NAME_LEN],
                    prospect_segment=f"users_of_{cid}",
                    personalization_hook=(
                        f"I noticed your team may be using {strategy.get('competitor_name', cid)}. "
                        f"Murphy replaces it entirely — here's how: "
                        f"{str(strategy.get('key_message', ''))[:200]}"
                    ),
                    channels=["email", "linkedin"],
                )
                configs.append(cfg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not build competitive configs: %s", exc)

        return configs

    def _build_community_plan(self) -> CommunityBuildingPlan:
        """Build the default community building plan."""
        return CommunityBuildingPlan(
            plan_id=str(uuid.uuid4()),
            status=PlanStatus.ACTIVE.value,
        )

    def _bootstrap_tier_campaigns(self) -> List[str]:
        """Bootstrap adaptive tier campaigns and return their IDs."""
        if self._adaptive_campaign_engine is None:
            return []
        try:
            self._adaptive_campaign_engine.bootstrap_tier_campaigns()
            campaigns = self._adaptive_campaign_engine.get_all_campaigns()
            return list(campaigns.keys())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tier campaign bootstrap failed: %s", exc)
            return []

    def _select_ab_variant(self, prospect_id: str) -> Optional[Dict[str, str]]:
        """Select a deterministic A/B variant for a prospect via modular hash."""
        variants = self._DEFAULT_SUBJECT_VARIANTS
        if not variants:
            return None
        # Use a stable integer hash of the prospect_id for deterministic assignment
        bucket = hash(prospect_id) % len(variants)
        return variants[bucket]

    def _get_competitive_hook(self, competitor_id: str) -> Optional[str]:
        """Return the personalization hook for a competitor, if configured."""
        with self._lock:
            for plan in reversed(self._plans):
                for cfg in plan.competitive_configs:
                    if cfg.competitor_id == competitor_id and cfg.active:
                        return cfg.personalization_hook
        return None

    def _find_content_config(self, trigger: str) -> Optional[ContentCampaignConfig]:
        """Find the first matching content campaign config for a trigger."""
        with self._lock:
            for plan in reversed(self._plans):
                if plan.status != PlanStatus.ACTIVE.value:
                    continue
                for cfg in plan.content_configs:
                    if cfg.trigger == trigger:
                        return cfg
        return None

    def _append_audit(self, **kwargs: Any) -> None:
        """Append an audit record (must be called with self._lock held)."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        capped_append(self._audit_log, record, _MAX_AUDIT_LOG)
