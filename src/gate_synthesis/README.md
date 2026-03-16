# `src/gate_synthesis` — Gate Synthesis Engine

Dynamic gate generator that creates control policies to prevent Murphy paths before they occur.
Implements failure mode enumeration, risk path analysis, and lifecycle management for gates.

## Public API

```python
from gate_synthesis import (
    Gate, GateType, GateCategory, GateState,
    RiskVector, RiskPath, FailureMode,
    GateGenerator, GateLifecycleManager,
    FailureModeEnumerator, MurphyProbabilityEstimator,
)
```

## Core Concepts

### Gate

A gate is a control policy that blocks or requires approval for a risky execution path:

```python
@dataclass
class Gate:
    gate_id: str
    gate_type: GateType           # HARD_BLOCK | SOFT_BLOCK | APPROVAL_REQUIRED
    category: GateCategory        # SAFETY | COMPLIANCE | RESOURCE | QUALITY
    state: GateState              # DRAFT | ACTIVE | RETIRED
    risk_vectors: List[RiskVector]
    blast_radius: BlastRadius
    retirement_condition: RetirementCondition
```

### Gate Generator

Generates gates from failure mode analysis:

```python
from gate_synthesis import GateGenerator, FailureModeEnumerator

enumerator = FailureModeEnumerator()
failure_modes = enumerator.enumerate(component="email_delivery")

generator = GateGenerator()
gates = generator.generate_from_failure_modes(failure_modes)
```

### Murphy Probability Estimator

Estimates the probability that a given risk path leads to system failure:

```python
from gate_synthesis import MurphyProbabilityEstimator

estimator = MurphyProbabilityEstimator()
p = estimator.estimate(risk_path)   # 0.0–1.0
```

## Gate Lifecycle

```
DRAFT  →  ACTIVE  →  RETIRED
           │
           ▼  (condition met)
        RETIRED
```

## Tests

`tests/test_gate_synthesis*.py`, `tests/test_gate_lifecycle*.py`
