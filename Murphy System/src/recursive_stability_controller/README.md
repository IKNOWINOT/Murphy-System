# `src/recursive_stability_controller` — Recursive Stability Controller

Formally stable feedback control over recursion, agent spawning, gate synthesis, and hallucination attractors using Lyapunov methods.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The recursive stability controller (RSC) prevents Murphy from entering self-amplifying feedback loops. A `LyapunovMonitor` continuously evaluates the system's energy function and raises a stability alert if it detects a non-converging trajectory. The `RecursionEnergyEstimator` quantifies how much recursive generation energy is in flight, and `SpawnRateController` throttles agent spawning to keep this energy below the configured threshold. `GateDampingController` reduces gate synthesis rate under high-energy conditions, and `FeedbackIsolationRouter` breaks circular dependencies before they stabilise. All state is exposed as `StabilityTelemetry` for observability.

## Key Components

| Module | Purpose |
|--------|---------|
| `rsc_service.py` | `RecursiveStabilityController` — top-level service coordinating all controllers |
| `lyapunov_monitor.py` | `LyapunovMonitor` — Lyapunov function evaluation and stability checks |
| `recursion_energy.py` | `RecursionEnergyEstimator` — measures total in-flight recursive generation energy |
| `spawn_controller.py` | `SpawnRateController` — throttles agent spawn rate |
| `gate_damping.py` | `GateDampingController` — reduces gate synthesis under high energy |
| `feedback_isolation.py` | `FeedbackIsolationRouter` — breaks circular feedback dependencies |
| `control_signals.py` | `ControlSignalGenerator` — produces throttle and damping signals |
| `stability_score.py` | `StabilityScoreCalculator` — composite stability metric |
| `state_variables.py` | `StateVariables`, `NormalizedState` — normalised system state representation |
| `telemetry.py` | `StabilityTelemetry` — structured stability telemetry emission |

## Usage

```python
from recursive_stability_controller import RecursiveStabilityController, StateVariables

rsc = RecursiveStabilityController()
state = StateVariables(recursion_depth=3, active_agents=12, gate_synthesis_rate=0.4)
signal = rsc.evaluate(state)
if signal.throttle:
    print("Throttling — stability score:", signal.score)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
