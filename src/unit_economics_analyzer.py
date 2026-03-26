"""
Unit Economics Analyzer — Cost vs. Revenue Viability at Scale

Design Label: BIZ-002 — Unit Economics & Scale Viability Analysis
Owner: Finance / CRO (Chief Revenue Officer)
Dependencies:
  - LLMController model cost data
  - Pricing tier definitions from sales_automation and inoni_org_bootstrap

Answers the question: "Do our offerings make sense for the cost of
processing and what we provide back at scale?"

Computes:
  1. Per-customer processing cost (LLM tokens, compute, storage, support)
  2. Revenue per tier (Free, Solo $99/mo, Business $299/mo, Enterprise custom pricing, Creator Starter $20/mo)
  3. Gross margin per tier
  4. Breakeven customer counts
  5. Scale projections (100 / 1K / 10K / 100K customers)
  6. Blended margin across a realistic tier mix
  7. Cost escalation alerts when margins drop below thresholds

All monetary values are in USD unless stated otherwise.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
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
# Cost Components — what it costs us to serve one customer per month
# ---------------------------------------------------------------------------

@dataclass
class ProcessingCostProfile:
    """Monthly processing cost to serve a single customer at a given tier.

    All values in USD/month.
    """

    tier: str
    llm_inference_cost: float = 0.0     # LLM API calls (DeepInfra primary / Together AI overflow)
    compute_cost: float = 0.0           # CPU/GPU time for pipelines
    storage_cost: float = 0.0           # Persistent storage, logs, artifacts
    bandwidth_cost: float = 0.0         # Egress, API calls, webhooks
    support_cost: float = 0.0           # Human/AI support allocation
    platform_overhead: float = 0.0      # CI/CD, monitoring, infra fixed share

    @property
    def total_cost(self) -> float:
        """Total monthly cost to serve one customer."""
        return (
            self.llm_inference_cost
            + self.compute_cost
            + self.storage_cost
            + self.bandwidth_cost
            + self.support_cost
            + self.platform_overhead
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "llm_inference_cost": round(self.llm_inference_cost, 4),
            "compute_cost": round(self.compute_cost, 4),
            "storage_cost": round(self.storage_cost, 4),
            "bandwidth_cost": round(self.bandwidth_cost, 4),
            "support_cost": round(self.support_cost, 4),
            "platform_overhead": round(self.platform_overhead, 4),
            "total_cost": round(self.total_cost, 4),
        }


# ---------------------------------------------------------------------------
# Tier Economics — revenue and margin per tier
# ---------------------------------------------------------------------------

@dataclass
class TierEconomics:
    """Revenue vs. cost analysis for a single pricing tier."""

    tier: str
    monthly_revenue: float              # What we charge per customer/month
    cost_profile: ProcessingCostProfile
    description: str = ""

    @property
    def gross_profit(self) -> float:
        """Gross profit per customer per month."""
        return self.monthly_revenue - self.cost_profile.total_cost

    @property
    def gross_margin(self) -> float:
        """Gross margin as a fraction (0.0–1.0). Returns 0 if revenue is 0."""
        if self.monthly_revenue <= 0:
            return 0.0
        return self.gross_profit / self.monthly_revenue

    @property
    def gross_margin_pct(self) -> float:
        """Gross margin as a percentage."""
        return round(self.gross_margin * 100, 2)

    @property
    def is_viable(self) -> bool:
        """A tier is viable when gross margin ≥ 40%."""
        return self.gross_margin >= 0.40

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "description": self.description,
            "monthly_revenue": round(self.monthly_revenue, 2),
            "monthly_cost": round(self.cost_profile.total_cost, 4),
            "gross_profit": round(self.gross_profit, 4),
            "gross_margin_pct": self.gross_margin_pct,
            "is_viable": self.is_viable,
            "cost_breakdown": self.cost_profile.to_dict(),
        }


# ---------------------------------------------------------------------------
# Scale Projection — how costs and margins change with customer count
# ---------------------------------------------------------------------------

@dataclass
class ScaleProjection:
    """Aggregate economics at a given customer count."""

    customer_count: int
    tier_mix: Dict[str, float]   # tier → fraction of customers (sums to 1.0)
    tier_economics: Dict[str, TierEconomics]

    @property
    def total_monthly_revenue(self) -> float:
        total = 0.0
        for tier, frac in self.tier_mix.items():
            econ = self.tier_economics.get(tier)
            if econ:
                total += econ.monthly_revenue * (self.customer_count * frac)
        return total

    @property
    def total_monthly_cost(self) -> float:
        total = 0.0
        for tier, frac in self.tier_mix.items():
            econ = self.tier_economics.get(tier)
            if econ:
                total += econ.cost_profile.total_cost * (self.customer_count * frac)
        return total

    @property
    def total_gross_profit(self) -> float:
        return self.total_monthly_revenue - self.total_monthly_cost

    @property
    def blended_margin(self) -> float:
        if self.total_monthly_revenue <= 0:
            return 0.0
        return self.total_gross_profit / self.total_monthly_revenue

    @property
    def blended_margin_pct(self) -> float:
        return round(self.blended_margin * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_count": self.customer_count,
            "tier_mix": {k: round(v, 4) for k, v in self.tier_mix.items()},
            "total_monthly_revenue": round(self.total_monthly_revenue, 2),
            "total_monthly_cost": round(self.total_monthly_cost, 2),
            "total_gross_profit": round(self.total_gross_profit, 2),
            "blended_margin_pct": self.blended_margin_pct,
            "annual_revenue": round(self.total_monthly_revenue * 12, 2),
            "annual_profit": round(self.total_gross_profit * 12, 2),
        }


# ---------------------------------------------------------------------------
# Unit Economics Analyzer
# ---------------------------------------------------------------------------

# Realistic default cost profiles based on the Murphy System's LLM costs
# DeepInfra (primary, ~80% of calls):
#   - Llama 3.1 70B: $0.00059/1k tokens
#   - Mixtral 8x7B:  $0.00024/1k tokens
# Together AI (overflow, ~20% of calls):
#   - Llama 3.1 70B: $0.00088/1k tokens
# Blended cost ≈ (0.80 × $0.00059) + (0.20 × $0.00088) = $0.000648/1k tokens

_DEFAULT_COST_PROFILES: Dict[str, ProcessingCostProfile] = {
    "community": ProcessingCostProfile(
        tier="community",
        llm_inference_cost=0.0,     # Self-hosted / no cloud LLM usage
        compute_cost=0.0,           # Self-hosted
        storage_cost=0.0,           # Self-hosted
        bandwidth_cost=0.0,         # Open source download only
        support_cost=0.0,           # Community support only
        platform_overhead=0.50,     # Docs, CI, GitHub Actions share
    ),
    "pro": ProcessingCostProfile(
        tier="pro",
        llm_inference_cost=8.50,    # ~14K 1k-token calls/mo at blended $0.000648 (DeepInfra 80% + Together 20%)
        compute_cost=12.00,         # Managed cloud compute share
        storage_cost=2.50,          # Logs, artifacts, config
        bandwidth_cost=1.50,        # API egress, webhooks
        support_cost=5.00,          # Priority support allocation
        platform_overhead=3.00,     # Monitoring, CI, infra share
    ),
    "enterprise": ProcessingCostProfile(
        tier="enterprise",
        llm_inference_cost=25.00,   # Higher volume, custom models
        compute_cost=40.00,         # Dedicated compute, GPU
        storage_cost=10.00,         # Compliance storage, backups
        bandwidth_cost=5.00,        # On-prem bridge, VPN
        support_cost=50.00,         # Dedicated CSM + SRE share
        platform_overhead=20.00,    # SOC2 audit, dedicated infra
    ),
    "creator_starter": ProcessingCostProfile(
        tier="creator_starter",
        llm_inference_cost=3.00,    # Moderate usage, content workflows
        compute_cost=5.00,          # Shared compute
        storage_cost=1.00,          # Content storage
        bandwidth_cost=1.00,        # API calls
        support_cost=2.00,          # AI-first support
        platform_overhead=2.00,     # Infra share
    ),
    "creator_pro": ProcessingCostProfile(
        tier="creator_pro",
        llm_inference_cost=6.00,    # Higher content gen volume
        compute_cost=8.00,          # More compute
        storage_cost=2.00,          # Media storage
        bandwidth_cost=1.50,        # API + webhook traffic
        support_cost=3.00,          # Priority AI support
        platform_overhead=2.50,     # Infra share
    ),
}

# Default tier revenue assumptions
_DEFAULT_TIER_REVENUES: Dict[str, float] = {
    "community": 0.00,       # Free — budgeted from total paid income
    "solo": 99.00,           # $99/mo per seat
    "pro": 599.00,           # $599/mo per seat (Professional tier)
    "enterprise": 750.00,    # Contact us (custom pricing, 750 used as baseline for modeling)
    "creator_starter": 20.00,  # $20/mo monthly
    "creator_pro": 299.00,   # Direct $299/mo subscription
}

# Realistic tier mix at different scale points
_DEFAULT_TIER_MIX: Dict[str, float] = {
    "community": 0.60,       # 60% free users
    "pro": 0.20,             # 20% pro
    "enterprise": 0.05,      # 5% enterprise
    "creator_starter": 0.10, # 10% creator starter
    "creator_pro": 0.05,     # 5% creator pro
}


class UnitEconomicsAnalyzer:
    """Analyzes whether Murphy System's offerings are economically viable at scale.

    Answers:
      - What does it cost us to serve each tier?
      - What revenue does each tier generate?
      - What is our gross margin per tier?
      - At what customer counts do we break even?
      - Does the blended margin hold at 100 / 1K / 10K / 100K customers?
      - Are there cost escalation risks?
    """

    # Margin threshold: below this we flag a warning
    MARGIN_WARNING_THRESHOLD = 0.40  # 40%
    MARGIN_CRITICAL_THRESHOLD = 0.20  # 20%

    def __init__(
        self,
        cost_profiles: Optional[Dict[str, ProcessingCostProfile]] = None,
        tier_revenues: Optional[Dict[str, float]] = None,
        tier_mix: Optional[Dict[str, float]] = None,
    ) -> None:
        self._cost_profiles = cost_profiles or dict(_DEFAULT_COST_PROFILES)
        self._tier_revenues = tier_revenues or dict(_DEFAULT_TIER_REVENUES)
        self._tier_mix = tier_mix or dict(_DEFAULT_TIER_MIX)
        self._analyses: List[Dict[str, Any]] = []

    # --- Tier-level analysis ---

    def get_tier_economics(self, tier: str) -> Optional[TierEconomics]:
        """Compute economics for a single tier."""
        cost_profile = self._cost_profiles.get(tier)
        revenue = self._tier_revenues.get(tier)
        if cost_profile is None or revenue is None:
            return None
        return TierEconomics(
            tier=tier,
            monthly_revenue=revenue,
            cost_profile=cost_profile,
            description=f"Unit economics for {tier} tier",
        )

    def analyze_all_tiers(self) -> Dict[str, TierEconomics]:
        """Return economics for every configured tier."""
        result: Dict[str, TierEconomics] = {}
        for tier in self._cost_profiles:
            econ = self.get_tier_economics(tier)
            if econ is not None:
                result[tier] = econ
        return result

    # --- Scale projections ---

    def project_at_scale(
        self,
        customer_count: int,
        tier_mix: Optional[Dict[str, float]] = None,
    ) -> ScaleProjection:
        """Project aggregate economics at a given customer count."""
        mix = tier_mix or self._tier_mix
        tier_econ = self.analyze_all_tiers()
        return ScaleProjection(
            customer_count=customer_count,
            tier_mix=mix,
            tier_economics=tier_econ,
        )

    def project_scale_ladder(
        self,
        counts: Optional[List[int]] = None,
        tier_mix: Optional[Dict[str, float]] = None,
    ) -> List[ScaleProjection]:
        """Project economics at multiple scale points."""
        counts = counts or [100, 1_000, 10_000, 100_000]
        return [self.project_at_scale(c, tier_mix) for c in counts]

    # --- Breakeven ---

    def breakeven_customers(
        self,
        monthly_fixed_costs: float = 5_000.0,
        tier_mix: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Compute the number of customers needed to cover fixed costs.

        Args:
            monthly_fixed_costs: Total monthly fixed costs (salaries, infra
                                 baseline, SaaS tools, etc.)
            tier_mix: Customer tier distribution.
        """
        mix = tier_mix or self._tier_mix
        tier_econ = self.analyze_all_tiers()

        # Blended contribution margin per customer
        blended_profit_per_customer = 0.0
        for tier, frac in mix.items():
            econ = tier_econ.get(tier)
            if econ:
                blended_profit_per_customer += frac * econ.gross_profit

        if blended_profit_per_customer <= 0:
            return {
                "breakeven_customers": None,
                "reason": "Blended contribution margin is zero or negative",
                "blended_profit_per_customer": round(blended_profit_per_customer, 4),
                "monthly_fixed_costs": monthly_fixed_costs,
            }

        breakeven = monthly_fixed_costs / blended_profit_per_customer
        return {
            "breakeven_customers": int(breakeven) + 1,  # ceiling
            "blended_profit_per_customer": round(blended_profit_per_customer, 4),
            "monthly_fixed_costs": monthly_fixed_costs,
            "months_to_breakeven_at_100_customers": (
                round(monthly_fixed_costs / (blended_profit_per_customer * 100), 1)
                if blended_profit_per_customer > 0 else None
            ),
        }

    # --- Alerts ---

    def check_cost_alerts(self) -> List[Dict[str, Any]]:
        """Check all tiers for margin alerts."""
        alerts: List[Dict[str, Any]] = []
        for tier, econ in self.analyze_all_tiers().items():
            if econ.monthly_revenue <= 0:
                # Free tier — expected to be loss-leader
                continue
            if econ.gross_margin < self.MARGIN_CRITICAL_THRESHOLD:
                alerts.append({
                    "tier": tier,
                    "severity": "critical",
                    "message": (
                        f"{tier} tier margin {econ.gross_margin_pct}% is below "
                        f"critical threshold ({self.MARGIN_CRITICAL_THRESHOLD * 100}%)"
                    ),
                    "gross_margin_pct": econ.gross_margin_pct,
                })
            elif econ.gross_margin < self.MARGIN_WARNING_THRESHOLD:
                alerts.append({
                    "tier": tier,
                    "severity": "warning",
                    "message": (
                        f"{tier} tier margin {econ.gross_margin_pct}% is below "
                        f"warning threshold ({self.MARGIN_WARNING_THRESHOLD * 100}%)"
                    ),
                    "gross_margin_pct": econ.gross_margin_pct,
                })
        return alerts

    # --- Full analysis report ---

    def full_analysis(
        self,
        monthly_fixed_costs: float = 5_000.0,
    ) -> Dict[str, Any]:
        """Generate a comprehensive unit economics report.

        This is the main entry point that answers: "Do our offerings make
        sense for the cost of processing and what we provide back at scale?"
        """
        tier_econ = self.analyze_all_tiers()
        scale_ladder = self.project_scale_ladder()
        breakeven = self.breakeven_customers(monthly_fixed_costs)
        alerts = self.check_cost_alerts()

        # Determine overall viability
        paid_tiers = {t: e for t, e in tier_econ.items() if e.monthly_revenue > 0}
        all_paid_viable = all(e.is_viable for e in paid_tiers.values())
        blended_at_1k = next(
            (p for p in scale_ladder if p.customer_count == 1_000), None
        )

        # Community free-tier budget at 1K paid customers
        community_budget = self.community_free_budget(paid_customer_count=1_000)

        report = {
            "report_id": f"ue-{uuid.uuid4().hex[:8]}",
            "summary": {
                "all_paid_tiers_viable": all_paid_viable,
                "paid_tier_count": len(paid_tiers),
                "total_tier_count": len(tier_econ),
                "alert_count": len(alerts),
                "blended_margin_at_1k_pct": (
                    blended_at_1k.blended_margin_pct if blended_at_1k else None
                ),
                "breakeven_customers": breakeven.get("breakeven_customers"),
                "community_free_users_at_1k_paid": (
                    community_budget.get("max_free_users")
                ),
                "verdict": (
                    "VIABLE — offerings support healthy margins at scale"
                    if all_paid_viable and (not alerts)
                    else "REVIEW NEEDED — some tiers have margin concerns"
                ),
            },
            "tier_economics": {t: e.to_dict() for t, e in tier_econ.items()},
            "scale_projections": [p.to_dict() for p in scale_ladder],
            "breakeven": breakeven,
            "community_budget": community_budget,
            "alerts": alerts,
            "monthly_fixed_costs": monthly_fixed_costs,
        }

        capped_append(self._analyses, report)
        logger.info(
            "Unit economics analysis complete: %s — %d alerts",
            report["summary"]["verdict"],
            len(alerts),
        )
        return report

    # --- Community free-tier budget ---

    def community_free_budget(
        self,
        paid_customer_count: int,
        tier_mix: Optional[Dict[str, float]] = None,
        reinvest_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """Calculate how many free community users we can sustain.

        The community tier is free.  We fund it by reinvesting a percentage
        of total paid-tier income into a monthly community budget, then
        dividing by per-user community cost.

        Args:
            paid_customer_count: Total number of *paying* customers.
            tier_mix: Distribution of paying customers across paid tiers
                      (community share is ignored; remaining fractions are
                      re-normalised).
            reinvest_pct: Fraction of total paid revenue allocated to the
                          community free pool (default 10%).

        Returns:
            Dict with monthly budget, cost per free user, and max free users.
        """
        mix = tier_mix or self._tier_mix
        tier_econ = self.analyze_all_tiers()

        # Collect only paid tiers and re-normalise their shares
        paid_shares: Dict[str, float] = {}
        for tier, frac in mix.items():
            econ = tier_econ.get(tier)
            if econ and econ.monthly_revenue > 0:
                paid_shares[tier] = frac

        total_share = sum(paid_shares.values())
        if total_share <= 0:
            return {
                "monthly_community_budget": 0.0,
                "community_cost_per_user": 0.0,
                "max_free_users": 0,
                "reinvest_pct": reinvest_pct,
                "paid_customer_count": paid_customer_count,
            }

        # Total monthly revenue from paid customers
        total_paid_revenue = 0.0
        for tier, frac in paid_shares.items():
            normed = frac / total_share
            econ = tier_econ[tier]
            total_paid_revenue += econ.monthly_revenue * (paid_customer_count * normed)

        monthly_budget = total_paid_revenue * reinvest_pct
        community_cost = self._cost_profiles.get("community")
        cost_per_free_user = community_cost.total_cost if community_cost else 0.0

        max_free_users = (
            int(monthly_budget / cost_per_free_user) if cost_per_free_user > 0 else 0
        )

        return {
            "monthly_community_budget": round(monthly_budget, 2),
            "community_cost_per_user": round(cost_per_free_user, 4),
            "max_free_users": max_free_users,
            "reinvest_pct": reinvest_pct,
            "paid_customer_count": paid_customer_count,
            "total_paid_monthly_revenue": round(total_paid_revenue, 2),
        }

    # --- Status ---

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured_tiers": list(self._cost_profiles.keys()),
            "analyses_run": len(self._analyses),
        }
