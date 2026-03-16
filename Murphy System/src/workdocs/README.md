# Workdocs

The `workdocs` package provides collaborative document management within
Murphy workspaces: creation, versioning, and team sharing.

## Key Modules

| Module | Purpose |
|--------|---------|
| `doc_manager.py` | `WorkdocManager` — CRUD and versioning for work documents |
| `models.py` | `Workdoc`, `DocVersion`, `DocShare` Pydantic models |
| `api.py` | FastAPI router for workdoc operations |
