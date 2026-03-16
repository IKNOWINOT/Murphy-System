# Supervisor System

The `supervisor_system` package monitors agent execution, captures
assumption violations, and closes correction loops through human-in-the-loop
(HITL) escalation.

## Key Modules

| Module | Purpose |
|--------|---------|
| `hitl_monitor.py` | Watches execution traces and flags anomalies for HITL review |
| `hitl_models.py` | `HITLEvent`, `SupervisionDecision` Pydantic models |
| `correction_loop.py` | Routes HITL decisions back into the learning engine |
| `assumption_management.py` | Tracks and validates assumptions made during execution |
| `anti_recursion.py` | Prevents the supervisor from triggering its own supervision loop |
