# Canonical Execution Adoption Plan v5

## Purpose

This document records the current preferred production target after the canonical execution v5 stack became not only the strongest bootable default path, but also the branch-aligned truth surface for execution outcomes and operator visibility.

## Preferred default production target

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface_v5.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v5.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface_v5.py`

## Why this is now the preferred path

This path is the strongest current default production target because it combines:

- canonical execution identity for users and automations
- founder/admin visibility as an additive privileged overlay
- bootable default app/bridge/startup path
- capability-aware live execution
- subsystem-family selection that influences execution
- machine-readable runtime lineage and deployment truth aligned to v5
- planner/executor enforcement alignment
- explicit review and HITL pauses
- controlled legacy fallback execution for hard blocking gates when policy allows
- endpoint outcome flags aligned to trace recovery state
- operator, ops, dashboard, and founder surfaces aligned to recent execution-outcome truth
- smoke-tested boot path and runtime-truth alignment across those surfaces

## Founder visibility model

Founder/admin visibility remains available through:

- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`
- `GET /api/founder/layer-index`

These remain privileged overlay surfaces on the same canonical runtime.
They do not redefine the default runtime audience.

## Operator-facing runtime truth now available

The canonical v5 path now exposes recent execution-outcome truth through:

- `GET /api/operator/runtime`
- `GET /api/operator/runtime-summary`
- `GET /api/ops/status`
- `GET /api/ui/runtime-dashboard`
- `GET /api/founder/visibility`
- `GET /api/founder/visibility-summary`

This means runtime topology and recent execution behavior are now visible through the same production-aligned stack.

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
