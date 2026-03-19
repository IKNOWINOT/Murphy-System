# Canonical Execution Adoption Plan v2

## Purpose

This document updates the preferred production target after the canonical execution app was aligned to runtime truth v4 and promoted to a bootable v2 default path.

## Preferred default production target

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface_v2.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v2.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface_v2.py`

## Why this is now the preferred path

This path is the current strongest default production target because it combines:

- canonical execution identity for users and automations
- runtime truth aligned to canonical execution defaults and founder overlay semantics
- capability-aware live execution
- subsystem-family selection that influences execution
- machine-readable production inventory
- founder/admin visibility as an additive overlay
- UI dashboard payloads
- operations status and runbook payloads

## Founder visibility model

Founder/admin visibility remains available through:

- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`
- `GET /api/founder/layer-index`

These are privileged overlay surfaces on the same canonical runtime.
They do not redefine the default runtime audience.

## Recommended commands

### Preferred startup
```bash
python -m src.runtime.main_core_v3_canonical_execution_surface_v2
```

### Direct app factory
```bash
uvicorn src.murphy_core.app_v3_canonical_execution_surface_v2:create_app --factory
```

## Remaining non-default paths

### Canonical execution v1
Useful correction step, but superseded by v2 alignment to runtime truth v4.

### Founder-labeled runtime path
Useful historical cutover step, but no longer the default runtime identity.

### Legacy compatibility shell
Retained for incremental migration and legacy UI/API coverage.

### Runtime-correct fallback core
Retained as rollback-oriented fallback path.
