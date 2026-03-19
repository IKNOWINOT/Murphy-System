# Boot Path Decision v2

## Purpose

This document updates the boot-path decision for the branch after the founder execution surface v2 became the canonical production target.

## Canonical production path

Use this path when you want the strongest current Murphy backend surface.

### App
- `Murphy System/src/murphy_core/app_v3_founder_execution_surface_v2.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_founder_execution_surface_v2.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_founder_execution_surface_v2.py`

### Choose this path when
- you want founder/admin visibility
- you want capability-aware live execution
- you want runtime truth aligned to the preferred path
- you want production inventory, UI dashboard, and ops payloads available from the same backend surface

## Transitional compatibility path

Use this path when you still need broad legacy UI/API coverage.

### App
- `Murphy System/src/runtime/legacy_runtime_compat_shell.py`

### Startup
- `Murphy System/src/runtime/main_legacy_compat_shell.py`

### Choose this path when
- legacy route coverage is still required
- `/api/chat` and `/api/execute` should already be core-owned
- migration is incremental rather than full cutover

## Rollback core path

Keep this as a lower-visibility fallback core path.

### App
- `Murphy System/src/murphy_core/app_v3_runtime.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_runtime_correct.py`

### Choose this path when
- you need a simpler fallback runtime-correct core path
- founder/admin visibility surfaces are not required for the rollback scenario

## Recommended commands

### Canonical production startup
```bash
python -m src.runtime.main_core_v3_founder_execution_surface_v2
```

### Canonical direct app factory
```bash
uvicorn src.murphy_core.app_v3_founder_execution_surface_v2:create_app --factory
```

## Decision rule

- choose founder execution surface v2 for production and operator/admin visibility
- choose legacy compat shell for incremental migration with broad legacy coverage
- choose runtime-correct core only as rollback or simplified fallback
