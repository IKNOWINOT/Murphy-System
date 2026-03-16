# `src/rosetta` — Rosetta State Management System

Persistent, human-readable agent state management for the Murphy System.
Stores agent identity, goals, tasks, system health, automation progress, and
improvement proposals in versioned JSON documents.

## Public API

```python
from rosetta import (
    RosettaManager,
    RosettaAgentState, Identity, SystemState, AgentState, Goal, Task,
    RosettaSubsystemWiring, WiringStatus, bootstrap_wiring,
)
```

## Core Usage

```python
from rosetta import RosettaManager, RosettaAgentState, Identity

mgr = RosettaManager(persistence_dir="data/rosetta")

# Save
state = RosettaAgentState(identity=Identity(agent_id="worker-1", name="Worker", role="executor"))
mgr.save_state(state)

# Load
loaded = mgr.load_state("worker-1")

# Partial update
mgr.update_state("worker-1", {"system_state": {"status": "active"}})
```

## Subsystem Wiring (INC-07 / H-03)

`RosettaSubsystemWiring` wires Rosetta to live Murphy subsystems (P3-001 through P3-005):

```python
from rosetta import bootstrap_wiring

wiring = bootstrap_wiring(
    rosetta_manager=mgr,
    event_backbone=backbone,
    self_improvement_engine=improvement_engine,
    self_automation_orchestrator=orchestrator,
    rag_vector_integration=rag,
)
# wiring.status.p3_001_patterns_to_rosetta → True
```

## File Layout

| Module | Purpose |
|--------|---------|
| `rosetta_manager.py` | CRUD + persistence (`save_state`, `load_state`, `update_state`) |
| `rosetta_models.py` | Pydantic models (`RosettaAgentState`, `Identity`, `Goal`, `Task`, …) |
| `subsystem_wiring.py` | P3 wiring (INC-07) — connects Rosetta to live subsystems |
| `rosetta_document_builder.py` | Human-readable markdown document builder |
| `global_aggregator.py` | Aggregates state across all agents |
| `archive_classifier.py` | Archives stale/completed states |
| `recalibration_scheduler.py` | Schedules periodic state recalibration |

## Tests

`tests/test_rosetta_*.py` — manager, models, subsystem wiring (38 tests).
