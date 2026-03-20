# Boot Path Decision v6

## Default production path

Use the canonical execution v5 path when you want the strongest current Murphy backend for users and automations.

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface_v5.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v5.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface_v5.py`

### Choose this path when
- you want the default runtime for normal users
- you want automations to run on the strongest current execution path
- you want subsystem-family selection and capability-aware execution
- you want founder visibility available without making founder the runtime identity
- you want machine-readable runtime truth to match the live boot path
- you want recent execution outcomes visible from operator, ops, dashboard, and founder surfaces on the same stack

## Founder visibility overlay

Founder/admin visibility is available on the same canonical runtime through:

- `/api/founder/visibility`
- `/api/founder/visibility-summary`
- `/api/founder/layer-index`

This remains a privileged overlay, not a separate default audience runtime.

## Runtime verification endpoints

After booting the canonical path, verify both topology and recent execution truth through:

- `/api/operator/runtime`
- `/api/operator/runtime-summary`
- `/api/ops/status`
- `/api/ui/runtime-dashboard`
- `/api/founder/visibility`

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
- you need a simpler runtime-correct fallback
- canonical execution v5 is temporarily not the desired boot path

## Recommended commands

### Canonical production startup
```bash
python -m src.runtime.main_core_v3_canonical_execution_surface_v5
```

### Canonical direct app factory
```bash
uvicorn src.murphy_core.app_v3_canonical_execution_surface_v5:create_app --factory
```
