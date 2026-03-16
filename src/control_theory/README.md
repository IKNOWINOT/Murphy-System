# `src/control_theory` — Control Theory Layer

Formal control-theory models providing Bayesian confidence, Lyapunov stability, jurisdiction tracking, and actor authority management.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The control theory package encodes the mathematical framework that governs Murphy's decision-making integrity. A `BayesianConfidenceEngine` maintains belief states over system claims and updates them from typed `Observation` events. Canonical state vectors are tracked across named dimensions through `CanonicalStateVector` and validated by a PI `ControlLaw`. The `LyapunovMonitor` verifies that the system remains within a stable attractor, and `DriftDetector` raises alerts when state trajectories deviate from expected bounds. Actor authority is managed by `ActorRegistry` with a formal `AuthorityMatrix` preventing privilege escalation.

## Key Components

| Module | Purpose |
|--------|---------|
| `bayesian_engine.py` | `BayesianConfidenceEngine`, `BeliefState`, `LikelihoodModel`, `UpdateResult` |
| `canonical_state.py` | `CanonicalStateVector`, `DimensionRegistry` — single source of truth for system state |
| `control_structure.py` | `AuthorityGate`, `ControlDimension`, `StabilityMonitor`, PI `ControlLaw` |
| `control_vector.py` | `ControlVector`, `ControlAction`, `ControlLaw` — actuation signal composition |
| `actor_registry.py` | `ActorRegistry`, `Actor`, `ActorKind`, `AuthorityMatrix` |
| `drift_detector.py` | State trajectory monitoring and anomaly flagging |
| `entropy.py` | System entropy calculation for stability scoring |
| `lyapunov_monitor.py` | Lyapunov function evaluation ensuring stability convergence |
| `state_model.py` | State model definitions and transition rules |
| `state_transition.py` | Valid state transition graph with guard conditions |
| `llm_synthesis_validator.py` | Validates LLM-synthesised control proposals against formal constraints |
| `observation_model.py` | Typed observation schema for Bayesian updates |
| `scaling_mechanism.py` | Adaptive scaling for control parameters under load |
| `jurisdiction.py` | Jurisdiction tracking for distributed control decisions |
| `stability.py` | Composite stability score aggregation |
| `state_adapter.py` | Adapts external state representations to canonical form |
| `infinity_metric.py` | ∞-norm metric for worst-case stability analysis |

## Usage

```python
from control_theory import BayesianConfidenceEngine, BeliefState, Observation

engine = BayesianConfidenceEngine()
belief = engine.initialise(claim="deployment_safe", prior=0.7)
updated = engine.update(belief, Observation(source="test_suite", passed=True, weight=0.9))
print(updated.posterior)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
