"""
Economic Depression and Crash Scenario Simulator.

Design Label: CHAOS-003 — Economic Depression Simulator
Owner: Platform Engineering

Models economic depressions, financial crises, hyperinflation, and deflationary
spirals with historically calibrated parameters.

Historical calibrations:
  GREAT_DEPRESSION       — GDP -29%, unemployment 24.9%, 43-month contraction
  FINANCIAL_CRISIS_2008  — GDP -4.3%, unemployment 10%, 18-month contraction
  DOT_COM_CRASH          — NASDAQ -78%, GDP -0.3%, 30-month bear
  WEIMAR_HYPERINFLATION  — Peak inflation 3.25×10^6 %, 3-year episode
  JAPAN_LOST_DECADE      — GDP flat 10 years, persistent deflation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_EXAMPLES = 5000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CrisisType(Enum):
    GREAT_DEPRESSION = "great_depression"
    DOT_COM_CRASH = "dot_com_crash"
    FINANCIAL_CRISIS_2008 = "financial_crisis_2008"
    HYPERINFLATION = "hyperinflation"
    DEFLATION_SPIRAL = "deflation_spiral"
    STAGFLATION = "stagflation"
    SOVEREIGN_DEFAULT = "sovereign_default"
    BANK_RUN = "bank_run"
    CREDIT_CRUNCH = "credit_crunch"
    COMMODITY_SHOCK = "commodity_shock"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EconomicIndicator:
    indicator_name: str
    baseline_value: float
    crisis_value: float
    recovery_value: float
    unit: str
    recovery_months: int


@dataclass
class DepressionScenario:
    crisis_id: str
    crisis_type: CrisisType
    trigger_event: str
    affected_sectors: List[str]
    duration_months: int
    peak_unemployment: float
    gdp_contraction_pct: float
    indicators: List[EconomicIndicator]
    policy_responses: List[str]


# ---------------------------------------------------------------------------
# Historical calibrations
# ---------------------------------------------------------------------------

_HISTORICAL_CALIBRATIONS: Dict[str, Dict[str, Any]] = {
    "GREAT_DEPRESSION": {
        "crisis_type": CrisisType.GREAT_DEPRESSION,
        "gdp_contraction_pct": -29.0,
        "peak_unemployment": 24.9,
        "duration_months": 43,
        "trigger": "stock_market_crash_1929",
        "sectors": ["banking", "agriculture", "manufacturing", "retail"],
        "indicators": [
            EconomicIndicator("GDP", 100.0, 71.0, 100.0, "index", 84),
            EconomicIndicator("Unemployment", 3.2, 24.9, 3.0, "pct", 120),
            EconomicIndicator("Money_Supply_M2", 100.0, 67.0, 100.0, "index", 60),
            EconomicIndicator("Bank_Failures", 0, 9000, 0, "count", 48),
        ],
    },
    "FINANCIAL_CRISIS_2008": {
        "crisis_type": CrisisType.FINANCIAL_CRISIS_2008,
        "gdp_contraction_pct": -4.3,
        "peak_unemployment": 10.0,
        "duration_months": 18,
        "trigger": "subprime_mortgage_collapse",
        "sectors": ["banking", "real_estate", "automotive", "construction"],
        "indicators": [
            EconomicIndicator("GDP", 100.0, 95.7, 100.0, "index", 24),
            EconomicIndicator("Unemployment", 4.7, 10.0, 4.0, "pct", 48),
            EconomicIndicator("Housing_Prices", 100.0, 67.0, 80.0, "index", 84),
            EconomicIndicator("Credit_Default_Swaps", 1.0, 62.0, 5.0, "trn_usd", 24),
        ],
    },
    "DOT_COM": {
        "crisis_type": CrisisType.DOT_COM_CRASH,
        "gdp_contraction_pct": -0.3,
        "peak_unemployment": 6.3,
        "duration_months": 30,
        "trigger": "internet_bubble_burst",
        "sectors": ["technology", "telecommunications", "media", "retail"],
        "indicators": [
            EconomicIndicator("NASDAQ", 100.0, 22.0, 45.0, "index", 60),
            EconomicIndicator("VC_Investment", 100.0, 12.0, 25.0, "index", 48),
            EconomicIndicator("Tech_Employment", 100.0, 84.0, 90.0, "index", 36),
        ],
    },
    "WEIMAR_HYPERINFLATION": {
        "crisis_type": CrisisType.HYPERINFLATION,
        "gdp_contraction_pct": -15.0,
        "peak_unemployment": 28.0,
        "duration_months": 36,
        "trigger": "war_reparations_and_money_printing",
        "sectors": ["banking", "retail", "manufacturing", "agriculture"],
        "indicators": [
            EconomicIndicator("Inflation_Rate", 1.0, 3_250_000.0, 1.0, "pct", 12),
            EconomicIndicator("Exchange_Rate_USD_Mark", 4.2, 4_200_000_000_000.0, 4.2, "mark_per_usd", 24),
            EconomicIndicator("Real_Wages", 100.0, 12.0, 60.0, "index", 24),
        ],
    },
    "JAPAN_LOST_DECADE": {
        "crisis_type": CrisisType.DEFLATION_SPIRAL,
        "gdp_contraction_pct": -2.0,
        "peak_unemployment": 5.5,
        "duration_months": 120,
        "trigger": "asset_bubble_burst_1991",
        "sectors": ["banking", "real_estate", "manufacturing", "construction"],
        "indicators": [
            EconomicIndicator("GDP_Growth", 4.0, 0.1, 1.5, "pct_annual", 120),
            EconomicIndicator("Nikkei_225", 38_916.0, 7_607.0, 15_000.0, "index", 240),
            EconomicIndicator("Land_Prices", 100.0, 32.0, 38.0, "index", 180),
            EconomicIndicator("Bank_NPL_Ratio", 1.0, 35.0, 3.0, "pct", 120),
        ],
    },
}


# ---------------------------------------------------------------------------
# Sector impact profiles per crisis type
# ---------------------------------------------------------------------------

_SECTOR_IMPACT_PROFILES: Dict[CrisisType, Dict[str, float]] = {
    CrisisType.GREAT_DEPRESSION:     {"banking": 0.90, "agriculture": 0.60, "manufacturing": 0.55, "retail": 0.50},
    CrisisType.DOT_COM_CRASH:        {"technology": 0.85, "telecoms": 0.70, "media": 0.40, "retail": 0.20},
    CrisisType.FINANCIAL_CRISIS_2008: {"banking": 0.80, "real_estate": 0.60, "automotive": 0.45, "construction": 0.50},
    CrisisType.HYPERINFLATION:       {"retail": 0.75, "manufacturing": 0.60, "banking": 0.85, "agriculture": 0.40},
    CrisisType.DEFLATION_SPIRAL:     {"real_estate": 0.55, "banking": 0.65, "manufacturing": 0.35, "construction": 0.60},
    CrisisType.STAGFLATION:          {"energy": 0.50, "manufacturing": 0.40, "retail": 0.35, "transportation": 0.45},
    CrisisType.SOVEREIGN_DEFAULT:    {"banking": 0.90, "government_bonds": 0.95, "currency": 0.70, "retail": 0.55},
    CrisisType.BANK_RUN:             {"banking": 0.95, "credit": 0.85, "retail": 0.40, "manufacturing": 0.30},
    CrisisType.CREDIT_CRUNCH:        {"banking": 0.70, "real_estate": 0.55, "small_business": 0.60, "construction": 0.50},
    CrisisType.COMMODITY_SHOCK:      {"energy": 0.65, "agriculture": 0.55, "chemicals": 0.50, "transportation": 0.40},
}


# ---------------------------------------------------------------------------
# EconomicDepressionSimulator — CHAOS-003
# ---------------------------------------------------------------------------

class EconomicDepressionSimulator:
    """CHAOS-003 — Economic Depression Simulator.

    Historically calibrated models for depressions, financial crises,
    hyperinflation, deflation spirals, and sovereign defaults.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.RLock()  # RLock: generate_training_examples calls simulate_crisis
        self._example_cache: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_crisis(
        self,
        crisis_type: CrisisType,
        trigger_event: Optional[str] = None,
        policy_responses: Optional[List[str]] = None,
    ) -> DepressionScenario:
        """Generate a DepressionScenario for the given crisis type."""
        with self._lock:
            cal = self._get_calibration(crisis_type)
            affected_sectors = list(cal.get("sectors", ["banking", "retail", "manufacturing"]))

            duration = int(cal["duration_months"] * self._rng.uniform(0.7, 1.5))
            gdp_contraction = cal["gdp_contraction_pct"] * self._rng.uniform(0.8, 1.3)
            peak_unemp = cal["peak_unemployment"] * self._rng.uniform(0.85, 1.2)

            scenario = DepressionScenario(
                crisis_id=str(uuid.uuid4()),
                crisis_type=crisis_type,
                trigger_event=trigger_event or cal.get("trigger", "unknown"),
                affected_sectors=affected_sectors,
                duration_months=duration,
                peak_unemployment=round(peak_unemp, 2),
                gdp_contraction_pct=round(gdp_contraction, 2),
                indicators=list(cal.get("indicators", [])),
                policy_responses=policy_responses or _default_policies(crisis_type),
            )

            if policy_responses:
                scenario = self._simulate_policy_responses(scenario, policy_responses)

            logger.debug("Simulated crisis %s id=%s gdp=%.2f%%",
                         crisis_type.value, scenario.crisis_id, scenario.gdp_contraction_pct)
            return scenario

    def get_risk_indicators(self, current_data: Dict[str, float]) -> float:
        """Compute an early-warning risk score from 0 (safe) to 10 (imminent crisis)."""
        score = 0.0
        checks = [
            ("yield_curve_spread", -0.5, +1.5, True),   # inverted = risky
            ("unemployment_delta", 0.0, 3.0, False),
            ("credit_growth_pct", -5.0, 15.0, False),
            ("housing_price_yoy", -10.0, 20.0, False),
            ("m2_growth_pct", 0.0, 25.0, False),
        ]
        for key, low_risk, high_risk, invert in checks:
            if key not in current_data:
                continue
            val = current_data[key]
            if invert:
                normalised = 1.0 - max(0.0, min(1.0, (val - low_risk) / max(1e-9, high_risk - low_risk)))
            else:
                normalised = max(0.0, min(1.0, (val - low_risk) / max(1e-9, high_risk - low_risk)))
            score += normalised * 2.0  # max contribution per indicator = 2.0

        return round(min(10.0, score), 2)

    def generate_training_examples(self, num_scenarios: int = 100) -> List[Dict[str, Any]]:
        """Generate ML training data from random crisis simulations."""
        with self._lock:
            examples: List[Dict[str, Any]] = []
            crisis_types = list(CrisisType)

            for _ in range(num_scenarios):
                ctype = self._rng.choice(crisis_types)
                scenario = self.simulate_crisis(ctype)
                quarterly = self._model_recovery_path(scenario)
                sector_impacts = self._calculate_sector_impacts(ctype, scenario.affected_sectors)

                example: Dict[str, Any] = {
                    "input": {
                        "crisis_type": ctype.value,
                        "duration_months": scenario.duration_months,
                        "num_sectors_affected": len(scenario.affected_sectors),
                        "num_policy_responses": len(scenario.policy_responses),
                    },
                    "output": {
                        "gdp_contraction_pct": scenario.gdp_contraction_pct,
                        "peak_unemployment": scenario.peak_unemployment,
                        "quarters_to_recover": len(quarterly),
                    },
                    "sector_impacts": sector_impacts,
                    "recovery_path": quarterly[:8],  # first 8 quarters
                    "source": "EconomicDepressionSimulator-CHAOS-003",
                }
                if len(self._example_cache) < _MAX_EXAMPLES:
                    self._example_cache.append(example)
                examples.append(example)

            return examples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_calibration(self, crisis_type: CrisisType) -> Dict[str, Any]:
        """Retrieve the closest historical calibration for a crisis type."""
        mapping = {
            CrisisType.GREAT_DEPRESSION: "GREAT_DEPRESSION",
            CrisisType.FINANCIAL_CRISIS_2008: "FINANCIAL_CRISIS_2008",
            CrisisType.DOT_COM_CRASH: "DOT_COM",
            CrisisType.HYPERINFLATION: "WEIMAR_HYPERINFLATION",
            CrisisType.DEFLATION_SPIRAL: "JAPAN_LOST_DECADE",
        }
        key = mapping.get(crisis_type)
        if key:
            return _HISTORICAL_CALIBRATIONS[key]

        # Synthetic calibration for un-anchored types
        return {
            "crisis_type": crisis_type,
            "gdp_contraction_pct": -self._rng.uniform(2.0, 20.0),
            "peak_unemployment": self._rng.uniform(5.0, 20.0),
            "duration_months": self._rng.randint(6, 48),
            "trigger": crisis_type.value,
            "sectors": ["banking", "retail", "manufacturing"],
            "indicators": [],
        }

    def _calculate_sector_impacts(
        self, crisis_type: CrisisType, affected_sectors: List[str]
    ) -> Dict[str, float]:
        """Return sector-level impact fractions (0-1)."""
        profile = _SECTOR_IMPACT_PROFILES.get(crisis_type, {})
        return {
            sector: round(profile.get(sector, self._rng.uniform(0.1, 0.5)) * self._rng.uniform(0.8, 1.2), 3)
            for sector in affected_sectors
        }

    def _model_recovery_path(self, scenario: DepressionScenario) -> List[Dict[str, float]]:
        """Return a list of quarterly recovery projections (GDP delta %)."""
        quarters: List[Dict[str, float]] = []
        # Phase 1: contraction
        contraction_quarters = max(1, scenario.duration_months // 3)
        trough = scenario.gdp_contraction_pct
        for q in range(contraction_quarters):
            frac = (q + 1) / contraction_quarters
            quarters.append({"quarter": q + 1, "gdp_delta_pct": round(trough * frac / contraction_quarters, 3)})

        # Phase 2: recovery — logistic-ish growth back toward 0
        recovery_quarters = max(4, (scenario.duration_months * 2) // 3)
        for q in range(recovery_quarters):
            frac = (q + 1) / recovery_quarters
            gdp = trough * (1.0 - frac) + self._rng.uniform(-0.5, 0.5)
            quarters.append({"quarter": contraction_quarters + q + 1, "gdp_delta_pct": round(gdp, 3)})

        return quarters

    def _simulate_policy_responses(
        self, scenario: DepressionScenario, policies: List[str]
    ) -> DepressionScenario:
        """Modify scenario metrics based on applied policy responses."""
        mitigation = 0.0
        policy_effects = {
            "fiscal_stimulus": 0.10,
            "quantitative_easing": 0.08,
            "rate_cuts": 0.07,
            "bank_bailout": 0.15,
            "trade_tariffs": -0.03,   # can worsen
            "capital_controls": 0.05,
            "debt_restructuring": 0.12,
            "austerity": -0.05,       # typically worsens in short term
        }
        for policy in policies:
            mitigation += policy_effects.get(policy, 0.02)

        mitigation = max(-0.3, min(0.4, mitigation))

        scenario.gdp_contraction_pct = round(scenario.gdp_contraction_pct * (1.0 - mitigation), 2)
        scenario.peak_unemployment = round(scenario.peak_unemployment * (1.0 - mitigation * 0.6), 2)
        scenario.duration_months = int(scenario.duration_months * (1.0 - mitigation * 0.3))
        return scenario


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _default_policies(crisis_type: CrisisType) -> List[str]:
    defaults: Dict[CrisisType, List[str]] = {
        CrisisType.GREAT_DEPRESSION: ["fiscal_stimulus", "bank_bailout", "rate_cuts"],
        CrisisType.FINANCIAL_CRISIS_2008: ["quantitative_easing", "bank_bailout", "rate_cuts"],
        CrisisType.HYPERINFLATION: ["rate_cuts", "capital_controls", "debt_restructuring"],
        CrisisType.DEFLATION_SPIRAL: ["quantitative_easing", "fiscal_stimulus"],
        CrisisType.SOVEREIGN_DEFAULT: ["debt_restructuring", "capital_controls"],
        CrisisType.BANK_RUN: ["bank_bailout", "deposit_insurance", "rate_cuts"],
    }
    return defaults.get(crisis_type, ["fiscal_stimulus", "rate_cuts"])
