# Adapter Framework

The `adapter_framework` package defines the contract that all Murphy adapters
must implement and provides the runtime that discovers, loads, and executes them.

## Key Modules

| Module | Purpose |
|--------|---------|
| `adapter_contract.py` | `AdapterContract` abstract base with typed `execute()` signature |
| `adapter_runtime.py` | Discovers adapters, validates contracts, and dispatches calls |
| `execution_packet_extension.py` | Extends `ExecutionPacket` with adapter-specific metadata |
| `safety_hooks.py` | Pre/post execution guards (rate-limit, sandboxing, rollback) |
| `adapters/` | Built-in adapter implementations |

## Writing an Adapter

```python
from adapter_framework.adapter_contract import AdapterContract, ExecutionResult
class MyAdapter(AdapterContract):
    capability = "my_capability"
    async def execute(self, payload: dict) -> ExecutionResult:
        ...
```
