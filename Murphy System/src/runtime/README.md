# Runtime

The `runtime` package is the core application bootstrap for the Murphy System.
It wires together all subsystems, exposes the FastAPI application, and manages
the full lifecycle of a running Murphy node.

## Key Modules

| Module | Purpose |
|--------|---------|
| `murphy_system_core.py` | `MurphySystemCore` — top-level orchestrator, calls `startup()` / `shutdown()` |
| `app.py` | FastAPI application factory; registers all API routers |
| `_deps.py` | Dependency injection helpers and `.env` loading |
| `living_document.py` | Self-updating documentation that mirrors current module state |
| `module_loader.py` | Dynamic module discovery and lazy import utilities |

## Quick Start

```python
from runtime.murphy_system_core import MurphySystemCore
core = MurphySystemCore()
await core.startup()
```

The HTTP server is exposed via `runtime.app:app` (a `FastAPI` instance) and
listens on port **8000** by default (configurable with `MURPHY_PORT`).
