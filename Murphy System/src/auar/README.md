# `src/auar` — Adaptive Universal API Router

Intelligent, capability-based semantic routing layer for APIs.
Internal codename: **FAPI** (Flexible Adaptive Provider Interface).

Accepts arbitrary API requests (REST, GraphQL, or natural language),
interprets intent using hybrid LLM + deterministic approaches, maps
requests to abstract capabilities, and routes to the optimal downstream
provider with automatic schema translation.

## Public API

```python
from auar import (
    AUARConfig, AUARPipeline,
    Capability, CapabilityGraph, Provider,
    MLOptimizer, RoutingFeatures,
    SchemaTranslator,
)

pipeline = AUARPipeline(AUARConfig())
result = await pipeline.route(request)
# result.provider  → selected upstream provider
# result.response  → translated response
```

## Architecture — 7 Layers

| Layer | Module | Description |
|-------|--------|-------------|
| 1. Intent | `pipeline.py` | Parse + classify incoming request |
| 2. Capability | `capability_graph.py` | Map intent to abstract capabilities |
| 3. Provider | `provider_adapter.py` | Enumerate candidate providers |
| 4. ML Routing | `ml_optimization.py` | UCB1-based provider selection |
| 5. Schema | `schema_translation.py` | Translate request/response schemas |
| 6. Signal | `signal_interpretation.py` | Parse provider response signals |
| 7. Observability | `observability.py` + `persistence.py` | Metrics, logging, state persistence |

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUAR_ML_ENABLED` | `true` | Enable UCB1 ML routing optimization |
| `AUAR_CACHE_TTL` | `300` | Capability cache TTL (seconds) |

## Tests

`tests/test_auar*.py` — routing, capability graph, schema translation.
