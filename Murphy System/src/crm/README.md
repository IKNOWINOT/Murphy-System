# CRM

The `crm` package provides customer-relationship management capabilities:
contact management, deal tracking, and interaction history.

## Key Modules

| Module | Purpose |
|--------|---------|
| `crm_manager.py` | `CRMManager` — CRUD for contacts, companies, and deals |
| `models.py` | `Contact`, `Company`, `Deal`, `Interaction` Pydantic models |
| `api.py` | FastAPI router for CRM operations |
