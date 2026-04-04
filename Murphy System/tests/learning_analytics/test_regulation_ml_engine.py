"""
Tests for RegulationMLEngine — Murphy System.

Covers:
  - Scenario matrix generation (country × industry → correct toggle sets)
  - Phase 1 profiling produces valid RegulationProfile objects
  - Phase 2 training produces a model
  - Phase 3 predictions return valid recommendations
  - Conflict detection for known problematic combos
  - Co-occurrence analysis
  - Immune memory fast-path
  - Thread safety
  - Integration with ComplianceToggleManager
  - get_status() returns correct module info
"""

import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from regulation_ml_engine import (
    RegulationMLEngine,
    RegulationProfile,
    _make_profile_key,
    _frameworks_bitmask,
    _bms_bitmask,
    _gate_vector,
    _derive_gate_types,
    _compute_gate_weights,
    _order_gates,
    _count_conflicts,
    _derive_bms_standards,
    _KNOWN_CONFLICTS,
    _REG_IMMUNE_MEMORY,
    _REG_IMMUNE_LOCK,
    ALL_FRAMEWORKS,
    _COUNTRY_FRAMEWORKS,
    _INDUSTRY_FRAMEWORKS,
    BMS_COMPLIANCE_STANDARDS,
    get_status,
    get_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> RegulationMLEngine:
    """Return a fresh engine instance (not the singleton)."""
    return RegulationMLEngine()


# ---------------------------------------------------------------------------
# RegulationProfile dataclass
# ---------------------------------------------------------------------------

class TestRegulationProfile:
    def test_to_dict_roundtrip(self):
        p = RegulationProfile(
            profile_id="abc-123",
            country_code="DE",
            industry="finance",
            enabled_frameworks=["gdpr", "sox"],
            bms_standards=["ASHRAE_135"],
            gate_types=["compliance", "audit"],
            gate_weights={"compliance": 0.9, "audit": 0.85},
            gate_ordering=["compliance", "audit"],
            co_occurrence_score=0.4,
            conflict_score=0.0,
            efficiency_score=0.8,
            rubix_confidence=0.75,
            simulation_result={"status": "stub"},
            created_at="2026-01-01T00:00:00+00:00",
        )
        d = p.to_dict()
        assert d["profile_id"] == "abc-123"
        assert d["country_code"] == "DE"
        assert d["industry"] == "finance"
        assert d["enabled_frameworks"] == ["gdpr", "sox"]
        assert d["bms_standards"] == ["ASHRAE_135"]
        assert d["gate_types"] == ["compliance", "audit"]
        assert d["gate_weights"] == {"compliance": 0.9, "audit": 0.85}
        assert d["gate_ordering"] == ["compliance", "audit"]
        assert d["co_occurrence_score"] == 0.4
        assert d["conflict_score"] == 0.0
        assert d["efficiency_score"] == 0.8
        assert d["rubix_confidence"] == 0.75
        assert d["simulation_result"] == {"status": "stub"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_make_profile_key_normalises_case(self):
        assert _make_profile_key("de", "Finance") == "DE:finance"
        assert _make_profile_key("US", "HEALTHCARE") == "US:healthcare"

    def test_frameworks_bitmask_zero_for_empty(self):
        assert _frameworks_bitmask([], ALL_FRAMEWORKS if ALL_FRAMEWORKS else ["a", "b"]) == 0

    def test_frameworks_bitmask_nonzero_for_known(self):
        if not ALL_FRAMEWORKS:
            pytest.skip("ALL_FRAMEWORKS not available")
        bitmask = _frameworks_bitmask(["gdpr"], ALL_FRAMEWORKS)
        assert bitmask != 0

    def test_bms_bitmask_zero_for_empty(self):
        assert _bms_bitmask([]) == 0

    def test_bms_bitmask_nonzero_for_known(self):
        keys = list(BMS_COMPLIANCE_STANDARDS.keys())
        if not keys:
            pytest.skip("BMS_COMPLIANCE_STANDARDS not available")
        bitmask = _bms_bitmask([keys[0]])
        assert bitmask != 0

    def test_gate_vector_length_matches_all_gate_types(self):
        from regulation_ml_engine import _ALL_GATE_TYPES
        vec = _gate_vector(["compliance", "audit"])
        assert len(vec) == len(_ALL_GATE_TYPES)

    def test_gate_vector_marks_present_gates(self):
        from regulation_ml_engine import _ALL_GATE_TYPES
        vec = _gate_vector(_ALL_GATE_TYPES[:2])
        assert vec[0] == 1
        assert vec[1] == 1
        assert all(v == 0 for v in vec[2:])

    def test_derive_gate_types_always_includes_compliance_and_audit(self):
        gates = _derive_gate_types([])
        assert "compliance" in gates
        assert "audit" in gates

    def test_derive_gate_types_adds_security_for_gdpr(self):
        gates = _derive_gate_types(["gdpr"])
        assert "security" in gates

    def test_compute_gate_weights_all_between_0_and_1(self):
        gates = ["compliance", "audit", "safety", "security"]
        weights = _compute_gate_weights(gates)
        for g, w in weights.items():
            assert 0.0 <= w <= 1.0, f"{g} has weight {w} out of range"

    def test_order_gates_descending_weights(self):
        gates = ["monitoring", "safety", "compliance"]
        weights = _compute_gate_weights(gates)
        ordered = _order_gates(weights)
        weights_ordered = [weights[g] for g in ordered]
        assert weights_ordered == sorted(weights_ordered, reverse=True)

    def test_count_conflicts_known_pair(self):
        # gdpr + dsgvo is a known conflict
        score = _count_conflicts(["gdpr", "dsgvo"])
        assert score >= 1.0

    def test_count_conflicts_no_conflict(self):
        score = _count_conflicts(["hipaa", "iso_9001"])
        assert score == 0.0

    def test_derive_bms_standards_healthcare(self):
        standards = _derive_bms_standards("healthcare")
        assert len(standards) > 0

    def test_derive_bms_standards_unknown_falls_back_to_general(self):
        standards = _derive_bms_standards("unknown_industry_xyz")
        # Falls back to "general" or returns empty list — both valid
        assert isinstance(standards, list)


# ---------------------------------------------------------------------------
# Scenario matrix generation
# ---------------------------------------------------------------------------

class TestScenarioMatrix:
    def test_generates_non_empty_matrix(self):
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        assert len(scenarios) > 0

    def test_scenario_tuple_structure(self):
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        for country, industry, frameworks in scenarios:
            assert isinstance(country, str)
            assert isinstance(industry, str)
            assert isinstance(frameworks, list)

    def test_all_frameworks_are_valid(self):
        if not ALL_FRAMEWORKS:
            pytest.skip("ALL_FRAMEWORKS not available")
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        fw_catalog = set(ALL_FRAMEWORKS)
        for _, _, frameworks in scenarios:
            for fw in frameworks:
                assert fw in fw_catalog, f"Unknown framework: {fw}"

    def test_no_duplicate_country_industry_pairs(self):
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        keys = [_make_profile_key(c, i) for c, i, _ in scenarios]
        assert len(keys) == len(set(keys)), "Duplicate scenario keys found"

    def test_de_finance_includes_gdpr_and_sox(self):
        if not ALL_FRAMEWORKS or "DE" not in _COUNTRY_FRAMEWORKS:
            pytest.skip("Required catalogs not available")
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        de_finance = [fws for c, i, fws in scenarios if c == "DE" and i == "finance"]
        assert de_finance, "DE/finance scenario not found"
        assert "gdpr" in de_finance[0]
        assert "sox" in de_finance[0]

    def test_us_healthcare_includes_hipaa(self):
        if not ALL_FRAMEWORKS or "US" not in _COUNTRY_FRAMEWORKS:
            pytest.skip("Required catalogs not available")
        engine = _make_engine()
        scenarios = engine._generate_scenario_matrix()
        us_hc = [fws for c, i, fws in scenarios if c == "US" and i == "healthcare"]
        assert us_hc, "US/healthcare scenario not found"
        assert "hipaa" in us_hc[0]


# ---------------------------------------------------------------------------
# Phase 1 — Profiling
# ---------------------------------------------------------------------------

class TestPhase1:
    def test_profile_scenario_returns_regulation_profile(self):
        engine = _make_engine()
        profile = engine._profile_scenario("DE", "finance", ["gdpr", "sox"])
        assert isinstance(profile, RegulationProfile)

    def test_profile_has_non_empty_gate_types(self):
        engine = _make_engine()
        profile = engine._profile_scenario("US", "healthcare", ["hipaa", "hitech"])
        assert len(profile.gate_types) > 0

    def test_profile_rubix_confidence_in_range(self):
        engine = _make_engine()
        profile = engine._profile_scenario("GB", "technology", ["gdpr", "soc2"])
        assert 0.0 <= profile.rubix_confidence <= 1.0

    def test_profile_efficiency_score_in_range(self):
        engine = _make_engine()
        profile = engine._profile_scenario("US", "manufacturing", ["iso_9001", "osha"])
        assert 0.0 <= profile.efficiency_score <= 1.0

    def test_profile_conflict_score_for_known_conflict(self):
        engine = _make_engine()
        profile = engine._profile_scenario("DE", "general", ["gdpr", "dsgvo"])
        assert profile.conflict_score >= 1.0

    def test_run_phase1_returns_count(self):
        engine = _make_engine()
        count = engine.run_phase1()
        assert count > 0

    def test_run_phase1_populates_profiles(self):
        engine = _make_engine()
        engine.run_phase1()
        profiles = engine.get_all_profiles()
        assert len(profiles) > 0

    def test_profiles_have_unique_ids(self):
        engine = _make_engine()
        engine.run_phase1()
        profiles = engine.get_all_profiles()
        ids = [p.profile_id for p in profiles]
        assert len(ids) == len(set(ids)), "Duplicate profile IDs found"

    def test_profiles_seed_immune_memory(self):
        engine = _make_engine()
        engine.run_phase1()
        # Immune memory should be non-empty after phase 1
        with _REG_IMMUNE_LOCK:
            count = len(_REG_IMMUNE_MEMORY)
        assert count > 0

    def test_profile_bms_standards_for_healthcare(self):
        engine = _make_engine()
        profile = engine._profile_scenario("US", "healthcare", ["hipaa"])
        assert isinstance(profile.bms_standards, list)

    def test_profile_gate_ordering_is_sorted_by_weight(self):
        engine = _make_engine()
        profile = engine._profile_scenario("US", "finance", ["sox", "pci_dss"])
        ordered_weights = [profile.gate_weights[g] for g in profile.gate_ordering if g in profile.gate_weights]
        assert ordered_weights == sorted(ordered_weights, reverse=True)


# ---------------------------------------------------------------------------
# Phase 2 — Training
# ---------------------------------------------------------------------------

class TestPhase2:
    def test_run_phase2_without_phase1_returns_empty(self):
        engine = _make_engine()
        result = engine.run_phase2()
        assert result == {}

    def test_train_returns_model_dict(self):
        engine = _make_engine()
        model = engine.train()
        assert isinstance(model, dict)

    def test_trained_flag_set_after_train(self):
        engine = _make_engine()
        engine.train()
        assert engine._trained is True

    def test_model_has_type_field(self):
        engine = _make_engine()
        model = engine.train()
        assert "type" in model
        assert model["type"] in ("ml", "stub")

    def test_model_has_profile_count(self):
        engine = _make_engine()
        model = engine.train()
        assert "profile_count" in model
        assert model["profile_count"] > 0

    def test_model_has_lookup(self):
        engine = _make_engine()
        model = engine.train()
        assert "lookup" in model
        assert isinstance(model["lookup"], dict)

    def test_export_model_is_json_serialisable(self):
        import json
        engine = _make_engine()
        engine.train()
        exported = engine.export_model()
        # Should not raise
        json.dumps(exported)

    def test_build_lookup_keys_are_country_industry(self):
        profiles = [
            RegulationProfile(
                profile_id="p1",
                country_code="DE",
                industry="finance",
                enabled_frameworks=["gdpr"],
                bms_standards=[],
                gate_types=["compliance"],
                gate_weights={"compliance": 0.9},
                gate_ordering=["compliance"],
                co_occurrence_score=0.1,
                conflict_score=0.0,
                efficiency_score=0.8,
                rubix_confidence=0.75,
                simulation_result={},
                created_at="2026-01-01T00:00:00+00:00",
            )
        ]
        lookup = RegulationMLEngine.build_lookup(profiles)
        assert "DE:finance" in lookup


# ---------------------------------------------------------------------------
# Phase 3 — Predictions
# ---------------------------------------------------------------------------

class TestPredictOptimalToggles:
    def test_returns_dict_with_required_keys(self):
        engine = _make_engine()
        engine.train()
        result = engine.predict_optimal_toggles("DE", "finance")
        assert isinstance(result, dict)
        assert "recommended_frameworks" in result
        assert "confidence" in result
        assert "gate_types" in result
        assert "gate_ordering" in result
        assert "conflict_score" in result
        assert "source" in result

    def test_recommended_frameworks_is_list(self):
        engine = _make_engine()
        engine.train()
        result = engine.predict_optimal_toggles("US", "healthcare")
        assert isinstance(result["recommended_frameworks"], list)

    def test_confidence_in_range(self):
        engine = _make_engine()
        engine.train()
        result = engine.predict_optimal_toggles("US", "finance")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_immune_memory_fast_path_used_after_first_call(self):
        engine = _make_engine()
        engine.train()
        # First call — populates immune memory
        engine.predict_optimal_toggles("AU", "retail")
        # Second call — should hit immune_memory
        result = engine.predict_optimal_toggles("AU", "retail")
        assert result["source"] == "immune_memory"

    def test_novel_combination_returns_heuristic(self):
        engine = _make_engine()
        # Don't train first — verify heuristic fallback kicks in
        result = engine.predict_optimal_toggles("XX_NOVEL_99", "novel_industry_xyz")
        assert "recommended_frameworks" in result
        assert "source" in result

    def test_all_returned_frameworks_are_valid(self):
        if not ALL_FRAMEWORKS:
            pytest.skip("ALL_FRAMEWORKS not available")
        engine = _make_engine()
        engine.train()
        result = engine.predict_optimal_toggles("DE", "healthcare")
        fw_catalog = set(ALL_FRAMEWORKS)
        for fw in result["recommended_frameworks"]:
            assert fw in fw_catalog

    def test_constraints_param_accepted(self):
        engine = _make_engine()
        engine.train()
        result = engine.predict_optimal_toggles("US", "finance", constraints={"exclude": ["sox"]})
        assert "recommended_frameworks" in result


class TestPredictGateConfig:
    def test_returns_gate_types(self):
        engine = _make_engine()
        result = engine.predict_gate_config_for_regulation_set(["gdpr", "sox", "hipaa"])
        assert "gate_types" in result
        assert len(result["gate_types"]) > 0

    def test_returns_gate_weights(self):
        engine = _make_engine()
        result = engine.predict_gate_config_for_regulation_set(["soc2", "iso_27001"])
        assert "gate_weights" in result
        for g, w in result["gate_weights"].items():
            assert 0.0 <= w <= 1.0

    def test_returns_gate_ordering(self):
        engine = _make_engine()
        result = engine.predict_gate_config_for_regulation_set(["pci_dss", "sox"])
        assert "gate_ordering" in result
        assert isinstance(result["gate_ordering"], list)

    def test_empty_frameworks_still_returns_compliance_and_audit(self):
        engine = _make_engine()
        result = engine.predict_gate_config_for_regulation_set([])
        assert "compliance" in result["gate_types"]
        assert "audit" in result["gate_types"]

    def test_conflict_score_for_known_pair(self):
        engine = _make_engine()
        result = engine.predict_gate_config_for_regulation_set(["gdpr", "dsgvo"])
        assert result["conflict_score"] >= 1.0


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class TestGetConflictReport:
    def test_returns_required_keys(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["gdpr", "sox"])
        assert "conflicts" in report
        assert "redundancies" in report
        assert "conflict_count" in report
        assert "is_clean" in report

    def test_clean_for_non_conflicting_set(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["hipaa", "iso_9001", "fedramp"])
        assert report["is_clean"] is True

    def test_detects_gdpr_dsgvo_conflict(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["gdpr", "dsgvo"])
        assert report["conflict_count"] >= 1
        assert report["is_clean"] is False

    def test_detects_soc1_soc2_conflict(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["soc1", "soc2"])
        conflict_pairs = {(c["framework_a"], c["framework_b"]) for c in report["conflicts"]}
        conflict_pairs |= {(c["framework_b"], c["framework_a"]) for c in report["conflicts"]}
        assert ("soc1", "soc2") in conflict_pairs or ("soc2", "soc1") in conflict_pairs

    def test_detects_dsgvo_redundancy(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["gdpr", "dsgvo"])
        redundancy_fws = {r["framework"] for r in report["redundancies"]}
        assert "dsgvo" in redundancy_fws

    def test_enabled_frameworks_returned_in_report(self):
        engine = _make_engine()
        fws = ["hipaa", "sox"]
        report = engine.get_conflict_report(fws)
        assert report["enabled_frameworks"] == fws

    def test_cmmc_nist_conflict(self):
        engine = _make_engine()
        report = engine.get_conflict_report(["cmmc", "nist_800_171"])
        conflict_pairs = {(c["framework_a"], c["framework_b"]) for c in report["conflicts"]}
        conflict_pairs |= {(c["framework_b"], c["framework_a"]) for c in report["conflicts"]}
        assert ("cmmc", "nist_800_171") in conflict_pairs or ("nist_800_171", "cmmc") in conflict_pairs


# ---------------------------------------------------------------------------
# Co-occurrence analysis
# ---------------------------------------------------------------------------

class TestCoOccurrenceInsights:
    def test_no_data_before_training(self):
        engine = _make_engine()
        insights = engine.get_co_occurrence_insights()
        assert insights["status"] in ("no_data", "ok")

    def test_ok_after_training(self):
        engine = _make_engine()
        engine.train()
        insights = engine.get_co_occurrence_insights()
        assert insights["status"] == "ok"

    def test_has_required_keys_after_training(self):
        engine = _make_engine()
        engine.train()
        insights = engine.get_co_occurrence_insights()
        assert "total_scenarios_profiled" in insights
        assert "top_pairs" in insights
        assert "most_efficient_combo" in insights
        assert "most_conflicted_combo" in insights

    def test_top_pairs_is_list(self):
        engine = _make_engine()
        engine.train()
        insights = engine.get_co_occurrence_insights()
        assert isinstance(insights["top_pairs"], list)

    def test_most_efficient_combo_has_country_and_industry(self):
        engine = _make_engine()
        engine.train()
        insights = engine.get_co_occurrence_insights()
        combo = insights["most_efficient_combo"]
        if combo is not None:
            assert "country" in combo
            assert "industry" in combo
            assert "efficiency_score" in combo


# ---------------------------------------------------------------------------
# Immune memory fast-path
# ---------------------------------------------------------------------------

class TestImmuneMemory:
    def test_second_call_returns_immune_memory_source(self):
        engine = _make_engine()
        engine.train()
        # First call
        engine.predict_optimal_toggles("CA", "finance")
        # Second call
        result = engine.predict_optimal_toggles("CA", "finance")
        assert result["source"] == "immune_memory"

    def test_immune_memory_populated_after_phase1(self):
        engine = _make_engine()
        engine.run_phase1()
        with _REG_IMMUNE_LOCK:
            count = len(_REG_IMMUNE_MEMORY)
        assert count > 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_train_calls_do_not_raise(self):
        engine = _make_engine()
        errors = []

        def train_worker():
            try:
                engine.train()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=train_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Thread safety errors: {errors}"

    def test_concurrent_predict_calls_do_not_raise(self):
        engine = _make_engine()
        engine.train()
        errors = []

        combos = [("DE", "finance"), ("US", "healthcare"), ("GB", "technology"), ("AU", "retail")]

        def predict_worker(country: str, industry: str):
            try:
                engine.predict_optimal_toggles(country, industry)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=predict_worker, args=(c, i))
            for c, i in combos * 3
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Thread safety errors: {errors}"


# ---------------------------------------------------------------------------
# Integration with ComplianceToggleManager
# ---------------------------------------------------------------------------

class TestComplianceToggleManagerIntegration:
    def test_get_recommended_frameworks_signature_unchanged(self):
        """Existing call without use_ml still works."""
        from compliance_toggle_manager import ComplianceToggleManager
        mgr = ComplianceToggleManager()
        result = mgr.get_recommended_frameworks("DE", "finance")
        assert isinstance(result, list)
        assert "gdpr" in result

    def test_get_recommended_frameworks_with_use_ml_true_returns_list(self):
        from compliance_toggle_manager import ComplianceToggleManager
        mgr = ComplianceToggleManager()
        result = mgr.get_recommended_frameworks("DE", "finance", use_ml=True)
        assert isinstance(result, list)

    def test_use_ml_does_not_return_invalid_frameworks(self):
        from compliance_toggle_manager import ComplianceToggleManager, ALL_FRAMEWORKS
        mgr = ComplianceToggleManager()
        result = mgr.get_recommended_frameworks("US", "healthcare", use_ml=True)
        fw_catalog = set(ALL_FRAMEWORKS)
        for fw in result:
            assert fw in fw_catalog, f"Invalid framework returned: {fw}"

    def test_use_ml_returns_at_least_as_many_as_without_ml(self):
        from compliance_toggle_manager import ComplianceToggleManager
        mgr = ComplianceToggleManager()
        without_ml = mgr.get_recommended_frameworks("JP", "finance", use_ml=False)
        with_ml = mgr.get_recommended_frameworks("JP", "finance", use_ml=True)
        # ML can add frameworks but should not remove existing ones
        assert all(fw in with_ml for fw in without_ml)


# ---------------------------------------------------------------------------
# get_status()
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_get_status_returns_dict(self):
        engine = _make_engine()
        status = engine.get_status()
        assert isinstance(status, dict)

    def test_get_status_has_module_name(self):
        engine = _make_engine()
        status = engine.get_status()
        assert status["module"] == "regulation_ml_engine"

    def test_get_status_has_version(self):
        engine = _make_engine()
        status = engine.get_status()
        assert "version" in status
        assert status["version"] == "1.0.0"

    def test_get_status_trained_false_initially(self):
        engine = _make_engine()
        assert engine.get_status()["trained"] is False

    def test_get_status_trained_true_after_train(self):
        engine = _make_engine()
        engine.train()
        assert engine.get_status()["trained"] is True

    def test_get_status_profile_count_increases_after_train(self):
        engine = _make_engine()
        assert engine.get_status()["profile_count"] == 0
        engine.train()
        assert engine.get_status()["profile_count"] > 0

    def test_module_level_get_status(self):
        status = get_status()
        assert isinstance(status, dict)
        assert status["module"] == "regulation_ml_engine"

    def test_get_status_has_all_availability_flags(self):
        engine = _make_engine()
        status = engine.get_status()
        for key in ("ml_available", "causality_available", "rubix_available",
                    "compliance_catalog_available", "bms_catalog_available"):
            assert key in status
            assert isinstance(status[key], bool)

    def test_get_status_framework_count(self):
        engine = _make_engine()
        status = engine.get_status()
        assert "framework_count" in status
        assert status["framework_count"] >= 0

    def test_get_engine_returns_singleton(self):
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2
