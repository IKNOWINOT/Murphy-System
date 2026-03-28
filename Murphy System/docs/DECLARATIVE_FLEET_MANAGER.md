# Declarative Fleet Manager

> Copyright © 2020 Inoni Limited Liability Company — License: BSL 1.1

Murphy System's **Declarative Fleet Manager** brings a Kubernetes-inspired
desired-state reconciliation model to the bot ecosystem.  Instead of imperatively
calling spawn/despawn APIs, you declare an entire fleet in a single YAML or JSON
manifest and let the `FleetReconciler` continuously converge actual state to match.

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Manifest Format Reference](#manifest-format-reference)
4. [Reconciliation Loop](#reconciliation-loop)
5. [Integration Guide](#integration-guide)
6. [Drift Detection](#drift-detection)
7. [Events Published](#events-published)
8. [Example: 5-Bot Fleet](#example-5-bot-fleet)
9. [API Reference](#api-reference)

---

## Overview

```
FleetManifest (YAML/JSON)
        │
        ▼
  ManifestLoader ──validate──► ManifestValidationError
        │
        ▼
  FleetReconciler
    ├── observe()          ← snapshot from BotInventoryLibrary
    ├── diff()             ← compare desired vs actual → [ReconciliationAction]
    └── reconcile()        ← execute actions (spawn / despawn / update / ...)
```

The `FleetDriftDetector` can be wired into any heartbeat tick cycle to continuously
monitor for out-of-band changes and publish `FLEET_DRIFT_DETECTED` events.

---

## Design Principles

| Principle | How it is enforced |
|---|---|
| **Declarative** | You declare what you want; the reconciler figures out how |
| **Idempotent** | Running `reconcile()` multiple times with the same manifest produces the same result |
| **Dependency-ordered startup** | Topological sort ensures dependencies start before dependents |
| **Full audit trail** | Every action publishes an event to `EventBackbone` |
| **Compatible with GovernanceKernel** | `governance.authority_band` in the manifest maps to authority band checks |

---

## Manifest Format Reference

```yaml
# ── Top-level fields ────────────────────────────────────────────────────────
fleet_id: "my_fleet"          # Unique identifier for this fleet
version: "1.0"                # Manifest schema version
description: "My fleet"       # Human-readable description
created_at: "2026-01-01T00:00:00+00:00"
updated_at: "2026-03-08T00:00:00+00:00"

# ── Global policies ──────────────────────────────────────────────────────────
global_policies:
  default_heartbeat_interval_seconds: 30   # Applied when a bot has no policy
  circuit_breaker_threshold: 5             # Max consecutive heartbeat failures
  circuit_breaker_timeout_seconds: 60      # Reset window for circuit breaker

# ── Bot declarations ─────────────────────────────────────────────────────────
bots:
  - bot_id: "orchestrator_001"   # Unique within this manifest
    name: "Fleet Orchestrator"   # Display name (used for spawning)
    role: "orchestrator"         # Must match BotRole enum value
    enabled: true                # false → bot is despawned if it exists
    replicas: 1                  # Number of instances (0 = effectively disabled)

    capabilities:                # Capability names from BotInventoryLibrary registry
      - coordinate_tasks
      - manage_workflow

    heartbeat_policy:
      interval_seconds: 15
      max_missed: 3
      recovery_strategy: restart  # restart | alert | escalate

    governance:
      authority_band: "executive"
      max_resource_limits:
        cpu_percent: 20
        memory_mb: 512
      required_approvals: []      # List of authority gates required to change this bot

    dependencies: []              # bot_ids that must be started before this one

# ── Supervision topology ─────────────────────────────────────────────────────
# Maps supervisor bot_ids → list of child bot_ids.
# Wired into SupervisionTree by the reconciler.
supervision_topology:
  orchestrator_001:
    - expert_001
    - validator_001
```

### Field validation rules

| Field | Constraint |
|---|---|
| `replicas` | Must be ≥ 0 |
| `dependencies` | All listed `bot_id` values must exist in the same manifest |
| `capabilities` | If a capability registry is provided, all names must exist in it |
| Dependency graph | Must be acyclic (cycle → `ManifestValidationError`) |

---

## Reconciliation Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                       FleetReconciler                           │
│                                                                 │
│  load_manifest(m)                                               │
│       │                                                         │
│       ▼                                                         │
│  observe() ──► BotInventoryLibrary.get_bot_inventory()          │
│       │                                                         │
│       ▼                                                         │
│  diff()   ──► topological_sort(bots)                            │
│               for each bot in order:                            │
│                 • missing?   → SPAWN action                     │
│                 • extra?     → DESPAWN action                   │
│                 • drifted?   → UPDATE action                    │
│                 • always     → REGISTER_HEARTBEAT action        │
│               for each topology entry:                          │
│                 • WIRE_SUPERVISION action                        │
│       │                                                         │
│       ▼                                                         │
│  reconcile()                                                    │
│    publish FLEET_RECONCILIATION_STARTED                         │
│    for each action:                                             │
│      execute → publish per-action event                         │
│    publish FLEET_RECONCILED                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration Guide

### Minimal usage

```python
from bot_inventory_library import BotInventoryLibrary
from declarative_fleet_manager import ManifestLoader, FleetReconciler

inventory = BotInventoryLibrary()
manifest  = ManifestLoader.load_from_yaml("fleet_manifests/default_fleet.yaml")

reconciler = FleetReconciler(bot_inventory=inventory)
reconciler.load_manifest(manifest)
result = reconciler.reconcile()
print(result)
```

### With all integrations

```python
from bot_inventory_library import BotInventoryLibrary
from supervision_tree import SupervisionTree
from event_backbone import EventBackbone
from persistence_manager import PersistenceManager
from declarative_fleet_manager import ManifestLoader, FleetReconciler

inventory    = BotInventoryLibrary()
sup_tree     = SupervisionTree()
backbone     = EventBackbone()
persistence  = PersistenceManager()
manifest     = ManifestLoader.load_from_yaml("fleet_manifests/default_fleet.yaml")

reconciler = FleetReconciler(
    bot_inventory=inventory,
    supervision_tree=sup_tree,
    event_backbone=backbone,
    persistence_manager=persistence,
)
reconciler.load_manifest(manifest)
reconciler.reconcile()
```

### Wiring into a heartbeat tick

```python
from declarative_fleet_manager import FleetDriftDetector

detector = FleetDriftDetector(manifest=manifest, bot_inventory=inventory)

# Call this on every heartbeat tick:
def on_heartbeat_tick():
    drifts = detector.check_drift()
    if drifts:
        # Publish FLEET_DRIFT_DETECTED or trigger reconcile()
        reconciler.reconcile()
```

---

## Drift Detection

`FleetDriftDetector.check_drift()` returns a list of `DriftItem` objects:

| `drift_type` | Meaning |
|---|---|
| `missing` | A bot declared in the manifest does not exist in the inventory |
| `extra` | A bot exists in the inventory but is not declared in the manifest |
| `config_mismatch` | A bot exists but a field (e.g. `role`) differs from the declaration |

---

## Events Published

All events are published to `EventBackbone` using the `EventType` enum:

| Event | When |
|---|---|
| `FLEET_RECONCILIATION_STARTED` | At the start of every `reconcile()` call |
| `FLEET_BOT_SPAWNED` | After a missing bot is successfully spawned |
| `FLEET_BOT_DESPAWNED` | After an excess or disabled bot is despawned |
| `FLEET_BOT_UPDATED` | After a drifted bot configuration is corrected |
| `FLEET_RECONCILED` | At the end of every `reconcile()` call |
| `FLEET_DRIFT_DETECTED` | (reserved for `FleetDriftDetector` integration) |

---

## Example: 5-Bot Fleet

See [`fleet_manifests/default_fleet.yaml`](../fleet_manifests/default_fleet.yaml)
for a fully annotated example declaring:

1. **Fleet Orchestrator** — coordinates the whole fleet; no dependencies
2. **Architecture Expert** — depends on the orchestrator
3. **Security Validator** — depends on the orchestrator
4. **Performance Monitor** — depends on the orchestrator
5. **Compliance Auditor** — depends on orchestrator + validator

The `supervision_topology` section maps the orchestrator as the supervisor for all
four other bots, wiring the `SupervisionTree` automatically on `reconcile()`.

---

## API Reference

### `ManifestLoader`

| Method | Description |
|---|---|
| `load_from_yaml(path, capability_registry=None)` | Load + validate from YAML file |
| `load_from_json(path, capability_registry=None)` | Load + validate from JSON file |
| `load_from_dict(data, capability_registry=None)` | Load + validate from dict |

### `FleetReconciler`

| Method | Description |
|---|---|
| `load_manifest(manifest)` | Set the desired-state manifest |
| `observe()` | Snapshot current actual state |
| `diff()` | Compute `List[ReconciliationAction]` to converge state |
| `reconcile()` | Execute diff actions; returns status dict |
| `get_reconciliation_status()` | Progress of the last reconciliation run |

### `FleetDriftDetector`

| Method | Description |
|---|---|
| `check_drift()` | Returns `List[DriftItem]` describing current drift |
| `update_manifest(manifest)` | Replace the monitored manifest |

### `ReconciliationAction`

| Field | Type | Description |
|---|---|---|
| `action_id` | str | Auto-generated unique ID |
| `action_type` | `ActionType` | SPAWN / DESPAWN / UPDATE / REGISTER_HEARTBEAT / WIRE_SUPERVISION |
| `target_bot_id` | str | `bot_id` from the manifest |
| `details` | dict | Action-specific parameters |
| `status` | `ActionStatus` | pending / completed / failed |
