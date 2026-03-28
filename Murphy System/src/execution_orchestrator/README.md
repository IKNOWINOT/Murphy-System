# Execution Orchestrator

The `execution_orchestrator` package is the high-level controller that
coordinates multi-step autonomous task execution from goal to completion.

## Key Modules

| Module | Purpose |
|--------|---------|
| `orchestrator.py` | `ExecutionOrchestrator` — top-level controller |
| `executor.py` | Dispatches individual steps to workers |
| `completion.py` | Evaluates completion criteria and aggregates results |
| `models.py` | `OrchestrationPlan`, `StepResult`, `CompletionReport` models |
| `api.py` | FastAPI router for orchestration management |
