# Module Registry Strategy

This document defines how Murphy Core builds and maintains a truthful module registry.

## Purpose

Murphy System is too large to trust a single source of truth. The registry must merge multiple sources and expose effective status.

## Source inputs

Murphy Core registry should merge:

1. baseline inventory
   - `docs/capability_baseline.json`
2. operational manifest
   - `src/matrix_bridge/module_manifest.py`
3. file existence
   - actual repo files/packages
4. runtime wiring
   - what `src/murphy_core/app.py` and adapters actually load/use
5. effective capability state
   - whether a module is active, optional, disabled, unavailable, or drifted

## Registry record

Each module record should contain:
- `module_name`
- `source_path`
- `present_in_baseline`
- `present_in_manifest`
- `source_exists`
- `category`
- `runtime_role`
- `status`
- `commands`
- `persona`
- `emits`
- `consumes`
- `used_by_runtime`
- `effective_capability`
- `notes`

## Status vocabulary

Use only these values:
- `core`
- `adapter`
- `optional`
- `experimental`
- `deprecated`
- `declared_only`

### Definitions

#### core
Required for Murphy Core's canonical runtime path.

#### adapter
Legacy or external subsystem wrapped behind Murphy Core contracts.

#### optional
Real subsystem that is not required for boot or base request handling.

#### experimental
Implemented but not trusted as part of the canonical production path.

#### deprecated
Kept for compatibility but no longer preferred.

#### declared_only
Mentioned in manifest/baseline/docs but not verified as implemented and wired.

## Effective capability vocabulary

Separate from module status, capability state should use:
- `live`
- `available`
- `disabled`
- `missing_dependency`
- `not_wired`
- `drifted`

## Drift detection examples

Mark `drifted` when:
- module is listed in manifest but file cannot be found
- file exists but registry metadata missing
- file exists and metadata exists but runtime never references it while docs claim it is active
- runtime references a module not represented in registry inputs

## Core-first categorization

The first modules that should become `core` are:
- contracts
- registry
- providers
- rosetta
- gates
- routing
- planner
- executor
- tracing
- capabilities
- app

Likely first adapters:
- control_plane_separation
- deterministic_routing_engine
- ai_workflow_generator
- event_backbone
- integration_bus
- hitl_autonomy_controller
- security_plane
- self_codebase_swarm
- visual_swarm_builder
- delivery_adapters

## Registry maintenance rule

Whenever a module is:
- added
- adapted
- newly wired
- deprecated
- replaced
- found missing

update the registry logic and status notes.

## UI/API expectations

Expose registry and capability truth through endpoints such as:
- `/api/registry/modules`
- `/api/capabilities/effective`
- `/api/system/map`

The UI should never have to guess what is actually live.

## Minimal implementation plan

1. parse baseline module names
2. parse manifest metadata
3. resolve file existence
4. attach Murphy Core runtime usage flags
5. compute status + effective capability
6. expose sorted registry output

## Decision rule

When uncertain, prefer honesty:
- if not verified, mark `declared_only`
- if present but not in path, mark `experimental` or `optional`
- if wrapped by Murphy Core, mark `adapter`
- if essential to canonical request path, mark `core`
