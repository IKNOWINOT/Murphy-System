# `src/synthetic_failure_generator` — Synthetic Failure Generator

Manufactures realistic multi-dimensional system failures safely in isolation for anti-fragile learning and gate policy training.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The synthetic failure generator creates structurally realistic disaster scenarios without touching production interfaces or emitting real execution packets. It produces `TrainingArtifact` objects across four failure dimensions — semantic, control-plane, interface, and organisational — which are consumed by confidence models and gate policy engines to improve their robustness. A `SafetyEnforcer` is active throughout every generation run, blocking any scenario that could leak outside the training plane. `TestModeExecutor` enables deterministic scenario replay for CI regression testing.

## Key Components

| Module | Purpose |
|--------|---------|
| `injection_pipeline.py` | `FailureInjectionPipeline` — orchestrates multi-dimensional failure generation |
| `semantic_failures.py` | `SemanticFailureGenerator` — hallucination, ambiguity, and context collapse |
| `control_failures.py` | `ControlPlaneFailureGenerator` — gate bypass, confidence inflation, deadlock |
| `interface_failures.py` | `InterfaceFailureGenerator` — API timeouts, auth failures, data corruption |
| `organizational_failures.py` | `OrganizationalFailureGenerator` — approval loops, role conflicts, escalation failures |
| `safety_enforcer.py` | `SafetyEnforcer` — ensures no scenario touches production |
| `training_output.py` | `TrainingOutputGenerator` — serialises artifacts for ML training pipelines |
| `test_modes.py` | `TestModeExecutor` — deterministic scenario replay |
| `models.py` | `FailureCase`, `FailureType`, `TrainingArtifact`, `SimulationResult`, `FailureManifold` |
| `api.py` | REST API for triggering and monitoring generation runs |

## Usage

```python
from synthetic_failure_generator import FailureInjectionPipeline, FailureType

pipeline = FailureInjectionPipeline()
artifacts = pipeline.generate(
    failure_types=[FailureType.SEMANTIC, FailureType.CONTROL_PLANE],
    count=100,
)
print(f"Generated {len(artifacts)} training artifacts")
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
