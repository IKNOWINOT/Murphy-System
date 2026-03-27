# Murphy Terminal

The `murphy_terminal` package powers the interactive command-line
interface embedded in the Murphy web UI.  It maintains a command registry
and dispatches terminal inputs to the appropriate Murphy subsystems.

## Key Module

| Module | Purpose |
|--------|---------|
| `command_registry.py` | `CommandRegistry` — maps command strings to handler functions |

## Usage

```python
from murphy_terminal.command_registry import CommandRegistry
registry = CommandRegistry()
result = await registry.dispatch("status", args=[])
```
