# Boot Path Decision

This document defines which Murphy boot path to use in each deployment stage.

## Preferred direct core path

Use the direct runtime-correct core path when you want the canonical backend and do not need the legacy route surface.

### App
- `src/murphy_core/app_v3_runtime.py`

### Bridge
- `src/runtime/murphy_core_bridge_v3_runtime_correct.py`

### Startup
- `src/runtime/main_core_v3_runtime_correct.py`

## Legacy compatibility shell path

Use the legacy compatibility shell when you still need broad legacy UI/API coverage but want:
- `/api/chat`
- `/api/execute`

to be delegated into Murphy Core.

### Shell app
- `src/runtime/legacy_runtime_compat_shell.py`

### Startup
- `src/runtime/main_legacy_compat_shell.py`

## Decision rule

### Choose direct core path when
- you are validating the canonical Murphy Core backend
- your UI/admin/operator work is aligned to core endpoints
- you do not require legacy endpoint coverage

### Choose legacy compatibility shell when
- you still depend on the legacy UI or broad legacy route surface
- you want to keep legacy coverage while migrating incrementally
- you want Murphy Core to own chat/execute without rewriting the whole monolith first

## Migration target

The long-term target remains the direct runtime-correct core path.

The legacy compatibility shell is a transitional deployment surface that reduces migration risk while making Murphy Core the orchestration authority for the highest-value flows.
