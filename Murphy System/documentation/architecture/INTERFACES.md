# Interfaces

Public interfaces exposed by the Murphy System for integration and extension.

---

## REST API Interface

The primary integration surface is the FastAPI-based REST API created by
`create_app()` in `src/runtime/app.py`. It exposes:

- **Core endpoints** — `/api/forms/*`, `/api/hitl/*`, `/api/corrections/*`, `/api/system/info`
- **AionMind cognitive pipeline** — `/api/aionmind/*` (execute, orchestrate, context, memory)
- **Module routers** — `/api/boards`, `/api/crm`, `/api/dashboards`, etc. (12 module groups)

All endpoints accept and return JSON. Authentication is handled by
`src/fastapi_security.py` (API key + RBAC).

---

## Plugin Extension SDK

`src/plugin_extension_sdk.py` provides a full lifecycle for third-party plugins.

### Plugin States

`REGISTERED` → `VALIDATED` → `INSTALLED` → `ACTIVE` → `SUSPENDED` / `UNINSTALLED` / `FAILED`

### Plugin Capabilities

Capabilities are declared in the plugin manifest and enforced by the sandbox:

| Capability | Description |
|------------|-------------|
| `READ_DATA` | Read system data |
| `WRITE_DATA` | Write/modify data |
| `EXECUTE_TASKS` | Submit tasks for execution |
| `MANAGE_WORKFLOWS` | Create and modify workflows |
| `ACCESS_TELEMETRY` | Read telemetry and metrics |
| `SEND_NOTIFICATIONS` | Send alerts and notifications |
| `MODIFY_CONFIG` | Change system configuration |
| `ADMIN` | Full administrative access |

### Manifest Schema

Every plugin must provide a JSON manifest with these required fields:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "author": "Developer Name",
  "description": "What this plugin does",
  "entry_point": "my_plugin.main",
  "capabilities": ["READ_DATA", "EXECUTE_TASKS"]
}
```

Optional fields: `dependencies`, `min_murphy_version`, `max_murphy_version`,
`config_schema`, `hooks`, `tags`, `license`, `homepage`.

### Sandboxed Execution

Plugins run inside `PluginSandbox`, which restricts access to only the declared
capabilities. Call counts and error counts are tracked per plugin.

```python
from plugin_extension_sdk import PluginManifest, PluginSandbox

manifest = PluginManifest(manifest_data)
sandbox = PluginSandbox(manifest, allowed_capabilities=["READ_DATA"])
```

---

## Module Router Interface

Modules register FastAPI routers via `app.include_router()`. Each module follows
the pattern:

```python
# In your_module/api.py
from fastapi import APIRouter

def create_your_router() -> APIRouter:
    router = APIRouter(prefix="/api/your-module", tags=["your-module"])
    # Define endpoints...
    return router
```

The main app discovers and mounts routers at startup with graceful fallback
if a module is not installed.

---

## Multi-Tenant API (FastAPI Router)

`create_multi_tenant_api(manager)` in `src/multi_tenant_workspace.py` returns a
FastAPI `APIRouter` with REST endpoints for tenant management. All endpoints enforce
tenant-boundary permission checks and return errors in the standard envelope:

```json
{"success": false, "error": {"code": "ERROR_CODE", "message": "message"}}
```

> **Upgrade note (2026-03):** This module previously exposed a Flask `Blueprint`.
> It now ships as a FastAPI `APIRouter` mounted directly by `create_app()` in
> `src/runtime/app.py`. The REST API surface is unchanged.

---

## RBAC Governance Interface

`src/rbac_governance.py` exposes:

- `GovernanceManager.check_permission(user_id, tenant_id, permission)` — returns bool.
- `GovernanceManager.assign_role(user_id, tenant_id, role)` — assigns a role.
- `GovernanceManager.get_audit_log(tenant_id)` — returns bounded audit entries.

Integrate with the FastAPI security layer via `register_rbac_governance(rbac)`.

---

## See Also

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [API Overview](../api/API_OVERVIEW.md)
- [API Reference](../user_guides/API_REFERENCE.md)
