"""
Cyclic Trends Engine — Murphy System
======================================

Injects cyclic environmental signals — weather patterns, seasonal rhythms,
economic cycles, daylight / circadian cycles, market sentiment cycles,
and cultural calendars — into every Murphy System automation type.

Every business process has a cyclic dimension that most automation ignores:
  • Sales pipelines slow in August and December regardless of strategy.
  • Energy consumption peaks in January and July regardless of efficiency.
  • Talent recruitment accelerates in Q1 regardless of headcount plan.
  • Client psychology shifts with weather — cold, grey days produce risk-aversion;
    warm, bright days correlate with optimism and deal velocity.
  • Construction and real-estate activity follows precipitation and temperature.
  • Retail follows cultural calendars: back-to-school, holiday, tax-refund.

This engine provides:

  CyclicSignal         — A single time-varying input (temperature, rainfall, etc.)
  CyclicPattern        — A named multi-signal pattern that recurs predictably
  AutomationType       — The 20 Murphy System automation types that consume cycles
  CyclePhase           — Current position in a cycle (RISING, PEAK, FALLING, TROUGH)
  CyclicContext        — Snapshot of all active cyclic signals at a given moment
  CyclicModifier       — How a cyclic context adjusts an automation parameter
  CyclicCalibration    — Per-automation-type adjusted parameters + justification
  WeatherSignalBank    — Canonical weather / climate signal definitions
  SeasonalCalendar     — Month-by-month multi-dimensional cycle profile
  CyclicTrendsEngine   — Top-level façade: calibrate any automation for any date/context

Design Label: CTE-001 — Cyclic Trends Engine
Owner:        Platform Engineering / Agent Intelligence
License:      BSL 1.1

Copyright © 2020 Inoni Limited Liability Company
Creator:      Corey Post
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AutomationType(str, Enum):
    """All Murphy System automation types that accept cyclic trend inputs."""
    SALES_PIPELINE          = "sales_pipeline"
    PROPOSAL_WRITER         = "proposal_writer"
    ESTIMATOR               = "estimator"
    ORG_CHART_SIMULATOR     = "org_chart_simulator"
    CLIENT_PSYCHOLOGY       = "client_psychology"
    CHARACTER_NETWORK       = "character_network"
    NETWORKING_MASTERY      = "networking_mastery"
    HISTORICAL_GREATNESS    = "historical_greatness"
    ENERGY_EFFICIENCY       = "energy_efficiency"
    CLIMATE_RESILIENCE      = "climate_resilience"
    INDUSTRY_AUTOMATION     = "industry_automation"
    BAS_EQUIPMENT           = "bas_equipment"
    SCHEDULING              = "scheduling"
    DEMAND_FORECASTING      = "demand_forecasting"
    TALENT_ACQUISITION      = "talent_acquisition"
    MARKETING_CAMPAIGNS     = "marketing_campaigns"
    FINANCIAL_PLANNING      = "financial_planning"
    SUPPLY_CHAIN            = "supply_chain"
    CONSTRUCTION_OPERATIONS = "construction_operations"
    RETAIL_OPERATIONS       = "retail_operations"


class CyclePhase(str, Enum):
    """Position within a repeating cycle."""
    RISING  = "rising"    # Increasing toward peak
    PEAK    = "peak"      # At or near maximum
    FALLING = "falling"   # Decreasing from peak
    TROUGH  = "trough"    # At or near minimum

    @property
    def momentum(self) -> float:
        """Directional momentum: +1 = accelerating up, -1 = accelerating down."""
        return {"rising": 0.75, "peak": 0.0, "falling": -0.75, "trough": 0.0}[self.value]


class WeatherPattern(str, Enum):
    """Broad weather pattern categories with distinct behavioral correlates."""
    WARM_SUNNY    = "warm_sunny"      # Optimism, activity, risk-taking
    HOT_HUMID     = "hot_humid"       # Fatigue, urgency reduction, discomfort
    MILD_OVERCAST = "mild_overcast"   # Neutral; analytical mode
    COLD_CLEAR    = "cold_clear"      # Focus, indoor productivity
    COLD_GREY     = "cold_grey"       # Risk-aversion, deliberation, caution
    WET_RAINY     = "wet_rainy"       # Introspection, planning, slower pace
    STORMY        = "stormy"          # Disruption, urgency, crisis mode
    DRY_DROUGHT   = "dry_drought"     # Scarcity mindset, cost-consciousness


class Season(str, Enum):
    SPRING = "spring"   # Mar–May (Northern Hemisphere)
    SUMMER = "summer"   # Jun–Aug
    AUTUMN = "autumn"   # Sep–Nov
    WINTER = "winter"   # Dec–Feb


class EconomicPhase(str, Enum):
    EXPANSION    = "expansion"    # GDP rising, employment up, confidence high
    PEAK         = "peak"         # Maximum activity, inflationary pressure
    CONTRACTION  = "contraction"  # GDP falling, employment softening
    TROUGH       = "trough"       # Minimum activity, recovery beginning


class MarketSentiment(str, Enum):
    EUPHORIC    = "euphoric"     # Risk appetite maximum
    OPTIMISTIC  = "optimistic"   # Constructive; deals flow easily
    NEUTRAL     = "neutral"      # Mixed signals
    CAUTIOUS    = "cautious"     # Defensive posture; longer cycle times
    FEARFUL     = "fearful"      # Risk-off; deals freeze


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CyclicSignal:
    """A single measurable cyclic input."""
    signal_id:       str
    name:            str
    unit:            str          # e.g., "°C", "mm/month", "daylight hours"
    current_value:   float
    seasonal_normal: float        # long-run average for this month
    deviation:       float        # current_value - seasonal_normal
    phase:           CyclePhase
    description:     str

    @property
    def relative_strength(self) -> float:
        """How far current is from normal, normalised to [-1, 1]."""
        if self.seasonal_normal == 0:
            return 0.0
        return max(-1.0, min(1.0, self.deviation / max(abs(self.seasonal_normal), 1.0)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id":       self.signal_id,
            "name":            self.name,
            "unit":            self.unit,
            "current_value":   self.current_value,
            "seasonal_normal": self.seasonal_normal,
            "deviation":       self.deviation,
            "phase":           self.phase.value,
            "relative_strength": self.relative_strength,
            "description":     self.description,
        }


@dataclass
class CyclicContext:
    """
    A complete snapshot of all active cyclic signals at a specific moment.

    This is the object passed to every automation type to adjust its behaviour.
    """
    snapshot_date:      date
    season:             Season
    weather_pattern:    WeatherPattern
    economic_phase:     EconomicPhase
    market_sentiment:   MarketSentiment
    signals:            List[CyclicSignal]

    # Aggregate indices
    activity_index:     float = 1.0   # 0=minimum activity, 1=normal, 2=peak activity
    risk_appetite:      float = 0.5   # 0=risk-off, 1=risk-on
    decision_velocity:  float = 0.5   # 0=very slow decisions, 1=fast
    energy_demand:      float = 0.5   # 0=minimum, 1=maximum demand
    outdoor_activity:   float = 0.5   # 0=indoor/sedentary, 1=outdoor/active
    consumer_optimism:  float = 0.5   # 0=pessimistic, 1=optimistic

    @property
    def month(self) -> int:
        return self.snapshot_date.month

    @property
    def quarter(self) -> int:
        return (self.snapshot_date.month - 1) // 3 + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_date":    self.snapshot_date.isoformat(),
            "season":           self.season.value,
            "weather_pattern":  self.weather_pattern.value,
            "economic_phase":   self.economic_phase.value,
            "market_sentiment": self.market_sentiment.value,
            "activity_index":   round(self.activity_index, 4),
            "risk_appetite":    round(self.risk_appetite, 4),
            "decision_velocity": round(self.decision_velocity, 4),
            "energy_demand":    round(self.energy_demand, 4),
            "outdoor_activity": round(self.outdoor_activity, 4),
            "consumer_optimism": round(self.consumer_optimism, 4),
            "signals":          [s.to_dict() for s in self.signals],
        }


@dataclass(frozen=True)
class CyclicModifier:
    """
    How a cyclic context adjusts one parameter of one automation type.

    direction:   +1 = cycle increases this parameter, -1 = decreases
    magnitude:   0–1 scale of the adjustment
    rationale:   plain-language explanation
    """
    parameter:  str
    direction:  float   # +1.0 to -1.0
    magnitude:  float   # 0.0 to 1.0
    rationale:  str

    @property
    def net_adjustment(self) -> float:
        """Signed adjustment to add to a baseline 0–1 score."""
        return round(self.direction * self.magnitude, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter":     self.parameter,
            "direction":     self.direction,
            "magnitude":     self.magnitude,
            "net_adjustment": self.net_adjustment,
            "rationale":     self.rationale,
        }


@dataclass
class CyclicCalibration:
    """
    A fully calibrated automation configuration adjusted for the current cycle.

    baseline_params:  the automation's default parameters (0–1 scores)
    adjusted_params:  parameters after cyclic modifiers applied
    modifiers:        the modifiers that were applied
    context:          the cyclic context used
    notes:            human-readable summary of the most significant adjustments
    """
    automation_type:  AutomationType
    context:          CyclicContext
    baseline_params:  Dict[str, float]
    adjusted_params:  Dict[str, float]
    modifiers:        List[CyclicModifier]
    notes:            List[str]
    confidence:       float   # 0–1: how reliable is this calibration

    @property
    def largest_adjustment(self) -> Optional[CyclicModifier]:
        if not self.modifiers:
            return None
        return max(self.modifiers, key=lambda m: abs(m.net_adjustment))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_type": self.automation_type.value,
            "context":         self.context.to_dict(),
            "baseline_params": self.baseline_params,
            "adjusted_params": self.adjusted_params,
            "modifiers":       [m.to_dict() for m in self.modifiers],
            "notes":           self.notes,
            "confidence":      round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Seasonal Calendar — month-by-month multi-dimensional profile
# ---------------------------------------------------------------------------

# Each month entry: (season, weather_pattern, activity_index, risk_appetite,
#                    decision_velocity, energy_demand, outdoor_activity, consumer_optimism)
# Values are Northern Hemisphere defaults (can be overridden for locale)

_MONTHLY_PROFILES: Dict[int, Tuple] = {
    1:  (Season.WINTER, WeatherPattern.COLD_GREY,    0.75, 0.35, 0.45, 0.90, 0.25, 0.40),
    2:  (Season.WINTER, WeatherPattern.COLD_GREY,    0.80, 0.40, 0.50, 0.85, 0.30, 0.42),
    3:  (Season.SPRING, WeatherPattern.MILD_OVERCAST,0.95, 0.55, 0.60, 0.70, 0.55, 0.58),
    4:  (Season.SPRING, WeatherPattern.WARM_SUNNY,   1.10, 0.65, 0.70, 0.60, 0.70, 0.68),
    5:  (Season.SPRING, WeatherPattern.WARM_SUNNY,   1.15, 0.70, 0.72, 0.55, 0.80, 0.72),
    6:  (Season.SUMMER, WeatherPattern.WARM_SUNNY,   1.10, 0.68, 0.68, 0.65, 0.85, 0.70),
    7:  (Season.SUMMER, WeatherPattern.HOT_HUMID,    0.90, 0.55, 0.55, 0.80, 0.75, 0.62),
    8:  (Season.SUMMER, WeatherPattern.HOT_HUMID,    0.80, 0.50, 0.45, 0.82, 0.70, 0.58),
    9:  (Season.AUTUMN, WeatherPattern.MILD_OVERCAST,1.05, 0.65, 0.68, 0.65, 0.60, 0.65),
    10: (Season.AUTUMN, WeatherPattern.COLD_CLEAR,   1.10, 0.68, 0.72, 0.68, 0.50, 0.66),
    11: (Season.AUTUMN, WeatherPattern.COLD_GREY,    0.95, 0.55, 0.60, 0.78, 0.35, 0.55),
    12: (Season.WINTER, WeatherPattern.COLD_GREY,    0.75, 0.40, 0.42, 0.88, 0.25, 0.50),
}


class SeasonalCalendar:
    """
    Provides month-by-month cyclic context profiles.

    Adjustable for hemisphere (Southern Hemisphere inverts seasons by 6 months)
    and for climate zone (tropical, arid, etc.).
    """

    def __init__(self, hemisphere: str = "northern") -> None:
        self.hemisphere = hemisphere.lower()

    def get_context_for_month(
        self,
        month: int,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
        temperature_deviation: float = 0.0,    # °C above/below normal
        precipitation_deviation: float = 0.0,  # mm/month above/below normal
    ) -> CyclicContext:
        """
        Build a CyclicContext for a given month and optional deviations.

        Parameters
        ----------
        month:                   1–12
        economic_phase:          current economic cycle phase
        market_sentiment:        current market sentiment
        temperature_deviation:   how much warmer/colder than seasonal normal (°C)
        precipitation_deviation: how much wetter/drier than normal (mm/month)
        """
        adj_month = month
        if self.hemisphere == "southern":
            adj_month = ((month + 5) % 12) + 1

        profile = _MONTHLY_PROFILES.get(adj_month, _MONTHLY_PROFILES[1])
        (season, base_weather, act_idx, risk_app,
         dec_vel, energy_dem, outdoor, optimism) = profile

        # Apply temperature deviation
        weather = self._adjust_weather(base_weather, temperature_deviation, precipitation_deviation)

        # Adjust indices for economic phase
        econ_mult = self._economic_multiplier(economic_phase)
        sent_mult = self._sentiment_multiplier(market_sentiment)

        signals = self._build_signals(
            month=adj_month,
            temp_deviation=temperature_deviation,
            precip_deviation=precipitation_deviation,
        )

        return CyclicContext(
            snapshot_date=date(date.today().year, month, 15),
            season=season,
            weather_pattern=weather,
            economic_phase=economic_phase,
            market_sentiment=market_sentiment,
            signals=signals,
            activity_index=min(2.0, max(0.0, act_idx * econ_mult)),
            risk_appetite=min(1.0, max(0.0, risk_app * sent_mult)),
            decision_velocity=min(1.0, max(0.0, dec_vel * sent_mult)),
            energy_demand=min(1.0, max(0.0, energy_dem)),
            outdoor_activity=min(1.0, max(0.0, outdoor)),
            consumer_optimism=min(1.0, max(0.0, optimism * sent_mult)),
        )

    def get_context_for_date(
        self,
        target_date: date,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
        temperature_deviation: float = 0.0,
        precipitation_deviation: float = 0.0,
    ) -> CyclicContext:
        """Build a CyclicContext for a specific calendar date."""
        ctx = self.get_context_for_month(
            month=target_date.month,
            economic_phase=economic_phase,
            market_sentiment=market_sentiment,
            temperature_deviation=temperature_deviation,
            precipitation_deviation=precipitation_deviation,
        )
        # Replace date in context
        return CyclicContext(
            snapshot_date=target_date,
            season=ctx.season,
            weather_pattern=ctx.weather_pattern,
            economic_phase=ctx.economic_phase,
            market_sentiment=ctx.market_sentiment,
            signals=ctx.signals,
            activity_index=ctx.activity_index,
            risk_appetite=ctx.risk_appetite,
            decision_velocity=ctx.decision_velocity,
            energy_demand=ctx.energy_demand,
            outdoor_activity=ctx.outdoor_activity,
            consumer_optimism=ctx.consumer_optimism,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _adjust_weather(
        self,
        base: WeatherPattern,
        temp_dev: float,
        precip_dev: float,
    ) -> WeatherPattern:
        if precip_dev > 30:
            return WeatherPattern.STORMY if precip_dev > 80 else WeatherPattern.WET_RAINY
        if precip_dev < -40:
            return WeatherPattern.DRY_DROUGHT
        if temp_dev > 5:
            return WeatherPattern.HOT_HUMID if base in (WeatherPattern.WARM_SUNNY,) else WeatherPattern.WARM_SUNNY
        if temp_dev < -5:
            return WeatherPattern.COLD_GREY
        return base

    def _economic_multiplier(self, phase: EconomicPhase) -> float:
        return {
            EconomicPhase.EXPANSION:   1.15,
            EconomicPhase.PEAK:        1.10,
            EconomicPhase.CONTRACTION: 0.85,
            EconomicPhase.TROUGH:      0.75,
        }[phase]

    def _sentiment_multiplier(self, sentiment: MarketSentiment) -> float:
        return {
            MarketSentiment.EUPHORIC:   1.20,
            MarketSentiment.OPTIMISTIC: 1.05,
            MarketSentiment.NEUTRAL:    1.00,
            MarketSentiment.CAUTIOUS:   0.90,
            MarketSentiment.FEARFUL:    0.75,
        }[sentiment]

    def _build_signals(
        self,
        month: int,
        temp_deviation: float,
        precip_deviation: float,
    ) -> List[CyclicSignal]:
        """Build the canonical signal list for a month."""
        # Seasonal temperature normals (°C, mid-latitude temperate)
        temp_normals = {
            1: 2, 2: 4, 3: 8, 4: 13, 5: 17, 6: 21,
            7: 24, 8: 23, 9: 18, 10: 13, 11: 7, 12: 3,
        }
        # Seasonal precipitation normals (mm/month)
        precip_normals = {
            1: 55, 2: 45, 3: 50, 4: 45, 5: 50, 6: 55,
            7: 50, 8: 55, 9: 50, 10: 60, 11: 65, 12: 60,
        }
        # Daylight hours (mid-latitude)
        daylight_normals = {
            1: 8.5, 2: 10.0, 3: 12.0, 4: 14.0, 5: 15.5, 6: 16.5,
            7: 16.0, 8: 14.5, 9: 12.5, 10: 10.5, 11: 9.0, 12: 8.0,
        }
        # Business activity index (1 = typical)
        business_normals = {
            1: 0.85, 2: 0.90, 3: 0.95, 4: 1.05, 5: 1.10, 6: 1.05,
            7: 0.90, 8: 0.85, 9: 1.10, 10: 1.15, 11: 1.00, 12: 0.80,
        }
        # Consumer spending index
        consumer_normals = {
            1: 0.90, 2: 0.88, 3: 0.92, 4: 0.95, 5: 0.98, 6: 1.00,
            7: 1.02, 8: 1.00, 9: 1.05, 10: 1.08, 11: 1.15, 12: 1.30,
        }
        # Heating/cooling demand index
        hvac_normals = {
            1: 1.00, 2: 0.95, 3: 0.70, 4: 0.45, 5: 0.35, 6: 0.50,
            7: 0.80, 8: 0.85, 9: 0.50, 10: 0.45, 11: 0.70, 12: 0.90,
        }

        t_norm = temp_normals[month]
        p_norm = precip_normals[month]
        t_cur  = t_norm + temp_deviation
        p_cur  = p_norm + precip_deviation

        def _phase(dev: float, norm: float) -> CyclePhase:
            ratio = dev / max(abs(norm), 1.0)
            if ratio > 0.20:
                return CyclePhase.PEAK
            if ratio > 0:
                return CyclePhase.RISING
            if ratio < -0.20:
                return CyclePhase.TROUGH
            return CyclePhase.FALLING

        dl = daylight_normals[month]

        return [
            CyclicSignal(
                signal_id="temperature",
                name="Air Temperature",
                unit="°C",
                current_value=round(t_cur, 2),
                seasonal_normal=t_norm,
                deviation=round(temp_deviation, 2),
                phase=_phase(temp_deviation, t_norm),
                description=(
                    f"Monthly average {t_cur:.1f}°C "
                    f"({'above' if temp_deviation >= 0 else 'below'} "
                    f"seasonal normal of {t_norm}°C)"
                ),
            ),
            CyclicSignal(
                signal_id="precipitation",
                name="Precipitation",
                unit="mm/month",
                current_value=round(p_cur, 2),
                seasonal_normal=p_norm,
                deviation=round(precip_deviation, 2),
                phase=_phase(precip_deviation, p_norm),
                description=(
                    f"Monthly total {p_cur:.0f}mm "
                    f"({'above' if precip_deviation >= 0 else 'below'} "
                    f"normal of {p_norm}mm)"
                ),
            ),
            CyclicSignal(
                signal_id="daylight_hours",
                name="Daylight Hours",
                unit="hours/day",
                current_value=dl,
                seasonal_normal=dl,
                deviation=0.0,
                phase=(CyclePhase.RISING if month in range(1, 7)
                       else CyclePhase.FALLING),
                description=f"{dl:.1f} hours of daylight per day",
            ),
            CyclicSignal(
                signal_id="business_activity",
                name="Business Activity Index",
                unit="index",
                current_value=business_normals[month],
                seasonal_normal=1.0,
                deviation=round(business_normals[month] - 1.0, 4),
                phase=_phase(business_normals[month] - 1.0, 1.0),
                description=(
                    f"Monthly business activity index: {business_normals[month]:.2f} "
                    f"(1.0 = typical)"
                ),
            ),
            CyclicSignal(
                signal_id="consumer_spending",
                name="Consumer Spending Index",
                unit="index",
                current_value=consumer_normals[month],
                seasonal_normal=1.0,
                deviation=round(consumer_normals[month] - 1.0, 4),
                phase=_phase(consumer_normals[month] - 1.0, 1.0),
                description=(
                    f"Consumer spending index: {consumer_normals[month]:.2f} "
                    f"(1.0 = typical)"
                ),
            ),
            CyclicSignal(
                signal_id="hvac_demand",
                name="Heating / Cooling Demand",
                unit="index",
                current_value=hvac_normals[month],
                seasonal_normal=0.65,
                deviation=round(hvac_normals[month] - 0.65, 4),
                phase=_phase(hvac_normals[month] - 0.65, 0.65),
                description=(
                    f"HVAC demand index: {hvac_normals[month]:.2f} "
                    f"(0=minimal, 1=maximum)"
                ),
            ),
        ]


# ---------------------------------------------------------------------------
# Automation Calibrator — maps cyclic context to per-automation adjustments
# ---------------------------------------------------------------------------

# Per automation type: list of (parameter, context_attribute, weight, rationale_template)
# context_attribute: attr name on CyclicContext that drives this parameter
_CALIBRATION_RULES: Dict[AutomationType, List[Tuple[str, str, float, str]]] = {

    AutomationType.SALES_PIPELINE: [
        ("outbound_cadence",    "decision_velocity", +0.30,
         "Decision velocity is {val:.2f} — scale outbound cadence accordingly"),
        ("deal_urgency_score",  "activity_index",    +0.25,
         "Business activity index {val:.2f} adjusts deal urgency framing"),
        ("pipeline_target_mul", "consumer_optimism", +0.20,
         "Consumer optimism {val:.2f} affects pipeline conversion expectations"),
        ("close_rate_forecast", "risk_appetite",     +0.20,
         "Risk appetite {val:.2f} directly correlates with buyer willingness to commit"),
        ("holiday_buffer_days", "activity_index",    -0.15,
         "Activity index {val:.2f} — low periods need longer pipeline coverage"),
    ],

    AutomationType.PROPOSAL_WRITER: [
        ("urgency_language",    "decision_velocity", +0.25,
         "Decision velocity {val:.2f} — calibrate urgency language in proposals"),
        ("risk_framing",        "risk_appetite",     +0.20,
         "Risk appetite {val:.2f} — high risk appetite → opportunity framing; low → safety framing"),
        ("pricing_confidence",  "market_sentiment",  +0.15,
         "Market sentiment adjusts pricing confidence level in proposals"),
        ("timeline_buffer",     "activity_index",    -0.10,
         "Low activity index {val:.2f} → add delivery timeline buffers"),
    ],

    AutomationType.ESTIMATOR: [
        ("labour_cost_index",      "outdoor_activity",   -0.20,
         "Outdoor activity {val:.2f} — winter reduces labour availability for field work"),
        ("material_lead_time_mul", "activity_index",     +0.15,
         "High activity {val:.2f} → supply chain pressure → longer lead times"),
        ("weather_risk_premium",   "weather_pattern",    +0.25,
         "Weather pattern affects contingency premium for outdoor work"),
        ("productivity_factor",    "outdoor_activity",   +0.20,
         "Outdoor productivity {val:.2f} adjusts labour hour estimates"),
        ("winter_heating_cost",    "energy_demand",      +0.15,
         "Energy demand {val:.2f} — cold months add temporary heating costs to estimates"),
    ],

    AutomationType.ENERGY_EFFICIENCY: [
        ("hvac_load_factor",       "energy_demand",      +0.35,
         "HVAC demand {val:.2f} — primary driver of energy efficiency scheduling"),
        ("setback_temperature",    "outdoor_activity",   -0.20,
         "Low outdoor activity {val:.2f} → buildings occupied less → deeper setbacks"),
        ("peak_demand_risk",       "energy_demand",      +0.30,
         "Peak demand risk scales with seasonal energy demand {val:.2f}"),
        ("renewable_availability", "outdoor_activity",   +0.15,
         "Solar/wind availability correlates with outdoor conditions"),
    ],

    AutomationType.CLIMATE_RESILIENCE: [
        ("flood_risk_score",       "precipitation",      +0.40,
         "Precipitation deviation {val:.2f} adjusts flood risk assessment"),
        ("heat_stress_score",      "temperature",        +0.35,
         "Temperature deviation {val:.2f} scales heat stress risk"),
        ("storm_readiness",        "weather_pattern",    +0.30,
         "Weather pattern {val} sets storm preparedness level"),
        ("drought_risk_score",     "precipitation",      -0.20,
         "Below-normal precipitation increases drought risk assessment"),
    ],

    AutomationType.CONSTRUCTION_OPERATIONS: [
        ("field_productivity",     "outdoor_activity",   +0.35,
         "Outdoor activity index {val:.2f} directly scales field productivity"),
        ("weather_delay_factor",   "weather_pattern",    -0.30,
         "Adverse weather pattern {val} adds delay factor to schedule"),
        ("concrete_pour_schedule", "temperature",        +0.25,
         "Temperature {val:.1f}°C — curing schedules adjust with ambient temperature"),
        ("winter_protection_cost", "energy_demand",      +0.20,
         "Energy demand {val:.2f} — cold weather increases temporary heating cost"),
        ("daylight_work_hours",    "daylight_hours",     +0.25,
         "Available daylight {val:.1f} hours constrains field work windows"),
    ],

    AutomationType.TALENT_ACQUISITION: [
        ("candidate_activity",     "business_activity",  +0.25,
         "Business activity {val:.2f} — Q1/Q4 are peak candidate-search periods"),
        ("offer_acceptance_rate",  "market_sentiment",   +0.20,
         "Market sentiment {val} affects candidate risk appetite for new roles"),
        ("campus_recruiting_mul",  "season",             +0.20,
         "Seasonal campus recruiting cycle — spring and autumn peak"),
        ("contract_start_buffer",  "holiday_proximity",  +0.15,
         "Holiday proximity adds buffer to contract start timelines"),
    ],

    AutomationType.MARKETING_CAMPAIGNS: [
        ("campaign_send_velocity", "decision_velocity",  +0.30,
         "Decision velocity {val:.2f} — scale campaign frequency accordingly"),
        ("seasonal_offer_weight",  "consumer_spending",  +0.35,
         "Consumer spending index {val:.2f} justifies seasonal promotion intensity"),
        ("emotional_tone",         "weather_pattern",    +0.20,
         "Weather pattern {val} — sunny weather campaigns → aspirational; grey → comfort"),
        ("holiday_campaign_mul",   "activity_index",     +0.15,
         "Activity index {val:.2f} scales holiday campaign budget allocation"),
    ],

    AutomationType.FINANCIAL_PLANNING: [
        ("budget_confidence",      "economic_phase",     +0.30,
         "Economic phase {val} — expansion → confident projections; contraction → conservative"),
        ("discount_rate_adj",      "market_sentiment",   -0.20,
         "Market sentiment {val} — fearful markets require higher discount rates"),
        ("cash_reserve_target",    "risk_appetite",      -0.25,
         "Low risk appetite {val:.2f} → higher cash reserve targets"),
        ("capex_timing_score",     "activity_index",     +0.20,
         "High activity {val:.2f} supports capital investment timing"),
    ],

    AutomationType.SUPPLY_CHAIN: [
        ("lead_time_buffer",       "activity_index",     +0.25,
         "High activity {val:.2f} → supply chain congestion → extend lead time buffers"),
        ("inventory_build_mul",    "consumer_spending",  +0.20,
         "Consumer spending {val:.2f} drives pre-season inventory decisions"),
        ("transport_cost_index",   "weather_pattern",    +0.15,
         "Severe weather patterns increase transport cost and delay risk"),
        ("seasonal_demand_signal", "season",             +0.25,
         "Seasonal demand signal adjusts reorder points and safety stock"),
    ],

    AutomationType.RETAIL_OPERATIONS: [
        ("floor_traffic_forecast", "consumer_spending",  +0.40,
         "Consumer spending index {val:.2f} is the primary retail traffic driver"),
        ("seasonal_assortment",    "season",             +0.30,
         "Season {val} drives assortment and merchandising decisions"),
        ("staffing_level",         "consumer_spending",  +0.25,
         "Consumer spending {val:.2f} calibrates floor staffing levels"),
        ("promotional_intensity",  "consumer_optimism",  +0.20,
         "Consumer optimism {val:.2f} — high optimism → aspirational promotions"),
    ],

    AutomationType.SCHEDULING: [
        ("capacity_utilisation",   "activity_index",     +0.25,
         "Activity index {val:.2f} — peak periods require proactive capacity management"),
        ("meeting_density",        "decision_velocity",  +0.20,
         "Decision velocity {val:.2f} — fast periods demand denser meeting schedules"),
        ("holiday_blackout_flag",  "activity_index",     -0.30,
         "Low activity {val:.2f} flags holiday/slow season blackout windows"),
        ("maintenance_window",     "activity_index",     -0.20,
         "Low-activity periods are the optimal maintenance scheduling window"),
    ],

    AutomationType.DEMAND_FORECASTING: [
        ("seasonal_adjustment",    "consumer_spending",  +0.35,
         "Consumer spending cycle {val:.2f} is the primary demand cycle driver"),
        ("weather_demand_shock",   "temperature",        +0.25,
         "Temperature deviation {val:.2f}°C creates demand shocks in weather-sensitive sectors"),
        ("economic_cycle_weight",  "economic_phase",     +0.20,
         "Economic phase {val} applied as a demand cycle multiplier"),
        ("sentiment_leading_ind",  "market_sentiment",   +0.15,
         "Market sentiment {val} is a leading indicator for demand 60–90 days forward"),
    ],

    AutomationType.BAS_EQUIPMENT: [
        ("setpoint_adjustment",    "energy_demand",      +0.35,
         "Energy demand {val:.2f} drives BAS setpoint scheduling for HVAC"),
        ("occupancy_forecast",     "outdoor_activity",   -0.20,
         "Low outdoor activity {val:.2f} → higher indoor occupancy → BAS demand increases"),
        ("lighting_schedule",      "daylight_hours",     +0.30,
         "Daylight hours {val:.1f} calibrate lighting automation schedules"),
        ("equipment_stress_risk",  "temperature",        +0.25,
         "Extreme temperatures increase equipment stress and maintenance priority"),
    ],

    AutomationType.INDUSTRY_AUTOMATION: [
        ("throughput_target",      "activity_index",     +0.20,
         "Activity index {val:.2f} sets production throughput targets"),
        ("maintenance_priority",   "energy_demand",      +0.15,
         "High energy demand periods increase industrial equipment wear"),
        ("shift_pattern",          "daylight_hours",     +0.10,
         "Daylight availability influences shift planning for outdoor operations"),
    ],

    AutomationType.CLIENT_PSYCHOLOGY: [
        ("optimism_baseline",      "consumer_optimism",  +0.30,
         "Consumer optimism {val:.2f} adjusts the baseline emotional register for client engagement"),
        ("risk_framing_weight",    "risk_appetite",      +0.25,
         "Risk appetite {val:.2f} — high → opportunity framing; low → safety/stability framing"),
        ("decision_urgency",       "decision_velocity",  +0.20,
         "Decision velocity {val:.2f} calibrates urgency language and follow-up cadence"),
        ("social_proof_weight",    "market_sentiment",   +0.15,
         "Market sentiment {val} adjusts how heavily to lean on social proof signals"),
    ],

    AutomationType.CHARACTER_NETWORK: [
        ("outreach_cadence",       "activity_index",     +0.20,
         "Activity index {val:.2f} — peak periods create more natural networking moments"),
        ("event_hosting_priority", "outdoor_activity",   +0.25,
         "High outdoor activity {val:.2f} → in-person events more viable"),
        ("follow_up_velocity",     "decision_velocity",  +0.15,
         "Decision velocity {val:.2f} — fast markets demand faster relationship follow-up"),
    ],

    AutomationType.NETWORKING_MASTERY: [
        ("conference_season_mul",  "business_activity",  +0.30,
         "Business activity {val:.2f} — Q1/Q4 are peak conference and event seasons"),
        ("digital_vs_inperson",    "outdoor_activity",   +0.25,
         "Outdoor activity {val:.2f} determines digital vs in-person networking mix"),
        ("buzz_campaign_timing",   "consumer_spending",  +0.20,
         "Consumer spending cycle {val:.2f} informs campaign launch timing"),
    ],

    AutomationType.ORG_CHART_SIMULATOR: [
        ("hiring_velocity",        "business_activity",  +0.25,
         "Business activity {val:.2f} drives optimal hiring and org growth pace"),
        ("team_output_factor",     "activity_index",     +0.20,
         "Activity index {val:.2f} modulates simulated team productivity"),
        ("scenario_stress_weight", "economic_phase",     -0.20,
         "Contraction phase increases weight on stress scenarios in simulation"),
    ],

    AutomationType.HISTORICAL_GREATNESS: [
        ("era_context_weight",     "economic_phase",     +0.15,
         "Economic phase {val} informs which historical eras are most analogous"),
        ("resilience_trait_boost", "risk_appetite",      -0.20,
         "Low risk appetite {val:.2f} → emphasise fortitude and resilience archetypes"),
    ],
}


# ---------------------------------------------------------------------------
# AutomationCalibrator
# ---------------------------------------------------------------------------

class AutomationCalibrator:
    """
    Applies CyclicContext modifiers to any automation type's baseline parameters.
    """

    def calibrate(
        self,
        automation_type: AutomationType,
        context: CyclicContext,
        baseline_params: Optional[Dict[str, float]] = None,
    ) -> CyclicCalibration:
        """
        Compute adjusted parameters for *automation_type* given *context*.

        Parameters
        ----------
        automation_type:  The automation type to calibrate.
        context:          Current cyclic context (from SeasonalCalendar).
        baseline_params:  Optional custom baseline 0–1 scores.
                          Defaults to 0.70 for all parameters.
        """
        rules = _CALIBRATION_RULES.get(automation_type, [])

        # Build baseline
        params = baseline_params or {}
        for param, _, _, _ in rules:
            params.setdefault(param, 0.70)

        # Compute modifiers
        modifiers: List[CyclicModifier] = []
        adjusted = dict(params)

        for param, ctx_attr, weight, rationale_tpl in rules:
            ctx_val = self._extract_context_value(context, ctx_attr)
            direction = +1.0 if weight > 0 else -1.0
            magnitude = abs(weight) * abs(ctx_val - 0.5) * 2  # deviation from neutral
            magnitude = min(0.40, max(0.0, magnitude))

            # Compute net adjustment: positive weight with high ctx_val → increase
            net = (ctx_val - 0.5) * weight * 2
            adjusted[param] = min(1.0, max(0.0, params[param] + net))

            try:
                rationale = rationale_tpl.format(val=ctx_val)
            except (KeyError, AttributeError):
                rationale = rationale_tpl.format(val=str(ctx_val))

            modifiers.append(CyclicModifier(
                parameter=param,
                direction=direction,
                magnitude=round(magnitude, 4),
                rationale=rationale,
            ))

        # Round all adjusted values
        adjusted = {k: round(v, 4) for k, v in adjusted.items()}

        notes = self._build_notes(automation_type, context, modifiers)
        confidence = self._confidence(context, len(rules))

        return CyclicCalibration(
            automation_type=automation_type,
            context=context,
            baseline_params=params,
            adjusted_params=adjusted,
            modifiers=modifiers,
            notes=notes,
            confidence=confidence,
        )

    def calibrate_all(self, context: CyclicContext) -> Dict[AutomationType, CyclicCalibration]:
        """Calibrate all automation types for the given context."""
        return {at: self.calibrate(at, context) for at in AutomationType}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_context_value(self, ctx: CyclicContext, attr: str) -> float:
        """Extract a numeric value from a CyclicContext attribute."""
        val = getattr(ctx, attr, None)
        if isinstance(val, (int, float)):
            return float(val)
        # Enum attributes: map to numeric
        if isinstance(val, EconomicPhase):
            return {"expansion": 0.80, "peak": 0.90, "contraction": 0.35, "trough": 0.20}[val.value]
        if isinstance(val, MarketSentiment):
            return {"euphoric": 0.95, "optimistic": 0.75, "neutral": 0.50,
                    "cautious": 0.30, "fearful": 0.10}[val.value]
        if isinstance(val, Season):
            return {"spring": 0.65, "summer": 0.70, "autumn": 0.60, "winter": 0.35}[val.value]
        if isinstance(val, WeatherPattern):
            return {"warm_sunny": 0.80, "hot_humid": 0.60, "mild_overcast": 0.55,
                    "cold_clear": 0.60, "cold_grey": 0.30, "wet_rainy": 0.35,
                    "stormy": 0.10, "dry_drought": 0.40}[val.value]
        # Signal attribute: try to get from signals list
        for signal in ctx.signals:
            if signal.signal_id == attr:
                # Normalise relative strength to 0-1
                return min(1.0, max(0.0, 0.50 + signal.relative_strength * 0.50))
        return 0.50

    def _build_notes(
        self,
        at: AutomationType,
        ctx: CyclicContext,
        modifiers: List[CyclicModifier],
    ) -> List[str]:
        notes = []
        top = sorted(modifiers, key=lambda m: abs(m.net_adjustment), reverse=True)[:3]
        for mod in top:
            notes.append(
                f"{at.value.replace('_', ' ').title()}: "
                f"{mod.parameter.replace('_', ' ')} adjusted by "
                f"{mod.net_adjustment:+.3f} — {mod.rationale}"
            )
        # Season note
        notes.append(
            f"Season: {ctx.season.value.title()} | "
            f"Weather: {ctx.weather_pattern.value.replace('_', ' ')} | "
            f"Economy: {ctx.economic_phase.value}"
        )
        return notes

    def _confidence(self, ctx: CyclicContext, rule_count: int) -> float:
        """Confidence is lower when signals are extreme (harder to predict)."""
        if ctx.weather_pattern in (WeatherPattern.STORMY, WeatherPattern.DRY_DROUGHT):
            return 0.65
        if ctx.economic_phase in (EconomicPhase.TROUGH, EconomicPhase.PEAK):
            return 0.75
        base = min(1.0, 0.75 + rule_count * 0.015)
        return round(base, 4)


# ---------------------------------------------------------------------------
# CyclicTrendsEngine — top-level façade
# ---------------------------------------------------------------------------

class CyclicTrendsEngine:
    """
    Top-level façade for the Cyclic Trends Engine.

    Provides a unified interface for injecting cyclic weather, seasonal,
    economic, and market signals into any Murphy System automation type.

    Usage::

        engine = CyclicTrendsEngine()

        # Get calibration for sales pipeline in October with cautious market
        cal = engine.calibrate(
            automation_type=AutomationType.SALES_PIPELINE,
            month=10,
            economic_phase=EconomicPhase.CONTRACTION,
            market_sentiment=MarketSentiment.CAUTIOUS,
        )
        print(cal.adjusted_params["outbound_cadence"])
        print(cal.notes)

        # Calibrate ALL automation types at once for current month
        all_cals = engine.calibrate_all_for_month(month=7)
    """

    def __init__(self, hemisphere: str = "northern") -> None:
        self._calendar   = SeasonalCalendar(hemisphere=hemisphere)
        self._calibrator = AutomationCalibrator()
        self._lock       = threading.Lock()
        self._cache:     Dict[str, CyclicCalibration] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calibrate(
        self,
        automation_type: AutomationType,
        month: Optional[int] = None,
        target_date: Optional[date] = None,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
        temperature_deviation: float = 0.0,
        precipitation_deviation: float = 0.0,
        baseline_params: Optional[Dict[str, float]] = None,
    ) -> CyclicCalibration:
        """
        Calibrate one automation type for a given cyclic context.

        Provide either *month* (1–12) or *target_date*.
        If neither is given, today's date is used.
        """
        effective_date = (
            target_date or
            (date(date.today().year, month, 15) if month else date.today())
        )

        ctx = self._calendar.get_context_for_date(
            target_date=effective_date,
            economic_phase=economic_phase,
            market_sentiment=market_sentiment,
            temperature_deviation=temperature_deviation,
            precipitation_deviation=precipitation_deviation,
        )

        cache_key = (
            f"{automation_type.value}:{effective_date.isoformat()}:"
            f"{economic_phase.value}:{market_sentiment.value}:"
            f"{temperature_deviation:.1f}:{precipitation_deviation:.1f}"
        )
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        cal = self._calibrator.calibrate(automation_type, ctx, baseline_params)

        with self._lock:
            if len(self._cache) > 500:
                keys = list(self._cache.keys())[:50]
                for k in keys:
                    del self._cache[k]
            self._cache[cache_key] = cal

        return cal

    def calibrate_all_for_month(
        self,
        month: int,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
        temperature_deviation: float = 0.0,
        precipitation_deviation: float = 0.0,
    ) -> Dict[AutomationType, CyclicCalibration]:
        """Calibrate ALL 20 automation types for the given month at once."""
        ctx = self._calendar.get_context_for_month(
            month=month,
            economic_phase=economic_phase,
            market_sentiment=market_sentiment,
            temperature_deviation=temperature_deviation,
            precipitation_deviation=precipitation_deviation,
        )
        return self._calibrator.calibrate_all(ctx)

    def get_context(
        self,
        month: Optional[int] = None,
        target_date: Optional[date] = None,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
        temperature_deviation: float = 0.0,
        precipitation_deviation: float = 0.0,
    ) -> CyclicContext:
        """Return the CyclicContext for a given date without calibrating."""
        effective_date = (
            target_date or
            (date(date.today().year, month, 15) if month else date.today())
        )
        return self._calendar.get_context_for_date(
            target_date=effective_date,
            economic_phase=economic_phase,
            market_sentiment=market_sentiment,
            temperature_deviation=temperature_deviation,
            precipitation_deviation=precipitation_deviation,
        )

    def annual_profile(
        self,
        automation_type: AutomationType,
        economic_phase: EconomicPhase = EconomicPhase.EXPANSION,
        market_sentiment: MarketSentiment = MarketSentiment.OPTIMISTIC,
    ) -> List[Dict[str, Any]]:
        """
        Return a 12-month cyclic profile for one automation type.

        Useful for annual planning and resource allocation.
        """
        profile = []
        for m in range(1, 13):
            cal = self.calibrate(
                automation_type=automation_type,
                month=m,
                economic_phase=economic_phase,
                market_sentiment=market_sentiment,
            )
            profile.append({
                "month":           m,
                "season":          cal.context.season.value,
                "weather_pattern": cal.context.weather_pattern.value,
                "activity_index":  cal.context.activity_index,
                "adjusted_params": cal.adjusted_params,
                "top_note":        cal.notes[0] if cal.notes else "",
            })
        return profile

    def all_automation_types(self) -> List[AutomationType]:
        """Return all 20 automation types."""
        return list(AutomationType)

    def describe_context(self, context: CyclicContext) -> str:
        """Return a human-readable summary of a cyclic context."""
        return (
            f"{context.season.value.title()} | "
            f"{context.weather_pattern.value.replace('_', ' ').title()} | "
            f"Economy: {context.economic_phase.value.title()} | "
            f"Sentiment: {context.market_sentiment.value.title()} | "
            f"Activity: {context.activity_index:.2f} | "
            f"Risk appetite: {context.risk_appetite:.2f} | "
            f"Decision velocity: {context.decision_velocity:.2f}"
        )
