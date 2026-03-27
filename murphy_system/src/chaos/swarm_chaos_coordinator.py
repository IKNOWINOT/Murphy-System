"""
Multi-Cursor + Swarm Augmented Chaos Scenario Coordinator.

Design Label: CHAOS-006 — Swarm Chaos Coordinator
Owner: Platform Engineering
Dependencies:
  - src.agent_module_loader (MultiCursorBrowser) — optional
  - src.domain_swarms (DomainSwarmGenerator) — optional
  - src.chaos.chaos_engine
  - src.chaos.war_supply_chain
  - src.chaos.economic_depression
  - src.chaos.market_transitions

Coordinates parallel chaos scenario execution across browser cursors and
domain-specific agent swarms to generate large-scale training datasets.

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
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_RESULTS = 50_000


# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from src.agent_module_loader import MultiCursorBrowser  # type: ignore
    _HAS_MULTI_CURSOR = True
except Exception as _mc_err:
    MultiCursorBrowser = None  # type: ignore
    _HAS_MULTI_CURSOR = False
    logger.debug("MultiCursorBrowser not available: %s", _mc_err)

try:
    from src.domain_swarms import DomainSwarmGenerator  # type: ignore
    _HAS_DOMAIN_SWARM = True
except Exception as _ds_err:
    DomainSwarmGenerator = None  # type: ignore
    _HAS_DOMAIN_SWARM = False
    logger.debug("DomainSwarmGenerator not available: %s", _ds_err)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SwarmChaosTask:
    task_id: str
    scenario_type: str
    assigned_cursors: List[int]
    assigned_agents: List[str]
    status: str  # pending | running | done | failed
    results: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# ---------------------------------------------------------------------------
# SwarmChaosCoordinator — CHAOS-006
# ---------------------------------------------------------------------------

class SwarmChaosCoordinator:
    """CHAOS-006 — Swarm Chaos Coordinator.

    Distributes chaos scenario simulations across a pool of virtual browser
    cursors and domain-specific agent workers for massively parallel generation
    of training data.
    """

    def __init__(self, max_cursors: int = 8, max_agents: int = 16) -> None:
        self._max_cursors = min(max_cursors, 64)   # MultiCursorBrowser caps at 64
        self._max_agents = max_agents
        self._lock = threading.Lock()
        self._result_store: List[Dict[str, Any]] = []
        self._tasks: List[SwarmChaosTask] = []
        self._executor = ThreadPoolExecutor(max_workers=max(4, max_cursors))
        self._rng = random.Random()

        # Lazy-load simulators to avoid circular imports
        self._war_sim = None
        self._depression_sim = None
        self._market_sim = None
        self._chaos_engine = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn_chaos_swarm(
        self, scenarios: List[Dict[str, Any]], parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """Run a list of scenario descriptors via the cursor/agent swarm.

        Each descriptor: {"type": "<scenario_type>", "params": {...}}
        Returns aggregated results.
        """
        tasks = self._build_tasks(scenarios)

        if parallel:
            futures: List[Future] = []
            for task in tasks:
                future = self._executor.submit(self._run_task, task)
                futures.append(future)
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("Swarm task failed: %s", exc)
        else:
            for task in tasks:
                self._run_task(task)

        return self._coordinate_results(tasks)

    def run_war_supply_chain_swarm(self, num_scenarios: int = 20) -> List[Dict[str, Any]]:
        """Run war/supply-chain scenarios in parallel swarm."""
        sim = self._get_war_sim()
        descriptors = [
            {"type": "war_supply_chain", "params": {"num": i}}
            for i in range(num_scenarios)
        ]
        return self.spawn_chaos_swarm(descriptors, parallel=True)

    def run_economic_depression_swarm(self, num_scenarios: int = 20) -> List[Dict[str, Any]]:
        """Run economic depression scenarios in parallel swarm."""
        descriptors = [
            {"type": "economic_depression", "params": {"num": i}}
            for i in range(num_scenarios)
        ]
        return self.spawn_chaos_swarm(descriptors, parallel=True)

    def run_market_transition_swarm(self, num_scenarios: int = 20) -> List[Dict[str, Any]]:
        """Run market transition scenarios in parallel swarm."""
        descriptors = [
            {"type": "market_transition", "params": {"num": i}}
            for i in range(num_scenarios)
        ]
        return self.spawn_chaos_swarm(descriptors, parallel=True)

    def run_full_chaos_battery(self, intensity: str = "severe") -> Dict[str, Any]:
        """Run all scenario types in parallel and return a consolidated report."""
        intensity_map = {
            "mild": 5, "moderate": 10, "severe": 20, "catastrophic": 50, "extinction": 100
        }
        n = intensity_map.get(intensity.lower(), 20)

        all_types = [
            "war_supply_chain", "economic_depression", "market_transition",
            "disruptive_tech", "temporal_market", "natural_disaster",
            "pandemic", "regulatory_shock", "cyber_attack", "currency_crisis",
        ]

        descriptors = [
            {"type": stype, "params": {"num": i, "intensity": intensity}}
            for stype in all_types
            for i in range(n // len(all_types) + 1)
        ]

        results = self.spawn_chaos_swarm(descriptors, parallel=True)

        by_type: Dict[str, List] = {}
        for r in results:
            stype = r.get("scenario_type", "unknown")
            by_type.setdefault(stype, []).append(r)

        return {
            "battery_id": str(uuid.uuid4()),
            "intensity": intensity,
            "total_scenarios_run": len(results),
            "scenario_types": list(all_types),
            "results_by_type": {k: len(v) for k, v in by_type.items()},
            "aggregate_stats": _aggregate_stats(results),
        }

    def generate_augmented_training_data(self, total_examples: int = 10_000) -> List[Dict[str, Any]]:
        """Use the full swarm to generate a large ML training dataset."""
        per_type = total_examples // 10
        all_examples: List[Dict[str, Any]] = []

        war_sim = self._get_war_sim()
        dep_sim = self._get_depression_sim()
        mkt_sim = self._get_market_sim()
        engine = self._get_chaos_engine()

        futures: List[Future] = []

        def _gen_war():
            return war_sim.generate_training_examples(per_type)

        def _gen_depression():
            return dep_sim.generate_training_examples(per_type)

        def _gen_market():
            return mkt_sim.generate_training_examples(per_type)

        def _gen_engine():
            outcomes = engine.run_scenario_battery(per_type)
            return engine.get_training_data(outcomes)

        for fn in [_gen_war, _gen_depression, _gen_market, _gen_engine]:
            futures.append(self._executor.submit(fn))

        for future in as_completed(futures):
            try:
                batch = future.result()
                all_examples.extend(batch)
            except Exception as exc:
                logger.warning("Training data generation batch failed: %s", exc)

        # Supplement to reach total_examples
        while len(all_examples) < total_examples:
            all_examples.extend(engine.get_training_data(engine.run_scenario_battery(50)))

        # capped_append to result store
        with self._lock:
            for ex in all_examples:
                if len(self._result_store) < _MAX_RESULTS:
                    self._result_store.append(ex)

        logger.info("Generated %d augmented training examples", len(all_examples))
        return all_examples[:total_examples]

    # ------------------------------------------------------------------
    # Internal task machinery
    # ------------------------------------------------------------------

    def _build_tasks(self, scenarios: List[Dict[str, Any]]) -> List[SwarmChaosTask]:
        """Build SwarmChaosTask objects, distributing cursors and agents."""
        tasks: List[SwarmChaosTask] = []
        for i, desc in enumerate(scenarios):
            cursor_pool = list(range(self._max_cursors))
            assigned_cursors = [cursor_pool[i % self._max_cursors]]
            assigned_agents = [f"agent_{j}" for j in range(min(2, self._max_agents))]

            task = SwarmChaosTask(
                task_id=str(uuid.uuid4()),
                scenario_type=desc.get("type", "generic"),
                assigned_cursors=assigned_cursors,
                assigned_agents=assigned_agents,
                status="pending",
            )
            with self._lock:
                if len(self._tasks) < _MAX_RESULTS:
                    self._tasks.append(task)
            tasks.append(task)

        return tasks

    def _run_task(self, task: SwarmChaosTask) -> None:
        """Execute a single SwarmChaosTask using the appropriate simulator."""
        task.status = "running"
        try:
            results = self._dispatch_to_simulator(task.scenario_type)
            task.results = results
            task.status = "done"
        except Exception as exc:
            logger.warning("Task %s failed: %s", task.task_id, exc)
            task.status = "failed"
            task.results = [{"error": str(exc)}]
        finally:
            task.completed_at = time.time()

    def _dispatch_to_simulator(self, scenario_type: str) -> List[Dict[str, Any]]:
        """Route a scenario type to its simulator and return results."""
        if scenario_type == "war_supply_chain":
            sim = self._get_war_sim()
            from src.chaos.war_supply_chain import ConflictType  # type: ignore
            ctype = self._rng.choice(list(ConflictType))
            regions = self._rng.sample(["middle_east", "asia_pacific", "eastern_europe", "global"], 2)
            return [sim.simulate_conflict(ctype, regions, self._rng.uniform(0.2, 1.0), self._rng.randint(3, 36))]

        if scenario_type == "economic_depression":
            sim = self._get_depression_sim()
            from src.chaos.economic_depression import CrisisType  # type: ignore
            ctype = self._rng.choice(list(CrisisType))
            sc = sim.simulate_crisis(ctype)
            return [{"crisis_id": sc.crisis_id, "crisis_type": sc.crisis_type.value,
                     "gdp_contraction_pct": sc.gdp_contraction_pct,
                     "peak_unemployment": sc.peak_unemployment}]

        if scenario_type == "market_transition":
            sim = self._get_market_sim()
            from src.chaos.market_transitions import CurrencySystem  # type: ignore
            systems = list(CurrencySystem)
            from_sys = self._rng.choice(systems)
            to_sys = self._rng.choice([s for s in systems if s != from_sys])
            sc = sim.simulate_transition(from_sys, to_sys)
            return [{"transition_id": sc.transition_id,
                     "from": sc.from_system.value, "to": sc.to_system.value,
                     "volatility_multiplier": sc.volatility_multiplier}]

        # Default: use ChaosEngine
        engine = self._get_chaos_engine()
        from src.chaos.chaos_engine import ChaosScenarioType, ChaosIntensity  # type: ignore
        stype = self._rng.choice(list(ChaosScenarioType))
        intensity = self._rng.choice(list(ChaosIntensity))
        scenario = engine.generate_scenario(stype, intensity)
        outcome = engine.simulate_scenario(scenario)
        return [{"scenario_id": outcome.scenario_id,
                 "gdp_impact_pct": outcome.gdp_impact_pct,
                 "scenario_type": stype.value}]

    def _coordinate_results(self, tasks: List[SwarmChaosTask]) -> List[Dict[str, Any]]:
        """Aggregate results from all completed swarm tasks."""
        aggregated: List[Dict[str, Any]] = []
        for task in tasks:
            for result in task.results:
                entry = {"task_id": task.task_id, "scenario_type": task.scenario_type, **result}
                aggregated.append(entry)
                with self._lock:
                    if len(self._result_store) < _MAX_RESULTS:
                        self._result_store.append(entry)
        return aggregated

    def _spawn_cursor_workers(self, scenarios: List[Dict[str, Any]]) -> List[Any]:
        """Create MultiCursorBrowser workers if available, else stub list."""
        if _HAS_MULTI_CURSOR and MultiCursorBrowser is not None:
            try:
                browser = MultiCursorBrowser(max_cursors=self._max_cursors)
                return [browser]
            except Exception as exc:
                logger.debug("MultiCursorBrowser init failed: %s", exc)
        return [{"stub_cursor": i} for i in range(min(len(scenarios), self._max_cursors))]

    def _spawn_agent_workers(self, scenarios: List[Dict[str, Any]]) -> List[Any]:
        """Spawn domain-specific agents for each scenario if DomainSwarmGenerator is available."""
        if _HAS_DOMAIN_SWARM and DomainSwarmGenerator is not None:
            return [{"domain_agent": i} for i in range(min(len(scenarios), self._max_agents))]
        return [{"stub_agent": i} for i in range(min(len(scenarios), self._max_agents))]

    # ------------------------------------------------------------------
    # Lazy simulator accessors
    # ------------------------------------------------------------------

    def _get_war_sim(self):
        if self._war_sim is None:
            from src.chaos.war_supply_chain import WarSupplyChainSimulator  # type: ignore
            self._war_sim = WarSupplyChainSimulator()
        return self._war_sim

    def _get_depression_sim(self):
        if self._depression_sim is None:
            from src.chaos.economic_depression import EconomicDepressionSimulator  # type: ignore
            self._depression_sim = EconomicDepressionSimulator()
        return self._depression_sim

    def _get_market_sim(self):
        if self._market_sim is None:
            from src.chaos.market_transitions import FiatCryptoTransitionSimulator  # type: ignore
            self._market_sim = FiatCryptoTransitionSimulator()
        return self._market_sim

    def _get_chaos_engine(self):
        if self._chaos_engine is None:
            from src.chaos.chaos_engine import ChaosEngine  # type: ignore
            self._chaos_engine = ChaosEngine()
        return self._chaos_engine


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _aggregate_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    gdp_values = [r.get("gdp_impact_pct", 0.0) for r in results if "gdp_impact_pct" in r]
    vol_values = [r.get("volatility_multiplier", 1.0) for r in results if "volatility_multiplier" in r]
    return {
        "total": len(results),
        "avg_gdp_impact_pct": round(sum(gdp_values) / max(1, len(gdp_values)), 3),
        "avg_volatility_multiplier": round(sum(vol_values) / max(1, len(vol_values)), 3),
        "failed": sum(1 for r in results if "error" in r),
    }
