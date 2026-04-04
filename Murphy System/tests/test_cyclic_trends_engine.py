"""
Tests for cyclic_trends_engine.py — Round 58

Covers:
  Part 1  — Enum completeness (AutomationType, CyclePhase, WeatherPattern, Season, etc.)
  Part 2  — CyclicSignal dataclass and relative_strength
  Part 3  — CyclicContext construction and properties
  Part 4  — CyclicModifier net_adjustment
  Part 5  — SeasonalCalendar — month profiles
  Part 6  — SeasonalCalendar — hemisphere inversion
  Part 7  — SeasonalCalendar — weather deviation adjustments
  Part 8  — SeasonalCalendar — signal bank completeness
  Part 9  — AutomationCalibrator — single automation calibration
  Part 10 — AutomationCalibrator — calibrate_all returns all types
  Part 11 — All 20 automation types have calibration rules
  Part 12 — CyclicCalibration structure and confidence
  Part 13 — CyclicTrendsEngine — calibrate convenience method
  Part 14 — CyclicTrendsEngine — calibrate_all_for_month
  Part 15 — CyclicTrendsEngine — annual_profile
  Part 16 — Economic and sentiment multipliers
  Part 17 — Weather-sensitive automations (construction, energy, BAS)
  Part 18 — Thread safety and caching
"""

import sys
import os
import threading
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cyclic_trends_engine import (
    AutomationType, CyclePhase, WeatherPattern, Season,
    EconomicPhase, MarketSentiment,
    CyclicSignal, CyclicContext, CyclicModifier, CyclicCalibration,
    SeasonalCalendar, AutomationCalibrator, CyclicTrendsEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return CyclicTrendsEngine()


@pytest.fixture
def calendar():
    return SeasonalCalendar()


@pytest.fixture
def calibrator():
    return AutomationCalibrator()


@pytest.fixture
def october_ctx(calendar):
    return calendar.get_context_for_month(10)


@pytest.fixture
def january_ctx(calendar):
    return calendar.get_context_for_month(1)


@pytest.fixture
def july_ctx(calendar):
    return calendar.get_context_for_month(7)


# ---------------------------------------------------------------------------
# Part 1 — Enum completeness
# ---------------------------------------------------------------------------

class TestEnumCompleteness:
    def test_automation_type_count(self):
        assert len(AutomationType) == 20

    def test_all_key_automation_types_present(self):
        values = {a.value for a in AutomationType}
        expected = {
            "sales_pipeline", "proposal_writer", "estimator",
            "energy_efficiency", "climate_resilience", "construction_operations",
            "talent_acquisition", "marketing_campaigns", "financial_planning",
            "supply_chain", "retail_operations", "scheduling",
            "demand_forecasting", "bas_equipment", "industry_automation",
            "client_psychology", "character_network", "networking_mastery",
            "org_chart_simulator", "historical_greatness",
        }
        assert expected == values

    def test_cycle_phase_count(self):
        assert len(CyclePhase) == 4

    def test_cycle_phase_momentum(self):
        assert CyclePhase.RISING.momentum > 0
        assert CyclePhase.FALLING.momentum < 0
        assert CyclePhase.PEAK.momentum == 0.0
        assert CyclePhase.TROUGH.momentum == 0.0

    def test_weather_pattern_count(self):
        assert len(WeatherPattern) == 8

    def test_season_count(self):
        assert len(Season) == 4

    def test_economic_phase_count(self):
        assert len(EconomicPhase) == 4

    def test_market_sentiment_count(self):
        assert len(MarketSentiment) == 5


# ---------------------------------------------------------------------------
# Part 2 — CyclicSignal dataclass
# ---------------------------------------------------------------------------

class TestCyclicSignal:
    def test_construction(self):
        sig = CyclicSignal(
            signal_id="temperature",
            name="Air Temperature",
            unit="°C",
            current_value=15.0,
            seasonal_normal=13.0,
            deviation=2.0,
            phase=CyclePhase.RISING,
            description="Above normal",
        )
        assert sig.signal_id == "temperature"
        assert sig.deviation == 2.0
        assert sig.phase == CyclePhase.RISING

    def test_relative_strength_positive(self):
        sig = CyclicSignal("t", "T", "°C", 20.0, 13.0, 7.0, CyclePhase.PEAK, "")
        assert sig.relative_strength > 0

    def test_relative_strength_negative(self):
        sig = CyclicSignal("t", "T", "°C", 5.0, 13.0, -8.0, CyclePhase.TROUGH, "")
        assert sig.relative_strength < 0

    def test_relative_strength_clamped(self):
        sig = CyclicSignal("t", "T", "°C", 200.0, 10.0, 190.0, CyclePhase.PEAK, "")
        assert sig.relative_strength <= 1.0

    def test_relative_strength_zero_normal(self):
        sig = CyclicSignal("t", "T", "°C", 5.0, 0.0, 5.0, CyclePhase.RISING, "")
        assert sig.relative_strength == 0.0

    def test_to_dict_keys(self):
        sig = CyclicSignal("t", "Temp", "°C", 15.0, 13.0, 2.0, CyclePhase.RISING, "test")
        d = sig.to_dict()
        for k in ("signal_id", "name", "unit", "current_value",
                  "seasonal_normal", "deviation", "phase", "relative_strength"):
            assert k in d


# ---------------------------------------------------------------------------
# Part 3 — CyclicContext
# ---------------------------------------------------------------------------

class TestCyclicContext:
    def test_month_property(self, october_ctx):
        assert october_ctx.month == 10

    def test_quarter_property(self, october_ctx):
        assert october_ctx.quarter == 4

    def test_january_is_winter(self, january_ctx):
        assert january_ctx.season == Season.WINTER

    def test_july_is_summer(self, july_ctx):
        assert july_ctx.season == Season.SUMMER

    def test_october_is_autumn(self, october_ctx):
        assert october_ctx.season == Season.AUTUMN

    def test_signals_are_list(self, october_ctx):
        assert isinstance(october_ctx.signals, list)
        assert len(october_ctx.signals) >= 4

    def test_all_indices_in_range(self, october_ctx):
        assert 0.0 <= october_ctx.risk_appetite <= 1.0
        assert 0.0 <= october_ctx.decision_velocity <= 1.0
        assert 0.0 <= october_ctx.energy_demand <= 1.0
        assert 0.0 <= october_ctx.outdoor_activity <= 1.0
        assert 0.0 <= october_ctx.consumer_optimism <= 1.0

    def test_activity_index_positive(self, october_ctx):
        assert october_ctx.activity_index > 0

    def test_to_dict_keys(self, october_ctx):
        d = october_ctx.to_dict()
        for k in ("snapshot_date", "season", "weather_pattern",
                  "economic_phase", "market_sentiment",
                  "activity_index", "risk_appetite", "decision_velocity",
                  "energy_demand", "outdoor_activity", "consumer_optimism",
                  "signals"):
            assert k in d


# ---------------------------------------------------------------------------
# Part 4 — CyclicModifier
# ---------------------------------------------------------------------------

class TestCyclicModifier:
    def test_positive_net_adjustment(self):
        m = CyclicModifier("param", +1.0, 0.20, "test")
        assert m.net_adjustment > 0

    def test_negative_net_adjustment(self):
        m = CyclicModifier("param", -1.0, 0.20, "test")
        assert m.net_adjustment < 0

    def test_zero_magnitude_zero_adjustment(self):
        m = CyclicModifier("param", +1.0, 0.0, "test")
        assert m.net_adjustment == 0.0

    def test_to_dict_keys(self):
        m = CyclicModifier("outbound_cadence", +1.0, 0.15, "activity high")
        d = m.to_dict()
        assert "parameter" in d
        assert "net_adjustment" in d
        assert "rationale" in d


# ---------------------------------------------------------------------------
# Part 5 — SeasonalCalendar month profiles
# ---------------------------------------------------------------------------

class TestSeasonalCalendarMonths:
    def test_all_months_return_context(self, calendar):
        for month in range(1, 13):
            ctx = calendar.get_context_for_month(month)
            assert isinstance(ctx, CyclicContext)

    def test_summer_higher_outdoor_activity_than_winter(self, calendar):
        summer = calendar.get_context_for_month(7)
        winter = calendar.get_context_for_month(1)
        assert summer.outdoor_activity > winter.outdoor_activity

    def test_december_low_activity(self, calendar):
        dec = calendar.get_context_for_month(12)
        oct = calendar.get_context_for_month(10)
        assert dec.activity_index < oct.activity_index

    def test_peak_business_months(self, calendar):
        """October should have higher activity than August"""
        aug = calendar.get_context_for_month(8)
        oct = calendar.get_context_for_month(10)
        assert oct.activity_index >= aug.activity_index

    def test_winter_high_energy_demand(self, calendar):
        jan = calendar.get_context_for_month(1)
        may = calendar.get_context_for_month(5)
        assert jan.energy_demand > may.energy_demand

    def test_summer_low_risk_appetite_relative_to_spring(self, calendar):
        """Hot August has lower decision velocity than May"""
        may = calendar.get_context_for_month(5)
        aug = calendar.get_context_for_month(8)
        assert may.decision_velocity >= aug.decision_velocity


# ---------------------------------------------------------------------------
# Part 6 — Hemisphere inversion
# ---------------------------------------------------------------------------

class TestHemisphereInversion:
    def test_southern_july_is_winter(self):
        cal = SeasonalCalendar(hemisphere="southern")
        ctx = cal.get_context_for_month(7)
        assert ctx.season == Season.WINTER

    def test_southern_january_is_summer(self):
        cal = SeasonalCalendar(hemisphere="southern")
        ctx = cal.get_context_for_month(1)
        assert ctx.season == Season.SUMMER

    def test_northern_default_july_is_summer(self):
        cal = SeasonalCalendar(hemisphere="northern")
        ctx = cal.get_context_for_month(7)
        assert ctx.season == Season.SUMMER


# ---------------------------------------------------------------------------
# Part 7 — Weather deviation adjustments
# ---------------------------------------------------------------------------

class TestWeatherDeviations:
    def test_heavy_rain_triggers_wet_rainy(self, calendar):
        ctx = calendar.get_context_for_month(5, precipitation_deviation=60.0)
        assert ctx.weather_pattern == WeatherPattern.WET_RAINY

    def test_extreme_rain_triggers_stormy(self, calendar):
        ctx = calendar.get_context_for_month(5, precipitation_deviation=100.0)
        assert ctx.weather_pattern == WeatherPattern.STORMY

    def test_drought_condition(self, calendar):
        ctx = calendar.get_context_for_month(8, precipitation_deviation=-60.0)
        assert ctx.weather_pattern == WeatherPattern.DRY_DROUGHT

    def test_heat_wave_in_spring(self, calendar):
        ctx = calendar.get_context_for_month(4, temperature_deviation=8.0)
        assert ctx.weather_pattern == WeatherPattern.WARM_SUNNY

    def test_cold_snap_in_april(self, calendar):
        ctx = calendar.get_context_for_month(4, temperature_deviation=-8.0)
        assert ctx.weather_pattern == WeatherPattern.COLD_GREY


# ---------------------------------------------------------------------------
# Part 8 — Signal bank completeness
# ---------------------------------------------------------------------------

class TestSignalBank:
    def test_signals_include_temperature(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "temperature" in ids

    def test_signals_include_precipitation(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "precipitation" in ids

    def test_signals_include_daylight(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "daylight_hours" in ids

    def test_signals_include_business_activity(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "business_activity" in ids

    def test_signals_include_consumer_spending(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "consumer_spending" in ids

    def test_signals_include_hvac(self, october_ctx):
        ids = {s.signal_id for s in october_ctx.signals}
        assert "hvac_demand" in ids

    def test_all_signal_phases_valid(self, october_ctx):
        for sig in october_ctx.signals:
            assert sig.phase in CyclePhase


# ---------------------------------------------------------------------------
# Part 9 — AutomationCalibrator single type
# ---------------------------------------------------------------------------

class TestAutomationCalibrator:
    def test_returns_calibration_object(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.SALES_PIPELINE, october_ctx)
        assert isinstance(cal, CyclicCalibration)

    def test_automation_type_preserved(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.ENERGY_EFFICIENCY, october_ctx)
        assert cal.automation_type == AutomationType.ENERGY_EFFICIENCY

    def test_adjusted_params_all_in_range(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.CONSTRUCTION_OPERATIONS, october_ctx)
        for param, val in cal.adjusted_params.items():
            assert 0.0 <= val <= 1.0, f"{param} = {val} out of range"

    def test_modifiers_are_list(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.FINANCIAL_PLANNING, october_ctx)
        assert isinstance(cal.modifiers, list)
        assert len(cal.modifiers) >= 1

    def test_notes_are_list(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.MARKETING_CAMPAIGNS, october_ctx)
        assert isinstance(cal.notes, list)
        assert len(cal.notes) >= 1

    def test_confidence_in_range(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.SALES_PIPELINE, october_ctx)
        assert 0.0 < cal.confidence <= 1.0

    def test_custom_baseline_params(self, calibrator, october_ctx):
        custom = {"outbound_cadence": 0.50, "deal_urgency_score": 0.50}
        cal = calibrator.calibrate(AutomationType.SALES_PIPELINE, october_ctx, custom)
        assert "outbound_cadence" in cal.adjusted_params

    def test_largest_adjustment_returns_modifier(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.SALES_PIPELINE, october_ctx)
        adj = cal.largest_adjustment
        assert adj is not None
        assert isinstance(adj, CyclicModifier)


# ---------------------------------------------------------------------------
# Part 10 — AutomationCalibrator.calibrate_all
# ---------------------------------------------------------------------------

class TestCalibrateAll:
    def test_calibrate_all_returns_20_types(self, calibrator, october_ctx):
        result = calibrator.calibrate_all(october_ctx)
        assert len(result) == 20

    def test_calibrate_all_keys_are_automation_types(self, calibrator, october_ctx):
        result = calibrator.calibrate_all(october_ctx)
        for at in AutomationType:
            assert at in result

    def test_calibrate_all_values_are_calibrations(self, calibrator, october_ctx):
        result = calibrator.calibrate_all(october_ctx)
        for at, cal in result.items():
            assert isinstance(cal, CyclicCalibration)
            assert cal.automation_type == at


# ---------------------------------------------------------------------------
# Part 11 — All 20 automation types have calibration rules
# ---------------------------------------------------------------------------

class TestAllAutomationTypesHaveRules:
    def test_each_type_produces_at_least_one_modifier(self, calibrator, october_ctx):
        for at in AutomationType:
            cal = calibrator.calibrate(at, october_ctx)
            assert len(cal.modifiers) >= 1, f"{at.value} has no modifiers"

    def test_each_type_produces_adjusted_params(self, calibrator, october_ctx):
        for at in AutomationType:
            cal = calibrator.calibrate(at, october_ctx)
            assert len(cal.adjusted_params) >= 1, f"{at.value} has no adjusted params"


# ---------------------------------------------------------------------------
# Part 12 — CyclicCalibration structure
# ---------------------------------------------------------------------------

class TestCyclicCalibrationStructure:
    def test_to_dict_keys(self, calibrator, october_ctx):
        cal = calibrator.calibrate(AutomationType.RETAIL_OPERATIONS, october_ctx)
        d = cal.to_dict()
        for k in ("automation_type", "context", "baseline_params",
                  "adjusted_params", "modifiers", "notes", "confidence"):
            assert k in d

    def test_adjusted_params_differ_from_baseline(self, calibrator):
        # Use a month with strong cyclic signal (January contraction)
        cal_jan = SeasonalCalendar()
        ctx = cal_jan.get_context_for_month(
            1,
            economic_phase=EconomicPhase.CONTRACTION,
            market_sentiment=MarketSentiment.FEARFUL,
        )
        cal = calibrator.calibrate(AutomationType.SALES_PIPELINE, ctx)
        # At least some params should differ from default 0.70 baseline
        differing = sum(1 for k, v in cal.adjusted_params.items()
                        if abs(v - cal.baseline_params.get(k, 0.70)) > 0.01)
        assert differing >= 1

    def test_stormy_weather_lower_confidence(self, calibrator):
        cal_s = SeasonalCalendar()
        ctx = cal_s.get_context_for_month(8, precipitation_deviation=100.0)
        cal = calibrator.calibrate(AutomationType.CONSTRUCTION_OPERATIONS, ctx)
        # Stormy context should have lower confidence
        assert cal.confidence <= 0.75


# ---------------------------------------------------------------------------
# Part 13 — CyclicTrendsEngine.calibrate
# ---------------------------------------------------------------------------

class TestCyclicTrendsEngineCalibrate:
    def test_calibrate_by_month(self, engine):
        cal = engine.calibrate(AutomationType.SALES_PIPELINE, month=10)
        assert isinstance(cal, CyclicCalibration)
        assert cal.automation_type == AutomationType.SALES_PIPELINE

    def test_calibrate_by_date(self, engine):
        d = date(2026, 3, 15)
        cal = engine.calibrate(AutomationType.ENERGY_EFFICIENCY, target_date=d)
        assert cal.context.month == 3

    def test_calibrate_uses_today_if_no_date(self, engine):
        cal = engine.calibrate(AutomationType.SCHEDULING)
        assert isinstance(cal, CyclicCalibration)

    def test_calibrate_contraction_lowers_sales_params(self, engine):
        cal_exp  = engine.calibrate(
            AutomationType.SALES_PIPELINE, month=10,
            economic_phase=EconomicPhase.EXPANSION,
            market_sentiment=MarketSentiment.OPTIMISTIC,
        )
        cal_cont = engine.calibrate(
            AutomationType.SALES_PIPELINE, month=10,
            economic_phase=EconomicPhase.CONTRACTION,
            market_sentiment=MarketSentiment.FEARFUL,
        )
        # Contraction should produce lower close_rate_forecast
        cr_exp  = cal_exp.adjusted_params.get("close_rate_forecast", 0.70)
        cr_cont = cal_cont.adjusted_params.get("close_rate_forecast", 0.70)
        assert cr_cont <= cr_exp

    def test_calibrate_returns_all_types_for_extreme_weather(self, engine):
        cal = engine.calibrate(
            AutomationType.CONSTRUCTION_OPERATIONS,
            month=1,
            temperature_deviation=-10.0,
            precipitation_deviation=80.0,
        )
        assert 0.0 <= cal.adjusted_params.get("field_productivity", 0.5) <= 1.0


# ---------------------------------------------------------------------------
# Part 14 — CyclicTrendsEngine.calibrate_all_for_month
# ---------------------------------------------------------------------------

class TestCalibrateAllForMonth:
    def test_returns_20_entries(self, engine):
        result = engine.calibrate_all_for_month(7)
        assert len(result) == 20

    def test_all_types_present(self, engine):
        result = engine.calibrate_all_for_month(4)
        for at in AutomationType:
            assert at in result

    def test_contraction_affects_financial_planning(self, engine):
        exp  = engine.calibrate_all_for_month(10, EconomicPhase.EXPANSION)
        cont = engine.calibrate_all_for_month(10, EconomicPhase.CONTRACTION)
        fp_exp  = exp[AutomationType.FINANCIAL_PLANNING].adjusted_params.get("budget_confidence", 0.70)
        fp_cont = cont[AutomationType.FINANCIAL_PLANNING].adjusted_params.get("budget_confidence", 0.70)
        assert fp_cont <= fp_exp


# ---------------------------------------------------------------------------
# Part 15 — CyclicTrendsEngine.annual_profile
# ---------------------------------------------------------------------------

class TestAnnualProfile:
    def test_returns_12_months(self, engine):
        profile = engine.annual_profile(AutomationType.ENERGY_EFFICIENCY)
        assert len(profile) == 12

    def test_all_months_present(self, engine):
        profile = engine.annual_profile(AutomationType.RETAIL_OPERATIONS)
        months = [p["month"] for p in profile]
        assert sorted(months) == list(range(1, 13))

    def test_each_entry_has_required_keys(self, engine):
        profile = engine.annual_profile(AutomationType.CONSTRUCTION_OPERATIONS)
        for entry in profile:
            assert "month" in entry
            assert "season" in entry
            assert "weather_pattern" in entry
            assert "adjusted_params" in entry

    def test_hvac_demand_higher_in_jan_than_jun(self, engine):
        profile = engine.annual_profile(AutomationType.ENERGY_EFFICIENCY)
        jan_hvac = profile[0]["adjusted_params"].get("hvac_load_factor", 0.5)
        jun_hvac = profile[5]["adjusted_params"].get("hvac_load_factor", 0.5)
        assert jan_hvac >= jun_hvac


# ---------------------------------------------------------------------------
# Part 16 — Economic and sentiment multipliers
# ---------------------------------------------------------------------------

class TestEconomicAndSentimentMultipliers:
    def test_expansion_higher_activity_than_contraction(self, calendar):
        exp  = calendar.get_context_for_month(5, economic_phase=EconomicPhase.EXPANSION)
        cont = calendar.get_context_for_month(5, economic_phase=EconomicPhase.CONTRACTION)
        assert exp.activity_index > cont.activity_index

    def test_euphoric_higher_risk_appetite_than_fearful(self, calendar):
        eup  = calendar.get_context_for_month(5, market_sentiment=MarketSentiment.EUPHORIC)
        fear = calendar.get_context_for_month(5, market_sentiment=MarketSentiment.FEARFUL)
        assert eup.risk_appetite > fear.risk_appetite

    def test_optimistic_higher_decision_velocity_than_cautious(self, calendar):
        opt  = calendar.get_context_for_month(5, market_sentiment=MarketSentiment.OPTIMISTIC)
        caut = calendar.get_context_for_month(5, market_sentiment=MarketSentiment.CAUTIOUS)
        assert opt.decision_velocity > caut.decision_velocity


# ---------------------------------------------------------------------------
# Part 17 — Weather-sensitive automations
# ---------------------------------------------------------------------------

class TestWeatherSensitiveAutomations:
    def test_construction_productivity_lower_in_stormy(self, engine):
        normal = engine.calibrate(
            AutomationType.CONSTRUCTION_OPERATIONS, month=6
        )
        stormy = engine.calibrate(
            AutomationType.CONSTRUCTION_OPERATIONS, month=6,
            precipitation_deviation=100.0,
        )
        norm_prod  = normal.adjusted_params.get("field_productivity", 0.70)
        storm_prod = stormy.adjusted_params.get("field_productivity", 0.70)
        assert storm_prod <= norm_prod

    def test_energy_hvac_higher_in_january(self, engine):
        jan = engine.calibrate(AutomationType.ENERGY_EFFICIENCY, month=1)
        jun = engine.calibrate(AutomationType.ENERGY_EFFICIENCY, month=6)
        jan_hvac = jan.adjusted_params.get("hvac_load_factor", 0.5)
        jun_hvac = jun.adjusted_params.get("hvac_load_factor", 0.5)
        assert jan_hvac >= jun_hvac

    def test_climate_resilience_flood_risk_with_heavy_rain(self, engine):
        dry   = engine.calibrate(
            AutomationType.CLIMATE_RESILIENCE, month=5,
            precipitation_deviation=-30.0,
        )
        flood = engine.calibrate(
            AutomationType.CLIMATE_RESILIENCE, month=5,
            precipitation_deviation=80.0,
        )
        dry_flood   = dry.adjusted_params.get("flood_risk_score", 0.5)
        heavy_flood = flood.adjusted_params.get("flood_risk_score", 0.5)
        assert heavy_flood >= dry_flood

    def test_bas_lighting_schedule_higher_in_winter(self, engine):
        jan = engine.calibrate(AutomationType.BAS_EQUIPMENT, month=1)
        jun = engine.calibrate(AutomationType.BAS_EQUIPMENT, month=6)
        jan_light = jan.adjusted_params.get("lighting_schedule", 0.5)
        jun_light = jun.adjusted_params.get("lighting_schedule", 0.5)
        # Winter has fewer daylight hours → lighting automation runs more
        assert jan_light >= jun_light


# ---------------------------------------------------------------------------
# Part 18 — Thread safety and caching
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_calibrate(self):
        engine  = CyclicTrendsEngine()
        results = []
        errors  = []

        def run(i):
            try:
                month = (i % 12) + 1
                cal   = engine.calibrate(
                    AutomationType.SALES_PIPELINE,
                    month=month,
                    economic_phase=EconomicPhase.EXPANSION,
                    market_sentiment=MarketSentiment.OPTIMISTIC,
                )
                results.append(cal)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(results) == 12

    def test_cache_hit_returns_same_object(self, engine):
        cal1 = engine.calibrate(
            AutomationType.ENERGY_EFFICIENCY,
            month=3,
            economic_phase=EconomicPhase.EXPANSION,
            market_sentiment=MarketSentiment.OPTIMISTIC,
        )
        cal2 = engine.calibrate(
            AutomationType.ENERGY_EFFICIENCY,
            month=3,
            economic_phase=EconomicPhase.EXPANSION,
            market_sentiment=MarketSentiment.OPTIMISTIC,
        )
        # Same parameters → same cached object
        assert cal1 is cal2

    def test_describe_context(self, engine):
        ctx = engine.get_context(month=7)
        desc = engine.describe_context(ctx)
        assert isinstance(desc, str)
        assert "Summer" in desc or "summer" in desc.lower()

    def test_all_automation_types_list(self, engine):
        types = engine.all_automation_types()
        assert len(types) == 20
        assert all(isinstance(t, AutomationType) for t in types)
