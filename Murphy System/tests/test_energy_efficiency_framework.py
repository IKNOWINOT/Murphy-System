"""Tests for energy_efficiency_framework.py"""
import pytest, sys, os

from energy_efficiency_framework import (
    EnergyEfficiencyFramework, ECM_CATALOG, MSSEnergyRubric,
    ASHRAE_AUDIT_LEVELS, ECMCategory, EnergyConservationMeasure,
    UtilityAnalysis, _CBECS,
)


@pytest.fixture
def eef():
    return EnergyEfficiencyFramework()

@pytest.fixture
def util_data():
    return {"site_name":"Test Site","electricity_kwh":1_000_000,"natural_gas_therms":5_000,
            "facility_sqft":40_000,"electricity_cost":120_000,"natural_gas_cost":6_000,
            "demand_charges":15_000,"peak_demand_kw":200,"facility_type":"office"}

class TestECMCatalog:
    def test_25_ecms(self): assert len(ECM_CATALOG) == 25
    def test_all_have_ids(self): assert all(e.ecm_id for e in ECM_CATALOG)
    def test_all_have_names(self): assert all(e.name for e in ECM_CATALOG)
    def test_all_have_cem_reference(self): assert all(e.cem_reference for e in ECM_CATALOG)
    def test_all_have_ashrae_reference(self): assert all(e.ashrae_reference for e in ECM_CATALOG)
    def test_savings_positive(self): assert all(e.typical_savings_pct > 0 for e in ECM_CATALOG)
    def test_payback_positive(self): assert all(e.typical_payback_years > 0 for e in ECM_CATALOG)
    def test_categories_covered(self):
        cats = {e.category for e in ECM_CATALOG}
        for cat in [ECMCategory.HVAC, ECMCategory.LIGHTING, ECMCategory.CONTROLS, ECMCategory.ENVELOPE]:
            assert cat in cats
    def test_to_dict(self):
        d = ECM_CATALOG[0].to_dict()
        assert "ecm_id" in d and "category" in d
    def test_cost_tiers(self):
        tiers = {e.implementation_cost_tier for e in ECM_CATALOG}
        assert tiers == {"low", "medium", "high"}

class TestUtilityAnalysis:
    def test_eui_calculation(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        expected = (1_000_000*3.412 + 5_000*100) / 40_000
        assert abs(a.eui_kbtu_sqft_yr - expected) < 0.1
    def test_site_name(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        assert a.site_name == "Test Site"
    def test_default_rates(self, eef):
        a = eef.analyze_utility_data({"electricity_kwh":1000,"facility_sqft":1000})
        assert a.electricity_cost == pytest.approx(1000*0.12)
    def test_to_dict(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        d = a.to_dict()
        assert "eui_kbtu_sqft_yr" in d

class TestRecommendECMs:
    def test_returns_10(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        ecms = eef.recommend_ecms(a)
        assert len(ecms) == 10
    def test_high_eui_sorts_by_savings(self, eef):
        a = eef.analyze_utility_data({"electricity_kwh":5_000_000,"facility_sqft":10_000})
        ecms = eef.recommend_ecms(a)
        assert ecms[0].typical_savings_pct >= ecms[1].typical_savings_pct

class TestCalculateROI:
    def test_returns_all_keys(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        roi = eef.calculate_roi(ECM_CATALOG[0], a)
        for k in ["ecm_id","annual_savings_kwh","annual_savings_usd","payback_years","npv_10yr","irr_pct"]:
            assert k in roi
    def test_payback_positive(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        roi = eef.calculate_roi(ECM_CATALOG[0], a)
        assert roi["payback_years"] > 0

class TestAuditReport:
    def test_all_levels(self, eef, util_data):
        a = eef.analyze_utility_data(util_data)
        ecms = eef.recommend_ecms(a)
        for level in ["Level_I","Level_II","Level_III"]:
            r = eef.generate_audit_report(level, a, ecms)
            assert r["audit_level"] == level
            assert len(r["deliverables"]) > 0
    def test_ashrae_levels_structure(self):
        for lvl, data in ASHRAE_AUDIT_LEVELS.items():
            assert "name" in data and "deliverables" in data

class TestMSSRubric:
    def test_magnify_keys(self, util_data):
        r = MSSEnergyRubric().magnify(util_data)
        assert "detailed_breakdown" in r and "ecm_opportunities" in r
    def test_simplify_keys(self, util_data):
        r = MSSEnergyRubric().simplify(util_data)
        assert "top_3_quick_wins" in r and len(r["top_3_quick_wins"]) == 3
    def test_solidify_keys(self, util_data):
        r = MSSEnergyRubric().solidify(util_data)
        assert "committed_ecm_plan" in r and "measurement_verification_plan" in r
    def test_via_framework(self, eef, util_data):
        for mode in ["magnify","simplify","solidify"]:
            r = eef.apply_mss_rubric(mode, util_data)
            assert "error" not in r
    def test_unknown_mode(self, eef):
        r = eef.apply_mss_rubric("unknown", {})
        assert "error" in r

class TestBenchmark:
    def test_office_benchmark(self, eef):
        b = eef.get_cem_benchmark("office")
        assert b["median_eui_kbtu_sqft_yr"] == _CBECS["office"]
    def test_climate_adjustment(self, eef):
        b1 = eef.get_cem_benchmark("office", "2A")
        b2 = eef.get_cem_benchmark("office", "5A")
        assert b1["median_eui_kbtu_sqft_yr"] >= b2["median_eui_kbtu_sqft_yr"]
    def test_unknown_facility(self, eef):
        b = eef.get_cem_benchmark("unknown_type")
        assert b["median_eui_kbtu_sqft_yr"] == _CBECS["other"]
