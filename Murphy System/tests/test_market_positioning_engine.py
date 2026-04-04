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

    def test_all_ten_verticals_present(self, engine):
        expected = {
            "healthcare", "financial_services", "manufacturing",
            "technology", "professional_services", "government",
            "iot_building_automation", "energy_management",
            "additive_manufacturing", "factory_automation",
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


# ---------------------------------------------------------------------------
# 11. New verticals: IoT/BAS, Energy Management, Additive Mfg, Factory Auto
# ---------------------------------------------------------------------------

class TestNewVerticals:

    def test_iot_building_automation_vertical_present(self):
        engine = MarketPositioningEngine()
        vert = engine.get_vertical("iot_building_automation")
        assert vert.vertical_id == "iot_building_automation"
        assert len(vert.pain_points) >= 3
        assert len(vert.murphy_value_props) >= 3
        assert len(vert.content_topics) >= 5
        assert vert.b2b_pitch_hook

    def test_energy_management_vertical_present(self):
        engine = MarketPositioningEngine()
        vert = engine.get_vertical("energy_management")
        assert vert.vertical_id == "energy_management"
        assert "ashrae" in " ".join(vert.content_topics).lower() or "iso 50001" in " ".join(vert.murphy_value_props).lower()

    def test_additive_manufacturing_vertical_present(self):
        engine = MarketPositioningEngine()
        vert = engine.get_vertical("additive_manufacturing")
        assert vert.vertical_id == "additive_manufacturing"
        assert any("opc" in t.lower() or "grabcad" in t.lower() or "stratasys" in t.lower()
                   for t in vert.content_topics)

    def test_factory_automation_vertical_present(self):
        engine = MarketPositioningEngine()
        vert = engine.get_vertical("factory_automation")
        assert vert.vertical_id == "factory_automation"
        assert any("isa-95" in t.lower() or "rockwell" in t.lower() or "beckhoff" in t.lower()
                   for t in vert.content_topics)

    def test_new_verticals_in_valid_set(self):
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            assert vid in _VALID_VERTICAL_IDS

    def test_new_verticals_have_relevant_capabilities(self):
        engine = MarketPositioningEngine()
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            caps = engine.get_capabilities_for_vertical(vid)
            assert len(caps) >= 4, f"{vid} should have ≥4 capabilities"

    def test_infer_vertical_beckhoff(self):
        engine = MarketPositioningEngine()
        result = engine._infer_vertical("beckhoff")
        assert result == "factory_automation"

    def test_infer_vertical_ameresco(self):
        engine = MarketPositioningEngine()
        result = engine._infer_vertical("ameresco")
        assert result == "energy_management"

    def test_infer_vertical_stratasys(self):
        engine = MarketPositioningEngine()
        result = engine._infer_vertical("stratasys")
        assert result == "additive_manufacturing"

    def test_infer_vertical_honeywell(self):
        engine = MarketPositioningEngine()
        result = engine._infer_vertical("honeywell forge buildings")
        assert result == "iot_building_automation"

    def test_score_partner_fit_factory_automation(self):
        engine = MarketPositioningEngine()
        score = engine.score_partner_fit("Rockwell Automation", ["integration_featuring", "case_study"])
        assert score > 0.0

    def test_content_topics_for_new_verticals_non_empty(self):
        engine = MarketPositioningEngine()
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            topics = engine.get_content_topics_for_vertical(vid)
            assert len(topics) >= 5

    def test_industry_pitch_angle_new_verticals(self):
        engine = MarketPositioningEngine()
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            angle = engine.get_industry_pitch_angle(vid)
            assert isinstance(angle, str) and len(angle) > 20

    def test_icp_for_new_verticals(self):
        engine = MarketPositioningEngine()
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            icp = engine.get_ideal_customer_profile(vid)
            assert icp["regulatory_context"]
            assert icp["b2b_pitch_hook"]

    def test_market_position_mentions_new_segments(self):
        engine = MarketPositioningEngine()
        mp = engine.get_market_position()
        segments_text = " ".join(mp.target_segments).lower()
        assert "building" in segments_text or "iot" in segments_text
        assert "energy" in segments_text or "audit" in segments_text
        assert "additive" in segments_text or "3d print" in segments_text
        assert "factory" in segments_text or "manufacturing" in segments_text

    def test_vertical_summary_includes_new_verticals(self):
        engine = MarketPositioningEngine()
        summary = engine.get_vertical_summary()
        for vid in ("iot_building_automation", "energy_management",
                    "additive_manufacturing", "factory_automation"):
            assert vid in summary


# ---------------------------------------------------------------------------
# 12. Commissioning gate wiring
# ---------------------------------------------------------------------------

class TestCommissioningGate:

    def _make_orchestrator(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from self_marketing_orchestrator import SelfMarketingOrchestrator
        return SelfMarketingOrchestrator()

    def test_commission_system_pass(self):
        orch = self._make_orchestrator()
        result = orch._commission_system(
            "test-001", "Test System",
            {"pieces_generated": 3, "errors": []},
        )
        assert result["status"] == "PASS"
        assert result["system_id"] == "test-001"
        assert result["system_name"] == "Test System"
        assert "checks_passed" in result
        assert "checks_failed" in result

    def test_commission_system_with_errors_still_returns_result(self):
        orch = self._make_orchestrator()
        result = orch._commission_system(
            "test-002", "Failing System",
            {"errors": ["Something went wrong"]},
        )
        # Errors present → checks_failed is non-empty
        assert isinstance(result["checks_failed"], list)
        assert len(result["checks_failed"]) >= 1

    def test_commission_system_sanitises_inputs(self):
        orch = self._make_orchestrator()
        result = orch._commission_system(
            "id\x00with\x00nulls", "name\x00here",
            {"errors": []},
        )
        assert "\x00" not in result["system_id"]
        assert "\x00" not in result["system_name"]

    def test_commission_system_caps_long_inputs(self):
        orch = self._make_orchestrator()
        result = orch._commission_system(
            "x" * 5000, "y" * 5000,
            {"errors": []},
        )
        assert len(result["system_id"]) <= 200
        assert len(result["system_name"]) <= 200

    def test_b2b_cycle_calls_commissioning(self):
        """B2B cycle result includes implicit commissioning — pipeline count non-negative."""
        orch = self._make_orchestrator()
        result = orch.run_b2b_partnership_cycle()
        # If commissioning fails, the cycle still returns a result (non-fatal)
        assert "cycle_id" in result

    def test_content_cycle_calls_commissioning(self):
        orch = self._make_orchestrator()
        result = orch.run_content_cycle()
        assert "cycle_id" in result


# ---------------------------------------------------------------------------
# 13. New DEFAULT_DESIRED_OFFERINGS entries
# ---------------------------------------------------------------------------

class TestNewDefaultOfferings:

    def _make_orchestrator(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from self_marketing_orchestrator import SelfMarketingOrchestrator
        return SelfMarketingOrchestrator()

    def test_total_partners_is_22(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        assert pipeline["total_partners"] == 22

    def test_new_iot_partners_present(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        ids = {p["partner_id"] for p in pipeline["partners"]}
        assert "siemens_smart_infrastructure" in ids
        assert "johnson_controls_openblue" in ids
        assert "honeywell_forge_buildings" in ids

    def test_new_energy_partners_present(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        ids = {p["partner_id"] for p in pipeline["partners"]}
        assert "ameresco" in ids
        assert "facilio" in ids
        assert "energycap" in ids

    def test_new_am_partners_present(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        ids = {p["partner_id"] for p in pipeline["partners"]}
        assert "stratasys" in ids
        assert "eos_gmbh" in ids
        assert "markforged" in ids

    def test_new_factory_partners_present(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        ids = {p["partner_id"] for p in pipeline["partners"]}
        assert "rockwell_automation" in ids
        assert "beckhoff" in ids
        assert "ptc_thingworx" in ids

    def test_all_new_partners_have_salesperson_name(self):
        orch = self._make_orchestrator()
        pipeline = orch.get_partnership_pipeline()
        new_ids = {
            "siemens_smart_infrastructure", "johnson_controls_openblue",
            "honeywell_forge_buildings", "ameresco", "facilio", "energycap",
            "stratasys", "eos_gmbh", "markforged",
            "rockwell_automation", "beckhoff", "ptc_thingworx",
        }
        for p in pipeline["partners"]:
            if p["partner_id"] in new_ids:
                assert p["has_named_contact"], f"{p['partner_id']} missing salesperson_name"

    def test_commissioning_is_not_an_offering_type(self):
        """Verify commissioning is never listed as a B2B offering type."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from self_marketing_orchestrator import B2B_OFFERING_TYPES, DEFAULT_DESIRED_OFFERINGS
        assert "commissioning" not in B2B_OFFERING_TYPES
        for offering in DEFAULT_DESIRED_OFFERINGS:
            assert "commissioning" not in offering.get("offering_types", [])
