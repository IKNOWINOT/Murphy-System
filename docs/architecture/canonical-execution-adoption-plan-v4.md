# Canonical Execution Adoption Plan v4

## Purpose

This document updates the preferred production target after canonical execution v5 became the strongest bootable default stack.

## Preferred default production target

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface_v5.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v5.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface_v5.py`

## Why this is now the preferred path

This path is the current strongest default production target because it combines:

- canonical execution identity for users and automations
- bootable default app/bridge/startup path
- capability-aware live execution
- subsystem-family selection that influences execution
- machine-readable runtime lineage and deployment truth aligned to v5
- founder/admin visibility as an additive overlay
- UI dashboard payloads
- operations status and runbook payloads
- smoke-tested boot path and runtime-truth alignment

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
python -m src.runtime.main_core_v3_canonical_execution_surface_v5
```

### Direct app factory
```bash
uvicorn src.murphy_core.app_v3_canonical_execution_surface_v5:create_app --factory
```

## Remaining non-default paths

### Canonical execution v1/v2/v3/v4
Useful correction and rollback steps, but superseded by the current v5 default stack.

### Founder-labeled runtime path
Useful historical cutover step, but no longer the default runtime identity.

### Legacy compatibility shell
Retained for incremental migration and legacy UI/API coverage.

### Runtime-correct fallback core
Retained as rollback-oriented fallback path.
