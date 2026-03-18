# Murphy Core v3 Runtime-Correct Adoption Plan

This document records the runtime-correct follow-up to Murphy Core v3.

## New file

- `src/murphy_core/app_v3_runtime.py`

## Why this exists

The earlier v3 app factory exposed operator status endpoints, but the operator truth layer was still tied to an older hardcoded preferred-factory label.

The runtime-correct v3 app fixes that by using the configurable operator runtime-truth service and setting:
- `preferred_factory = murphy_core_v3`

## What this improves

- `/api/operator/status` now has a truthful runtime label
- `/api/operator/summary` now has a truthful runtime label
- readiness operator summary now aligns with the actual preferred backend path

## Recommended role

Treat `src/murphy_core/app_v3_runtime.py` as the preferred v3 app factory while migration is still using additive files.

## Next intended adoption

1. create or update bridge/startup surfaces to prefer the runtime-correct v3 app
2. phase out older v3 app usage
3. keep older app/bridge/startup layers as rollback only until stable

## Truth rule

Do not reintroduce hardcoded preferred-factory labels in new app layers.
Use the configurable runtime-truth service whenever runtime identity must be reported.
