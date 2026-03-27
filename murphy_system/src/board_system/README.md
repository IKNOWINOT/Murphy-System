# Board System

The `board_system` package provides Kanban-style project boards for tracking
tasks and workflows within the Murphy System.

## Key Modules

| Module | Purpose |
|--------|---------|
| `board_manager.py` | CRUD for boards and columns |
| `column_types.py` | Built-in column types: `BACKLOG`, `IN_PROGRESS`, `DONE`, `BLOCKED` |
| `models.py` | `Board`, `Column`, `Card` Pydantic models |
| `permissions.py` | Per-board permission model |
| `api.py` | FastAPI router for board operations |
