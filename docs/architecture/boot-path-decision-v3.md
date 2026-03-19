# Boot Path Decision v3

## Default production path

Use the canonical execution path when you want the strongest current Murphy backend for users and automations.

### App
- `Murphy System/src/murphy_core/app_v3_canonical_execution_surface.py`

### Bridge
- `Murphy System/src/runtime/murphy_core_bridge_v3_canonical_execution_surface.py`

### Startup
- `Murphy System/src/runtime/main_core_v3_canonical_execution_surface.py`

### Choose this path when
- you want the default runtime for normal users
- you want automations to run on the strongest current execution path
- you want subsystem-family selection and capability-aware execution
- you want founder visibility available without making founder the runtime identity

## Founder visibility overlay

Founder/admin visibility is available on the same canonical runtime through:

- `/api/founder/visibility`
- `/api/founder/visibility-summary`
- `/api/founder/layer-index`

This is a privileged overlay, not a separate default audience runtime.

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
- canonical execution is temporarily not the desired boot path

## Recommended commands

### Canonical production startup
```bash
python -m src.runtime.main_core_v3_canonical_execution_surface
```

### Canonical direct app factory
```bash
uvicorn src.murphy_core.app_v3_canonical_execution_surface:create_app --factory
```
