# Schema Registry

The `schema_registry` package maintains a central registry of all JSON
schemas used across the Murphy System, enabling schema validation and
versioned schema evolution.

## Key Modules

| Module | Purpose |
|--------|---------|
| `registry.py` | `SchemaRegistry` — registers, retrieves, and validates schemas |
| `schemas.py` | Built-in core schemas for Murphy request/response types |

## Usage

```python
from schema_registry.registry import SchemaRegistry
registry = SchemaRegistry()
registry.register("TaskRequest", schema_dict)
registry.validate("TaskRequest", payload)
```
