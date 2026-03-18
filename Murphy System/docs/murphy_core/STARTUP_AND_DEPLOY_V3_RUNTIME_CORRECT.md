# Murphy Core v3 Runtime-Correct Startup and Deploy

This document defines the preferred startup path for the runtime-correct Murphy Core v3 layer.

## Preferred startup entrypoint

Use:
- `src/runtime/main_core_v3_runtime_correct.py`

This entrypoint uses:
- `src/runtime/murphy_core_bridge_v3_runtime_correct.py`

## Preferred app target

The preferred app factory is:
- `src/murphy_core/app_v3_runtime.py`

This is the runtime-correct v3 app because it reports the truthful operator runtime identity.

## Bridge behavior

The bridge chooses between runtime-correct v3 and earlier v3 bridge path using:
- `MURPHY_PREFER_CORE_V3_RUNTIME_CORRECT=true|false`

### Default
Default is:
- `true`

## Recommended development command

```bash
python -m src.runtime.main_core_v3_runtime_correct
```

## Recommended production command

```bash
python -m src.runtime.main_core_v3_runtime_correct
```

For direct app-factory startup, use:

```bash
uvicorn src.murphy_core.app_v3_runtime:create_app --factory
```

## Migration recommendation

For new deployments, prefer the runtime-correct v3 path.
Treat older core app/bridge/startup layers as fallback or rollback paths during migration.

## Operational target

Final target is:
- `app_v3_runtime.py` as preferred app factory
- `main_core_v3_runtime_correct.py` as preferred startup entrypoint
- older bridges/startup layers reduced to compatibility or rollback only
