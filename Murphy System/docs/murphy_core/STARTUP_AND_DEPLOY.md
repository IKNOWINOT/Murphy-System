# Murphy Core Startup and Deploy

This document defines the preferred startup path for Murphy Core during migration.

## Preferred startup entrypoint

Use:
- `src/runtime/main_core.py`

This entrypoint uses:
- `src/runtime/murphy_core_bridge.py`

## Bridge behavior

The bridge chooses between Murphy Core and legacy runtime using:
- `MURPHY_PREFER_CORE=true|false`

### Default
Default is:
- `true`

That means the startup path prefers Murphy Core unless explicitly told otherwise.

## Recommended development command

```bash
python -m src.runtime.main_core
```

## Recommended production command

```bash
uvicorn src.runtime.main_core:main
```

If process managers require an app factory, use the bridge or the core app directly instead.

## Direct app options

Direct Murphy Core app:

```bash
uvicorn src.murphy_core.app:create_app --factory
```

Bridge app:

```bash
python -c "from src.runtime.murphy_core_bridge import create_bridge_app; import uvicorn; uvicorn.run(create_bridge_app(prefer_core=True), host='0.0.0.0', port=8000)"
```

## Migration recommendation

During migration:
- use `main_core.py` for new deployments
- keep the legacy runtime available for compatibility fallback
- move operator docs and deploy configs toward Murphy Core

## Environment variables

### `MURPHY_PREFER_CORE`
- `true`: start Murphy Core through bridge
- `false`: fall back to legacy runtime through bridge

### `MURPHY_PORT` or `PORT`
Used to choose port.

## Operational target

Final target is:
- Murphy Core direct startup
- legacy runtime only as compatibility adapter or retired surface
