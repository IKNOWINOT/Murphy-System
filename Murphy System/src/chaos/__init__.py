"""
src/chaos — Murphy System Chaos Simulation Package.

Design Label: CHAOS-PKG — Chaos Package Public API
Owner: Platform Engineering

Public API surface (all imports wrapped in try/except for graceful degradation):

    from src.chaos import (
        # chaos_engine
        ChaosScenarioType, ChaosIntensity, ChaosScenario, ChaosOutcome, ChaosEngine,

        # war_supply_chain
        ConflictType, SupplyChainNode, ConflictScenario, WarSupplyChainSimulator,

        # economic_depression
        CrisisType, EconomicIndicator, DepressionScenario, EconomicDepressionSimulator,

        # disruptive_technology
        DisruptionType, DisruptionPhase, TechDisruptionScenario,
        TimeTravelEconomics, DisruptiveTechnologySimulator,

        # market_transitions
        CurrencySystem, MarketStructure, TransitionScenario, FiatCryptoTransitionSimulator,

        # swarm_chaos_coordinator
        SwarmChaosTask, SwarmChaosCoordinator,

        # automation_pilot
        PilotMode, PilotJob, AutomationPilot,

        # api
        create_chaos_router,
    )

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# chaos_engine
# ---------------------------------------------------------------------------
try:
    from .chaos_engine import (  # noqa: F401
        ChaosEngine,
        ChaosIntensity,
        ChaosOutcome,
        ChaosScenario,
        ChaosScenarioType,
    )
except Exception as _e:
    logger.warning("src.chaos.chaos_engine import failed: %s", _e)

# ---------------------------------------------------------------------------
# war_supply_chain
# ---------------------------------------------------------------------------
try:
    from .war_supply_chain import (  # noqa: F401
        ConflictScenario,
        ConflictType,
        SupplyChainNode,
        WarSupplyChainSimulator,
    )
except Exception as _e:
    logger.warning("src.chaos.war_supply_chain import failed: %s", _e)

# ---------------------------------------------------------------------------
# economic_depression
# ---------------------------------------------------------------------------
try:
    from .economic_depression import (  # noqa: F401
        CrisisType,
        DepressionScenario,
        EconomicDepressionSimulator,
        EconomicIndicator,
    )
except Exception as _e:
    logger.warning("src.chaos.economic_depression import failed: %s", _e)

# ---------------------------------------------------------------------------
# disruptive_technology
# ---------------------------------------------------------------------------
try:
    from .disruptive_technology import (  # noqa: F401
        DisruptionPhase,
        DisruptionType,
        DisruptiveTechnologySimulator,
        TechDisruptionScenario,
        TimeTravelEconomics,
    )
except Exception as _e:
    logger.warning("src.chaos.disruptive_technology import failed: %s", _e)

# ---------------------------------------------------------------------------
# market_transitions
# ---------------------------------------------------------------------------
try:
    from .market_transitions import (  # noqa: F401
        CurrencySystem,
        FiatCryptoTransitionSimulator,
        MarketStructure,
        TransitionScenario,
    )
except Exception as _e:
    logger.warning("src.chaos.market_transitions import failed: %s", _e)

# ---------------------------------------------------------------------------
# swarm_chaos_coordinator
# ---------------------------------------------------------------------------
try:
    from .swarm_chaos_coordinator import (  # noqa: F401
        SwarmChaosCoordinator,
        SwarmChaosTask,
    )
except Exception as _e:
    logger.warning("src.chaos.swarm_chaos_coordinator import failed: %s", _e)

# ---------------------------------------------------------------------------
# automation_pilot
# ---------------------------------------------------------------------------
try:
    from .automation_pilot import (  # noqa: F401
        AutomationPilot,
        PilotJob,
        PilotMode,
    )
except Exception as _e:
    logger.warning("src.chaos.automation_pilot import failed: %s", _e)

# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
try:
    from .api import create_chaos_router  # noqa: F401
except Exception as _e:
    logger.warning("src.chaos.api import failed: %s", _e)
