# `src/governance_framework` — Governance Framework

Formal governance framework implementing agent descriptors, artifact ingestion,
stability monitoring, and scheduling invariants for the Murphy System.

## Public API

```python
from governance_framework import (
    AgentDescriptor, AgentDescriptorValidator, AuthorityBand, ActionType,
    GovernanceArtifact, ArtifactRegistry, ArtifactValidator, ArtifactType,
    StabilityController, StabilityMetrics,
    RefusalHandler, RefusalRecord,
    GovernanceScheduler, SchedulingDecision,
)
```

## Key Components

### AgentDescriptor

Defines an agent's identity, capabilities, and authority boundaries:

```python
descriptor = AgentDescriptor(
    agent_id="worker-1",
    authority_band=AuthorityBand.OPERATOR,
    allowed_actions=[ActionType.READ, ActionType.EXECUTE],
    requires_hitl_for=[ActionType.DELETE, ActionType.ADMIN],
)
validator = AgentDescriptorValidator()
validator.validate(descriptor)   # raises on violation
```

### StabilityController

Tracks execution outcomes and triggers refusals when stability metrics degrade:

```python
controller = StabilityController()
controller.record_outcome(ExecutionOutcome.SUCCESS)
metrics: StabilityMetrics = controller.get_metrics()
# metrics.stability_score  → 0.0–1.0
```

### GovernanceScheduler

Enforces scheduling invariants (rate limits, quorum, conflict resolution):

```python
scheduler = GovernanceScheduler()
decision: SchedulingDecision = scheduler.evaluate(task)
# decision.approved → True | False
```

## Tests

`tests/test_governance*.py`, `tests/test_hitl_gates*.py`
