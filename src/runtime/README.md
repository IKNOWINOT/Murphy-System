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
| `tiered_orchestrator.py` | `TieredOrchestrator` — tiered runtime (opt-in via `MURPHY_RUNTIME_MODE=tiered`) |
| `living_document.py` | `LivingDocument` — evolving markdown document tracked over time |
| `_deps.py` | Dependency injection helpers (`.env` loading, DB, Redis, LLM) |
| `module_loader.py` | `ModuleLoader` — loads critical + optional subsystems at startup |

## Runtime Mode

Murphy System supports two startup modes controlled by `MURPHY_RUNTIME_MODE`:

### `monolith` (default)

The original behaviour — everything loads at startup.  Safe, well-tested,
and unchanged from before the tiered runtime was introduced.

```dotenv
MURPHY_RUNTIME_MODE=monolith
```

### `tiered` (opt-in)

Only loads the capability packs the team actually needs, based on their
onboarding profile.  Faster startup, lower memory, automatic unloading of
idle domain packs.  Falls back to the monolith automatically on failure.

```dotenv
MURPHY_RUNTIME_MODE=tiered
MURPHY_PACK_FALLBACK=monolith   # safest fallback option
MURPHY_PACK_IDLE_TIMEOUT=30     # unload idle domain packs after 30 min
```

See [docs/TIERED_RUNTIME.md](../../docs/TIERED_RUNTIME.md) for full details.

## Startup Sequence

### Monolith path (default)

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

### Tiered path (`MURPHY_RUNTIME_MODE=tiered`)

```
TieredOrchestrator.boot(team_profile)
  │
  ├─ 1. Load KERNEL packs  (kernel_security, kernel_events, kernel_governance, kernel_health)
  ├─ 2. Load PLATFORM packs (platform_api, platform_llm, platform_persistence, platform_confidence)
  ├─ 3. Load DOMAIN packs matching team_profile["capabilities"]
  │       (e.g. domain_crm, domain_hvac — only what was requested at onboarding)
  └─ 4. EPHEMERAL packs — never pre-loaded

  On KERNEL/PLATFORM failure → fallback_to_monolith() → full MurphySystem
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
| `MURPHY_RUNTIME_MODE` | `monolith` | `monolith` or `tiered` |
| `MURPHY_PACK_IDLE_TIMEOUT` | `30` | Minutes before idle domain packs unload (tiered mode) |
| `MURPHY_PACK_FALLBACK` | `monolith` | Fallback mode for tiered: `monolith` \| `degraded` \| `strict` |

## Tests

`tests/test_app*.py`, `tests/test_module_loader.py` (30 tests), `tests/commissioning/`,
`src/runtime/runtime_packs/tests/test_tiered_orchestrator.py` (tiered runtime tests).
