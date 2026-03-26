"""
Core Chaos Orchestration Engine.

Design Label: CHAOS-001 — Core Chaos Orchestration Engine
Owner: Platform Engineering
Dependencies:
  - src.lcm_chaos_simulation (LCMChaosSimulation) — optional
  - src.chaos_resilience_loop (ChaosResilienceLoop) — optional

Generates, simulates, and manages chaos scenarios across all supported
scenario types with full reproducibility via seeded randomness.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_HISTORY = 1000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChaosScenarioType(Enum):
    WAR_SUPPLY_CHAIN = "war_supply_chain"
    ECONOMIC_DEPRESSION = "economic_depression"
    DISRUPTIVE_TECH = "disruptive_tech"
    MARKET_TRANSITION = "market_transition"
    TEMPORAL_MARKET = "temporal_market"
    NATURAL_DISASTER = "natural_disaster"
    PANDEMIC = "pandemic"
    REGULATORY_SHOCK = "regulatory_shock"
    CYBER_ATTACK = "cyber_attack"
    CURRENCY_CRISIS = "currency_crisis"


class ChaosIntensity(Enum):
    MILD = 1
    MODERATE = 3
    SEVERE = 5
    CATASTROPHIC = 7
    EXTINCTION_LEVEL = 10


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChaosScenario:
    scenario_id: str
    scenario_type: ChaosScenarioType
    intensity: ChaosIntensity
    parameters: Dict[str, Any]
    affected_sectors: List[str]
    start_epoch: float
    duration_days: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosOutcome:
    scenario_id: str
    affected_metrics: Dict[str, float]
    supply_chain_disruption_pct: float
    gdp_impact_pct: float
    market_volatility_multiplier: float
    recovery_time_days: int
    lessons_learned: List[str]


# ---------------------------------------------------------------------------
# ChaosEngine — CHAOS-001
# ---------------------------------------------------------------------------

class ChaosEngine:
    """CHAOS-001 — Core Chaos Orchestration Engine.

    Generates and simulates chaos scenarios with reproducible seeding.
    All public methods are thread-safe via an internal Lock.
    """

    _ALL_SECTORS = [
        "energy", "food", "manufacturing", "logistics", "finance",
        "technology", "healthcare", "agriculture", "defense", "telecoms",
        "retail", "real_estate", "utilities", "chemicals", "automotive",
    ]

    _SCENARIO_PARAMS: Dict[ChaosScenarioType, Dict[str, Any]] = {
        ChaosScenarioType.WAR_SUPPLY_CHAIN: {
            "conflict_regions": ["europe", "asia_pacific"],
            "blockade_probability": 0.4,
            "shipping_disruption_base": 0.35,
        },
        ChaosScenarioType.ECONOMIC_DEPRESSION: {
            "trigger": "credit_crunch",
            "unemployment_peak": 0.15,
            "gdp_contraction_base": 0.08,
        },
        ChaosScenarioType.DISRUPTIVE_TECH: {
            "technology": "general_ai",
            "adoption_rate": 0.6,
            "obsolescence_rate": 0.3,
        },
        ChaosScenarioType.MARKET_TRANSITION: {
            "from_system": "modern_fiat",
            "to_system": "cbdc",
            "transition_speed": "gradual",
        },
        ChaosScenarioType.TEMPORAL_MARKET: {
            "years_of_future_knowledge": 10,
            "arbitrage_potential": 0.85,
        },
        ChaosScenarioType.NATURAL_DISASTER: {
            "disaster_type": "earthquake",
            "affected_area_km2": 50_000,
            "infrastructure_loss_pct": 0.2,
        },
        ChaosScenarioType.PANDEMIC: {
            "pathogen_r0": 3.5,
            "mortality_rate": 0.01,
            "lockdown_duration_months": 6,
        },
        ChaosScenarioType.REGULATORY_SHOCK: {
            "regulation_type": "carbon_tax",
            "compliance_cost_pct": 0.05,
            "phase_in_years": 2,
        },
        ChaosScenarioType.CYBER_ATTACK: {
            "attack_vector": "ransomware",
            "systems_compromised_pct": 0.15,
            "data_loss_pct": 0.08,
        },
        ChaosScenarioType.CURRENCY_CRISIS: {
            "currency": "USD",
            "devaluation_pct": 0.30,
            "contagion_countries": 12,
        },
    }

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._history: List[ChaosOutcome] = []
        self._lcm_sim = None
        self._resilience_loop = None
        self._load_existing_chaos_modules()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_scenario(
        self,
        scenario_type: ChaosScenarioType,
        intensity: ChaosIntensity,
        affected_sectors: Optional[List[str]] = None,
    ) -> ChaosScenario:
        """Generate a reproducible ChaosScenario."""
        with self._lock:
            if affected_sectors is None:
                k = max(2, intensity.value)
                affected_sectors = self._rng.sample(self._ALL_SECTORS, min(k, len(self._ALL_SECTORS)))

            base_params = dict(self._SCENARIO_PARAMS.get(scenario_type, {}))
            intensity_factor = intensity.value / 10.0
            params: Dict[str, Any] = {}
            for key, val in base_params.items():
                if isinstance(val, float):
                    params[key] = min(1.0, val * (1.0 + intensity_factor * self._rng.uniform(0.5, 2.0)))
                elif isinstance(val, int):
                    params[key] = int(val * (1.0 + intensity_factor * self._rng.uniform(0.2, 1.5)))
                else:
                    params[key] = val

            duration_days = int(30 * intensity.value * self._rng.uniform(0.8, 2.5))

            scenario = ChaosScenario(
                scenario_id=str(uuid.uuid4()),
                scenario_type=scenario_type,
                intensity=intensity,
                parameters=params,
                affected_sectors=affected_sectors,
                start_epoch=time.time(),
                duration_days=duration_days,
                metadata={"generated_by": "ChaosEngine-CHAOS-001", "seed_used": True},
            )
            logger.debug("Generated scenario %s type=%s intensity=%s",
                         scenario.scenario_id, scenario_type.value, intensity.name)
            return scenario

    def simulate_scenario(self, scenario: ChaosScenario) -> ChaosOutcome:
        """Run a scenario through the simulation model and return a ChaosOutcome."""
        with self._lock:
            intensity_val = scenario.intensity.value
            rng = self._rng

            scd_pct = min(0.99, 0.05 * intensity_val * rng.uniform(0.7, 1.8))
            gdp_impact = -(0.02 * intensity_val * rng.uniform(0.5, 2.5))
            vol_mult = 1.0 + (0.5 * intensity_val * rng.uniform(0.8, 1.5))
            recovery_days = int(
                scenario.duration_days * (1.0 + (intensity_val / 10.0) * rng.uniform(0.5, 3.0))
            )

            affected_metrics: Dict[str, float] = {
                sector: round(rng.uniform(0.1, 1.0) * intensity_val / 10.0, 4)
                for sector in scenario.affected_sectors
            }

            lessons = _derive_lessons(scenario)

            outcome = ChaosOutcome(
                scenario_id=scenario.scenario_id,
                affected_metrics=affected_metrics,
                supply_chain_disruption_pct=round(scd_pct * 100, 2),
                gdp_impact_pct=round(gdp_impact * 100, 2),
                market_volatility_multiplier=round(vol_mult, 3),
                recovery_time_days=recovery_days,
                lessons_learned=lessons,
            )

            if self._lcm_sim is not None:
                try:
                    self._lcm_sim.record_outcome(scenario.scenario_type.value, outcome.gdp_impact_pct)
                except Exception as exc:
                    logger.debug("LCM record_outcome skipped: %s", exc)

            # capped_append
            if len(self._history) >= _MAX_HISTORY:
                self._history.pop(0)
            self._history.append(outcome)

            return outcome

    def run_scenario_battery(
        self,
        num_scenarios: int = 10,
        intensity_range: Optional[List[ChaosIntensity]] = None,
    ) -> List[ChaosOutcome]:
        """Generate and simulate a battery of random scenarios."""
        if intensity_range is None:
            intensity_range = list(ChaosIntensity)

        scenario_types = list(ChaosScenarioType)
        outcomes: List[ChaosOutcome] = []

        for _ in range(num_scenarios):
            stype = self._rng.choice(scenario_types)
            intensity = self._rng.choice(intensity_range)
            scenario = self.generate_scenario(stype, intensity)
            outcomes.append(self.simulate_scenario(scenario))

        avg_impact = sum(o.gdp_impact_pct for o in outcomes) / max(1, len(outcomes))
        logger.info("Battery complete: %d scenarios, avg_gdp_impact=%.2f%%", num_scenarios, avg_impact)
        return outcomes

    def get_training_data(self, outcomes: Optional[List[ChaosOutcome]] = None) -> List[Dict[str, Any]]:
        """Convert ChaosOutcome list into ML training examples."""
        with self._lock:
            source = outcomes if outcomes is not None else list(self._history)

        return [
            {
                "input": {
                    "supply_chain_disruption_pct": o.supply_chain_disruption_pct,
                    "market_volatility_multiplier": o.market_volatility_multiplier,
                    "affected_sector_count": len(o.affected_metrics),
                },
                "output": {
                    "gdp_impact_pct": o.gdp_impact_pct,
                    "recovery_time_days": o.recovery_time_days,
                },
                "labels": o.lessons_learned,
                "source": "ChaosEngine-CHAOS-001",
            }
            for o in source
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_existing_chaos_modules(self) -> None:
        """Load optional existing chaos modules with graceful fallback."""
        try:
            from src.lcm_chaos_simulation import LCMChaosSimulation  # type: ignore
            self._lcm_sim = LCMChaosSimulation()
            logger.debug("LCMChaosSimulation loaded into ChaosEngine")
        except Exception as exc:
            logger.debug("LCMChaosSimulation not available: %s", exc)

        try:
            from src.chaos_resilience_loop import ChaosResilienceLoop  # type: ignore
            self._resilience_loop = ChaosResilienceLoop()
            logger.debug("ChaosResilienceLoop loaded into ChaosEngine")
        except Exception as exc:
            logger.debug("ChaosResilienceLoop not available: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _derive_lessons(scenario: ChaosScenario) -> List[str]:
    lessons = [
        f"Diversify supply chains away from affected sectors: {', '.join(scenario.affected_sectors[:3])}",
        f"Build {scenario.duration_days}-day strategic reserves for critical inputs",
        f"Establish {scenario.intensity.name.lower()}-resilience protocols for {scenario.scenario_type.value}",
    ]
    if scenario.intensity in (ChaosIntensity.CATASTROPHIC, ChaosIntensity.EXTINCTION_LEVEL):
        lessons.append("Activate continuity-of-operations plans immediately")
        lessons.append("Coordinate with sovereign entities on systemic risk mitigation")
    return lessons
