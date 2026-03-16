# Automations

The `automations` package manages user-defined automation rules and the
engine that evaluates and executes them on a trigger basis.

## Key Modules

| Module | Purpose |
|--------|---------|
| `engine.py` | `AutomationEngine` — evaluates triggers and dispatches actions |
| `api.py` | FastAPI router: CRUD for automation rules |
| `models.py` | `Automation`, `Trigger`, `Action` Pydantic models |

## Usage

```python
from automations.engine import AutomationEngine
engine = AutomationEngine()
await engine.evaluate_event(event_type="FILE_UPLOADED", payload={...})
```
