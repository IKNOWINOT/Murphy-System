"""
Tests for MKT-005: CompetitiveIntelligenceEngine.

Validates:
  - Competitor registration and default landscape loading
  - Competitive landscape analysis (positioning matrix, threat assessment)
  - Capability gap detection (features competitors have that we don't)
  - R&D backlog routing from gaps with priority and impact
  - Competitive response strategy generation (adversarial messaging)
  - Full competitive analysis end-to-end
  - CRO / VP Marketing routing for competitive queries

Design Label: TEST-008 / MKT-005
Owner: QA Team
"""

import pytest

from src.competitive_intelligence_engine import (
    CompetitiveIntelligenceEngine,
    CompetitorProfile,
    CompetitiveGap,
    RDBacklogItem,
    CompetitiveResponseStrategy,
    CompetitorThreatLevel,
    RDPriority,
    RDStatus,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    """Engine with default competitor landscape loaded."""
    e = CompetitiveIntelligenceEngine()
    e.load_default_landscape()
    return e


@pytest.fixture
def bare_engine():
    """Engine with no competitors."""
    return CompetitiveIntelligenceEngine()


# ------------------------------------------------------------------
# Competitor Registration
# ------------------------------------------------------------------

class TestCompetitorRegistration:
    def test_register_competitor(self, bare_engine):
        profile = bare_engine.register_competitor(
            name="TestCorp",
            website="testcorp.com",
            products=["Product A"],
            pricing={"basic": "$10/mo"},
            target_markets=["developers"],
        )
        assert profile.name == "TestCorp"
        assert profile.competitor_id.startswith("comp-")

    def test_load_default_landscape(self, bare_engine):
        count = bare_engine.load_default_landscape()
        assert count == 5
        competitors = bare_engine.list_competitors()
        assert len(competitors) == 5

    def test_list_competitors(self, engine):
        competitors = engine.list_competitors()
        names = [c["name"] for c in competitors]
        assert "Zapier" in names
        assert "UiPath" in names
        assert "n8n" in names

    def test_get_competitor(self, engine):
        competitors = engine.list_competitors()
        comp_id = competitors[0]["competitor_id"]
        result = engine.get_competitor(comp_id)
        assert result is not None
        assert "name" in result

    def test_get_nonexistent_competitor(self, engine):
        result = engine.get_competitor("fake-id")
        assert result is None

    def test_competitor_has_pricing(self, engine):
        competitors = engine.list_competitors()
        zapier = next(c for c in competitors if c["name"] == "Zapier")
        assert "enterprise" in zapier["pricing"]

    def test_competitor_has_target_markets(self, engine):
        competitors = engine.list_competitors()
        uipath = next(c for c in competitors if c["name"] == "UiPath")
        assert "enterprise_it" in uipath["target_markets"]


# ------------------------------------------------------------------
# Landscape Analysis
# ------------------------------------------------------------------

class TestLandscapeAnalysis:
    def test_analyze_landscape_structure(self, engine):
        analysis = engine.analyze_landscape()
        assert "competitor_count" in analysis
        assert "our_unique_capabilities" in analysis
        assert "competitor_only_features" in analysis
        assert "threat_matrix" in analysis
        assert analysis["competitor_count"] == 5

    def test_our_unique_capabilities_found(self, engine):
        analysis = engine.analyze_landscape()
        unique = analysis["our_unique_capabilities"]
        # Murphy has safety_first_architecture — no competitor lists this
        assert "safety_first_architecture" in unique or len(unique) > 0

    def test_competitor_gaps_found(self, engine):
        analysis = engine.analyze_landscape()
        gaps = analysis["competitor_only_features"]
        assert len(gaps) > 0  # Competitors have features we don't

    def test_threat_matrix_per_competitor(self, engine):
        analysis = engine.analyze_landscape()
        matrix = analysis["threat_matrix"]
        assert len(matrix) == 5
        for entry in matrix:
            assert "competitor" in entry
            assert "threat_level" in entry
            assert "they_have_we_dont" in entry
            assert "we_have_they_dont" in entry

    def test_high_threat_competitors(self, engine):
        """Zapier (25%), Power Automate (20%), UiPath (15%) should be high threat."""
        analysis = engine.analyze_landscape()
        matrix = analysis["threat_matrix"]
        high_threats = [m for m in matrix if m["threat_level"] == "high"]
        high_names = {m["competitor"] for m in high_threats}
        assert "Zapier" in high_names
        assert "Microsoft Power Automate" in high_names

    def test_empty_landscape_error(self, bare_engine):
        result = bare_engine.analyze_landscape()
        assert "error" in result

    def test_competitor_weaknesses_in_matrix(self, engine):
        analysis = engine.analyze_landscape()
        matrix = analysis["threat_matrix"]
        zapier_entry = next(m for m in matrix if m["competitor"] == "Zapier")
        assert "no_on_premise" in zapier_entry["their_weaknesses"]


# ------------------------------------------------------------------
# Gap Detection
# ------------------------------------------------------------------

class TestGapDetection:
    def test_detect_gaps(self, engine):
        gaps = engine.detect_gaps()
        assert len(gaps) > 0
        for gap in gaps:
            assert gap.feature not in engine._our_capabilities

    def test_gaps_have_competitor_owners(self, engine):
        gaps = engine.detect_gaps()
        for gap in gaps:
            assert len(gap.competitors_with_feature) > 0

    def test_critical_gaps_have_multiple_competitors(self, engine):
        gaps = engine.detect_gaps()
        critical = [g for g in gaps if g.suggested_priority == RDPriority.CRITICAL]
        for gap in critical:
            assert len(gap.competitors_with_feature) >= 3

    def test_gap_demand_levels(self, engine):
        gaps = engine.detect_gaps()
        demands = {g.customer_demand for g in gaps}
        # With 5 competitors, we should have at least high and medium
        assert "high" in demands or "medium" in demands


# ------------------------------------------------------------------
# R&D Backlog Routing
# ------------------------------------------------------------------

class TestRDRouting:
    def test_route_gaps_to_rd(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        assert len(items) > 0

    def test_rd_items_have_priority(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        for item in items:
            assert item.priority in (RDPriority.CRITICAL, RDPriority.HIGH, RDPriority.MEDIUM, RDPriority.LOW)

    def test_rd_items_have_competitors_driving(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        for item in items:
            assert len(item.competitors_driving) > 0

    def test_rd_items_have_target_tier(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        for item in items:
            assert item.target_tier in ("pro", "enterprise", "creator_pro", "creator_starter")

    def test_rd_items_proposed_status(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        for item in items:
            assert item.status == RDStatus.PROPOSED

    def test_get_rd_backlog_by_priority(self, engine):
        engine.detect_gaps()
        engine.route_gaps_to_rd()
        critical = engine.get_rd_backlog(priority=RDPriority.CRITICAL)
        for item in critical:
            assert item["priority"] == "critical"

    def test_advance_rd_item(self, engine):
        engine.detect_gaps()
        items = engine.route_gaps_to_rd()
        if items:
            result = engine.advance_rd_item(items[0].item_id, RDStatus.ACCEPTED)
            assert result is not None
            assert result["status"] == "accepted"

    def test_advance_nonexistent_item(self, engine):
        result = engine.advance_rd_item("fake-id", RDStatus.ACCEPTED)
        assert result is None

    def test_rd_routing_idempotent(self, engine):
        """Running route_gaps_to_rd twice doesn't duplicate items."""
        engine.detect_gaps()
        items1 = engine.route_gaps_to_rd()
        items2 = engine.route_gaps_to_rd()
        assert len(items2) == 0  # All already routed
        total = engine.get_rd_backlog()
        assert len(total) == len(items1)


# ------------------------------------------------------------------
# Competitive Response Strategies
# ------------------------------------------------------------------

class TestCompetitiveStrategies:
    def test_generate_strategies(self, engine):
        strategies = engine.generate_competitive_strategies()
        assert len(strategies) == 5  # One per competitor

    def test_strategy_has_advantages(self, engine):
        strategies = engine.generate_competitive_strategies()
        for s in strategies:
            assert len(s.our_advantages) > 0

    def test_strategy_has_messaging(self, engine):
        strategies = engine.generate_competitive_strategies()
        for s in strategies:
            assert len(s.messaging) > 0
            # Messaging should reference the competitor
            assert s.competitor_name in s.messaging

    def test_strategy_has_channels(self, engine):
        strategies = engine.generate_competitive_strategies()
        for s in strategies:
            assert len(s.recommended_channels) > 0
            # Every strategy should include comparison landing page
            assert "comparison_landing_page" in s.recommended_channels

    def test_strategy_targets_competitor_markets(self, engine):
        strategies = engine.generate_competitive_strategies()
        for s in strategies:
            assert len(s.target_segments) > 0

    def test_enterprise_competitor_gets_enterprise_tier(self, engine):
        """UiPath targets enterprise — strategy should recommend enterprise tier."""
        strategies = engine.generate_competitive_strategies()
        uipath_strat = next(s for s in strategies if s.competitor_name == "UiPath")
        assert uipath_strat.recommended_tier == "enterprise"

    def test_strategy_exploits_weaknesses(self, engine):
        strategies = engine.generate_competitive_strategies()
        for s in strategies:
            assert len(s.their_weaknesses_to_exploit) > 0


# ------------------------------------------------------------------
# Full Competitive Analysis
# ------------------------------------------------------------------

class TestFullAnalysis:
    def test_full_analysis_structure(self, engine):
        report = engine.full_competitive_analysis()
        assert "report_id" in report
        assert "landscape" in report
        assert "gaps" in report
        assert "rd_backlog" in report
        assert "competitive_strategies" in report
        assert "summary" in report

    def test_full_analysis_summary(self, engine):
        report = engine.full_competitive_analysis()
        summary = report["summary"]
        assert summary["competitors_analyzed"] == 5
        assert summary["our_unique_advantages"] > 0
        assert summary["capability_gaps"] > 0
        assert summary["rd_items_created"] > 0
        assert summary["strategies_generated"] == 5

    def test_full_analysis_rd_items_created(self, engine):
        report = engine.full_competitive_analysis()
        assert report["rd_backlog"]["new_items_routed"] > 0

    def test_full_analysis_gaps_counted(self, engine):
        report = engine.full_competitive_analysis()
        assert report["gaps"]["total"] > 0


# ------------------------------------------------------------------
# CRO / VP Marketing Routing
# ------------------------------------------------------------------

class TestRouting:
    @pytest.fixture()
    def bootstrap(self):
        from src.inoni_org_bootstrap import InoniOrgBootstrap
        b = InoniOrgBootstrap()
        b.bootstrap()
        return b

    def test_route_competitor_query(self, bootstrap):
        """Competitive queries should route to CRO or VP Marketing."""
        persona = bootstrap.route_to_agent("Who are our competitors and how do we beat them?")
        assert persona is not None
        # Should route to marketing or CRO
        assert persona["role"] in ("chief_revenue_officer", "vp_marketing")

    def test_route_market_landscape_query(self, bootstrap):
        persona = bootstrap.route_to_agent("What does the competitive landscape look like?")
        assert persona is not None
        assert persona["role"] in ("chief_revenue_officer", "vp_marketing")


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_get_status(self, engine):
        status = engine.get_status()
        assert status["competitors"] == 5
        assert status["gaps_detected"] == 0  # Not yet run

    def test_status_after_analysis(self, engine):
        engine.full_competitive_analysis()
        status = engine.get_status()
        assert status["gaps_detected"] > 0
        assert status["rd_backlog_size"] > 0
        assert status["strategies_generated"] == 5
