# `src/runtime` — Murphy System Runtime

The core FastAPI application, system startup coordinator, and living document system.
This package is the entry point for the Murphy System server.

## Public API

```python
from runtime import MurphySystem, LivingDocument, create_app, main
```

## Starting the Server

```bash
# Development
python -m src.runtime.app

# Production
uvicorn src.runtime.app:create_app --factory --host 0.0.0.0 --port 8000
```

## Key Modules

| Module | Purpose |
|--------|---------|
| `app.py` | FastAPI application factory (`create_app()`), all 557+ API routes |
| `murphy_system_core.py` | `MurphySystem` — orchestrates subsystem startup/shutdown |
| `living_document.py` | `LivingDocument` — evolving markdown document tracked over time |
| `_deps.py` | Dependency injection helpers (`.env` loading, DB, Redis, LLM) |
| `module_loader.py` | `ModuleLoader` — loads critical + optional subsystems at startup |

## Startup Sequence

```
main()
  │
  ├─ configure_logging()
  ├─ ModuleLoader.load_critical()   ← security_plane, event_backbone, governance_kernel
  ├─ ModuleLoader.load_optional()   ← 14 sub-router packages
  ├─ bootstrap_self_healing()
  ├─ bootstrap_learning_connector()
  ├─ create_app()                   ← FastAPI app + all routes
  └─ uvicorn.serve()
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_API_KEY` | — | API key for `X-API-Key` auth |
| `DATABASE_URL` | — | PostgreSQL URL (SQLite fallback) |
| `REDIS_URL` | — | Redis URL for rate limiting / cache |
| `PORT` | `8000` | HTTP server port |
| `WORKERS` | `4` | Uvicorn worker count |
| `MURPHY_LOG_FORMAT` | `text` | `text` or `json` |
| `MFM_ENABLED` | `false` | Enable Murphy Foundation Model |

## Tests

`tests/test_app*.py`, `tests/test_module_loader.py` (30 tests), `tests/commissioning/`.
