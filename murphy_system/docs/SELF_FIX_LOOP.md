# Self-Fix Loop — ARCH-005

**Design Label:** ARCH-005 — Autonomous Self-Fix Loop  
**Owner:** Backend Team  
**Module:** `src/self_fix_loop.py`  
**Tests:** `tests/test_self_fix_loop.py`

---

## Overview

The Self-Fix Loop is Murphy System's autonomous closed-loop remediation engine. It detects problems, generates structured plans, executes runtime fixes, tests the outcome, and repeats until no gaps remain.

> **"Make a plan to fill the gap with context. Perform that plan. Then perform testing that shows the object's purpose is successfully being performed in all versions of its uses and the gaps it closes are provenly being closed. Repeat until there are no errors, gaps, bugs, problems, missing documentation, or documentation updates needed."**

---

## How the Loop Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-FIX LOOP                                │
│                                                                 │
│  1. DIAGNOSE  → Scan system for errors/gaps/bugs               │
│  2. PLAN      → Generate structured remediation plan            │
│  3. EXECUTE   → Apply fixes (config, thresholds, recovery)     │
│  4. TEST      → Run targeted tests proving the fix works       │
│  5. VERIFY    → Confirm gap is closed, no regressions          │
│  6. REPEAT    → If gaps remain, go to step 1                   │
│  7. REPORT    → Generate final verification report             │
└─────────────────────────────────────────────────────────────────┘
```

Each iteration processes all outstanding gaps in priority order (critical → high → medium → low). Plans that fail testing are automatically rolled back before moving to the next gap.

---

## What Types of Fixes Are Applied Autonomously

| `fix_type` | What it does | Example |
|---|---|---|
| `threshold_tuning` | Adjusts timeout values or confidence thresholds at runtime | Increase `timeout_seconds` for `api_call` tasks from 60 to 90 |
| `recovery_registration` | Registers a new `RecoveryProcedure` with `SelfHealingCoordinator` | Add automatic DB connection retry for `database_failure` category |
| `route_optimization` | Updates routing weights based on outcome data | Switch `ml_inference` tasks to `deterministic` route after high success rate |
| `config_adjustment` | Modifies any runtime configuration key | Adjust retry count, backoff multiplier, etc. |

---

## What Requires Human Review

| `fix_type` | Why it is not auto-applied |
|---|---|
| `code_proposal` | Any fix that would require modifying Python source files, logic, or algorithms is persisted as a proposal and **requires human approval**. |

Code proposals are saved to `PersistenceManager` with `type: "code_proposal"` and surfaced in the remediation backlog. The loop still reports them as "handled" — they are just not autonomously applied.

---

## Safety Guarantees

1. **Source files are never touched.** The loop operates exclusively at the runtime level.
2. **Maximum iteration bound.** The loop terminates after `max_iterations` (default: 10) even if gaps remain.
3. **Mutex — only one loop at a time.** A `RuntimeError` is raised if `run_loop()` is called while another run is active.
4. **Rollback on failure.** If a plan's tests fail, all steps are reversed using `rollback_steps` before proceeding.
5. **No regressions tolerated.** The `test()` step scans for regressions (invalid config values, out-of-range thresholds). Any regression causes the plan to be rolled back.
6. **Full audit trail.** Every `FixPlan`, `FixExecution`, and `LoopReport` is persisted and published as events to `EventBackbone`.

---

## How to Trigger the Loop

### Programmatic API

```python
from self_fix_loop import SelfFixLoop
from self_improvement_engine import SelfImprovementEngine
from self_healing_coordinator import SelfHealingCoordinator
from bug_pattern_detector import BugPatternDetector
from event_backbone import EventBackbone
from persistence_manager import PersistenceManager

loop = SelfFixLoop(
    improvement_engine=SelfImprovementEngine(),
    healing_coordinator=SelfHealingCoordinator(),
    bug_detector=BugPatternDetector(),
    event_backbone=EventBackbone(),
    persistence_manager=PersistenceManager(),
)

report = loop.run_loop(max_iterations=10)
print(f"Fixed {report.gaps_fixed} gaps in {report.iterations_run} iterations")
print(f"Remaining: {report.gaps_remaining}, Health: {report.final_health_status}")
```

### REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/self-fix/run` | Trigger the self-fix loop |
| `GET` | `/api/self-fix/status` | Get current loop status |
| `GET` | `/api/self-fix/history` | Get past loop reports |
| `GET` | `/api/self-fix/plans` | Get all fix plans with their status |

---

## Data Models

### `Gap`
Describes a known issue found during diagnosis.

| Field | Description |
|---|---|
| `gap_id` | Unique identifier |
| `description` | Human-readable description of the problem |
| `source` | `"bug_detector"` \| `"improvement_engine"` \| `"health_check"` |
| `severity` | `"critical"` \| `"high"` \| `"medium"` \| `"low"` |
| `category` | Affected component or task type |
| `proposal_id` | Link to `ImprovementProposal` if from improvement engine |

### `FixPlan`
A structured remediation plan for a specific gap.

| Field | Description |
|---|---|
| `plan_id` | Unique identifier |
| `gap_description` | What is broken |
| `fix_type` | Type of fix |
| `fix_steps` | Ordered list of atomic steps to execute |
| `rollback_steps` | Steps to reverse if the plan fails |
| `expected_outcome` | What success looks like |
| `test_criteria` | How to verify the fix |
| `status` | `planned` → `executing` → `testing` → `verified` \| `failed` \| `rolled_back` |

### `FixExecution`
Records the runtime execution of a `FixPlan`.

| Field | Description |
|---|---|
| `execution_id` | Unique identifier |
| `step_results` | Result of each executed step |
| `tests_run` | Test name, passed/failed, output |
| `gaps_before` | Gap IDs present before fix |
| `gaps_after` | Gap IDs remaining after fix |
| `regressions` | New issues introduced by the fix |
| `status` | `pending` \| `success` \| `partial` \| `failed` \| `rolled_back` |

### `LoopReport`
Final report produced by a completed self-fix loop run.

| Field | Description |
|---|---|
| `report_id` | Unique identifier |
| `iterations_run` | Total iterations completed |
| `gaps_found` | Total gaps discovered |
| `gaps_fixed` | Gaps successfully resolved |
| `gaps_remaining` | Gaps not yet resolved |
| `plans_executed` | Total plans run |
| `plans_succeeded` | Plans that passed verification |
| `plans_rolled_back` | Plans that were rolled back due to failure |
| `tests_run` | Total test checks evaluated |
| `tests_passed` | Test checks that passed |
| `tests_failed` | Test checks that failed |
| `duration_ms` | Total loop duration in milliseconds |
| `final_health_status` | `"green"` (no gaps) \| `"yellow"` (some remain) |

---

## Example Loop Execution Trace

```
[INFO] SelfFixLoop started (max_iterations=10)

[ITERATION 1]
  DIAGNOSE:  3 gaps found
    - gap-prop-abc123  (high)    Timeout cluster in 'api_call' (4 occurrences)
    - gap-bug-def456   (medium)  Connection timeout on database call
    - gap-prop-ghi789  (low)     Success pattern in 'deploy' (avg 2.3s)

  Processing gap-prop-abc123 (threshold_tuning):
    PLAN:    plan-xyz — adjust_timeout api_call +30s
    EXECUTE: exec-uvw — timeout_seconds:api_call 60 → 90
    TEST:    timeout_errors_reduced:api_call → PASSED
    VERIFY:  gap-prop-abc123 no longer in diagnose → VERIFIED ✅

  Processing gap-bug-def456 (recovery_registration):
    PLAN:    plan-pqr — register_recovery_procedure db_timeout
    EXECUTE: exec-stu — registered auto-proc-xxx for 'db_timeout'
    TEST:    recovery_procedure_registered:db_timeout → PASSED
    VERIFY:  gap-bug-def456 no longer in diagnose → VERIFIED ✅

  Processing gap-prop-ghi789 (code_proposal):
    PLAN:    plan-mno — human_review (code_proposal)
    EXECUTE: exec-jkl — persisted as code-proposal-yyy
    TEST:    proposal_logged_for_review → PASSED
    VERIFY:  logged → VERIFIED ✅

[ITERATION 2]
  DIAGNOSE:  0 gaps found → DONE

[REPORT]
  Iterations: 2, Gaps Fixed: 3, Remaining: 0
  Plans: 3 executed, 3 succeeded, 0 rolled back
  Tests: 3 run, 3 passed, 0 failed
  Health: green ✅
```

---

## Integration Points

| Component | How it is used |
|---|---|
| `SelfImprovementEngine.get_remediation_backlog()` | Sources gaps from pending proposals |
| `SelfImprovementEngine.generate_executable_fix()` | Converts proposals into structured `FixPlan` steps |
| `SelfImprovementEngine.get_confidence_calibration()` | Supplies calibrated threshold values for `recalibrate_confidence` steps |
| `BugPatternDetector.run_detection_cycle()` | Triggers fresh bug pattern analysis during `diagnose()` |
| `BugPatternDetector.get_patterns()` | Converts detected patterns into `Gap` objects |
| `SelfHealingCoordinator.register_procedure()` | Registers auto-generated recovery handlers |
| `EventBackbone.publish_event()` | Publishes all lifecycle events for audit and observability |
| `PersistenceManager.save_document()` | Durably stores plans, executions, and reports |

---

## Event Reference

All events are published to `EventBackbone` using the following `EventType` values:

| Event | When published |
|---|---|
| `SELF_FIX_STARTED` | At the start of `run_loop()` |
| `SELF_FIX_PLAN_CREATED` | When a `FixPlan` is generated for a gap |
| `SELF_FIX_EXECUTED` | After `execute()` completes |
| `SELF_FIX_TESTED` | After `test()` completes |
| `SELF_FIX_VERIFIED` | After `verify()` completes |
| `SELF_FIX_COMPLETED` | At the end of `run_loop()` with the final report |
| `SELF_FIX_ROLLED_BACK` | When a plan's rollback is triggered |


---

## MMSMMS Cadence in Setup Retries

The `EnvironmentSetupAgent` applies a specialised **Magnify→Magnify→Simplify→Magnify→Magnify→Solidify** cadence
to its retry loop every 3rd attempt.  This prevents the retry loop from repeatedly attempting the same failing
approach and instead generates a qualitatively different fix strategy using root-cause analysis.

### Cadence Pattern

```
Attempt 1  →  Normal retry (probe → plan → execute → verify)
Attempt 2  →  Normal retry
Attempt 3  →  MMSMMS cadence:
               M1: Magnify — gather full failure context, OS state, cascade effects
               M2: Magnify — deepen: find prerequisite gaps, OS quirks, port conflicts
               S:  Simplify — distil to single root cause
               M3: Magnify — expand solution space given root cause
               M4: Magnify — rank solutions by reliability, invasiveness, speed
               S:  Solidify — emit a concrete SetupPlan targeting the root cause
Attempt 4  →  Normal retry (using the amplified plan)
Attempt 5  →  Normal retry
Attempt 6  →  MMSMMS cadence again  …
```

### Implementation

| File | Role |
|---|---|
| `src/setup_retry_amplifier.py` | `SetupRetryAmplifier` — standalone MMSMMS engine |
| `src/environment_setup_agent.py` | `EnvironmentSetupAgent.execute_and_verify()` — triggers cadence every 3rd retry |
| `tests/test_setup_retry_amplifier.py` | Full test coverage for all 6 phases and integration |

### Confidence Thresholds

All phase gates use thresholds aligned with the MFGC system:

| Gate | Threshold | Effect if not met |
|---|---|---|
| `CONFIDENCE_EXPAND` | 0.30 | Cadence aborted — fall back to normal retry |
| `CONFIDENCE_CONSTRAIN` | 0.65 | Cadence aborted after Simplify — fall back to normal retry |
| `CONFIDENCE_EXECUTE` | 0.85 | Solidified plan rejected — fall back to normal retry |

### Design Guarantees

- **HITL preserved:** every amplified plan goes through `HITLApprovalGate.approve_all()` before execution
- **Bounded:** `max_attempts` is always respected — the cadence never extends the loop
- **Thread-safe:** the amplifier shares the agent's `_audit_log` list with capped appends
- **LLM-free:** all phase reasoning is structural (pattern-matching), no external API key required
- **Full audit trail:** every amplification phase is logged with phase name, confidence, and timestamp
