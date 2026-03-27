"""
Disruptive Technology Simulation.

Design Label: CHAOS-004 — Disruptive Technology Simulator
Owner: Platform Engineering

Models the economic and market impact of disruptive technologies including
General AI, quantum computing, biotech, and the whimsically-but-rigorously
modelled case of time-travel economics.

"What happens to grain futures if someone with 2035 crop-yield data arrives in 2024?"
— spoiler: it depends on how quickly regulators notice the impossible hit-rate.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_EXAMPLES = 5000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DisruptionType(Enum):
    GENERAL_AI = "general_ai"
    QUANTUM_COMPUTING = "quantum_computing"
    BIOTECH_REVOLUTION = "biotech_revolution"
    TIME_TRAVEL_ECONOMICS = "time_travel_economics"
    COLD_FUSION = "cold_fusion"
    MOLECULAR_ASSEMBLY = "molecular_assembly"
    BRAIN_COMPUTER_INTERFACE = "brain_computer_interface"
    AUTONOMOUS_SYSTEMS = "autonomous_systems"
    SPACE_MINING = "space_mining"
    SYNTHETIC_BIOLOGY = "synthetic_biology"


class DisruptionPhase(Enum):
    INVENTION = "invention"
    EARLY_ADOPTION = "early_adoption"
    GROWTH = "growth"
    MASS_ADOPTION = "mass_adoption"
    SATURATION = "saturation"
    DISRUPTION_COMPLETE = "disruption_complete"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TechDisruptionScenario:
    disruption_id: str
    disruption_type: DisruptionType
    phase: DisruptionPhase
    year_introduced: int
    affected_industries: List[str]
    obsoleted_jobs_pct: float
    new_jobs_created_pct: float
    gdp_impact_pct: float
    timeline_years: int
    market_shifts: Dict[str, float]


# ---------------------------------------------------------------------------
# Phase GDP multipliers — how much each phase amplifies net GDP impact
# ---------------------------------------------------------------------------

_PHASE_GDP_MULT = {
    DisruptionPhase.INVENTION: 0.05,
    DisruptionPhase.EARLY_ADOPTION: 0.15,
    DisruptionPhase.GROWTH: 0.40,
    DisruptionPhase.MASS_ADOPTION: 0.80,
    DisruptionPhase.SATURATION: 1.00,
    DisruptionPhase.DISRUPTION_COMPLETE: 1.10,
}

# Base GDP impact and job disruption profiles per technology
_TECH_PROFILES: Dict[DisruptionType, Dict[str, Any]] = {
    DisruptionType.GENERAL_AI: {
        "base_gdp_impact": 14.0,
        "obsoleted_jobs_pct": 35.0,
        "new_jobs_pct": 28.0,
        "timeline_years": 20,
        "industries": ["knowledge_work", "manufacturing", "healthcare", "finance", "logistics"],
    },
    DisruptionType.QUANTUM_COMPUTING: {
        "base_gdp_impact": 5.0,
        "obsoleted_jobs_pct": 8.0,
        "new_jobs_pct": 12.0,
        "timeline_years": 15,
        "industries": ["cryptography", "pharmaceuticals", "finance", "logistics", "energy"],
    },
    DisruptionType.BIOTECH_REVOLUTION: {
        "base_gdp_impact": 8.0,
        "obsoleted_jobs_pct": 12.0,
        "new_jobs_pct": 18.0,
        "timeline_years": 25,
        "industries": ["pharmaceuticals", "agriculture", "healthcare", "food_production"],
    },
    DisruptionType.TIME_TRAVEL_ECONOMICS: {
        "base_gdp_impact": 50.0,   # theoretical upper bound — infinite arbitrage potential
        "obsoleted_jobs_pct": 60.0,
        "new_jobs_pct": 5.0,       # very few new sustainable roles
        "timeline_years": 1,       # singularity-fast market adaptation
        "industries": ["finance", "commodities", "insurance", "forecasting", "journalism"],
    },
    DisruptionType.COLD_FUSION: {
        "base_gdp_impact": 20.0,
        "obsoleted_jobs_pct": 25.0,
        "new_jobs_pct": 10.0,
        "timeline_years": 30,
        "industries": ["fossil_fuels", "utilities", "automotive", "aerospace"],
    },
    DisruptionType.MOLECULAR_ASSEMBLY: {
        "base_gdp_impact": 35.0,
        "obsoleted_jobs_pct": 50.0,
        "new_jobs_pct": 20.0,
        "timeline_years": 40,
        "industries": ["manufacturing", "retail", "logistics", "mining", "pharmaceuticals"],
    },
    DisruptionType.BRAIN_COMPUTER_INTERFACE: {
        "base_gdp_impact": 10.0,
        "obsoleted_jobs_pct": 20.0,
        "new_jobs_pct": 22.0,
        "timeline_years": 20,
        "industries": ["healthcare", "education", "media", "communications", "defence"],
    },
    DisruptionType.AUTONOMOUS_SYSTEMS: {
        "base_gdp_impact": 12.0,
        "obsoleted_jobs_pct": 30.0,
        "new_jobs_pct": 15.0,
        "timeline_years": 15,
        "industries": ["transportation", "logistics", "manufacturing", "agriculture", "defence"],
    },
    DisruptionType.SPACE_MINING: {
        "base_gdp_impact": 8.0,
        "obsoleted_jobs_pct": 10.0,
        "new_jobs_pct": 14.0,
        "timeline_years": 35,
        "industries": ["mining", "metals", "aerospace", "energy", "manufacturing"],
    },
    DisruptionType.SYNTHETIC_BIOLOGY: {
        "base_gdp_impact": 9.0,
        "obsoleted_jobs_pct": 15.0,
        "new_jobs_pct": 20.0,
        "timeline_years": 25,
        "industries": ["pharmaceuticals", "agriculture", "food_production", "chemicals", "energy"],
    },
}


# ---------------------------------------------------------------------------
# TimeTravelEconomics — special sub-class
# ---------------------------------------------------------------------------

class TimeTravelEconomics:
    """Models information asymmetry from temporal knowledge.

    Mathematical framework:
      - Arbitrage potential scales as log(years) × market_depth_factor
      - Regulatory crackdown probability rises with hit-rate anomaly score
      - Paradox probability follows a logistic curve (self-defeating prophecy)

    "What happens to grain futures if someone with 2035 crop-yield data arrives in 2024?"
    Model answer: Unlimited profit until regulators detect a statistically impossible
    win-rate (~5-12 months at human reaction speed), followed by market freeze,
    inquiry, and either new temporal-trading regulation or paradox collapse.
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng or random.Random()

    def simulate_time_travel_market_impact(
        self, years_of_future_knowledge: int, market: str = "stock"
    ) -> Dict[str, Any]:
        """Return market distortion metrics for a temporal arbitrageur."""
        arb = self._calculate_arbitrage_potential(years_of_future_knowledge, market)
        regulatory = self._model_regulatory_response(arb["asymmetry_level"])
        paradox_prob = self._calculate_paradox_probability(years_of_future_knowledge)

        # Market distortion escalates until regulatory crackdown
        months_before_detection = max(1, int(12.0 / (arb["hit_rate_anomaly_sigma"] * 0.5)))

        return {
            "years_of_knowledge": years_of_future_knowledge,
            "market": market,
            "theoretical_max_return_pct_annual": arb["max_return_pct"],
            "asymmetry_level": arb["asymmetry_level"],
            "hit_rate_anomaly_sigma": arb["hit_rate_anomaly_sigma"],
            "months_before_regulatory_detection": months_before_detection,
            "market_distortion_magnitude": arb["distortion_magnitude"],
            "regulatory_response": regulatory,
            "paradox_probability": paradox_prob,
            "scenario_note": (
                f"Trader with {years_of_future_knowledge}y of future data achieves "
                f"{arb['hit_rate_anomaly_sigma']:.1f}σ hit-rate anomaly, "
                f"triggering {regulatory['response_type']} in ~{months_before_detection} months. "
                f"Self-defeating paradox probability: {paradox_prob:.1%}"
            ),
        }

    def _calculate_arbitrage_potential(self, years: int, market: str) -> Dict[str, float]:
        """Compute theoretical arbitrage value from temporal information advantage."""
        # log-scaling: diminishing returns beyond ~20 years (regime changes dominate)
        info_value = math.log1p(years) * 10.0

        market_depth = {
            "stock": 1.0, "commodity": 1.3, "forex": 1.1,
            "crypto": 2.0, "bond": 0.7, "real_estate": 0.5,
        }.get(market, 1.0)

        max_return = info_value * market_depth * self._rng.uniform(8.0, 15.0)
        hit_rate_anomaly = info_value * market_depth * 0.8  # sigma units
        distortion = min(10.0, info_value * market_depth / 5.0)

        return {
            "max_return_pct": round(max_return, 1),
            "asymmetry_level": round(info_value * market_depth, 2),
            "hit_rate_anomaly_sigma": round(hit_rate_anomaly, 2),
            "distortion_magnitude": round(distortion, 3),
        }

    def _model_regulatory_response(self, asymmetry_level: float) -> Dict[str, Any]:
        """Return regulatory crackdown scenario based on information asymmetry level."""
        if asymmetry_level < 5.0:
            response_type = "enhanced_surveillance"
            market_freeze_probability = 0.05
            fine_usd_millions = round(asymmetry_level * 10.0, 1)
        elif asymmetry_level < 15.0:
            response_type = "trading_halt_and_investigation"
            market_freeze_probability = 0.35
            fine_usd_millions = round(asymmetry_level * 50.0, 1)
        elif asymmetry_level < 30.0:
            response_type = "market_circuit_breaker_and_criminal_referral"
            market_freeze_probability = 0.70
            fine_usd_millions = round(asymmetry_level * 200.0, 1)
        else:
            response_type = "full_market_suspension_and_temporal_act_legislation"
            market_freeze_probability = 0.98
            fine_usd_millions = round(asymmetry_level * 1000.0, 1)

        return {
            "response_type": response_type,
            "market_freeze_probability": market_freeze_probability,
            "fine_usd_millions": fine_usd_millions,
            "international_coordination_required": asymmetry_level > 20.0,
            "estimated_legislative_response_months": max(3, int(24 / (1 + asymmetry_level / 10))),
        }

    def _calculate_paradox_probability(self, years: int) -> float:
        """Logistic probability that future-knowledge creates a self-defeating outcome.

        At 1 year ahead: ~5% paradox chance (small info, minimal butterfly effect).
        At 10 years ahead: ~50% (regime changes, feedback loops).
        At 50+ years ahead: ~99% (complete temporal self-cancellation).
        """
        return round(1.0 / (1.0 + math.exp(-0.3 * (years - 10))), 4)


# ---------------------------------------------------------------------------
# DisruptiveTechnologySimulator — CHAOS-004
# ---------------------------------------------------------------------------

class DisruptiveTechnologySimulator:
    """CHAOS-004 — Disruptive Technology Simulator.

    Models economic disruption across the technology adoption lifecycle,
    including the special case of time-travel economics.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.RLock()  # RLock: simulate_time_travel_economics calls simulate_disruption
        self._time_travel = TimeTravelEconomics(rng=self._rng)
        self._example_cache: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_disruption(
        self,
        disruption_type: DisruptionType,
        phase: Optional[DisruptionPhase] = None,
        year: Optional[int] = None,
    ) -> TechDisruptionScenario:
        """Generate a TechDisruptionScenario for the given disruption type."""
        with self._lock:
            profile = _TECH_PROFILES.get(disruption_type, {
                "base_gdp_impact": 5.0,
                "obsoleted_jobs_pct": 10.0,
                "new_jobs_pct": 8.0,
                "timeline_years": 20,
                "industries": ["manufacturing", "services"],
            })

            if phase is None:
                phase = self._rng.choice(list(DisruptionPhase))

            phase_mult = _PHASE_GDP_MULT[phase]
            noise = self._rng.uniform(0.8, 1.3)

            gdp_impact = profile["base_gdp_impact"] * phase_mult * noise
            obsoleted = profile["obsoleted_jobs_pct"] * phase_mult * noise
            new_jobs = profile["new_jobs_pct"] * phase_mult * noise

            industries = list(profile["industries"])
            displacement = self._model_industry_displacement(disruption_type, phase)
            transition_costs = self._calculate_transition_costs_internal(obsoleted, gdp_impact)

            return TechDisruptionScenario(
                disruption_id=str(uuid.uuid4()),
                disruption_type=disruption_type,
                phase=phase,
                year_introduced=year or (2024 + self._rng.randint(0, 15)),
                affected_industries=industries,
                obsoleted_jobs_pct=round(obsoleted, 2),
                new_jobs_created_pct=round(new_jobs, 2),
                gdp_impact_pct=round(gdp_impact, 2),
                timeline_years=profile["timeline_years"],
                market_shifts={**displacement, "transition_cost_gdp_pct": transition_costs},
            )

    def simulate_time_travel_economics(self, years_ahead: int = 10) -> Dict[str, Any]:
        """Return a detailed time-travel market analysis for the given knowledge horizon."""
        with self._lock:
            markets = ["stock", "commodity", "forex", "crypto", "bond"]
            results: Dict[str, Any] = {}
            for market in markets:
                results[market] = self._time_travel.simulate_time_travel_market_impact(
                    years_ahead, market
                )

            grain_case = self._simulate_grain_futures_case(years_ahead)
            scenario = self.simulate_disruption(DisruptionType.TIME_TRAVEL_ECONOMICS)

            return {
                "years_ahead": years_ahead,
                "market_analyses": results,
                "grain_futures_case_study": grain_case,
                "disruption_scenario": {
                    "disruption_id": scenario.disruption_id,
                    "gdp_impact_pct": scenario.gdp_impact_pct,
                    "obsoleted_jobs_pct": scenario.obsoleted_jobs_pct,
                    "affected_industries": scenario.affected_industries,
                    "market_shifts": scenario.market_shifts,
                },
            }

    def generate_training_examples(self, num_scenarios: int = 50) -> List[Dict[str, Any]]:
        """Generate ML training data from random disruption simulations."""
        with self._lock:
            examples: List[Dict[str, Any]] = []
            dtypes = list(DisruptionType)
            phases = list(DisruptionPhase)

            for _ in range(num_scenarios):
                dtype = self._rng.choice(dtypes)
                phase = self._rng.choice(phases)
                scenario = self.simulate_disruption(dtype, phase)

                example: Dict[str, Any] = {
                    "input": {
                        "disruption_type": dtype.value,
                        "phase": phase.value,
                        "year_introduced": scenario.year_introduced,
                        "num_industries_affected": len(scenario.affected_industries),
                    },
                    "output": {
                        "gdp_impact_pct": scenario.gdp_impact_pct,
                        "obsoleted_jobs_pct": scenario.obsoleted_jobs_pct,
                        "new_jobs_created_pct": scenario.new_jobs_created_pct,
                        "timeline_years": scenario.timeline_years,
                    },
                    "market_shifts": scenario.market_shifts,
                    "source": "DisruptiveTechnologySimulator-CHAOS-004",
                }
                if len(self._example_cache) < _MAX_EXAMPLES:
                    self._example_cache.append(example)
                examples.append(example)

            return examples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _model_industry_displacement(
        self, disruption_type: DisruptionType, phase: DisruptionPhase
    ) -> Dict[str, float]:
        """Return industry-level displacement fractions (0-1)."""
        profile = _TECH_PROFILES.get(disruption_type, {})
        phase_mult = _PHASE_GDP_MULT[phase]
        return {
            industry: round(phase_mult * self._rng.uniform(0.2, 1.0), 3)
            for industry in profile.get("industries", [])
        }

    def _calculate_transition_costs_internal(
        self, obsoleted_jobs_pct: float, gdp_impact_pct: float
    ) -> float:
        """Estimate retraining and adaptation costs as GDP percentage."""
        retraining_cost = obsoleted_jobs_pct * 0.02   # ~2% of GDP per 100% job obsolescence
        adaptation_cost = gdp_impact_pct * 0.05
        return round(retraining_cost + adaptation_cost, 3)

    def _calculate_transition_costs(self, scenario: TechDisruptionScenario) -> float:
        """Public-facing wrapper for transition cost calculation."""
        return self._calculate_transition_costs_internal(
            scenario.obsoleted_jobs_pct, scenario.gdp_impact_pct
        )

    def _simulate_grain_futures_case(self, years_ahead: int) -> Dict[str, Any]:
        """Detailed case study: temporal arbitrageur in grain futures market.

        Model: A traveller from year (2024 + years_ahead) arrives in 2024 with
        perfect crop-yield forecasts.  We trace market impact, detection, and
        regulatory collapse.
        """
        # Perfect knowledge of crop yields → perfect futures positioning
        hit_rate = 1.0  # 100% accurate
        baseline_hit_rate = 0.52  # random walk baseline
        z_score = (hit_rate - baseline_hit_rate) / (0.5 / math.sqrt(250))  # 250 trading days

        # Days until anomaly exceeds 5σ detection threshold
        days_to_detect = max(5, int(5.0 / max(0.01, z_score) * 250))

        # Profit before detection
        daily_return = 0.012 * years_ahead  # more future knowledge → bigger edge
        profit_multiple = (1.0 + daily_return) ** min(days_to_detect, 252)

        return {
            "scenario": f"Temporal arbitrageur with {years_ahead}-year crop yield data in grain futures",
            "hit_rate_pct": 100.0,
            "baseline_hit_rate_pct": 52.0,
            "z_score_anomaly": round(z_score, 1),
            "days_until_5sigma_detection": days_to_detect,
            "profit_multiple_before_detection": round(profit_multiple, 2),
            "estimated_profit_usd_millions": round(profit_multiple * 10.0, 1),
            "regulatory_outcome": (
                "SEC/CFTC investigation → trading halt → temporal information act emergency legislation"
                if days_to_detect < 60 else
                "Pattern flagged by algo surveillance → quiet investigation → asset freeze"
            ),
            "market_impact_after_exposure": {
                "wheat_futures_vol_spike": round(self._rng.uniform(1.5, 4.0) * years_ahead / 5.0, 2),
                "corn_futures_vol_spike": round(self._rng.uniform(1.3, 3.5) * years_ahead / 5.0, 2),
                "exchange_circuit_breakers_triggered": days_to_detect < 30,
            },
            "paradox_note": (
                "Once the traveller's foreknowledge becomes public, farmers adjust planting, "
                "altering the future yield data — classic bootstrap paradox rendering "
                f"{years_ahead}-year-old crop reports obsolete within one growing season."
            ),
        }
