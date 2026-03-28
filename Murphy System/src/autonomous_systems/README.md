# Autonomous Systems

The `autonomous_systems` package provides scheduling, risk management, and
human-oversight primitives for autonomous Murphy operations.

## Key Modules

| Module | Purpose |
|--------|---------|
| `autonomous_scheduler.py` | Schedules autonomous tasks with priority queuing |
| `risk_manager.py` | Calculates and enforces risk budgets for autonomous actions |
| `human_oversight_system.py` | HITL gate that pauses execution pending human approval |

## Usage

```python
from autonomous_systems.autonomous_scheduler import AutonomousScheduler
scheduler = AutonomousScheduler()
scheduler.schedule(task={...}, run_at="2026-04-01T00:00:00Z")
```
