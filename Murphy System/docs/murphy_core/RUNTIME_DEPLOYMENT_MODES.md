# Runtime Deployment Modes

This document defines the machine-readable deployment modes for Murphy runtime adoption.

## New file

- `src/murphy_core/runtime_deployment_modes.py`

## Goal

Expose the currently supported deployment choices in one structured place so that:
- operators know which mode is canonical
- migration tooling knows which mode is transitional
- UI/admin surfaces can explain the difference cleanly

## Current modes

### Direct core runtime-correct
- app target: `src/murphy_core/app_v3_runtime.py`
- startup: `src/runtime/main_core_v3_runtime_correct.py`
- category: `canonical`

Use this when validating or deploying the preferred Murphy Core backend directly.

### Legacy compat shell
- app target: `src/runtime/legacy_runtime_compat_shell.py`
- startup: `src/runtime/main_legacy_compat_shell.py`
- category: `transitional`

Use this when you still need broad legacy route/UI coverage but want `/api/chat` and `/api/execute` delegated into Murphy Core.

## Intended next adoption

The operator runtime surface should eventually include deployment mode summary so that operators can see:
- the canonical deployment mode
- the transitional shell mode
- which one they should choose for their current migration stage
