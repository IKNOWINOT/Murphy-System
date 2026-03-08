# Supervision Tree — ARCH-013

**Design Label:** ARCH-013 — Erlang/OTP-Inspired Supervision Tree  
**Owner:** Backend Team  
**License:** BSL 1.1

---

## Overview

The Supervision Tree provides a hierarchical fault-isolation model for the
Murphy System, inspired by **Erlang/OTP supervision trees**.  When a component
fails, its supervisor applies a bounded restart strategy, optionally backing
off exponentially and escalating unrecoverable failures up the tree.

Key design principles:

- **Crash-only design** — components are expected to fail; recovery is the
  normal path.
- **Hierarchical isolation** — failures in one subtree never cascade to
  unrelated siblings.
- **Bounded restarts** — a rolling time window prevents infinite restart
  storms.
- **Full audit trail** — every lifecycle event is published to `EventBackbone`.

---

## Architecture Diagram

```
                     ┌─────────────────────┐
                     │   Root Supervisor   │  strategy: ONE_FOR_ONE
                     │   (ARCH-013 root)   │  max_restarts: 5
                     └────────┬────────────┘
                              │ escalates to (no parent → CRITICAL)
              ┌───────────────┼────────────────────┐
              ▼               ▼                    ▼
    ┌──────────────┐  ┌──────────────┐   ┌──────────────────┐
    │ SelfFix      │  │ Bot          │   │ Coordinator      │
    │ Supervisor   │  │ Supervisor   │   │ Supervisor       │
    │ ONE_FOR_ONE  │  │ REST_FOR_ONE │   │ ONE_FOR_ALL      │
    └──────┬───────┘  └──────┬───────┘   └────────┬─────────┘
           │                 │                    │
    ┌──────▼───────┐  ┌──────▼───────┐   ┌────────▼─────────┐
    │ SelfFixLoop  │  │ BotInstance1 │   │ SelfHealing      │
    │ Improvement  │  │ BotInstance2 │   │ Coordinator      │
    │ Engine       │  │ BotInstance3 │   │ BugPattern       │
    └──────────────┘  └──────────────┘   │ Detector         │
                                         └──────────────────┘
```

---

## Restart Strategies

### ONE_FOR_ONE

Only the failed component is restarted.  All other siblings continue running
unaffected.

**Use when:** components are independent and a single component's failure
should not affect its siblings.

```
Before: [A: RUNNING] [B: FAILED] [C: RUNNING]
After:  [A: RUNNING] [B: RUNNING] [C: RUNNING]
                      ↑ restarted only
```

### ONE_FOR_ALL

When any component fails, **all** siblings are stopped and restarted in
registration order.

**Use when:** components share state and a single failure means the whole
group is in an inconsistent state.

```
Before: [A: RUNNING] [B: FAILED] [C: RUNNING]
After:  [A: RUNNING] [B: RUNNING] [C: RUNNING]
         ↑ restarted  ↑ restarted  ↑ restarted
```

### REST_FOR_ONE

The failed component and all components registered **after** it are restarted.
Components registered before the failed one are untouched.

**Use when:** components have ordered startup dependencies
(later components depend on earlier ones).

```
Registration order: [A] [B] [C] [D]
B fails →
Before: [A: RUNNING] [B: FAILED]  [C: RUNNING] [D: RUNNING]
After:  [A: RUNNING] [B: RUNNING] [C: RUNNING] [D: RUNNING]
                      ↑ restarted  ↑ restarted  ↑ restarted
```

---

## Escalation & Bounded Restarts

A `SupervisionPolicy` configures two independent escalation triggers:

1. **`max_restarts` within `time_window_sec`** — if a component restarts more
   than `max_restarts` times in the rolling window, the failure is escalated.
2. **`escalate_after` consecutive failures** — if a component fails
   consecutively `escalate_after` times without a successful restart between
   them, the failure is escalated regardless of the time window.

When escalation is triggered:

- If the supervisor has a **parent**, the failure is forwarded to the parent's
  `handle_failure`.
- If the supervisor has **no parent**, it enters `CRITICAL` state and publishes
  a `SUPERVISOR_CRITICAL` event.

---

## Exponential Backoff

Before each restart attempt, the supervisor sleeps for:

```
backoff = min(backoff_base_sec × 2^(recent_restarts − 1), backoff_max_sec)
```

The first restart of a fresh component has `recent_restarts = 0` → backoff = 0.

---

## API Reference

### `RestartStrategy` (enum)

| Member | Value | Description |
|--------|-------|-------------|
| `ONE_FOR_ONE` | `"one_for_one"` | Restart only the failed component |
| `ONE_FOR_ALL` | `"one_for_all"` | Restart all siblings |
| `REST_FOR_ONE` | `"rest_for_one"` | Restart failed + later components |

---

### `SupervisionPolicy` (dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | `RestartStrategy` | — | Restart strategy |
| `max_restarts` | `int` | `3` | Max restarts within `time_window_sec` |
| `time_window_sec` | `float` | `60.0` | Rolling window for restart counting |
| `backoff_base_sec` | `float` | `1.0` | Exponential backoff base (seconds) |
| `backoff_max_sec` | `float` | `30.0` | Maximum backoff cap (seconds) |
| `escalate_after` | `int` | `3` | Consecutive failures before escalation |

---

### `SupervisedComponent` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `component_id` | `str` | Unique component identifier |
| `component_type` | `str` | `"bot"` \| `"service"` \| `"coordinator"` \| `"engine"` |
| `start_fn` | `Callable[[], Any]` | Called to start or restart the component |
| `stop_fn` | `Callable[[], Any]` | Called to gracefully stop the component |
| `health_check_fn` | `Callable[[], bool]` | Returns `True` if the component is healthy |
| `restart_count` | `int` | Cumulative restart counter |
| `last_restart_at` | `Optional[float]` | `time.monotonic()` timestamp of the last restart |
| `status` | `ComponentStatus` | Current lifecycle status |

---

### `ComponentStatus` (enum)

| Value | Meaning |
|-------|---------|
| `RUNNING` | Component started successfully |
| `STOPPED` | Component was stopped gracefully |
| `RESTARTING` | Restart in progress |
| `FAILED` | Last start attempt failed |
| `ESCALATED` | Failure was escalated to parent supervisor |

---

### `Supervisor` (class)

```python
Supervisor(
    supervisor_id: str,
    policy: SupervisionPolicy,
    parent: Optional[Supervisor] = None,
    event_backbone: Optional[EventBackbone] = None,
)
```

#### Methods

| Method | Description |
|--------|-------------|
| `add_child(component)` | Register a `SupervisedComponent` |
| `add_child_supervisor(supervisor)` | Attach a nested child supervisor |
| `start_all()` | Start all components in registration order |
| `stop_all()` | Stop all components in reverse registration order |
| `handle_failure(component_id, error)` | Apply restart strategy; escalate if needed |
| `get_tree_status()` | Recursive health report of the entire subtree |

`handle_failure` returns a dict:

```python
{
    "supervisor_id": str,
    "strategy":      str,   # e.g. "one_for_one"
    "restarts":      Dict[str, bool],  # component_id → success
    "escalated":     bool,
    "error":         str,
}
```

---

### `SupervisionTreeBuilder` (fluent builder)

```python
tree = (
    SupervisionTreeBuilder("root")
    .with_policy(SupervisionPolicy(
        strategy=RestartStrategy.ONE_FOR_ONE,
        max_restarts=5,
        backoff_base_sec=1.0,
    ))
    .add_child(
        "self_fix_loop",
        component_type="engine",
        start_fn=lambda: self_fix_loop.start(),
        stop_fn=lambda: self_fix_loop.stop(),
        health_fn=lambda: self_fix_loop.is_healthy(),
    )
    .add_supervisor(
        "bot_supervisor",
        strategy=RestartStrategy.REST_FOR_ONE,
        children=[bot_a_component, bot_b_component],
    )
    .build()
)
```

#### Builder Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `with_policy(policy)` | `self` | Set full supervision policy |
| `with_strategy(strategy)` | `self` | Set only the restart strategy |
| `with_event_backbone(backbone)` | `self` | Attach event backbone |
| `add_child(component_id, start_fn, stop_fn, health_fn, component_type)` | `self` | Register a component |
| `add_supervisor(supervisor_id, strategy, children, policy)` | `self` | Add nested supervisor |
| `build()` | `Supervisor` | Construct and return the root supervisor |

---

## Event Types Published

All events are published to `EventBackbone` when one is provided.

| Event | When Published |
|-------|---------------|
| `SUPERVISOR_CHILD_STARTED` | A component is successfully started via `start_all()` |
| `SUPERVISOR_CHILD_STOPPED` | A component is gracefully stopped via `stop_all()` |
| `SUPERVISOR_CHILD_RESTARTED` | A component is restarted after a failure |
| `SUPERVISOR_CHILD_ESCALATED` | A failure is escalated to the parent supervisor |
| `SUPERVISOR_CRITICAL` | No parent available; entering critical state |

---

## Integration Points

| Component | Integration |
|-----------|-------------|
| `SelfFixLoop` | Register as a `SupervisedComponent` with `component_type="engine"` |
| `SelfHealingCoordinator` | Register under a `coordinator` supervisor subtree |
| `BotInventoryLibrary` | Each registered bot becomes a `SupervisedComponent` under a bot supervisor |
| `EventBackbone` | Pass to `Supervisor(event_backbone=...)` for full audit trail |
| `GovernanceKernel` | CRITICAL authority band required to modify the live supervision tree |

---

## Example: Murphy Default Tree

```python
from supervision_tree import (
    RestartStrategy,
    SupervisionPolicy,
    SupervisionTreeBuilder,
    SupervisedComponent,
)
from event_backbone import EventBackbone
from self_fix_loop import SelfFixLoop
from self_healing_coordinator import SelfHealingCoordinator

backbone = EventBackbone()
fix_loop = SelfFixLoop()
coordinator = SelfHealingCoordinator()

root = (
    SupervisionTreeBuilder("murphy_root")
    .with_event_backbone(backbone)
    .with_policy(SupervisionPolicy(
        strategy=RestartStrategy.ONE_FOR_ONE,
        max_restarts=5,
        time_window_sec=120.0,
        backoff_base_sec=1.0,
        backoff_max_sec=30.0,
        escalate_after=3,
    ))
    .add_child(
        "self_fix_loop",
        component_type="engine",
        start_fn=fix_loop.start,
        stop_fn=fix_loop.stop,
        health_fn=lambda: True,
    )
    .add_supervisor(
        "coordinator_supervisor",
        strategy=RestartStrategy.ONE_FOR_ALL,
        children=[
            SupervisedComponent(
                component_id="self_healing_coordinator",
                component_type="coordinator",
                start_fn=coordinator.start,
                stop_fn=coordinator.stop,
                health_check_fn=lambda: True,
            ),
        ],
    )
    .build()
)

root.start_all()
```

---

*Copyright © 2020 Inoni Limited Liability Company — License: BSL 1.1*
