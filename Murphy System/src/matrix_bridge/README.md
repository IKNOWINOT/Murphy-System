# Matrix Bridge

The `matrix_bridge` package connects the Murphy System to a Matrix homeserver.
It manages room subscriptions, routes subsystem events to the appropriate
Matrix rooms, and translates Matrix commands back into Murphy actions.

## Key Modules

| Module | Purpose |
|--------|---------|
| `room_registry.py` | `SUBSYSTEM_ROOMS` — canonical list of all Matrix room aliases |
| `module_manifest.py` | `MODULE_MANIFEST` — maps every Murphy module to its room |
| `appservice.py` | Matrix Application Service endpoint (webhook receiver) |
| `auth_bridge.py` | Matrix ↔ Murphy credential bridging |
| `bot_bridge_adapter.py` | Adapts bot events to Murphy task format |
| `_registry_data_a/b.py` | Static room-capability data (split for size limits) |
| `_registry_types.py` | Typed dataclasses for registry entries |

## Usage

```python
from matrix_bridge.room_registry import SUBSYSTEM_ROOMS
from matrix_bridge.module_manifest import MODULE_MANIFEST
# Verify all modules have registered rooms
missing = [e for e in MODULE_MANIFEST if e.room not in SUBSYSTEM_ROOMS]
assert missing == []
```
