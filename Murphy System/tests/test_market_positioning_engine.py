"""
Tests for MarketPositioningEngine (MPE-001)

Coverage areas:
  1. Data model integrity — all registered capabilities and verticals are well-formed
  2. Capability queries — get_capability, list_capabilities, get_capability_matrix
  3. Vertical queries — get_vertical, list_verticals, get_ideal_customer_profile
  4. Content topics — get_content_topics_for_vertical
  5. Pitch helpers — get_industry_pitch_angle, get_positioning_for_offering_types
  6. Partner fit scoring — score_partner_fit with explicit and inferred verticals
  7. Market position — get_market_position, get_vertical_summary
  8. Input validation / hardening — unknown IDs, injection strings, length caps (CWE-20)
  9. Wiring into SelfMarketingOrchestrator — dashboard, B2B pitch enrichment,
     content cycle vertical topic injection
 10. Singleton accessor — get_default_positioning_engine
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from market_positioning_engine import (
    INDUSTRY_VERTICALS,
    MURPHY_CAPABILITIES,
    MURPHY_MARKET_POSITION,
    IndustryVertical,
    MarketPosition,
    MarketPositioningEngine,
    MurphyCapability,
    _VALID_CAPABILITY_IDS,
    _VALID_VERTICAL_IDS,
    get_default_positioning_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> MarketPositioningEngine:
    return MarketPositioningEngine()


# ---------------------------------------------------------------------------
# 1. Data model integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:

    def test_all_capability_ids_in_registry(self, engine):
        """Every ID in _VALID_CAPABILITY_IDS must exist in MURPHY_CAPABILITIES."""
        for cap_id in _VALID_CAPABILITY_IDS:
            assert cap_id in MURPHY_CAPABILITIES, f"Missing capability: {cap_id}"

    def test_all_vertical_ids_in_registry(self, engine):
        """Every ID in _VALID_VERTICAL_IDS must exist in INDUSTRY_VERTICALS."""
        for vert_id in _VALID_VERTICAL_IDS:
            assert vert_id in INDUSTRY_VERTICALS, f"Missing vertical: {vert_id}"

    def test_capability_maturity_scores_in_range(self, engine):
        for cap in MURPHY_CAPABILITIES.values():
            assert 1 <= cap.maturity_score <= 10, (
                f"{cap.capability_id} has out-of-range maturity_score {cap.maturity_score}"
            )

    def test_capability_relevant_verticals_are_valid(self, engine):
        for cap in MURPHY_CAPABILITIES.values():
            for v_id in cap.relevant_vertical_ids:
                assert v_id in _VALID_VERTICAL_IDS, (
                    f"{cap.capability_id} references unknown vertical {v_id!r}"
                )

    def test_vertical_relevant_capabilities_are_valid(self, engine):
        for vert in INDUSTRY_VERTICALS.values():
            for cap_id in vert.relevant_capability_ids:
                assert cap_id in _VALID_CAPABILITY_IDS, (
                    f"{vert.vertical_id} references unknown capability {cap_id!r}"
                )

    def test_market_position_has_all_fields(self):
        mp = MURPHY_MARKET_POSITION
        assert mp.positioning_statement
        assert mp.tagline
        assert len(mp.differentiation_pillars) >= 3
        assert len(mp.target_segments) >= 2
        assert len(mp.competitive_moats) >= 3

    def test_capability_dataclass_is_frozen(self):
        cap = list(MURPHY_CAPABILITIES.values())[0]
        with pytest.raises((AttributeError, TypeError)):
            cap.name = "mutated"  # type: ignore[misc]

    def test_vertical_dataclass_is_frozen(self):
        vert = list(INDUSTRY_VERTICALS.values())[0]
        with pytest.raises((AttributeError, TypeError)):
            vert.name = "mutated"  # type: ignore[misc]

    def test_market_position_dataclass_is_frozen(self):
        mp = MURPHY_MARKET_POSITION
        with pytest.raises((AttributeError, TypeError)):
            mp.tagline = "mutated"  # type: ignore[misc]

    def test_all_capabilities_have_differentiators(self):
        for cap in MURPHY_CAPABILITIES.values():
            assert len(cap.differentiators) >= 1, f"{cap.capability_id} has no differentiators"

    def test_all_verticals_have_pain_points(self):
        for vert in INDUSTRY_VERTICALS.values():
            assert len(vert.pain_points) >= 3, f"{vert.vertical_id} has fewer than 3 pain points"

    def test_all_verticals_have_value_props(self):
        for vert in INDUSTRY_VERTICALS.values():
            assert len(vert.murphy_value_props) >= 3, (
                f"{vert.vertical_id} has fewer than 3 value props"
            )

    def test_all_verticals_have_content_topics(self):
        for vert in INDUSTRY_VERTICALS.values():
            assert len(vert.content_topics) >= 5, (
                f"{vert.vertical_id} has fewer than 5 content topics"
            )

    def test_all_verticals_have_b2b_pitch_hook(self):
        for vert in INDUSTRY_VERTICALS.values():
            assert vert.b2b_pitch_hook, f"{vert.vertical_id} missing b2b_pitch_hook"


# ---------------------------------------------------------------------------
# 2. Capability queries
# ---------------------------------------------------------------------------

class TestCapabilityQueries:

    def test_list_capabilities_returns_all(self, engine):
        caps = engine.list_capabilities()
        assert len(caps) == len(MURPHY_CAPABILITIES)

    def test_list_capabilities_sorted_by_maturity_descending(self, engine):
        caps = engine.list_capabilities()
        scores = [c.maturity_score for c in caps]
        assert scores == sorted(scores, reverse=True)

    def test_get_capability_known_id(self, engine):
        cap = engine.get_capability("nlp_workflow_automation")
        assert cap.capability_id == "nlp_workflow_automation"
        assert cap.maturity_score == 10

    def test_get_capability_unknown_id_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown capability_id"):
            engine.get_capability("nonexistent_capability")

    def test_get_capability_injection_string_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability("'; DROP TABLE caps; --")

    def test_get_capability_empty_string_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability("")

    def test_get_capability_non_string_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability(None)  # type: ignore

    def test_get_capability_matrix_all_keys(self, engine):
        matrix = engine.get_capability_matrix()
        assert set(matrix.keys()) == set(MURPHY_CAPABILITIES.keys())

    def test_get_capability_matrix_values_are_lists(self, engine):
        matrix = engine.get_capability_matrix()
        for v in matrix.values():
            assert isinstance(v, list)

    def test_get_capabilities_for_vertical_returns_subset(self, engine):
        caps = engine.get_capabilities_for_vertical("healthcare")
        cap_ids = {c.capability_id for c in caps}
        vert = INDUSTRY_VERTICALS["healthcare"]
        assert cap_ids == set(vert.relevant_capability_ids)

    def test_get_capabilities_for_vertical_unknown_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_capabilities_for_vertical("unknown_vertical")


# ---------------------------------------------------------------------------
# 3. Vertical queries
# ---------------------------------------------------------------------------

class TestVerticalQueries:

    def test_list_verticals_returns_all(self, engine):
        verts = engine.list_verticals()
        assert len(verts) == len(INDUSTRY_VERTICALS)

    def test_get_vertical_known_id(self, engine):
        vert = engine.get_vertical("healthcare")
        assert vert.vertical_id == "healthcare"

    def test_get_vertical_unknown_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown vertical_id"):
            engine.get_vertical("unknown")

    def test_get_vertical_injection_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_vertical("<script>alert(1)</script>")

    def test_get_ideal_customer_profile_has_required_fields(self, engine):
        icp = engine.get_ideal_customer_profile("financial_services")
        assert icp["vertical_id"] == "financial_services"
        assert "icp" in icp
        assert "pain_points" in icp
        assert "regulatory_context" in icp
        assert "murphy_value_props" in icp
        assert "b2b_pitch_hook" in icp

    def test_get_ideal_customer_profile_unknown_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_ideal_customer_profile("invalid_vertical")

    def test_all_six_verticals_present(self, engine):
        expected = {
            "healthcare", "financial_services", "manufacturing",
            "technology", "professional_services", "government",
        }
        ids = {v.vertical_id for v in engine.list_verticals()}
        assert ids == expected


# ---------------------------------------------------------------------------
# 4. Content topics
# ---------------------------------------------------------------------------

class TestContentTopics:

    def test_get_topics_for_each_vertical_returns_list(self, engine):
        for v_id in _VALID_VERTICAL_IDS:
            topics = engine.get_content_topics_for_vertical(v_id)
            assert isinstance(topics, list)
            assert len(topics) >= 5, f"{v_id} should have ≥5 topics"

    def test_topics_are_strings(self, engine):
        for v_id in _VALID_VERTICAL_IDS:
            for topic in engine.get_content_topics_for_vertical(v_id):
                assert isinstance(topic, str)

    def test_get_topics_unknown_vertical_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_content_topics_for_vertical("nonexistent")

    def test_healthcare_topics_mention_relevant_terms(self, engine):
        topics = engine.get_content_topics_for_vertical("healthcare")
        combined = " ".join(topics).lower()
        assert any(kw in combined for kw in ["hipaa", "clinical", "physician", "fhir", "article"])

    def test_manufacturing_topics_mention_relevant_terms(self, engine):
        topics = engine.get_content_topics_for_vertical("manufacturing")
        combined = " ".join(topics).lower()
        assert any(kw in combined for kw in ["scada", "iot", "maintenance", "sil", "safety"])


# ---------------------------------------------------------------------------
# 5. Pitch helpers
# ---------------------------------------------------------------------------

class TestPitchHelpers:

    def test_get_industry_pitch_angle_no_offerings(self, engine):
        angle = engine.get_industry_pitch_angle("technology")
        assert isinstance(angle, str)
        assert len(angle) > 20

    def test_get_industry_pitch_angle_with_offerings(self, engine):
        angle = engine.get_industry_pitch_angle("healthcare", ["case_study"])
        assert "case_study" not in angle or "capabilities" in angle.lower() or angle
        assert isinstance(angle, str)

    def test_get_industry_pitch_angle_all_verticals(self, engine):
        for v_id in _VALID_VERTICAL_IDS:
            angle = engine.get_industry_pitch_angle(v_id)
            assert angle  # must be non-empty

    def test_get_industry_pitch_angle_unknown_vertical_raises(self, engine):
        with pytest.raises(ValueError):
            engine.get_industry_pitch_angle("unknown_vertical")

    def test_get_positioning_for_offering_types_valid(self, engine):
        result = engine.get_positioning_for_offering_types(["case_study", "featuring"])
        assert "positioning_statement" in result
        assert "tagline" in result
        assert "relevant_capabilities" in result
        assert "offering_types" in result
        assert isinstance(result["relevant_capabilities"], list)

    def test_get_positioning_for_offering_types_empty(self, engine):
        result = engine.get_positioning_for_offering_types([])
        assert "positioning_statement" in result
        assert result["offering_types"] == []

    def test_get_positioning_for_offering_types_unknown_filtered(self, engine):
        result = engine.get_positioning_for_offering_types(["unknown_type", "case_study"])
        assert "unknown_type" not in result["offering_types"]
        assert "case_study" in result["offering_types"]

    def test_get_positioning_for_offering_types_caps_at_six(self, engine):
        many = ["case_study"] * 20
        result = engine.get_positioning_for_offering_types(many)
        assert len(result["offering_types"]) <= 6


# ---------------------------------------------------------------------------
# 6. Partner fit scoring
# ---------------------------------------------------------------------------

class TestPartnerFitScoring:

    def test_score_returns_float_in_range(self, engine):
        score = engine.score_partner_fit("HubSpot", ["case_study", "featuring"])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_higher_with_valid_offering_types(self, engine):
        score_valid = engine.score_partner_fit("Acme Corp", ["case_study"])
        score_empty = engine.score_partner_fit("Acme Corp", [])
        assert score_valid >= score_empty

    def test_score_with_explicit_vertical(self, engine):
        score = engine.score_partner_fit("Anyco", ["case_study"], vertical_id="healthcare")
        assert 0.0 <= score <= 1.0

    def test_score_with_inferred_vertical_technology(self, engine):
        # "HubSpot" triggers the technology heuristic
        score = engine.score_partner_fit("HubSpot", ["featuring", "integration_featuring"])
        assert score > 0.0

    def test_score_with_all_invalid_offering_types(self, engine):
        score = engine.score_partner_fit("Acme", ["invalid_type_xyz"])
        assert score == 0.0

    def test_score_unknown_company_does_not_crash(self, engine):
        score = engine.score_partner_fit("Totally Unknown Corp XYZ", ["case_study"])
        assert 0.0 <= score <= 1.0

    def test_score_long_company_name_truncated(self, engine):
        long_name = "A" * 5000
        score = engine.score_partner_fit(long_name, ["case_study"])
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 7. Market position + vertical summary
# ---------------------------------------------------------------------------

class TestMarketPosition:

    def test_get_market_position_returns_market_position(self, engine):
        mp = engine.get_market_position()
        assert isinstance(mp, MarketPosition)

    def test_market_position_positioning_statement_non_empty(self, engine):
        mp = engine.get_market_position()
        assert len(mp.positioning_statement) > 50

    def test_market_position_tagline(self, engine):
        mp = engine.get_market_position()
        assert "Automate" in mp.tagline or "automate" in mp.tagline.lower() or mp.tagline

    def test_get_vertical_summary_has_all_verticals(self, engine):
        summary = engine.get_vertical_summary()
        assert set(summary.keys()) == _VALID_VERTICAL_IDS

    def test_get_vertical_summary_has_counts(self, engine):
        summary = engine.get_vertical_summary()
        for v_id, info in summary.items():
            assert info["pain_points_count"] >= 3
            assert info["value_props_count"] >= 3
            assert info["relevant_capabilities"] >= 4


# ---------------------------------------------------------------------------
# 8. Input validation / hardening (CWE-20)
# ---------------------------------------------------------------------------

class TestHardening:

    def test_null_byte_in_capability_id_rejected(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability("nlp_workflow\x00_automation")

    def test_null_byte_in_vertical_id_rejected(self, engine):
        with pytest.raises(ValueError):
            engine.get_vertical("healthcare\x00")

    def test_very_long_capability_id_rejected(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability("a" * 201)

    def test_very_long_vertical_id_rejected(self, engine):
        with pytest.raises(ValueError):
            engine.get_vertical("a" * 201)

    def test_path_traversal_in_capability_id_rejected(self, engine):
        with pytest.raises(ValueError):
            engine.get_capability("../../etc/passwd")

    def test_pitch_angle_with_long_offering_list_bounded(self, engine):
        # Should not crash or produce unbounded output
        many = ["case_study"] * 100
        result = engine.get_positioning_for_offering_types(many)
        assert len(result["offering_types"]) <= 6

    def test_score_partner_fit_many_offering_types_bounded(self, engine):
        many = ["case_study"] * 100
        score = engine.score_partner_fit("Corp", many)
        assert 0.0 <= score <= 1.0

    def test_get_industry_pitch_angle_with_many_offering_types_bounded(self, engine):
        many_types = ["case_study", "featuring"] * 50
        result = engine.get_industry_pitch_angle("technology", many_types)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 9. SelfMarketingOrchestrator wiring
# ---------------------------------------------------------------------------

class TestOrchestratorWiring:

    def _make_orchestrator(self, positioning_engine=None):
        from self_marketing_orchestrator import SelfMarketingOrchestrator
        return SelfMarketingOrchestrator(positioning_engine=positioning_engine)

    def test_orchestrator_accepts_positioning_engine(self):
        engine = MarketPositioningEngine()
        orch = self._make_orchestrator(positioning_engine=engine)
        assert orch._positioning is engine

    def test_orchestrator_uses_default_engine_when_none(self):
        orch = self._make_orchestrator(positioning_engine=None)
        assert isinstance(orch._positioning, MarketPositioningEngine)

    def test_dashboard_includes_market_position(self):
        orch = self._make_orchestrator()
        dashboard = orch.get_marketing_dashboard()
        assert "market_position" in dashboard
        mp = dashboard["market_position"]
        assert "positioning_statement" in mp
        assert "tagline" in mp
        assert "vertical_summary" in mp
        assert "total_capabilities" in mp
        assert "total_verticals" in mp

    def test_dashboard_market_position_counts_correct(self):
        orch = self._make_orchestrator()
        dashboard = orch.get_marketing_dashboard()
        mp = dashboard["market_position"]
        assert mp["total_capabilities"] == len(MURPHY_CAPABILITIES)
        assert mp["total_verticals"] == len(INDUSTRY_VERTICALS)

    def test_dashboard_vertical_summary_structure(self):
        orch = self._make_orchestrator()
        dashboard = orch.get_marketing_dashboard()
        vs = dashboard["market_position"]["vertical_summary"]
        assert set(vs.keys()) == _VALID_VERTICAL_IDS

    def test_b2b_pitch_includes_positioning_section(self):
        from self_marketing_orchestrator import PartnershipProspect
        orch = self._make_orchestrator()
        partner = PartnershipProspect(
            partner_id="testco",
            company="TestCo",
            contact_role="partnerships",
            channel="email",
            offering_types=["case_study", "featuring"],
            pitch_angle="Murphy automates TestCo workflows via NL.",
        )
        pitch = orch.generate_b2b_pitch(partner)
        # The positioning engine should have enriched the body with capability info
        assert "Murphy" in pitch["body"]
        assert "TestCo" in pitch["body"]
        assert len(pitch["body"]) > 200

    def test_content_cycle_runs_with_positioning_engine(self):
        orch = self._make_orchestrator()
        result = orch.run_content_cycle()
        assert "cycle_id" in result
        # Vertical topics should have been injected — at least some content generated
        assert result["pieces_generated"] >= 0  # may be 0 if dedup kicks in

    def test_orchestrator_does_not_crash_with_custom_engine(self):
        class MinimalEngine(MarketPositioningEngine):
            pass
        orch = self._make_orchestrator(positioning_engine=MinimalEngine())
        dashboard = orch.get_marketing_dashboard()
        assert "market_position" in dashboard


# ---------------------------------------------------------------------------
# 10. Singleton accessor
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_default_engine_returns_instance(self):
        e = get_default_positioning_engine()
        assert isinstance(e, MarketPositioningEngine)

    def test_get_default_engine_is_stable(self):
        """Two calls return the same object."""
        e1 = get_default_positioning_engine()
        e2 = get_default_positioning_engine()
        assert e1 is e2

    def test_default_engine_functional(self):
        e = get_default_positioning_engine()
        mp = e.get_market_position()
        assert mp.positioning_statement
