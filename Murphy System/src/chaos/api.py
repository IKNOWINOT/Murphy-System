"""
FastAPI Router for Chaos Endpoints.

Design Label: CHAOS-API — Chaos Package HTTP Router
Owner: Platform Engineering

Provides REST endpoints for generating and running chaos scenarios,
querying the automation pilot, and fetching training data summaries.

All responses: {"success": bool, "data": ...}

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional FastAPI import
# ---------------------------------------------------------------------------
try:
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
    _HAS_FASTAPI = True
except ImportError:
    APIRouter = None  # type: ignore
    JSONResponse = None  # type: ignore
    _HAS_FASTAPI = False
    logger.warning("FastAPI not available — chaos API router will be a stub")

try:
    from pydantic import BaseModel
    _HAS_PYDANTIC = True
except ImportError:
    BaseModel = object  # type: ignore
    _HAS_PYDANTIC = False

# ---------------------------------------------------------------------------
# Request models (gracefully degrade if pydantic missing)
# ---------------------------------------------------------------------------

if _HAS_PYDANTIC:
    from pydantic import BaseModel as _Base

    class ScenarioRequest(_Base):
        scenario_type: str = "war_supply_chain"
        intensity: str = "moderate"
        affected_sectors: Optional[List[str]] = None

    class WarScenarioRequest(_Base):
        conflict_type: str = "regional_war"
        regions: List[str] = ["middle_east"]
        intensity: float = 0.5
        duration_months: int = 12

    class DepressionRequest(_Base):
        crisis_type: str = "financial_crisis_2008"
        trigger_event: Optional[str] = None
        policy_responses: Optional[List[str]] = None

    class TechDisruptionRequest(_Base):
        disruption_type: str = "general_ai"
        phase: Optional[str] = None
        year: Optional[int] = None

    class MarketTransitionRequest(_Base):
        from_system: str = "modern_fiat"
        to_system: str = "cbdc"
        trigger: Optional[str] = None
        speed: str = "gradual"

    class TimeTravelRequest(_Base):
        years_ahead: int = 10

    class SwarmBatteryRequest(_Base):
        intensity: str = "severe"

    class PilotStartRequest(_Base):
        mode: str = "shadow"
        scenarios_per_cycle: int = 10
        cycle_interval_seconds: int = 3600
        hitl_confirmed: bool = False

else:
    # Minimal stubs when pydantic is absent
    class ScenarioRequest:  # type: ignore
        scenario_type = "war_supply_chain"
        intensity = "moderate"
        affected_sectors = None

    class WarScenarioRequest:  # type: ignore
        conflict_type = "regional_war"
        regions = ["middle_east"]
        intensity = 0.5
        duration_months = 12

    class DepressionRequest:  # type: ignore
        crisis_type = "financial_crisis_2008"
        trigger_event = None
        policy_responses = None

    class TechDisruptionRequest:  # type: ignore
        disruption_type = "general_ai"
        phase = None
        year = None

    class MarketTransitionRequest:  # type: ignore
        from_system = "modern_fiat"
        to_system = "cbdc"
        trigger = None
        speed = "gradual"

    class TimeTravelRequest:  # type: ignore
        years_ahead = 10

    class SwarmBatteryRequest:  # type: ignore
        intensity = "severe"

    class PilotStartRequest:  # type: ignore
        mode = "shadow"
        scenarios_per_cycle = 10
        cycle_interval_seconds = 3600
        hitl_confirmed = False


# ---------------------------------------------------------------------------
# Shared state (module-level singletons, instantiated lazily)
# ---------------------------------------------------------------------------

_chaos_engine = None
_war_sim = None
_dep_sim = None
_tech_sim = None
_mkt_sim = None
_swarm_coordinator = None
_pilot = None


def _get_chaos_engine():
    global _chaos_engine
    if _chaos_engine is None:
        from src.chaos.chaos_engine import ChaosEngine
        _chaos_engine = ChaosEngine()
    return _chaos_engine


def _get_war_sim():
    global _war_sim
    if _war_sim is None:
        from src.chaos.war_supply_chain import WarSupplyChainSimulator
        _war_sim = WarSupplyChainSimulator()
    return _war_sim


def _get_dep_sim():
    global _dep_sim
    if _dep_sim is None:
        from src.chaos.economic_depression import EconomicDepressionSimulator
        _dep_sim = EconomicDepressionSimulator()
    return _dep_sim


def _get_tech_sim():
    global _tech_sim
    if _tech_sim is None:
        from src.chaos.disruptive_technology import DisruptiveTechnologySimulator
        _tech_sim = DisruptiveTechnologySimulator()
    return _tech_sim


def _get_mkt_sim():
    global _mkt_sim
    if _mkt_sim is None:
        from src.chaos.market_transitions import FiatCryptoTransitionSimulator
        _mkt_sim = FiatCryptoTransitionSimulator()
    return _mkt_sim


def _get_swarm_coordinator():
    global _swarm_coordinator
    if _swarm_coordinator is None:
        from src.chaos.swarm_chaos_coordinator import SwarmChaosCoordinator
        _swarm_coordinator = SwarmChaosCoordinator()
    return _swarm_coordinator


def _get_pilot():
    global _pilot
    if _pilot is None:
        from src.chaos.automation_pilot import AutomationPilot, PilotMode
        _pilot = AutomationPilot(mode=PilotMode.SHADOW)
    return _pilot


def _ok(data: Any) -> "JSONResponse":
    return JSONResponse({"success": True, "data": data})


def _err(msg: str, status_code: int = 500) -> "JSONResponse":
    return JSONResponse({"success": False, "data": {"error": msg}}, status_code=status_code)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_chaos_router() -> Any:
    """Return an APIRouter with all chaos endpoints, or a stub object if FastAPI is absent."""
    if not _HAS_FASTAPI:
        logger.warning("FastAPI unavailable — returning stub chaos router")
        return _StubRouter()

    router = APIRouter(prefix="/api/chaos", tags=["chaos"])

    # ------------------------------------------------------------------
    # POST /api/chaos/scenario
    # ------------------------------------------------------------------
    @router.post("/scenario")
    async def run_scenario(req: ScenarioRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.chaos_engine import ChaosScenarioType, ChaosIntensity
            engine = _get_chaos_engine()

            stype = ChaosScenarioType(req.scenario_type)
            intensity = ChaosIntensity[req.intensity.upper()]
            scenario = engine.generate_scenario(stype, intensity, req.affected_sectors)
            outcome = engine.simulate_scenario(scenario)

            return _ok({
                "scenario_id": outcome.scenario_id,
                "scenario_type": req.scenario_type,
                "gdp_impact_pct": outcome.gdp_impact_pct,
                "supply_chain_disruption_pct": outcome.supply_chain_disruption_pct,
                "market_volatility_multiplier": outcome.market_volatility_multiplier,
                "recovery_time_days": outcome.recovery_time_days,
                "affected_metrics": outcome.affected_metrics,
                "lessons_learned": outcome.lessons_learned,
            })
        except Exception as exc:
            logger.error("/scenario error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/war-scenario
    # ------------------------------------------------------------------
    @router.post("/war-scenario")
    async def war_scenario(req: WarScenarioRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.war_supply_chain import ConflictType
            sim = _get_war_sim()
            ctype = ConflictType(req.conflict_type)
            result = sim.simulate_conflict(ctype, req.regions, req.intensity, req.duration_months)
            return _ok(result)
        except Exception as exc:
            logger.error("/war-scenario error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/depression-scenario
    # ------------------------------------------------------------------
    @router.post("/depression-scenario")
    async def depression_scenario(req: DepressionRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.economic_depression import CrisisType
            sim = _get_dep_sim()
            ctype = CrisisType(req.crisis_type)
            sc = sim.simulate_crisis(ctype, req.trigger_event, req.policy_responses)
            return _ok({
                "crisis_id": sc.crisis_id,
                "crisis_type": sc.crisis_type.value,
                "trigger_event": sc.trigger_event,
                "duration_months": sc.duration_months,
                "peak_unemployment": sc.peak_unemployment,
                "gdp_contraction_pct": sc.gdp_contraction_pct,
                "affected_sectors": sc.affected_sectors,
                "policy_responses": sc.policy_responses,
            })
        except Exception as exc:
            logger.error("/depression-scenario error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/tech-disruption
    # ------------------------------------------------------------------
    @router.post("/tech-disruption")
    async def tech_disruption(req: TechDisruptionRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.disruptive_technology import DisruptionType, DisruptionPhase
            sim = _get_tech_sim()
            dtype = DisruptionType(req.disruption_type)
            phase = DisruptionPhase(req.phase) if req.phase else None
            sc = sim.simulate_disruption(dtype, phase, req.year)
            return _ok({
                "disruption_id": sc.disruption_id,
                "disruption_type": sc.disruption_type.value,
                "phase": sc.phase.value,
                "year_introduced": sc.year_introduced,
                "gdp_impact_pct": sc.gdp_impact_pct,
                "obsoleted_jobs_pct": sc.obsoleted_jobs_pct,
                "new_jobs_created_pct": sc.new_jobs_created_pct,
                "timeline_years": sc.timeline_years,
                "affected_industries": sc.affected_industries,
                "market_shifts": sc.market_shifts,
            })
        except Exception as exc:
            logger.error("/tech-disruption error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/market-transition
    # ------------------------------------------------------------------
    @router.post("/market-transition")
    async def market_transition(req: MarketTransitionRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.market_transitions import CurrencySystem
            sim = _get_mkt_sim()
            from_sys = CurrencySystem(req.from_system)
            to_sys = CurrencySystem(req.to_system)
            sc = sim.simulate_transition(from_sys, to_sys, req.trigger, req.speed)
            return _ok({
                "transition_id": sc.transition_id,
                "from_system": sc.from_system.value,
                "to_system": sc.to_system.value,
                "trigger": sc.trigger,
                "duration_years": sc.duration_years,
                "volatility_multiplier": sc.volatility_multiplier,
                "adoption_rate_curve": sc.adoption_rate_curve,
                "winners": sc.winners,
                "losers": sc.losers,
                "regulatory_response": sc.regulatory_response,
            })
        except Exception as exc:
            logger.error("/market-transition error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/time-travel-economics
    # ------------------------------------------------------------------
    @router.post("/time-travel-economics")
    async def time_travel_economics(req: TimeTravelRequest):  # type: ignore[name-defined]
        try:
            sim = _get_tech_sim()
            result = sim.simulate_time_travel_economics(req.years_ahead)
            return _ok(result)
        except Exception as exc:
            logger.error("/time-travel-economics error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/swarm-battery
    # ------------------------------------------------------------------
    @router.post("/swarm-battery")
    async def swarm_battery(req: SwarmBatteryRequest):  # type: ignore[name-defined]
        try:
            coordinator = _get_swarm_coordinator()
            result = coordinator.run_full_chaos_battery(intensity=req.intensity)
            return _ok(result)
        except Exception as exc:
            logger.error("/swarm-battery error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # GET /api/chaos/pilot/status
    # ------------------------------------------------------------------
    @router.get("/pilot/status")
    async def pilot_status():
        try:
            return _ok(_get_pilot().get_status())
        except Exception as exc:
            logger.error("/pilot/status error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/pilot/start
    # ------------------------------------------------------------------
    @router.post("/pilot/start")
    async def pilot_start(req: PilotStartRequest):  # type: ignore[name-defined]
        try:
            from src.chaos.automation_pilot import AutomationPilot, PilotMode
            global _pilot
            mode = PilotMode(req.mode)
            _pilot = AutomationPilot(mode=mode, scenarios_per_cycle=req.scenarios_per_cycle,
                                     cycle_interval_seconds=req.cycle_interval_seconds)
            result = _pilot.start(hitl_required=not req.hitl_confirmed)
            return _ok(result)
        except Exception as exc:
            logger.error("/pilot/start error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # POST /api/chaos/pilot/stop
    # ------------------------------------------------------------------
    @router.post("/pilot/stop")
    async def pilot_stop():
        try:
            return _ok(_get_pilot().stop())
        except Exception as exc:
            logger.error("/pilot/stop error: %s", exc)
            return _err(str(exc))

    # ------------------------------------------------------------------
    # GET /api/chaos/training-data
    # ------------------------------------------------------------------
    @router.get("/training-data")
    async def training_data_summary():
        try:
            engine = _get_chaos_engine()
            examples = engine.get_training_data()
            pilot_stats = _get_pilot().get_stats()
            return _ok({
                "engine_examples": len(examples),
                "pilot_stats": pilot_stats,
                "sample": examples[:3] if examples else [],
            })
        except Exception as exc:
            logger.error("/training-data error: %s", exc)
            return _err(str(exc))

    return router


# ---------------------------------------------------------------------------
# Stub router for environments without FastAPI
# ---------------------------------------------------------------------------

class _StubRouter:
    """No-op router returned when FastAPI is not installed."""

    def get(self, *a, **kw):
        def _dec(fn):
            return fn
        return _dec

    def post(self, *a, **kw):
        def _dec(fn):
            return fn
        return _dec

    def include_router(self, *a, **kw):
        pass
