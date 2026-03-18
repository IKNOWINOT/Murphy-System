# Contributing to the Murphy System Runtime

Copyright © 2020 Inoni Limited Liability Company | License: BSL 1.1

This guide explains how the tiered runtime works and how to extend it safely.
For general contribution guidelines see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## How the Boot Dispatcher Works

Murphy System supports two runtime modes, selected via the `MURPHY_RUNTIME_MODE`
environment variable (default: `monolith`):

| Mode       | Description                                                 |
|------------|-------------------------------------------------------------|
| `monolith` | All modules loaded at startup — the original behaviour.     |
| `tiered`   | Only modules needed by the team profile are loaded.         |

The single entry point is **`src/runtime/boot.py`**:

```
python -m src.runtime.boot
```

Or from code:

```python
from src.runtime.boot import boot_murphy
app = await boot_murphy()          # reads MURPHY_RUNTIME_MODE automatically
app = await boot_murphy("tiered")  # force tiered
app = await boot_murphy("monolith")# force monolith
```

The boot dispatcher:
1. Reads `MURPHY_RUNTIME_MODE`.
2. In **monolith** mode — calls `src.runtime.app.create_app()` exactly as before.
3. In **tiered** mode — creates a `TieredOrchestrator`, registers all packs from
   the registry, boots with the team profile (if available), and builds a
   lightweight FastAPI app via `src.runtime.tiered_app_factory.create_tiered_app()`.
4. On **any failure in tiered mode** — automatically falls back to monolith.

---

## Switching Runtime Mode

```bash
bash scripts/switch_runtime.sh tiered
bash scripts/switch_runtime.sh monolith
```

Or set `MURPHY_RUNTIME_MODE=tiered` manually in your `.env`.

---

## How Packs Work

A **RuntimePack** (`src/runtime/tiered_orchestrator.py`) is a self-contained
bundle that represents a domain (e.g. "compliance", "hvac", "analytics").

Each pack declares:
- **`name`** — unique identifier (e.g. `"compliance"`).
- **`capabilities`** — set of string tags the pack provides (e.g. `{"gdpr", "hipaa"}`).
- **`description`** — human-readable summary.
- **`router_factory`** — optional `() -> APIRouter` callable.  Called during load
  to produce a FastAPI router that is automatically mounted.
- **`on_load`** / **`on_unload`** — optional async hooks for resource setup/teardown.

The orchestrator loads a pack only if the team profile requests at least one of
the pack's capabilities.  If no team profile is present, **all** packs are loaded.

---

## Adding a New Module / Domain Pack

### Step 1 — Implement your domain logic

Put your new module in `src/` as usual.  Keep it self-contained and avoid
top-level imports of heavyweight optional dependencies.

### Step 2 — Create a RuntimePack factory in `registry.py`

Open `src/runtime/runtime_packs/registry.py` and add:

```python
def _make_my_domain_pack() -> RuntimePack:
    return RuntimePack(
        name="my_domain",
        capabilities={"my_capability", "another_capability"},
        description="Short description of what this pack provides.",
        version="1.0.0",
        # Optional: expose API routes when loaded
        router_factory=_build_my_domain_router,
        # Optional: async setup / teardown
        on_load=_my_domain_on_load,
        on_unload=_my_domain_on_unload,
    )
```

Then add it to `_PACK_FACTORIES`:

```python
_PACK_FACTORIES = [
    ...
    _make_my_domain_pack,   # ← add here
]
```

### Step 3 — Register capabilities in `CAPABILITY_TO_PACK`

```python
CAPABILITY_TO_PACK: Dict[str, str] = {
    ...
    "my_capability":     "my_domain",   # ← add here
    "another_capability":"my_domain",
}
```

This mapping lets the boot dispatcher answer: _"which pack do I need to serve
capability X?"_.

### Step 4 — (Optional) Expose API routes

Implement a router factory that returns a FastAPI `APIRouter`:

```python
def _build_my_domain_router():
    from fastapi import APIRouter
    from src.my_domain_module import do_something   # imported lazily!
    router = APIRouter(prefix="/api/my-domain", tags=["my-domain"])

    @router.get("/status")
    async def my_domain_status():
        return {"status": "ok"}

    return router
```

> **Important**: import heavy dependencies _inside_ the factory function, not at
> module level.  This preserves the lazy-loading benefit of tiered mode.

### Step 5 — Test your pack loads correctly

```python
import asyncio
from src.runtime.tiered_orchestrator import TieredOrchestrator
from src.runtime.runtime_packs.registry import get_all_packs

async def test():
    orch = TieredOrchestrator()
    for pack in get_all_packs():
        orch.register_pack(pack)
    result = await orch.boot(team_profile={"capabilities": ["my_capability"]})
    assert "my_domain" in result.loaded_packs
    assert result.success

asyncio.run(test())
```

---

## Team Profile

The team profile (`data/team_profile.json`) tells the tiered orchestrator which
capabilities this team needs.  Example:

```json
{
  "team": "Acme Corp Engineering",
  "capabilities": [
    "auth",
    "workflows",
    "compliance",
    "analytics"
  ]
}
```

If the file is absent, **all** packs are loaded (same behaviour as monolith).

The `MURPHY_PERSISTENCE_DIR` environment variable controls where the file is
looked up (defaults to `./data`).

---

## Runtime Management API (Tiered Mode Only)

When running in tiered mode, these endpoints are available:

| Method | Path                                  | Description                         |
|--------|---------------------------------------|-------------------------------------|
| GET    | `/api/health`                         | Liveness probe                      |
| GET    | `/api/runtime/mode`                   | Current runtime mode                |
| GET    | `/api/runtime/status`                 | Full orchestrator status            |
| GET    | `/api/runtime/packs`                  | List all packs + status             |
| POST   | `/api/runtime/packs/{name}/load`      | Manually load a pack                |
| POST   | `/api/runtime/packs/{name}/unload`    | Manually unload a pack              |
| POST   | `/api/runtime/fallback`               | Trigger emergency monolith fallback |

---

## Diagnostic Scripts

```bash
# Check current mode and server health
bash scripts/runtime_status.sh

# Switch modes
bash scripts/switch_runtime.sh tiered
bash scripts/switch_runtime.sh monolith
```

---

## Critical Rules for Developers

1. **DO NOT** modify `src/runtime/murphy_system_core.py`, `src/runtime/app.py`,
   or `murphy_system_1.0_runtime.py`.  These are the protected monolith runtime
   files.
2. **DO NOT** modify `src/runtime/module_loader.py`.
3. New domain packs **must** be registered in `registry.py` — do not call
   `orchestrator.register_pack()` from scattered places in the codebase.
4. Keep pack `router_factory` functions **lazy** (defer heavy imports inside the
   function body) to preserve the startup performance benefit.
5. Always include a fallback path: if a pack fails to load, the system must
   continue (either without that pack in tiered mode, or by falling back to
   monolith).
6. All new files must carry the BSL 1.1 copyright header.
