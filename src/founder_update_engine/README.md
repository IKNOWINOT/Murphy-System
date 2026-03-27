# `src/founder_update_engine` — Founder Update Engine

Design Label: **ARCH-007** — Central system that monitors, recommends, and coordinates how Murphy updates and maintains itself.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `founder_update_engine` package provides the self-improvement recommendation core for Murphy System. It scans subsystems for maintenance needs, detects SDK updates, applies auto-patches, handles bug responses, and produces operational dashboards — all coordinated by `UpdateCoordinator` and surfaced to the founder via the `RecommendationEngine`.

## Key Components

| Module | Purpose |
|--------|---------|
| `recommendation_engine.py` | `RecommendationEngine` — generates typed `Recommendation` objects |
| `subsystem_registry.py` | `SubsystemRegistry` — catalog of all subsystems + health metadata |
| `update_coordinator.py` | `UpdateCoordinator` — schedules and tracks `UpdateRecord` lifecycles |
| `sdk_update_scanner.py` | `SdkUpdateScanner` — scans `requirements.txt` for outdated packages |
| `auto_update_applicator.py` | `AutoUpdateApplicator` — applies low-risk updates automatically |
| `bug_response_handler.py` | `BugResponseHandler` — triages and responds to bug reports |
| `operating_analysis_dashboard.py` | `OperatingAnalysisDashboard` — real-time health dashboard |

## Public API

```python
from src.founder_update_engine import (
    RecommendationEngine, RecommendationType, RecommendationPriority, Recommendation,
    SubsystemRegistry, SubsystemInfo,
    UpdateCoordinator, MaintenanceWindow, UpdateRecord,
    SdkUpdateScanner, SdkScanReport, PackageScanRecord,
    AutoUpdateApplicator, ApplicationCycle, ApplicationRecord, ApplicationOutcome,
    BugResponseHandler, BugReport, BugResponse, BugSeverity, BugCategory,
    OperatingAnalysisDashboard, DashboardSnapshot, SubsystemHealthSummary,
)
```

## Related

- `src/founder_update_orchestrator.py` (ARCH-007) — aggregates recommendations
- `docs/FOUNDER_UPDATE_ENGINE.md` — full specification
