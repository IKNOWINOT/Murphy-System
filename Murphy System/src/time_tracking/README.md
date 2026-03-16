# Time Tracking

The `time_tracking` package provides time-entry management, approval
workflows, and billing integration for tracked work within the Murphy System.

## Key Modules

| Module | Purpose |
|--------|---------|
| `approval_service.py` | Routes time entries through manager approval workflows |
| `billing_integration.py` | Syncs approved time entries to the billing subsystem |
| `dashboard_api.py` | FastAPI router for time-tracking dashboards |
| `config.py` | Configuration for approval thresholds and billing rates |
| `api.py` | Main FastAPI router for time entry CRUD |
