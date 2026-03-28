# AionMind

The `aionmind` package provides a multi-modal reasoning bridge that connects
Murphy's capability registry to external AI backends via a directed acyclic
graph (DAG) execution model.

## Key Modules

| Module | Purpose |
|--------|---------|
| `capability_registry.py` | Registry of all AionMind-compatible capabilities |
| `context_engine.py` | Builds enriched context objects for each inference call |
| `dag_bridge.py` | Executes capability DAGs with parallelism and dependency ordering |
| `bot_capability_bridge.py` | Maps bot commands to AionMind capability invocations |
| `api.py` | Internal API for triggering AionMind reasoning flows |

## Usage

```python
from aionmind.dag_bridge import DAGBridge
bridge = DAGBridge()
result = await bridge.run(dag_spec={...}, context={...})
```
