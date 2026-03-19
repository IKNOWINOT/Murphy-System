# Founder Execution Surface v2 Adoption Plan

## Purpose

This document defines the current preferred production target for Murphy Core after the founder/admin visibility, capability-aware execution, and corrected runtime truth layers were aligned.

## Preferred production target

### App
- `Murphy System/src/murphy_core/app_v3_founder_execution_surface_v2.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_founder_execution_surface_v2.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_founder_execution_surface_v2.py`

## Why this is now the preferred path

This path is the first bootable target in the branch that combines:

- capability-aware live execution
- unified founder/admin visibility
- runtime truth aligned to the actual preferred path
- machine-readable production inventory
- UI dashboard payloads
- operations status and runbook payloads
- preserved subsystem-family visibility

## Why older preferred paths were superseded

### `app_v3_runtime.py`
Useful runtime-correct step, but it predates the founder/admin visibility and inventory surfaces.

### `app_v3_runtime_surface.py`
Useful runtime/operator surface step, but it predates the corrected preferred-path truth and deeper founder/admin visibility.

### `app_v3_inventory_surface.py`
Useful inventory surface step, but it did not yet put capability-aware gating into the live execution path.

### `app_v3_founder_execution_surface.py`
Useful founder execution step, but it still pointed at older runtime truth layers before the v2 lineage/deployment/runtime-surface correction.

## Current recommended boot commands

### Preferred startup
```bash
python -m src.runtime.main_core_v3_founder_execution_surface_v2
```

### Direct app factory
```bash
uvicorn src.murphy_core.app_v3_founder_execution_surface_v2:create_app --factory
```

## Operational recommendation

Use the founder execution surface v2 for:

- production deployments
- founder/admin control access
- runtime and subsystem visibility
- migration oversight
- operator UI integration

Retain the legacy compatibility shell and runtime-correct path as rollback or transitional options only.
