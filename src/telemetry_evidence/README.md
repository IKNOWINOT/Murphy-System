# `src/telemetry_evidence` — Telemetry Evidence Store

Design Label: **ARCH-007** — Stores real telemetry snapshots for historical analysis, trend detection, and incident investigation.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `telemetry_evidence` package provides durable, queryable storage for telemetry snapshots captured during Murphy System operation. Snapshots are typed by `SnapshotKind` (health, API, errors, performance, etc.), timestamped, and indexed for retrieval by the `TelemetryEvidenceStore`. The store supports both in-memory (development) and file-backed (production) modes.

## Key Components

| Module | Purpose |
|--------|---------|
| `evidence_store.py` | `TelemetryEvidenceStore` — CRUD for `TelemetrySnapshot` objects |

## Public API

```python
from src.telemetry_evidence import (
    TelemetryEvidenceStore,
    TelemetrySnapshot,
    EvidenceQuery,
    SnapshotKind,
)

store = TelemetryEvidenceStore()
store.record(TelemetrySnapshot(kind=SnapshotKind.HEALTH, data={"uptime": 3600}))
results = store.query(EvidenceQuery(kind=SnapshotKind.HEALTH, limit=10))
```

## `SnapshotKind` values

| Value | Description |
|-------|-------------|
| `HEALTH` | System health check results |
| `API` | API response latency and status codes |
| `ERROR` | Exception and error events |
| `PERFORMANCE` | CPU, memory, and throughput metrics |
| `AUDIT` | Security and access audit events |

## Related

- `src/observability_counters.py` — real-time metrics counters
- `docs/UNIFIED_OBSERVABILITY_ENGINE.md` — full observability architecture
