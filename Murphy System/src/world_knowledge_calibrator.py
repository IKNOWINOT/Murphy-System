# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
World Knowledge Calibrator — Murphy System
============================================

Provides **algebraic calibration sensors** that anchor LLM inference to
real-world values, preventing hallucination by locking in known constants,
cyclic patterns, and statistical distributions.

The core insight: certain facts are *mathematically deterministic* — not
because we have a real-time API, but because we can derive them from:
  - Historical averages (e.g., 8.5% average US inflation in 2022)
  - Physical constants (speed of light, Planck constant, etc.)
  - Cyclic patterns (seasonal demand curves, daylight hours)
  - Statistical baselines (industry conversion rates, churn rates)

When an LLM room brain operates in CALIBRATE mode, it calls
``WorldKnowledgeCalibrator.calibrate()`` to receive a set of
:class:`SensorReading` objects that act as **algebraic anchors** — the LLM
must not contradict these values.

Algebraic lock formula::

    calibrated_value = base_value × cyclic_modifier × confidence_weight

Where:
  ``base_value``        — the known constant or historical average
  ``cyclic_modifier``   — 0.0–2.0 multiplier from ``CyclicTrendsEngine``
  ``confidence_weight`` — 0.0–1.0 reliability score

Design:  WKC-001
Owner:   Platform AI / Calibration
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import — CyclicTrendsEngine is optional
# ---------------------------------------------------------------------------

def _try_import_cyclic():
    try:
        from cyclic_trends_engine import CyclicTrendsEngine, AutomationType
        return CyclicTrendsEngine, AutomationType
    except ImportError:
        return None, None


# ---------------------------------------------------------------------------
# Built-in world-knowledge constants
# ---------------------------------------------------------------------------

#: Physical and mathematical constants
PHYSICAL_CONSTANTS: Dict[str, Dict[str, Any]] = {
    "speed_of_light_ms":        {"value": 299_792_458.0,  "unit": "m/s",   "confidence": 1.0},
    "planck_constant_js":       {"value": 6.626e-34,       "unit": "J·s",   "confidence": 1.0},
    "avogadro_number":          {"value": 6.022e23,        "unit": "mol⁻¹","confidence": 1.0},
    "gravitational_constant":   {"value": 9.80665,         "unit": "m/s²",  "confidence": 1.0},
    "euler_number":             {"value": math.e,          "unit": "",      "confidence": 1.0},
    "pi":                       {"value": math.pi,         "unit": "",      "confidence": 1.0},
}

#: Statistical business baselines (US/global averages — update periodically)
BUSINESS_BASELINES: Dict[str, Dict[str, Any]] = {
    "saas_monthly_churn_rate":        {"value": 0.023,  "unit": "%/month",  "confidence": 0.82},
    "b2b_email_open_rate":            {"value": 0.215,  "unit": "%",        "confidence": 0.78},
    "b2b_proposal_conversion_rate":   {"value": 0.19,   "unit": "%",        "confidence": 0.75},
    "avg_sales_cycle_days":           {"value": 84.0,   "unit": "days",     "confidence": 0.72},
    "avg_customer_acquisition_cost":  {"value": 702.0,  "unit": "USD",      "confidence": 0.65},
    "avg_ltv_cac_ratio":              {"value": 3.1,    "unit": "ratio",    "confidence": 0.70},
    "market_cagr_saas":               {"value": 0.173,  "unit": "%/yr",     "confidence": 0.68},
    "inflation_us_2023":              {"value": 0.034,  "unit": "%/yr",     "confidence": 0.95},
    "prime_rate_us_2024":             {"value": 0.083,  "unit": "%/yr",     "confidence": 0.92},
    "unemployment_us_2024":           {"value": 0.038,  "unit": "%",        "confidence": 0.94},
}

#: Cyclic seasonal multipliers by month (1=Jan … 12=Dec)
#: Values >1 mean the phenomenon is above average in that month
SEASONAL_MULTIPLIERS: Dict[str, List[float]] = {
    #                         J     F     M     A     M     J     J     A     S     O     N     D
    "sales_velocity":       [0.82, 0.85, 1.05, 1.12, 1.10, 1.08, 0.90, 0.78, 1.05, 1.15, 0.95, 0.75],
    "hiring_activity":      [1.20, 1.15, 1.18, 1.10, 1.05, 0.95, 0.90, 0.85, 1.10, 1.15, 1.00, 0.70],
    "energy_demand":        [1.25, 1.20, 1.00, 0.85, 0.90, 1.10, 1.30, 1.25, 0.95, 0.85, 1.00, 1.20],
    "retail_demand":        [0.80, 0.75, 0.90, 0.95, 1.00, 1.05, 0.95, 1.05, 1.10, 1.20, 1.30, 1.50],
    "construction_activity":[0.65, 0.70, 0.90, 1.10, 1.20, 1.25, 1.20, 1.15, 1.10, 0.95, 0.80, 0.60],
    "market_volatility":    [1.10, 1.05, 1.00, 0.95, 0.90, 0.95, 1.00, 1.05, 1.15, 1.20, 1.10, 1.00],
}


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

@dataclass
class CalibrationAnchor:
    """A single world-knowledge anchor used to constrain LLM inference."""

    sensor_id: str
    base_value: float
    cyclic_modifier: float = 1.0
    confidence_weight: float = 1.0
    unit: str = ""
    source: str = "world_knowledge"
    description: str = ""

    @property
    def calibrated_value(self) -> float:
        """Algebraic lock: base × cyclic × confidence."""
        return self.base_value * self.cyclic_modifier * self.confidence_weight

    def to_sensor_reading(self) -> "SensorReading":
        """Convert to a SensorReading for use by RoomLLMBrain."""
        try:
            from room_llm_brain import SensorReading
        except ImportError:
            # Fallback plain dict proxy
            @dataclass
            class SensorReading:
                sensor_id: str
                value: float
                unit: str = ""
                confidence: float = 1.0
                source: str = "world_knowledge"

        return SensorReading(
            sensor_id  = self.sensor_id,
            value      = self.calibrated_value,
            unit       = self.unit,
            confidence = self.confidence_weight,
            source     = self.source,
        )


@dataclass
class CalibrationBundle:
    """A set of anchors for a specific domain / inference context."""

    domain: str
    anchors: List[CalibrationAnchor] = field(default_factory=list)
    calibration_date: date = field(default_factory=date.today)

    def sensor_readings(self) -> List[Any]:
        """Return all anchors as SensorReading objects."""
        return [a.to_sensor_reading() for a in self.anchors]

    def avg_confidence(self) -> float:
        if not self.anchors:
            return 1.0
        return sum(a.confidence_weight for a in self.anchors) / len(self.anchors)

    def locked_values(self) -> Dict[str, float]:
        """Return ``{sensor_id: calibrated_value}`` for all anchors."""
        return {a.sensor_id: a.calibrated_value for a in self.anchors}


# ---------------------------------------------------------------------------
# Algebraic sensor functions
# ---------------------------------------------------------------------------

AlgebraicFn = Callable[[float, float], float]


def lock_seasonal(base: float, signal_key: str, month: Optional[int] = None) -> float:
    """
    Apply a seasonal multiplier to *base* for the given *signal_key*.

    ::

        locked = base × SEASONAL_MULTIPLIERS[signal_key][month-1]
    """
    if month is None:
        month = datetime.now(timezone.utc).month
    multipliers = SEASONAL_MULTIPLIERS.get(signal_key)
    if not multipliers:
        return base
    idx = max(0, min(11, month - 1))
    return base * multipliers[idx]


def lock_decay(base: float, half_life_days: float, age_days: float) -> float:
    """
    Exponential decay algebraic lock::

        locked = base × e^(−(age / half_life) × ln 2)
    """
    if half_life_days <= 0:
        return base
    return base * math.exp(-(age_days / half_life_days) * math.log(2))


def lock_logistic(base: float, growth_rate: float, carrying_capacity: float) -> float:
    """
    Logistic growth lock (S-curve)::

        locked = K / (1 + ((K − base) / base) × e^(−r))
    """
    if base <= 0 or carrying_capacity <= 0:
        return base
    exponent = -growth_rate
    ratio = (carrying_capacity - base) / base
    return carrying_capacity / (1.0 + ratio * math.exp(exponent))


def lock_moving_average(values: List[float], window: int = 7) -> float:
    """Return the simple moving average over the last *window* values."""
    if not values:
        return 0.0
    tail = values[-window:] if len(values) >= window else values
    return sum(tail) / len(tail)


def sensor_inference(
    signals: Dict[str, float],
    algebraic_fn: AlgebraicFn,
    *fn_args: float,
) -> float:
    """
    Combine multiple sensor signals with an algebraic function.

    The mean of *signals* values is fed as the first argument to
    *algebraic_fn*; remaining positional args follow.

    ::

        result = algebraic_fn(mean(signals), *fn_args)
    """
    if not signals:
        return 0.0
    mean_val = sum(signals.values()) / len(signals)
    return algebraic_fn(mean_val, *fn_args)


# ---------------------------------------------------------------------------
# Main calibrator
# ---------------------------------------------------------------------------

class WorldKnowledgeCalibrator:
    """
    Provides calibration bundles for any named domain.

    The calibrator:

    1. Looks up base values from built-in knowledge dicts
       (``PHYSICAL_CONSTANTS``, ``BUSINESS_BASELINES``, …)
    2. Applies seasonal cyclic modifiers via ``SEASONAL_MULTIPLIERS``
    3. Optionally invokes ``CyclicTrendsEngine`` if available
    4. Returns a :class:`CalibrationBundle` of algebraically locked anchors

    Usage::

        cal = WorldKnowledgeCalibrator()
        bundle = cal.calibrate("sales_pipeline")
        # inject into RoomInferenceRequest
        req = RoomInferenceRequest(content="...", sensor_readings=bundle.sensor_readings())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        CyclicTrendsEngine, AutomationType = _try_import_cyclic()
        self._cyclic_engine = None
        if CyclicTrendsEngine is not None:
            try:
                self._cyclic_engine = CyclicTrendsEngine()
            except Exception as exc:
                logger.debug("CyclicTrendsEngine init failed: %s", exc)

    # ------------------------------------------------------------------

    def calibrate(
        self,
        domain: str,
        ref_date: Optional[date] = None,
        extra_signals: Optional[Dict[str, float]] = None,
    ) -> CalibrationBundle:
        """
        Build a calibration bundle for *domain*.

        Parameters
        ----------
        domain:
            A business or physics domain key
            (e.g. ``"sales_pipeline"``, ``"energy"``, ``"physics"``).
        ref_date:
            Reference date for cyclic modifiers.  Defaults to today UTC.
        extra_signals:
            Additional ``{sensor_id: value}`` pairs to include.
        """
        if ref_date is None:
            ref_date = date.today()

        anchors: List[CalibrationAnchor] = []

        # ── Physics domain ────────────────────────────────────────────
        if domain in ("physics", "engineering", "simulation"):
            for key, info in PHYSICAL_CONSTANTS.items():
                anchors.append(CalibrationAnchor(
                    sensor_id         = key,
                    base_value        = float(info["value"]),
                    cyclic_modifier   = 1.0,       # constants don't cycle
                    confidence_weight = float(info["confidence"]),
                    unit              = info["unit"],
                    source            = "physical_constant",
                    description       = f"Physical constant: {key}",
                ))

        # ── Business domains ──────────────────────────────────────────
        relevant_baselines = self._select_baselines(domain)
        for key, info in relevant_baselines.items():
            cyclic_mod = self._get_cyclic_modifier(domain, ref_date)
            anchors.append(CalibrationAnchor(
                sensor_id         = key,
                base_value        = float(info["value"]),
                cyclic_modifier   = cyclic_mod,
                confidence_weight = float(info["confidence"]),
                unit              = info["unit"],
                source            = "business_baseline",
                description       = f"Business baseline: {key}",
            ))

        # ── Seasonal signal for any domain ────────────────────────────
        for signal_key, base in self._domain_seasonal_base(domain).items():
            locked = lock_seasonal(base, signal_key, ref_date.month)
            anchors.append(CalibrationAnchor(
                sensor_id         = f"seasonal_{signal_key}",
                base_value        = base,
                cyclic_modifier   = locked / base if base else 1.0,
                confidence_weight = 0.85,
                unit              = "modifier",
                source            = "seasonal_calendar",
                description       = f"Seasonal multiplier for {signal_key}",
            ))

        # ── Extra signals passed in ───────────────────────────────────
        for sid, val in (extra_signals or {}).items():
            anchors.append(CalibrationAnchor(
                sensor_id         = sid,
                base_value        = val,
                cyclic_modifier   = 1.0,
                confidence_weight = 0.90,
                unit              = "raw",
                source            = "caller_supplied",
            ))

        return CalibrationBundle(
            domain             = domain,
            anchors            = anchors,
            calibration_date   = ref_date,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_baselines(self, domain: str) -> Dict[str, Dict[str, Any]]:
        """Return baselines relevant to *domain*."""
        domain_map: Dict[str, List[str]] = {
            "sales":       ["b2b_email_open_rate", "b2b_proposal_conversion_rate",
                            "avg_sales_cycle_days", "avg_customer_acquisition_cost",
                            "avg_ltv_cac_ratio"],
            "saas":        ["saas_monthly_churn_rate", "market_cagr_saas",
                            "avg_customer_acquisition_cost"],
            "finance":     ["inflation_us_2023", "prime_rate_us_2024",
                            "market_cagr_saas"],
            "trading":     ["market_volatility", "inflation_us_2023",
                            "prime_rate_us_2024"],
            "hr":          ["avg_sales_cycle_days", "unemployment_us_2024"],
            "marketing":   ["b2b_email_open_rate", "b2b_proposal_conversion_rate",
                            "market_cagr_saas"],
            "operations":  ["avg_sales_cycle_days", "inflation_us_2023"],
        }
        # match by substring
        matched_keys: List[str] = []
        for k, keys in domain_map.items():
            if k in domain.lower():
                matched_keys.extend(keys)
        if not matched_keys:
            matched_keys = list(BUSINESS_BASELINES.keys())[:4]
        return {k: BUSINESS_BASELINES[k] for k in matched_keys if k in BUSINESS_BASELINES}

    def _get_cyclic_modifier(self, domain: str, ref_date: date) -> float:
        """Return a cyclic multiplier from CyclicTrendsEngine if available."""
        if self._cyclic_engine is None:
            return 1.0
        try:
            # Use calibrate_all_for_month if available
            if hasattr(self._cyclic_engine, "calibrate_all_for_month"):
                all_cals = self._cyclic_engine.calibrate_all_for_month(month=ref_date.month)
                # Average across all calibrations as a general modifier
                if all_cals:
                    mods = []
                    for cal in all_cals.values():
                        params = getattr(cal, "adjusted_params", {})
                        for v in params.values():
                            if isinstance(v, (int, float)):
                                mods.append(float(v))
                    if mods:
                        return min(2.0, max(0.1, sum(mods) / len(mods)))
        except Exception as exc:
            logger.debug("CyclicTrendsEngine modifier failed: %s", exc)
        return 1.0

    @staticmethod
    def _domain_seasonal_base(domain: str) -> Dict[str, float]:
        """Return which seasonal signals apply to *domain* and their base values."""
        mapping: Dict[str, Dict[str, float]] = {
            "sales":        {"sales_velocity": 1.0},
            "hr":           {"hiring_activity": 1.0},
            "energy":       {"energy_demand": 1.0},
            "retail":       {"retail_demand": 1.0},
            "construction": {"construction_activity": 1.0},
            "trading":      {"market_volatility": 1.0},
            "finance":      {"market_volatility": 1.0, "retail_demand": 0.5},
        }
        for k, v in mapping.items():
            if k in domain.lower():
                return v
        return {"sales_velocity": 1.0}    # default for all domains

    # ------------------------------------------------------------------
    # Convenience: algebraic locks as static methods
    # ------------------------------------------------------------------

    @staticmethod
    def lock_seasonal(base: float, signal_key: str, month: Optional[int] = None) -> float:
        return lock_seasonal(base, signal_key, month)

    @staticmethod
    def lock_decay(base: float, half_life_days: float, age_days: float) -> float:
        return lock_decay(base, half_life_days, age_days)

    @staticmethod
    def lock_logistic(base: float, growth_rate: float, carrying_capacity: float) -> float:
        return lock_logistic(base, growth_rate, carrying_capacity)

    @staticmethod
    def sensor_inference(
        signals: Dict[str, float],
        algebraic_fn: AlgebraicFn,
        *fn_args: float,
    ) -> float:
        return sensor_inference(signals, algebraic_fn, *fn_args)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_calibrator: Optional[WorldKnowledgeCalibrator] = None
_cal_lock = threading.Lock()


def get_calibrator() -> WorldKnowledgeCalibrator:
    """Return (and lazily create) the default :class:`WorldKnowledgeCalibrator`."""
    global _default_calibrator
    with _cal_lock:
        if _default_calibrator is None:
            _default_calibrator = WorldKnowledgeCalibrator()
    return _default_calibrator


__all__ = [
    "PHYSICAL_CONSTANTS",
    "BUSINESS_BASELINES",
    "SEASONAL_MULTIPLIERS",
    "CalibrationAnchor",
    "CalibrationBundle",
    "WorldKnowledgeCalibrator",
    "get_calibrator",
    "lock_seasonal",
    "lock_decay",
    "lock_logistic",
    "lock_moving_average",
    "sensor_inference",
]
