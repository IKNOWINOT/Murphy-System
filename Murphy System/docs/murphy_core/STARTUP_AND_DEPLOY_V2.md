# Murphy Core v2 Startup and Deploy

This document defines the preferred startup path for Murphy Core v2.

## Preferred startup entrypoint

Use:
- `src/runtime/main_core_v2.py`

This entrypoint uses:
- `src/runtime/murphy_core_bridge_v2.py`

## Bridge behavior

The v2 bridge chooses between Murphy Core v2 and the earlier bridge path using:
- `MURPHY_PREFER_CORE_V2=true|false`

### Default
Default is:
- `true`

That means startup prefers Murphy Core v2 unless explicitly told otherwise.

## Recommended development command

```bash
python -m src.runtime.main_core_v2
```

## Recommended production command

```bash
python -m src.runtime.main_core_v2
```

For direct app-factory startup, use:

```bash
uvicorn src.murphy_core.app_v2:create_app --factory
```

## Migration recommendation

For new deployments and verification, prefer v2.
Use older core bridge/startup files only as compatibility fallback during migration.

## Environment variables

### `MURPHY_PREFER_CORE_V2`
- `true`: start Murphy Core v2 through bridge
- `false`: fall back to earlier bridge path

### `MURPHY_PORT` or `PORT`
Used to choose port.

## Operational target

Final target is:
- Murphy Core v2 direct startup
- legacy runtime and older core bridge only as compatibility surfaces or retired paths
