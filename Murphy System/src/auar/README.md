# AUAR — Autonomous Universal Adapter Runtime

The `auar` package implements Murphy's self-optimising adapter-routing
engine.  It selects the best adapter for each incoming capability request
using a **UCB1 bandit algorithm** with per-capability epsilon-greedy
exploration, tracks performance in a pluggable persistence backend, and
exposes real-time observability.

## Key Modules

| Module | Purpose |
|--------|---------|
| `routing_engine.py` | UCB1 adapter selection; updates weights after every call |
| `ml_optimization.py` | Per-capability UCB1 state, exploration budget management |
| `pipeline.py` | End-to-end request pipeline: intake → route → translate → execute |
| `provider_adapter.py` | Wraps external providers with retries and timeout guards |
| `schema_translation.py` | Bidirectional schema mapping between Murphy and provider formats |
| `capability_graph.py` | Directed capability-dependency graph used by the router |
| `persistence.py` | `InMemoryPersistence` and `FilePersistence` backends |
| `observability.py` | Prometheus metrics and structured log emission |
| `config.py` | `AUARConfig` dataclass with environment-variable resolution |

## Usage

```python
from auar.pipeline import AUARPipeline
pipeline = AUARPipeline()
result = await pipeline.execute(capability="translate_document", payload={...})
```
