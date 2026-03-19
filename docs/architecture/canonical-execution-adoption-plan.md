# Canonical Execution Adoption Plan

## Purpose

This document updates the preferred production target after the runtime identity was corrected so that:

- canonical execution is the default runtime for users and automations
- founder visibility is a privileged overlay on that runtime
- legacy compatibility remains transitional only

## Preferred default production target

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface.py`

## Why this is now the preferred path

This path is the current strongest production default because it combines:

- capability-aware live execution
- subsystem-family selection that influences execution
- machine-readable production inventory
- runtime truth aligned to canonical execution defaults
- founder/admin visibility as an additive overlay
- UI dashboard payloads
- operations status and runbook payloads

## Founder visibility model

Founder/admin visibility remains available through:

- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`
- `GET /api/founder/layer-index`

These are privileged overlay surfaces on the same canonical runtime.
They do **not** redefine the runtime as founder-only for all users.

## Recommended commands

### Preferred startup
```bash
python -m src.runtime.main_core_v3_canonical_execution_surface
```

### Direct app factory
```bash
uvicorn src.murphy_core.app_v3_canonical_execution_surface:create_app --factory
```

## Remaining non-default paths

### Founder-labeled runtime path
Useful historical/cutover step, but no longer the default runtime identity.

### Legacy compatibility shell
Retained for incremental migration and legacy UI/API coverage.

### Runtime-correct fallback core
Retained as rollback-oriented fallback path.
