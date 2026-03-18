# Legacy Runtime Compatibility Shell

This document defines the compatibility-shell approach for making the legacy runtime subordinate to Murphy Core without a risky monolithic in-place edit.

## New file

- `src/runtime/legacy_runtime_compat_shell.py`

## Goal

Preserve the legacy runtime for all non-migrated routes while making:
- `/api/chat`
- `/api/execute`

delegate into Murphy Core.

## Why this approach was chosen

The legacy runtime file is extremely large and contains many unrelated endpoint families.

Directly editing the monolith in place is possible, but riskier than necessary for the current migration stage.

The compatibility shell provides a safer transition:
- override chat/execute at the top level
- mount the legacy runtime for everything else
- keep the old UI/API surface available
- make Murphy Core the orchestration authority for the most important flows

## Behavior

### Delegated routes
The shell owns:
- `POST /api/chat`
- `POST /api/execute`

These routes call:
- `LegacyChatExecuteDelegate.delegate_chat()`
- `LegacyChatExecuteDelegate.delegate_execute()`

which route into Murphy Core.

### Legacy passthrough
All other routes are served by the mounted legacy runtime app.

## Migration value

This is effectively the architectural outcome we wanted:
- the legacy runtime becomes a compatibility shell
- Murphy Core becomes the orchestrator for chat and execute

without needing a brittle one-shot surgery on `src/runtime/app.py`.

## Intended next adoption

1. add a startup path that uses the compatibility shell when legacy UI/API coverage is needed
2. mark legacy `/api/chat` and `/api/execute` as compatibility-delegated in runtime lineage / operator surfaces
3. progressively migrate more route families from legacy passthrough to core-owned paths

## Completion signal

This shell approach is successful when deployments that still need the legacy route surface can boot through the compatibility shell and have chat/execute fully delegated into Murphy Core.
