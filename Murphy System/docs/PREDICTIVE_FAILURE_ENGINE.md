# Predictive Failure Anticipation Engine — PRED-001

**License:** BSL 1.1  
**Owner:** Backend Team  
**Design Label:** PRED-001  
**Status:** Active

---

## Overview

The **Predictive Failure Anticipation Engine** uses statistical analysis of
historical telemetry, error patterns, and confidence trajectories to predict
failures *before* they happen and pre-emptively trigger remediation.

It complements the reactive `SelfFixLoop` (ARCH-005) with a proactive, forward-
looking layer that surfaces weak signals early enough for automated intervention.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Murphy System Runtime                         │
│                                                                  │
│  Telemetry Events ──► PredictiveFailureEngine                    │
│  Error Records    ──►   │                                        │
│                         ├── _detect_latency_degradation()        │
│                         ├── _detect_error_rate_acceleration()    │
│                         ├── _detect_confidence_drift()           │
│                         ├── _detect_resource_exhaustion()        │
│                         └── _detect_recurring_patterns()         │
│                                  │                               │
│                         AdaptiveWeightManager                    │
│                                  │                               │
│                         PredictionResult[]                       │
│                                  │                               │
│              ┌───────────────────┴─────────────────┐            │
│              │                                     │            │
│         preempt()                          EventBackbone         │
│              │                                     │            │
│    ┌─────────┴──────────┐              PREDICTION_GENERATED      │
│    │                    │              PREDICTION_PREEMPTED       │
│ SelfFixLoop     SelfHealingCoordinator  PREDICTION_MATERIALIZED  │
│ (ARCH-005)      (OBS-004)              PREDICTION_FALSE_POSITIVE │
│                                                                  │
│  record_outcome() ──► AdaptiveWeightManager (feedback loop)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Other Modules

| Module | Integration Point |
|---|---|
| `SelfFixLoop` (ARCH-005) | `preempt()` calls `run_loop(max_iterations=1)` when a prediction is generated |
| `SelfHealingCoordinator` (OBS-004) | Fallback in `preempt()` if SelfFixLoop is unavailable; `handle_failure()` is called |
| `BugPatternDetector` (DEV-004) | `_detect_recurring_patterns()` queries `get_patterns()` for known fingerprints |
| `EventBackbone` | Publishes `PREDICTION_GENERATED`, `PREDICTION_PREEMPTED`, `PREDICTION_MATERIALIZED`, `PREDICTION_FALSE_POSITIVE` |
| `PersistenceManager` | Every `PredictionResult` is durably saved via `save_document()` |
| `GovernanceKernel` | Engine itself does not modify source files; all preemptive actions are bounded by existing authority bands |

---

## Heuristic Detectors

### 1. `_detect_latency_degradation()`

- **Trigger:** p95 response time exceeds 2× the established baseline.
- **Baseline:** Computed lazily from the first half of the sliding window.
- **Signal type:** `latency_spike`
- **Tuning parameters:**
  - `_LATENCY_BASELINE_RATIO` (default `2.0`) — multiplier above baseline to trigger.
  - `window_size` (default `100`) — number of telemetry events in the sliding window.
- **Minimum data:** 5 telemetry events with `response_time_ms`.

### 2. `_detect_error_rate_acceleration()`

- **Trigger:** The error count derivative is strictly positive for `_ERROR_ACCEL_WINDOWS` consecutive snapshots.
- **Signal type:** `error_rate_increase`
- **Tuning parameters:**
  - `_ERROR_ACCEL_WINDOWS` (default `3`) — consecutive windows that must show acceleration.
  - `error_window` (default `50`) — sliding window size for error records.

### 3. `_detect_confidence_drift()`

- **Trigger:** Linear regression slope of confidence scores for any component falls below `-_CONFIDENCE_DRIFT_THRESHOLD`.
- **Signal type:** `confidence_drift`
- **Tuning parameters:**
  - `_CONFIDENCE_DRIFT_THRESHOLD` (default `0.05`) — negative slope magnitude to trigger.
- **Minimum data:** 3 confidence readings per component.

### 4. `_detect_resource_exhaustion()`

- **Trigger:** Any of:
  - `memory_mb > 90%` of a 4 GB reference (3686 MB).
  - `runtime_config_size > 10,000` entries.
  - `registered_procedures > 500`.
- **Signal type:** `resource_pressure`
- **Tuning parameters:** Thresholds are currently constant; submit to `GovernanceKernel` for runtime override.

### 5. `_detect_recurring_patterns()`

- **Trigger:** An error fingerprint that was seen before reappears within the cooldown window.
- **Signal type:** `pattern_recurrence`
- **Tuning parameters:**
  - `_PATTERN_COOLDOWN_SEC` (default `3600`) — seconds within which a re-occurrence counts as recurring.
- **Confidence:** Fixed at `0.9` — recurrence is a strong indicator.

---

## AdaptiveWeightManager

Maintains per-heuristic accuracy scores and adjusts prediction probability weights:

| Event | Effect |
|---|---|
| `record_outcome("materialized")` | Increases heuristic weight by `_WEIGHT_INCREASE` (0.10) |
| `record_outcome("false_positive")` | Decreases heuristic weight by `_WEIGHT_DECREASE` (0.15) |

Weights are bounded within `[0.1, 2.0]`.

---

## Event Reference

| Event Type | When Published |
|---|---|
| `PREDICTION_GENERATED` | Every time `analyze()` produces a `PredictionResult` |
| `PREDICTION_PREEMPTED` | When `preempt()` successfully initiates a preemptive action |
| `PREDICTION_MATERIALIZED` | When `record_outcome()` is called with `"materialized"` |
| `PREDICTION_FALSE_POSITIVE` | When `record_outcome()` is called with `"false_positive"` |

---

## Example Prediction Trace

```
1. Telemetry ingestion:
   engine.ingest_telemetry({"component": "api-gw", "response_time_ms": 80})
   ... (baseline established at ~90 ms) ...
   engine.ingest_telemetry({"component": "api-gw", "response_time_ms": 950})

2. Analysis:
   predictions = engine.analyze()
   # → [PredictionResult(
   #       prediction_id="pred-a1b2c3d4",
   #       predicted_failure_type="latency_spike",
   #       probability=0.72,
   #       estimated_time_to_failure_sec=648.0,
   #       recommended_preemptive_action="Scale out affected service or trigger cache warm-up",
   #       status="predicted",
   #   )]

3. Preemption:
   engine.preempt(predictions[0])
   # → SelfFixLoop.run_loop(max_iterations=1) called
   # → EventBackbone publishes PREDICTION_PREEMPTED

4. Outcome feedback:
   engine.record_outcome("pred-a1b2c3d4", "false_positive")
   # → AdaptiveWeightManager decreases "latency_degradation" weight by 0.15
   # → EventBackbone publishes PREDICTION_FALSE_POSITIVE
```

---

## Safety Invariants

- **Non-blocking:** `analyze()` is purely synchronous and on-demand; no background threads are spawned.
- **Bounded memory:** Sliding windows use `deque(maxlen=N)` or `capped_append()`.
- **Read-only analysis:** No source files are modified.
- **Thread-safe:** All shared state is guarded by `threading.Lock`.
- **Graceful degradation:** If `SelfFixLoop`, `SelfHealingCoordinator`, `EventBackbone`, or `PersistenceManager` are `None`, the engine continues operating silently.

---

*Copyright © 2020 Inoni Limited Liability Company — License: BSL 1.1*
