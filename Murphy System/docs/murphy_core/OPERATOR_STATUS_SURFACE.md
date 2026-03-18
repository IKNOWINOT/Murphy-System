# Operator Status Surface

This document defines the operator-facing status surface for Murphy Core v2.

## New file

- `src/murphy_core/operator_status.py`

## Goal

Expose a truthful, operator-usable snapshot of the live Murphy Core v2 path.

This goes beyond:
- raw module inventory
- generic health checks
- static docs

It should answer:
- which runtime factory is preferred?
- which provider path is preferred and available?
- which gate families are active?
- how many core/adapter/drifted modules exist?
- what compatibility ownership map is in effect?

## Why this matters

Murphy has many layers:
- legacy runtime
- original core bridge
- v2 bridge/startup
- provider adapters
- gate adapters
- registry truth
- compatibility ownership

Operators and the UI need one place that summarizes the real live path.

## Expected contents

### Runtime
- preferred factory
- environment
- default provider
- legacy-adapter preference

### Providers
- provider health list
- preferred provider

### Gates
- gate health list

### Registry
- total module count
- core modules
- adapter modules
- drifted modules

### System map
- canonical request path
- compatibility routes
- runtime hints

## Intended next adoption

The v2 app factory should eventually expose:
- `/api/operator/status`
- `/api/operator/summary`

so the frontend/admin UI can inspect the active runtime truth directly.

## Truth rule

Do not let the operator surface guess.
It must be built from the actual configured services and runtime map.
