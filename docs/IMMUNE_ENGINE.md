# Murphy Immune Engine — ARCH-014

**Design Label:** ARCH-014 — Murphy Immune Engine  
**Owner:** Backend Team  
**Module:** `src/murphy_immune_engine.py`  
**Tests:** `tests/test_murphy_immune_engine.py`  
**License:** BSL 1.1

---

## Overview

The Murphy Immune Engine is Murphy System's next-generation autonomous self-coding and self-healing platform.  It wraps and extends every existing self-healing component — adding Kubernetes-style desired-state reconciliation, predictive failure analysis, biological immune memory, chaos-hardened fix validation, and cascade-aware planning.

> **Design philosophy:** Don't just react to failures — predict them, remember their cures, harden those cures against chaos, and prevent cascades before they begin.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        MURPHY IMMUNE ENGINE  (ARCH-014)                      │
│                                                                              │
│  Phase 1 ─ RECONCILE ─────▶ DesiredStateReconciler ──▶ DriftEvents          │
│  Phase 2 ─ PREDICT ────────▶ PredictiveFailureAnalyzer ▶ PredictedFailures  │
│  Phase 3 ─ DIAGNOSE ───────▶ SelfFixLoop.diagnose() ──▶ Gaps                │
│  Phase 4 ─ RECALL ─────────▶ ImmunityMemory ──────────▶ instant fix / skip  │
│  Phase 5 ─ PLAN ───────────▶ SelfFixLoop.plan()                             │
│  Phase 6 ─ EXECUTE ────────▶ SelfFixLoop.execute()                          │
│  Phase 7 ─ TEST ───────────▶ SelfFixLoop.test()                             │
│  Phase 8 ─ HARDEN ─────────▶ ChaosHardenedValidator ──▶ chaos pass/fail     │
│  Phase 9 ─ CASCADE CHECK ──▶ CascadeAnalyzer ─────────▶ regressions?        │
│  Phase 10 ─ MEMORIZE ──────▶ ImmunityMemory.memorize()                      │
│  Phase 11 ─ REPORT ────────▶ ImmuneReport                                   │
│                                                                              │
│  ┌──────────────┐  ┌───────────────────────┐  ┌──────────────────────────┐  │
│  │ SelfFixLoop  │  │ SelfImprovementEngine │  │ SelfHealingCoordinator   │  │
│  │  (ARCH-005)  │  │       (ARCH-001)      │  │        (OBS-004)         │  │
│  └──────────────┘  └───────────────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌───────────────────────┐  ┌──────────────────────────┐  │
│  │BugPatternDet.│  │    EventBackbone      │  │   PersistenceManager     │  │
│  │  (DEV-004)   │  │                       │  │                          │  │
│  └──────────────┘  └───────────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## How the Immune Cycle Works

### Phase 1 — Reconcile

`DesiredStateReconciler` loads the desired-state manifest and compares it against live subsystem observations.  Every discrepancy emits a `DriftEvent` and publishes `DRIFT_DETECTED` to the EventBackbone.

### Phase 2 — Predict

`PredictiveFailureAnalyzer` consumes historical error-rate snapshots from `BugPatternDetector`, performs time-series trend analysis, and produces `PredictedFailure` objects for categories showing consistent upward error rates.  Each prediction publishes `FAILURE_PREDICTED`.

### Phase 3 — Diagnose

Delegates to `SelfFixLoop.diagnose()` for current system gaps.  Predicted failures are converted to synthetic gaps and appended to the active gap list.

### Phase 4 — Recall

For each gap, `ImmunityMemory` is consulted.  If a proven fix exists with sufficient confidence:
- The fix is applied immediately (planning/execution skipped).
- `IMMUNITY_RECALLED` event is published.
- The gap is marked resolved.

### Phase 5–7 — Plan → Execute → Test

New gaps (not in memory) are processed by the underlying `SelfFixLoop`: `plan()` → `execute()` → `test()`.  Failed tests trigger `rollback()`.

### Phase 8 — Harden

Every fix that passes normal testing is submitted to `ChaosHardenedValidator`.  Synthetic failures matching the same category are injected via `FailureInjectionPipeline` (if available) to stress-test the fix.  Fixes that fail chaos testing are **not** promoted to `ImmunityMemory`.

### Phase 9 — Cascade Check

`CascadeAnalyzer` inspects all downstream categories connected to the fixed category.  Optional per-category health-checks detect regressions.  Fixes that trigger cascades are **not** memorized.

### Phase 10 — Memorize

Fixes that pass both chaos hardening **and** cascade checks are stored in `ImmunityMemory` with full confidence.  Future occurrences of the same failure are resolved instantly.

### Phase 11 — Report

An `ImmuneReport` is generated, persisted to `PersistenceManager`, and published as `IMMUNE_CYCLE_COMPLETED` on the EventBackbone.

---

## Components

### `DesiredStateReconciler`

Kubernetes-style drift detection.  Compares a user-supplied manifest (dict) against observed system state.

| Key capability | Detail |
|---|---|
| `reconcile(actual_state)` | Returns `List[DriftEvent]` — one per discrepancy |
| `set_desired_state(manifest)` | Update the manifest at runtime |
| `get_drift_history()` | Full history of drift events |
| Severity classification | `circuit_breaker_states` → critical; `active_bot_count` → high; default → medium |

---

### `PredictiveFailureAnalyzer`

Statistical trend analysis on historical error-rate snapshots.

| Key capability | Detail |
|---|---|
| `record_snapshot(snapshot)` | Record `{category: count}` snapshot |
| `analyze(horizon_seconds)` | Returns `List[PredictedFailure]` for trending categories |
| `get_canary_score(category)` | 0.0–1.0 risk score for a specific category |
| Trigger threshold | Category must show positive growth in ≥30% of intervals |

---

### `ImmunityMemory`

Biological immune memory pattern.  Stores proven fixes indexed by a SHA-256 fingerprint of `(category, error_type, severity)`.

| Key capability | Detail |
|---|---|
| `memorize(...)` | Store or reinforce a fix; confidence +0.10 on reinforce |
| `recall(fingerprint)` | Return `ImmunityEntry` or `None` if not found / expired |
| `decay_all()` | Apply confidence decay to all entries; evict below `min_confidence` |
| `penalize(fingerprint)` | Reduce confidence when a fix fails; evict if below threshold |
| TTL | Default 7 days; configurable |
| Decay rate | Default 0.05 per cycle; configurable |
| Min confidence | Default 0.10; entries below this are evicted |

---

### `ChaosHardenedValidator`

Fix validation under synthetic chaos conditions.

| Key capability | Detail |
|---|---|
| `validate(plan_id, category, fix_callable, test_callable)` | Run N chaos rounds; return `(passed, pass_rate)` |
| Pass threshold | ≥ 0.70 pass rate required to promote to memory |
| Pipeline integration | Uses `FailureInjectionPipeline.create_base_scenario()` when injected |
| Graceful degradation | Works without pipeline (assumes chaos pass); logs skipped injection |

---

### `CascadeAnalyzer`

Directed dependency graph tracking causal relationships between subsystem categories.

| Key capability | Detail |
|---|---|
| `record_edge(source, target)` | Create or reinforce a causal edge |
| `get_downstream(category)` | Return directly connected downstream categories |
| `check_cascade(category, health_check)` | Detect regressions in downstream after a fix |
| `get_graph_stats()` | Node count, edge count, total observed regressions |

---

### `MurphyImmuneEngine`

Main orchestrator.  Wires all components and runs the 11-phase cycle.

| Key method | Description |
|---|---|
| `run_immune_cycle(max_iterations)` | Run the full cycle; returns `ImmuneReport` |
| `set_desired_state(manifest)` | Update the reconciler manifest |
| `get_reconciler()` | Access the `DesiredStateReconciler` |
| `get_predictor()` | Access the `PredictiveFailureAnalyzer` |
| `get_memory()` | Access the `ImmunityMemory` |
| `get_chaos_validator()` | Access the `ChaosHardenedValidator` |
| `get_cascade_analyzer()` | Access the `CascadeAnalyzer` |
| `get_reports()` | Return all completed `ImmuneReport` objects |

---

## Data Models

### `DriftEvent`

| Field | Description |
|---|---|
| `drift_id` | Unique identifier (`drift-xxxxxxxx`) |
| `component` | The manifest key that drifted |
| `expected` | Value from the desired-state manifest |
| `actual` | Observed value |
| `severity` | `critical` \| `high` \| `medium` |
| `detected_at` | ISO timestamp |

---

### `PredictedFailure`

| Field | Description |
|---|---|
| `prediction_id` | Unique identifier (`pred-xxxxxxxx`) |
| `category` | Affected component category |
| `description` | Human-readable description including trend slope |
| `probability` | 0.0–1.0 probability of materializing |
| `time_horizon_seconds` | Estimated seconds until failure |
| `supporting_evidence` | List of evidence strings |
| `severity` | Derived from probability (`>0.80` = critical) |

---

### `ImmunityEntry`

| Field | Description |
|---|---|
| `entry_id` | Unique identifier (`imm-xxxxxxxx`) |
| `fingerprint` | 16-char SHA-256 prefix of `category:error_type:severity` |
| `category` | Failure category |
| `error_type` | Type of error |
| `severity` | Severity level |
| `fix_steps` | Ordered fix steps (from `FixPlan`) |
| `rollback_steps` | Steps to reverse the fix |
| `test_criteria` | Verification criteria |
| `confidence` | 0.0–1.0 decaying confidence score |
| `applications` | Number of successful applications |
| `created_at` | ISO timestamp |
| `last_applied_at` | ISO timestamp of last application |

---

### `CascadeEdge`

| Field | Description |
|---|---|
| `edge_id` | Unique identifier (`edge-xxxxxxxx`) |
| `source_category` | Category where a fix was applied |
| `target_category` | Potentially affected downstream category |
| `weight` | 0.0–1.0 causal strength |
| `observed_regressions` | Count of regressions observed after source fixes |

---

### `ImmuneReport`

Extends the `LoopReport` concept with immune-specific metrics.

| Field | Description |
|---|---|
| `report_id` | Unique identifier (`immune-xxxxxxxx`) |
| `iterations_run` | Iterations completed |
| `gaps_found` | Total gaps (including predicted) |
| `gaps_fixed` | Gaps resolved |
| `gaps_remaining` | Unresolved gaps |
| `drift_events_detected` | Reconciler drift events |
| `predicted_failures` | Failures predicted pre-emptively |
| `immunity_recalls` | Gaps resolved via ImmunityMemory fast-path |
| `chaos_validations_passed` | Fixes that survived chaos testing |
| `chaos_validations_failed` | Fixes that failed chaos testing |
| `cascade_regressions_detected` | Downstream regressions detected |
| `entries_memorized` | New fixes stored in ImmunityMemory |
| `plans_executed` | Fix plans run |
| `plans_succeeded` | Plans verified |
| `plans_rolled_back` | Plans rolled back due to failure |
| `tests_run` | Total test checks |
| `tests_passed` | Passing test checks |
| `tests_failed` | Failing test checks |
| `duration_ms` | Total cycle duration |
| `final_health_status` | `"green"` or `"yellow"` |

---

## Safety Guarantees

1. **Source files are never touched.** The engine operates exclusively at the runtime level.  Any fix that requires source changes is handled as a `code_proposal` by the underlying `SelfFixLoop` and surfaced for human review.
2. **Maximum iteration bound.** `run_immune_cycle()` terminates after `max_iterations` (default: 20) even if gaps remain.
3. **Mutex — only one cycle at a time.** A `RuntimeError` is raised if `run_immune_cycle()` is called while another cycle is active.
4. **Rollback on test failure.** If a fix's tests fail, all steps are reversed before the cycle continues.
5. **Chaos validation required.** No fix is promoted to `ImmunityMemory` without surviving chaos testing.
6. **Cascade check required.** No fix is memorized if it causes downstream regressions.
7. **Full audit trail.** Every action is published to `EventBackbone` and persisted via `PersistenceManager`.

---

## How to Use

### Programmatic API

```python
from murphy_immune_engine import MurphyImmuneEngine
from self_fix_loop import SelfFixLoop
from self_improvement_engine import SelfImprovementEngine
from self_healing_coordinator import SelfHealingCoordinator
from bug_pattern_detector import BugPatternDetector
from event_backbone import EventBackbone
from persistence_manager import PersistenceManager
from synthetic_failure_generator import FailureInjectionPipeline

engine = MurphyImmuneEngine(
    fix_loop=SelfFixLoop(
        improvement_engine=SelfImprovementEngine(),
        healing_coordinator=SelfHealingCoordinator(),
        bug_detector=BugPatternDetector(),
    ),
    event_backbone=EventBackbone(),
    persistence_manager=PersistenceManager(),
    failure_injection_pipeline=FailureInjectionPipeline(),
    desired_state={
        "recovery_procedures": 10,
        "active_bot_count": 5,
        "circuit_breaker_states": "CLOSED",
    },
    chaos_rounds=3,
)

report = engine.run_immune_cycle(max_iterations=20)
print(f"Fixed {report.gaps_fixed} gaps in {report.iterations_run} iterations")
print(f"Recalls from memory: {report.immunity_recalls}")
print(f"Chaos validations: {report.chaos_validations_passed} passed, {report.chaos_validations_failed} failed")
print(f"New entries memorized: {report.entries_memorized}")
print(f"Health: {report.final_health_status}")
```

---

## Event Reference

| Event | When published | Payload keys |
|---|---|---|
| `IMMUNE_CYCLE_STARTED` | Start of `run_immune_cycle()` | `max_iterations` |
| `DRIFT_DETECTED` | Each drift event from reconciler | `drift_id`, `component`, `expected`, `actual`, `severity` |
| `FAILURE_PREDICTED` | Each predicted failure | `prediction_id`, `category`, `probability`, `severity` |
| `IMMUNITY_RECALLED` | Gap resolved from ImmunityMemory | `gap_id`, `fingerprint`, `entry_id`, `confidence` |
| `CHAOS_VALIDATED` | After chaos hardening attempt | `plan_id`, `category`, `passed` |
| `CASCADE_CHECKED` | After cascade regression check | `category`, `regressions` |
| `IMMUNE_CYCLE_COMPLETED` | End of cycle | `report_id`, `gaps_fixed`, `gaps_remaining`, `health_status` |

---

## Example Execution Trace

```
[INFO] MurphyImmuneEngine: immune cycle started (max_iterations=20)

[PHASE 1 — RECONCILE]
  Desired: recovery_procedures=10, actual: 7 → DRIFT (high)
  Event: DRIFT_DETECTED {component: recovery_procedures, expected: 10, actual: 7}

[PHASE 2 — PREDICT]
  Category 'db' trending: slope=3.2/interval, probability=0.71
  Event: FAILURE_PREDICTED {category: db, probability: 0.71, severity: high}

[PHASE 3 — DIAGNOSE]
  3 live gaps found + 1 predicted gap (db)

[PHASE 4 — RECALL]
  gap-xyz (category=timeout, error_type=timeout_error, severity=medium):
    Fingerprint match in ImmunityMemory (confidence=0.85) → INSTANT FIX ✅
    Event: IMMUNITY_RECALLED {gap_id: gap-xyz, confidence: 0.85}

[PHASES 5–7 — PLAN → EXECUTE → TEST]
  gap-abc (category=db, error_type=connection_failed, severity=high):
    PLAN:    plan-001 — register_recovery_procedure db_connection_failed
    EXECUTE: exec-001 — recovery proc registered
    TEST:    recovery_procedure_registered → PASSED ✅

[PHASE 8 — HARDEN]
  Chaos round 1/3: PASS
  Chaos round 2/3: PASS
  Chaos round 3/3: PASS
  Pass rate: 1.00 — CHAOS HARDENED ✅
  Event: CHAOS_VALIDATED {plan_id: plan-001, passed: true}

[PHASE 9 — CASCADE CHECK]
  No downstream regressions detected ✅
  Event: CASCADE_CHECKED {category: db, regressions: []}

[PHASE 10 — MEMORIZE]
  Fix for (db, connection_failed, high) stored in ImmunityMemory ✅

[PHASE 11 — REPORT]
  gaps_found=4, gaps_fixed=3, gaps_remaining=1
  immunity_recalls=1, entries_memorized=1
  chaos_validations_passed=1, chaos_validations_failed=0
  health_status=yellow
  Event: IMMUNE_CYCLE_COMPLETED
```

---

## Comparison to SelfFixLoop (ARCH-005)

| Capability | SelfFixLoop (ARCH-005) | Murphy Immune Engine (ARCH-014) |
|---|---|---|
| Core cycle | DIAGNOSE → PLAN → EXECUTE → TEST → VERIFY → REPEAT | All of ARCH-005 **plus** 5 additional phases |
| Desired-state reconciliation | ❌ | ✅ Kubernetes-style drift detection |
| Predictive pre-healing | ❌ | ✅ Statistical trend analysis |
| Immune memory | ❌ | ✅ Instant replay for known failures |
| Chaos hardening | ❌ | ✅ Every fix stress-tested before promotion |
| Cascade detection | ❌ | ✅ Directed dependency graph |
| Cross-run learning | ❌ | ✅ ImmunityMemory persists across restarts |
| Audit | Full | Full + 7 new event types |

---

## See Also

- `docs/SELF_FIX_LOOP.md` — ARCH-005 documentation
- `ARCHITECTURE_MAP.md` — ARCH-014 entry
- `src/immune_memory.py` — ARCH-011 biological immune memory primitives
- `src/synthetic_failure_generator/` — Chaos engineering pipeline
