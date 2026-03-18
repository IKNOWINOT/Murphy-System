# Vibe Code System

This document defines the no-drift operating system for building Murphy Core inside the Murphy System repository.

## Goal

Keep implementation, runtime wiring, registry truth, and documentation synchronized while evolving a very large codebase.

## Core rule

Every change must update **four linked layers** or explicitly state why one layer is unchanged:

1. **Contract layer**
   - typed models and invariants
2. **Runtime layer**
   - actual app wiring and execution path
3. **Registry layer**
   - module/capability truth
4. **Documentation layer**
   - design and usage truth

If those four layers drift, Murphy drifts.

## Canonical paths

Use these folders as the authoritative Murphy Core path:

- `src/murphy_core/`
- `docs/murphy_core/`

Legacy subsystems may remain elsewhere, but Murphy Core must reference them through explicit adapters and registry entries.

## Required linked files

These files must stay aligned:
- `docs/murphy_core/MURPHY_CORE_BUILD_PROMPT.md`
- `docs/murphy_core/VIBE_CODE_SYSTEM.md`
- `docs/murphy_core/MODULE_REGISTRY_STRATEGY.md`
- `docs/murphy_core/WEBAPP_PRODUCTION_TARGET.md`
- `src/murphy_core/contracts.py`
- `src/murphy_core/registry.py`
- `src/murphy_core/app.py`

## The no-drift loop

For every feature, fix, or migration:

### Step 1 — Name the layer touched
Choose one or more:
- inference
- rosetta
- gates
- routing
- planner
- execution
- tracing
- registry
- capabilities
- ui/api
- adapters

### Step 2 — Update the contract first
If behavior changes, update the typed contract before runtime implementation.

### Step 3 — Wire runtime second
Make runtime use the contract.

### Step 4 — Update registry truth
If a module was added, adapted, deprecated, or newly wired, update registry metadata and effective capability status.

### Step 5 — Update docs
Record the change in Murphy Core docs when it changes behavior, path ownership, or operational meaning.

## Module status vocabulary

Every module must be classified using the same vocabulary:
- `core`
- `adapter`
- `optional`
- `experimental`
- `deprecated`
- `declared_only`

Do not invent new status words without updating the registry strategy document.

## Request-path invariants

Every executable request must follow this path:

`request -> inference -> rosetta -> gates -> routing -> planner -> execution -> trace -> delivery`

If a path skips one of these layers, that must be visible and justified as an adapter or legacy exception.

## LLM safety invariant

Raw LLM/provider text must never directly trigger execution.

Provider output must always be compiled into typed control structures first.

## UI invariant

The UI must be able to answer:
- what happened?
- what route was chosen?
- what blocked execution?
- what modules are live?
- what capability state is real?

If the backend cannot answer those, the system is not production-ready.

## File preservation rule

Do not destructively overwrite legacy files unless:
- a copy exists,
- a replacement path exists,
- the registry marks the old file/module status clearly.

Prefer:
- wrappers
- adapters
- copied migrations
- compatibility shims with explicit deprecation notes

## Implementation style

Prefer strict, typed, inspectable structures over freeform glue.

Prefer:
- dataclasses / pydantic models
- explicit enums
- explicit service wiring
- explicit status outputs
- explicit route selection
- explicit trace emission

Avoid:
- magical global state
- duplicated runtime entrypoints
- undocumented provider calls
- undocumented module status
- hidden execution side paths

## PR / change checklist

Before considering a change complete, verify:
- contract updated if behavior changed
- runtime wired to new contract
- registry status updated if module/capability changed
- docs updated if user-facing or operator-facing truth changed
- trace still records route/gates/outcome
- no second runtime authority was introduced

## Drift alarms

Treat these as drift symptoms:
- manifest says a module exists but file cannot be found
- baseline inventory lists a module that runtime never references
- app claims a capability but capability endpoint cannot report it
- docs claim a runtime file that is only a compatibility shim
- UI endpoint exists but returns placeholder data for a supposedly core feature

## Preferred migration strategy

1. build core contracts
2. wrap legacy systems behind adapters
3. classify modules in registry
4. expose truthful capabilities
5. shrink legacy direct wiring over time

## Short operating slogan

**Contract first. Runtime second. Registry third. Docs always.**
