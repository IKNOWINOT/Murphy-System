"""
Tests for BIZ-002: UnitEconomicsAnalyzer.

Validates:
  - Per-tier cost profile calculations
  - Tier economics (revenue, cost, margin, viability)
  - Scale projections at 100 / 1K / 10K / 100K customers
  - Breakeven customer calculation
  - Cost escalation alerts
  - Full analysis report
  - CRO routing for unit economics queries

Design Label: TEST-006 / BIZ-002
Owner: QA Team
"""

import pytest

from src.unit_economics_analyzer import (
    ProcessingCostProfile,
    TierEconomics,
    ScaleProjection,
    UnitEconomicsAnalyzer,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def analyzer():
    """Analyzer with default cost profiles and revenues."""
    return UnitEconomicsAnalyzer()


@pytest.fixture
def custom_analyzer():
    """Analyzer with controlled cost profiles for deterministic tests."""
    costs = {
        "free": ProcessingCostProfile(
            tier="free",
            platform_overhead=0.50,
        ),
        "basic": ProcessingCostProfile(
            tier="basic",
            llm_inference_cost=5.0,
            compute_cost=5.0,
            storage_cost=1.0,
            bandwidth_cost=0.5,
            support_cost=2.0,
            platform_overhead=1.5,
        ),
        "premium": ProcessingCostProfile(
            tier="premium",
            llm_inference_cost=15.0,
            compute_cost=20.0,
            storage_cost=5.0,
            bandwidth_cost=3.0,
            support_cost=10.0,
            platform_overhead=7.0,
        ),
    }
    revenues = {
        "free": 0.0,
        "basic": 49.0,
        "premium": 199.0,
    }
    tier_mix = {
        "free": 0.70,
        "basic": 0.20,
        "premium": 0.10,
    }
    return UnitEconomicsAnalyzer(
        cost_profiles=costs,
        tier_revenues=revenues,
        tier_mix=tier_mix,
    )


# ------------------------------------------------------------------
# ProcessingCostProfile
# ------------------------------------------------------------------

class TestProcessingCostProfile:
    def test_total_cost(self):
        profile = ProcessingCostProfile(
            tier="test",
            llm_inference_cost=10.0,
            compute_cost=5.0,
            storage_cost=2.0,
            bandwidth_cost=1.0,
            support_cost=3.0,
            platform_overhead=1.0,
        )
        assert profile.total_cost == 22.0

    def test_zero_cost(self):
        profile = ProcessingCostProfile(tier="free")
        assert profile.total_cost == 0.0

    def test_to_dict(self):
        profile = ProcessingCostProfile(tier="test", llm_inference_cost=1.5)
        d = profile.to_dict()
        assert d["tier"] == "test"
        assert d["llm_inference_cost"] == 1.5
        assert "total_cost" in d


# ------------------------------------------------------------------
# TierEconomics
# ------------------------------------------------------------------

class TestTierEconomics:
    def test_gross_profit(self):
        profile = ProcessingCostProfile(tier="pro", compute_cost=20.0)
        econ = TierEconomics(tier="pro", monthly_revenue=99.0, cost_profile=profile)
        assert econ.gross_profit == 79.0

    def test_gross_margin(self):
        profile = ProcessingCostProfile(tier="pro", compute_cost=33.0)
        econ = TierEconomics(tier="pro", monthly_revenue=99.0, cost_profile=profile)
        expected_margin = (99.0 - 33.0) / 99.0
        assert abs(econ.gross_margin - expected_margin) < 0.001

    def test_gross_margin_zero_revenue(self):
        profile = ProcessingCostProfile(tier="free", platform_overhead=0.50)
        econ = TierEconomics(tier="free", monthly_revenue=0.0, cost_profile=profile)
        assert econ.gross_margin == 0.0

    def test_is_viable(self):
        # 67% margin — viable
        profile = ProcessingCostProfile(tier="pro", compute_cost=33.0)
        econ = TierEconomics(tier="pro", monthly_revenue=99.0, cost_profile=profile)
        assert econ.is_viable is True

    def test_is_not_viable(self):
        # 10% margin — not viable
        profile = ProcessingCostProfile(tier="bad", compute_cost=90.0)
        econ = TierEconomics(tier="bad", monthly_revenue=100.0, cost_profile=profile)
        assert econ.is_viable is False

    def test_to_dict(self):
        profile = ProcessingCostProfile(tier="pro", compute_cost=20.0)
        econ = TierEconomics(tier="pro", monthly_revenue=99.0, cost_profile=profile)
        d = econ.to_dict()
        assert d["tier"] == "pro"
        assert d["monthly_revenue"] == 99.0
        assert "gross_margin_pct" in d
        assert "is_viable" in d


# ------------------------------------------------------------------
# Scale Projections
# ------------------------------------------------------------------

class TestScaleProjection:
    def test_total_monthly_revenue(self, custom_analyzer):
        proj = custom_analyzer.project_at_scale(1000)
        # 1000 * (0.7*0 + 0.2*49 + 0.1*199) = 1000 * 29.7 = 29700
        assert abs(proj.total_monthly_revenue - 29700.0) < 0.01

    def test_total_monthly_cost(self, custom_analyzer):
        proj = custom_analyzer.project_at_scale(1000)
        # free cost = 0.50, basic cost = 15.0, premium cost = 60.0
        # 1000 * (0.7*0.5 + 0.2*15 + 0.1*60) = 1000 * 9.35 = 9350
        assert abs(proj.total_monthly_cost - 9350.0) < 0.01

    def test_blended_margin(self, custom_analyzer):
        proj = custom_analyzer.project_at_scale(1000)
        # profit = 29700 - 9350 = 20350
        # margin = 20350 / 29700 ≈ 68.52%
        assert proj.blended_margin_pct > 60.0

    def test_to_dict(self, custom_analyzer):
        proj = custom_analyzer.project_at_scale(1000)
        d = proj.to_dict()
        assert d["customer_count"] == 1000
        assert "annual_revenue" in d
        assert "blended_margin_pct" in d


# ------------------------------------------------------------------
# UnitEconomicsAnalyzer
# ------------------------------------------------------------------

class TestUnitEconomicsAnalyzer:
    def test_get_tier_economics(self, analyzer):
        econ = analyzer.get_tier_economics("pro")
        assert econ is not None
        assert econ.tier == "pro"
        assert econ.monthly_revenue == 599.0

    def test_get_tier_economics_missing(self, analyzer):
        econ = analyzer.get_tier_economics("nonexistent")
        assert econ is None

    def test_analyze_all_tiers(self, analyzer):
        all_tiers = analyzer.analyze_all_tiers()
        assert "community" in all_tiers
        assert "pro" in all_tiers
        assert "enterprise" in all_tiers

    def test_pro_tier_is_viable(self, analyzer):
        """Pro tier at $599/mo with ~$32.50 cost should be viable."""
        econ = analyzer.get_tier_economics("pro")
        assert econ is not None
        assert econ.is_viable is True
        assert econ.gross_margin_pct > 40.0

    def test_enterprise_tier_is_viable(self, analyzer):
        """Enterprise at $500/mo with ~$150 cost should be viable."""
        econ = analyzer.get_tier_economics("enterprise")
        assert econ is not None
        assert econ.is_viable is True

    def test_community_tier_is_loss_leader(self, analyzer):
        """Community tier is free — $0 revenue, small overhead cost."""
        econ = analyzer.get_tier_economics("community")
        assert econ is not None
        assert econ.monthly_revenue == 0.0
        assert econ.cost_profile.total_cost > 0.0  # There's always some cost
        assert econ.gross_profit < 0.0  # Expected: loss-leader

    def test_scale_ladder(self, analyzer):
        ladder = analyzer.project_scale_ladder()
        assert len(ladder) == 4
        counts = [p.customer_count for p in ladder]
        assert counts == [100, 1_000, 10_000, 100_000]

    def test_scale_ladder_custom_counts(self, analyzer):
        ladder = analyzer.project_scale_ladder(counts=[500, 5000])
        assert len(ladder) == 2

    def test_breakeven_customers(self, analyzer):
        result = analyzer.breakeven_customers(monthly_fixed_costs=5000.0)
        assert "breakeven_customers" in result
        assert result["breakeven_customers"] is not None
        assert result["breakeven_customers"] > 0

    def test_breakeven_with_zero_margin(self):
        """If all tiers lose money, breakeven should be None."""
        costs = {
            "only": ProcessingCostProfile(tier="only", compute_cost=200.0),
        }
        revenues = {"only": 50.0}  # Losing money
        mix = {"only": 1.0}
        a = UnitEconomicsAnalyzer(
            cost_profiles=costs, tier_revenues=revenues, tier_mix=mix,
        )
        result = a.breakeven_customers()
        assert result["breakeven_customers"] is None

    def test_check_cost_alerts_no_false_flags(self, analyzer):
        """Default config flags creator_starter (low rev-share margin) but not paid tiers like pro/enterprise."""
        alerts = analyzer.check_cost_alerts()
        # Pro and Enterprise should NOT be flagged
        flagged_tiers = {a["tier"] for a in alerts}
        assert "pro" not in flagged_tiers
        assert "enterprise" not in flagged_tiers

    def test_check_cost_alerts_triggered(self):
        """Tier with 10% margin should trigger critical alert."""
        costs = {
            "bad": ProcessingCostProfile(tier="bad", compute_cost=90.0),
        }
        revenues = {"bad": 100.0}
        a = UnitEconomicsAnalyzer(cost_profiles=costs, tier_revenues=revenues)
        alerts = a.check_cost_alerts()
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_full_analysis(self, analyzer):
        report = analyzer.full_analysis()
        assert "report_id" in report
        assert "summary" in report
        assert "tier_economics" in report
        assert "scale_projections" in report
        assert "breakeven" in report
        assert "alerts" in report
        # The creator_starter tier (5% rev-share at $15/mo) has thin margins,
        # so the verdict will flag review needed — this is the correct finding.
        assert "verdict" in report["summary"]

    def test_full_analysis_includes_all_paid_tiers(self, analyzer):
        report = analyzer.full_analysis()
        assert report["summary"]["paid_tier_count"] > 0

    def test_get_status(self, analyzer):
        status = analyzer.get_status()
        assert "configured_tiers" in status
        assert "analyses_run" in status
        assert len(status["configured_tiers"]) >= 3


# ------------------------------------------------------------------
# CRO Routing for unit economics queries
# ------------------------------------------------------------------

class TestCROUnitEconomicsRouting:
    """Ensure cost/margin/unit-economics queries route to CRO."""

    @pytest.fixture()
    def bootstrap(self):
        from src.inoni_org_bootstrap import InoniOrgBootstrap
        b = InoniOrgBootstrap()
        b.bootstrap()
        return b

    def test_route_cost_query(self, bootstrap):
        persona = bootstrap.route_to_agent("What is the cost per customer at scale?")
        assert persona is not None
        assert persona["role"] == "chief_revenue_officer"

    def test_route_pricing_query(self, bootstrap):
        persona = bootstrap.route_to_agent("Does our pricing make sense?")
        assert persona is not None
        assert persona["role"] == "chief_revenue_officer"

    def test_route_margin_query(self, bootstrap):
        persona = bootstrap.route_to_agent("What are our margins on the pro tier?")
        assert persona is not None
        assert persona["role"] == "chief_revenue_officer"
