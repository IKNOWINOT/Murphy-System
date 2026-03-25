# Permutation Calibration System

> **Murphy should use permutation-driven exploration to discover high-value ordered evidence patterns from live-world interaction, then distill those patterns into governed procedural policies that remain subject to drift detection, HITL review, and rollback.**

## Overview

The Permutation Calibration System enables Murphy to treat **information order as a learnable control variable**. In dynamic environments, the order of:

- Connector updates
- API responses
- Human feedback
- Telemetry
- Evidence collection

...can change confidence, routing, escalation timing, procedural choice, and final output quality.

This system allows Murphy to:
1. **Explore different orderings** (Mode A)
2. **Measure which orderings improve calibration**
3. **Learn recurring high-value patterns**
4. **Convert those patterns into procedural execution** (Mode B)

## Architecture

```
Connectors / APIs / Sensors / Human Inputs
                  ↓
      Intake normalization + grouping
                  ↓
   Permutation candidate generation (Mode A)
                  ↓
   Calibration / outcome / stability scoring
                  ↓
      Policy distillation + registration
                  ↓
 Deterministic routing + procedural execution
                  ↓
      HITL / delivery / audit / observability
                  ↓
      Drift detection → reopen exploration
```

## Core Modules

### 1. Permutation Policy Registry (`src/permutation_policy_registry.py`)

Central storage for learned sequence families with lifecycle management.

**Lifecycle States:**
- **Experimental** - Newly discovered pattern, lightly supported
- **Probationary** - Shows repeated promise, not enough validation yet
- **Promoted** - Allowed to drive procedural routing in Mode B
- **Deprecated** - Demoted because drift or fragility appeared

```python
from src.permutation_policy_registry import (
    PermutationPolicyRegistry, 
    SequenceType, 
    SequenceStatus
)

registry = PermutationPolicyRegistry()

# Register a discovered sequence
sequence_id = registry.register_sequence(
    name="CRM Integration Order",
    sequence_type=SequenceType.CONNECTOR_ORDER,
    domain="crm_integration",
    ordering=["crm_connector", "analytics_api", "user_feedback"],
)

# Record evaluation results
registry.record_evaluation(
    sequence_id=sequence_id,
    outcome_quality=0.85,
    calibration_quality=0.8,
    stability_score=0.75,
    success=True,
)

# Promote when ready
registry.promote_sequence(
    sequence_id=sequence_id,
    target_status=SequenceStatus.PROMOTED,
    approver="admin",
)
```

### 2. Permutation Calibration Adapter (`src/permutation_calibration_adapter.py`)

Bridges intake order generation to scoring. Supports multiple exploration modes:

- **Exhaustive** - Try all permutations (for small sets ≤6 items)
- **Sampling** - Random sampling of permutations
- **Greedy** - Best-first neighbor exploration
- **Beam Search** - Beam search with pruning

```python
from src.permutation_calibration_adapter import (
    PermutationCalibrationAdapter,
    create_intake_item,
    ExplorationMode,
)

adapter = PermutationCalibrationAdapter()

# Create intake items
items = [
    create_intake_item("connector", "crm"),
    create_intake_item("api", "analytics"),
    create_intake_item("evidence", "feedback"),
]

# Start exploration session
session_id = adapter.start_exploration(
    domain="sales_pipeline",
    items=items,
    mode=ExplorationMode.SAMPLING,
    max_candidates=50,
)

# Run exploration
result = adapter.run_exploration(session_id)
print(f"Best ordering: {result['best_result']['ordering']}")
print(f"Best score: {result['best_result']['aggregate_score']}")
```

### 3. Procedural Distiller (`src/procedural_distiller.py`)

Converts learned sequences into executable procedural templates for Mode B.

```python
from src.procedural_distiller import ProceduralDistiller

distiller = ProceduralDistiller()

# Distill from a sequence
result = distiller.distill_from_sequence(
    sequence_data={
        "sequence_id": "seq-001",
        "name": "Sales Pipeline Order",
        "domain": "sales",
        "ordering": ["crm", "analytics", "feedback"],
        "confidence_score": 0.8,
    },
    item_types={
        "crm": "connector",
        "analytics": "api",
        "feedback": "evidence",
    },
)

# Activate for production use
distiller.activate_template(result["template_id"], approver="admin")
```

### 4. Order Sensitivity Metrics (`src/order_sensitivity_metrics.py`)

Provides statistical analysis of whether ordering actually matters.

```python
from src.order_sensitivity_metrics import OrderSensitivityMetrics

metrics = OrderSensitivityMetrics()

# Record observations
for ordering, score in results:
    metrics.record_observation(
        domain="sales",
        ordering=ordering,
        outcome_score=score,
    )

# Analyze path dependence
analysis = metrics.analyze_path_dependence("sales")
print(f"Path dependent: {analysis['is_path_dependent']}")
print(f"Strength: {analysis['path_dependence_strength']}")
print(f"Should learn: {analysis['should_learn_ordering']}")
```

## Integration with Existing Murphy Systems

### Self-Improvement Engine Extension

The `PermutationLearningExtension` in `src/self_improvement_engine.py` adds:
- Exploratory vs procedural outcome comparison
- Drift detection
- Promotion/demotion recommendations

```python
from src.self_improvement_engine import (
    SelfImprovementEngine,
    PermutationLearningExtension,
)

engine = SelfImprovementEngine()
ext = PermutationLearningExtension(engine)

# Compare modes
comparison = ext.compare_exploratory_vs_procedural("sales_domain")
if comparison["recommendation"] == "reopen_exploration":
    # Performance drifted - reopen Mode A
    pass
```

### Observability Counters

New categories in `src/observability_counters.py`:
- `permutation_exploration` - Exploration run counts
- `sequence_learning` - Learned sequence counts
- `permutation_promotion` - Promotion events
- `permutation_demotion` - Demotion events
- `drift_detection` - Drift detection events

```python
from src.observability_counters import ObservabilitySummaryCounters

counters = ObservabilitySummaryCounters()
counters.record_exploration("sales", 50, "Sales domain exploration")
counters.record_promotion("sales", "Promoted sales sequence")

summary = counters.get_permutation_calibration_summary()
```

### Gate Execution Wiring

New gates in `src/gate_execution_wiring.py`:
- `PERMUTATION_EXPLORATION` - Controls when exploration is allowed
- `SEQUENCE_PROMOTION` - Controls sequence promotion to production

```python
from src.gate_execution_wiring import GateExecutionWiring

gates = GateExecutionWiring()

# Limit exploration to specific domains
gates.register_permutation_exploration_gate(
    max_candidates=100,
    allowed_domains=["sales", "support"],
)

# Require approval for promotion
gates.register_sequence_promotion_gate(
    require_approval=True,
    min_evaluations=10,
    min_confidence=0.7,
)
```

### Semantics Boundary Controller

New methods in `src/semantics_boundary_controller.py`:
- `check_order_invariance()` - Test if results are order-sensitive
- `classify_domain_sensitivity()` - Classify as stable/sensitive/fragile
- `get_order_invariance_summary()` - Get invariance statistics

```python
from src.semantics_boundary_controller import SemanticsBoundaryController

controller = SemanticsBoundaryController()

# Check if ordering matters
result = controller.check_order_invariance(
    domain="sales",
    ordering_a=["a", "b", "c"],
    result_a=0.85,
    ordering_b=["c", "b", "a"],
    result_b=0.82,
)

print(f"Classification: {result['classification']}")
# "invariant", "weakly_sensitive", "moderately_sensitive", "highly_sensitive"
```

## Scoring Dimensions

The system scores sequences across multiple dimensions (spec Section 8):

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Outcome Quality | 0.25 | Overall result quality |
| Calibration Quality | 0.25 | Confidence calibration accuracy |
| Stability | 0.20 | Consistency across variations |
| Latency | 0.10 | Execution speed |
| Cost | 0.10 | Execution cost |
| HITL Efficiency | 0.05 | Human intervention efficiency |
| Governance Fit | 0.05 | Compliance with governance rules |

## Promotion Criteria

A sequence is promoted when it demonstrates (spec Section 5.2):
- Better outcome than current baseline
- Acceptable repeatability
- Low enough fragility
- Understandable explanation
- Gate approval for risk level

Default criteria for Probationary → Promoted:
- Minimum 10 evaluations
- ≥75% success rate
- ≥0.7 stability score
- ≥0.65 calibration quality
- ≤0.3 fragility
- Gate approval required

## Reversion Rules

A sequence should be deprecated when (spec Section 5.3):
- Success rate drops significantly
- Confidence drifts down
- Connector timing changes
- Source reliability changes
- Human overrides rise
- Policy becomes brittle under minor variation

## Best Application Areas

1. **Connector Arbitration** - Learn which order to query/trust multiple connectors
2. **Incident Triage** - Learn evidence ordering for best swarm composition
3. **Self-Improvement Loops** - Learn orderings that reduce downstream fixes
4. **Golden Path Replay** - Compare to prior successful ordered paths
5. **HITL Graduation** - Graduate procedures with stable ordering patterns
6. **Paper Trading / Simulation** - Learn ordering for market observations
7. **Industrial / Sensor Fusion** - Learn sensor sequence for safest interpretation

## Safety Requirements

The system remains governed (spec Section 9):
- Gate-based exploration permissions
- Bounded permutation count
- Policy audit trail
- Human approval for high-impact promotion
- Rollback to prior policy

## Usage Example: Complete Workflow

```python
from src.permutation_policy_registry import PermutationPolicyRegistry, SequenceType, SequenceStatus
from src.permutation_calibration_adapter import PermutationCalibrationAdapter, create_intake_item
from src.procedural_distiller import ProceduralDistiller
from src.order_sensitivity_metrics import OrderSensitivityMetrics
from src.self_improvement_engine import SelfImprovementEngine, PermutationLearningExtension

# Initialize components
registry = PermutationPolicyRegistry()
adapter = PermutationCalibrationAdapter()
distiller = ProceduralDistiller()
metrics = OrderSensitivityMetrics()
engine = SelfImprovementEngine()
learning_ext = PermutationLearningExtension(engine)
learning_ext.connect_registry(registry)
learning_ext.connect_order_metrics(metrics)

# Step 1: Create intake items
items = [
    create_intake_item("connector", "crm_connector"),
    create_intake_item("api", "analytics_api"),
    create_intake_item("evidence", "user_feedback"),
]

# Step 2: Run exploration (Mode A)
session_id = adapter.start_exploration(
    domain="crm_integration",
    items=items,
    max_candidates=30,
)
exploration_result = adapter.run_exploration(session_id)
best_ordering = exploration_result["best_result"]["ordering"]

# Step 3: Register discovered sequence
sequence_id = registry.register_sequence(
    name="CRM Integration Sequence",
    sequence_type=SequenceType.CONNECTOR_ORDER,
    domain="crm_integration",
    ordering=best_ordering,
)

# Step 4: Validate through multiple evaluations
for _ in range(10):
    registry.record_evaluation(
        sequence_id=sequence_id,
        outcome_quality=0.85,
        calibration_quality=0.8,
        stability_score=0.75,
        success=True,
    )

# Step 5: Promote to procedural mode
registry.promote_sequence(
    sequence_id=sequence_id,
    target_status=SequenceStatus.PROMOTED,
    approver="system_admin",
)

# Step 6: Distill into procedure (Mode B)
seq_data = registry.get_sequence(sequence_id)
distill_result = distiller.distill_from_sequence(
    sequence_data=seq_data,
    item_types={item.item_id: item.item_type for item in items},
)

# Step 7: Activate procedure
distiller.activate_template(distill_result["template_id"], approver="system_admin")

# Step 8: Monitor for drift
for execution in production_executions:
    learning_ext.record_procedural_outcome(
        domain="crm_integration",
        sequence_id=sequence_id,
        ordering=best_ordering,
        outcome_quality=execution.quality,
        calibration_quality=execution.calibration,
        session_id=execution.session_id,
    )

drift = learning_ext.detect_drift("crm_integration")
if drift["drift_detected"]:
    # Reopen exploration
    registry.deprecate_sequence(sequence_id, "Performance drift detected")
    # Start new exploration cycle...
```

## Files Changed

### New Files
- `src/permutation_policy_registry.py` - Sequence family registry
- `src/permutation_calibration_adapter.py` - Exploration adapter
- `src/procedural_distiller.py` - Procedure distillation
- `src/order_sensitivity_metrics.py` - Statistical metrics
- `tests/test_permutation_calibration.py` - Comprehensive tests (69 tests)

### Modified Files
- `src/self_improvement_engine.py` - Added `PermutationLearningExtension`
- `src/observability_counters.py` - Added permutation categories and recorders
- `src/gate_execution_wiring.py` - Added permutation gates
- `src/semantics_boundary_controller.py` - Added order invariance checking

## References

- Permutation Calibration Application Spec for Murphy (provided in problem statement)
- Murphy System Architecture documentation
- Self-Improvement Engine (ARCH-001)
- Golden Path Bridge documentation
- HITL Autonomy Controller documentation
