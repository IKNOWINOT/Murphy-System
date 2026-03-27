# Synthetic Failure Generator

The `synthetic_failure_generator` package injects controlled failures into
the Murphy System for chaos-engineering tests and resilience validation.

## Key Modules

| Module | Purpose |
|--------|---------|
| `injection_pipeline.py` | Orchestrates failure injection with timing and targeting |
| `control_failures.py` | Control-plane failure scenarios (latency, drop, reorder) |
| `interface_failures.py` | API and interface failure scenarios (timeout, 5xx, schema error) |
| `models.py` | `FailureSpec`, `InjectionResult` Pydantic models |
| `api.py` | REST API for scheduling and monitoring failure injections |
