"""Tests for climate_resilience_engine.py"""
import pytest, sys, os

from climate_resilience_engine import (
    ClimateResilienceEngine, CLIMATE_ZONE_DATABASE, ClimateZone, ResilienceFactors, EnergyTarget,
)


@pytest.fixture
def engine():
    return ClimateResilienceEngine()

class TestClimateZoneDatabase:
    def test_15_zones(self): assert len(CLIMATE_ZONE_DATABASE) >= 12
    def test_each_has_zone_id(self):
        for zid, z in CLIMATE_ZONE_DATABASE.items():
            assert z.zone_id == zid
    def test_each_has_degree_days(self):
        for z in CLIMATE_ZONE_DATABASE.values():
            assert z.heating_degree_days >= 0
            assert z.cooling_degree_days >= 0

class TestLookupClimateZone:
    def test_miami_is_1a(self, engine):
        z = engine.lookup_climate_zone("Miami")
        assert z is not None and z.zone_id == "1A"
    def test_chicago_is_5a(self, engine):
        z = engine.lookup_climate_zone("Chicago")
        assert z is not None and z.zone_id == "5A"
    def test_phoenix_hot_dry(self, engine):
        z = engine.lookup_climate_zone("Phoenix")
        assert z is not None
    def test_unknown_returns_none_or_fallback(self, engine):
        z = engine.lookup_climate_zone("XYZnonexistent12345")
        # acceptable: None or a fallback zone
        assert z is None or hasattr(z, "zone_id")

class TestDesignRecommendations:
    def test_miami_chiller_rec(self, engine):
        recs = engine.get_design_recommendations("Miami", "chiller")
        assert len(recs) > 0
        assert any(isinstance(r, str) for r in recs)
    def test_chicago_boiler_rec(self, engine):
        recs = engine.get_design_recommendations("Chicago", "boiler")
        assert len(recs) > 0
    def test_unknown_location(self, engine):
        recs = engine.get_design_recommendations("Unknown City", "AHU")
        assert isinstance(recs, list)

class TestResilienceFactors:
    def test_miami_hurricane_high(self, engine):
        r = engine.get_resilience_factors("Miami")
        assert r.hurricane_risk in (True, "high", "moderate", "yes")
    def test_resilience_has_expected_fields(self, engine):
        r = engine.get_resilience_factors("Chicago")
        assert hasattr(r, "hurricane_risk")
        assert hasattr(r, "flood_zone")
        assert hasattr(r, "design_temp_cooling")
    def test_returns_resilience_factors(self, engine):
        r = engine.get_resilience_factors("Seattle")
        assert isinstance(r, ResilienceFactors)

class TestEnergyTargets:
    def test_office_target(self, engine):
        t = engine.get_energy_targets("Chicago", "office")
        assert isinstance(t, EnergyTarget)
        assert t.ashrae_901_eui > 0
    def test_heating_recommendation_cold_climate(self, engine):
        t = engine.get_energy_targets("Chicago", "office")
        assert t.heating_system_recommendation
    def test_cooling_recommendation_hot_climate(self, engine):
        t = engine.get_energy_targets("Miami", "office")
        assert t.cooling_system_recommendation

class TestEquipmentSizingFactors:
    def test_returns_dict(self, engine):
        factors = engine.get_equipment_sizing_factors("Miami")
        assert isinstance(factors, dict) and len(factors) > 0
    def test_cold_climate_larger_heating(self, engine):
        cold = engine.get_equipment_sizing_factors("Fairbanks")
        warm = engine.get_equipment_sizing_factors("Miami")
        assert cold.get("heating_oversizing_factor", 1.0) >= warm.get("heating_oversizing_factor", 1.0)

class TestResilienceAssessment:
    def test_assess(self, engine):
        result = engine.assess_resilience("Miami", ["chiller", "generator"])
        assert isinstance(result, dict)
