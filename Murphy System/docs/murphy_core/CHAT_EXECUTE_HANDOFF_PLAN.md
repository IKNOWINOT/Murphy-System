# Chat and Execute Handoff Plan

This document defines how legacy chat and execute surfaces should delegate into Murphy Core.

## Goal

Ensure `/api/chat` and `/api/execute` do not remain independent orchestration authorities outside Murphy Core.

## New additive handoff module

A new helper exists at:
- `src/runtime/core_handoff.py`

It exposes explicit handoff helpers:
- `handoff_chat()`
- `handoff_execute()`

These helpers target the runtime bridge and, when configured to prefer core, delegate into Murphy Core.

## Why this exists

The legacy runtime is too large to safely rewrite in a single pass.

This handoff module provides:
- an explicit migration target
- a testable delegation mechanism
- one place to express the intended ownership rule

## Ownership rule

### Canonical owner
Murphy Core is the canonical owner of:
- chat orchestration
- execute orchestration
- route selection metadata
- gate summaries
- trace IDs

### Legacy role
Legacy runtime should become:
- a caller of the handoff helper, or
- a compatibility shell that forwards chat/execute into Murphy Core

## Expected payload behavior

### Chat
Input payload:
```json
{
  "message": "help me build a workflow",
  "session_id": "optional",
  "context": {}
}
```

Expected delegated output includes:
- `trace_id`
- `request_id`
- `route`
- `gate_results`
- `result`

### Execute
Input payload:
```json
{
  "task_description": "execute invoice workflow",
  "session_id": "optional",
  "parameters": {}
}
```

Expected delegated output includes:
- `trace_id`
- `request_id`
- `route`
- `gate_results`
- `result`

## Migration steps

1. keep using `src/runtime/main_core.py` as preferred startup
2. use `src/runtime/core_handoff.py` for explicit delegation behavior
3. patch legacy runtime chat/execute handlers to call the handoff helper
4. remove duplicate orchestration logic once stable

## Completion signal

This handoff plan is complete when legacy `/api/chat` and `/api/execute` no longer own independent orchestration behavior and instead forward into Murphy Core.
