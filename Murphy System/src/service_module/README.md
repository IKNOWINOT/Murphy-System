# Service Module

The `service_module` package provides a generic service-management API
for registering, updating, and querying Murphy micro-services.

## Key Modules

| Module | Purpose |
|--------|---------|
| `service_manager.py` | `ServiceManager` — lifecycle management for Murphy services |
| `models.py` | `Service`, `ServiceConfig`, `ServiceHealth` Pydantic models |
| `api.py` | FastAPI router for service registry operations |
