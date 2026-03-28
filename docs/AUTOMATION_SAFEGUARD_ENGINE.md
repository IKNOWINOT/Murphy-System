# Automation Safeguard Engine — Module Documentation

**Design Label:** AUTO-SAFE-001  
**Version:** 1.0.0  
**Owner:** Platform Engineering  
**Status:** ✅ Implemented  
**Date:** 2026-03-17  

---

## Table of Contents

1. [Executive Summary — Recommendations](#1-executive-summary--recommendations)
2. [Problem Analysis — 7 Automation Failure Modes](#2-problem-analysis--7-automation-failure-modes)
3. [Implementation Plan](#3-implementation-plan)
4. [Guard Reference](#4-guard-reference)
5. [Integration Map — Where Guards Are Wired](#5-integration-map--where-guards-are-wired)
6. [Usage Guide](#6-usage-guide)
7. [Configuration Reference](#7-configuration-reference)
8. [Observability](#8-observability)
9. [Testing](#9-testing)
10. [Adoption Roadmap](#10-adoption-roadmap)

---

## 1. Executive Summary — Recommendations

Based on analysis of Murphy System's automation layer, combined with industry research
(Google SRE Book on cascading failures, Netflix Chaos Engineering, NIST industrial
automation literature), we identified **seven recurring failure modes** that account for
nearly all automation system collapses:

| # | Failure Mode | Root Cause | Murphy Risk Areas |
|---|---|---|---|
| 1 | **Runaway loop / Infinite regeneration** | Missing iteration cap or wall-clock bound | `AutomationLoopConnector.run_cycle()`, `SelfFixLoop`, `ChaosResilienceLoop`, proposal generators |
| 2 | **Event storm / Flood** | Missing rate limit or debounce on event ingestion | `RecipeEngine.process_event()`, webhook receivers, EventBackbone subscribers |
| 3 | **Feedback oscillation** | Over-correcting control loop | `ConfidenceEngine`, `SelfImprovementEngine` reward updates, any PID-style feedback |
| 4 | **Cascade failure** | Upstream failure propagates to all dependents | Cross-service calls, API gateway, bot orchestration dependencies |
| 5 | **Duplicate / Double-trigger** | No idempotency on event processing | `RecipeEngine.process_event()`, webhook handlers, task creation from proposals |
| 6 | **Tracking accumulation / Memory leak** | Unbounded collections that grow without eviction | `_execution_log`, `_cycle_history`, `_audit_log`, proposal tracking sets |
| 7 | **Deadlock / Starvation** | Circular lock acquisition or uncapped wait time | Multi-threaded bot coordination, shared resource locks |

### Key Recommendations

1. **Wire RunawayLoopGuard into `AutomationLoopConnector.run_cycle()`** — the inner loops
   over `pending_outcomes` and `proposals` must have hard caps to prevent infinite processing
   if the upstream engines malfunction.

2. **Wire EventStormSuppressor into `RecipeEngine.process_event()`** — the existing per-recipe
   rate limiter uses a simple timestamp list with no cross-recipe global budget.  The
   `EventStormSuppressor` adds a global sliding window + per-key debounce.

3. **Wire IdempotencyGuard into `RecipeEngine.process_event()`** — the same event can trigger
   the same recipe multiple times if the event backbone redelivers.  A SHA-256 content hash
   with TTL prevents double-execution of actions.

4. **Register all mutable collections with `TrackingAccumulationWatcher`** — specifically
   `RecipeEngine._log`, `AutomationLoopConnector._cycle_history`, and
   `AutomationLoopConnector._pending_outcomes`.

5. **Surface safeguard health via `check_all()`** — integrate into the existing Murphy
   health-check endpoint so operators can see guard status alongside system health.

6. **Add oscillation monitoring to confidence-sensitive loops** — any loop that records
   and responds to `ConfidenceEngine` scores should pass those scores to
   `FeedbackOscillationDetector` to catch runaway reward hacking.

7. **Register cross-service dependencies in `CascadeBreaker`** — API calls from Murphy
   to external providers (Stripe, SendGrid, DeepInfra) should register dependency chains so a
   single provider outage does not cascade through unrelated workflows.

---

## 2. Problem Analysis — 7 Automation Failure Modes

### 2.1 Runaway Loops

**Symptom:** A loop that should terminate in O(n) iterations runs indefinitely,
consuming CPU, creating proposals faster than they can be consumed, or regenerating
the same work in a tight loop.

**Murphy-specific risk:**  
`AutomationLoopConnector.run_cycle()` iterates over `_pending_outcomes` and `proposals`.
If `SelfImprovementEngine.generate_proposals()` returns an unbounded list (e.g., due to
a pattern-extraction bug), the inner for-loop will process all of them in a single cycle
and attempt to create orchestrator tasks for each.  Under sustained event load this can
overwhelm the orchestrator queue.

**Solution:** `RunawayLoopGuard` — hard iteration cap + wall-clock timeout kill switch.

```python
with safeguard.loop_guard("run_cycle_proposals", max_iterations=500, max_seconds=30.0):
    for prop in proposals:
        safeguard.loop_guard("run_cycle_proposals").tick()
        # ... create task
```

### 2.2 Event Storms

**Symptom:** A burst of events (webhook retry storm, timer tick accumulation,
EventBackbone fan-out) overwhelms the processing pipeline, causing cascading timeouts.

**Murphy-specific risk:**  
`RecipeEngine.process_event()` iterates all active recipes for every event.
Under a storm of identical events (e.g., Monday.com status column updated 200×/sec),
each recipe fires 200 times per second.  The existing per-recipe rate limiter only
controls per-recipe frequency, not the global event rate.

**Solution:** `EventStormSuppressor` — global sliding-window rate + per-key debounce.

### 2.3 Feedback Oscillation

**Symptom:** A feedback control loop oscillates: action A increases a metric, which
triggers action B to decrease it, which triggers A again — never converging.

**Murphy-specific risk:**  
Any loop that reads a confidence score and adjusts behaviour based on it can enter
oscillation if the confidence delta is large and the adjustment overshoot is not damped.

**Solution:** `FeedbackOscillationDetector` — sign-change count on delta series, fires
callback when oscillation threshold is exceeded.

### 2.4 Cascade Failures

**Symptom:** Component A fails, causing B (which depends on A) to also fail, which
causes C to fail — the "domino effect".

**Murphy-specific risk:**  
Murphy's bot orchestration layer has inter-bot dependencies.  If the `TaskExecutor`
fails, bots that depend on task results queue up indefinitely.

**Solution:** `CascadeBreaker` — dependency graph with blast-radius cap (`max_open`).

### 2.5 Duplicate / Double-Trigger

**Symptom:** The same action is executed multiple times because the same triggering
event is delivered more than once (at-least-once delivery semantics).

**Murphy-specific risk:**  
`RecipeEngine.process_event()` processes every event it receives.  EventBackbone
guarantees at-least-once delivery.  A Stripe webhook retry will fire the billing
action twice unless there is content-hash deduplication.

**Solution:** `IdempotencyGuard` — SHA-256 content hash + TTL eviction.

### 2.6 Tracking Accumulation

**Symptom:** A list or dict grows without bound because items are added but never
evicted.  Eventually the process runs out of memory.

**Murphy-specific risk:**  
`RecipeEngine._log` and `AutomationLoopConnector._cycle_history` are capped by
`capped_append`, but `_pending_outcomes` can accumulate if `run_cycle()` is never
called.  Custom recipe action handlers may also maintain state that grows unboundedly.

**Solution:** `TrackingAccumulationWatcher` — register collections by size-callable,
alert after N consecutive growth checks exceed a threshold.

### 2.7 Deadlock / Starvation

**Symptom:** Two threads each hold a lock the other needs — neither can proceed.
Or a thread waits for a lock indefinitely because the holder never releases it.

**Murphy-specific risk:**  
Multi-threaded bot coordination (SplitScreenManager, MultiCursorDesktop) acquires
multiple shared-resource locks.  If acquisition order is inconsistent, a cycle forms.

**Solution:** `DeadlockDetector` — DFS wait-for graph cycle detection + starvation
timeout.

---

## 3. Implementation Plan

The integration was completed in two stages:

### Stage 1 — Core Guards Built (AUTO-SAFE-001 v1.0.0)

✅ `src/automation_safeguard_engine.py` — All 7 guard primitives implemented.  
✅ `tests/test_automation_safeguard_engine.py` — 94 tests covering all guards + scenarios.  
✅ 3 Murphy commands registered: `/safeguard status`, `/safeguard check`, `/safeguard reset`.

### Stage 2 — Wired into Production Automation Loops

✅ `src/automation_loop_connector.py` — `RunawayLoopGuard` + `IdempotencyGuard` wired:
  - `run_cycle()` proposal-to-task loop bounded by `RunawayLoopGuard("run_cycle_proposals")`
  - `_pending_outcomes` processing bounded by `RunawayLoopGuard("run_cycle_outcomes")`
  - `_tracked_proposals` idempotency checked via `IdempotencyGuard`
  - `_pending_outcomes` registered with `TrackingAccumulationWatcher`

✅ `src/management_systems/automation_recipes.py` — `EventStormSuppressor` + `IdempotencyGuard` wired:
  - `process_event()` passes through global `EventStormSuppressor` before any recipe matching
  - Event idempotency checked per (recipe_id, event_hash) before action execution
  - `_log` registered with `TrackingAccumulationWatcher`

✅ `tests/test_safeguard_integration.py` — Integration tests for wired guards.

---

## 4. Guard Reference

### 4.1 RunawayLoopGuard

Prevents runaway loops and infinite regeneration.

| Parameter | Default | Description |
|---|---|---|
| `name` | required | Identifier for the guard instance |
| `max_iterations` | `1_000` | Hard iteration cap |
| `max_seconds` | `60.0` | Wall-clock timeout in seconds |
| `on_runaway` | `None` | Callback `(name, reason) -> None` |

**Raises:** `RunawayLoopError` (subclass of `RuntimeError`) when either cap is exceeded.

**Context manager usage:**
```python
guard = RunawayLoopGuard("proposals", max_iterations=500, max_seconds=30.0)
with guard:
    for item in items:
        guard.tick()
        process(item)
```

### 4.2 EventStormSuppressor

Prevents event storms and floods via sliding-window rate limit + debounce.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `max_per_window` | `200` | Max events allowed per `window_sec` |
| `window_sec` | `1.0` | Sliding window duration in seconds |
| `debounce_sec` | `0.05` | Min interval between same-key events |
| `on_storm` | `None` | Callback `(name, detail) -> None` |

**Usage:**
```python
suppressor = EventStormSuppressor("recipe_events", max_per_window=100)
if suppressor.allow(event_key):
    process_event(event)
```

### 4.3 FeedbackOscillationDetector

Detects over-correcting control loops via sign-change count on delta series.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `window` | `20` | Number of recent samples to analyse |
| `max_sign_changes` | `6` | Threshold for oscillation detection |
| `on_oscillation` | `None` | Callback `(name, rate) -> None` |

**Usage:**
```python
detector = FeedbackOscillationDetector("confidence_pid", window=20)
detector.record(confidence_score)
if detector.is_oscillating():
    apply_damping()
```

### 4.4 CascadeBreaker

Dependency-aware circuit breaker with blast-radius cap.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `trip_ratio` | `0.5` | Failure ratio that opens the breaker |
| `window_sec` | `60.0` | Rolling window for failure counting |
| `reset_sec` | `30.0` | Half-open cooldown after opening |
| `max_open` | `10` | Max breakers open simultaneously |
| `on_trip` | `None` | Callback `(component, opened_list) -> None` |

**Usage:**
```python
breaker = CascadeBreaker("services")
breaker.register("stripe_api", depends_on=["billing"])
breaker.record_failure("stripe_api")
if breaker.is_open("billing"):
    use_fallback()
```

### 4.5 IdempotencyGuard

SHA-256 content-hash deduplication with TTL eviction.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `ttl_sec` | `300.0` | Time-to-live for seen hashes (seconds) |
| `max_cache` | `10_000` | Max cached hashes before eviction |

**Usage:**
```python
guard = IdempotencyGuard("webhooks", ttl_sec=300.0)
if guard.is_new(event_payload):
    execute_action(event_payload)
```

### 4.6 TrackingAccumulationWatcher

Monitors collection growth, alerts on unbounded accumulation.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `growth_threshold_pct` | `10.0` | % growth per check to consider "growing" |
| `alert_after_n_checks` | `3` | Consecutive growth checks before alert |
| `on_accumulation` | `None` | Callback `(collection_name, msg) -> None` |

**Usage:**
```python
watcher = TrackingAccumulationWatcher("recipe_engine")
watcher.register("execution_log", lambda: len(engine._log), max_size=10_000)
watcher.check()  # call periodically
```

### 4.7 DeadlockDetector

DFS wait-for graph cycle detection + lock-hold starvation timeout.

| Parameter | Default | Description |
|---|---|---|
| `name` | `"default"` | Identifier |
| `starvation_timeout_sec` | `30.0` | Max wait time before starvation alert |
| `on_deadlock` | `None` | Callback `(name, cycle) -> None` |

**Usage:**
```python
detector = DeadlockDetector("bot_resources")
detector.acquire("trading_bot", "market_feed")
detector.acquire("compliance_bot", "audit_queue")
if detector.has_deadlock():
    detector.emergency_release_all()
```

---

## 5. Integration Map — Where Guards Are Wired

```
AutomationSafeguardEngine (singleton: get_engine())
│
├── automation_loop_connector.AutomationLoopConnector
│   ├── run_cycle() / proposal loop ──── RunawayLoopGuard("run_cycle_proposals")
│   ├── run_cycle() / outcomes loop ──── RunawayLoopGuard("run_cycle_outcomes")
│   ├── _tracked_proposals ──────────── IdempotencyGuard("loop_proposals")
│   └── _pending_outcomes ───────────── TrackingAccumulationWatcher (registered)
│
└── management_systems.automation_recipes.RecipeEngine
    ├── process_event() ─────────────── EventStormSuppressor("recipe_events")
    ├── process_event() per recipe ──── IdempotencyGuard("recipe_events")
    └── _log ────────────────────────── TrackingAccumulationWatcher (registered)
```

### Not Yet Wired (Adoption Roadmap)

| Module | Recommended Guard | Priority |
|---|---|---|
| `self_fix_loop.SelfFixLoop` | `RunawayLoopGuard` | High |
| `chaos_resilience_loop.ChaosResilienceLoop` | `RunawayLoopGuard` (augments `max_experiments`) | Medium |
| `self_improvement_engine` | `FeedbackOscillationDetector` on confidence deltas | Medium |
| `bot_governance_policy_mapper` | `CascadeBreaker` for bot dependency chains | Medium |
| `autonomous_repair_system` | `TrackingAccumulationWatcher` for repair queue | Low |
| `event_backbone` | `EventStormSuppressor` on publish() | Low |

---

## 6. Usage Guide

### 6.1 Accessing the Singleton

```python
from automation_safeguard_engine import get_engine

safeguard = get_engine()
```

The singleton is module-scoped and thread-safe.  All guards share state across
the lifetime of the process.

### 6.2 Full Health Check

```python
health = safeguard.check_all()
# {
#   "module": "automation_safeguard_engine",
#   "healthy": True,
#   "guards": {
#     "event_storm": {...},
#     "cascade_breaker": {"open_count": 0, ...},
#     "idempotency": {"blocked_count": 12, ...},
#     ...
#   },
#   "accumulation_alerts": [],
#   "starvation_alerts": []
# }
```

### 6.3 Murphy Commands

| Command | Description |
|---|---|
| `/safeguard status` | Get status dict for all 7 guards |
| `/safeguard check` | Run `check_all()` and return health dict |
| `/safeguard reset [loop\|cascade\|deadlock\|idempotency\|all]` | Reset guard state (operator role required) |

### 6.4 Event Storm Protection in Custom Webhooks

```python
from automation_safeguard_engine import get_engine

safeguard = get_engine()

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.json()
    
    # 1. Rate / debounce
    if not safeguard.event_storm.allow("stripe_webhook"):
        return {"status": "rate_limited"}
    
    # 2. Idempotency
    if not safeguard.idempotency.is_new(payload):
        return {"status": "duplicate_suppressed"}
    
    # 3. Process
    handle_stripe_event(payload)
    return {"status": "ok"}
```

### 6.5 Runaway Loop Protection

```python
from automation_safeguard_engine import get_engine, RunawayLoopError

safeguard = get_engine()

def generate_proposals_bounded(engine):
    try:
        proposals = engine.generate_proposals()
        guard = safeguard.loop_guard("proposal_gen", max_iterations=500)
        with guard:
            for prop in proposals:
                guard.tick()
                create_task(prop)
    except RunawayLoopError as exc:
        logger.error("Proposal generation loop tripped: %s", exc)
        # alert, emit metric, etc.
```

---

## 7. Configuration Reference

All defaults can be overridden when constructing a custom `AutomationSafeguardEngine`:

```python
from automation_safeguard_engine import AutomationSafeguardEngine

safeguard = AutomationSafeguardEngine(
    loop_max_iterations=2_000,        # default: 1_000
    loop_max_seconds=120.0,           # default: 60.0
    storm_max_per_window=500,         # default: 200
    storm_window_sec=1.0,             # default: 1.0
    storm_debounce_sec=0.1,           # default: 0.05
    osc_window=30,                    # default: 20
    osc_max_sign_changes=8,           # default: 6
    cb_trip_ratio=0.6,                # default: 0.5
    cb_window_sec=120.0,              # default: 60.0
    cb_reset_sec=60.0,                # default: 30.0
    cb_max_open=5,                    # default: 10
    idem_ttl_sec=600.0,               # default: 300.0
    accum_growth_threshold_pct=20.0,  # default: 10.0
    accum_alert_after_n_checks=5,     # default: 3
    deadlock_starvation_timeout_sec=60.0,  # default: 30.0
)
```

---

## 8. Observability

### 8.1 Logging

All guards emit structured log records:

| Level | Guard | Event |
|---|---|---|
| `WARNING` | RunawayLoopGuard | Loop tripped (iteration cap or timeout) |
| `DEBUG` | EventStormSuppressor | Each blocked event |
| `WARNING` | FeedbackOscillationDetector | Oscillation detected |
| `WARNING` | CascadeBreaker | Breaker opened; cascade propagation |
| `DEBUG` | IdempotencyGuard | Duplicate suppressed |
| `WARNING` | TrackingAccumulationWatcher | Growth threshold exceeded |
| `ERROR` | DeadlockDetector | Deadlock cycle detected |
| `WARNING` | DeadlockDetector | Starvation timeout exceeded |

### 8.2 Metrics Integration

All guards expose `get_status() -> Dict[str, Any]`.  The top-level `check_all()` 
aggregates all guard statuses in a single call suitable for periodic scraping:

```python
# Prometheus-style integration (example)
status = safeguard.get_status()
metrics["safeguard_event_storm_blocked"] = status["event_storm_blocked"]
metrics["safeguard_cascade_open_count"] = status["cascade_open"]
metrics["safeguard_idempotency_blocked"] = status["idempotency_blocked"]
metrics["safeguard_loop_guard_trips"] = status["loop_guard_trips"]
metrics["safeguard_deadlock_count"] = status["deadlock_count"]
```

---

## 9. Testing

### 9.1 Unit Tests

`tests/test_automation_safeguard_engine.py` — 94 tests:

- All 7 guards tested individually with edge cases
- Boundary conditions (exact iteration cap, TTL expiry, debounce window)
- Callback firing verified
- Thread-safety tests (5 concurrent-access scenarios)
- Automation-type scenario tests (3D printer PID, Stripe webhook double-charge,
  email storm, multi-bot deadlock, proposal regeneration loop)
- Command registry integration (3 tests)

### 9.2 Integration Tests

`tests/test_safeguard_integration.py` — validates guards wired into
`AutomationLoopConnector` and `RecipeEngine`.

### 9.3 Temporal Variation Tests

`tests/test_regulation_temporal_variations.py` — 170 tests validating the
`AutomationSafeguardEngine` temporal behaviour across 12 business archetypes × 5
growth stages each (see `docs/REGULATION_ML_ENGINE.md`).

---

## 10. Adoption Roadmap

### Phase 1 — Completed ✅

- [x] All 7 guard primitives built (`src/automation_safeguard_engine.py`)
- [x] `AutomationLoopConnector` wired with `RunawayLoopGuard` + `IdempotencyGuard`
- [x] `RecipeEngine` wired with `EventStormSuppressor` + `IdempotencyGuard`
- [x] 94 unit tests + integration tests passing
- [x] 3 Murphy commands registered

### Phase 2 — Recommended Next Steps

- [ ] Wire `RunawayLoopGuard` into `SelfFixLoop.run()` (bounded gap-fix iteration)
- [ ] Wire `FeedbackOscillationDetector` into `ConfidenceEngine` update path
- [ ] Wire `CascadeBreaker` into bot governance policy mapper
- [ ] Register `TrackingAccumulationWatcher` for all audit logs system-wide
- [ ] Expose `check_all()` via `/api/system/health` route extension

### Phase 3 — Long-Term

- [ ] Persist guard state across restarts (immune memory style)
- [ ] ML-based adaptive threshold tuning (integrate with `RegulationMLEngine`)
- [ ] Distributed guard state for multi-node deployments
- [ ] Grafana dashboard template for all guard metrics

---

*Auto-generated from `src/automation_safeguard_engine.py` v1.0.0*  
*Copyright © 2020 Inoni Limited Liability Company — BSL 1.1*
