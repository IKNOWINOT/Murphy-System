# Runtime Migration Plan to Murphy Core

This plan defines how Murphy System moves from the legacy runtime to Murphy Core without breaking the current repo.

## Goal

Make `src/murphy_core/app.py` the canonical production server while preserving the existing runtime during migration.

## Current situation

The repo still has a very large legacy runtime in:
- `src/runtime/app.py`

Murphy Core now exists in:
- `src/murphy_core/`

A runtime bridge now exists in:
- `src/runtime/murphy_core_bridge.py`

## Migration rule

Do not attempt a one-shot rewrite of `src/runtime/app.py`.

Instead:
1. build Murphy Core as the truthful canonical path
2. bridge legacy entrypoints into Murphy Core where safe
3. migrate endpoint families incrementally
4. leave legacy-only surfaces in place until replaced or explicitly deprecated

## Recommended adoption sequence

### Phase 1
Use Murphy Core for new canonical endpoints:
- `/api/health`
- `/api/readiness`
- `/api/capabilities/effective`
- `/api/registry/modules`
- `/api/system/map`
- `/api/chat`
- `/api/execute`
- `/api/traces/recent`
- `/api/traces/{trace_id}`

### Phase 2
Add explicit startup entrypoint pointing to Murphy Core.
Examples:
- `uvicorn src.murphy_core.app:create_app`
- wrapper script that imports `src.runtime.murphy_core_bridge:create_bridge_app`

### Phase 3
Forward selected legacy endpoints into Murphy Core orchestration where response contracts are compatible.

### Phase 4
Mark legacy-only endpoint groups as:
- compatibility
- adapter-backed
- deprecated

### Phase 5
Retire duplicate runtime authority.

## What should not happen

Do not:
- duplicate inference logic in both runtimes
- duplicate gate evaluation policy in both runtimes
- maintain two conflicting registries
- invent separate routing truths for legacy and core

## Technical target

Legacy runtime should become one of these:
- a compatibility shell that mounts or forwards into Murphy Core
- a deprecated adapter surface for routes not yet migrated

## Immediate next code tasks

1. add a startup script for Murphy Core
2. add tests around Murphy Core endpoints
3. add env switch for bridge preference
4. document canonical production command
5. gradually port high-value legacy endpoints into core-owned modules

## Completion criteria

Migration is complete when:
- production server authority is unambiguous
- Murphy Core owns inference → rosetta → gates → routing → planning → execution → tracing
- registry/capability truth comes from Murphy Core
- legacy runtime is either a thin shim or retired
