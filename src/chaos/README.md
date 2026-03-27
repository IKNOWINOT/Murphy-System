# `src/chaos` — Chaos Simulation Engine

Murphy System chaos simulation package — models adversarial economic and supply-chain scenarios for stress-testing automation strategies.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `chaos` package provides scenario-based simulation engines that stress-test Murphy's automation layer under extreme conditions: war-driven supply chain disruptions, economic depressions, disruptive technology waves, and fiat-to-crypto market transitions. Each engine produces typed `ChaosOutcome` records consumed by the swarm coordinator.

## Key Components

| Module | Design Label | Purpose |
|--------|-------------|---------|
| `chaos_engine.py` | CHAOS-001 | Core scenario runner — `ChaosEngine` orchestrates all simulations |
| `war_supply_chain.py` | CHAOS-002 | `WarSupplyChainSimulator` — models conflict-driven logistics disruption |
| `economic_depression.py` | CHAOS-003 | `EconomicDepressionSimulator` — models deflationary spiral cascades |
| `disruptive_technology.py` | CHAOS-004 | `DisruptiveTechnologySimulator` + `TimeTravelEconomics` |
| `market_transitions.py` | CHAOS-005 | `FiatCryptoTransitionSimulator` — models monetary system transitions |
| `swarm_chaos_coordinator.py` | CHAOS-006 | Distributes chaos tasks across the Murphy swarm |
| `automation_pilot.py` | CHAOS-007 | `AutomationPilot` — adaptive pilot modes for live chaos response |
| `api.py` | CHAOS-API | FastAPI router for chaos scenario CRUD and execution |

## Public API

```python
from src.chaos import (
    ChaosEngine, ChaosScenarioType, ChaosIntensity, ChaosScenario, ChaosOutcome,
    WarSupplyChainSimulator, EconomicDepressionSimulator,
    DisruptiveTechnologySimulator, TimeTravelEconomics,
    FiatCryptoTransitionSimulator,
    SwarmChaosCoordinator, SwarmChaosTask,
    AutomationPilot, PilotMode, PilotJob,
)
```

## Configuration

No environment variables required. Scenarios are parameterised at construction time via `ChaosScenario` dataclasses.

## Related

- `src/resilience/` — pairs with chaos output to test recovery
- `docs/CHAOS_RESILIENCE_LOOP.md` — architecture overview
