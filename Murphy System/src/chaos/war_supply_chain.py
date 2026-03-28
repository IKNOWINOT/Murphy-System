"""
War and Conflict Supply Chain Disruption Simulator.

Design Label: CHAOS-002 — War Supply Chain Disruption Engine
Owner: Platform Engineering

Simulates the commodity, routing, and logistics impacts of armed conflict,
trade wars, sanctions, blockades, and hybrid warfare using historically
calibrated disruption models.

Historical calibration sources:
  WWII_PACIFIC       — Pacific shipping disruption ~80% (1941-1945)
  GULF_WAR_OIL       — Crude oil price spike ~+400% (1990-1991)
  UKRAINE_GRAIN      — Wheat futures +40% (2022)
  SUEZ_CRISIS        — Shipping rerouting costs +30% (1956)
  COVID_CONTAINERS   — Container rates +200% (2020-2022)

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

_MAX_EXAMPLES = 5000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConflictType(Enum):
    REGIONAL_WAR = "regional_war"
    WORLD_WAR = "world_war"
    TRADE_WAR = "trade_war"
    SANCTIONS = "sanctions"
    BLOCKADE = "blockade"
    CYBER_WARFARE = "cyber_warfare"
    HYBRID_WARFARE = "hybrid_warfare"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SupplyChainNode:
    node_id: str
    node_type: str  # port | factory | warehouse | route
    region: str
    capacity: float  # normalised 0-1
    vulnerability_score: float  # 0-1
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ConflictScenario:
    conflict_id: str
    conflict_type: ConflictType
    affected_regions: List[str]
    duration_months: int
    intensity: float  # 0-1
    start_date: str
    commodity_impacts: Dict[str, float]  # commodity → disruption pct


# ---------------------------------------------------------------------------
# WarSupplyChainSimulator — CHAOS-002
# ---------------------------------------------------------------------------

class WarSupplyChainSimulator:
    """CHAOS-002 — War Supply Chain Disruption Engine.

    Simulates commodity and logistics disruptions caused by armed and economic
    conflict.  Historically calibrated with five anchor events.
    """

    # -----------------------------------------------------------------------
    # Historical calibration anchors
    # -----------------------------------------------------------------------
    _HISTORICAL_SCENARIOS: Dict[str, Dict[str, Any]] = {
        "WWII_PACIFIC": {
            "conflict_type": ConflictType.WORLD_WAR,
            "regions": ["asia_pacific", "north_pacific"],
            "duration_months": 47,
            "intensity": 1.0,
            "commodity_impacts": {
                "shipping": 80.0, "rubber": 95.0, "tin": 70.0,
                "oil": 40.0, "food": 35.0,
            },
            "description": "Pacific theatre shipping disruption 1941-1945",
        },
        "GULF_WAR_OIL": {
            "conflict_type": ConflictType.REGIONAL_WAR,
            "regions": ["middle_east"],
            "duration_months": 7,
            "intensity": 0.75,
            "commodity_impacts": {
                "petroleum": 400.0, "natural_gas": 120.0, "petrochemicals": 80.0,
                "food": 15.0, "shipping": 20.0,
            },
            "description": "Gulf War crude oil price shock 1990-1991",
        },
        "UKRAINE_GRAIN": {
            "conflict_type": ConflictType.REGIONAL_WAR,
            "regions": ["eastern_europe", "black_sea"],
            "duration_months": 24,
            "intensity": 0.65,
            "commodity_impacts": {
                "wheat": 40.0, "corn": 25.0, "sunflower_oil": 60.0,
                "fertilizers": 45.0, "natural_gas": 200.0,
            },
            "description": "Russia-Ukraine conflict grain & energy shock 2022",
        },
        "SUEZ_CRISIS": {
            "conflict_type": ConflictType.BLOCKADE,
            "regions": ["middle_east", "north_africa"],
            "duration_months": 6,
            "intensity": 0.5,
            "commodity_impacts": {
                "shipping_routes": 30.0, "oil": 25.0, "transit_costs": 30.0,
            },
            "description": "Suez Canal closure rerouting costs 1956",
        },
        "COVID_CONTAINERS": {
            "conflict_type": ConflictType.HYBRID_WARFARE,
            "regions": ["global"],
            "duration_months": 24,
            "intensity": 0.8,
            "commodity_impacts": {
                "container_rates": 200.0, "electronics": 35.0, "automotive_parts": 45.0,
                "consumer_goods": 30.0, "pharmaceuticals": 20.0,
            },
            "description": "COVID-19 pandemic container shipping crisis 2020-2022",
        },
    }

    # Commodity disruption multipliers per conflict type
    _CONFLICT_COMMODITY_BASE: Dict[ConflictType, Dict[str, float]] = {
        ConflictType.REGIONAL_WAR: {
            "oil": 1.5, "food": 0.6, "metals": 0.8, "shipping": 0.7,
        },
        ConflictType.WORLD_WAR: {
            "oil": 2.0, "food": 1.5, "metals": 2.5, "shipping": 3.0, "labour": 1.8,
        },
        ConflictType.TRADE_WAR: {
            "manufactured_goods": 0.4, "semiconductors": 0.5, "agricultural": 0.3,
            "steel": 0.6, "aluminium": 0.5,
        },
        ConflictType.SANCTIONS: {
            "financial_services": 0.8, "energy": 0.6, "technology": 0.5,
            "luxury_goods": 1.2, "currency": 0.9,
        },
        ConflictType.BLOCKADE: {
            "shipping": 1.2, "transit_costs": 0.8, "port_throughput": 1.5,
        },
        ConflictType.CYBER_WARFARE: {
            "financial_services": 0.7, "energy_grid": 0.6, "logistics_systems": 0.5,
            "communications": 0.8,
        },
        ConflictType.HYBRID_WARFARE: {
            "information": 0.6, "energy": 0.5, "food": 0.3, "shipping": 0.7,
            "financial_services": 0.5,
        },
    }

    # Region multipliers — hotter regions amplify impact
    _REGION_MULTIPLIERS: Dict[str, float] = {
        "middle_east": 1.8,
        "asia_pacific": 1.5,
        "eastern_europe": 1.4,
        "north_africa": 1.3,
        "black_sea": 1.6,
        "north_pacific": 1.4,
        "global": 2.5,
        "western_europe": 1.1,
        "north_america": 0.8,
        "latin_america": 1.0,
    }

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._example_cache: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_conflict(
        self,
        conflict_type: ConflictType,
        regions: List[str],
        intensity: float,
        duration_months: int,
    ) -> Dict[str, Any]:
        """Simulate a conflict and return a comprehensive impact dictionary."""
        with self._lock:
            commodity_impacts = self._calculate_commodity_impacts(conflict_type, regions, intensity)
            recovery_months = self._calculate_recovery_timeline(conflict_type, intensity)
            rerouting_cost = self._simulate_rerouting_costs(conflict_type, regions)

            scenario = ConflictScenario(
                conflict_id=str(uuid.uuid4()),
                conflict_type=conflict_type,
                affected_regions=regions,
                duration_months=duration_months,
                intensity=intensity,
                start_date=_epoch_to_date(time.time()),
                commodity_impacts=commodity_impacts,
            )

            return {
                "conflict_id": scenario.conflict_id,
                "conflict_type": conflict_type.value,
                "affected_regions": regions,
                "duration_months": duration_months,
                "intensity": intensity,
                "commodity_impacts": commodity_impacts,
                "recovery_months": recovery_months,
                "rerouting_cost_multiplier": rerouting_cost,
                "supply_chain_nodes_affected": self._estimate_node_impact(regions, intensity),
                "gdp_impact_pct": self._estimate_gdp_impact(commodity_impacts, intensity),
                "historical_analogs": self.get_historical_analogs(scenario),
            }

    def get_historical_analogs(self, scenario: ConflictScenario) -> List[str]:
        """Return names of historical scenarios most similar to the given one."""
        analogs: List[str] = []
        for name, hist in self._HISTORICAL_SCENARIOS.items():
            if hist["conflict_type"] == scenario.conflict_type:
                analogs.append(name)
            elif any(r in hist["regions"] for r in scenario.affected_regions):
                analogs.append(name)
        return analogs[:3]

    def generate_training_examples(self, num_scenarios: int = 50) -> List[Dict[str, Any]]:
        """Generate ML training examples by running randomised conflict simulations."""
        with self._lock:
            examples: List[Dict[str, Any]] = []
            conflict_types = list(ConflictType)
            all_regions = list(self._REGION_MULTIPLIERS.keys())

            for _ in range(num_scenarios):
                ctype = self._rng.choice(conflict_types)
                regions = self._rng.sample(all_regions, self._rng.randint(1, 3))
                intensity = self._rng.uniform(0.1, 1.0)
                duration = self._rng.randint(1, 60)
                impacts = self._calculate_commodity_impacts(ctype, regions, intensity)
                gdp = self._estimate_gdp_impact(impacts, intensity)

                example: Dict[str, Any] = {
                    "input": {
                        "conflict_type": ctype.value,
                        "num_regions": len(regions),
                        "intensity": round(intensity, 3),
                        "duration_months": duration,
                    },
                    "output": {
                        "gdp_impact_pct": gdp,
                        "recovery_months": self._calculate_recovery_timeline(ctype, intensity),
                        "avg_commodity_disruption": (
                            sum(impacts.values()) / max(1, len(impacts))
                        ),
                    },
                    "commodity_impacts": impacts,
                    "source": "WarSupplyChainSimulator-CHAOS-002",
                }
                # capped_append
                if len(self._example_cache) < _MAX_EXAMPLES:
                    self._example_cache.append(example)
                examples.append(example)

            return examples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_commodity_impacts(
        self,
        conflict_type: ConflictType,
        regions: List[str],
        intensity: float,
    ) -> Dict[str, float]:
        """Return a dict mapping commodity names to disruption percentages."""
        base = self._CONFLICT_COMMODITY_BASE.get(conflict_type, {})
        region_mult = max(
            (self._REGION_MULTIPLIERS.get(r, 1.0) for r in regions), default=1.0
        )
        impacts: Dict[str, float] = {}
        for commodity, base_val in base.items():
            noise = self._rng.uniform(0.8, 1.3)
            impacts[commodity] = round(base_val * intensity * region_mult * noise * 100.0, 2)
        return impacts

    def _calculate_recovery_timeline(self, conflict_type: ConflictType, intensity: float) -> int:
        """Estimate recovery period in months."""
        base_months = {
            ConflictType.REGIONAL_WAR: 24,
            ConflictType.WORLD_WAR: 120,
            ConflictType.TRADE_WAR: 36,
            ConflictType.SANCTIONS: 18,
            ConflictType.BLOCKADE: 6,
            ConflictType.CYBER_WARFARE: 3,
            ConflictType.HYBRID_WARFARE: 18,
        }
        base = base_months.get(conflict_type, 12)
        return int(base * intensity * self._rng.uniform(0.7, 1.5))

    def _simulate_rerouting_costs(self, conflict_type: ConflictType, affected_regions: List[str]) -> float:
        """Return a cost multiplier for alternative routing (1.0 = no extra cost)."""
        base_cost = {
            ConflictType.BLOCKADE: 1.35,
            ConflictType.REGIONAL_WAR: 1.20,
            ConflictType.WORLD_WAR: 2.10,
            ConflictType.TRADE_WAR: 1.15,
            ConflictType.SANCTIONS: 1.25,
            ConflictType.CYBER_WARFARE: 1.10,
            ConflictType.HYBRID_WARFARE: 1.18,
        }.get(conflict_type, 1.05)

        region_penalty = sum(
            0.05 for r in affected_regions if r in ("black_sea", "middle_east", "asia_pacific")
        )
        return round(base_cost + region_penalty + self._rng.uniform(-0.05, 0.05), 3)

    def _estimate_node_impact(self, regions: List[str], intensity: float) -> int:
        """Estimate how many supply chain nodes are affected."""
        nodes_per_region = {"global": 500, "middle_east": 120, "asia_pacific": 200}
        total = sum(nodes_per_region.get(r, 80) for r in regions)
        return int(total * intensity * self._rng.uniform(0.5, 1.0))

    def _estimate_gdp_impact(self, commodity_impacts: Dict[str, float], intensity: float) -> float:
        """Derive a GDP impact percentage from commodity disruptions."""
        if not commodity_impacts:
            return 0.0
        avg_disruption = sum(commodity_impacts.values()) / len(commodity_impacts)
        return round(-(avg_disruption / 100.0) * intensity * self._rng.uniform(0.1, 0.4), 3)


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _epoch_to_date(epoch: float) -> str:
    import datetime
    return datetime.datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%d")
