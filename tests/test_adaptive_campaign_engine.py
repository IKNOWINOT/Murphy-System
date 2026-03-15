"""
Tests for MKT-004: AdaptiveCampaignEngine.

Validates:
  - Per-tier campaign bootstrapping
  - Performance snapshot recording
  - Traction evaluation (healthy / low / critical)
  - Automatic campaign adjustment (channel / demographic pivots)
  - Paid-ad proposal generation with HITL founder approval gate
  - Proposal approval and rejection flows
  - evaluate_and_act full-cycle integration
  - Updated pricing: Creator Starter $20/mo, Enterprise Contact us

Design Label: TEST-007 / MKT-004
Owner: QA Team
"""

import pytest

from src.adaptive_campaign_engine import (
    AdaptiveCampaignEngine,
    TierCampaignStatus,
    TractionLevel,
    ProposalStatus,
    TierPerformanceSnapshot,
    CampaignAdjustment,
    PaidAdProposal,
    TierCampaign,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    """Engine with default tier campaigns bootstrapped."""
    e = AdaptiveCampaignEngine()
    e.bootstrap_tier_campaigns()
    return e


@pytest.fixture
def bare_engine():
    """Engine with no campaigns bootstrapped."""
    return AdaptiveCampaignEngine()


# ------------------------------------------------------------------
# Bootstrap
# ------------------------------------------------------------------

class TestBootstrap:
    def test_bootstrap_creates_all_tiers(self, engine):
        campaigns = engine.get_all_campaigns()
        assert "community" in campaigns
        assert "pro" in campaigns
        assert "enterprise" in campaigns
        assert "creator_starter" in campaigns
        assert "creator_pro" in campaigns

    def test_bootstrap_sets_channels(self, engine):
        c = engine.get_campaign("pro")
        assert c is not None
        assert len(c["channels"]) > 0

    def test_bootstrap_sets_demographics(self, engine):
        c = engine.get_campaign("enterprise")
        assert c is not None
        assert len(c["demographics"]) > 0

    def test_bootstrap_idempotent(self, engine):
        """Calling bootstrap twice doesn't create duplicate campaigns."""
        engine.bootstrap_tier_campaigns()
        assert engine.get_status()["tier_campaign_count"] == 5

    def test_bootstrap_subset(self, bare_engine):
        bare_engine.bootstrap_tier_campaigns(tiers=["pro", "enterprise"])
        assert bare_engine.get_status()["tier_campaign_count"] == 2

    def test_creator_starter_messaging_contains_20(self, engine):
        """Creator Starter campaigns should reference $20/mo pricing."""
        c = engine.get_campaign("creator_starter")
        assert "$20/mo" in c["messaging"]

    def test_enterprise_messaging_contains_contact(self, engine):
        """Enterprise campaigns should reference 'Contact us' pricing."""
        c = engine.get_campaign("enterprise")
        assert "Contact us" in c["messaging"]


# ------------------------------------------------------------------
# Performance Snapshots
# ------------------------------------------------------------------

class TestSnapshots:
    def test_record_snapshot(self, engine):
        snap = engine.record_snapshot("pro", "2026-W09", impressions=1000, leads=50, conversions=5)
        assert snap is not None
        assert snap.impressions == 1000
        assert snap.leads == 50
        assert snap.conversions == 5

    def test_record_snapshot_unknown_tier(self, engine):
        snap = engine.record_snapshot("nonexistent", "2026-W09", impressions=100)
        assert snap is None

    def test_conversion_rate(self):
        snap = TierPerformanceSnapshot(period="test", leads=100, conversions=5)
        assert abs(snap.conversion_rate - 0.05) < 0.001

    def test_conversion_rate_zero_leads(self):
        snap = TierPerformanceSnapshot(period="test", leads=0, conversions=0)
        assert snap.conversion_rate == 0.0

    def test_lead_rate(self):
        snap = TierPerformanceSnapshot(period="test", impressions=1000, leads=50)
        assert abs(snap.lead_rate - 0.05) < 0.001


# ------------------------------------------------------------------
# Traction Evaluation
# ------------------------------------------------------------------

class TestTractionEvaluation:
    def test_healthy_traction(self, engine):
        # 5% conversion = healthy
        engine.record_snapshot("pro", "W1", impressions=1000, leads=100, conversions=5)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=100, conversions=4)
        result = engine.evaluate_traction("pro")
        assert result["traction"] == TractionLevel.HEALTHY.value
        assert result["action"] == "maintain"

    def test_low_traction(self, engine):
        # 2% conversion = low
        engine.record_snapshot("pro", "W1", impressions=1000, leads=100, conversions=2)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=100, conversions=2)
        result = engine.evaluate_traction("pro")
        assert result["traction"] == TractionLevel.LOW.value
        assert result["action"] == "adjust_campaign"

    def test_critical_traction(self, engine):
        # 0.5% conversion = critical
        engine.record_snapshot("pro", "W1", impressions=1000, leads=200, conversions=1)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=200, conversions=1)
        result = engine.evaluate_traction("pro")
        assert result["traction"] == TractionLevel.CRITICAL.value

    def test_critical_after_max_adjustments_proposes_paid(self, engine):
        # Exhaust organic adjustments
        for _ in range(3):
            engine.adjust_campaign("pro")
        # Now record critical traction
        engine.record_snapshot("pro", "W1", impressions=1000, leads=200, conversions=1)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=200, conversions=1)
        result = engine.evaluate_traction("pro")
        assert result["action"] == "propose_paid_ads"

    def test_no_data_returns_awaiting(self, engine):
        result = engine.evaluate_traction("pro")
        assert result["action"] == "awaiting_data"

    def test_unknown_tier(self, engine):
        result = engine.evaluate_traction("nonexistent")
        assert result is None


# ------------------------------------------------------------------
# Campaign Adjustment
# ------------------------------------------------------------------

class TestCampaignAdjustment:
    def test_adjust_changes_channels(self, engine):
        old = engine.get_campaign("pro")
        old_channels = old["channels"]
        adj = engine.adjust_campaign("pro")
        assert adj is not None
        assert adj.old_channels == old_channels
        assert adj.new_channels != old_channels

    def test_adjust_changes_demographics(self, engine):
        adj = engine.adjust_campaign("enterprise")
        assert adj is not None
        assert len(adj.new_demographics) > 0

    def test_adjust_sets_status_adjusting(self, engine):
        engine.adjust_campaign("pro")
        c = engine.get_campaign("pro")
        assert c["status"] == TierCampaignStatus.ADJUSTING.value

    def test_adjust_preserves_first_channel(self, engine):
        old = engine.get_campaign("pro")
        first = old["channels"][0]
        adj = engine.adjust_campaign("pro")
        assert first in adj.new_channels

    def test_adjust_unknown_tier(self, engine):
        adj = engine.adjust_campaign("nonexistent")
        assert adj is None

    def test_multiple_adjustments_tracked(self, engine):
        engine.adjust_campaign("pro")
        engine.adjust_campaign("pro")
        c = engine.get_campaign("pro")
        assert c["adjustment_count"] == 2


# ------------------------------------------------------------------
# Paid Ad Proposals (HITL-gated)
# ------------------------------------------------------------------

class TestPaidAdProposals:
    def test_propose_creates_proposal(self, engine):
        # Record some data first
        engine.record_snapshot("pro", "W1", impressions=1000, leads=100, conversions=1)
        proposal = engine.propose_paid_campaign("pro", 2000.0)
        assert proposal is not None
        assert proposal.status == ProposalStatus.PENDING
        assert proposal.proposed_budget_usd == 2000.0

    def test_proposal_requires_founder_approval(self, engine):
        """Proposals must be PENDING — no auto-approval."""
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        proposal = engine.propose_paid_campaign("pro", 5000.0)
        assert proposal.status == ProposalStatus.PENDING
        assert proposal.approved_by is None

    def test_proposal_includes_strategy(self, engine):
        engine.record_snapshot("enterprise", "W1", impressions=500, leads=20, conversions=0)
        proposal = engine.propose_paid_campaign("enterprise", 5000.0)
        assert "STRATEGY" in proposal.market_strategy
        assert "founder approval" in proposal.market_strategy.lower()

    def test_proposal_includes_rationale(self, engine):
        engine.record_snapshot("pro", "W1", impressions=2000, leads=100, conversions=2)
        proposal = engine.propose_paid_campaign("pro", 2000.0)
        assert "organic" in proposal.rationale.lower() or "paid" in proposal.rationale.lower()

    def test_approve_proposal(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        proposal = engine.propose_paid_campaign("pro", 2000.0)
        result = engine.approve_proposal("pro", proposal.proposal_id, "corey_post_founder")
        assert result is not None
        assert result.status == ProposalStatus.APPROVED
        assert result.approved_by == "corey_post_founder"
        assert result.approved_at is not None

    def test_reject_proposal(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        proposal = engine.propose_paid_campaign("pro", 2000.0)
        result = engine.reject_proposal("pro", proposal.proposal_id, "Budget too high")
        assert result is not None
        assert result.status == ProposalStatus.REJECTED
        assert result.rejection_reason == "Budget too high"

    def test_approve_nonexistent_proposal(self, engine):
        result = engine.approve_proposal("pro", "fake-id", "founder")
        assert result is None

    def test_get_pending_approvals(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        engine.propose_paid_campaign("pro", 2000.0)
        engine.record_snapshot("enterprise", "W1", impressions=500, leads=20, conversions=0)
        engine.propose_paid_campaign("enterprise", 5000.0)
        pending = engine.get_pending_approvals()
        assert len(pending) == 2
        assert all(p["status"] == "pending" for p in pending)

    def test_proposal_projected_roi(self, engine):
        engine.record_snapshot("enterprise", "W1", impressions=500, leads=20, conversions=2)
        proposal = engine.propose_paid_campaign("enterprise", 5000.0)
        # Enterprise = custom pricing (750 baseline) * 12 = $9000/year per conversion
        assert proposal.projected_roi > 0

    def test_campaign_status_pending_after_proposal(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        engine.propose_paid_campaign("pro", 2000.0)
        c = engine.get_campaign("pro")
        assert c["status"] == TierCampaignStatus.PENDING_APPROVAL.value

    def test_campaign_status_active_after_approval(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=50, conversions=1)
        proposal = engine.propose_paid_campaign("pro", 2000.0)
        engine.approve_proposal("pro", proposal.proposal_id, "founder")
        c = engine.get_campaign("pro")
        assert c["status"] == TierCampaignStatus.ACTIVE.value


# ------------------------------------------------------------------
# Evaluate and Act (full cycle)
# ------------------------------------------------------------------

class TestEvaluateAndAct:
    def test_healthy_tiers_maintained(self, engine):
        # All tiers healthy — no adjustments
        for tier in ["pro", "enterprise", "creator_starter", "creator_pro"]:
            engine.record_snapshot(tier, "W1", impressions=1000, leads=100, conversions=5)
            engine.record_snapshot(tier, "W2", impressions=1000, leads=100, conversions=4)
        results = engine.evaluate_and_act()
        for tier in ["pro", "enterprise"]:
            assert results[tier]["evaluation"]["action"] == "maintain"
            assert "adjustment" not in results[tier]

    def test_low_traction_triggers_adjustment(self, engine):
        engine.record_snapshot("pro", "W1", impressions=1000, leads=100, conversions=1)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=100, conversions=1)
        results = engine.evaluate_and_act()
        assert results["pro"]["evaluation"]["action"] == "adjust_campaign"
        assert results["pro"]["adjustment"] is not None

    def test_critical_after_exhaustion_triggers_proposal(self, engine):
        # Exhaust organic adjustments
        for _ in range(3):
            engine.adjust_campaign("pro")
        # Critical traction
        engine.record_snapshot("pro", "W1", impressions=1000, leads=200, conversions=0)
        engine.record_snapshot("pro", "W2", impressions=1000, leads=200, conversions=0)
        results = engine.evaluate_and_act()
        assert results["pro"]["evaluation"]["action"] == "propose_paid_ads"
        assert results["pro"]["proposal"] is not None
        assert results["pro"]["proposal"]["status"] == "pending"


# ------------------------------------------------------------------
# Status and Queries
# ------------------------------------------------------------------

class TestStatus:
    def test_get_status(self, engine):
        status = engine.get_status()
        assert status["tier_campaign_count"] == 5
        assert status["total_adjustments"] == 0
        assert status["total_proposals"] == 0

    def test_event_log_grows(self, engine):
        # Bootstrap already logged events
        status = engine.get_status()
        assert status["event_log_count"] >= 5  # One per tier bootstrap

    def test_get_all_campaigns(self, engine):
        all_c = engine.get_all_campaigns()
        assert len(all_c) == 5
        for tier, data in all_c.items():
            assert "channels" in data
            assert "demographics" in data


# ------------------------------------------------------------------
# Updated Pricing Tests (Creator Starter $20/mo, Enterprise Contact us)
# ------------------------------------------------------------------

class TestUpdatedPricing:
    def test_creator_starter_revenue_20(self):
        """Unit economics analyzer reflects $20/mo creator starter."""
        from src.unit_economics_analyzer import UnitEconomicsAnalyzer
        a = UnitEconomicsAnalyzer()
        econ = a.get_tier_economics("creator_starter")
        assert econ is not None
        assert econ.monthly_revenue == 20.0

    def test_enterprise_revenue_750(self):
        """Unit economics analyzer uses 750 baseline for enterprise modeling."""
        from src.unit_economics_analyzer import UnitEconomicsAnalyzer
        a = UnitEconomicsAnalyzer()
        econ = a.get_tier_economics("enterprise")
        assert econ is not None
        assert econ.monthly_revenue == 750.0

    def test_creator_starter_now_viable(self):
        """At $20/mo with $14 cost, creator_starter has ~30% margin — improved from 6.67%."""
        from src.unit_economics_analyzer import UnitEconomicsAnalyzer
        a = UnitEconomicsAnalyzer()
        econ = a.get_tier_economics("creator_starter")
        assert econ is not None
        assert econ.gross_margin_pct > 25.0  # 30% at $20 vs $14

    def test_enterprise_margin_improved(self):
        """At 750 baseline with $150 cost, enterprise has 80% margin."""
        from src.unit_economics_analyzer import UnitEconomicsAnalyzer
        a = UnitEconomicsAnalyzer()
        econ = a.get_tier_economics("enterprise")
        assert econ is not None
        assert econ.gross_margin_pct > 75.0

    def test_community_budget_from_paid_income(self):
        """Community free tier budgeted from total paid income."""
        from src.unit_economics_analyzer import UnitEconomicsAnalyzer
        a = UnitEconomicsAnalyzer()
        budget = a.community_free_budget(paid_customer_count=1000)
        assert budget["max_free_users"] > 0
        assert budget["monthly_community_budget"] > 0
        assert budget["reinvest_pct"] == 0.10
