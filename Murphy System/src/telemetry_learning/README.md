# `src/telemetry_learning` — Telemetry & Learning Loops

Enterprise telemetry collection with conservative learning loops that harden gates, tune phase schedules, detect bottlenecks, and invalidate stale assumptions.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The telemetry learning package closes the feedback loop between Murphy's observed behaviour and its control parameters. `TelemetryIngester` normalises incoming events across six domains — operational, human, control, safety, and market — into `TelemetryArtifact` objects buffered on a `TelemetryBus`. Learning engines then process buffered artifacts: `GateStrengtheningEngine` tightens gates where failures cluster, `PhaseTuningEngine` adjusts automation phase schedules based on throughput data, `BottleneckDetector` surfaces throttling points, and `AssumptionInvalidator` revokes assumptions contradicted by telemetry evidence. `ShadowModeController` governs the transition from observation-only to active gate changes.

## Key Components

| Module | Purpose |
|--------|---------|
| `ingestion.py` | `TelemetryBus`, `TelemetryIngester` — normalisation and buffering |
| `learning.py` | `GateStrengtheningEngine`, `PhaseTuningEngine`, `BottleneckDetector`, `AssumptionInvalidator`, `HardeningPolicyEngine` |
| `models.py` | `TelemetryArtifact`, `TelemetryDomain`, `GateEvolutionArtifact`, `InsightArtifact` |
| `shadow_mode.py` | `ShadowModeController`, `AuthorizationInterface` — observation-only mode control |
| `schemas.py` | Serialisation schemas for telemetry wire format |
| `simple_wrapper.py` | Lightweight wrapper for packages that don't need the full learning stack |
| `api.py` | REST API for telemetry ingestion and insight queries |

## Usage

```python
from telemetry_learning import TelemetryIngester, TelemetryDomain, TelemetryArtifact

ingester = TelemetryIngester()
artifact = TelemetryArtifact(domain=TelemetryDomain.OPERATIONAL, event="gate_passed",
                             metadata={"gate_id": "g-42", "latency_ms": 120})
ingester.ingest(artifact)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
