# Execution Engine

The `execution_engine` package orchestrates multi-step task workflows,
manages execution context, dispatches sub-tasks to workers, and collects
results into structured outcomes.

## Key Modules

| Module | Purpose |
|--------|---------|
| `execution_orchestrator.py` | Top-level orchestrator; drives the full plan-execute-evaluate loop |
| `task_executor.py` | Executes individual tasks with retry, timeout, and circuit-breaker |
| `workflow_orchestrator.py` | Manages sequential and parallel workflow graphs |
| `decision_engine.py` | Context-aware decision branching during execution |
| `execution_context.py` | `ExecutionContext` — scoped state carrier for a single execution run |
| `state_manager.py` | Persists and restores execution state across process restarts |
| `form_executor.py` | Specialised executor for form-driven workflows |
| `form_execution_models.py` | Pydantic models for form execution payloads |
| `integrated_form_executor.py` | Combines form and free-form execution paths |

## Usage

```python
from execution_engine.execution_orchestrator import ExecutionOrchestrator
orch = ExecutionOrchestrator()
result = await orch.execute(plan={...})
```
