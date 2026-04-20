# `src/aionmind` — AionMind Runtime Framework

Collaborative Orchestrator-of-Orchestrators implementing six cognitive layers for the Murphy System 2.0 runtime.

## Architecture

```
Layer 1: Cognitive Input       — ContextEngine (context awareness)
Layer 2: Collaborative Reason  — ReasoningEngine (orchestrator-of-orchestrators)
Layer 3: Stability Control     — RSCClientAdapter (recursive stability)
Layer 4: Dynamic Orchestration — OrchestrationEngine (DAG execution)
Layer 5: Memory Integration    — MemoryLayer (STM / LTM)
Layer 6: Optimization          — OptimizationEngine (conservative learning)
```

**Non-negotiable constraint:** NO AUTONOMY — all high-risk/low-confidence/irreversible operations require human approval (HITL gate).

## Public API

```python
from aionmind import AionMindKernel, ContextEngine, ReasoningEngine, OptimizationEngine

kernel = AionMindKernel()
result = kernel.process(context_object)
# result.proposals → List[OptimizationProposal]  (never auto-executed)
```

## Key Classes

| Class | Module | Description |
|-------|--------|-------------|
| `AionMindKernel` | `runtime_kernel.py` | Main entry point, wires all 6 layers |
| `ContextEngine` | `context_engine.py` | Builds `ContextGraph` from inputs |
| `ReasoningEngine` | `reasoning_engine.py` | Multi-agent reasoning over context |
| `OrchestrationEngine` | `orchestration_engine.py` | DAG-based execution planning |
| `MemoryLayer` | `memory_layer.py` | Short-term + long-term memory |
| `OptimizationEngine` | `optimization_engine.py` | Proposal generation (never execution) |
| `CapabilityRegistry` | `capability_registry.py` | Registers agent capabilities |

## Tests

`tests/test_aionmind_*.py` — kernel, context engine, reasoning, DAG bridge.
