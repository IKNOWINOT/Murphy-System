"""
Competitive Intelligence Engine — Adversarial Marketing & R&D Gap Routing

Design Label: MKT-005 — Competitive Intelligence & Adversarial Positioning
Owner: VP Marketing / CRO / Chief Research Officer
Dependencies:
  - AdaptiveCampaignEngine (MKT-004, tier campaigns)
  - UnitEconomicsAnalyzer (BIZ-002, our pricing & margins)
  - CapabilityMap (gap analysis for R&D routing)
  - EventBackbone (audit trail)

Purpose:
  Adversarial marketing: request marketing information from all competitors,
  create offering systems that are competitive against the landscape.
  Identify who competitors are selling to and how, discover how we can
  improve upon that, and route anything we don't have through R&D for
  future plans to start building.

Flow:
  1. Register competitor profiles (name, products, pricing, target markets,
     channels, strengths, weaknesses)
  2. Analyze the competitive landscape (positioning matrix, gap detection)
  3. Generate competitive response strategies per tier
  4. Detect capability gaps where competitors offer something we don't
  5. Route gaps to R&D backlog with priority, rationale, and projected
     impact
  6. Generate adversarial campaign briefs that position Murphy against
     each competitor's weaknesses

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: configurable max competitors and R&D items
  - Audit trail: every analysis and R&D routing is logged

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
from enum import Enum
from typing import Any, Dict, List, Optional, Set

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

class CompetitorThreatLevel(str, Enum):
    """How much of a threat a competitor poses to a specific tier."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RDPriority(str, Enum):
    """Priority for R&D backlog items."""
    CRITICAL = "critical"       # Competitor has it, customers ask for it
    HIGH = "high"               # Competitor has it, strategic advantage
    MEDIUM = "medium"           # Nice to have, some competitive pressure
    LOW = "low"                 # Future consideration


class RDStatus(str, Enum):
    """Status of an R&D backlog item."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CompetitorProfile:
    """Profile of a competitor in the automation/AI platform landscape."""
    competitor_id: str
    name: str
    website: str = ""
    products: List[str] = field(default_factory=list)
    pricing: Dict[str, str] = field(default_factory=dict)  # tier→price
    target_markets: List[str] = field(default_factory=list)
    sales_channels: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    key_features: List[str] = field(default_factory=list)
    estimated_market_share: float = 0.0  # 0.0–1.0
    notes: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "name": self.name,
            "website": self.website,
            "products": list(self.products),
            "pricing": dict(self.pricing),
            "target_markets": list(self.target_markets),
            "sales_channels": list(self.sales_channels),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "key_features": list(self.key_features),
            "estimated_market_share": self.estimated_market_share,
            "notes": self.notes,
            "created_at": self.created_at,
        }


@dataclass
class CompetitiveGap:
    """A capability that competitors have but we don't."""
    gap_id: str
    feature: str
    competitors_with_feature: List[str]
    customer_demand: str            # "high", "medium", "low"
    impact_description: str
    suggested_priority: RDPriority = RDPriority.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "feature": self.feature,
            "competitors_with_feature": list(self.competitors_with_feature),
            "customer_demand": self.customer_demand,
            "impact_description": self.impact_description,
            "suggested_priority": self.suggested_priority.value,
        }


@dataclass
class RDBacklogItem:
    """An R&D backlog item routed from competitive gap analysis."""
    item_id: str
    title: str
    description: str
    source_gap_id: Optional[str] = None
    priority: RDPriority = RDPriority.MEDIUM
    status: RDStatus = RDStatus.PROPOSED
    competitors_driving: List[str] = field(default_factory=list)
    projected_impact: str = ""
    target_tier: str = ""           # Which pricing tier benefits most
    estimated_effort: str = ""      # "small", "medium", "large"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "source_gap_id": self.source_gap_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "competitors_driving": list(self.competitors_driving),
            "projected_impact": self.projected_impact,
            "target_tier": self.target_tier,
            "estimated_effort": self.estimated_effort,
            "created_at": self.created_at,
        }


@dataclass
class CompetitiveResponseStrategy:
    """A strategy for positioning Murphy against a specific competitor."""
    strategy_id: str
    competitor_id: str
    competitor_name: str
    our_advantages: List[str]
    their_weaknesses_to_exploit: List[str]
    target_segments: List[str]       # Which of their customers to target
    messaging: str
    recommended_channels: List[str]
    recommended_tier: str            # Which Murphy tier to promote
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "competitor_id": self.competitor_id,
            "competitor_name": self.competitor_name,
            "our_advantages": list(self.our_advantages),
            "their_weaknesses_to_exploit": list(self.their_weaknesses_to_exploit),
            "target_segments": list(self.target_segments),
            "messaging": self.messaging,
            "recommended_channels": list(self.recommended_channels),
            "recommended_tier": self.recommended_tier,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Murphy's own capabilities (what we offer that others may not)
# ---------------------------------------------------------------------------

_MURPHY_CAPABILITIES: Set[str] = {
    "natural_language_automation",
    "75_plus_connectors",
    "enterprise_governance_rbac",
    "audit_trail_compliance",
    "human_in_the_loop",
    "emergency_stop",
    "swarm_orchestration",
    "self_improving_ml",
    "scada_iot_integration",
    "on_premise_deployment",
    "content_creator_tools",
    "multi_llm_routing",
    "financial_reporting",
    "executive_planning",
    "domain_engine_10_domains",
    "zero_budget_bootstrap",
    "open_source_core",
    "safety_first_architecture",
    "deterministic_routing",
    "workspace_boundaries",
}

# Murphy pricing for competitive comparison
_MURPHY_PRICING: Dict[str, str] = {
    "community": "Free (open source)",
    "solo": "$99/mo",
    "pro": "$599/mo per seat",
    "enterprise": "Contact us",
    "creator_starter": "$20/mo",
    "creator_pro": "$299/mo",
}


# ---------------------------------------------------------------------------
# Default competitor landscape (AI/automation platforms)
# ---------------------------------------------------------------------------

_DEFAULT_COMPETITORS: List[Dict[str, Any]] = [
    {
        "name": "Zapier",
        "website": "zapier.com",
        "products": ["Zapier Workflows", "Zapier Tables", "Zapier Interfaces"],
        "pricing": {"free": "$0 (100 tasks)", "starter": "$19.99/mo", "professional": "$49/mo", "team": "$69/mo", "enterprise": "Custom"},
        "target_markets": ["smb_owners", "marketing_teams", "ops_managers", "non_technical_users"],
        "sales_channels": ["content_marketing", "seo", "google_ads", "partnerships", "freemium_funnel"],
        "strengths": ["brand_recognition", "5000_app_integrations", "ease_of_use", "no_code_ui"],
        "weaknesses": ["no_on_premise", "no_ai_orchestration", "limited_governance", "no_scada_iot", "no_safety_gates", "per_task_pricing_expensive_at_scale"],
        "key_features": ["workflow_automation", "multi_step_zaps", "webhooks", "tables_database", "interfaces_ui"],
        "estimated_market_share": 0.25,
    },
    {
        "name": "Make (Integromat)",
        "website": "make.com",
        "products": ["Make Scenarios", "Make Enterprise"],
        "pricing": {"free": "$0 (1000 ops)", "core": "$9/mo", "pro": "$16/mo", "teams": "$29/mo", "enterprise": "Custom"},
        "target_markets": ["smb_owners", "freelancers", "agencies", "marketing_teams"],
        "sales_channels": ["freemium_funnel", "content_marketing", "partner_marketplace", "youtube_tutorials"],
        "strengths": ["visual_workflow_builder", "complex_routing", "affordable_pricing", "operations_based_billing"],
        "weaknesses": ["no_on_premise", "no_governance_rbac", "no_ai_orchestration", "limited_enterprise_features", "no_scada_iot", "no_safety_gates"],
        "key_features": ["visual_scenarios", "http_modules", "data_stores", "error_handling", "scheduling"],
        "estimated_market_share": 0.10,
    },
    {
        "name": "n8n",
        "website": "n8n.io",
        "products": ["n8n Cloud", "n8n Self-hosted"],
        "pricing": {"community": "Free (self-hosted)", "starter": "$20/mo", "pro": "$50/mo", "enterprise": "Custom"},
        "target_markets": ["developers", "devops_engineers", "agencies", "tech_savvy_smb"],
        "sales_channels": ["open_source_community", "github", "content_marketing", "developer_advocacy"],
        "strengths": ["open_source", "self_hosted_option", "developer_friendly", "code_extensible", "fair_code_license"],
        "weaknesses": ["limited_enterprise_governance", "no_swarm_orchestration", "no_scada_iot", "smaller_connector_library", "no_content_creator_tools", "no_financial_reporting"],
        "key_features": ["visual_workflow", "code_nodes", "ai_agents", "self_hosted", "community_nodes"],
        "estimated_market_share": 0.05,
    },
    {
        "name": "UiPath",
        "website": "uipath.com",
        "products": ["UiPath Platform", "UiPath Autopilot", "Test Suite"],
        "pricing": {"free": "$0 (limited)", "pro": "$420/mo", "enterprise": "Custom (expensive)"},
        "target_markets": ["enterprise_it", "fortune_500", "financial_services", "healthcare", "government"],
        "sales_channels": ["enterprise_sales_team", "partner_network", "gartner_presence", "industry_events"],
        "strengths": ["rpa_market_leader", "enterprise_grade", "attended_unattended_bots", "process_mining", "large_partner_ecosystem"],
        "weaknesses": ["very_expensive", "complex_setup", "heavy_infrastructure", "no_content_creator_tools", "no_open_source", "steep_learning_curve", "no_natural_language_automation"],
        "key_features": ["rpa_bots", "process_mining", "document_understanding", "test_automation", "ai_center"],
        "estimated_market_share": 0.15,
    },
    {
        "name": "Microsoft Power Automate",
        "website": "powerautomate.microsoft.com",
        "products": ["Power Automate Cloud", "Power Automate Desktop", "Process Mining"],
        "pricing": {"per_user": "$15/mo", "per_flow": "$100/mo (5 flows)", "attended_rpa": "$40/mo", "unattended_rpa": "$150/mo"},
        "target_markets": ["microsoft_365_users", "enterprise_it", "business_analysts", "office_workers"],
        "sales_channels": ["microsoft_365_bundle", "enterprise_licensing", "partner_network", "microsoft_learn"],
        "strengths": ["microsoft_ecosystem", "huge_installed_base", "copilot_ai_integration", "desktop_rpa", "low_code"],
        "weaknesses": ["microsoft_lock_in", "no_open_source", "complex_licensing", "no_scada_iot", "no_content_creator_tools", "no_swarm_orchestration", "limited_multi_llm"],
        "key_features": ["cloud_flows", "desktop_flows", "ai_builder", "process_mining", "copilot"],
        "estimated_market_share": 0.20,
    },
]


# ---------------------------------------------------------------------------
# Competitive Intelligence Engine
# ---------------------------------------------------------------------------

class CompetitiveIntelligenceEngine:
    """Adversarial marketing: analyze competitors, build competitive
    strategies, and route capability gaps through R&D.

    Responsibilities:
      1. Maintain a competitor profile database
      2. Analyze landscape to find positioning opportunities
      3. Generate competitive response strategies per competitor
      4. Detect capability gaps (they have it, we don't)
      5. Route gaps to R&D backlog with priority and impact
      6. Generate adversarial campaign briefs for the marketing team
    """

    def __init__(self, our_capabilities: Optional[Set[str]] = None) -> None:
        self._competitors: Dict[str, CompetitorProfile] = {}
        self._gaps: List[CompetitiveGap] = []
        self._rd_backlog: List[RDBacklogItem] = []
        self._strategies: List[CompetitiveResponseStrategy] = []
        self._our_capabilities = our_capabilities or set(_MURPHY_CAPABILITIES)
        self._lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Competitor management
    # ------------------------------------------------------------------

    def register_competitor(
        self,
        name: str,
        website: str = "",
        products: Optional[List[str]] = None,
        pricing: Optional[Dict[str, str]] = None,
        target_markets: Optional[List[str]] = None,
        sales_channels: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        key_features: Optional[List[str]] = None,
        estimated_market_share: float = 0.0,
        notes: str = "",
    ) -> CompetitorProfile:
        """Register a competitor profile."""
        profile = CompetitorProfile(
            competitor_id=f"comp-{uuid.uuid4().hex[:8]}",
            name=name,
            website=website,
            products=products or [],
            pricing=pricing or {},
            target_markets=target_markets or [],
            sales_channels=sales_channels or [],
            strengths=strengths or [],
            weaknesses=weaknesses or [],
            key_features=key_features or [],
            estimated_market_share=estimated_market_share,
            notes=notes,
        )
        with self._lock:
            self._competitors[profile.competitor_id] = profile
            self._log_event("competitor_registered", {
                "competitor_id": profile.competitor_id,
                "name": name,
            })
        return profile

    def load_default_landscape(self) -> int:
        """Load the default competitor landscape."""
        count = 0
        for comp_data in _DEFAULT_COMPETITORS:
            self.register_competitor(**comp_data)
            count += 1
        return count

    def get_competitor(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            c = self._competitors.get(competitor_id)
            return c.to_dict() if c else None

    def list_competitors(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_dict() for c in self._competitors.values()]

    # ------------------------------------------------------------------
    # Competitive landscape analysis
    # ------------------------------------------------------------------

    def analyze_landscape(self) -> Dict[str, Any]:
        """Analyze the full competitive landscape.

        Returns a positioning matrix showing where Murphy is stronger,
        where competitors are stronger, and where there are gaps.
        """
        with self._lock:
            competitors = list(self._competitors.values())

        if not competitors:
            return {"error": "No competitors registered"}

        # Collect all competitor features into a set
        all_competitor_features: Set[str] = set()
        for c in competitors:
            all_competitor_features.update(c.key_features)
            all_competitor_features.update(c.strengths)

        # Features we have that no competitor has
        our_unique = self._our_capabilities - all_competitor_features

        # Features competitors have that we don't
        their_unique = all_competitor_features - self._our_capabilities

        # Shared features
        shared = self._our_capabilities & all_competitor_features

        # Per-competitor threat assessment
        threat_matrix: List[Dict[str, Any]] = []
        for c in competitors:
            comp_features = set(c.key_features) | set(c.strengths)
            overlap = self._our_capabilities & comp_features
            they_have_we_dont = comp_features - self._our_capabilities
            we_have_they_dont = self._our_capabilities - comp_features

            threat = CompetitorThreatLevel.LOW
            if c.estimated_market_share > 0.15:
                threat = CompetitorThreatLevel.HIGH
            elif c.estimated_market_share > 0.05:
                threat = CompetitorThreatLevel.MEDIUM

            threat_matrix.append({
                "competitor": c.name,
                "competitor_id": c.competitor_id,
                "threat_level": threat.value,
                "market_share": c.estimated_market_share,
                "overlap_count": len(overlap),
                "they_have_we_dont": sorted(they_have_we_dont),
                "we_have_they_dont": sorted(we_have_they_dont),
                "their_weaknesses": c.weaknesses,
                "their_target_markets": c.target_markets,
                "their_sales_channels": c.sales_channels,
            })

        analysis = {
            "competitor_count": len(competitors),
            "our_unique_capabilities": sorted(our_unique),
            "competitor_only_features": sorted(their_unique),
            "shared_features": sorted(shared),
            "murphy_capability_count": len(self._our_capabilities),
            "threat_matrix": threat_matrix,
        }

        self._log_event("landscape_analyzed", {
            "competitors": len(competitors),
            "our_unique": len(our_unique),
            "gaps_found": len(their_unique),
        })

        return analysis

    # ------------------------------------------------------------------
    # Capability gap detection + R&D routing
    # ------------------------------------------------------------------

    def detect_gaps(self) -> List[CompetitiveGap]:
        """Detect capabilities that competitors have but we don't.

        Groups gaps by how many competitors offer the feature and
        assigns suggested priority based on competitive pressure.
        """
        with self._lock:
            competitors = list(self._competitors.values())

        # Map feature → list of competitors who have it
        feature_owners: Dict[str, List[str]] = {}
        for c in competitors:
            all_features = set(c.key_features) | set(c.strengths)
            for feat in all_features:
                if feat not in self._our_capabilities:
                    feature_owners.setdefault(feat, []).append(c.name)

        gaps: List[CompetitiveGap] = []
        for feature, owners in feature_owners.items():
            owner_count = len(owners)
            if owner_count >= 3:
                demand = "high"
                priority = RDPriority.CRITICAL
            elif owner_count >= 2:
                demand = "medium"
                priority = RDPriority.HIGH
            else:
                demand = "low"
                priority = RDPriority.MEDIUM

            gap = CompetitiveGap(
                gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                feature=feature,
                competitors_with_feature=owners,
                customer_demand=demand,
                impact_description=(
                    f"{owner_count} competitor(s) offer '{feature}' — "
                    f"{'high' if owner_count >= 3 else 'moderate'} competitive pressure"
                ),
                suggested_priority=priority,
            )
            gaps.append(gap)

        with self._lock:
            self._gaps = gaps

        self._log_event("gaps_detected", {"gap_count": len(gaps)})
        return gaps

    def route_gaps_to_rd(self) -> List[RDBacklogItem]:
        """Convert detected gaps into R&D backlog items.

        Each gap becomes an R&D item with priority, description,
        competitors driving the need, and projected impact.
        """
        if not self._gaps:
            self.detect_gaps()

        new_items: List[RDBacklogItem] = []
        with self._lock:
            existing_gap_ids = {
                item.source_gap_id for item in self._rd_backlog
                if item.source_gap_id
            }

        for gap in self._gaps:
            if gap.gap_id in existing_gap_ids:
                continue

            # Determine target tier based on feature type
            target_tier = self._infer_target_tier(gap.feature)

            # Estimate effort
            effort = "medium"
            if gap.suggested_priority == RDPriority.CRITICAL:
                effort = "large"
            elif gap.suggested_priority == RDPriority.LOW:
                effort = "small"

            item = RDBacklogItem(
                item_id=f"rd-{uuid.uuid4().hex[:8]}",
                title=f"Build: {gap.feature}",
                description=(
                    f"Competitive gap: {gap.impact_description}. "
                    f"Competitors with this: {', '.join(gap.competitors_with_feature)}. "
                    f"Customer demand: {gap.customer_demand}."
                ),
                source_gap_id=gap.gap_id,
                priority=gap.suggested_priority,
                competitors_driving=list(gap.competitors_with_feature),
                projected_impact=(
                    f"Closing this gap improves competitiveness against "
                    f"{len(gap.competitors_with_feature)} competitor(s) "
                    f"in the {target_tier} tier."
                ),
                target_tier=target_tier,
                estimated_effort=effort,
            )
            new_items.append(item)

        with self._lock:
            for item in new_items:
                capped_append(self._rd_backlog, item, max_size=500)

        self._log_event("gaps_routed_to_rd", {
            "new_items": len(new_items),
            "total_backlog": len(self._rd_backlog),
        })
        return new_items

    def get_rd_backlog(
        self,
        priority: Optional[RDPriority] = None,
        status: Optional[RDStatus] = None,
    ) -> List[Dict[str, Any]]:
        """Get R&D backlog items, optionally filtered."""
        with self._lock:
            items = list(self._rd_backlog)
        if priority:
            items = [i for i in items if i.priority == priority]
        if status:
            items = [i for i in items if i.status == status]
        return [i.to_dict() for i in items]

    def advance_rd_item(self, item_id: str, new_status: RDStatus) -> Optional[Dict[str, Any]]:
        """Update the status of an R&D backlog item."""
        with self._lock:
            for item in self._rd_backlog:
                if item.item_id == item_id:
                    item.status = new_status
                    self._log_event("rd_item_advanced", {
                        "item_id": item_id,
                        "new_status": new_status.value,
                    })
                    return item.to_dict()
        return None

    # ------------------------------------------------------------------
    # Competitive response strategies
    # ------------------------------------------------------------------

    def generate_competitive_strategies(self) -> List[CompetitiveResponseStrategy]:
        """Generate adversarial marketing strategies against each competitor.

        For each competitor, identify:
          - Our advantages to highlight
          - Their weaknesses to exploit
          - Which of their customers to target
          - What messaging and channels to use
        """
        with self._lock:
            competitors = list(self._competitors.values())

        strategies: List[CompetitiveResponseStrategy] = []

        for comp in competitors:
            comp_features = set(comp.key_features) | set(comp.strengths)
            we_have_they_dont = sorted(self._our_capabilities - comp_features)

            # Determine which Murphy tier best competes with their offering
            rec_tier = self._recommend_tier_against(comp)

            # Build targeted messaging
            messaging = self._build_competitive_messaging(comp, we_have_they_dont, rec_tier)

            # Recommend channels to reach their customers
            channels = self._recommend_channels_against(comp)

            strategy = CompetitiveResponseStrategy(
                strategy_id=f"strat-{uuid.uuid4().hex[:8]}",
                competitor_id=comp.competitor_id,
                competitor_name=comp.name,
                our_advantages=we_have_they_dont[:5],  # Top 5
                their_weaknesses_to_exploit=comp.weaknesses[:5],
                target_segments=comp.target_markets,
                messaging=messaging,
                recommended_channels=channels,
                recommended_tier=rec_tier,
            )
            strategies.append(strategy)

        with self._lock:
            self._strategies = strategies

        self._log_event("strategies_generated", {
            "count": len(strategies),
        })
        return strategies

    # ------------------------------------------------------------------
    # Full competitive analysis (main entry point)
    # ------------------------------------------------------------------

    def full_competitive_analysis(self) -> Dict[str, Any]:
        """Run the complete adversarial marketing analysis.

        1. Analyze landscape
        2. Detect capability gaps
        3. Route gaps to R&D
        4. Generate competitive strategies

        Returns a comprehensive report.
        """
        landscape = self.analyze_landscape()
        gaps = self.detect_gaps()
        rd_items = self.route_gaps_to_rd()
        strategies = self.generate_competitive_strategies()

        critical_gaps = [g for g in gaps if g.suggested_priority == RDPriority.CRITICAL]
        high_gaps = [g for g in gaps if g.suggested_priority == RDPriority.HIGH]

        report = {
            "report_id": f"ci-{uuid.uuid4().hex[:8]}",
            "landscape": landscape,
            "gaps": {
                "total": len(gaps),
                "critical": len(critical_gaps),
                "high": len(high_gaps),
                "items": [g.to_dict() for g in gaps],
            },
            "rd_backlog": {
                "new_items_routed": len(rd_items),
                "total_backlog_size": len(self._rd_backlog),
                "items": [i.to_dict() for i in rd_items],
            },
            "competitive_strategies": [s.to_dict() for s in strategies],
            "summary": {
                "competitors_analyzed": landscape.get("competitor_count", 0),
                "our_unique_advantages": len(landscape.get("our_unique_capabilities", [])),
                "capability_gaps": len(gaps),
                "rd_items_created": len(rd_items),
                "strategies_generated": len(strategies),
                "recommendation": (
                    f"Focus on {len(critical_gaps)} critical gaps and "
                    f"leverage {len(landscape.get('our_unique_capabilities', []))} "
                    f"unique capabilities for differentiation."
                ),
            },
        }

        self._log_event("full_analysis_completed", report["summary"])
        return report

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "competitors": len(self._competitors),
                "gaps_detected": len(self._gaps),
                "rd_backlog_size": len(self._rd_backlog),
                "strategies_generated": len(self._strategies),
                "event_log_count": len(self._event_log),
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _infer_target_tier(self, feature: str) -> str:
        """Infer which Murphy tier a feature gap would benefit most."""
        enterprise_keywords = {
            "enterprise", "rpa", "process_mining", "governance",
            "compliance", "attended", "unattended", "partner_ecosystem",
            "copilot", "microsoft",
        }
        creator_keywords = {
            "content", "creator", "streaming", "social", "fan",
            "monetization", "moderation",
        }
        lower = feature.lower()
        if any(kw in lower for kw in enterprise_keywords):
            return "enterprise"
        if any(kw in lower for kw in creator_keywords):
            return "creator_pro"
        return "pro"

    def _recommend_tier_against(self, comp: CompetitorProfile) -> str:
        """Recommend which Murphy tier best competes against a competitor."""
        # If they target enterprise, we compete with Enterprise
        enterprise_markets = {"enterprise_it", "fortune_500", "financial_services", "healthcare", "government", "microsoft_365_users"}
        creator_markets = {"content_creators", "onlyfans_operators", "twitch_streamers", "youtubers"}

        comp_markets = set(comp.target_markets)
        if comp_markets & enterprise_markets:
            return "enterprise"
        if comp_markets & creator_markets:
            return "creator_starter"
        return "pro"

    def _build_competitive_messaging(
        self,
        comp: CompetitorProfile,
        our_advantages: List[str],
        rec_tier: str,
    ) -> str:
        """Build adversarial messaging positioning Murphy against competitor."""
        price = _MURPHY_PRICING.get(rec_tier, "$299/mo")
        advantages_text = ", ".join(our_advantages[:3]) if our_advantages else "comprehensive automation"
        weaknesses_text = ", ".join(comp.weaknesses[:2]) if comp.weaknesses else "limited scope"

        return (
            f"Unlike {comp.name}, Murphy offers {advantages_text} "
            f"with {price} transparent pricing. "
            f"While {comp.name} struggles with {weaknesses_text}, "
            f"Murphy delivers enterprise-grade governance, safety-first "
            f"architecture, and 75+ connectors from day one."
        )

    def _recommend_channels_against(self, comp: CompetitorProfile) -> List[str]:
        """Recommend marketing channels to win competitor's customers."""
        # Mirror their channels + add our unique ones
        base_channels = ["comparison_landing_page", "competitor_keyword_seo"]
        if "content_marketing" in comp.sales_channels or "seo" in comp.sales_channels:
            base_channels.append("blog_comparison_posts")
        if "enterprise_sales_team" in comp.sales_channels or "partner_network" in comp.sales_channels:
            base_channels.append("direct_outbound_sales")
        if "freemium_funnel" in comp.sales_channels or "open_source_community" in comp.sales_channels:
            base_channels.append("open_source_community_engagement")
        # Always include review sites
        base_channels.append("g2_capterra_reviews")
        return base_channels

    def _log_event(self, action: str, details: Dict[str, Any]) -> None:
        event = {
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._event_log, event, max_size=10_000)
        logger.info("CompetitiveIntel: %s", action)
