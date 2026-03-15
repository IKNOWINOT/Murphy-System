# Chaos Resilience Loop — ARCH-006

**Design Label:** ARCH-006 — Continuous Chaos Resilience Verification  
**Owner:** Platform Engineering  
**Module:** `src/chaos_resilience_loop.py`  
**Tests:** `tests/test_chaos_resilience_loop.py`  
**License:** BSL 1.1

---

## Overview

The Chaos Resilience Loop is Murphy System's automated chaos engineering engine. Inspired by Netflix's continuous resilience verification approach, it continuously generates synthetic failures, injects them into a sandboxed environment, measures recovery behaviour, scores resilience, and feeds findings back into the SelfFixLoop as actionable gaps.

> **"Resilience is not assumed — it is continuously verified."**

Unlike infrastructure-focused chaos tools, Murphy's chaos targets are **confidence engines, gates, bot orchestration, and recovery procedures** — the cognitive and control plane of the system.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CHAOS RESILIENCE LOOP                              │
│                                                                         │
│  1. HYPOTHESIS  → Define what resilience behavior is expected           │
│  2. GENERATE    → SyntheticFailureGenerator creates a FailureCase       │
│  3. INJECT      → FailureInjectionPipeline runs sandboxed simulation    │
│  4. OBSERVE     → Extract recovery metrics from SimulationResult        │
│  5. SCORE       → Compute 0.0–1.0 resilience score                     │
│  6. REPORT      → Aggregate into ResilienceScorecard                   │
│  7. FEED BACK   → Convert weak spots into Gap objects → SelfFixLoop    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Integration Diagram

```
SyntheticFailureGenerator
         │
         │  (FailureCase)
         ▼
ChaosResilienceLoop ──── run_experiment() ──────────────────────►
         │                                                        │
         │  generate_scorecard()                                  │
         │                                                        ▼
         │                                               ResilienceScorecard
         │                                                        │
         │  feed_gaps_to_self_fix()                              │
         ▼                                                        │
     SelfFixLoop ◄────────────── Gap objects ────────────────────┘
         │
         ▼
   Recovery / Remediation
```

### Event Flow

```
CHAOS_EXPERIMENT_STARTED ──► FailureInjectionPipeline ──►
CHAOS_EXPERIMENT_COMPLETED ──► Scoring ──►
CHAOS_SCORECARD_GENERATED ──► feed_gaps_to_self_fix() ──►
CHAOS_GAPS_SUBMITTED ──► SelfFixLoop.plan() ──► SelfFixLoop.execute()
```

---

## Safety Guarantees

| Guarantee | Mechanism |
|---|---|
| Never touches production | Uses only SyntheticFailureGenerator (synthetic packets) |
| Bounded experiments | `max_experiments` hard limit in `run_suite()` |
| Full audit trail | Every experiment persisted via PersistenceManager |
| Event visibility | All lifecycle events published to EventBackbone |
| Thread-safe | `threading.Lock` guards all shared state |
| GovernanceKernel compatible | Requires HIGH authority level to run chaos experiments |

---

## Data Models

### `ResilienceHypothesis`

Defines *what* resilience behaviour is expected when a specific failure occurs.

| Field | Type | Description |
|---|---|---|
| `hypothesis_id` | `str` | Unique identifier |
| `description` | `str` | Human-readable summary |
| `target_component` | `str` | Which subsystem is being tested |
| `failure_type` | `str` | FailureType value (e.g. `"skipped_gate"`) |
| `expected_behavior` | `str` | What should happen |
| `max_acceptable_recovery_time_sec` | `float` | Maximum recovery window (default: 60s) |
| `max_acceptable_confidence_drop` | `float` | Maximum allowed confidence drop (default: 0.3) |

**Example:**
```python
ResilienceHypothesis(
    hypothesis_id="hyp-001",
    description="Skipped gate should trigger confidence grounding check",
    target_component="confidence_engine",
    failure_type="skipped_gate",
    expected_behavior="Gate fires and confidence is grounded within 30s",
    max_acceptable_recovery_time_sec=30.0,
    max_acceptable_confidence_drop=0.2,
)
```

---

### `ResilienceExperiment`

Records the full outcome of a single chaos experiment.

| Field | Type | Description |
|---|---|---|
| `experiment_id` | `str` | Unique experiment ID |
| `hypothesis_id` | `str` | Reference to tested hypothesis |
| `injected_failure` | `FailureCase` | The synthetic failure that was injected |
| `recovery_observed` | `bool` | Whether recovery was observed |
| `recovery_time_sec` | `float` | How long recovery took |
| `confidence_drop` | `float` | Drop in confidence score |
| `gates_that_fired` | `List[str]` | Gates that correctly fired |
| `gates_that_missed` | `List[str]` | Gates that should have fired but didn't |
| `regression_detected` | `bool` | Whether a regression was detected |
| `score` | `float` | Resilience score (0.0–1.0) |

---

### `ResilienceScorecard`

Aggregated results after running a suite of experiments.

| Field | Type | Description |
|---|---|---|
| `overall_score` | `float` | Mean score across all experiments |
| `component_scores` | `Dict[str, float]` | Per-component resilience scores |
| `weakest_components` | `List[str]` | Components below the 0.7 threshold |
| `recommendations` | `List[str]` | Actionable remediation recommendations |
| `experiments_run` | `int` | Total experiments executed |
| `experiments_passed` | `int` | Experiments with score ≥ 0.7 |

---

## Scoring Methodology

Each experiment is scored from **0.0** (total failure) to **1.0** (perfect resilience).

### Score Components

| Component | Weight | Condition |
|---|---|---|
| Recovery observed | 40% | `recovery_observed == True` |
| Recovery within time | 30% | `recovery_time_sec ≤ max_acceptable_recovery_time_sec` |
| Confidence drop bounded | 20% | `confidence_drop ≤ max_acceptable_confidence_drop` |
| No regression | 10% | `regression_detected == False` |

**Partial credit:** If recovery time or confidence drop exceeds the threshold, partial credit is awarded proportionally:
```
time_credit = 0.30 × min(1.0, max_time / actual_time)
drop_credit = 0.20 × min(1.0, max_drop / actual_drop)
```

**Gate miss penalty:** When expected gates were missed, the total score is scaled down:
```
gate_coverage = fired / (fired + missed)
score = score × (1.0 − miss_ratio × 0.5)
```

### Score Interpretation

| Score Range | Interpretation | Action |
|---|---|---|
| 1.0 | Perfect resilience | No action required |
| 0.7–0.99 | Good resilience | Monitor |
| 0.5–0.69 | Degraded resilience | Review gate coverage |
| 0.0–0.49 | Poor resilience | Immediate remediation; gap fed to SelfFixLoop |

### Formula

```
if recovery_observed == False:
    score = 0.0
else:
    score = 0.4 (base)
           + 0.3 × time_ratio
           + 0.2 × drop_ratio
           + 0.1 × (1 if no regression)
    score = score × (1.0 − miss_ratio × 0.5)
    score = clamp(score, 0.0, 1.0)
```

---

## Built-in Hypothesis Library

Four hypotheses are pre-defined for Murphy's core subsystems:

| ID | Description | Failure Type | Target | Max Time |
|---|---|---|---|---|
| `hyp-builtin-001` | Timeout cluster should be caught by threshold tuning | `delayed_verification` | `threshold_tuning` | 60s |
| `hyp-builtin-002` | Skipped gate should trigger confidence grounding check | `skipped_gate` | `confidence_engine` | 30s |
| `hyp-builtin-003` | False confidence inflation should be detected and corrected | `false_confidence` | `confidence_engine` | 45s |
| `hyp-builtin-004` | Missing rollback should trigger recovery procedure registration | `missing_rollback` | `recovery_coordinator` | 30s |

Access via:
```python
hypotheses = ChaosResilienceLoop.builtin_hypotheses()
```

---

## Usage

### Basic Usage

```python
from chaos_resilience_loop import ChaosResilienceLoop
from event_backbone import EventBackbone
from self_fix_loop import SelfFixLoop
from synthetic_failure_generator.injection_pipeline import FailureInjectionPipeline

# Initialise dependencies
pipeline = FailureInjectionPipeline()
fix_loop = SelfFixLoop(...)
backbone = EventBackbone()

# Create the chaos loop
chaos = ChaosResilienceLoop(
    failure_generator=pipeline,
    self_fix_loop=fix_loop,
    event_backbone=backbone,
)

# Run built-in hypothesis suite
results = chaos.run_suite(ChaosResilienceLoop.builtin_hypotheses())

# Generate scorecard
scorecard = chaos.generate_scorecard()
print(f"Overall resilience: {scorecard.overall_score:.2f}")
print(f"Weakest components: {scorecard.weakest_components}")

# Feed gaps back to SelfFixLoop
submitted = chaos.feed_gaps_to_self_fix()
print(f"Submitted {len(submitted)} gaps to SelfFixLoop")
```

### Defining Custom Hypotheses

```python
h = chaos.define_hypothesis(
    hypothesis_id="hyp-custom-001",
    description="Authority override should be blocked within 10s",
    target_component="governance_kernel",
    failure_type="authority_override",
    expected_behavior="Governance kernel blocks override and logs audit trail",
    max_acceptable_recovery_time_sec=10.0,
    max_acceptable_confidence_drop=0.15,
)

# Run a single experiment
experiment = chaos.run_experiment(h)
print(f"Score: {experiment.score:.2f}")
print(f"Gates fired: {experiment.gates_that_fired}")
```

### Running a Bounded Suite

```python
# Define multiple custom hypotheses
hypotheses = [
    chaos.define_hypothesis(f"hyp-{i}", ...),
    ...
]

# Run with a hard limit of 20 experiments
results = chaos.run_suite(hypotheses, max_experiments=20)
```

---

## Example Experiment Trace

```
[CHAOS] Experiment exp-a3f2b1c0 started
  hypothesis: hyp-builtin-002 (skipped_gate → confidence_engine)
  failure_type: skipped_gate

[CHAOS] FailureInjectionPipeline: generating failure case
  failure_id: fc-7e2d9a1b
  missed_gates: ["confidence-grounding-check"]

[CHAOS] Running sandboxed simulation...
  initial_confidence: 0.800
  final_confidence: 0.620
  confidence_drop: 0.180
  detection_latency: 4.2s
  gates_triggered: ["confidence-grounding-check"]
  gates_missed: []
  execution_halted: True

[CHAOS] Scoring...
  recovery_observed: True (+0.40)
  time: 4.2s ≤ 30s (+0.30)
  drop: 0.18 ≤ 0.20 (+0.20)
  no regression (+0.10)
  gate miss penalty: 0 missed / 1 total (×1.0)
  SCORE: 1.00

[CHAOS] Experiment exp-a3f2b1c0 completed: score=1.00
  Published: CHAOS_EXPERIMENT_COMPLETED
```

---

## How to Add Custom Hypotheses

1. **Choose a FailureType** from `synthetic_failure_generator.models.FailureType`
2. **Identify the target component** (e.g. `"confidence_engine"`, `"threshold_tuning"`)
3. **Define recovery criteria** — maximum time and confidence drop
4. **Define expected behaviour** — what gates should fire and what should happen

```python
# Step 1-4: Define hypothesis
h = chaos.define_hypothesis(
    hypothesis_id="hyp-my-custom",
    description="My custom resilience test",
    target_component="my_component",
    failure_type="false_confidence",            # from FailureType enum
    expected_behavior="Recalibration gate fires and confidence is restored",
    max_acceptable_recovery_time_sec=45.0,
    max_acceptable_confidence_drop=0.25,
)

# Step 5: Run it
experiment = chaos.run_experiment(h)
```

### Available FailureType Values

| Category | Values |
|---|---|
| Semantic | `unit_mismatch`, `ambiguous_label`, `missing_constraint`, `conflicting_goal` |
| Control Plane | `delayed_verification`, `skipped_gate`, `false_confidence`, `missing_rollback` |
| Interface | `stale_data`, `actuator_drift`, `intermittent_connectivity`, `partial_write` |
| Organizational | `authority_override`, `ignored_warning`, `misaligned_incentive`, `schedule_pressure` |

---

## Event Reference

All events are published to the `EventBackbone`. Subscribe using `EventType` enum values.

| Event | Type | Payload |
|---|---|---|
| `CHAOS_EXPERIMENT_STARTED` | `EventType.CHAOS_EXPERIMENT_STARTED` | `experiment_id`, `hypothesis_id`, `failure_type`, `target_component` |
| `CHAOS_EXPERIMENT_COMPLETED` | `EventType.CHAOS_EXPERIMENT_COMPLETED` | `experiment_id`, `hypothesis_id`, `score`, `recovery_observed` |
| `CHAOS_SCORECARD_GENERATED` | `EventType.CHAOS_SCORECARD_GENERATED` | Full scorecard dict |
| `CHAOS_GAPS_SUBMITTED` | `EventType.CHAOS_GAPS_SUBMITTED` | `gap_count`, `gap_ids` |

**Example subscription:**
```python
from event_backbone import EventType

backbone.subscribe(
    EventType.CHAOS_EXPERIMENT_COMPLETED,
    lambda evt: print(f"Experiment done: score={evt.payload['score']}"),
)
```

---

## Related Modules

| Module | Relationship |
|---|---|
| `synthetic_failure_generator` | Generates synthetic `FailureCase` objects and runs sandboxed simulations |
| `self_fix_loop` | Receives `Gap` objects from weak-component analysis |
| `self_healing_coordinator` | Provides recovery procedure context |
| `event_backbone` | Receives all lifecycle events |
| `governance_kernel` | Enforces HIGH authority requirement for chaos experiments |
| `persistence_manager` | Stores all experiment and scorecard data |

---

*Copyright © 2020 Inoni Limited Liability Company — License: BSL 1.1*
